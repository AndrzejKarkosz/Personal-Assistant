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

log = logging.getLogger("alfred.mcp")


@dataclass
class ServerState:
    name: str
    config: dict[str, Any]
    status: str = "disabled"
    error: str | None = None
    tools: list[dict[str, Any]] = field(default_factory=list)
    hints: dict[str, dict[str, Any]] = field(default_factory=dict)
    session: Any = None


def compact(text: str, drop: set[str]) -> str:
    """Minify a JSON tool result and strip `drop` keys and empty values - it stays in the context for every
    later agent round. Non-JSON text passes through untouched."""
    try:
        data = json.loads(text)
    except ValueError:
        return text

    def clean(x: Any) -> Any:
        if isinstance(x, dict):
            return {k: clean(v) for k, v in x.items() if k not in drop and v not in (None, "", [], {})}
        return [clean(v) for v in x] if isinstance(x, list) else x
    return json.dumps(clean(data), ensure_ascii=False, separators=(",", ":"))


def claude_tool_name(server: str, tool: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", f"{server}__{tool}")[:64]


class MCPHub:
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.servers: dict[str, ServerState] = {}
        self._name_map: dict[str, tuple[str, str]] = {}
        self._stop = asyncio.Event()
        self._ready = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._load_config()

    def _load_config(self) -> None:
        data = json.loads(self.config_path.read_text(encoding="utf-8")) if self.config_path.exists() else {}
        for name, cfg in data.get("mcpServers", {}).items():
            self.servers[name] = ServerState(name=name, config=cfg,
                                             status="connecting" if cfg.get("enabled", True) else "disabled")

    async def start(self, timeout_s: float = 30.0) -> None:
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
            except (asyncio.TimeoutError, Exception):
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
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        cfg = state.config
        if cfg.get("type", "stdio") == "stdio":
            command = shutil.which(cfg["command"]) or cfg["command"]
            params = StdioServerParameters(
                command=command,
                args=cfg.get("args", []),
                env={**os.environ, **cfg.get("env", {})} if cfg.get("env") else None,
                cwd=cfg.get("cwd"),
            )
            read, write = await stack.enter_async_context(stdio_client(params))
        else:
            from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client
            http = await stack.enter_async_context(create_mcp_http_client(headers=cfg.get("headers")))
            read, write = await stack.enter_async_context(streamable_http_client(cfg["url"], http_client=http))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        listed = await session.list_tools()
        state.session = session
        state.tools = []
        for tool in listed.tools:
            name = claude_tool_name(state.name, tool.name)
            self._name_map[name] = (state.name, tool.name)
            schema = getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None)
            state.tools.append({
                "name": name,
                "description": (tool.description or tool.name)[:1024],
                "input_schema": schema or {"type": "object", "properties": {}},
            })
            ann = getattr(tool, "annotations", None)
            state.hints[name] = {
                "mcp_name": tool.name,
                "title": getattr(tool, "title", None) or getattr(ann, "title", None),
                "read_only": getattr(ann, "read_only_hint", None) if ann else None,
                "destructive": getattr(ann, "destructive_hint", None) if ann else None,
            }

    def all_tools(self) -> dict[str, dict[str, Any]]:
        return {t["name"]: t for s in self.servers.values() if s.status == "ready" for t in s.tools}

    def tools_for(self, server_names: list[str]) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        for name in server_names:
            state = self.servers.get(name)
            if state and state.status == "ready":
                tools.extend(state.tools)
        return tools

    def owns(self, claude_name: str) -> bool:
        return claude_name in self._name_map

    async def call(self, claude_name: str, arguments: dict[str, Any]) -> tuple[str, bool]:
        server, tool = self._name_map[claude_name]
        session = self.servers[server].session
        result = await session.call_tool(tool, arguments)
        drop = set(self.servers[server].config.get("drop_fields", []))
        parts = []
        for block in getattr(result, "content", None) or []:
            text = getattr(block, "text", None)
            parts.append(compact(text, drop) if text is not None else f"[{getattr(block, 'type', 'content')}]")
        is_error = getattr(result, "is_error", None) or getattr(result, "isError", False)
        return "\n".join(parts)[:20000], bool(is_error)

    def status(self) -> list[dict[str, Any]]:
        return [{
            "name": s.name, "status": s.status, "error": s.error,
            "description": s.config.get("description", ""), "tools": [t["name"] for t in s.tools],
        } for s in self.servers.values()]
