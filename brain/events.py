"""The event bus: every step of the brain announces itself here ("transcript", "classified", "tool_call", ...).

Each event goes to the UI (live, over the websocket) and to a daily log file data/logs/YYYY-MM-DD.jsonl.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:10]}"


@dataclass
class Event:
    kind: str                      # what happened, e.g. "answer"
    node: str                      # which part of the brain it happened in, e.g. "voice"
    data: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None
    session_id: str | None = None
    ts: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ActivityLog:
    """One JSON line per event, one file per day. Audio is not stored (too big)."""

    def __init__(self, directory: Path):
        self.dir = directory
        self.dir.mkdir(parents=True, exist_ok=True)

    def _file(self, day: str | None = None) -> Path:
        return self.dir / f"{day or datetime.now().strftime('%Y-%m-%d')}.jsonl"

    def write(self, event: Event) -> None:
        record = event.to_dict()
        record["data"] = {k: v for k, v in record["data"].items() if k != "audio_b64"}
        with self._file().open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def read(self, day: str | None = None, limit: int = 200, kind: str | None = None) -> list[dict]:
        path = self._file(day)
        if not path.exists():
            return []
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return [r for r in rows if not kind or r["kind"] == kind][-limit:]

    def days(self) -> list[str]:
        return sorted((p.stem for p in self.dir.glob("*.jsonl")), reverse=True)


class EventBus:
    def __init__(self, log: ActivityLog | None = None):
        self.log = log
        self._subscribers: set[asyncio.Queue[Event]] = set()
        # What Alfred said on his own while no UI was open - handed to the next UI that connects.
        self.unheard: deque[Event] = deque(maxlen=20)

    def subscribe(self) -> asyncio.Queue[Event]:
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=500)
        while self.unheard:
            queue.put_nowait(self.unheard.popleft())
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Event]) -> None:
        self._subscribers.discard(queue)

    def emit(self, kind: str, node: str, request_id: str | None = None, session_id: str | None = None,
             **data: Any) -> Event:
        event = Event(kind, node, data, request_id, session_id)
        if self.log:
            self.log.write(event)
        if not self._subscribers and kind == "answer" and data.get("source") != "user":
            self.unheard.append(event)
        for queue in list(self._subscribers):
            if not queue.full():  # a stuck UI must never block the brain
                queue.put_nowait(event)
        return event
