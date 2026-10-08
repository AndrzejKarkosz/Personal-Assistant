"""Settings = config/brain.yaml, plus what you changed in the UI (data/settings.json), plus secrets from .env."""
from __future__ import annotations

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


def merge(base: dict, extra: dict) -> dict:
    """Deep merge: nested dicts are merged key by key, any other value in `extra` wins."""
    out = dict(base)
    for key, value in extra.items():
        both_dicts = isinstance(value, dict) and isinstance(out.get(key), dict)
        out[key] = merge(out[key], value) if both_dicts else value
    return out


def _saved_overrides() -> dict:
    return json.loads(OVERRIDES_FILE.read_text(encoding="utf-8")) if OVERRIDES_FILE.exists() else {}


class Settings:
    def __init__(self, data: dict[str, Any]):
        self.data = data

    @classmethod
    def load(cls) -> Settings:
        return cls(merge(yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}, _saved_overrides()))

    def get(self, dotted: str, default: Any = None) -> Any:
        """get("router.timeout_s") reads data["router"]["timeout_s"]."""
        node: Any = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def path(self, dotted: str) -> Path:
        """A path from the config; relative paths are relative to the project folder."""
        path = Path(self.get(dotted))
        return path if path.is_absolute() else ROOT / path

    def update(self, patch: dict[str, Any]) -> None:
        """Apply a change from the UI now and remember it in data/settings.json."""
        OVERRIDES_FILE.parent.mkdir(parents=True, exist_ok=True)
        OVERRIDES_FILE.write_text(json.dumps(merge(_saved_overrides(), patch), indent=2, ensure_ascii=False),
                                  encoding="utf-8")
        self.data = merge(self.data, patch)

    def replace(self, dotted: str, value: Any) -> None:
        """Set one key to exactly `value` (update() merges dicts, so it can never drop a key - e.g. a category)."""
        saved = _saved_overrides()
        for target in (saved, self.data):
            *parents, last = dotted.split(".")
            for part in parents:
                target = target.setdefault(part, {})
            target[last] = value
        OVERRIDES_FILE.parent.mkdir(parents=True, exist_ok=True)
        OVERRIDES_FILE.write_text(json.dumps(saved, indent=2, ensure_ascii=False), encoding="utf-8")

    @property
    def jev_key(self) -> str | None:
        return os.getenv("JEV_API_KEY") or None

    @property
    def elevenlabs_key(self) -> str | None:
        return os.getenv("ELEVENLABS_API_KEY") or None

    @property
    def voice_id(self) -> str:
        return self.get("voice.voice_id") or os.getenv("ELEVENLABS_VOICE_ID") or "JBFqnCBsd6RMkjVDRZzb"

    def keys(self) -> dict[str, bool]:
        """Which optional services have a key in .env."""
        return {"jev": bool(self.jev_key), "elevenlabs": bool(self.elevenlabs_key)}
