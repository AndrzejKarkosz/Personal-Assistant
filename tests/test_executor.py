import json
import sys
import textwrap


from brain import mcp_hub, tools
from brain.atlas import BrainMap, build_map
from brain.config import ROOT
from brain.events import EventBus
from brain.executor import Guard
from brain.mcp_hub import MCPHub
from brain.memory import MemoryStore
from brain.modules import ModuleRegistry


async def test_guard_treats_silence_as_no():
    guard = Guard(EventBus(), timeout_s=0.05)
    assert guard.resolve(True) is False
    assert await guard.confirm("r-1", None, "confirm_action", "Potwierdzasz?") is False
    assert guard.pending is None


async def test_builtin_memory_and_task_tools(tmp_path):
    h = tools.make_handlers(MemoryStore(tmp_path))
    saved = await h["memory_remember"]({"category": "people", "title": "Mama", "content": "dzwoni w niedziele"}, "s-1")
    assert saved == "Remembered in facts/people/mama.md"
    hits = json.loads(await h["memory_search"]({"query": "niedziele"}, None))
    assert hits[0]["path"] == "facts/people/mama.md"
    assert "dzwoni" in await h["memory_read"]({"path": hits[0]["path"]}, None)

    task_id = (await h["task_create"]({"tasks": [{"title": "Faktura", "due": "2030-01-01T09:00:00+01:00"}]}, "s-1")).split()[-1]
    listed = json.loads(await h["task_list"]({}, None))
    assert [t["id"] for t in listed] == [task_id] and "history" not in listed[0]
    assert (await h["task_update"]({"task_id": task_id, "status": "waiting"}, None)).endswith("(still open)")
    assert await h["task_update"]({"task_id": task_id, "status": "done"}, None) == f"Task {task_id} is now done"

    many = await h["task_create"]({"tasks": [{"title": "Fryzjer"}, {"title": "Trening", "category": "Reszta"}]}, "s-1")
    assert many.startswith("Created tasks ") and len(json.loads(await h["task_list"]({}, None))) == 2


async def test_task_and_routine_tools_refuse_what_went_wrong_on_2026_09_29(tmp_path):
    import pytest
    h = tools.make_handlers(MemoryStore(tmp_path / "mem"), tmp_path / "routines.yaml")
    with pytest.raises(ValueError, match="in the past"):  # "reminder today 17:00" said at 21:09
        await h["task_create"]({"tasks": [{"title": "Merge request", "due": "2020-09-29T17:00:00+02:00"}]}, "s")
    with pytest.raises(ValueError, match="timezone"):
        await h["task_create"]({"tasks": [{"title": "Merge request", "due": "2030-09-30T10:00:00"}]}, "s")
    assert h["task_list"] and json.loads(await h["task_list"]({}, None)) == []  # the bad batch created nothing

    two = [{"title": "Przejrzeć merge requesta od Macieja", "due": "2030-09-30T10:00:00+02:00"},
           {"title": "Przejrzeć merge requesta od Macieja", "due": "2030-09-30T17:00:00+02:00"}]
    await h["task_create"]({"tasks": two}, "s")
    again = await h["task_create"]({"tasks": two[:1]}, "s")
    assert again.startswith("Nothing created") and "not duplicated" in again

    # the model guessed a shortened id: ambiguous -> error listing the real ids; unique title -> resolved
    from datetime import datetime
    with pytest.raises(KeyError, match="Several task.*Open tasks: .*maci-2"):
        await h["task_update"]({"task_id": f"{datetime.now():%Y%m%d}-przejrzec-merge-requesta-od",
                                "due": "2030-10-01T10:00:00+02:00"}, "s")
    await h["task_create"]({"tasks": [{"title": "Fryzjer"}]}, "s")
    assert (await h["task_update"]({"task_id": "fryzjer", "status": "done"}, "s")).endswith("is now done")

    with pytest.raises(ValueError, match="cron"):
        await h["routine_save"]({"id": "brief", "schedule": "codziennie o 8", "prompt": "brief"}, "s")
    assert (await h["routine_save"]({"id": "Poranny brief", "schedule": "30 7 * * 1-5", "prompt": "Daj brief",
                                     "module": "calendar"}, "s")) == "Created routine poranny-brief (30 7 * * 1-5)"
    assert (await h["routine_save"]({"id": "poranny-brief", "schedule": "0 8 * * 1-5", "prompt": "Daj brief"},
                                    "s")).startswith("Updated")
    import yaml
    saved = yaml.safe_load((tmp_path / "routines.yaml").read_text(encoding="utf-8"))["routines"]
    assert saved == [{"id": "poranny-brief", "schedule": "0 8 * * 1-5", "prompt": "Daj brief", "module": "calendar"}]
    assert await h["routine_delete"]({"id": "poranny-brief"}, "s") == "Deleted routine poranny-brief"
    with pytest.raises(KeyError, match="No routine"):
        await h["routine_delete"]({"id": "poranny-brief"}, "s")


