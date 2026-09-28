"""Executor internals: the guard, built-in tools, the API tool loop and the MCP hub against a real server."""
import json
import sys
import textwrap

import anthropic
import httpx
from conftest import FakeBlock, text_response, tool_response

from brain.atlas import BrainMap, MapBuilder
from brain.config import ROOT
from brain.events import EventBus
from brain.executor import ApiExecutor, Guard, MCPHub, builtin
from brain.memory import MemoryStore, Session
from brain.modules import ModuleRegistry
from brain.router import Route


async def test_guard_treats_silence_as_no():
    guard = Guard(EventBus(), timeout_s=0.05)
    assert guard.resolve(True) is False                                   # nothing pending
    assert await guard.confirm("r-1", None, "confirm_action", "Potwierdzasz?") is False
    assert guard.pending is None


async def test_builtin_memory_and_task_tools(tmp_path):
    h = builtin.make_handlers(MemoryStore(tmp_path))
    saved = await h["memory_remember"]({"category": "people", "title": "Mama", "content": "dzwoni w niedziele"}, "s-1")
    assert saved == "Remembered in facts/people/mama.md"
    hits = json.loads(await h["memory_search"]({"query": "niedziele"}, None))
    assert hits[0]["path"] == "facts/people/mama.md"
    assert "dzwoni" in await h["memory_read"]({"path": hits[0]["path"]}, None)

    task_id = (await h["task_create"]({"title": "Faktura", "due": "2030-01-01T09:00:00+01:00"}, "s-1")).split()[-1]
    listed = json.loads(await h["task_list"]({}, None))
    assert [t["id"] for t in listed] == [task_id] and "history" not in listed[0]
    assert (await h["task_update"]({"task_id": task_id, "status": "waiting"}, None)).endswith("(still open)")
    assert await h["task_update"]({"task_id": task_id, "status": "done"}, None) == f"Task {task_id} is now done"
    assert [t["name"] for t in builtin.select(["task_*"])] == ["task_list", "task_create", "task_update"]


async def test_without_an_api_key_alfred_says_so(make_brain):
    brain, _ = make_brain()
    ex = ApiExecutor(None, brain.settings, brain.registry, brain.map, brain.hub, brain.store, brain.guard, brain.bus)
    result = await ex.run("hej", Route(module="smalltalk"), Session(), "r-1")
    assert "ANTHROPIC_API_KEY" in result.text


async def test_api_errors_become_a_spoken_apology(make_brain):
    brain, fake = make_brain()

    async def down(**_):
        raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))

    fake.messages.create = down
    queue = brain.bus.subscribe()
    answer = await brain.handle_text("co słychać", module_hint="smalltalk")
    assert answer == "Coś poszło nie tak po mojej stronie, szefie. Spróbuj proszę za chwilę."
    kinds = []
    while not queue.empty():
        kinds.append(queue.get_nowait().kind)
    assert "error" in kinds and "answer" in kinds


async def test_refusal_is_answered_politely(make_brain):
    brain, _ = make_brain([text_response("", stop="refusal")])
    assert await brain.handle_text("coś złego", module_hint="smalltalk") == "Niestety, z tym nie mogę pomóc."


async def test_tool_errors_go_back_to_claude(make_brain):
    calls = tool_response("task_update", {"task_id": "nope"}, call_id="a")
    calls.content += [FakeBlock("tool_use", id="b", name="task_list", input={}),
                      FakeBlock("tool_use", id="c", name="ghost_tool", input={})]
    brain, fake = make_brain([calls, text_response("Nie ma takiego zadania.")])
    assert await brain.handle_text("zamknij zadanie", module_hint="tasks") == "Nie ma takiego zadania."

    results = {b["tool_use_id"]: b for m in fake.messages.calls[-1]["messages"]
               if m["role"] == "user" and isinstance(m["content"], list) for b in m["content"]}
    assert results["a"]["is_error"] and "KeyError" in results["a"]["content"]
    assert "is_error" not in results["b"] and results["b"]["content"] == "[]"
    assert results["c"] == {"type": "tool_result", "tool_use_id": "c", "content": "Unknown tool ghost_tool",
                            "is_error": True}


async def test_tool_loop_stops_after_max_rounds(make_brain):
    brain, fake = make_brain([tool_response("task_list", {})] * 5)
    brain.settings.data["models"]["max_tool_rounds"] = 1
    assert await brain.handle_text("pokaż zadania", module_hint="tasks") == "Gotowe."
    assert sum(1 for c in fake.messages.calls if "tools" in c) == 2          # first call + one tool round


async def test_request_options_follow_the_model(make_brain):
    brain, fake = make_brain([text_response("a"), text_response("b")])
    brain.settings.data["models"]["executor"] = "claude-haiku-4-5"
    await brain.handle_text("hej", module_hint="smalltalk")
    call = fake.messages.calls[-1]
    assert call["model"] == "claude-haiku-4-5" and "output_config" not in call and "fallbacks" not in call

    brain.settings.data["models"]["executor"] = "claude-sonnet-5"
    await brain.handle_text("hej", module_hint="smalltalk")
    call = fake.messages.calls[-1]
    assert call["output_config"] == {"effort": "low"} and "fallbacks" not in call     # smalltalk: effort low

    defs = brain.executor.tool_definitions(Route(module="research", capabilities=["research.web"]))
    assert {d["name"]: d["type"] for d in defs} == {"web_fetch": "web_fetch_20260209",
                                                   "web_search": "web_search_20260209"}


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
        assert {t["name"] for t in hub.tools_for(["notes", "broken", "missing"])} == set(hub.all_tools())
        assert hub.owns("notes__find_note") and not hub.owns("task_create")
        assert await hub.call("notes__find_note", {"query": "x"}) == ("found x", False)
        text, is_error = await hub.call("notes__delete_note", {"note_id": "1"})
        assert is_error and "note is locked" in text

        # the brain map picks the live tools up; a destructive tool needs a spoken "yes"
        MapBuilder(tmp_path / "map", ModuleRegistry(ROOT / "modules"), hub).build()
        m = BrainMap(tmp_path / "map")
        assert m.tools["notes__delete_note"]["side_effect"] == "destructive"
        assert m.needs_confirmation("notes__delete_note") and not m.needs_confirmation("notes__find_note")
        assert m.servers["notes"]["status"] == "ready"
    finally:
        await hub.stop()
