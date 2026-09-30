"""The Brain: wires all the parts together and handles one request from start to finish.

    audio -> ears (voice.py) -> shield + router (router.py) -> executor (executor.py) -> voice -> memory

handle_text() is the whole story of one request; read it top to bottom.
"""
from __future__ import annotations

import ast
import re
from datetime import timedelta
from typing import Any

from . import llm, okf, persona
from .atlas import BrainMap, build_map
from .config import ROOT, Settings
from .events import ActivityLog, EventBus, new_id
from .executor import Executor, Guard
from .mcp_hub import MCPHub
from .memory import MemoryStore, Session, SessionManager
from .modules import ModuleRegistry
from .router import JevClient, Route, Router
from .scheduler import ProactiveEngine
from .voice import ElevenLabs

# Chat mode: the answer is read on screen, so the spoken-length rules of the persona step aside.
CHAT_NOTE = ("<reply_mode>text chat - the user reads your answer on screen, nothing is spoken. Answer fully and in "
             "depth, like a knowledgeable assistant explaining a topic. Use Markdown (headings, lists, tables, code "
             "blocks, links) where it helps. The 'How you speak' rules about length, markdown and URLs do not apply "
             "here; keep your character.</reply_mode>\n\n")
BLOCKED = {"pl": "Tego nie wykonam - wygląda to na próbę manipulacji moimi instrukcjami.",
           "en": "I won't do that - it looks like an attempt to tamper with my instructions."}

