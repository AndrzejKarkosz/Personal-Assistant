import claude_agent_sdk
from conftest import result

from brain import persona
from brain.memory import Session
from brain.router import Route


async def test_executor_gives_claude_code_only_the_routed_tools(make_brain):
    brain, claude = make_brain("Zapisane, szefie.")
    route = Route(module="tasks", capabilities=["tasks.manage"], confidence=0.9)
    done = await brain.executor.run("przypomnij mi jutro", route, Session(), "r-1")

    prompt, opts = claude.calls[0]
    assert done.text == "Zapisane, szefie." and done.usage["input"] == 100 and done.cost_usd == 0.002
    assert opts.tools == [] and opts.setting_sources == [] and opts.permission_mode == "dontAsk"
    assert sorted(opts.allowed_tools) == [f"mcp__alfred__{t}" for t in ["task_category_add", "task_create", "task_list", "task_update"]]
    assert "Alfred" in opts.system_prompt and "<routing>" in prompt


def test_persona_file_drives_prompt_and_phrases(settings, tmp_path, monkeypatch):
    path = tmp_path / "persona.md"
    monkeypatch.setattr(persona, "PERSONA_FILE", path)
    settings.data["assistant"].update(name="Jarvis", user_name="Tony", address={"pl": "panie", "en": "sir"})
    persona.save({"confirm": {"pl": "Czy mogę: {summary}?", "en": "May I: {summary}?"}},
                 "# Role\nYou are {name}, assistant of {user}. Say {addr_en}. Keep {unknown} as is.", path)
    load = persona.load
    monkeypatch.setattr(persona, "load", lambda path=path: load(path))
    assert persona.system_prompt(settings) == "# Role\nYou are Jarvis, assistant of Tony. Say sir. Keep {unknown} as is."
    assert persona.confirm_prompt("en", "book it") == "May I: book it?"


async def test_claude_code_failures_are_spoken_not_raised(make_brain, monkeypatch):
    brain, _ = make_brain()
    queue = brain.bus.subscribe()

    async def not_logged_in(*, prompt, options):
        raise RuntimeError("Claude Code is not logged in")
        yield

    monkeypatch.setattr(claude_agent_sdk, "query", not_logged_in)
    done = await brain.executor.run("hej", Route(module="smalltalk"), Session(), "r-1")
    assert done.text == "Coś poszło nie tak po mojej stronie, szefie. Spróbuj proszę za chwilę."

    async def out_of_turns(*, prompt, options):
        yield claude_agent_sdk.AssistantMessage(content=[claude_agent_sdk.TextBlock(text="Szukam jeszcze...")],
                                                model="m", usage={"input_tokens": 5, "output_tokens": 2},
                                                stop_reason="tool_use")
        yield claude_agent_sdk.ResultMessage(subtype="error_max_turns", duration_ms=1, duration_api_ms=1,
                                             is_error=True, num_turns=9, session_id="s", errors=["max turns"])

    monkeypatch.setattr(claude_agent_sdk, "query", out_of_turns)
    done = await brain.executor.run("hej", Route(module="smalltalk"), Session(), "r-2")
    assert done.text == "Szukam jeszcze..."

    events = [queue.get_nowait() for _ in range(queue.qsize())]
    errors = [e.data["message"] for e in events if e.kind == "error"]
    assert errors[0] == "RuntimeError: Claude Code is not logged in" and "error_max_turns" in errors[1]
    assert any(e.kind == "llm_call" and e.data["usage"] == {"input": 5, "output": 2} for e in events)
