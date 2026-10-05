"""The brain map (brain_map/): one Markdown page per module, capability, skill, tool, server and knowledge topic.

build_map() writes it from modules/*, the live MCP tools and the knowledge-library topics (at every start and on
"rebuild"). BrainMap reads it back - the router takes its Jev categories from these pages, so a hand edit of a page
(examples_extra, a "## Notes" section) changes routing and survives the next rebuild. Whether a tool needs a "yes"
comes from module.yaml only (a capability's `confirm:`), never from a hand edit here.

    Module --has--> Capability --includes--> Tool --served by--> Server;  Skill --uses--> Capability
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from . import okf
from .events import now_iso
from .modules import ModuleRegistry
from .tools import CONFIRM_TOOL, TOOLS, WEB_TOOLS

KEPT_ON_REBUILD = ("examples_extra",)
MAP_INTRO = ("What the brain is connected to and how the parts relate. Compiled from `modules/`, the live MCP servers "
             "and the knowledge library by `brain/atlas.py`. The router builds its Jev categories from these pages.\n\n"
             "Module --has--> Capability --includes--> Tool --served by--> Server;  Skill --uses--> Capability;  "
             "Module --uses--> Capability of another module.")
SERVER_KINDS = {"mcp": "MCP Server", "builtin": "Built-in tools", "server": "Claude server tools"}
WRITE_WORDS = re.compile(r"(create|update|delete|remove|send|submit|click|type|fill|select|respond|book|upload|"
                         r"drag|press|write|add|move|cancel|remember|save|file_upload|handle_dialog)", re.I)


def side_effect(name: str, hints: dict[str, Any] | None = None) -> str:
    """read / write / destructive / guard - from the MCP server's hints, else guessed from the tool name."""
    hints = hints or {}
    if name == CONFIRM_TOOL:
        return "guard"
    if hints.get("destructive"):
        return "destructive"
    if hints.get("read_only"):
        return "read"
    return "write" if WRITE_WORDS.search(name.split("__")[-1]) else "read"


def _params(schema: dict | None) -> list[dict[str, Any]]:
    schema = schema or {}
    required = set(schema.get("required", []))
    return [{"name": k, "type": v.get("type", "any") if isinstance(v, dict) else "any", "required": k in required,
             "description": (v.get("description", "") if isinstance(v, dict) else "")[:160]}
            for k, v in (schema.get("properties") or {}).items()]


def _tool(name, server, kind, short, description="", params=(), effect="read", status="online") -> dict[str, Any]:
    return {"name": name, "server": server, "kind": kind, "short": short, "description": description or "",
            "params": list(params), "side_effect": effect, "status": status}


def collect_tools(hub) -> tuple[dict[str, dict], dict[str, dict]]:
    """Every tool the brain can call (Alfred's own, Claude's web tools, each MCP server's) and every server."""
    servers = {"alfred": {"kind": "builtin", "status": "ready",
                          "description": "Alfred's own tools: session memory, tasks, spoken confirmation."},
               "anthropic": {"kind": "server", "status": "ready",
                             "description": "Tools Claude runs itself during a request (web search and fetch)."}}
    tools = {n: _tool(n, "alfred", "builtin", n, t["description"], _params(t["input_schema"]), side_effect(n))
             for n, t in TOOLS.items()}
    tools |= {n: _tool(n, "anthropic", "server", n, desc) for n, (_, desc) in WEB_TOOLS.items()}
    for state in hub.servers.values():
        cfg = state.config
        servers[state.name] = {"kind": "mcp", "status": state.status, "error": state.error,
                               "description": cfg.get("description", ""), "transport": cfg.get("type", "stdio"),
                               "command": " ".join([cfg.get("command", ""), *cfg.get("args", [])]).strip()
                               or cfg.get("url", "")}
        for t in state.tools:
            hints = state.hints.get(t["name"], {})
            tools[t["name"]] = _tool(t["name"], state.name, "mcp", hints.get("mcp_name") or t["name"].split("__", 1)[-1],
                                     t["description"], _params(t.get("input_schema")), side_effect(t["name"], hints))
    return tools, servers


