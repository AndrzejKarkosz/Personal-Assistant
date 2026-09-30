"""Who Alfred is: config/persona.md. The header holds his name, your name, how he addresses you and the
confirmation question; the body is his system prompt ({name}, {user}, {addr_pl}, {addr_en} are filled in)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import okf
from .config import ROOT

PERSONA_FILE = ROOT / "config" / "persona.md"
DEFAULT_CONFIRM = {"pl": "Zanim to zrobię: {summary}. Potwierdzasz?", "en": "Before I do that: {summary}. Shall I proceed?"}
POLISH = re.compile(r"[ąćęłńóśźż]|\b(jest|mam|mnie|jutro|dzisiaj|proszę|zrób|czy|jak|co|się|na|nie|tak|dla)\b", re.I)
ENGLISH = re.compile(r"\b(the|what|is|my|please|can|you|book|remind|tomorrow|today)\b", re.I)

_cache: dict[str, Any] = {"mtime": None, "meta": {}, "body": ""}   # re-read only when the file changes


def load(path: Path = PERSONA_FILE) -> tuple[dict[str, Any], str]:
    mtime = path.stat().st_mtime if path.exists() else None
    if mtime != _cache["mtime"]:
        meta, body = okf.read(path) if path.exists() else ({}, "")
        _cache.update(mtime=mtime, meta=meta, body=body)
    return _cache["meta"], _cache["body"]


def save(meta: dict[str, Any], body: str, path: Path = PERSONA_FILE) -> None:
    okf.write(path, {"type": "Persona", **{k: v for k, v in meta.items() if k != "type"}}, body)
    _cache["mtime"] = None


class _KeepUnknown(dict):
    """'{unknown}' stays as it is instead of raising KeyError in str.format_map."""

    def __missing__(self, key):
        return "{" + key + "}"


def system_prompt(settings) -> str:
    meta, body = load()
    address = meta.get("address") or settings.get("assistant.address") or {}
    values = _KeepUnknown(name=meta.get("name") or settings.get("assistant.name", "Alfred"),
                          user=meta.get("user_name") or settings.get("assistant.user_name", "the user"),
                          addr_pl=address.get("pl") or "szefie", addr_en=address.get("en") or "boss")
    return (body or "You are {name}, the personal assistant of {user}.").format_map(values).strip()


def confirm_prompt(lang: str, summary: str) -> str:
    """The yes/no question Alfred asks before a risky action."""
    meta, _ = load()
    template = (meta.get("confirm") or {}).get(lang) or DEFAULT_CONFIRM.get(lang, DEFAULT_CONFIRM["en"])
    return template.format_map(_KeepUnknown(summary=summary))


def detect_language(text: str, default: str = "pl") -> str:
    return "pl" if POLISH.search(text) else "en" if ENGLISH.search(text) else default
