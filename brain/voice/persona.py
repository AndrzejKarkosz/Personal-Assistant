"""Alfred's persona - role, character, speech and working rules - lives in config/persona.md.

The frontmatter holds the structured parts (name, how he addresses you, acknowledgement phrases,
the confirmation question); the markdown body is the system prompt. Edit the file or the
"Osobowość" tab in the UI; changes apply to the next request.
"""
from __future__ import annotations

import random
import re
from pathlib import Path
from typing import Any

from ..config import ROOT
from ..memory import okf

PERSONA_FILE = ROOT / "config" / "persona.md"

_DEFAULT_ACKS = {"pl": ["Oczywiście, {addr}. Już się tym zajmuję."], "en": ["Of course, {addr}. I'm on it."]}
_DEFAULT_CONFIRM = {"pl": "Zanim to zrobię: {summary}. Potwierdzasz?",
                    "en": "Before I do that: {summary}. Shall I proceed?"}

_PL_HINTS = re.compile(r"[ąćęłńóśźż]|\b(jest|mam|mnie|jutro|dzisiaj|proszę|zrób|czy|jak|co|się|na|nie|tak|dla)\b",
                       re.IGNORECASE)

_cache: dict[str, Any] = {"mtime": None, "meta": {}, "body": ""}


def load(path: Path = PERSONA_FILE) -> tuple[dict[str, Any], str]:
    """Persona (frontmatter, body), re-read whenever the file changes."""
    mtime = path.stat().st_mtime if path.exists() else None
    if mtime != _cache["mtime"]:
        meta, body = okf.read(path) if path.exists() else ({}, "")
        _cache.update(mtime=mtime, meta=meta, body=body)
    return _cache["meta"], _cache["body"]


def save(meta: dict[str, Any], body: str, path: Path = PERSONA_FILE) -> None:
    meta = {"type": "Persona", **{k: v for k, v in meta.items() if k != "type"}}
    okf.write(path, meta, body)
    _cache["mtime"] = None


def _address(settings, lang: str) -> str:
    meta, _ = load()
    return (meta.get("address") or settings.get("assistant.address", {}) or {}).get(lang, "")


def detect_language(text: str, default: str = "pl") -> str:
    if _PL_HINTS.search(text):
        return "pl"
    if re.search(r"\b(the|what|is|my|please|can|you|book|remind|tomorrow|today)\b", text, re.IGNORECASE):
        return "en"
    return default


class _Safe(dict):
    def __missing__(self, key):          # unknown {placeholders} in a user-edited prompt stay as they are
        return "{" + key + "}"


def system_prompt(settings) -> str:
    meta, body = load()
    values = _Safe(
        name=meta.get("name") or settings.get("assistant.name", "Alfred"),
        user=meta.get("user_name") or settings.get("assistant.user_name", "the user"),
        addr_pl=_address(settings, "pl") or "szefie",
        addr_en=_address(settings, "en") or "boss",
    )
    return (body or "You are {name}, the personal assistant of {user}.").format_map(values).strip()


def ack_phrase(settings, lang: str, rng: random.Random | None = None) -> str:
    meta, _ = load()
    phrases = (meta.get("acks") or {}).get(lang) or _DEFAULT_ACKS.get(lang, _DEFAULT_ACKS["en"])
    return (rng or random).choice(phrases).format_map(_Safe(addr=_address(settings, lang))).replace(" ,", ",")


def confirm_prompt(settings, lang: str, summary: str) -> str:
    meta, _ = load()
    template = (meta.get("confirm") or {}).get(lang) or _DEFAULT_CONFIRM.get(lang, _DEFAULT_CONFIRM["en"])
    return template.format_map(_Safe(summary=summary))


# Kept for callers that still import the constant.
CONFIRM_PROMPT = _DEFAULT_CONFIRM
