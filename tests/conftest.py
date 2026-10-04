from __future__ import annotations

from contextlib import AsyncExitStack
from pathlib import Path

import claude_agent_sdk as sdk
import httpx
import pytest
from mcp import Client

from brain import config
from brain.config import Settings
from brain.mcp_hub import MCPHub
from brain.router import JevClient, JevError

ROUTED = {"module": "tasks", "second_module": "none", "capabilities": ["tasks.manage"], "skill": "none",
          "topic": "none", "confidence": 0.9, "urgency": 1, "acts_on_world": False, "needs_history": False}
SUMMARY = {"title": "Test session", "summary": "User asked for a reminder.", "domains": ["tasks"],
           "done": ["created reminder"], "changed": [], "open_threads": ["call mum"],
           "facts": [{"category": "people", "title": "Mum", "content": "Andrzej calls mum on Sundays"}]}


def result(text: str = "", structured: dict | None = None, cost: float = 0.002, **extra) -> sdk.ResultMessage:
    return sdk.ResultMessage(subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=1,
                             session_id="s", usage={"input_tokens": 100, "output_tokens": 20}, total_cost_usd=cost,
                             result=text, structured_output=structured, **extra)


class FakeClaude:
    """Stands in for Claude Code (claude_agent_sdk.query) - tests never start the real one.

    Offline by default (every call fails), like a machine without Claude Code. Once `online`:
    - quick JSON questions (router fallback, session summary) get a canned answer;
    - the executor plays `script`: a str is the final answer, ("tool", name, args) is a tool call that really goes
      through Alfred's tool server - shield, guard and handlers included. Results land in `tool_results`.
    """

    def __init__(self):
        self.online = False
        self.routed = dict(ROUTED)          # what the router fallback answers
        self.script: list = []
        self.calls: list[tuple[str, sdk.ClaudeAgentOptions]] = []
        self.tool_results: list[tuple[str, str, bool]] = []

    async def query(self, *, prompt, options):
        if not self.online:
            raise RuntimeError("Claude Code is not logged in")
        if options.output_format:
            asked = options.output_format["schema"]["properties"]
            yield result(structured=self.routed if "module" in asked else SUMMARY, cost=0.0001)
            return
        self.calls.append((prompt, options))
        answer = "Gotowe."
        async with AsyncExitStack() as stack:
            server = options.mcp_servers.get("alfred", {}).get("instance")
            client = await stack.enter_async_context(Client(server)) if server else None
            while self.script:
                step = self.script.pop(0)
                if isinstance(step, str):
                    answer = step
                    break
                kind, name, args = step
                yield sdk.AssistantMessage(
                    content=[sdk.ToolUseBlock(id="t", name=name if kind == "web" else f"mcp__alfred__{name}", input=args)],
                    model="m", usage={"input_tokens": 100, "output_tokens": 20}, stop_reason="tool_use")
                if kind == "web":       # ("web", "WebFetch", {...}): Claude Code read a web page by itself
                    continue
                out = await client.call_tool(name, args)
                self.tool_results.append((name, out.content[0].text, bool(out.is_error)))
        yield sdk.AssistantMessage(content=[sdk.TextBlock(text=answer)], model="m", stop_reason="end_turn",
                                   usage={"input_tokens": 100, "output_tokens": 20})
        yield result(answer)


class ShieldJev(JevClient):
    """Jev that answers the shield's questions (`breach` decides). Routing questions fail, so Claude routes -
    unless a test sets `routing` (Jev's answers to the router's questions)."""

    def __init__(self):
        super().__init__("key", "http://jev", "jev")
        self.breach = False
        self.routing: dict | None = None

    async def ask(self, state, questions):
        key = next(iter(questions))
        if key in ("injection", "unsafe_action"):
            return {"answers": {key: {"noul": 0.9 if self.breach else 0.1}}}
        if self.routing is None:
            raise JevError("only the shield asks this Jev")
        return {"answers": self.routing}


@pytest.fixture(autouse=True)
def claude(request, monkeypatch) -> FakeClaude | None:
    if request.node.get_closest_marker("live"):     # tests/test_live.py talks to the real Claude Code
        return None
    fake = FakeClaude()
    monkeypatch.setattr(sdk, "query", fake.query)
    return fake


@pytest.fixture
def settings(tmp_path: Path, monkeypatch) -> Settings:
    for key in ("ANTHROPIC_API_KEY", "JEV_API_KEY", "ELEVENLABS_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(config, "OVERRIDES_FILE", tmp_path / "settings.json")
    s = Settings.load()
    s.data["models"]["executor"] = "claude-opus-5"
    s.data["assistant"].update(reply_language="", context_capabilities=[])   # tests opt in to these
    s.data["map"] = {"dir": str(tmp_path / "brain_map"), "topic_sources": []}
    s.data["memory"]["dir"] = str(tmp_path / "memory")
    s.data["proactive"]["routines"] = str(tmp_path / "routines.yaml")
    s.data["logging"]["dir"] = str(tmp_path / "logs")
    (tmp_path / "mcp.json").write_text('{"mcpServers": {}}')
    s.data["mcp_config"] = str(tmp_path / "mcp.json")
    return s


@pytest.fixture
def http(monkeypatch):
    real = httpx.AsyncClient

    def install(handler):
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    return install


@pytest.fixture
def make_brain(settings, claude):
    """make_brain("answer", ("tool", "task_list", {}), ...) -> (brain, fake Claude playing that script)."""
    from brain.pipeline import Brain

    def _make(*script):
        claude.online = True
        claude.script += list(script)
        brain = Brain(settings, hub=MCPHub(Path(settings.data["mcp_config"])))
        brain.router.jev = ShieldJev()
        brain.rebuild_map()
        return brain, claude
    return _make
