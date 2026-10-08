import functools
import json
import re
import shutil
import sys

import pytest
from fastapi.testclient import TestClient

from brain import config
from brain.config import ROOT
from brain import persona
from brain.mcp_hub import ServerState
from brain.modules import ModuleRegistry


@pytest.fixture
def api(make_brain, monkeypatch):
    from brain import app as server

    brain, fake = make_brain()
    monkeypatch.setattr(server, "brain", brain)
    return TestClient(server.app), brain, fake


def test_status_graph_modules_and_map(api):
    client, brain, _ = api
    status = client.get("/api/status").json()
    assert status["session"] is None and status["pending_confirmation"] is None
    graph = client.get("/api/graph").json()
    assert {"core", "persona", "module", "tool"} <= {n["kind"] for n in graph["nodes"]}

    modules = {m["id"]: m for m in client.get("/api/modules").json()}
    assert {"tasks", "calendar", "smalltalk"} <= set(modules)
    assert modules["tasks"]["capabilities"][0]["tools"] == ["task_category_add", "task_create", "task_list", "task_update"]

    brain_map = client.get("/api/map").json()
    assert brain_map["counts"]["modules"] == len(modules) and "module" in brain_map["jev"]
    assert client.get("/api/map/page", params={"path": "index.md"}).json()["content"].startswith("---")
    assert client.get("/api/map/page", params={"path": "../mcp.json"}).status_code == 404
    assert client.post("/api/map/rebuild").json()["modules"] == len(modules)


def test_tasks_from_the_ui_use_the_fixed_categories(api):
    client, brain, _ = api
    assert client.get("/api/status").json()["task_categories"] == ["MojaFirma", "Praca", "Reszta"]
    task = client.post("/api/tasks", json={"title": "Demo", "category": "moja firma"}).json()
    assert task["category"] == "MojaFirma"
    assert client.post("/api/tasks", json={"title": "Odkurzyć", "category": "Dom"}).status_code == 400
    assert client.patch(f"/api/tasks/{task['id']}", json={"category": "Sport"}).status_code == 400
    assert client.patch(f"/api/tasks/{task['id']}", json={"category": ""}).json()["category"] is None
    # you add one yourself in Ustawienia - no yes/no needed, you are the one asking
    assert client.post("/api/task-categories", json={"name": " Dom ", "description": "Sprawy domowe"}).json() == \
        ["MojaFirma", "Praca", "Reszta", "Dom"]
    assert client.post("/api/tasks", json={"title": "Odkurzyć", "category": "dom"}).json()["category"] == "Dom"


def test_disabling_a_module_is_saved_in_your_settings(api, tmp_path):
    client, brain, _ = api
    manifest = (ROOT / "modules" / "research" / "module.yaml").read_text(encoding="utf-8")
    assert client.post("/api/modules/research/enabled", json={"enabled": False}).json() == \
        {"id": "research", "enabled": False}
    assert json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))["modules"] == {"research": False}
    assert (ROOT / "modules" / "research" / "module.yaml").read_text(encoding="utf-8") == manifest   # as shipped
    assert brain.map.modules["research"]["enabled"] is False
    assert ModuleRegistry(ROOT / "modules", brain.settings).get("research").enabled is False         # after a restart
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
    assert brain.settings.get("assistant.name") == "Jarvis"           # who he is: the settings, not the file
    assert "Jarvis" not in path.read_text(encoding="utf-8")
    assert any(r["kind"] == "persona_updated" for r in brain.bus.log.read())


def test_classify_ask_and_the_session(api):
    client, brain, fake = api
    fake.script.append("Dzień dobry, szefie.")
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
    edited = client.patch(f"/api/tasks/{created['id']}", json={"title": "Faktura VAT", "description": "  do 10.  "}).json()
    assert (edited["title"], edited["description"]) == ("Faktura VAT", "do 10.")
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

    async def call(name, args, limit=20000):
        assert limit is None                      # a month / year of events must not be cut to Claude's size
        calls.append((name, args))
        return replies.pop(0)
    monkeypatch.setattr(brain.hub, "call", call)
    assert client.get("/api/calendar", params=week).json()["events"] == [{"id": "e1", "summary": "Standup"}]
    assert calls[0] == ("google-calendar__list-events", {"calendarId": "primary", "timeMin": week["start"],
                                                         "timeMax": week["end"], "timeZone": "Europe/Warsaw"})
    assert client.get("/api/calendar", params=week).json() == {"status": "error", "error": "invalid_grant", "events": []}


def test_routines_show_what_ran_today(api, tmp_path):
    client, brain, _ = api
    (tmp_path / "routines.yaml").write_text(
        "routines:\n"
        "  - {id: brief, schedule: '0 0 * * *', prompt: Daj brief}\n"
        "  - {id: broken, schedule: '0 0 * * *', prompt: Zepsuj}\n"
        "  - {id: hello, schedule: '@start', prompt: Przywitaj}\n", encoding="utf-8")
    brain.bus.emit("routine_run", "proactive", "r-1", routine="brief")
    brain.bus.emit("answer", "voice", "r-1", text="Dzień dobry.", source="routine")
    brain.bus.emit("routine_run", "proactive", "r-2", routine="broken")
    brain.bus.emit("error", "executor", "r-2", message="boom")
    brain.bus.emit("answer", "voice", "r-2", text="Przepraszam, coś poszło nie tak.", source="routine")
    r = {x["id"]: x for x in client.get("/api/routines").json()}
    assert (r["brief"]["result"], r["brief"]["answer"], r["brief"]["due_today"]) == ("answer", "Dzień dobry.", True)
    assert (r["broken"]["result"], r["broken"]["answer"]) == ("error", "boom")
    assert r["hello"]["ran_at"] is None and r["hello"]["next_run"] is None and r["brief"]["next_run"]

    (tmp_path / "routines.yaml").write_text(        # its prompt changed: the run still counts - it is found by id
        "routines:\n  - {id: brief, schedule: '0 0 * * *', prompt: Daj krótki brief}\n", encoding="utf-8")
    assert client.get("/api/routines").json()[0]["answer"] == "Dzień dobry."


