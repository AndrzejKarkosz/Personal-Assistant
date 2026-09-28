"""Settings, the event bus / activity log and the LLM backend switch."""
import json
import os
import shutil
import subprocess
from datetime import datetime
from types import SimpleNamespace

import claude_agent_sdk

from brain import config, llm
from brain.config import Settings
from brain.events import ActivityLog, EventBus


def test_settings_dotted_access_paths_and_persisted_overrides(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OVERRIDES_FILE", tmp_path / "settings.json")
    s = Settings({"a": {"b": 1, "c": {"d": 2}}, "rel": "data/x", "abs": str(tmp_path)})
    assert s.get("a.c.d") == 2 and s.get("a.nope", "dflt") == "dflt" and s.get("a.b.c") is None
    assert s.path("rel") == config.ROOT / "data" / "x" and s.path("abs") == tmp_path

    s.update({"a": {"c": {"e": 3}}})
    assert s.get("a.c.d") == 2 and s.get("a.c.e") == 3                  # deep merge keeps siblings
    assert json.loads((tmp_path / "settings.json").read_text()) == {"a": {"c": {"e": 3}}}
    loaded = Settings.load()                                              # overrides layer on brain.yaml
    assert loaded.get("a.c.e") == 3 and loaded.get("assistant.name") == "Alfred"


def test_secrets_come_from_the_environment(monkeypatch):
    for key in ("ANTHROPIC_API_KEY", "JEV_API_KEY", "ELEVENLABS_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("JEV_API_KEY", "jev")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "env-voice")
    s = Settings({})
    assert s.status() == {"anthropic": False, "jev": True, "elevenlabs": False}
    assert s.voice_id == "env-voice"
    s.data["voice"] = {"voice_id": "ui-voice"}                             # a voice picked in the UI wins
    assert s.voice_id == "ui-voice"


def test_activity_log_keeps_everything_but_audio(tmp_path):
    bus = EventBus(ActivityLog(tmp_path))
    queue = bus.subscribe()
    bus.emit("answer", "voice", "r-1", "s-1", text="hej", audio_b64="AAAA")
    bus.emit("ack", "voice", text="ok")

    assert queue.get_nowait().data["audio_b64"] == "AAAA"                 # live subscribers get the audio
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
    assert queue.qsize() == 500                                            # overflow is dropped, not awaited
    bus.unsubscribe(queue)
    bus.emit("tick", "brain")
    assert queue.qsize() == 500


def test_subscription_mode_hides_the_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    llm.prepare_environment(Settings({"llm": {"backend": "api"}}))
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-test"
    llm.prepare_environment(Settings({}))                                  # subscription is the default
    assert "ANTHROPIC_API_KEY" not in os.environ


def test_light_client_per_backend(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert isinstance(llm.light_client(Settings({})), llm.SubscriptionClient)
    assert llm.light_client(Settings({"llm": {"backend": "api"}})) is None
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert type(llm.light_client(Settings({"llm": {"backend": "api"}}))).__name__ == "AsyncAnthropic"


async def test_subscription_client_speaks_the_messages_api(tmp_path, monkeypatch):
    seen = {}

    async def fake_query(*, prompt, options):
        seen["prompt"], seen["options"] = prompt, options
        yield claude_agent_sdk.AssistantMessage(content=[claude_agent_sdk.TextBlock(text="myślę")], model="m")
        yield claude_agent_sdk.ResultMessage(
            subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=1, session_id="s",
            usage={"input_tokens": 7, "output_tokens": 3}, result="plain text", structured_output={"module": "tasks"})

    monkeypatch.setattr(claude_agent_sdk, "query", fake_query)
    client = llm.SubscriptionClient(Settings({"memory": {"dir": str(tmp_path / "memory")}}))
    schema = {"type": "object"}
    resp = await client.messages.create(model="claude-haiku-4-5", system="route",
                                        messages=[{"role": "user", "content": "hej"}],
                                        output_config={"format": {"type": "json_schema", "schema": schema}})
    assert json.loads(resp.content[0].text) == {"module": "tasks"}
    assert (resp.usage.input_tokens, resp.usage.output_tokens) == (7, 3)
    opts = seen["options"]
    assert opts.output_format == {"type": "json_schema", "schema": schema} and seen["prompt"] == "hej"
    assert opts.tools == [] and opts.setting_sources == [] and opts.cwd == str(tmp_path)

    plain = await client.messages.create(model="claude-haiku-4-5", messages=[{"role": "user", "content": "hej"}])
    assert plain.content[0].text == "plain text"


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
    bus.emit("answer", "voice", text="Brief gotowy.", source="routine")      # the UI is closed
    bus.emit("answer", "voice", text="Odpowiedź", source="user")
    bus.emit("ack", "voice", text="Już")
    ui = bus.subscribe()
    assert [ui.get_nowait().data["text"] for _ in range(ui.qsize())] == ["Brief gotowy."]
    assert bus.subscribe().empty()                                          # handed over once
    bus.emit("answer", "voice", text="Przypomnienie", source="proactive")   # someone is listening now
    assert not bus.unheard
