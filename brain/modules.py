"""Modules = what Alfred can do, one folder each in modules/:

    modules/calendar/module.yaml   label, description, examples, capabilities (groups of tools), uses, model
    modules/calendar/prompt.md     extra instructions for Claude when this module is active
    modules/calendar/skills/*.md   step-by-step procedures (header: name, description, uses)
"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import okf


@dataclass
class Capability:
    id: str                    # "<module>.<name>", e.g. "calendar.write"
    module: str
    label: str
    description: str = ""
    tools: list[str] = field(default_factory=list)   # tool name patterns, e.g. "google-calendar__create-*"
    examples: list[str] = field(default_factory=list)
    confirm: bool | None = None   # true: every tool here needs a spoken "yes"; false: none, even destructive ones;
                                  # not set: only the tools the server marks destructive
    always: bool = False       # given whenever the module is active

    def matches(self, tool_name: str) -> bool:
        return any(fnmatch.fnmatch(tool_name, pattern) for pattern in self.tools)


@dataclass
class Skill:
    id: str                    # "<module>.<file name>"
    name: str
    description: str
    body: str
    uses: list[str] = field(default_factory=list)


@dataclass
class Module:
    id: str
    label: str
    description: str
    examples: list[str] = field(default_factory=list)
    capabilities: dict[str, Capability] = field(default_factory=dict)
    uses: list[str] = field(default_factory=list)      # capabilities borrowed from other modules
    model: str | None = None
    effort: str | None = None
    enabled: bool = True
    prompt: str = ""
    skills: list[Skill] = field(default_factory=list)
    path: Path | None = None


def load_module(folder: Path) -> Module:
    data = yaml.safe_load((folder / "module.yaml").read_text(encoding="utf-8")) or {}
    mid = data.get("id", folder.name)
    prompt = folder / "prompt.md"
    module = Module(id=mid, label=data.get("label", mid), description=data.get("description", ""),
                    examples=data.get("examples", []), uses=data.get("uses", []), model=data.get("model"),
                    effort=data.get("effort"), enabled=data.get("enabled", True), path=folder,
                    prompt=prompt.read_text(encoding="utf-8").strip() if prompt.exists() else "")
    for name, cap in (data.get("capabilities") or {}).items():
        module.capabilities[f"{mid}.{name}"] = Capability(
            id=f"{mid}.{name}", module=mid, label=cap.get("label", name), description=cap.get("description", ""),
            tools=cap.get("tools", []), examples=cap.get("examples", []), confirm=cap.get("confirm"),
            always=bool(cap.get("always")))
    for file in sorted((folder / "skills").glob("*.md")):
        meta, body = okf.read(file)
        module.skills.append(Skill(id=f"{mid}.{file.stem}", name=meta.get("name", file.stem), body=body.strip(),
                                   description=meta.get("description", ""), uses=meta.get("uses", [])))
    return module


class ModuleRegistry:
    def __init__(self, root: Path):
        self.root = root
        self.modules: dict[str, Module] = {}
        self.reload()

    def reload(self) -> None:
        self.modules = {m.id: m for m in (load_module(f.parent) for f in sorted(self.root.glob("*/module.yaml")))}

    def get(self, module_id: str) -> Module | None:
        return self.modules.get(module_id)

    def skill(self, skill_id: str | None) -> Skill | None:
        module = self.get((skill_id or "").split(".", 1)[0])
        return next((s for s in module.skills if s.id == skill_id), None) if module else None

    def set_enabled(self, module_id: str, enabled: bool) -> None:
        """Switch a module on/off - saved in its module.yaml."""
        module = self.modules[module_id]
        manifest = module.path / "module.yaml"
        data = (yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}) | {"enabled": enabled}
        manifest.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        module.enabled = enabled
