"""OKF pages: Markdown files with a YAML header ("frontmatter") between two `---` lines.

Memory, the brain map, the persona and module skills are all stored this way, so you can open them in any editor.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

import yaml


def parse(text: str) -> tuple[dict[str, Any], str]:
    """'---\\nkey: value\\n---\\nbody' -> ({'key': 'value'}, 'body')."""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return yaml.safe_load(parts[1]) or {}, parts[2].lstrip("\n")
    return {}, text


def dump(meta: dict[str, Any], body: str) -> str:
    header = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, default_flow_style=None).strip()
    return f"---\n{header}\n---\n\n{body.strip()}\n"


def read(path: Path) -> tuple[dict[str, Any], str]:
    return parse(path.read_text(encoding="utf-8"))


def write(path: Path, meta: dict[str, Any], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump(meta, body), encoding="utf-8")


def read_inside(root: Path, relative: str) -> str:
    """Read a file under `root`; refuses '../' tricks that would leave the folder."""
    path = (root / relative).resolve()
    if root.resolve() not in path.parents:
        raise ValueError(f"{relative} is outside {root}")
    return path.read_text(encoding="utf-8")


def slugify(text: str, max_len: int = 48) -> str:
    """'Łódź — Kraków!' -> 'lodz-krakow' (safe for file names)."""
    text = unicodedata.normalize("NFKD", text.replace("ł", "l").replace("Ł", "L"))
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.encode("ascii", "ignore").decode()).strip("-").lower()
    return text[:max_len].strip("-") or "item"
