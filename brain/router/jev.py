"""Minimal async client for Jev (TypeSafe AI "System One" typed decisions).

POST {url}  Authorization: Bearer <key>
{ "model": ..., "state": "<text>", "questions": { "<id>": {type, instructions, criteria} } }
-> { "answers": { "<id>": {...} }, "usage": {...} }

Question types:
  choice  criteria = {option_id: description}     -> {choice, probabilities, confidence}
  score   criteria = [level_low, ..., level_high]  -> {score, legend, probabilities, confidence}
  noul    criteria = {"true": ..., "false": ...}   -> {noul: P(yes)}
"""
from __future__ import annotations

from typing import Any

import httpx


class JevError(RuntimeError):
    pass


def choice(instructions: str, criteria: dict[str, str]) -> dict[str, Any]:
    return {"type": "choice", "instructions": instructions, "criteria": criteria}


def score(instructions: str, levels: list[str]) -> dict[str, Any]:
    return {"type": "score", "instructions": instructions, "criteria": levels}


def noul(instructions: str, true: str | None = None, false: str | None = None) -> dict[str, Any]:
    q: dict[str, Any] = {"type": "noul", "instructions": instructions}
    if true or false:
        q["criteria"] = {"true": true or "", "false": false or ""}
    return q


class JevClient:
    def __init__(self, api_key: str | None, url: str, model: str, timeout_s: float = 4.0):
        self.api_key = api_key
        self.url = url
        self.model = model
        self.timeout_s = timeout_s

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    async def ask(self, state: str, questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """Returns the full response: {"answers": {...}, "usage": {...}, "model": ...}."""
        if not self.api_key:
            raise JevError("JEV_API_KEY is not set")
        payload = {"model": self.model, "state": state, "questions": questions}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                resp = await client.post(
                    self.url,
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
        except httpx.HTTPError as exc:
            raise JevError(f"Jev request failed: {exc!r}") from exc
        if resp.status_code != 200:
            raise JevError(f"Jev returned {resp.status_code}: {resp.text[:300]}")
        body = resp.json()
        if "answers" not in body:
            raise JevError(f"Unexpected Jev response: {str(body)[:300]}")
        return body
