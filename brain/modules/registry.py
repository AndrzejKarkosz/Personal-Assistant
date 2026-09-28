"""Module registry: every folder in modules/ with a module.yaml is one brain "lobe".

A module declares (authoring source for the brain map):
  - how the router recognises it       label, description, examples
  - its capabilities                    named groups of tools, e.g. calendar.read / calendar.write,
                                        each with tool name patterns, examples and a confirm flag
  - capabilities it borrows             uses: [tasks.manage, memory.recall]
  - its skills                          skills/*.md - procedures, with `uses:` capabilities
  - model / effort / acknowledge

The brain map compiler (brain/atlas) joins this with the live tool catalogue into an OKF bundle.
"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

import yaml


def _split_frontmatter(text: str) -> tuple[dict, str]:
    if text.startswith("---"):
        _, fm, body = text.split("---", 2)
        return yaml.safe_load(fm) or {}, body.strip()
    return {}, text.strip()


@dataclass
class Capability:
    id: str                    # "<module>.<name>"
    module: str
    label: str
    description: str = ""
    tools: list[str] = field(default_factory=list)      # glob patterns over tool names
    examples: list[str] = field(default_factory=list)
    confirm: bool = False      # every tool in it needs a spoken "yes"
    always: bool = False       # loaded whenever its module is routed (e.g. confirm_action)

    def matches(self, tool_name: str) -> bool:
        return any(fnmatch.fnmatch(tool_name, p) for p in self.tools)


@dataclass
class Skill:
    id: str                   # "<module>.<skill>"
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
    uses: list[str] = field(default_factory=list)
    model: str | None = None
    effort: str | None = None
    acknowledge: bool = True
    enabled: bool = True
    prompt: str = ""
    skills: list[Skill] = field(default_factory=list)
    path: Path | None = None

    def criteria_text(self) -> str:
        text = f"{self.label}. {self.description}".strip()
        if self.examples:
            text += " Examples: " + "; ".join(self.examples[:4])
        return text


class ModuleRegistry:
    def __init__(self, root: Path):
        self.root = root
        self.modules: dict[str, Module] = {}
        self.reload()

    def reload(self) -> None:
        self.modules.clear()
        for manifest in sorted(self.root.glob("*/module.yaml")):
            data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
            folder = manifest.parent
            mid = data.get("id", folder.name)
            prompt_file = folder / "prompt.md"
            module = Module(
                id=mid,
                label=data.get("label", mid),
                description=data.get("description", ""),
                examples=data.get("examples", []),
                uses=data.get("uses", []),
                model=data.get("model"),
                effort=data.get("effort"),
                acknowledge=data.get("acknowledge", True),
                enabled=data.get("enabled", True),
                prompt=prompt_file.read_text(encoding="utf-8").strip() if prompt_file.exists() else "",
                path=folder,
            )
            for name, cap in (data.get("capabilities") or {}).items():
                cid = f"{mid}.{name}"
                module.capabilities[cid] = Capability(
                    id=cid, module=mid, label=cap.get("label", name), description=cap.get("description", ""),
                    tools=cap.get("tools", []), examples=cap.get("examples", []),
                    confirm=bool(cap.get("confirm", False)), always=bool(cap.get("always", False)),
                )
            for skill_file in sorted((folder / "skills").glob("*.md")):
                fm, body = _split_frontmatter(skill_file.read_text(encoding="utf-8"))
                module.skills.append(Skill(
                    id=f"{mid}.{skill_file.stem}", name=fm.get("name", skill_file.stem),
                    description=fm.get("description", ""), body=body, uses=fm.get("uses", []),
                ))
            self.modules[mid] = module

    def enabled(self) -> list[Module]:
        return [m for m in self.modules.values() if m.enabled]

    def get(self, module_id: str) -> Module | None:
        return self.modules.get(module_id)

    def capability(self, cap_id: str) -> Capability | None:
        module = self.get(cap_id.split(".", 1)[0]) if "." in cap_id else None
        return module.capabilities.get(cap_id) if module else None

    def all_capabilities(self) -> list[Capability]:
        return [c for m in self.enabled() for c in m.capabilities.values()]

    def module_capabilities(self, module_id: str) -> list[Capability]:
        """Own capabilities plus the ones the module borrows (`uses`)."""
        module = self.get(module_id)
        if not module:
            return []
        caps = list(module.capabilities.values())
        caps += [c for c in (self.capability(u) for u in module.uses) if c and c not in caps]
        return caps

    def skill(self, skill_id: str | None) -> Skill | None:
        if not skill_id or "." not in skill_id:
            return None
        module = self.get(skill_id.split(".", 1)[0])
        return next((s for s in module.skills if s.id == skill_id), None) if module else None

    def all_skills(self) -> list[Skill]:
        return [s for m in self.enabled() for s in m.skills]

    def set_enabled(self, module_id: str, enabled: bool) -> None:
        module = self.modules[module_id]
        manifest = module.path / "module.yaml"
        data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
        data["enabled"] = enabled
        manifest.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        module.enabled = enabled
