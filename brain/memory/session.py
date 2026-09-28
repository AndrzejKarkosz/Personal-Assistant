"""Live session: the working memory of one conversation.

A session starts on the first utterance, keeps the last turns as plain text (not the
tool-call transcripts - those stay inside a single request) and closes after an idle
pause. On close, the light model writes the OKF session page: summary, what was done,
what changed, open threads and facts - and facts are filed into facts/<category>/.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from ..events import new_id, now_iso
from .store import FACT_CATEGORIES, MemoryStore

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "domains": {"type": "array", "items": {"type": "string"}},
        "done": {"type": "array", "items": {"type": "string"}},
        "changed": {"type": "array", "items": {"type": "string"}},
        "open_threads": {"type": "array", "items": {"type": "string"}},
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": list(FACT_CATEGORIES)},
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["category", "title", "content"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "summary", "domains", "done", "changed", "open_threads", "facts"],
    "additionalProperties": False,
}


@dataclass
class Turn:
    role: str            # user | assistant
    text: str
    module: str | None = None
    ts: str = field(default_factory=now_iso)


@dataclass
class Session:
    id: str = field(default_factory=lambda: new_id(f"s-{datetime.now():%Y%m%d-%H%M}-"))
    started: str = field(default_factory=now_iso)
    last_activity: datetime = field(default_factory=datetime.now)
    turns: list[Turn] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)      # tool calls that changed something
    usage: dict[str, int] = field(default_factory=lambda: {"input": 0, "output": 0, "cache_read": 0, "jev": 0})
    briefing: str = ""
    language: str = "pl"

    def add(self, role: str, text: str, module: str | None = None) -> None:
        self.turns.append(Turn(role, text, module))
        self.last_activity = datetime.now()

    def add_usage(self, usage: dict[str, Any]) -> None:
        for key, value in usage.items():
            if isinstance(value, (int, float)):
                self.usage[key] = self.usage.get(key, 0) + int(value)

    def recent_text(self, n: int = 6) -> str:
        return "\n".join(f"{t.role}: {t.text}" for t in self.turns[-n:])

    def history_messages(self, n: int = 8) -> list[dict[str, str]]:
        """Last turns as alternating user/assistant messages (plain text only)."""
        msgs: list[dict[str, str]] = []
        for turn in self.turns[-n:]:
            if msgs and msgs[-1]["role"] == turn.role:
                msgs[-1]["content"] += "\n" + turn.text
            else:
                msgs.append({"role": turn.role, "content": turn.text})
        while msgs and msgs[0]["role"] != "user":
            msgs.pop(0)
        return msgs


class SessionManager:
    def __init__(self, store: MemoryStore, settings, anthropic_client=None, bus=None):
        self.store = store
        self.settings = settings
        self.anthropic = anthropic_client
        self.bus = bus
        self.current: Session | None = None

    @property
    def idle_limit(self) -> timedelta:
        return timedelta(minutes=float(self.settings.get("memory.session_idle_minutes", 15)))

    async def get(self) -> Session:
        """Current session, or a fresh one (closing a stale one first)."""
        if self.current and datetime.now() - self.current.last_activity > self.idle_limit:
            await self.close()
        if self.current is None:
            self.current = Session(briefing=self.store.briefing(int(self.settings.get("memory.recall_sessions", 3))))
            if self.bus:
                self.bus.emit("session_started", "memory", session_id=self.current.id,
                              briefing=self.current.briefing)
        return self.current

    async def close_if_idle(self) -> None:
        if self.current and datetime.now() - self.current.last_activity > self.idle_limit:
            await self.close()

    async def close(self) -> None:
        session, self.current = self.current, None
        if session is None or not session.turns:
            return
        summary = await self._summarize(session)
        for fact in summary.get("facts", []):
            self.store.remember(fact["category"], fact["title"], fact["content"], session.id)
        path = self.store.write_session(session.id, session.started, now_iso(), summary,
                                        session.usage, len(session.turns))
        if self.bus:
            self.bus.emit("session_closed", "memory", session_id=session.id,
                          path=str(path), title=summary.get("title"), summary=summary.get("summary"))

    async def _summarize(self, session: Session) -> dict[str, Any]:
        transcript = "\n".join(f"[{t.ts[11:16]}] {t.role}{'/' + t.module if t.module else ''}: {t.text}"
                               for t in session.turns)
        actions = "\n".join(f"- {a}" for a in session.actions) or "- none"
        fallback = {
            "title": session.turns[0].text[:60], "summary": transcript[:400], "domains": [],
            "done": session.actions, "changed": [], "open_threads": [], "facts": [],
        }
        if self.anthropic is None:
            return fallback
        prompt = (
            "Write the memory record of this assistant session. Be terse; the record is read by the "
            "assistant at the start of future sessions to know what is done and what to pick up.\n"
            "- summary: 1-2 sentences\n- done: completed actions\n- changed: things created/updated\n"
            "- open_threads: unfinished items the assistant should pick up later\n"
            "- facts: durable facts about the user worth remembering (people, places, preferences, "
            "projects); skip trivia\n\n"
            f"Actions taken:\n{actions}\n\nTranscript:\n{transcript}"
        )
        try:
            response = await self.anthropic.messages.create(
                model=self.settings.get("models.light"),
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
                output_config={"format": {"type": "json_schema", "schema": SUMMARY_SCHEMA}},
            )
            text = next(b.text for b in response.content if b.type == "text")
            return json.loads(text)
        except Exception:  # noqa: BLE001 - never lose a session because the summary failed
            return fallback