class Brain:
    def __init__(self, settings: Settings | None = None, hub: MCPHub | None = None):
        s = self.settings = settings or Settings.load()
        llm.hide_api_key()
        self.bus = EventBus(ActivityLog(s.path("logging.dir")))
        self.registry = ModuleRegistry(ROOT / "modules")
        self.store = MemoryStore(s.path("memory.dir"))
        self.sessions = SessionManager(self.store, s, self.bus)
        self.hub = hub or MCPHub(s.path("mcp_config"))
        self.map = BrainMap(s.path("map.dir"))
        self.router = Router(self.map, JevClient(s.jev_key, s.get("router.jev_url"), s.get("router.jev_model"),
                                                 float(s.get("router.timeout_s", 4.0))), s)
        self.voice = ElevenLabs(s, ROOT / "data" / "tts_cache")
        self.guard = Guard(self.bus)
        self.proactive = ProactiveEngine(self, s.path("memory.dir").parent / "proactive_state.json")
        self.executor = Executor(s, self.registry, self.map, self.hub, self.store, self.guard, self.bus,
                                 tts=self.voice, shield=self.router.check_action, routines=self.proactive.routines)

    async def start(self, with_scheduler: bool = True) -> None:
        self.bus.emit("brain_start", "brain", keys=self.settings.keys())
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

    def rebuild_map(self) -> dict[str, Any]:
        self.registry.reload()
        summary = build_map(self.settings.path("map.dir"), self.registry, self.hub,
                            self.settings.get("map.topic_sources") or [])
        self.map.reload()
        self.bus.emit("map_built", "map", **{**summary, "changes": summary["changes"][:50]})
        return summary

    # ---- one request ------------------------------------------------------------------------------------------

    async def handle_audio(self, audio: bytes, filename: str = "speech.webm") -> str | None:
        request_id = new_id("r-")
        self.bus.emit("listening", "ears", request_id, bytes=len(audio))
        try:
            heard = await self.voice.transcribe(audio, filename)
        except Exception as exc:
            self.bus.emit("error", "ears", request_id, message=f"STT failed: {exc}")
            return None
        if not heard or not heard.text:
            self.bus.emit("error", "ears", request_id, message="Nothing was transcribed.")
            return None
        return await self.handle_text(heard.text, language=heard.language, request_id=request_id)

    async def handle_text(self, text: str, language: str | None = None, source: str = "user",
                          request_id: str | None = None, module_hint: str | None = None, mode: str = "voice") -> str:
        """source: user | routine | proactive.  mode: "voice" (short spoken answer) or "chat" (long, written)."""
        request_id, text, chat, from_user = request_id or new_id("r-"), text.strip(), mode == "chat", source == "user"

        # 1. Alfred is waiting for a yes/no? Then this is the answer, not a new request.
        if from_user and self.guard.pending:
            approved = await self.router.is_yes(text, self.guard.pending["question"])
            if approved is not None:
                self.bus.emit("transcript", "ears", request_id, text=text, source=source, confirmation=True)
                self.guard.resolve(approved)
                return ""

        # 2. Session and language.
        session = await self.sessions.get()
        if from_user:
            spoken = language if language in ("pl", "en") else persona.detect_language(
                text, session.language or self.settings.get("assistant.default_language", "pl"))
            session.language = self.settings.get("assistant.reply_language") or spoken
        lang = session.language
        self.bus.emit("transcript", "ears", request_id, session.id, text=text, language=lang, source=source, mode=mode)
        idle = self.proactive.idle()
        self.proactive.touch()

        # 3. Shield (Jev only): nothing goes anywhere until it passes. Jev down -> do nothing at all.
        if from_user:
            verdict = await self.router.is_injection(text, session.recent_text(4))
            self.bus.emit("shield", "shield", request_id, session.id, **verdict)
            if verdict["source"] == "closed":
                self.bus.emit("error", "shield", request_id, session.id,
                              message="Jev nie odpowiada - tarcza nie sprawdziła prośby, nic nie zrobiłem.")
                return ""
            if verdict["breach"]:
                self.bus.emit("blocked", "shield", request_id, session.id, text=text)
                return await self.say(BLOCKED.get(lang, BLOCKED["en"]), source, request_id, session.id, lang,
                                      model="shield", mode=mode)
            away = timedelta(minutes=float(self.settings.get("assistant.welcome_back.after_minutes", 120)))
            if idle and idle >= away and not chat:
                await self.welcome_back(lang, request_id, session.id)

        # 4. Route: which module and tools.
        route = await self._route(text, session, module_hint)
        router_tokens = int(route.usage.get("input") or 0) + int(route.usage.get("output") or 0)
        session.add_usage({"jev": router_tokens})
        self.bus.emit("classified", "router", request_id, session.id, **route.to_dict())

        # 5. Claude does the work.
        result = await self.executor.run(CHAT_NOTE + text if chat else text, route, session, request_id)

        # 6. Remember, speak, report.
        session.add("user", text if from_user else f"(proactive) {text[:200]}", route.module)
        session.add("assistant", result.text, route.module)
        session.actions.extend(result.actions)
        cost = None if result.cost_usd is None else result.cost_usd + (route.usage.get("cost_usd") or 0)
        session.add_usage({**result.usage, "cost_usd": cost or 0})
        audio = None if chat else await self.voice.synthesize(result.text)
        self.bus.emit("answer", "voice", request_id, session.id, text=result.text, audio_b64=audio, mode=mode,
                      language=lang, model=result.model, usage={**result.usage, "router": router_tokens},
                      cost_usd=cost, actions=result.actions, tools=result.tools_used, source=source)
        return result.text

    async def _route(self, text: str, session: Session, module_hint: str | None) -> Route:
        if module_hint in self.map.modules:     # routines and reminders know their module already
            route = Route(module=module_hint, confidence=1.0, probabilities={module_hint: 1.0}, source="hint")
            self.router.apply_policy(route)
            self.router.force(route, text)
            return route
        return await self.router.classify(text, context=session.recent_text(4))

    async def say(self, text: str, source: str, request_id: str | None = None, session_id: str | None = None,
                  lang: str | None = None, model: str = "static", interim: bool = False, mode: str = "voice") -> str:
        """Speak a fixed line - voice only, no Claude. `interim`: the real answer is still coming."""
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

    # ---- the 3D brain in the UI -------------------------------------------------------------------------------

    def graph(self) -> dict[str, Any]:
        """Everything the UI draws: the pipeline, the brain map, the code, tests, routines, persona and memory."""
        nodes = [{"id": i, "label": l, "kind": "core"} for i, l in [
            ("ears", "Ears (speech-to-text)"), ("shield", "Shield (Jev)"), ("router", "Router (Jev)"),
            ("executor", "Executor (Claude)"), ("guard", "Guard"), ("voice", "Voice (Alfred)"),
            ("memory", "Session memory (OKF)"), ("proactive", "Proactive")]]
        edges = [{"source": a, "target": b, "rel": "flow"} for a, b in [
            ("ears", "shield"), ("shield", "router"), ("shield", "voice"), ("router", "executor"), ("executor", "guard"),
            ("executor", "voice"), ("executor", "memory"), ("proactive", "router"), ("memory", "executor"),
            ("mcp:alfred", "memory")]]

        def node(nid: str, label: str, kind: str, description: str = "", **extra: Any) -> None:
            nodes.append({"id": nid, "label": label, "kind": kind, "description": description, **extra})

        for f in sorted((ROOT / "brain").glob("*.py")):
            if not f.name.startswith("_"):
                doc = ast.get_docstring(ast.parse(f.read_text(encoding="utf-8"))) or ""
                node(f"repo:{f.stem}", f"brain/{f.name}", "repo", doc.split("\n\n")[0])
        for f in sorted((ROOT / "tests").glob("test_*.py")):
            names = re.findall(r"^(?:async )?def (test_\w+)", f.read_text(encoding="utf-8"), re.M)
            node(f"test:{f.stem}", f.name, "test", f"{len(names)} testów: " + ", ".join(names))
            edges.append({"source": f"test:{f.stem}", "target": f"repo:{f.stem[5:]}", "rel": "tests"})
        for r in self.proactive.routines():
            node(f"routine:{r['id']}", r["id"], "routine", f"{r['schedule']} · {r['prompt']}", prompt=r["prompt"])
            edges += [{"source": "proactive", "target": f"routine:{r['id']}", "rel": "runs"},
                      {"source": f"routine:{r['id']}", "target": f"module:{r.get('module')}", "rel": "runs in"}]

        meta, body = persona.load()
        facets = [("Tożsamość", "Imię", meta.get("name")), ("Tożsamość", "Szef", meta.get("user_name")),
                  ("Tożsamość", "Zwrot PL", (meta.get("address") or {}).get("pl")),
                  ("Tożsamość", "Zwrot EN", (meta.get("address") or {}).get("en")),
                  ("Zwroty", "Pytanie o zgodę", (meta.get("confirm") or {}).get("pl"))]
        for section in re.split(r"^# ", body, flags=re.M)[1:]:     # each "# Heading" of the persona body
            title, _, text = section.partition("\n")
            facets.append(("Charakter", title, text))
        for i, (group, label, text) in enumerate(facets):
            node(f"persona:{i}", label.strip(), "persona", str(text or "").strip()[:500], group=group)

        for t in self.store.list_tasks("open"):
            node(f"task:{t.id}", t.title, "memory", t.status + (f", termin {t.due}" if t.due else ""),
                 group="Zadania", mem_path=f"tasks/{t.id}.md")
        for i, (m, _) in enumerate(self.store.recent_sessions(8)):
            node(f"session:{i}", m.get("title", ""), "memory", m.get("description", ""), group="Sesje")
        for f in sorted((self.store.root / "facts").rglob("*.md"))[:40]:
            fact, rel = okf.read(f)[0], f.relative_to(self.store.root).as_posix()
            node(f"fact:{rel}", fact.get("title", f.stem), "memory", fact.get("description", ""), group="Fakty",
                 mem_path=rel)

        brain_map = self.map.graph()
        nodes += brain_map["nodes"]
        known = {n["id"] for n in nodes}
        edges = [e for e in edges if e["source"] in known and e["target"] in known] + brain_map["edges"]
        return {"nodes": nodes, "edges": edges, "backend": "subscription"}
