import json

from fastapi.testclient import TestClient

from brain import config


async def test_first_run_is_the_setup_conversation_and_saves_what_he_says(make_brain, settings, tmp_path):
    settings.data["setup"]["done"] = False
    (tmp_path / "mcp.json").write_text('{"mcpServers": {"strava": {"enabled": false, "command": "x"}}}')
    brain, claude = make_brain(
        ("tool", "setup_save", {"user_name": "Kasia", "address": {"pl": "Kasiu"}, "timezone": "Europe/Berlin",
                                "task_categories": {"Dom": "Sprawy domowe", "Reszta": "Wszystko inne"},
                                "modules": {"training": True, "weight": False}, "integrations": {"strava": True},
                                "done": True}),
        "Gotowe, Kasiu.")
    await brain.handle_text("dodaj zadanie kupić mleko")          # not a task yet: the setup comes first

    prompt, opts = claude.calls[0]
    assert "## Module: Alfred's setup" in prompt
    assert {"mcp__alfred__setup_status", "mcp__alfred__setup_save"} <= set(opts.allowed_tools)
    out, is_error = claude.tool_results[0][1:]
    assert not is_error and "Integrations strava switched" in out
    assert settings.get("assistant.user_name") == "Kasia" and settings.get("assistant.address.pl") == "Kasiu"
    assert list(settings.get("tasks.categories")) == ["Dom", "Reszta"]          # replaced, not merged
    saved = json.loads(config.OVERRIDES_FILE.read_text(encoding="utf-8"))
    assert list(saved["tasks"]["categories"]) == ["Dom", "Reszta"] and saved["setup"] == {"done": True}
    assert json.loads((tmp_path / "mcp.json").read_text())["mcpServers"]["strava"]["enabled"] is True
    assert brain.map.modules["training"]["enabled"] is True and brain.map.modules["weight"]["enabled"] is False


async def test_setup_rejects_what_does_not_exist(make_brain, settings):
    settings.data["setup"]["done"] = False
    brain, claude = make_brain(("tool", "setup_save", {"timezone": "Mars/Olympus"}),
                               ("tool", "setup_save", {"modules": {"ghost": True}}), "Hm.")
    await brain.handle_text("zmień moją strefę czasową")
    assert [r[2] for r in claude.tool_results] == [True, True]
    assert "not a timezone" in claude.tool_results[0][1] and "No module ghost" in claude.tool_results[1][1]


def test_start_screen_saves_the_keys_into_env(make_brain, monkeypatch, tmp_path):
    from brain import app as server

    brain, _ = make_brain()
    brain.settings.data["setup"]["done"] = False
    monkeypatch.setattr(server, "brain", brain)
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    client = TestClient(server.app)
    assert client.get("/api/status").json()["setup"] == {"done": False}
    status = client.post("/api/setup/keys", json={"jev": " jev-123 ", "elevenlabs": ""}).json()
    assert status["keys"]["jev"] is True and status["keys"]["elevenlabs"] is False
    assert "JEV_API_KEY='jev-123'" in (tmp_path / ".env").read_text() and brain.router.jev.api_key == "jev-123"
