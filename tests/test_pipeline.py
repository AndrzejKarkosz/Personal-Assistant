import asyncio
from datetime import datetime

from conftest import text_response, tool_response

from brain.proactive import scheduler
from brain.proactive.scheduler import in_quiet_hours
from brain.voice.elevenlabs import Transcript


def collect(brain):
    queue = brain.bus.subscribe()

    def drain():
        out = []
        while not queue.empty():
            out.append(queue.get_nowait())
        return out
    return drain


async def test_ack_then_tool_then_spoken_answer(make_brain):
    brain, fake = make_brain([
        tool_response("task_create", {"title": "Zadzwonić do mamy", "due": "2026-09-26T09:00:00+02:00"}),
        text_response("Zapisane, szefie. Przypomnę jutro o dziewiątej."),
    ])
    drain = collect(brain)
    answer = await brain.handle_text("przypomnij mi jutro o 9 żeby zadzwonić do mamy")

    assert answer.startswith("Zapisane")
    kinds = [e.kind for e in drain()]
    assert kinds.index("classified") < kinds.index("ack") < kinds.index("answer")
    assert "tool_call" in kinds and "tool_result" in kinds
    assert brain.store.list_tasks("open")[0].title == "Zadzwonić do mamy"

    first = next(c for c in fake.messages.calls if "tools" in c)       # calls[0] is the router fallback
    names = {t["name"] for t in first["tools"]}
    assert "task_create" in names and "web_search" not in names          # only the routed module's tools
    assert "<memory_briefing>" in first["messages"][0]["content"]          # first turn gets the briefing
    assert first["system"][-1]["cache_control"] == {"type": "ephemeral"}
    assert first["fallbacks"] == "default"                                  # claude-opus-5 refusal fallback


async def test_smalltalk_has_no_ack(make_brain):
    brain, _ = make_brain([text_response("Dzień dobry, szefie.")])
    brain.router.jev.api_key = None
    drain = collect(brain)
    await brain.handle_text("cześć Alfred, jak się masz?", module_hint="smalltalk")
    assert "ack" not in [e.kind for e in drain()]


async def test_confirmation_yes_by_voice(make_brain):
    brain, _ = make_brain([
        tool_response("confirm_action", {"summary": "Stolik dla dwóch w Nolicie, piątek 19:00"}),
        text_response("Zarezerwowane."),
    ])
    task = asyncio.create_task(brain.handle_text("zarezerwuj stolik w Nolicie", module_hint="bookings"))
    for _ in range(50):
        if brain.guard.pending:
            break
        await asyncio.sleep(0.02)
    assert "Nolicie" in brain.guard.pending.question
    await brain.handle_text("tak, potwierdzam")
    assert await task == "Zarezerwowane."
    assert any("approved" in a for a in brain.sessions.current.actions)


async def test_confirmation_declined(make_brain):
    brain, fake = make_brain([
        tool_response("confirm_action", {"summary": "Wyślę maila do szefa"}),
        text_response("Dobrze, nie wysyłam."),
    ])
    task = asyncio.create_task(brain.handle_text("wyślij maila", module_hint="bookings"))
    while not brain.guard.pending:
        await asyncio.sleep(0.02)
    brain.guard.resolve(False)
    await task
    messages = fake.messages.calls[-1]["messages"]
    tool_results = [b for m in messages if m["role"] == "user" and isinstance(m["content"], list)
                    for b in m["content"] if isinstance(b, dict) and b.get("type") == "tool_result"]
    assert "declined" in tool_results[0]["content"]


async def test_session_close_writes_okf_page_and_facts(make_brain):
    brain, _ = make_brain([text_response("Jasne.")])
    await brain.handle_text("pamiętaj że dzwonię do mamy w niedziele", module_hint="memory")
    await brain.sessions.close()
    brief = brain.store.briefing()
    assert "Test session" in brief and "call mum" in brief
    assert brain.store.search("Sundays")[0]["type"] == "Fact"
    assert brain.sessions.current is None