def test_mcp_results_are_compacted():
    raw = json.dumps({"event": {"id": "e1", "summary": "Rekrutacja", "etag": "x", "attendees": [],
                                "start": {"dateTime": "2026-09-29T15:30:00+02:00"}, "reminders": {"useDefault": True},
                                "allDay": False}}, indent=2)
    assert mcp_hub.compact(raw, {"etag", "reminders"}) == \
        '{"event":{"id":"e1","summary":"Rekrutacja","start":{"dateTime":"2026-09-29T15:30:00+02:00"},"allDay":false}}'
    assert mcp_hub.compact("plain text", {"etag"}) == "plain text"


async def test_when_claude_is_down_alfred_apologises(make_brain):
    brain, claude = make_brain()
    claude.online = False
    queue = brain.bus.subscribe()
    answer = await brain.handle_text("co słychać", source="routine", module_hint="smalltalk")   # no shield
    assert answer == "Coś poszło nie tak po mojej stronie, szefie. Spróbuj proszę za chwilę."
    kinds = [queue.get_nowait().kind for _ in range(queue.qsize())]
    assert "error" in kinds and "answer" in kinds


async def test_tool_errors_go_back_to_claude(make_brain):
    brain, claude = make_brain(("tool", "task_update", {"task_id": "nope"}), ("tool", "task_list", {}),
                               ("tool", "ghost_tool", {}), "Nie ma takiego zadania.")
    assert await brain.handle_text("zamknij zadanie", module_hint="tasks") == "Nie ma takiego zadania."
    (update, update_err), (listed, list_err), (ghost, ghost_err) = [(o, e) for _, o, e in claude.tool_results]
    assert update_err and "KeyError" in update
    assert (listed, list_err) == ("[]", False)
    assert ghost_err and "not found" in ghost      # Claude only ever gets the routed tools


async def test_request_options_follow_the_module(make_brain):
    brain, claude = make_brain("a", "b")
    brain.settings.data["models"].update(executor="claude-opus-5-5", executor_effort="medium", max_tool_rounds=3)
    await brain.handle_text("hej", module_hint="smalltalk")
    opts = claude.calls[-1][1]
    assert (opts.model, opts.effort, opts.max_turns) == ("claude-opus-5-5", "medium", 4)   # config/brain.yaml
    brain.registry.modules["knowledge"].model = "claude-sonnet-5-5"                  # a module.yaml may override
    await brain.handle_text("co wiem o SQL?", module_hint="knowledge")
    assert claude.calls[-1][1].model == "claude-sonnet-5-5"

    opts = (await _options_for(brain, claude, module="research", capabilities=["research.web"]))
    assert sorted(opts.tools) == ["WebFetch", "WebSearch"] and "WebSearch" in opts.allowed_tools


async def _options_for(brain, claude, **route):
    from brain.memory import Session
    from brain.router import Route
    await brain.executor.run("x", Route(**route), Session(), "r-1")
    return claude.calls[-1][1]


NOTES_SERVER = textwrap.dedent('''
    from mcp.server.mcpserver import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError
    from mcp.types import ToolAnnotations

    server = MCPServer("notes")

    @server.tool(annotations=ToolAnnotations(read_only_hint=True))
    def find_note(query: str) -> str:
        """Find a note."""
        return f"found {query}"

    @server.tool(annotations=ToolAnnotations(destructive_hint=True))
    def delete_note(note_id: str) -> str:
        """Delete a note."""
        raise ToolError("note is locked")

    server.run()
''')


async def test_mcp_hub_against_a_real_stdio_server(tmp_path):
    script = tmp_path / "notes_server.py"
    script.write_text(NOTES_SERVER)
    cfg = tmp_path / "mcp.json"
    cfg.write_text(json.dumps({"mcpServers": {
        "notes": {"command": sys.executable, "args": [str(script)], "description": "Test notes"},
        "off": {"enabled": False, "command": "whatever"},
        "broken": {"command": "definitely-not-a-real-binary-4711"},
    }}))
    hub = MCPHub(cfg)
    await hub.start(timeout_s=60)
    try:
        status = {s["name"]: s for s in hub.status()}
        assert (status["notes"]["status"], status["off"]["status"], status["broken"]["status"]) == \
            ("ready", "disabled", "error")
        assert set(hub.all_tools()) == {"notes__find_note", "notes__delete_note"}
        assert hub.owns("notes__find_note") and not hub.owns("task_create")
        assert await hub.call("notes__find_note", {"query": "x"}) == ("found x", False)
        text, is_error = await hub.call("notes__delete_note", {"note_id": "1"})
        assert is_error and "note is locked" in text

        build_map(tmp_path / "map", ModuleRegistry(ROOT / "modules"), hub)
        m = BrainMap(tmp_path / "map")
        assert m.tools["notes__delete_note"]["side_effect"] == "destructive"
        assert m.needs_confirmation("notes__delete_note") and not m.needs_confirmation("notes__find_note")
        assert m.servers["notes"]["status"] == "ready"
    finally:
        await hub.stop()
