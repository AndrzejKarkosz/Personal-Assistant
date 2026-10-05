"""Connections to the MCP servers from config/mcp.json (knowledge base, Google Calendar, browser ...).

All servers are connected once at start-up and stay connected. Their tools get names like
"google-calendar__list-events" (server + "__" + tool), which is how the rest of the brain refers to them.
A remote server with "oauth": true (nutrition-mcp.com) opens your browser to log in the first time; its tokens are
kept in data/oauth/<server>.json and refreshed by themselves.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import webbrowser
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from mcp import ClientSession, StdioServerParameters
from mcp.client.auth import AuthorizationCodeResult, OAuthClientProvider
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken

from .config import ROOT

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


class FileTokens:
    """OAuth tokens and the registered client of one server, in one JSON file (OAuthClientProvider's storage)."""
    def __init__(self, path: Path):
        self.path = path

    def _load(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}

    def _save(self, key: str, value: Any) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = self._load() | {key: value.model_dump(mode="json", exclude_none=True)}
        self.path.write_text(json.dumps(data), encoding="utf-8")

    async def get_tokens(self) -> OAuthToken | None:
        return OAuthToken(**t) if (t := self._load().get("tokens")) else None

    async def set_tokens(self, tokens: OAuthToken) -> None:
        self._save("tokens", tokens)

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        return OAuthClientInformationFull(**c) if (c := self._load().get("client")) else None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        self._save("client", client_info)


async def _open_browser(url: str) -> None:
    log.warning("MCP login - finish it in the browser: %s", url)
    print(f"Jeśli przeglądarka się nie otworzyła, wejdź na: {url}", flush=True)
    webbrowser.open(url)


async def _wait_for_code(port: int) -> AuthorizationCodeResult:
    """The authorization server sends the browser back to http://localhost:<port>/callback?code=..."""
    got: asyncio.Future = asyncio.get_running_loop().create_future()

    async def on_request(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        target = (await reader.readline()).decode(errors="replace").split(" ")
        query = {k: v[0] for k, v in parse_qs(urlparse(target[1] if len(target) > 1 else "").query).items()}
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain; charset=utf-8\r\nConnection: close\r\n\r\n"
                     + "Zalogowano - możesz wrócić do Alfreda.".encode())
        await writer.drain()
        writer.close()
        if "code" in query and not got.done():
            got.set_result(AuthorizationCodeResult(code=query["code"], state=query.get("state"), iss=query.get("iss")))

    async with await asyncio.start_server(on_request, "localhost", port):
        return await got


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

    @property
    def ready(self) -> bool:
        """Every enabled server has finished connecting (ready or error)."""
        return self._ready.is_set()

    async def wait_ready(self) -> None:
        await self._ready.wait()

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, 10)
            except Exception:
                self._task.cancel()

    async def _run(self) -> None:
        async with AsyncExitStack() as stack:
            # OAuth servers last and with time for you to log in, so they never hold up the others
            for state in sorted(self.servers.values(), key=lambda s: bool(s.config.get("oauth"))):
                if state.status == "disabled":
                    continue
                try:
                    await asyncio.wait_for(self._connect(stack, state), 300 if state.config.get("oauth") else 25)
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
            http = await stack.enter_async_context(create_mcp_http_client(
                headers=cfg.get("headers"), auth=self._oauth(state) if cfg.get("oauth") else None))
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

    def _oauth(self, state: ServerState) -> OAuthClientProvider:
        port = int(state.config.get("oauth_port", 8722))
        meta = OAuthClientMetadata(client_name="Alfred", redirect_uris=[f"http://localhost:{port}/callback"],
                                   grant_types=["authorization_code", "refresh_token"], response_types=["code"])
        return OAuthClientProvider(state.config["url"], meta, FileTokens(ROOT / "data" / "oauth" / f"{state.name}.json"),
                                   redirect_handler=_open_browser, callback_handler=lambda: _wait_for_code(port))

    def all_tools(self) -> dict[str, dict[str, Any]]:
        """Tools of every connected server, by name."""
        return {t["name"]: t for s in self.servers.values() if s.status == "ready" for t in s.tools}

    def owns(self, name: str) -> bool:
        return name in self._owner

    async def call(self, name: str, arguments: dict[str, Any], limit: int | None = 20000) -> tuple[str, bool]:
        """Run a tool; returns (text, is_error). `limit` keeps Claude's context small - the UI passes None, because
        cut JSON (a month or a year of events) cannot be parsed."""
        server, tool = self._owner[name]
        result = await self.servers[server].session.call_tool(tool, arguments)
        drop = set(self.servers[server].config.get("drop_fields", []))
        parts = [compact(b.text, drop) if getattr(b, "text", None) is not None else f"[{getattr(b, 'type', 'content')}]"
                 for b in getattr(result, "content", None) or []]
        is_error = getattr(result, "is_error", None) or getattr(result, "isError", False)
        return "\n".join(parts)[:limit], bool(is_error)

    async def call_json(self, name: str, arguments: dict[str, Any]) -> Any:
        """A tool's result as data, for the UI: its structuredContent, else its text parsed as JSON."""
        server, tool = self._owner[name]
        result = await self.servers[server].session.call_tool(tool, arguments)
        text = "\n".join(getattr(b, "text", "") or "" for b in getattr(result, "content", None) or [])
        if getattr(result, "is_error", None) or getattr(result, "isError", False):
            raise RuntimeError(text[:300] or f"{name} failed")
        data = getattr(result, "structured_content", None)
        return data if data is not None else json.loads(text)

    def status(self) -> list[dict[str, Any]]:
        return [{"name": s.name, "status": s.status, "error": s.error, "description": s.config.get("description", ""),
                 "tools": [t["name"] for t in s.tools]} for s in self.servers.values()]
