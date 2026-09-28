"""Shared fixtures: a Brain wired to temp dirs, a fake Claude client and no MCP servers."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from brain import config
from brain.config import Settings
from brain.executor import MCPHub


@dataclass
class FakeBlock:
    type: str
    text: str = ""
    id: str = ""
    name: str = ""
    input: dict = field(default_factory=dict)

    def model_dump(self, **_: Any) -> dict:          # lets the SDK-style append work in tests
        return {k: v for k, v in self.__dict__.items() if v not in ("", {}, None)}


def text_response(text: str, stop: str = "end_turn"):
    return SimpleNamespace(content=[FakeBlock("text", text=text)], stop_reason=stop,
                           usage=SimpleNamespace(input_tokens=100, output_tokens=20,
                                                 cache_read_input_tokens=0, cache_creation_input_tokens=0))


def tool_response(name: str, args: dict, preface: str = "", call_id: str = "tu_1"):
    blocks = ([FakeBlock("text", text=preface)] if preface else []) + [
        FakeBlock("tool_use", id=call_id, name=name, input=args)]
    return SimpleNamespace(content=blocks, stop_reason="tool_use",
                           usage=SimpleNamespace(input_tokens=120, output_tokens=30,
                                                 cache_read_input_tokens=0, cache_creation_input_tokens=0))


class FakeMessages:
    def __init__(self, script: list):
        self.script = script
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if "output_config" in kwargs and "format" in kwargs["output_config"]:
            # structured output request (session summary / fallback router)
            return text_response(json.dumps(self._structured(kwargs)))
        return self.script.pop(0) if self.script else text_response("Gotowe.")

    @staticmethod
    def _structured(kwargs) -> dict:
        props = kwargs["output_config"]["format"]["schema"]["properties"]
        if "module" in props:
            return {"module": "tasks", "second_module": "none", "capabilities": ["tasks.manage"], "skill": "none",
                    "topic": "none", "confidence": 0.9, "urgency": 1, "acts_on_world": False, "needs_history": False}
        return {"title": "Test session", "summary": "User asked for a reminder.", "domains": ["tasks"],
                "done": ["created reminder"], "changed": [], "open_threads": ["call mum"],
                "facts": [{"category": "people", "title": "Mum", "content": "Andrzej calls mum on Sundays"}]}


class FakeAnthropic:
    def __init__(self, script: list | None = None):
        self.messages = FakeMessages(script or [])
        self.beta = SimpleNamespace(messages=self.messages)


@pytest.fixture
def settings(tmp_path: Path, monkeypatch) -> Settings:
    for key in ("ANTHROPIC_API_KEY", "JEV_API_KEY", "ELEVENLABS_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    # UI overrides (data/settings.json) would leak the developer's local settings into tests - and back.
    monkeypatch.setattr(config, "OVERRIDES_FILE", tmp_path / "settings.json")
    s = Settings.load()
    s.data["llm"] = {"backend": "api"}
    s.data["map"] = {"dir": str(tmp_path / "brain_map"), "topic_sources": []}
    s.data["memory"]["dir"] = str(tmp_path / "memory")
    s.data["logging"]["dir"] = str(tmp_path / "logs")
    empty = tmp_path / "mcp.json"
    empty.write_text('{"mcpServers": {}}')
    s.data["mcp_config"] = str(empty)
    return s


@pytest.fixture
def http(monkeypatch):
    """Answer every httpx.AsyncClient request with a handler: http(lambda request: httpx.Response(200))."""
    real = httpx.AsyncClient

    def install(handler):
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    return install


@pytest.fixture
def make_brain(settings, tmp_path):
    from brain.pipeline import Brain

    def _make(script: list | None = None):
        fake = FakeAnthropic(script)
        brain = Brain(settings, anthropic_client=fake, hub=MCPHub(Path(settings.data["mcp_config"])))
        brain.rebuild_map()
        return brain, fake
    return _make
