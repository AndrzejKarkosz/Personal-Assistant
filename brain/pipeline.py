"""The brain pipeline:

  ears (STT) -> router (Jev) -> acknowledgement ("On it, boss") -> executor (Claude + module tools)
             -> guard (confirm side effects) -> voice (TTS) -> memory (session turns, tasks, log)

Every step emits events to the bus: the UI draws them on the brain graph and the activity log
keeps them forever.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from . import llm
from .atlas import BrainMap, MapBuilder
from .config import ROOT, Settings
from .events import ActivityLog, EventBus, new_id
from .executor import ApiExecutor, Guard, MCPHub
from .memory import MemoryStore, SessionManager
from .modules import ModuleRegistry
from .proactive import ProactiveEngine
from .router import JevClient, Route, Router
from .voice import persona
from .voice.elevenlabs import ElevenLabs

log = logging.getLogger("alfred")


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

        # 1. Router - one fast typed decision.
        if module_hint and module_hint in self.map.modules:
            route = Route(module=module_hint, confidence=1.0, probabilities={module_hint: 1.0}, source="hint")
            self.router.apply_policy(route)
        else:
            route = await self.router.classify(text, context=session.recent_text(4))
        session.add_usage({"jev": int((route.usage or {}).get("input_tokens", 0))
                           + int((route.usage or {}).get("output_tokens", 0))})
        self.bus.emit("classified", "router", request_id, session.id, **route.to_dict())

        # 2. Instant acknowledgement while the real work starts.
        lead = self.registry.get(route.module)
        ack_task = None
        if source == "user" and lead and lead.acknowledge and not route.clarify:
            ack_task = asyncio.create_task(self._acknowledge(request_id, session.id, lang))

        # 3. Executor - Claude with only this route's tools.
        result = await self.executor.run(text, route, session, request_id)
        if ack_task:
            await ack_task      # never let the answer overtake the acknowledgement

        # 4. Memory - remember the turn and what changed.
        session.add("user", text if source == "user" else f"(proactive) {text[:200]}", route.module)
        session.add("assistant", result.text, route.module)
        session.actions.extend(result.actions)
        session.add_usage(result.usage)

        # 5. Voice.
        audio = await self.voice.synthesize(result.text)
        self.bus.emit("answer", "voice", request_id, session.id, text=result.text, audio_b64=audio,
                      language=lang, model=result.model, usage=result.usage, actions=result.actions,
                      tools=result.tools_used, source=source)
        return result.text

    async def _acknowledge(self, request_id: str, session_id: str, lang: str) -> None:
        phrase = persona.ack_phrase(self.settings, lang)
        audio = await self.voice.synthesize(phrase)
        self.bus.emit("ack", "voice", request_id, session_id, text=phrase, audio_b64=audio, language=lang)

    # ------------------------------------------------------------------- graph
    def graph(self) -> dict[str, Any]:
        """Nodes and edges for the brain view: the pipeline core plus the compiled brain map."""
        core = [
            ("ears", "Ears (speech-to-text)"), ("router", "Router (Jev)"), ("executor", "Executor (Claude)"),
            ("guard", "Guard"), ("voice", "Voice (Alfred)"), ("memory", "Session memory (OKF)"),
            ("proactive", "Proactive"),
        ]
        nodes = [{"id": i, "label": l, "kind": "core"} for i, l in core]
        edges = [{"source": a, "target": b, "rel": "flow"} for a, b in (
            ("ears", "router"), ("router", "executor"), ("executor", "guard"), ("executor", "voice"),
            ("executor", "memory"), ("proactive", "router"), ("memory", "executor"), ("mcp:alfred", "memory"))]
        m = self.map.graph()
        nodes += m["nodes"]
        known = {n["id"] for n in nodes}
        edges = [e for e in edges if e["source"] in known and e["target"] in known] + m["edges"]
        return {"nodes": nodes, "edges": edges, "backend": self.executor.backend}