def test_routines_added_in_przeglad_and_the_productivity_routine(api):
    client, brain, _ = api
    new = {"id": "Poranny brief", "schedule": "30 7 * * 1-5", "prompt": "Daj brief", "module": "calendar"}
    assert client.post("/api/routines", json=new).json() == {"result": "Created routine poranny-brief (30 7 * * 1-5)"}
    assert client.post("/api/routines", json=new | {"schedule": "codziennie"}).status_code == 400
    assert [r["id"] for r in client.get("/api/routines").json()] == ["poranny-brief"]

    preset = [r["id"] for r in brain.settings.get("productivity.routines")]
    assert preset and client.get("/api/productivity").json()["enabled"] is False
    assert client.put("/api/productivity", json={"enabled": True}).json()["enabled"] is True
    assert [r["id"] for r in client.get("/api/routines").json()] == ["poranny-brief", *preset]
    plan = client.get("/api/productivity").json()["plan"] | {"peak_start": "08:15", "weekly_day": "6",
                                                           "if_then": "- Jeśli wrócę po 19, to trening w domu"}
    client.put("/api/productivity", json={"enabled": True, "plan": plan})
    r = {x["id"]: x for x in client.get("/api/routines").json()}
    assert r["prod-szczyt-energii"]["schedule"] == "15 8 * * 1-5" and r["prod-plan-tygodnia"]["schedule"] == "0 19 * * 6"
    assert r["prod-priorytety-dnia"]["schedule"] == "30 7 * * 1-5"                 # no slot: as in brain.yaml
    assert "jeśli-to: Jeśli wrócę po 19, to trening w domu" in r["prod-blok-admin"]["prompt"]
    assert client.put("/api/productivity", json={"enabled": True, "plan": plan | {"close": "25:00"}}).status_code == 422
    assert client.put("/api/productivity", json={"enabled": False}).json()["enabled"] is False
    assert client.delete("/api/routines/poranny-brief").status_code == 200
    assert client.get("/api/routines").json() == [] and client.delete("/api/routines/nope").status_code == 400


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
    fake.script += [("tool", "confirm_action", {"summary": "Stolik w Nolicie o 19"}), "Zarezerwowane."]
    fake.routed.update(module="bookings", capabilities=["bookings.browse"])

    def until(ws, kind):
        while (event := ws.receive_json())["kind"] != kind:
            pass
        return event

    brain.bus.emit("answer", "voice", text="Brief gotowy.", source="routine")
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["data"]["text"] == "Brief gotowy."

        ws.send_json({"type": "audio", "b64": "AAAA", "mime": "audio/ogg"})
        assert until(ws, "error")["data"]["message"] == "Nothing was transcribed."

        ws.send_json({"type": "text", "text": "zarezerwuj stolik w Nolicie"})
        assert "Nolicie" in until(ws, "confirm_request")["data"]["text"]
        ws.send_json({"type": "confirm", "approved": True})
        assert until(ws, "answer")["data"]["text"] == "Zarezerwowane."


def test_cli_classify_chat_and_serve(make_brain, monkeypatch, capsys):
    import uvicorn

    from brain import cli, pipeline

    brain, _ = make_brain("Dzień dobry, szefie.")
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


def test_summary_sums_a_day_month_quarter_or_year(api):
    from datetime import datetime
    from brain.app import period_range
    now = datetime(2026, 11, 15, 14, 30)
    span = lambda p, o=0: tuple(f"{d:%Y-%m-%d}" for d in period_range(p, o, now))
    assert span("day") == ("2026-11-15", "2026-11-16") and span("day", -1) == ("2026-11-14", "2026-11-15")
    assert span("month") == ("2026-11-01", "2026-12-01") and span("month", 2) == ("2027-01-01", "2027-02-01")
    assert span("quarter") == ("2026-10-01", "2027-01-01") and span("quarter", -4) == ("2025-10-01", "2026-01-01")
    assert span("year") == ("2026-01-01", "2027-01-01") and span("year", -1) == ("2025-01-01", "2026-01-01")

    client, brain, _ = api
    task = client.post("/api/tasks", json={"title": "Faktura", "category": "Praca"}).json()
    client.patch(f"/api/tasks/{task['id']}", json={"status": "done"})
    brain.store.write_session("s-1", datetime.now().astimezone().isoformat(), datetime.now().astimezone().isoformat(),
                              {"title": "Rano"}, {"cost_usd": 0.02, "jev_usd": 0.001, "elevenlabs_usd": 0.05}, 4)
    for period in ("day", "month", "quarter", "year"):
        s = client.get("/api/summary", params={"period": period}).json()
        assert (s["tasks"]["created"], s["tasks"]["done"], s["tasks"]["done_by_category"]) == (1, 1, {"Praca": 1})
        assert s["sessions"] == {"count": 1, "turns": 4} and s["cost"]["elevenlabs_usd"] == 0.05
    assert client.get("/api/summary", params={"period": "day", "offset": -1}).json()["tasks"]["done"] == 0
    assert client.get("/api/summary", params={"period": "week"}).status_code == 400
