import json
import os
import shutil
import subprocess
from datetime import datetime
from types import SimpleNamespace

import claude_agent_sdk
import pytest
from conftest import result

from brain import config, llm
from brain.config import Settings
from brain.events import ActivityLog, EventBus


def test_settings_dotted_access_paths_and_persisted_overrides(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OVERRIDES_FILE", tmp_path / "settings.json")
    s = Settings({"a": {"b": 1, "c": {"d": 2}}, "rel": "data/x", "abs": str(tmp_path)})
    assert s.get("a.c.d") == 2 and s.get("a.nope", "dflt") == "dflt" and s.get("a.b.c") is None
    assert s.path("rel") == config.ROOT / "data" / "x" and s.path("abs") == tmp_path

    s.update({"a": {"c": {"e": 3}}})
    assert s.get("a.c.d") == 2 and s.get("a.c.e") == 3
    assert json.loads((tmp_path / "settings.json").read_text()) == {"a": {"c": {"e": 3}}}
    loaded = Settings.load()
    assert loaded.get("a.c.e") == 3 and loaded.get("assistant.name") == "Alfred"


def test_secrets_come_from_the_environment(monkeypatch):
    for key in ("JEV_API_KEY", "ELEVENLABS_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("JEV_API_KEY", "jev")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "env-voice")
    s = Settings({})
    assert s.keys() == {"jev": True, "elevenlabs": False}
    assert s.voice_id == "env-voice"
    s.data["voice"] = {"voice_id": "ui-voice"}
    assert s.voice_id == "ui-voice"


def test_activity_log_keeps_everything_but_audio(tmp_path):
    bus = EventBus(ActivityLog(tmp_path))
    queue = bus.subscribe()
    bus.emit("answer", "voice", "r-1", "s-1", text="hej", audio_b64="AAAA")
    bus.emit("ack", "voice", text="ok")

    assert queue.get_nowait().data["audio_b64"] == "AAAA"
    rows = bus.log.read()
    assert [r["kind"] for r in rows] == ["answer", "ack"] and "audio_b64" not in rows[0]["data"]
    assert rows[0]["request_id"] == "r-1" and rows[0]["session_id"] == "s-1"
    assert bus.log.read(kind="ack")[0]["data"] == {"text": "ok"}
    assert [r["kind"] for r in bus.log.read(limit=1)] == ["ack"]
    assert bus.log.days() == [datetime.now().strftime("%Y-%m-%d")]
    assert bus.log.read(day="1999-01-01") == []


def test_a_slow_subscriber_never_blocks_the_bus():
    bus = EventBus()
    queue = bus.subscribe()
    for i in range(600):
        bus.emit("tick", "brain", n=i)
    assert queue.qsize() == 500
    bus.unsubscribe(queue)
    bus.emit("tick", "brain")
    assert queue.qsize() == 500


def test_the_api_key_is_hidden_so_the_subscription_is_used(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    llm.hide_api_key()
    assert "ANTHROPIC_API_KEY" not in os.environ


async def test_ask_json_runs_a_bare_claude_code(tmp_path, monkeypatch):
    seen = {}

    async def fake_query(*, prompt, options):
        seen["prompt"], seen["options"] = prompt, options
        yield claude_agent_sdk.AssistantMessage(content=[claude_agent_sdk.TextBlock(text="myślę")], model="m")
        yield result("plain text", structured={"module": "tasks"})

    monkeypatch.setattr(claude_agent_sdk, "query", fake_query)
    s = Settings({"memory": {"dir": str(tmp_path / "memory")}, "models": {"light": "claude-haiku-4-5"}})
    schema = {"type": "object"}
    answer, usage = await llm.ask_json(s, "hej", schema, system="route")
    assert answer == {"module": "tasks"} and (usage["input"], usage["output"]) == (100, 20)
    opts = seen["options"]
    assert opts.output_format == {"type": "json_schema", "schema": schema} and seen["prompt"] == "hej"
    assert opts.tools == [] and opts.setting_sources == [] and opts.cwd == str(tmp_path)
    assert opts.model == "claude-haiku-4-5" and opts.system_prompt == "route"

    async def no_json(*, prompt, options):
        yield result("plain text")
    monkeypatch.setattr(claude_agent_sdk, "query", no_json)
    with pytest.raises(RuntimeError):
        await llm.ask_json(s, "hej", schema)


def test_subscription_status_reads_claude_auth(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: None)
    assert llm.subscription_status()["ok"] is False

    monkeypatch.setattr(shutil, "which", lambda _: "claude")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: SimpleNamespace(
        stdout='{"loggedIn": true, "authMethod": "claude.ai"}'))
    assert llm.subscription_status() == {"ok": True, "method": "claude.ai", "detail": "subscription (claude.ai)"}

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: SimpleNamespace(stdout="not json"))
    assert llm.subscription_status()["ok"] is False


def test_what_alfred_says_to_an_empty_room_waits_for_the_ui():
    bus = EventBus()
    bus.emit("answer", "voice", text="Brief gotowy.", source="routine")
    bus.emit("answer", "voice", text="Odpowiedź", source="user")
    bus.emit("ack", "voice", text="Już")
    ui = bus.subscribe()
    assert [ui.get_nowait().data["text"] for _ in range(ui.qsize())] == ["Brief gotowy."]
    assert bus.subscribe().empty()
    bus.emit("answer", "voice", text="Przypomnienie", source="proactive")
    assert not bus.unheard
