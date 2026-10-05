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


async def test_calendar_changes_happen_right_away_without_a_yes(make_brain):
    brain, claude = make_brain(("tool", "google-calendar__create-event", MEETING), "Dodane, szefie.")
    reached = with_calendar(brain, claude, ["calendar.write"])
    queue = brain.bus.subscribe()
    assert await brain.handle_text("dodaj spotkanie z Tomkiem jutro o 14") == "Dodane, szefie."
    assert reached == [("google-calendar__create-event", MEETING)] and brain.guard.pending is None
    assert "confirm_request" not in [queue.get_nowait().kind for _ in range(queue.qsize())]


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


def jev_heard(brain, category=None, status=None):
    """Jev routes to tasks and says which task category and status it heard."""
    brain.router.jev.routing = {"module": {"choice": "tasks", "confidence": 0.9, "probabilities": {"tasks": 0.9}},
                                "capability": {"choice": "tasks.manage"},
                                "task_category": {"choice": category or "none"},
                                "task_status": {"choice": status or "none"}}


async def test_jev_asks_for_the_fixed_task_categories_and_the_four_statuses(make_brain):
    brain, _ = make_brain()
    qs = brain.router.questions()
    assert list(qs["task_category"]["criteria"]) == ["SmartMeet", "Praca", "Reszta", "none"]
    assert list(qs["task_status"]["criteria"]) == ["todo", "in_progress", "done", "cancelled", "none"]


async def test_the_category_and_status_jev_heard_go_on_the_new_task(make_brain):
    brain, claude = make_brain(("tool", "task_create", {"tasks": [{"title": "Demo dla klienta"}]}), "Dodane.")
    jev_heard(brain, "SmartMeet", "in_progress")
    await brain.handle_text("dodaj do SmartMeet demo dla klienta, już nad tym siedzę")
    task = brain.store.list_tasks()[0]
    assert (task.title, task.category, task.status) == ("Demo dla klienta", "SmartMeet", "in_progress")
    assert "task category=SmartMeet" in claude.calls[0][0] and "SmartMeet, Praca, Reszta" in claude.calls[0][0]


async def test_jev_classifies_each_task_and_claude_only_executes(make_brain):
    brain, _ = make_brain(("tool", "task_create", {"tasks": [{"title": "Faktura", "category": "Reszta"},
                                                             {"title": "Siłownia", "category": "SmartMeet",
                                                              "status": "done"}]}), "Dodane.")
    jev_heard(brain, "SmartMeet")                       # the request-level guess - each task gets its own question
    brain.router.jev.routing |= {"c0": {"choice": "Praca"}, "s0": {"choice": "todo"},
                                 "c1": {"choice": "Reszta"}, "s1": {"choice": "in_progress"}}
    drain = brain.bus.subscribe()
    await brain.handle_text("faktura do pracy, a siłownię już zaczynam - do reszty")
    assert {t.title: (t.category, t.status) for t in brain.store.list_tasks()} == \
        {"Faktura": ("Praca", "todo"), "Siłownia": ("Reszta", "in_progress")}   # Claude's values ignored
    seen = []
    while not drain.empty():
        seen.append(drain.get_nowait())
    assert next(e for e in seen if e.kind == "tasks_classified").data["source"] == "jev"


async def test_without_jev_claude_does_the_classifiers_job_within_the_fixed_list(make_brain):
    brain, _ = make_brain(("tool", "task_create", {"tasks": [{"title": "Siłownia", "category": "Sport"}]}),
                          ("tool", "task_create", {"tasks": [{"title": "Siłownia", "category": "reszta"}]}), "Dodane.")
    await brain.handle_text("siłownia do reszty")      # this Jev answers only the shield: Claude routes and classifies
    assert [(t.title, t.category) for t in brain.store.list_tasks()] == [("Siłownia", "Reszta")]  # "Sport" refused


async def test_a_status_jev_heard_finishes_a_task_but_never_overrides_other_changes(make_brain):
    brain, claude = make_brain()
    invoice = brain.store.create_task("Faktura").id
    gym = brain.store.create_task("Siłownia").id
    # Claude sends a bare update (no status), then one that only moves a due date
    claude.script += [("tool", "task_update", {"task_id": invoice}), "Zrobione.",
                      ("tool", "task_update", {"task_id": gym, "due": "2030-10-01T10:00:00+02:00"}), "Przesunięte."]
    jev_heard(brain, status="done")
    await brain.handle_text("faktura zrobiona")
    await brain.handle_text("siłownię przesuń, zrobione")
    assert brain.store.get_task(invoice).status == "done" and brain.store.get_task(gym).status == "todo"


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