async def test_activity_log_records_everything(make_brain):
    brain, _ = make_brain([text_response("Ok.")])
    await brain.handle_text("co słychać", module_hint="smalltalk")
    kinds = [r["kind"] for r in brain.bus.log.read()]
    assert {"session_started", "transcript", "classified", "executor_start", "llm_call", "answer"} <= set(kinds)
    assert all("audio_b64" not in r["data"] for r in brain.bus.log.read())


async def test_proactive_gate_fires_due_task(make_brain):
    brain, _ = make_brain([text_response("Szefie, pora zadzwonić do mamy.")])
    brain.settings.data["proactive"]["quiet_hours"] = []
    task = brain.store.create_task("Zadzwonić do mamy", due="2020-01-01T09:00:00+01:00", module="tasks")
    drain = collect(brain)
    await brain.proactive.check_due()
    events = drain()
    gate = next(e for e in events if e.kind == "proactive_gate")
    assert gate.data["fired"] is True
    assert any(e.kind == "answer" and e.data["source"] == "proactive" for e in events)
    await brain.proactive.check_due()                 # fires once only
    assert not any(e.kind == "proactive_gate" for e in drain())
    assert brain.store.get_task(task.id) is not None


async def test_audio_in_goes_through_speech_to_text(make_brain, monkeypatch):
    brain, _ = make_brain([text_response("Dzień dobry, szefie.")])
    drain = collect(brain)
    assert await brain.handle_audio(b"audio") is None                      # no ElevenLabs key: nothing heard
    assert [e.data["message"] for e in drain() if e.kind == "error"] == ["Nothing was transcribed."]

    async def broken(audio, filename):
        raise RuntimeError("STT down")

    monkeypatch.setattr(brain.voice, "transcribe", broken)
    assert await brain.handle_audio(b"audio") is None
    assert [e.data["message"] for e in drain() if e.kind == "error"] == ["STT failed: STT down"]

    async def heard(audio, filename):
        return Transcript("hello Alfred, how are you", "en")

    monkeypatch.setattr(brain.voice, "transcribe", heard)
    assert await brain.handle_audio(b"audio") == "Dzień dobry, szefie."
    assert brain.sessions.current.language == "en"


async def test_start_and_stop(make_brain):
    brain, _ = make_brain([text_response("Ok.")])
    await brain.start(with_scheduler=False)
    await brain.handle_text("co słychać", module_hint="smalltalk")
    await brain.stop()
    kinds = {r["kind"] for r in brain.bus.log.read()}
    assert {"brain_start", "mcp_status", "map_built", "session_closed", "brain_stop"} <= kinds


def test_graph_joins_the_pipeline_and_the_map(make_brain):
    brain, _ = make_brain()
    g = brain.graph()
    ids = {n["id"] for n in g["nodes"]}
    assert {"ears", "router", "executor", "module:tasks", "cap:tasks.manage", "tool:task_create", "mcp:alfred"} <= ids
    assert all(e["source"] in ids and e["target"] in ids for e in g["edges"]) and g["backend"] == "api"


def test_quiet_hours_window():
    quiet = ["23:00", "07:00"]
    assert in_quiet_hours(datetime(2026, 9, 28, 23, 30), quiet) and in_quiet_hours(datetime(2026, 9, 28, 6, 59), quiet)
    assert not in_quiet_hours(datetime(2026, 9, 28, 7, 0), quiet)
    assert in_quiet_hours(datetime(2026, 9, 28, 13, 0), ["12:00", "14:00"])
    assert not in_quiet_hours(datetime(2026, 9, 28, 3, 0), []) and not in_quiet_hours(datetime(2026, 9, 28, 3, 0), None)