def build_map(root: Path, registry: ModuleRegistry, hub, topic_sources: list[dict] | None = None) -> dict[str, Any]:
    """Write brain_map/. Returns counts and the list of changes (also appended to brain_map/log.md)."""
    root.mkdir(parents=True, exist_ok=True)
    before = {f.relative_to(root).as_posix(): okf.read(f) for f in root.rglob("*.md") if f.name != "log.md"
              or f.parent != root}
    tools, servers = collect_tools(hub)
    for meta, _ in before.values():   # a server that is offline right now keeps its tools on the map
        server = meta.get("server")
        if meta.get("type") == "Tool" and meta.get("id") not in tools and server in servers \
                and servers[server]["status"] != "ready":
            tools[meta["id"]] = _tool(meta["id"], server, meta.get("kind", "mcp"), meta.get("short", meta["id"]),
                                      meta.get("description", ""), [{"name": p, "type": "", "required": False,
                                                                     "description": ""} for p in meta.get("params", [])],
                                      meta.get("side_effect", "read"), "offline")

    modules = registry.modules.values()
    caps = {c.id: c for m in modules for c in m.capabilities.values()}
    cap_tools = {cid: sorted(n for n in tools if c.matches(n)) for cid, c in caps.items()}
    used_by: dict[str, list[str]] = {}
    for m in modules:
        for u in m.uses:
            used_by.setdefault(u, []).append(f"module:{m.id}")
        for s in m.skills:
            for u in s.uses:
                used_by.setdefault(u, []).append(f"skill:{s.id}")

    pages: dict[str, tuple[dict, str]] = {}
    stamp = now_iso()

    def page(path: str, meta: dict, *lines: str) -> None:
        body = "\n\n".join(l for l in lines if l is not None)
        pages[path] = ({**meta, "timestamp": stamp}, re.sub(r"\n\n(?=[-*|] )", "\n", body))

    def link(title: str, target: str, here: str) -> str:
        return f"[{title}]({'../' * here.count('/')}{target})"

    def cap_links(ids, here) -> list[str]:
        return [f"- {link(caps[c].label, f'capabilities/{c}.md', here)} (`{c}`)" for c in ids if c in caps]

    def tool_path(t: dict) -> str:
        return f"tools/{t['server']}/{okf.slugify(t['short'], 64)}.md"

    for m in modules:
        p = f"modules/{m.id}.md"
        own, borrowed = list(m.capabilities), [u for u in m.uses if u in caps]
        used_servers = sorted({tools[n]["server"] for c in own + borrowed for n in cap_tools.get(c, [])})
        page(p, {"type": "Module", "title": m.label, "description": m.description, "id": m.id, "capabilities": own,
                 "uses": borrowed, "skills": [s.id for s in m.skills], "servers": used_servers, "examples": m.examples,
                 "enabled": m.enabled, "model": m.model, "effort": m.effort, "tags": ["module"]},
             f"# {m.label}", m.description, "## Capabilities", "\n".join(cap_links(own, p)) or "- none",
             "## Borrowed capabilities\n" + "\n".join(cap_links(borrowed, p)) if borrowed else None,
             "## Skills\n" + "\n".join(f"- {link(s.name, f'skills/{s.id}.md', p)}" for s in m.skills) if m.skills else None,
             "## Connected servers\n" + "\n".join(f"- {link(s, f'servers/{s}.md', p)}" for s in used_servers),
             "## Example requests\n" + "\n".join(f"- {e}" for e in m.examples) if m.examples else None)
        for s in m.skills:
            sp = f"skills/{s.id}.md"
            page(sp, {"type": "Skill", "title": s.name, "description": s.description, "id": s.id, "module": m.id,
                      "uses": [u for u in s.uses if u in caps], "tags": ["skill", m.id]},
                 f"# {s.name}", s.description, f"Module: {link(m.id, f'modules/{m.id}.md', sp)}", "## Uses",
                 "\n".join(cap_links(s.uses, sp)) or "- -", "## Procedure", s.body)

    for cid, c in caps.items():
        p, names = f"capabilities/{cid}.md", cap_tools[cid]
        listed = [f"- {link(tools[n]['short'], tool_path(tools[n]), p)} - {tools[n]['server']}, {tools[n]['side_effect']}"
                  + ("" if tools[n]["status"] == "online" else ", offline") for n in names]
        page(p, {"type": "Capability", "title": c.label, "description": c.description, "id": cid, "module": c.module,
                 "tools": names, "tool_patterns": c.tools, "confirm": bool(c.confirm), "always": c.always,
                 "available": sum(tools[n]["status"] == "online" for n in names), "examples": c.examples,
                 "used_by": used_by.get(cid, []), "tags": ["capability", c.module]},
             f"# {c.label}", c.description, f"Module: {link(c.module, f'modules/{c.module}.md', p)}", "## Tools",
             "\n".join(listed) or "- no tool connected yet" + (f" (expects {', '.join(c.tools)})" if c.tools else ""),
             "## Used by\n" + "\n".join(f"- {u}" for u in used_by[cid]) if used_by.get(cid) else None,
             "## Example requests\n" + "\n".join(f"- {e}" for e in c.examples) if c.examples else None)

    for name, t in tools.items():
        p = tool_path(t)
        in_caps = [cid for cid, names in cap_tools.items() if name in names]
        said = [caps[c].confirm for c in in_caps if caps[c].confirm is not None]   # what module.yaml says decides
        params = ["| name | type | required | description |", "|---|---|---|---|"] + [
            f"| `{x['name']}` | {x['type']} | {'yes' if x['required'] else ''} | {x['description'].replace('|', '/')} |"
            for x in t["params"]]
        page(p, {"type": "Tool", "title": t["short"], "description": t["description"][:240], "id": name,
                 "server": t["server"], "kind": t["kind"], "short": t["short"], "capabilities": in_caps,
                 "modules": sorted({c.split(".", 1)[0] for c in in_caps}), "side_effect": t["side_effect"],
                 "requires_confirmation": any(said) if said else t["side_effect"] == "destructive",
                 "status": t["status"], "params": [x["name"] for x in t["params"]], "tags": ["tool", t["server"]]},
             f"# {t['short']}", t["description"], "Server: " + link(t["server"], f"servers/{t['server']}.md", p),
             "## Capabilities", "\n".join(cap_links(in_caps, p))
             or "- not assigned to any capability yet - add a pattern to a module's capabilities",
             "## Parameters\n" + "\n".join(params) if t["params"] else None)

    for name, info in servers.items():
        p, own_tools = f"servers/{name}.md", [t for t in tools.values() if t["server"] == name]
        page(p, {"type": SERVER_KINDS[info["kind"]], "title": name, "description": info.get("description", ""),
                 "id": name, "status": info["status"], "tools": [t["name"] for t in own_tools],
                 "tags": ["server", info["kind"]]},
             f"# {name}", info.get("description", ""),
             f"Status: **{info['status']}**" + (f" - {info['error']}" if info.get("error") else ""),
             f"Runs: `{info['command']}`" if info.get("command") else None,
             "## Tools", "\n".join(f"- {link(t['short'], tool_path(t), p)} - {t['side_effect']}" for t in own_tools)
             or "- no tools discovered yet (server not connected)")

    for src in topic_sources or []:     # subjects of the knowledge library, so Jev can route by topic
        folder, server, cap = Path(src["path"]), src["server"], src.get("capability")
        for f in sorted(folder.glob("*.md")) if folder.exists() else []:
            if f.name == "index.md":
                continue
            meta, body = okf.read(f)
            lines = body.splitlines()
            title = meta.get("title") or next((l[2:] for l in lines if l.startswith("# ")), f.stem)
            desc = str(meta.get("description") or next((l for l in lines if l and not l.startswith("#")), ""))
            p = f"topics/{server}/{f.stem}.md"
            where = f"Lives in {link(server, f'servers/{server}.md', p)}" + (
                f", reached through {link(cap, f'capabilities/{cap}.md', p)}" if cap else "")
            page(p, {"type": "Topic", "title": title, "description": desc[:240], "id": f"topic:{f.stem}",
                     "server": server, "capability": cap, "source": f.as_posix(), "tags": ["topic", server]},
                 f"# {title}", desc, where + ".")

    sections = {"modules": ("Modules", "The brain's lobes. The router's first question picks one."),
                "capabilities": ("Capabilities", "Groups of tools - the router's second question. Only the chosen "
                                                 "capabilities' tools are given to Claude."),
                "skills": ("Skills", "Procedures the executor follows. Jev can pick one directly."),
                "tools": ("Tools", "Every tool the brain can call, by server."),
                "servers": ("Servers", "Where tools live: MCP servers, Alfred's built-ins, Claude server tools."),
                "topics": ("Topics", "What the knowledge library covers - lets Jev route by subject.")}
    counts = {folder: sum(p.startswith(folder + "/") for p in pages) for folder in sections}
    for folder, (title, desc) in sections.items():
        items = [f"* [{pages[p][0]['title']}]({p.split('/', 1)[1]}) - {pages[p][0].get('description', '')[:120]}"
                 for p in sorted(pages) if p.startswith(folder + "/")]
        pages[f"{folder}/index.md"] = ({"type": "Index", "title": title, "description": desc, "timestamp": stamp},
                                       "\n".join([f"# {title}", desc, "", *items]))
    online = sum(t["status"] == "online" for t in tools.values())
    pages["index.md"] = ({"type": "Index", "title": "Alfred's brain map", "okf_version": "0.2", "timestamp": stamp,
                          "description": "Modules, capabilities, skills, tools, servers and topics of the brain."},
                         "\n".join(["# Alfred's brain map", MAP_INTRO, "", "# Sections",
                                    f"* [modules](modules/index.md) - {counts['modules']} modules",
                                    f"* [capabilities](capabilities/index.md) - {counts['capabilities']} capabilities",
                                    f"* [skills](skills/index.md) - {counts['skills']} skills",
                                    f"* [tools](tools/index.md) - {counts['tools']} tools, {online} online",
                                    "* [servers](servers/index.md) - "
                                    + ", ".join(f"{n} ({i['status']})" for n, i in servers.items()),
                                    f"* [topics](topics/index.md) - {counts['topics']} knowledge topics",
                                    "* [log](log.md) - changes between builds"]))

    changes = _write(root, pages, before)
    return {**counts, "changes": changes}


