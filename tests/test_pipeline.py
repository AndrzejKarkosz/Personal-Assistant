import asyncio

from conftest import text_response, tool_response


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
