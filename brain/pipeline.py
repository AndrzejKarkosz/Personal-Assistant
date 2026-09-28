"""The brain pipeline:

  ears (STT) -> shield (Jev: prompt injection?) -> acknowledgement ("On it, boss") + router (Jev) -> executor (Claude + module tools)
             -> guard (confirm side effects) -> voice (TTS) -> memory (session turns, tasks, log)

Every step emits events to the bus: the UI draws them on the brain graph and the activity log
keeps them forever.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from . import llm
from .atlas import BrainMap, MapBuilder
from .config import ROOT, Settings
from .events import ActivityLog, EventBus, new_id
from .executor import ApiExecutor, Guard, MCPHub
from .memory import MemoryStore, SessionManager, okf
from .modules import ModuleRegistry
from .proactive import ProactiveEngine
from .router import JevClient, Route, Router
from .voice import persona
from .voice.elevenlabs import ElevenLabs

log = logging.getLogger("alfred")

_BLOCKED = {"pl": "Tego nie wykonam - wygląda to na próbę manipulacji moimi instrukcjami.",
            "en": "I won't do that - it looks like an attempt to tamper with my instructions."}


class Brain:
    def __init__(self, settings: Settings | None = None, anthropic_client: Any = None,
                 hub: MCPHub | None = None):
        self.settings = settings or Settings.load()
        s = self.settings
        llm.prepare_environment(s)
        self.bus = EventBus(ActivityLog(s.path("logging.dir")))
        # Light calls (fallback router, session summaries): the plan via Agent SDK, or the API.
        self.anthropic = anthropic_client if anthropic_client is not None else llm.light_client(s)
        self.registry = ModuleRegistry(ROOT / "modules")
        self.store = MemoryStore(s.path("memory.dir"))
        self.sessions = SessionManager(self.store, s, self.anthropic, self.bus)
        self.hub = hub or MCPHub(s.path("mcp_config"))
        self.map = BrainMap(s.path("map.dir"))
        self.jev = JevClient(s.jev_key, s.get("router.jev_url"), s.get("router.jev_model"),
                             float(s.get("router.timeout_s", 4.0)))
        self.router = Router(self.map, self.jev, s, self.anthropic)
        self.voice = ElevenLabs(s, ROOT / "data" / "tts_cache")
        self.guard = Guard(self.bus)
        common = (s, self.registry, self.map, self.hub, self.store, self.guard, self.bus)
        if llm.backend(s) == "subscription" and anthropic_client is None:
            from .executor.agent import SubscriptionExecutor
            self.executor = SubscriptionExecutor(*common, tts=self.voice)
        else:
            self.executor = ApiExecutor(anthropic_client if anthropic_client is not None else self.anthropic,
                                        *common, tts=self.voice)
        self.proactive = ProactiveEngine(self, s.path("memory.dir").parent / "proactive_state.json")

    def rebuild_map(self) -> dict[str, Any]:
        """Compile the brain map from modules + live tools + knowledge topics, then reload it."""
        self.registry.reload()
        summary = MapBuilder(self.settings.path("map.dir"), self.registry, self.hub,
                             self.settings.get("map.topic_sources") or []).build()
        self.map.reload()
        self.bus.emit("map_built", "map", **{k: v for k, v in summary.items() if k != "changes"},
                      changes=summary["changes"][:50])
        return summary

    # --------------------------------------------------------------- lifecycle
    async def start(self, with_scheduler: bool = True) -> None:
        self.bus.emit("brain_start", "brain", keys=self.settings.status())
        await self.hub.start()
        self.bus.emit("mcp_status", "mcp", servers=self.hub.status())
        self.rebuild_map()
        if with_scheduler and self.settings.get("proactive.enabled", True):
            self.proactive.start()

    async def stop(self) -> None:
        self.proactive.shutdown()
        await self.sessions.close()
        await self.hub.stop()
        self.bus.emit("brain_stop", "brain")

    # ------------------------------------------------------------------ input
    async def handle_audio(self, audio: bytes, filename: str = "speech.webm") -> str | None:
        request_id = new_id("r-")
        self.bus.emit("listening", "ears", request_id, bytes=len(audio))
        try:
            transcript = await self.voice.transcribe(audio, filename)
        except Exception as exc:  # noqa: BLE001
            self.bus.emit("error", "ears", request_id, message=f"STT failed: {exc}")
            return None
        if transcript is None or not transcript.text:
            self.bus.emit("error", "ears", request_id, message="Nothing was transcribed.")
            return None
        return await self.handle_text(transcript.text, language=transcript.language, request_id=request_id)

    async def handle_text(self, text: str, language: str | None = None, source: str = "user",
                          request_id: str | None = None, module_hint: str | None = None) -> str:
        request_id = request_id or new_id("r-")
        text = text.strip()

        # An answer to a pending "shall I proceed?" question goes to the guard, not the router.
        if source == "user" and self.guard.pending:
            approved = await self.router.is_yes(text, self.guard.pending.question)
            if approved is not None:
                self.bus.emit("transcript", "ears", request_id, text=text, source=source, confirmation=True)
                self.guard.resolve(approved)
                return ""

        session = await self.sessions.get()
        if source == "user":
            session.language = language if language in ("pl", "en") else persona.detect_language(
                text, session.language or self.settings.get("assistant.default_language", "pl"))
        lang = session.language
        self.bus.emit("transcript", "ears", request_id, session.id, text=text, language=lang, source=source)

        # 0. Shield - every user utterance is checked for prompt injection (Jev) before Claude sees it.
        #    The router starts at the same time; its answer is only used once the shield has passed.
        routing = asyncio.create_task(self._route(text, session, module_hint))
        ack_task = None
        ack_after = float(self.settings.get("voice.ack_after_s", 1.5))
        if source == "user":
            verdict = await self.router.is_injection(text, session.recent_text(4))
            self.bus.emit("shield", "shield", request_id, session.id, **verdict)
            if verdict["breach"]:
                routing.cancel()
                reply = _BLOCKED.get(lang, _BLOCKED["en"])
                self.bus.emit("blocked", "shield", request_id, session.id, text=text)
                self.bus.emit("answer", "voice", request_id, session.id, text=reply,
                              audio_b64=await self.voice.synthesize(reply), language=lang, model="shield",
                              usage={}, source=source)
                return reply
            # 1. "Of course, boss, checking" - only if the answer takes longer than voice.ack_after_s.
            ack_task = asyncio.create_task(self._acknowledge(request_id, session.id, lang, ack_after))

        # 2. Router - one fast typed decision over the whole brain map.
        route = await routing
        route_usage = route.usage or {}
        router_tokens = int(route_usage.get("input_tokens", 0)) + int(route_usage.get("output_tokens", 0))
        session.add_usage({"jev": router_tokens})
        self.bus.emit("classified", "router", request_id, session.id, **route.to_dict())
        if ack_task and route.module == "smalltalk":
            ack_task.cancel()   # conversation needs no "checking, boss"

        # 3. Executor - Claude with only this route's tools.
        result = await self.executor.run(text, route, session, request_id)
        if ack_task:
            if ack_after > 0:
                ack_task.cancel()   # the answer is ready - a late "on it" would only get in the way
            await asyncio.gather(ack_task, return_exceptions=True)  # never let the answer overtake a started ack

        # 4. Memory - remember the turn and what changed.
        session.add("user", text if source == "user" else f"(proactive) {text[:200]}", route.module)
        session.add("assistant", result.text, route.module)
        session.actions.extend(result.actions)
        # Jev is billed by its own provider, so only the Claude router fallback has a dollar figure.
        cost = None if result.cost_usd is None else result.cost_usd + (route_usage.get("cost_usd") or 0)
        session.add_usage({**result.usage, "cost_usd": cost or 0})

        # 5. Voice.
        audio = await self.voice.synthesize(result.text)
        self.bus.emit("answer", "voice", request_id, session.id, text=result.text, audio_b64=audio,
                      language=lang, model=result.model, usage={**result.usage, "router": router_tokens},
                      cost_usd=cost, actions=result.actions,
                      tools=result.tools_used, source=source)
        return result.text

    async def _route(self, text: str, session, module_hint: str | None) -> Route:
        if module_hint and module_hint in self.map.modules:
            route = Route(module=module_hint, confidence=1.0, probabilities={module_hint: 1.0}, source="hint")
            self.router.apply_policy(route)
            return route
        return await self.router.classify(text, context=session.recent_text(4))

    async def _acknowledge(self, request_id: str, session_id: str, lang: str, delay: float = 0) -> None:
        if delay > 0:
            await asyncio.sleep(delay)
        phrase = persona.ack_phrase(self.settings, lang)
        audio = await self.voice.synthesize(phrase)
        self.bus.emit("ack", "voice", request_id, session_id, text=phrase, audio_b64=audio, language=lang)

    # ------------------------------------------------------------------- graph
    def graph(self) -> dict[str, Any]:
        """Nodes and edges for the brain view: the pipeline core, the compiled brain map and the rest of
        the brain's anatomy (code, tests, routines, persona, memory)."""
        core = [
            ("ears", "Ears (speech-to-text)"), ("shield", "Shield (Jev)"), ("router", "Router (Jev)"), ("executor", "Executor (Claude)"),
            ("guard", "Guard"), ("voice", "Voice (Alfred)"), ("memory", "Session memory (OKF)"),
            ("proactive", "Proactive"),
        ]
        nodes = [{"id": i, "label": l, "kind": "core"} for i, l in core]
        edges = [{"source": a, "target": b, "rel": "flow"} for a, b in (
            ("ears", "shield"), ("shield", "router"), ("shield", "voice"), ("router", "executor"), ("executor", "guard"), ("executor", "voice"),
            ("executor", "memory"), ("proactive", "router"), ("memory", "executor"), ("mcp:alfred", "memory"))]
        m = self.map.graph()
        more_nodes, more_edges = self._anatomy()
        nodes += m["nodes"] + more_nodes
        known = {n["id"] for n in nodes}
        edges = [e for e in edges + more_edges if e["source"] in known and e["target"] in known] + m["edges"]
        return {"nodes": nodes, "edges": edges, "backend": self.executor.backend}

    def _anatomy(self) -> tuple[list[dict], list[dict]]:
        """Brain-view nodes beyond the map. `group` is the folder the UI shows them in."""
        nodes: list[dict] = []
        edges: list[dict] = []

        def node(nid: str, label: str, kind: str, description: str = "", **extra: Any) -> None:
            nodes.append({"id": nid, "label": label, "kind": kind, "description": description, **extra})

        for p in sorted((ROOT / "brain").iterdir()):
            files = sorted(f.name for f in p.glob("*.py") if f.name != "__init__.py") if p.is_dir() else [p.name]
            if not p.name.startswith("_") and files and (p.is_dir() or p.suffix == ".py"):
                node(f"repo:{p.stem}", f"brain/{p.name}", "repo", ", ".join(files))
        for f in sorted((ROOT / "tests").glob("test_*.py")):
            names = re.findall(r"^(?:async )?def (test_\w+)", f.read_text(encoding="utf-8"), re.M)
            node(f"test:{f.stem}", f.name, "test", f"{len(names)} testów: " + ", ".join(names))
            edges.append({"source": f"test:{f.stem}", "target": f"repo:{f.stem[5:]}", "rel": "tests"})
        for r in self.proactive.routines():
            node(f"routine:{r['id']}", r["id"], "routine", f"{r['schedule']} · {r['prompt']}", prompt=r["prompt"])
            edges += [{"source": "proactive", "target": f"routine:{r['id']}", "rel": "runs"},
                      {"source": f"routine:{r['id']}", "target": f"module:{r.get('module')}", "rel": "runs in"}]

        meta, body = persona.load()
        address, acks = meta.get("address") or {}, meta.get("acks") or {}
        facets = [("Tożsamość", "Imię", meta.get("name")), ("Tożsamość", "Szef", meta.get("user_name")),
                  ("Tożsamość", "Zwrot PL", address.get("pl")), ("Tożsamość", "Zwrot EN", address.get("en")),
                  ("Zwroty", "Potwierdzenia PL", " · ".join(acks.get("pl") or [])),
                  ("Zwroty", "Potwierdzenia EN", " · ".join(acks.get("en") or [])),
                  ("Zwroty", "Pytanie o zgodę", (meta.get("confirm") or {}).get("pl"))]
        for section in re.split(r"^# ", body, flags=re.M)[1:]:
            title, _, text = section.partition("\n")
            facets.append(("Charakter", title, text))
        for i, (group, label, text) in enumerate(facets):
            node(f"persona:{i}", label.strip(), "persona", str(text or "").strip()[:500], group=group)

        for t in self.store.list_tasks("open"):
            node(f"task:{t.id}", t.title, "memory", t.status + (f", termin {t.due}" if t.due else ""),
                 group="Zadania", mem_path=f"tasks/{t.id}.md")
        for i, (meta, _) in enumerate(self.store.recent_sessions(8)):
            node(f"session:{i}", meta.get("title", ""), "memory", meta.get("description", ""), group="Sesje")
        for f in sorted((self.store.root / "facts").rglob("*.md"))[:40]:   # ponytail: first 40, newest first if it grows
            rel = f.relative_to(self.store.root).as_posix()
            fact, _ = okf.read(f)
            node(f"fact:{rel}", fact.get("title", f.stem), "memory", fact.get("description", ""),
                 group="Fakty", mem_path=rel)
        return nodes, edges
