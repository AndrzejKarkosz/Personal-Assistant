"""Typical requests end to end with a fake Jev and a fake Claude: do the right tools run, and only after a "tak"?"""
import asyncio

from brain.mcp_hub import ServerState

EVENT = {"type": "object", "required": ["summary", "start", "end"],
         "properties": {"summary": {"type": "string"}, "start": {"type": "string"}, "end": {"type": "string"}}}
MEETING = {"summary": "Spotkanie z Tomkiem", "start": "2030-10-01T14:00:00", "end": "2030-10-01T15:00:00"}


def with_calendar(brain, claude, capabilities):
    """Plug a fake Google Calendar into the brain; returns the list of calls that really reached it."""
    tools = [{"name": f"google-calendar__{t}", "description": t, "input_schema": EVENT if t == "create-event" else
              {"type": "object", "properties": {}}} for t in ("create-event", "list-events")]
    brain.hub.servers["google-calendar"] = ServerState("google-calendar", {}, status="ready", tools=tools)
    brain.hub._owner.update({t["name"]: ("google-calendar", t["name"].split("__")[1]) for t in tools})
    reached = []

    async def call(name, args):
        reached.append((name, args))
        return '{"events": []}', False
    brain.hub.call = call
    brain.rebuild_map()
    claude.routed.update(module="calendar", capabilities=capabilities)
    return reached


async def answer_confirmation(brain, request: str, approved: bool) -> tuple[str, str]:
    """Send `request`, wait for "Potwierdzasz?", answer it. Returns (the question, Alfred's final answer)."""
    task = asyncio.create_task(brain.handle_text(request))
    for _ in range(250):
        if brain.guard.pending:
            break
        await asyncio.sleep(0.02)
    question = brain.guard.pending["question"]
    brain.guard.resolve(approved)
    return question, await task


async def test_adding_a_calendar_event_waits_for_yes(make_brain):
    brain, claude = make_brain(("tool", "google-calendar__create-event", MEETING), "Dodane, szefie.")
    reached = with_calendar(brain, claude, ["calendar.write"])
    question, answer = await answer_confirmation(brain, "dodaj spotkanie z Tomkiem jutro o 14", approved=True)
    assert "Spotkanie z Tomkiem" in question and answer == "Dodane, szefie."
    assert reached == [("google-calendar__create-event", MEETING)]


async def test_a_declined_calendar_event_is_never_created(make_brain):
    brain, claude = make_brain(("tool", "google-calendar__create-event", MEETING), "Dobrze, nie dodaję.")
    reached = with_calendar(brain, claude, ["calendar.write"])
    await answer_confirmation(brain, "dodaj spotkanie z Tomkiem jutro o 14", approved=False)
    assert reached == [] and "declined" in claude.tool_results[0][1]


async def test_reading_the_calendar_needs_no_yes(make_brain):
    brain, claude = make_brain(("tool", "google-calendar__list-events", {}), "Jutro masz wolne.")
    reached = with_calendar(brain, claude, ["calendar.read"])
    assert await brain.handle_text("co mam jutro w kalendarzu?") == "Jutro masz wolne."
    assert [name for name, _ in reached] == ["google-calendar__list-events"] and brain.guard.pending is None


async def test_web_search_is_logged_and_makes_later_tools_checked(make_brain):
    brain, claude = make_brain(("web", "WebSearch", {"query": "pogoda Kraków jutro"}),
                               ("tool", "task_create", {"tasks": [{"title": "Parasol"}]}), "Jutro pada.")
    claude.routed.update(module="research", capabilities=["research.web", "tasks.manage"])
    queue = brain.bus.subscribe()
    assert await brain.handle_text("jaka jutro pogoda w Krakowie?") == "Jutro pada."
    events = [queue.get_nowait() for _ in range(queue.qsize())]
    assert [e.data["tool"] for e in events if e.kind == "tool_call"] == ["WebSearch", "task_create"]
    assert [e.data["tool"] for e in events if e.kind == "action_check"] == ["task_create"]  # after a web page


async def test_each_kind_of_request_gets_only_its_own_tools(make_brain):
    brain, claude = make_brain("a", "b", "c")
    for module, caps, expected, not_expected in [
        ("tasks", ["tasks.manage"], "task_create", "memory_remember"),
        ("memory", ["memory.remember"], "memory_remember", "task_create"),
        ("research", ["research.web"], "WebSearch", "task_create"),
    ]:
        claude.routed.update(module=module, capabilities=caps)
        await brain.handle_text("coś")
        tools = claude.calls[-1][1].allowed_tools
        assert any(t.endswith(expected) for t in tools) and not any(t.endswith(not_expected) for t in tools), module
