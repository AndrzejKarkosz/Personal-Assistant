"""Tool catalogue: every tool the brain can reach right now, with where it lives and what it does."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..executor import builtin
from ..executor.builtin import SERVER_TOOLS

BUILTIN_SERVER = "alfred"          # the brain's own tools (memory, tasks, confirmation)
ANTHROPIC_SERVER = "anthropic"     # Claude server tools (web search / fetch)

_WRITE = re.compile(r"(create|update|delete|remove|send|submit|click|type|fill|select|respond|book|upload|"
                    r"drag|press|write|add|move|cancel|remember|file_upload|handle_dialog)", re.I)


@dataclass
class ToolInfo:
    name: str                      # the name Claude sees: "<server>__<tool>" for MCP, plain for the rest
    server: str
    kind: str                      # mcp | builtin | server
    short: str                     # tool name inside its server
    description: str = ""
    params: list[dict[str, Any]] = field(default_factory=list)
    side_effect: str = "read"      # read | write | destructive | guard
    status: str = "online"         # online | offline


def _params(schema: dict[str, Any] | None) -> list[dict[str, Any]]:
    schema = schema or {}
    required = set(schema.get("required", []))
    return [{"name": k, "type": v.get("type", "any") if isinstance(v, dict) else "any",
             "required": k in required,
             "description": (v.get("description", "") if isinstance(v, dict) else "")[:160]}
            for k, v in (schema.get("properties") or {}).items()]


def side_effect(name: str, hints: dict[str, Any] | None = None) -> str:
    hints = hints or {}
    if name == builtin.CONFIRM_TOOL:
        return "guard"
    if hints.get("destructive"):
        return "destructive"
    if hints.get("read_only"):
        return "read"
    return "write" if _WRITE.search(name.split("__")[-1]) else "read"


def collect(hub) -> tuple[dict[str, ToolInfo], dict[str, dict[str, Any]]]:
    """Returns (tools by Claude name, server info by server name)."""
    tools: dict[str, ToolInfo] = {}
    servers: dict[str, dict[str, Any]] = {
        BUILTIN_SERVER: {"kind": "builtin", "status": "ready",
                         "description": "Alfred's own tools: session memory, tasks, spoken confirmation."},
        ANTHROPIC_SERVER: {"kind": "server", "status": "ready",
                           "description": "Tools executed by Anthropic's servers during a Claude request."},
    }
    for t in builtin.BUILTIN_TOOLS:
        tools[t["name"]] = ToolInfo(t["name"], BUILTIN_SERVER, "builtin", t["name"], t["description"],
                                    _params(t.get("input_schema")), side_effect(t["name"]))
    for name, spec in SERVER_TOOLS.items():
        tools[name] = ToolInfo(name, ANTHROPIC_SERVER, "server", name,
                               {"web_search": "Search the web for current information.",
                                "web_fetch": "Fetch and read a web page by URL."}.get(name, spec["type"]))
    for state in hub.servers.values():
        cfg = state.config
        servers[state.name] = {
            "kind": "mcp", "status": state.status, "error": state.error,
            "description": cfg.get("description", ""), "transport": cfg.get("type", "stdio"),
            "command": " ".join([cfg.get("command", "")] + cfg.get("args", [])).strip() or cfg.get("url", ""),
        }
        for t in state.tools:
            hints = state.hints.get(t["name"], {})
            tools[t["name"]] = ToolInfo(
                t["name"], state.name, "mcp", hints.get("mcp_name") or t["name"].split("__", 1)[-1],
                t["description"], _params(t.get("input_schema")), side_effect(t["name"], hints))
    return tools, servers
