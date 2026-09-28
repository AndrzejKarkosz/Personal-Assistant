"""Configuration: secrets from .env, everything else from config/brain.yaml.

Runtime overrides made from the UI are stored in data/settings.json and layered on top.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

CONFIG_FILE = ROOT / "config" / "brain.yaml"
OVERRIDES_FILE = ROOT / "data" / "settings.json"


def _deep_merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


class Settings:
    """Dict-backed settings with dotted access: settings.get("models.executor")."""

    def __init__(self, data: dict[str, Any]):
        self.data = data

    @classmethod
    def load(cls) -> "Settings":
        data = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
        if OVERRIDES_FILE.exists():
            data = _deep_merge(data, json.loads(OVERRIDES_FILE.read_text(encoding="utf-8")))
        return cls(data)

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def path(self, dotted: str) -> Path:
        p = Path(self.get(dotted))
        return p if p.is_absolute() else ROOT / p

    def update(self, patch: dict[str, Any]) -> None:
        """Apply a UI change and persist it as an override (brain.yaml stays untouched)."""
        current = json.loads(OVERRIDES_FILE.read_text(encoding="utf-8")) if OVERRIDES_FILE.exists() else {}
        current = _deep_merge(current, patch)
        OVERRIDES_FILE.parent.mkdir(parents=True, exist_ok=True)
        OVERRIDES_FILE.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
        self.data = _deep_merge(self.data, patch)

    # Secrets -----------------------------------------------------------------
    @property
    def anthropic_key(self) -> str | None:
        return os.getenv("ANTHROPIC_API_KEY") or None

    @property
    def jev_key(self) -> str | None:
        return os.getenv("JEV_API_KEY") or None

    @property
    def elevenlabs_key(self) -> str | None:
        return os.getenv("ELEVENLABS_API_KEY") or None

    @property
    def voice_id(self) -> str:
        return self.get("voice.voice_id") or os.getenv("ELEVENLABS_VOICE_ID") or "JBFqnCBsd6RMkjVDRZzb"

    def status(self) -> dict[str, bool]:
        return {
            "anthropic": bool(self.anthropic_key),
            "jev": bool(self.jev_key),
            "elevenlabs": bool(self.elevenlabs_key),
        }