def _write(root: Path, pages: dict[str, tuple[dict, str]], before: dict[str, tuple[dict, str]]) -> list[str]:
    """Write only what changed, keep hand edits, delete pages that are gone, log the differences."""
    changes = []
    for rel, (meta, body) in pages.items():
        old = before.get(rel)
        if old:
            meta |= {k: old[0][k] for k in KEPT_ON_REBUILD if k in old[0]}
            if "## Notes" in old[1]:
                body = body.rstrip() + "\n\n## Notes" + old[1].split("## Notes", 1)[1]
            same = {k: v for k, v in old[0].items() if k != "timestamp"} == \
                   {k: v for k, v in meta.items() if k != "timestamp"}
            if same and old[1].strip() == body.strip():
                continue
            changes.append(f"changed {rel}")
        elif meta.get("type") != "Index":
            changes.append(f"added {rel}")
        okf.write(root / rel, meta, body)
    for rel in set(before) - set(pages):
        (root / rel).unlink(missing_ok=True)
        changes.append(f"removed {rel}")
    for folder in sorted(root.rglob("*"), reverse=True):
        if folder.is_dir() and not any(folder.iterdir()):
            shutil.rmtree(folder, ignore_errors=True)
    log = root / "log.md"
    if not log.exists():
        okf.write(log, {"type": "Log", "title": "Brain map change log",
                        "description": "What appeared, disappeared or changed between builds."}, "# Change log\n")
    changes = [c for c in changes if not c.endswith("index.md")]
    if changes:
        with log.open("a", encoding="utf-8") as fh:
            fh.write(f"\n## {now_iso()}\n" + "\n".join(f"- {c}" for c in changes[:200]) + "\n")
    return changes


