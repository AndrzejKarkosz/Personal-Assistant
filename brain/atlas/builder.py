from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from ..memory import okf
from ..modules import ModuleRegistry
from .catalog import ToolInfo, collect

CURATED = ("examples_extra", "aliases", "side_effect_override", "confirm_override", "notes")


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def tool_path(t: ToolInfo | dict) -> str:
    server = t.server if isinstance(t, ToolInfo) else t["server"]
    short = t.short if isinstance(t, ToolInfo) else t["short"]
    return f"tools/{server}/{okf.slugify(short, 64)}.md"


def _link(title: str, path: str, here: str) -> str:
    depth = here.count("/")
    return f"[{title}]({'../' * depth}{path})"


class MapBuilder:
    def __init__(self, root: Path, registry: ModuleRegistry, hub, topic_sources: list[dict] | None = None):
        self.root = root
        self.registry = registry
        self.hub = hub
        self.topic_sources = topic_sources or []
        self.pages: dict[str, tuple[dict, str]] = {}

    def build(self) -> dict[str, Any]:
        self.root.mkdir(parents=True, exist_ok=True)
        before = self._existing()
        tools, servers = collect(self.hub)
        tools = self._keep_offline(tools, servers, before)
        caps = {c.id: c for m in self.registry.modules.values() for c in m.capabilities.values()}

        cap_tools = {cid: sorted(n for n in tools if c.matches(n)) for cid, c in caps.items()}
        tool_caps: dict[str, list[str]] = {}
        for cid, names in cap_tools.items():
            for n in names:
                tool_caps.setdefault(n, []).append(cid)
        used_by: dict[str, list[str]] = {}
        for m in self.registry.modules.values():
            for u in m.uses:
                used_by.setdefault(u, []).append(f"module:{m.id}")
            for s in m.skills:
                for u in s.uses:
                    used_by.setdefault(u, []).append(f"skill:{s.id}")

        for m in self.registry.modules.values():
            self._module_page(m, caps, cap_tools, tools)
        for cid, c in caps.items():
            self._capability_page(c, cap_tools[cid], tools, used_by.get(cid, []))
        for m in self.registry.modules.values():
            for s in m.skills:
                self._skill_page(s, caps)
        for name, t in tools.items():
            self._tool_page(t, tool_caps.get(name, []), caps)
        for name, info in servers.items():
            self._server_page(name, info, [t for t in tools.values() if t.server == name])
        topics = self._topics()
        self._indexes(caps, tools, servers, topics)

        changes = self._write(before)
        return {"modules": len(self.registry.modules), "capabilities": len(caps), "skills": sum(
            len(m.skills) for m in self.registry.modules.values()), "tools": len(tools),
            "servers": len(servers), "topics": len(topics), "changes": changes}

    def _put(self, path: str, meta: dict, body: str) -> None:
        body = re.sub(r"\n\n(?=[-*|] )", "\n", body)
        self.pages[path] = (meta, body)

    def _module_page(self, m, caps, cap_tools, tools) -> None:
        p = f"modules/{m.id}.md"
        own = list(m.capabilities)
        borrowed = [u for u in m.uses if u in caps]
        servers = sorted({tools[n].server for cid in own + borrowed for n in cap_tools.get(cid, [])})
        body = [f"# {m.label}", m.description, "## Capabilities"]
        body += [f"- {_link(caps[c].label, f'capabilities/{c}.md', p)} (`{c}`)" for c in own] or ["- none"]
        if borrowed:
            body += ["## Borrowed capabilities"] + [f"- {_link(caps[c].label, f'capabilities/{c}.md', p)} (`{c}`)"
                                                    for c in borrowed]
        if m.skills:
            body += ["## Skills"] + [f"- {_link(s.name, f'skills/{s.id}.md', p)}" for s in m.skills]
        body += ["## Connected servers"] + [f"- {_link(s, f'servers/{s}.md', p)}" for s in servers] or []
        if m.examples:
            body += ["## Example requests"] + [f"- {e}" for e in m.examples]
        self._put(p, {"type": "Module", "title": m.label, "description": m.description, "id": m.id,
                      "capabilities": own, "uses": borrowed, "skills": [s.id for s in m.skills],
                      "servers": servers, "examples": m.examples, "enabled": m.enabled,
                      "model": m.model, "effort": m.effort,
                      "tags": ["module"], "timestamp": _now()}, "\n\n".join(body))

    def _capability_page(self, c, names, tools, used_by) -> None:
        p = f"capabilities/{c.id}.md"
        online = [n for n in names if tools[n].status == "online"]
        body = [f"# {c.label}", c.description or "",
                f"Module: {_link(c.module, f'modules/{c.module}.md', p)}",
                "## Tools"]
        body += [f"- {_link(tools[n].short, tool_path(tools[n]), p)} - {tools[n].server}, "
                 f"{tools[n].side_effect}{'' if tools[n].status == 'online' else ', offline'}" for n in names] \
            or ["- no tool connected yet" + (f" (expects {', '.join(c.tools)})" if c.tools else "")]
        if used_by:
            body += ["## Used by"] + [f"- {u}" for u in used_by]
        if c.examples:
            body += ["## Example requests"] + [f"- {e}" for e in c.examples]
        self._put(p, {"type": "Capability", "title": c.label, "description": c.description, "id": c.id,
                      "module": c.module, "tools": names, "tool_patterns": c.tools, "available": len(online),
                      "confirm": c.confirm, "always": c.always, "examples": c.examples, "used_by": used_by,
                      "tags": ["capability", c.module], "timestamp": _now()}, "\n\n".join(body))

    def _skill_page(self, s, caps) -> None:
        p = f"skills/{s.id}.md"
        module = s.id.split(".", 1)[0]
        body = [f"# {s.name}", s.description, f"Module: {_link(module, f'modules/{module}.md', p)}", "## Uses"]
        body += [f"- {_link(caps[u].label, f'capabilities/{u}.md', p)} (`{u}`)" for u in s.uses if u in caps] or ["- -"]
        body += ["## Procedure", s.body]
        self._put(p, {"type": "Skill", "title": s.name, "description": s.description, "id": s.id,
                      "module": module, "uses": [u for u in s.uses if u in caps],
                      "tags": ["skill", module], "timestamp": _now()}, "\n\n".join(body))

    def _tool_page(self, t: ToolInfo, cap_ids, caps) -> None:
        p = tool_path(t)
        confirm = t.side_effect == "destructive" or any(caps[c].confirm for c in cap_ids)
        body = [f"# {t.short}", t.description or "",
                f"Server: {_link(t.server, f'servers/{t.server}.md', p)}", "## Capabilities"]
        body += [f"- {_link(caps[c].label, f'capabilities/{c}.md', p)} (`{c}`)" for c in cap_ids] \
            or ["- not assigned to any capability yet - add a pattern to a module's capabilities"]
        if t.params:
            body += ["## Parameters", "| name | type | required | description |", "|---|---|---|---|"]
            body += [f"| `{x['name']}` | {x['type']} | {'yes' if x['required'] else ''} | "
                     f"{x['description'].replace('|', '/')} |" for x in t.params]
        self._put(p, {"type": "Tool", "title": t.short, "description": (t.description or "")[:240], "id": t.name,
                      "server": t.server, "kind": t.kind, "short": t.short, "capabilities": cap_ids,
                      "modules": sorted({c.split('.', 1)[0] for c in cap_ids}), "side_effect": t.side_effect,
                      "requires_confirmation": confirm, "status": t.status,
                      "params": [x["name"] for x in t.params], "tags": ["tool", t.server], "timestamp": _now()},
                  "\n\n".join(body))

    def _server_page(self, name, info, tools) -> None:
        p = f"servers/{name}.md"
        kind = {"mcp": "MCP Server", "builtin": "Built-in tools", "server": "Claude server tools"}[info["kind"]]
        body = [f"# {name}", info.get("description", ""), f"Status: **{info['status']}**"
                + (f" - {info['error']}" if info.get("error") else "")]
        if info.get("command"):
            body.append(f"Runs: `{info['command']}`")
        body += ["## Tools"] + [f"- {_link(t.short, tool_path(t), p)} - {t.side_effect}" for t in tools] \
            or ["- no tools discovered yet (server not connected)"]
        self._put(p, {"type": kind, "title": name, "description": info.get("description", ""), "id": name,
                      "status": info["status"], "tools": [t.name for t in tools],
                      "tags": ["server", info["kind"]], "timestamp": _now()}, "\n\n".join(body))

    def _topics(self) -> list[str]:
        out = []
        for src in self.topic_sources:
            folder = Path(src["path"])
            if not folder.exists():
                continue
            for f in sorted(folder.glob("*.md")):
                if f.name == "index.md":
                    continue
                meta, body = okf.read(f)
                title = meta.get("title") or next((l[2:] for l in body.splitlines() if l.startswith("# ")), f.stem)
                desc = meta.get("description") or next((l for l in body.splitlines() if l and not l.startswith("#")), "")
                server, cap = src["server"], src.get("capability")
                p = f"topics/{server}/{f.stem}.md"
                where = f"Lives in {_link(server, f'servers/{server}.md', p)}"
                if cap:
                    where += f", reached through {_link(cap, f'capabilities/{cap}.md', p)}"
                self._put(p, {"type": "Topic", "title": title, "description": str(desc)[:240], "id": f"topic:{f.stem}",
                              "server": server, "capability": cap, "source": f.as_posix(),
                              "tags": ["topic", server], "timestamp": _now()},
                          f"# {title}\n\n{desc}\n\n{where}.")
                out.append(p)
        return out

    def _indexes(self, caps, tools, servers, topics) -> None:
        groups = {
            "modules": ("Modules", "The brain's lobes. The router's first question picks one."),
            "capabilities": ("Capabilities", "Groups of tools - the router's second question. Only the chosen "
                                             "capabilities' tools are given to Claude."),
            "skills": ("Skills", "Procedures the executor follows. Jev can pick one directly."),
            "tools": ("Tools", "Every tool the brain can call, by server."),
            "servers": ("Servers", "Where tools live: MCP servers, Alfred's built-ins, Claude server tools."),
            "topics": ("Topics", "What the knowledge library covers - lets Jev route by subject."),
        }
        for folder, (title, desc) in groups.items():
            items = sorted(p for p in self.pages if p.startswith(folder + "/"))
            lines = [f"# {title}", desc, ""]
            lines += [f"* [{self.pages[p][0]['title']}]({p.split('/', 1)[1]}) - {self.pages[p][0].get('description', '')[:120]}"
                      for p in items]
            self._put(f"{folder}/index.md", {"type": "Index", "title": title, "description": desc,
                                             "timestamp": _now()}, "\n".join(lines))
        online = sum(1 for t in tools.values() if t.status == "online")
        body = [
            "# Alfred's brain map",
            "What the brain is connected to and how the parts relate. Compiled from `modules/`, the live MCP "
            "servers and the knowledge library by `brain/atlas`. The router builds its Jev categories from these "
            "pages: modules, capabilities, skills and topics.",
            "",
            "Module --has--> Capability --includes--> Tool --served by--> Server;  "
            "Skill --uses--> Capability;  Module --uses--> Capability of another module.",
            "",
            "# Sections",
            f"* [modules](modules/index.md) - {len(self.registry.modules)} modules",
            f"* [capabilities](capabilities/index.md) - {len(caps)} capabilities (routing categories)",
            f"* [skills](skills/index.md) - {sum(len(m.skills) for m in self.registry.modules.values())} skills",
            f"* [tools](tools/index.md) - {len(tools)} tools, {online} online",
            f"* [servers](servers/index.md) - " + ", ".join(f"{n} ({i['status']})" for n, i in servers.items()),
            f"* [topics](topics/index.md) - {len(topics)} knowledge topics",
            "* [log](log.md) - changes between builds",
        ]
        self._put("index.md", {"type": "Index", "title": "Alfred's brain map", "okf_version": "0.2",
                               "description": "Modules, capabilities, skills, tools, servers and topics of the brain.",
                               "timestamp": _now()}, "\n".join(body))

    def _existing(self) -> dict[str, tuple[dict, str]]:
        out = {}
        for f in self.root.rglob("*.md"):
            rel = f.relative_to(self.root).as_posix()
            if rel != "log.md":
                out[rel] = okf.read(f)
        return out

    def _keep_offline(self, tools, servers, before) -> dict[str, ToolInfo]:
        for rel, (meta, _) in before.items():
            if meta.get("type") != "Tool" or meta.get("id") in tools:
                continue
            server = meta.get("server")
            if servers.get(server, {}).get("status") == "ready" or server not in servers:
                continue
            tools[meta["id"]] = ToolInfo(meta["id"], server, meta.get("kind", "mcp"), meta.get("short", meta["id"]),
                                         meta.get("description", ""), [{"name": p, "type": "", "required": False,
                                                                        "description": ""} for p in meta.get("params", [])],
                                         meta.get("side_effect", "read"), "offline")
        return tools

    @staticmethod
    def _signature(meta: dict) -> dict:
        return {k: v for k, v in meta.items() if k != "timestamp"}

    def _write(self, before: dict[str, tuple[dict, str]]) -> list[str]:
        changes = []
        for rel, (meta, body) in self.pages.items():
            old = before.get(rel)
            if old:
                for key in CURATED:
                    if key in old[0]:
                        meta[key] = old[0][key]
                if "## Notes" in old[1]:
                    body = body.rstrip() + "\n\n## Notes" + old[1].split("## Notes", 1)[1]
                if self._signature(old[0]) == self._signature(meta) and old[1].strip() == body.strip():
                    continue
                changes.append(f"changed {rel}")
            elif meta.get("type") != "Index":
                changes.append(f"added {rel}")
            okf.write(self.root / rel, meta, body)
        for rel in set(before) - set(self.pages):
            (self.root / rel).unlink(missing_ok=True)
            changes.append(f"removed {rel}")
        for folder in self.root.rglob("*"):
            if folder.is_dir() and not any(folder.iterdir()):
                shutil.rmtree(folder, ignore_errors=True)
        log = self.root / "log.md"
        if not log.exists():
            okf.write(log, {"type": "Log", "title": "Brain map change log",
                            "description": "What appeared, disappeared or changed between builds."}, "# Change log\n")
        interesting = [c for c in changes if not c.endswith("index.md")]
        if interesting:
            with log.open("a", encoding="utf-8") as fh:
                fh.write(f"\n## {_now()}\n" + "\n".join(f"- {c}" for c in interesting[:200]) + "\n")
        return interesting
