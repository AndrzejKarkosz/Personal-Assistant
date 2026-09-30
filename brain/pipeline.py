from __future__ import annotations

import asyncio
import logging
import re
from datetime import timedelta
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

# Chat mode: he reads on screen instead of listening, so the spoken-length rules of the persona step aside.
CHAT_NOTE = ("<reply_mode>text chat - the user reads your answer on screen, nothing is spoken. Answer fully and "
             "in depth, like a knowledgeable assistant explaining a topic. Use Markdown (headings, lists, tables, "
             "code blocks, links) where it helps. The 'How you speak' rules about length, markdown and URLs do "
             "not apply here; keep your character.</reply_mode>\n\n")

_BLOCKED = {"pl": "Tego nie wykonam - wygląda to na próbę manipulacji moimi instrukcjami.",
            "en": "I won't do that - it looks like an attempt to tamper with my instructions."}


class Brain:
    def __init__(self, settings: Settings | None = None, anthropic_client: Any = None,
                 hub: MCPHub | None = None):
        self.settings = settings or Settings.load()
        s = self.settings
        llm.prepare_environment(s)
        self.bus = EventBus(ActivityLog(s.path("logging.dir")))
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
        extra = {"tts": self.voice, "shield": self.router.check_action}
        if llm.backend(s) == "subscription" and anthropic_client is None:
            from .executor.agent import SubscriptionExecutor
            self.executor = SubscriptionExecutor(*common, **extra)
        else:
            self.executor = ApiExecutor(anthropic_client if anthropic_client is not None else self.anthropic,
                                        *common, **extra)
        self.proactive = ProactiveEngine(self, s.path("memory.dir").parent / "proactive_state.json")
        self.executor.routines = self.proactive.routines

    def rebuild_map(self) -> dict[str, Any]:
        self.registry.reload()
        summary = MapBuilder(self.settings.path("map.dir"), self.registry, self.hub,
                             self.settings.get("map.topic_sources") or []).build()
        self.map.reload()
        self.bus.emit("map_built", "map", **{k: v for k, v in summary.items() if k != "changes"},
                      changes=summary["changes"][:50])
        return summary

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

    async def handle_audio(self, audio: bytes, filename: str = "speech.webm") -> str | None:
        request_id = new_id("r-")
        self.bus.emit("listening", "ears", request_id, bytes=len(audio))
        try:
            transcript = await self.voice.transcribe(audio, filename)
        except Exception as exc:
            self.bus.emit("error", "ears", request_id, message=f"STT failed: {exc}")
            return None
        if transcript is None or not transcript.text:
            self.bus.emit("error", "ears", request_id, message="Nothing was transcribed.")
            return None
        return await self.handle_text(transcript.text, language=transcript.language, request_id=request_id)

    async def handle_text(self, text: str, language: str | None = None, source: str = "user",
                          request_id: str | None = None, module_hint: str | None = None, mode: str = "voice") -> str:
        """`mode`: "voice" (short spoken answers) or "chat" (long written answers, no TTS)."""
        request_id = request_id or new_id("r-")
        chat = mode == "chat"
        text = text.strip()

        if source == "user" and self.guard.pending:
            approved = await self.router.is_yes(text, self.guard.pending.question)
            if approved is not None:
                self.bus.emit("transcript", "ears", request_id, text=text, source=source, confirmation=True)
                self.guard.resolve(approved)
                return ""

        session = await self.sessions.get()
        if source == "user":
            session.language = self.settings.get("assistant.reply_language") or (
                language if language in ("pl", "en") else persona.detect_language(
                    text, session.language or self.settings.get("assistant.default_language", "pl")))
        lang = session.language
        self.bus.emit("transcript", "ears", request_id, session.id, text=text, language=lang, source=source, mode=mode)
        idle = self.proactive.idle()
        self.proactive.touch()

        routing = asyncio.create_task(self._route(text, session, module_hint))
        if source == "user":
            verdict = await self.router.is_injection(text, session.recent_text(4))
            self.bus.emit("shield", "shield", request_id, session.id, **verdict)
            if verdict["breach"]:
                routing.cancel()
                self.bus.emit("blocked", "shield", request_id, session.id, text=text)
                return await self.say(_BLOCKED.get(lang, _BLOCKED["en"]), source, request_id, session.id, lang,
                                      model="shield", mode=mode)
            after = timedelta(minutes=float(self.settings.get("assistant.welcome_back.after_minutes", 120)))
            if idle and idle >= after and not chat:
                await self.welcome_back(lang, request_id, session.id)

        route = await routing
        route_usage = route.usage or {}
        router_tokens = int(route_usage.get("input_tokens", 0)) + int(route_usage.get("output_tokens", 0))
        session.add_usage({"jev": router_tokens})
        self.bus.emit("classified", "router", request_id, session.id, **route.to_dict())

        result = await self.executor.run(CHAT_NOTE + text if chat else text, route, session, request_id)

        session.add("user", text if source == "user" else f"(proactive) {text[:200]}", route.module)
        session.add("assistant", result.text, route.module)
        session.actions.extend(result.actions)
        cost = None if result.cost_usd is None else result.cost_usd + (route_usage.get("cost_usd") or 0)
        session.add_usage({**result.usage, "cost_usd": cost or 0})

        audio = None if chat else await self.voice.synthesize(result.text)
        self.bus.emit("answer", "voice", request_id, session.id, text=result.text, audio_b64=audio, mode=mode,
                      language=lang, model=result.model, usage={**result.usage, "router": router_tokens},
                      cost_usd=cost, actions=result.actions,
                      tools=result.tools_used, source=source)
        return result.text

    async def say(self, text: str, source: str, request_id: str | None = None, session_id: str | None = None,
                  lang: str | None = None, model: str = "static", interim: bool = False, mode: str = "voice") -> str:
        """Speak a fixed line - TTS only, no LLM. `interim`: the real answer is still coming."""
        self.proactive.touch()
        self.bus.emit("answer", "voice", request_id or new_id("r-"), session_id, text=text,
                      audio_b64=None if mode == "chat" else await self.voice.synthesize(text),
                      language=lang or self.settings.get("assistant.default_language", "pl"),
                      model=model, usage={}, source=source, interim=interim, mode=mode)
        return text

    async def welcome_back(self, lang: str | None = None, request_id: str | None = None,
                           session_id: str | None = None) -> str:
        lang = lang or self.settings.get("assistant.default_language", "pl")
        texts = self.settings.get("assistant.welcome_back") or {}
        return await self.say(texts.get(lang) or texts.get("pl") or "Witaj z powrotem.", "welcome",
                              request_id, session_id, lang, interim=request_id is not None)

    async def _route(self, text: str, session, module_hint: str | None) -> Route:
        if module_hint and module_hint in self.map.modules:
            route = Route(module=module_hint, confidence=1.0, probabilities={module_hint: 1.0}, source="hint")
            self.router.apply_policy(route)
            self.router.force(route, text)
            return route
        return await self.router.classify(text, context=session.recent_text(4))

    def graph(self) -> dict[str, Any]:
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
        address = meta.get("address") or {}
        facets = [("Tożsamość", "Imię", meta.get("name")), ("Tożsamość", "Szef", meta.get("user_name")),
                  ("Tożsamość", "Zwrot PL", address.get("pl")), ("Tożsamość", "Zwrot EN", address.get("en")),
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
        for f in sorted((self.store.root / "facts").rglob("*.md"))[:40]:
            rel = f.relative_to(self.store.root).as_posix()
            fact, _ = okf.read(f)
            node(f"fact:{rel}", fact.get("title", f.stem), "memory", fact.get("description", ""),
                 group="Fakty", mem_path=rel)
        return nodes, edges