class BrainMap:
    """brain_map/ read back into dicts (the page headers), by type and id."""

    def __init__(self, root: Path):
        self.root = root
        self.reload()

    def reload(self) -> None:
        self.modules, self.capabilities, self.skills, self.tools, self.servers, self.topics = {}, {}, {}, {}, {}, {}
        by_type = {"Module": self.modules, "Capability": self.capabilities, "Skill": self.skills, "Tool": self.tools,
                   "Topic": self.topics, **{kind: self.servers for kind in SERVER_KINDS.values()}}
        for f in self.root.rglob("*.md") if self.root.exists() else []:
            meta, _ = okf.read(f)
            if meta.get("type") in by_type:
                by_type[meta["type"]][meta.get("id")] = meta | {"path": f.relative_to(self.root).as_posix()}

    def page(self, relative_path: str) -> str:
        return okf.read_inside(self.root, relative_path)

    def enabled_modules(self) -> list[dict]:
        return [m for m in self.modules.values() if m.get("enabled", True)]

    def capabilities_of(self, module_ids: list[str]) -> list[str]:
        """Own and borrowed capabilities of these modules, in order, no duplicates."""
        ids = [c for mid in module_ids for c in (self.modules.get(mid, {}).get("capabilities") or [])
               + (self.modules.get(mid, {}).get("uses") or [])]
        return list(dict.fromkeys(ids))

    def always_capabilities(self, module_ids: list[str]) -> list[str]:
        return [c for c in self.capabilities_of(module_ids) if self.capabilities.get(c, {}).get("always")]

    def tools_of(self, cap_ids: list[str]) -> list[str]:
        """Online tools of these capabilities."""
        names = [n for c in cap_ids for n in self.capabilities.get(c, {}).get("tools") or []
                 if self.tools.get(n, {}).get("status", "online") == "online"]
        return list(dict.fromkeys(names))

    def needs_confirmation(self, tool: str) -> bool:
        return bool((self.tools.get(tool) or {}).get("requires_confirmation"))

    # ---- the texts Jev chooses between (id -> description) ----------------------------------------------------

    @staticmethod
    def _examples(meta: dict) -> str:
        ex = list(meta.get("examples") or [])[:3] + list(meta.get("examples_extra") or [])[:3]
        return " Examples: " + "; ".join(ex) if ex else ""

    def module_criteria(self) -> dict[str, str]:
        out = {}
        for m in self.enabled_modules():
            can = [self.capabilities[c]["title"] for c in m.get("capabilities", []) if c in self.capabilities]
            out[m["id"]] = f"{m['title']}. {m.get('description', '')}" + (
                f" Can: {'; '.join(can)}." if can else "") + self._examples(m)
        return out

    def capability_criteria(self) -> dict[str, str]:
        enabled = {m["id"] for m in self.enabled_modules()}
        return {cid: f"{c['title']}: {c.get('description', '')}" + self._examples(c)
                for cid, c in self.capabilities.items() if c.get("module") in enabled}

    def skill_criteria(self) -> dict[str, str]:
        enabled = {m["id"] for m in self.enabled_modules()}
        return {sid: f"{s['title']}: {s.get('description', '')}" for sid, s in self.skills.items()
                if s.get("module") in enabled}

    def topic_criteria(self) -> dict[str, str]:
        return {tid: f"{t['title']}: {t.get('description', '')}"[:200] for tid, t in self.topics.items()}

    def graph(self) -> dict[str, Any]:
        """Nodes and edges for the 3D brain in the UI."""
        nodes, edges = [], []
        for mid, m in self.modules.items():
            nodes.append({"id": f"module:{mid}", "label": mid, "kind": "module", "description": m.get("description", ""),
                          "enabled": m.get("enabled", True), "path": m["path"]})
            edges += [("router", f"module:{mid}", "routes to"), (f"module:{mid}", "executor", "runs on")]
            edges += [(f"module:{mid}", f"cap:{c}", "uses") for c in m.get("uses") or []]
        for cid, c in self.capabilities.items():
            nodes.append({"id": f"cap:{cid}", "label": c["title"], "kind": "capability", "path": c["path"],
                          "description": c.get("description", ""), "available": c.get("available", 0),
                          "confirm": c.get("confirm", False)})
            edges += [(f"module:{c['module']}", f"cap:{cid}", "has")]
            edges += [(f"cap:{cid}", f"tool:{t}", "includes") for t in c.get("tools") or []]
        for sid, s in self.skills.items():
            nodes.append({"id": f"skill:{sid}", "label": s["title"], "kind": "skill", "path": s["path"],
                          "description": s.get("description", "")})
            edges += [(f"module:{s['module']}", f"skill:{sid}", "has skill")]
            edges += [(f"skill:{sid}", f"cap:{c}", "uses") for c in s.get("uses") or []]
        for tid, t in self.tools.items():
            nodes.append({"id": f"tool:{tid}", "label": t.get("short", tid), "kind": "tool", "path": t["path"],
                          "description": t.get("description", ""), "status": t.get("status"),
                          "side_effect": t.get("side_effect"), "confirm": self.needs_confirmation(tid),
                          "server": t.get("server")})
            edges.append((f"tool:{tid}", f"mcp:{t['server']}", "served by"))
        for name, s in self.servers.items():
            nodes.append({"id": f"mcp:{name}", "label": name, "kind": "mcp", "status": s.get("status"),
                          "description": s.get("description", ""), "path": s["path"]})
        for tid, t in self.topics.items():
            nodes.append({"id": tid, "label": t["title"], "kind": "topic", "description": t.get("description", ""),
                          "path": t["path"]})
            edges.append((tid, f"mcp:{t['server']}", "lives in"))
        known = {n["id"] for n in nodes} | {"router", "executor"}
        return {"nodes": nodes, "edges": [{"source": a, "target": b, "rel": rel} for a, b, rel in edges
                                          if a in known and b in known]}
