"""BrainMap: the compiled OKF brain map, read back as a typed graph.

The router asks it for Jev categories; the executor asks it which tools a route may use and
which of them need a spoken "yes"; the UI asks it for the 3D graph. Everything comes from the
pages on disk, so edits to the bundle (examples_extra, confirm_override, ...) take effect.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..memory import okf

NO_TOPIC = "none"


class BrainMap:
    def __init__(self, root: Path):
        self.root = root
        self.modules: dict[str, dict] = {}
        self.capabilities: dict[str, dict] = {}
        self.skills: dict[str, dict] = {}
        self.tools: dict[str, dict] = {}
        self.servers: dict[str, dict] = {}
        self.topics: dict[str, dict] = {}
        self.reload()

    def reload(self) -> None:
        for d in (self.modules, self.capabilities, self.skills, self.tools, self.servers, self.topics):
            d.clear()
        if not self.root.exists():
            return
        for f in self.root.rglob("*.md"):
            meta, _ = okf.read(f)
            meta["path"] = f.relative_to(self.root).as_posix()
            kind = meta.get("type")
            key = meta.get("id")
            if kind == "Module":
                self.modules[key] = meta
            elif kind == "Capability":
                self.capabilities[key] = meta
            elif kind == "Skill":
                self.skills[key] = meta
            elif kind == "Tool":
                self.tools[key] = meta
            elif kind in ("MCP Server", "Built-in tools", "Claude server tools"):
                self.servers[key] = meta
            elif kind == "Topic":
                self.topics[key] = meta

    # ------------------------------------------------------------ relations
    def enabled_modules(self) -> list[dict]:
        return [m for m in self.modules.values() if m.get("enabled", True)]

    def capabilities_of(self, module_ids: list[str]) -> list[str]:
        """Own + borrowed capabilities of the modules, in order, no duplicates."""
        out: list[str] = []
        for mid in module_ids:
            m = self.modules.get(mid) or {}
            out += [c for c in (m.get("capabilities") or []) + (m.get("uses") or []) if c not in out]
        return out

    def always_capabilities(self, module_ids: list[str]) -> list[str]:
        return [c for c in self.capabilities_of(module_ids) if self.capabilities.get(c, {}).get("always")]

    def tools_of(self, cap_ids: list[str], online_only: bool = True) -> list[str]:
        out: list[str] = []
        for cid in cap_ids:
            for name in self.capabilities.get(cid, {}).get("tools") or []:
                tool = self.tools.get(name, {})
                if name not in out and (not online_only or tool.get("status", "online") == "online"):
                    out.append(name)
        return out

    def needs_confirmation(self, tool_name: str) -> bool:
        tool = self.tools.get(tool_name) or {}
        if "confirm_override" in tool:
            return bool(tool["confirm_override"])
        return bool(tool.get("requires_confirmation"))

    # --------------------------------------------------------- Jev criteria
    @staticmethod
    def _examples(meta: dict, n: int = 3) -> list[str]:
        return list(meta.get("examples") or [])[:n] + list(meta.get("examples_extra") or [])[:n]

    def module_criteria(self) -> dict[str, str]:
        out = {}
        for m in self.enabled_modules():
            caps = [self.capabilities[c]["title"] for c in m.get("capabilities", []) if c in self.capabilities]
            text = f"{m['title']}. {m.get('description', '')}"
            if caps:
                text += " Can: " + "; ".join(caps) + "."
            ex = self._examples(m)
            if ex:
                text += " Examples: " + "; ".join(ex)
            out[m["id"]] = text
        return out

    def capability_criteria(self) -> dict[str, str]:
        enabled = {m["id"] for m in self.enabled_modules()}
        out = {}
        for cid, c in self.capabilities.items():
            if c.get("module") not in enabled:
                continue
            text = f"{c['title']}: {c.get('description', '')}"
            ex = self._examples(c)
            if ex:
                text += " Examples: " + "; ".join(ex)
            out[cid] = text
        return out

    def skill_criteria(self) -> dict[str, str]:
        enabled = {m["id"] for m in self.enabled_modules()}
        return {sid: f"{s['title']}: {s.get('description', '')}" for sid, s in self.skills.items()
                if s.get("module") in enabled}

    def topic_criteria(self) -> dict[str, str]:
        return {tid: f"{t['title']}: {t.get('description', '')}"[:200] for tid, t in self.topics.items()}

    # ------------------------------------------------------------- UI graph
    def graph(self) -> dict[str, Any]:
        nodes, edges = [], []

        def node(nid, label, kind, **extra):
            nodes.append({"id": nid, "label": label, "kind": kind, **extra})

        def edge(src, dst, rel):
            edges.append({"source": src, "target": dst, "rel": rel})

        for mid, m in self.modules.items():
            node(f"module:{mid}", mid, "module", description=m.get("description", ""),
                 enabled=m.get("enabled", True), path=m["path"])
            edge("router", f"module:{mid}", "routes to")
            edge(f"module:{mid}", "executor", "runs on")
            for c in m.get("uses") or []:
                edge(f"module:{mid}", f"cap:{c}", "uses")
        for cid, c in self.capabilities.items():
            node(f"cap:{cid}", c["title"], "capability", description=c.get("description", ""),
                 available=c.get("available", 0), confirm=c.get("confirm", False), path=c["path"])
            edge(f"module:{c['module']}", f"cap:{cid}", "has")
            for t in c.get("tools") or []:
                edge(f"cap:{cid}", f"tool:{t}", "includes")
        for sid, s in self.skills.items():
            node(f"skill:{sid}", s["title"], "skill", description=s.get("description", ""), path=s["path"])
            edge(f"module:{s['module']}", f"skill:{sid}", "has skill")
            for c in s.get("uses") or []:
                edge(f"skill:{sid}", f"cap:{c}", "uses")
        for tid, t in self.tools.items():
            node(f"tool:{tid}", t.get("short", tid), "tool", description=t.get("description", ""),
                 status=t.get("status"), side_effect=t.get("side_effect"),
                 confirm=self.needs_confirmation(tid), server=t.get("server"), path=t["path"])
            edge(f"tool:{tid}", f"mcp:{t['server']}", "served by")
        for name, s in self.servers.items():
            node(f"mcp:{name}", name, "mcp", status=s.get("status"), description=s.get("description", ""),
                 path=s["path"])
        for tid, t in self.topics.items():
            node(tid, t["title"], "topic", description=t.get("description", ""), path=t["path"])
            edge(tid, f"mcp:{t['server']}", "lives in")
        known = {n["id"] for n in nodes} | {"router", "executor"}
        return {"nodes": nodes, "edges": [e for e in edges if e["source"] in known and e["target"] in known]}

    def page(self, rel: str) -> str:
        path = (self.root / rel).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError("Path outside brain map")
        return path.read_text(encoding="utf-8")
