"""Subscription backend (Claude Agent SDK) with a fake `query`, and the editable persona."""
import asyncio

import claude_agent_sdk

from brain.executor.agent import SubscriptionExecutor, sdk_name
from brain.memory import Session
from brain.router import Route
from brain.voice import persona


def _executor(brain) -> SubscriptionExecutor:
    return SubscriptionExecutor(brain.settings, brain.registry, brain.map, brain.hub, brain.store, brain.guard,
                                brain.bus)


async def test_subscription_executor_uses_only_routed_tools(make_brain, monkeypatch):
    brain, _ = make_brain()
    ex = _executor(brain)
    captured = {}

    async def fake_query(*, prompt, options):
        captured["prompt"], captured["options"] = prompt, options
        server = options.mcp_servers["alfred"]["instance"]
        assert server is not None
        yield claude_agent_sdk.ResultMessage(
            subtype="success", duration_ms=10, duration_api_ms=8, is_error=False, num_turns=1,
            session_id="s", total_cost_usd=0.0, usage={"input_tokens": 50, "output_tokens": 7},
            result="Zapisane, szefie.")

    monkeypatch.setattr(claude_agent_sdk, "query", fake_query)
    route = Route(module="tasks", capabilities=["tasks.manage"], confidence=0.9)
    result = await ex.run("przypomnij mi jutro", route, Session(), "r-1")

    opts = captured["options"]
    assert result.text == "Zapisane, szefie." and result.usage["input"] == 50
    assert opts.tools == [] and opts.setting_sources == [] and opts.permission_mode == "dontAsk"
    assert sorted(opts.allowed_tools) == sorted(sdk_name(t) for t in ["task_create", "task_list", "task_update"])
    assert "Alfred" in opts.system_prompt and "<routing>" in captured["prompt"]


async def test_subscription_tool_handler_goes_through_guard(make_brain):
    brain, _ = make_brain()
    ex = _executor(brain)
    session = Session()
    route = Route(module="bookings", capabilities=["bookings.confirm"], confidence=0.9)
    from brain.executor.claude import ExecResult
    result = ExecResult(text="", model="m")
    tools = {t.name: t for t in ex._sdk_tools(ex.tool_names(route), session, "r-2", result)}
    assert "confirm_action" in tools

    task = asyncio.create_task(tools["confirm_action"].handler({"summary": "Stolik w Nolicie o 19"}))
    while not brain.guard.pending:
        await asyncio.sleep(0.01)
    assert "Nolicie" in brain.guard.pending.question
    brain.guard.resolve(True)
    out = await task
    assert "approved" in out["content"][0]["text"]


def test_persona_file_drives_prompt_and_phrases(settings, tmp_path, monkeypatch):
    path = tmp_path / "persona.md"
    monkeypatch.setattr(persona, "PERSONA_FILE", path)
    persona.save({"name": "Jarvis", "user_name": "Tony", "address": {"pl": "panie", "en": "sir"},
                  "acks": {"pl": ["Już, {addr}."], "en": ["At once, {addr}."]},
                  "confirm": {"pl": "Czy mogę: {summary}?", "en": "May I: {summary}?"}},
                 "# Role\nYou are {name}, assistant of {user}. Say {addr_en}. Keep {unknown} as is.", path)
    load = persona.load
    monkeypatch.setattr(persona, "load", lambda path=path: load(path))
    assert persona.system_prompt(settings) == "# Role\nYou are Jarvis, assistant of Tony. Say sir. Keep {unknown} as is."
    assert persona.ack_phrase(settings, "pl") == "Już, panie."
    assert persona.confirm_prompt(settings, "en", "book it") == "May I: book it?"


async def test_subscription_failures_are_spoken_not_raised(make_brain, monkeypatch):
    brain, _ = make_brain()
    ex = _executor(brain)
    queue = brain.bus.subscribe()

    async def not_logged_in(*, prompt, options):
        raise RuntimeError("Claude Code is not logged in")
        yield  # noqa - makes this an async generator like the real query()

    monkeypatch.setattr(claude_agent_sdk, "query", not_logged_in)
    result = await ex.run("hej", Route(module="smalltalk"), Session(), "r-1")
    assert result.text == "Coś poszło nie tak po mojej stronie, szefie. Spróbuj proszę za chwilę."

    async def out_of_turns(*, prompt, options):
        yield claude_agent_sdk.AssistantMessage(content=[claude_agent_sdk.TextBlock(text="Szukam jeszcze...")],
                                                model="m", usage={"input_tokens": 5, "output_tokens": 2},
                                                stop_reason="tool_use")
        yield claude_agent_sdk.ResultMessage(subtype="error_max_turns", duration_ms=1, duration_api_ms=1,
                                             is_error=True, num_turns=9, session_id="s", errors=["max turns"])

    monkeypatch.setattr(claude_agent_sdk, "query", out_of_turns)
    result = await ex.run("hej", Route(module="smalltalk"), Session(), "r-2")
    assert result.text == "Szukam jeszcze..."                              # the last thing Claude said

    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    errors = [e.data["message"] for e in events if e.kind == "error"]
    assert errors[0] == "RuntimeError: Claude Code is not logged in" and "error_max_turns" in errors[1]
    assert any(e.kind == "llm_call" and e.data["usage"] == {"input": 5, "output": 2} for e in events)
