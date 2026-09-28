"""The FastAPI server (REST, WebSocket, UI files) and the `alfred` CLI, on a test brain.

TestClient is used without `with`, so the lifespan (real MCP servers, `claude auth status`) never runs.
"""
import functools
import json
import re
import shutil
import sys

import pytest
from conftest import text_response, tool_response
from fastapi.testclient import TestClient

from brain import config
from brain.config import ROOT
from brain.executor.mcp_hub import ServerState
from brain.modules import ModuleRegistry
from brain.voice import persona


@pytest.fixture
def api(make_brain, monkeypatch):
    from brain import app as server

    brain, fake = make_brain()
    monkeypatch.setattr(server, "brain", brain)
    return TestClient(server.app), brain, fake


def test_status_graph_modules_and_map(api):
    client, brain, _ = api
    status = client.get("/api/status").json()
    assert status["backend"] == "api" and status["session"] is None and status["pending_confirmation"] is None
    graph = client.get("/api/graph").json()
    assert graph["backend"] == "api" and {"repo", "test", "persona"} <= {n["kind"] for n in graph["nodes"]}
    assert {"source": "test:test_router", "target": "repo:router", "rel": "tests"} in graph["edges"]

    modules = {m["id"]: m for m in client.get("/api/modules").json()}
    assert {"tasks", "calendar", "smalltalk"} <= set(modules)
    assert modules["tasks"]["capabilities"][0]["tools"] == ["task_create", "task_list", "task_update"]

    brain_map = client.get("/api/map").json()
    assert brain_map["counts"]["modules"] == len(modules) and "module" in brain_map["jev"]
    assert client.get("/api/map/page", params={"path": "index.md"}).json()["content"].startswith("---")
    assert client.get("/api/map/page", params={"path": "../mcp.json"}).status_code == 404
    assert client.post("/api/map/rebuild").json()["modules"] == len(modules)


def test_disabling_a_module_is_saved_in_its_manifest(api, tmp_path):
    client, brain, _ = api
    shutil.copytree(ROOT / "modules", tmp_path / "modules")                 # never touch the real manifests
    brain.registry = ModuleRegistry(tmp_path / "modules")
    assert client.post("/api/modules/research/enabled", json={"enabled": False}).json() == \
        {"id": "research", "enabled": False}
    assert "enabled: false" in (tmp_path / "modules" / "research" / "module.yaml").read_text(encoding="utf-8")
    assert brain.map.modules["research"]["enabled"] is False
    assert client.post("/api/modules/ghost/enabled", json={"enabled": True}).status_code == 404
    assert client.post("/api/modules/reload").status_code == 200


def test_persona_roundtrip(api, tmp_path, monkeypatch):
    client, brain, _ = api
    path = tmp_path / "persona.md"
    persona.save({"name": "Alfred"}, "You are {name}.", path)
    monkeypatch.setattr(persona, "load", functools.partial(persona.load, path=path))
    monkeypatch.setattr(persona, "save", functools.partial(persona.save, path=path))

    assert client.get("/api/persona").json()["preview"] == "You are Alfred."
    saved = client.put("/api/persona", json={"meta": {"name": "Jarvis"}, "body": "You are {name}."}).json()
    assert saved["preview"] == "You are Jarvis." and saved["meta"]["type"] == "Persona"
    assert "Jarvis" in path.read_text(encoding="utf-8")
    assert any(r["kind"] == "persona_updated" for r in brain.bus.log.read())


def test_classify_ask_and_the_session(api):
    client, brain, fake = api
    fake.messages.script.append(text_response("Dzień dobry, szefie."))
    route = client.post("/api/classify", json={"text": "przypomnij mi jutro"}).json()
    assert route["module"] == "tasks" and route["source"] == "llm"
    assert client.post("/api/ask", json={"text": "cześć"}).json() == {"answer": "Dzień dobry, szefie."}

    assert client.get("/api/status").json()["session"]["turns"] == 2
    assert client.post("/api/session/close").json() == {"closed": True}
    assert client.get("/api/memory/sessions").json()[0]["title"] == "Test session"
    assert client.get("/api/logs/days").json() == brain.bus.log.days()
    answers = client.get("/api/logs", params={"kind": "answer"}).json()
    assert [r["data"]["text"] for r in answers] == ["Dzień dobry, szefie."]


def test_tasks_rest(api):
    client, _, _ = api
    created = client.post("/api/tasks", json={"title": "Faktura", "due": "2030-01-01T09:00:00+01:00"}).json()
    assert [t["id"] for t in client.get("/api/tasks").json()] == [created["id"]]
    assert client.patch(f"/api/tasks/{created['id']}", json={"status": "done"}).json()["status"] == "done"
    assert client.get("/api/tasks").json() == []
    assert len(client.get("/api/tasks", params={"status": "all"}).json()) == 1
    assert client.patch("/api/tasks/nope", json={"status": "done"}).status_code == 404


