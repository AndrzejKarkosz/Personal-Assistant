"""Guard: actions with side effects in the world wait for a spoken (or clicked) "yes".

The executor calls `await guard.confirm(...)`. The guard emits a `confirm_request` event (the
UI speaks it and shows Yes/No), and the next user utterance - or a button - resolves it.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass
class PendingConfirmation:
    id: str
    question: str
    tool: str
    future: asyncio.Future


class Guard:
    def __init__(self, bus, timeout_s: float = 120.0):
        self.bus = bus
        self.timeout_s = timeout_s
        self.pending: PendingConfirmation | None = None

    async def confirm(self, request_id: str, session_id: str | None, tool: str, question: str,
                      audio_b64: str | None = None) -> bool:
        loop = asyncio.get_running_loop()
        self.pending = PendingConfirmation(id=request_id, question=question, tool=tool, future=loop.create_future())
        self.bus.emit("confirm_request", "guard", request_id, session_id, tool=tool, text=question,
                      audio_b64=audio_b64)
        try:
            approved = await asyncio.wait_for(self.pending.future, self.timeout_s)
        except asyncio.TimeoutError:
            approved = False
        self.bus.emit("confirm_result", "guard", request_id, session_id, tool=tool, approved=approved)
        self.pending = None
        return approved

    def resolve(self, approved: bool) -> bool:
        if self.pending and not self.pending.future.done():
            self.pending.future.set_result(approved)
            return True
        return False
