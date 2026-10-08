"""Who Alfred is: data/persona.md (until you edit him, the template config/persona.md). The header holds the
confirmation question, the body his system prompt ({name}, {user}, {addr_pl}, {addr_en} are filled in from
identity(): his name, yours and how he addresses you - kept in the settings, where the setup saves them)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import okf
from .config import ROOT

PERSONA_FILE = ROOT / "data" / "persona.md"
TEMPLATE = ROOT / "config" / "persona.md"
DEFAULT_CONFIRM = {"pl": "Zanim to zrobię: {summary}. Potwierdzasz?", "en": "Before I do that: {summary}. Shall I proceed?"}
POLISH = re.compile(r"[ąćęłńóśźż]|\b(jest|mam|mnie|jutro|dzisiaj|proszę|zrób|czy|jak|co|się|na|nie|tak|dla)\b", re.I)
ENGLISH = re.compile(r"\b(the|what|is|my|please|can|you|book|remind|tomorrow|today)\b", re.I)

_cache: dict[str, Any] = {"mtime": None, "meta": {}, "body": ""}   # re-read only when the file changes


def load(path: Path | None = None) -> tuple[dict[str, Any], str]:
    path = path or (PERSONA_FILE if PERSONA_FILE.exists() else TEMPLATE)
    mtime = (path, path.stat().st_mtime if path.exists() else None)
    if mtime != _cache["mtime"]:
        meta, body = okf.read(path) if path.exists() else ({}, "")
        _cache.update(mtime=mtime, meta=meta, body=body)
    return _cache["meta"], _cache["body"]


def save(meta: dict[str, Any], body: str, path: Path | None = None) -> None:
    okf.write(path or PERSONA_FILE, {"type": "Persona", **{k: v for k, v in meta.items() if k != "type"}}, body)
    _cache["mtime"] = None


class _KeepUnknown(dict):
    """'{unknown}' stays as it is instead of raising KeyError in str.format_map."""

    def __missing__(self, key):
        return "{" + key + "}"


IDENTITY = ("name", "user_name", "address")


def identity(settings) -> dict[str, Any]:
    """His name, yours, how he addresses you: the settings (assistant.*), else an older persona file's header."""
    meta, _ = load()
    return {k: settings.get(f"assistant.{k}") or meta.get(k) for k in IDENTITY}


def system_prompt(settings) -> str:
    _, body = load()
    me = identity(settings)
    address = me["address"] or {}
    values = _KeepUnknown(name=me["name"] or "Alfred", user=me["user_name"] or "the user",
                          addr_pl=address.get("pl") or "szefie", addr_en=address.get("en") or "boss")
    return (body or "You are {name}, the personal assistant of {user}.").format_map(values).strip()


def confirm_prompt(lang: str, summary: str) -> str:
    """The yes/no question Alfred asks before a risky action."""
    meta, _ = load()
    template = (meta.get("confirm") or {}).get(lang) or DEFAULT_CONFIRM.get(lang, DEFAULT_CONFIRM["en"])
    return template.format_map(_KeepUnknown(summary=summary))


def detect_language(text: str, default: str = "pl") -> str:
    return "pl" if POLISH.search(text) else "en" if ENGLISH.search(text) else default