def test_calendar_reads_google_through_mcp(api, monkeypatch):
    client, brain, _ = api
    week = {"start": "2026-09-28T00:00:00", "end": "2026-10-05T00:00:00"}
    assert client.get("/api/calendar", params=week).json() == {"status": "missing", "error": None, "events": []}

    brain.hub.servers["google-calendar"] = ServerState("google-calendar", {}, status="ready")
    replies = [(json.dumps({"events": [{"id": "e1", "summary": "Standup"}], "totalCount": 1}), False),
               ("invalid_grant", True)]
    calls = []

    async def call(name, args):
        calls.append((name, args))
        return replies.pop(0)
    monkeypatch.setattr(brain.hub, "call", call)
    assert client.get("/api/calendar", params=week).json()["events"] == [{"id": "e1", "summary": "Standup"}]
    assert calls[0] == ("google-calendar__list-events", {"calendarId": "primary", "timeMin": week["start"],
                                                         "timeMax": week["end"], "timeZone": "Europe/Warsaw"})
    assert client.get("/api/calendar", params=week).json() == {"status": "error", "error": "invalid_grant", "events": []}
    assert [r["data"]["events"] for r in brain.bus.log.read(kind="calendar_sync")] == [1]


def test_routines_show_what_ran_today(api, tmp_path):
    client, brain, _ = api
    (tmp_path / "routines.yaml").write_text(
        "routines:\n"
        "  - {id: brief, schedule: '0 0 * * *', prompt: Daj brief}\n"      # due every midnight -> due today
        "  - {id: broken, schedule: '0 0 * * *', prompt: Zepsuj}\n"
        "  - {id: hello, schedule: '@start', prompt: Przywitaj}\n", encoding="utf-8")
    brain.bus.emit("transcript", "ears", "r-1", text="Daj brief", source="routine")
    brain.bus.emit("answer", "voice", "r-1", text="Dzień dobry.", source="routine")
    brain.bus.emit("transcript", "ears", "r-2", text="Zepsuj", source="routine")
    brain.bus.emit("error", "executor", "r-2", message="boom")
    brain.bus.emit("answer", "voice", "r-2", text="Przepraszam, coś poszło nie tak.", source="routine")
    r = {x["id"]: x for x in client.get("/api/routines").json()}
    assert (r["brief"]["result"], r["brief"]["answer"], r["brief"]["due_today"]) == ("answer", "Dzień dobry.", True)
    assert (r["broken"]["result"], r["broken"]["answer"]) == ("error", "boom")
    assert r["hello"]["ran_at"] is None and r["hello"]["next_run"] is None and r["brief"]["next_run"]


def test_memory_rest(api):
    client, brain, _ = api
    brain.store.remember("people", "Mama", "dzwoni w niedziele")
    assert "Open tasks: none" in client.get("/api/memory/briefing").json()["briefing"]
    hit = client.get("/api/memory/search", params={"q": "niedziele"}).json()[0]
    assert "dzwoni" in client.get("/api/memory/page", params={"path": hit["path"]}).json()["content"]
    for bad in ("../../outside.md", "missing.md"):
        assert client.get("/api/memory/page", params={"path": bad}).status_code == 404


def test_only_editable_settings_are_saved(api):
    client, brain, _ = api
    saved = client.put("/api/settings", json={"router": {"timeout_s": 2.0}, "mcp_config": {"x": 1},
                                              "voice": "not a dict"}).json()
    assert saved["router"]["timeout_s"] == 2.0 and "mcp_config" not in saved
    assert json.loads(config.OVERRIDES_FILE.read_text(encoding="utf-8")) == {"router": {"timeout_s": 2.0}}
    assert isinstance(brain.settings.get("voice"), dict)


def test_ui_and_its_assets_are_served(api):
    client, _, _ = api
    html = client.get("/").text
    assets = re.findall(r'(?:src|href)="(/static/[^"]+)"', html)
    assert {"/static/app.js", "/static/brain3d.js", "/static/style.css"} <= set(assets)
    for path in assets:
        assert client.get(path).status_code == 200, path


def test_websocket_streams_events_and_takes_answers(api):
    client, brain, fake = api
    fake.messages.script += [tool_response("confirm_action", {"summary": "Stolik w Nolicie o 19"}),
                             text_response("Zarezerwowane.")]

    def until(ws, kind):
        while (event := ws.receive_json())["kind"] != kind:
            pass
        return event

    brain.bus.emit("answer", "voice", text="Brief gotowy.", source="routine")    # said while the UI was closed
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["data"]["text"] == "Brief gotowy."              # first thing on opening

        ws.send_json({"type": "audio", "b64": "AAAA", "mime": "audio/ogg"})
        assert until(ws, "error")["data"]["message"] == "Nothing was transcribed."

        ws.send_json({"type": "text", "text": "zarezerwuj stolik w Nolicie"})
        assert "Nolicie" in until(ws, "confirm_request")["data"]["text"]
        ws.send_json({"type": "confirm", "approved": True})
        assert until(ws, "answer")["data"]["text"] == "Zarezerwowane."


def test_cli_classify_chat_and_serve(make_brain, monkeypatch, capsys):
    import uvicorn

    from brain import cli, pipeline

    brain, _ = make_brain([text_response("Dzień dobry, szefie.")])
    monkeypatch.setattr(pipeline, "Brain", lambda: brain)

    monkeypatch.setattr(sys, "argv", ["alfred", "classify", "przypomnij mi jutro"])
    cli.main()
    assert json.loads(capsys.readouterr().out)["module"] == "tasks"

    lines = iter(["cześć", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(lines))
    monkeypatch.setattr(sys, "argv", ["alfred", "chat"])
    cli.main()
    out = capsys.readouterr().out
    assert "[router/llm] tasks" in out and "Alfred: Dzień dobry, szefie." in out

    served = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: served.update(app=app, **kw))
    monkeypatch.setattr(sys, "argv", ["alfred", "serve", "--port", "9000"])
    cli.main()
    assert served == {"app": "brain.app:app", "host": "127.0.0.1", "port": 9000, "reload": False}
