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


@dataclass
class Event:
    kind: str
    node: str
    data: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None
    session_id: str | None = None
    ts: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_UNLOGGED_KEYS = {"audio_b64"}


class ActivityLog:
    def __init__(self, directory: Path):
        self.dir = directory
        self.dir.mkdir(parents=True, exist_ok=True)

    def _file(self, day: str | None = None) -> Path:
        return self.dir / f"{day or datetime.now().strftime('%Y-%m-%d')}.jsonl"

    def write(self, event: Event) -> None:
        record = event.to_dict()
        record["data"] = {k: v for k, v in record["data"].items() if k not in _UNLOGGED_KEYS}
        with self._file().open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def read(self, day: str | None = None, limit: int = 200, kind: str | None = None) -> list[dict]:
        path = self._file(day)
        if not path.exists():
            return []
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if kind:
            rows = [r for r in rows if r["kind"] == kind]
        return rows[-limit:]

    def days(self) -> list[str]:
        return sorted((p.stem for p in self.dir.glob("*.jsonl")), reverse=True)


class EventBus:
    def __init__(self, log: ActivityLog | None = None):
        self.log = log
        self._subscribers: set[asyncio.Queue[Event]] = set()
        self.unheard: deque[Event] = deque(maxlen=20)

    def subscribe(self) -> asyncio.Queue[Event]:
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=500)
        while self.unheard:
            queue.put_nowait(self.unheard.popleft())
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Event]) -> None:
        self._subscribers.discard(queue)

    def emit(self, kind: str, node: str, request_id: str | None = None,
             session_id: str | None = None, **data: Any) -> Event:
        event = Event(kind=kind, node=node, data=data, request_id=request_id, session_id=session_id)
        if self.log:
            self.log.write(event)
        if not self._subscribers and kind == "answer" and data.get("source") != "user":
            self.unheard.append(event)
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass
        return event


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:10]}"
