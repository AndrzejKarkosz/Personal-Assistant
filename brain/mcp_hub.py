"""Connections to the MCP servers from config/mcp.json (knowledge base, Google Calendar, browser ...).

All servers are connected once at start-up and stay connected. Their tools get names like
"google-calendar__list-events" (server + "__" + tool), which is how the rest of the brain refers to them.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

log = logging.getLogger("alfred.mcp")


@dataclass
class ServerState:
    name: str
    config: dict[str, Any]
    status: str = "disabled"            # disabled | connecting | ready | error
    error: str | None = None
    tools: list[dict[str, Any]] = field(default_factory=list)       # name, description, input_schema
    hints: dict[str, dict[str, Any]] = field(default_factory=dict)  # per tool: mcp_name, title, read_only, destructive
    session: Any = None


def compact(text: str, drop: set[str]) -> str:
    """Shrink a JSON tool result (minify, remove `drop` keys and empty values) - it stays in Claude's context for
    every later round. Text that is not JSON passes through untouched."""
    try:
        data = json.loads(text)
    except ValueError:
        return text

    def clean(x: Any) -> Any:
        if isinstance(x, dict):
            return {k: clean(v) for k, v in x.items() if k not in drop and v not in (None, "", [], {})}
        return [clean(v) for v in x] if isinstance(x, list) else x
    return json.dumps(clean(data), ensure_ascii=False, separators=(",", ":"))


class MCPHub:
    def __init__(self, config_path: Path):
        data = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
        self.servers = {name: ServerState(name, cfg, "connecting" if cfg.get("enabled", True) else "disabled")
                        for name, cfg in data.get("mcpServers", {}).items()}
        self._owner: dict[str, tuple[str, str]] = {}    # "server__tool" -> (server, tool name on that server)
        self._stop = asyncio.Event()
        self._ready = asyncio.Event()
        self._task: asyncio.Task | None = None

    async def start(self, timeout_s: float = 30.0) -> None:
        # The connections live in one background task: MCP clients must be opened and closed in the same task.
        self._task = asyncio.create_task(self._run(), name="mcp-hub")
        try:
            await asyncio.wait_for(self._ready.wait(), timeout_s)
        except asyncio.TimeoutError:
            log.warning("MCP hub: some servers are still connecting after %ss", timeout_s)

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, 10)
            except Exception:
                self._task.cancel()

    async def _run(self) -> None:
        async with AsyncExitStack() as stack:
            for state in self.servers.values():
                if state.status == "disabled":
                    continue
                try:
                    await asyncio.wait_for(self._connect(stack, state), 25)
                    state.status = "ready"
                except Exception as exc:
                    state.status, state.error = "error", f"{type(exc).__name__}: {exc}"
                    log.warning("MCP server %s failed: %s", state.name, state.error)
            self._ready.set()
            await self._stop.wait()

    async def _connect(self, stack: AsyncExitStack, state: ServerState) -> None:
        cfg = state.config
        if cfg.get("type", "stdio") == "stdio":
            params = StdioServerParameters(command=shutil.which(cfg["command"]) or cfg["command"],
                                           args=cfg.get("args", []), cwd=cfg.get("cwd"),
                                           env={**os.environ, **cfg["env"]} if cfg.get("env") else None)
            read, write = await stack.enter_async_context(stdio_client(params))
        else:
            http = await stack.enter_async_context(create_mcp_http_client(headers=cfg.get("headers")))
            read, write = await stack.enter_async_context(streamable_http_client(cfg["url"], http_client=http))
        state.session = await stack.enter_async_context(ClientSession(read, write))
        await state.session.initialize()
        for tool in (await state.session.list_tools()).tools:
            name = re.sub(r"[^a-zA-Z0-9_-]", "_", f"{state.name}__{tool.name}")[:64]
            self._owner[name] = (state.name, tool.name)
            state.tools.append({"name": name, "description": (tool.description or tool.name)[:1024],
                                "input_schema": getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None)
                                or {"type": "object", "properties": {}}})
            notes = getattr(tool, "annotations", None)
            state.hints[name] = {"mcp_name": tool.name, "title": getattr(tool, "title", None) or getattr(notes, "title", None),
                                 "read_only": getattr(notes, "read_only_hint", None),
                                 "destructive": getattr(notes, "destructive_hint", None)}

    def all_tools(self) -> dict[str, dict[str, Any]]:
        """Tools of every connected server, by name."""
        return {t["name"]: t for s in self.servers.values() if s.status == "ready" for t in s.tools}

    def owns(self, name: str) -> bool:
        return name in self._owner

    async def call(self, name: str, arguments: dict[str, Any]) -> tuple[str, bool]:
        """Run a tool; returns (text for Claude, is_error)."""
        server, tool = self._owner[name]
        result = await self.servers[server].session.call_tool(tool, arguments)
        drop = set(self.servers[server].config.get("drop_fields", []))
        parts = [compact(b.text, drop) if getattr(b, "text", None) is not None else f"[{getattr(b, 'type', 'content')}]"
                 for b in getattr(result, "content", None) or []]
        is_error = getattr(result, "is_error", None) or getattr(result, "isError", False)
        return "\n".join(parts)[:20000], bool(is_error)

    def status(self) -> list[dict[str, Any]]:
        return [{"name": s.name, "status": s.status, "error": s.error, "description": s.config.get("description", ""),
                 "tools": [t["name"] for t in s.tools]} for s in self.servers.values()]