async def test_proactive_respects_quiet_hours_the_gate_and_restarts(make_brain, monkeypatch):
    brain, fake = make_brain([text_response("Szefie, faktura.")])
    monkeypatch.setattr(scheduler, "in_quiet_hours", lambda now, quiet: True)
    normal = brain.store.create_task("Podlać kwiaty", due="2020-01-01T09:00:00+01:00")
    urgent = brain.store.create_task("Faktura", due="2020-01-01T09:00:00+01:00", priority="high")
    drain = collect(brain)

    await brain.proactive.check_due()
    gates = {e.data["task"]: e.data["fired"] for e in drain() if e.kind == "proactive_gate"}
    assert gates == {"Podlać kwiaty": False, "Faktura": True}              # only high priority breaks the silence

    restarted = scheduler.ProactiveEngine(brain, brain.proactive.state_file)
    assert f"{urgent.id}@{urgent.due}" in restarted._fired                  # fired reminders survive a restart

    async def not_now(state):
        return 0.1

    monkeypatch.setattr(brain.router, "should_interrupt", not_now)
    await brain.proactive.fire(normal.id, "schedule")
    assert [e.data["fired"] for e in drain() if e.kind == "proactive_gate"] == [False]
    brain.store.update_task(normal.id, status="done")
    await brain.proactive.fire(normal.id, "schedule")                     # closed task: nothing to say
    assert not drain()

    await brain.proactive.heartbeat()
    assert [e.data for e in drain() if e.kind == "heartbeat"] == [{"open_tasks": 1, "overdue": 1}]


async def test_recurring_tasks_become_cron_jobs(make_brain):
    brain, _ = make_brain()
    daily = brain.store.create_task("Poranny brief", schedule="0 8 * * 1-5", module="calendar")
    brain.store.create_task("Zepsuty cron", schedule="kiedyś tam")
    brain.proactive.start()
    try:
        ids = {j["id"] for j in brain.proactive.status()}
        assert ids == {"due-check", "idle-close", "heartbeat", f"task:{daily.id}@0 8 * * 1-5"}   # bad cron skipped
        brain.store.update_task(daily.id, schedule="30 7 * * *")               # a new schedule replaces the job
        brain.proactive.sync_recurring()
        assert {j["id"] for j in brain.proactive.status()} - ids == {f"task:{daily.id}@30 7 * * *"}
        brain.store.update_task(daily.id, status="done")
        brain.proactive.sync_recurring()
        assert not [j for j in brain.proactive.status() if j["id"].startswith("task:")]
    finally:
        brain.proactive.shutdown()


ROUTINES = """
routines:
  - {id: powitanie, schedule: "@start", prompt: Przywitaj mnie}
  - {id: brief, schedule: "0 8 * * 1-5", module: calendar, prompt: Daj mi poranny brief}
  - {id: zly-cron, schedule: kiedyś, prompt: x}
  - {id: bez-promptu, schedule: "0 9 * * *"}
"""


async def test_routines_run_on_start_and_on_schedule(make_brain):
    brain, _ = make_brain([text_response("Dzień dobry, szefie."), text_response("Brief gotowy.")])
    routines = brain.settings.path("proactive.routines")
    routines.write_text(ROUTINES, encoding="utf-8")
    brain.proactive.start()
    try:
        for _ in range(250):                                  # the @start routine runs in the background
            if brain.bus.unheard:
                break
            await asyncio.sleep(0.02)
        said = brain.bus.subscribe().get_nowait()             # nobody was listening: it waited for the UI
        assert (said.data["text"], said.data["source"]) == ("Dzień dobry, szefie.", "routine")
        ids = {j["id"] for j in brain.proactive.status()}
        assert "routine:brief@0 8 * * 1-5" in ids and not any("zly-cron" in i or "bez-promptu" in i for i in ids)

        drain = collect(brain)
        await brain.proactive.run_routine("brief")            # what the cron job does at 8:00
        events = drain()
        assert next(e for e in events if e.kind == "classified").data["module"] == "calendar"
        assert next(e for e in events if e.kind == "answer").data["text"] == "Brief gotowy."

        routines.write_text(ROUTINES.replace("0 8 * * 1-5", "30 7 * * *"), encoding="utf-8")   # edited file
        brain.proactive.sync_recurring()
        ids = {j["id"] for j in brain.proactive.status()}
        assert "routine:brief@30 7 * * *" in ids and "routine:brief@0 8 * * 1-5" not in ids

        routines.write_text("routines: [", encoding="utf-8")                 # broken YAML: ignored, not fatal
        assert brain.proactive.routines() == []
        await brain.proactive.run_routine("brief")
        assert not drain()
    finally:
        brain.proactive.shutdown()
