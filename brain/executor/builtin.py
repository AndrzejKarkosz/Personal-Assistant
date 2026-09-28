"""Built-in tools backed by the brain's own session memory.

Module manifests opt into them by name or glob in `builtin_tools` (e.g. "task_*", "memory_*").
"""
from __future__ import annotations

import fnmatch
import json
from typing import Any, Awaitable, Callable

from ..memory import MemoryStore
from ..memory.store import FACT_CATEGORIES, OPEN_STATUSES, TASK_STATUSES

# Claude server tools (run on Anthropic's side in API mode; Claude Code's WebSearch/WebFetch in subscription mode).
SERVER_TOOLS = {
    "web_search": {"type": "web_search_20260209", "name": "web_search", "max_uses": 5},
    "web_fetch": {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 5},
}

BUILTIN_TOOLS: list[dict[str, Any]] = [
    {
        "name": "memory_search",
        "description": "Search Alfred's own memory (past sessions, tasks, facts about the user) by keywords. "
                       "Returns titles, descriptions and paths; open a page with memory_read.",
        "input_schema": {"type": "object", "properties": {
            "query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 20}},
            "required": ["query"]},
    },
    {
        "name": "memory_read",
        "description": "Read one page of Alfred's memory by the path returned from memory_search "
                       "(e.g. 'sessions/2026/09/s-....md', 'tasks/<id>.md', 'index.md', 'log.md').",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
    {
        "name": "memory_remember",
        "description": "Store a durable fact about the user (a person, place, preference or project) for future sessions.",
        "input_schema": {"type": "object", "properties": {
            "category": {"type": "string", "enum": list(FACT_CATEGORIES)},
            "title": {"type": "string", "description": "Short name, e.g. 'Favourite restaurant'"},
            "content": {"type": "string"}},
            "required": ["category", "title", "content"]},
    },
    {
        "name": "task_list",
        "description": "List tasks Alfred tracks for the user. status: open (default), all, or one status.",
        "input_schema": {"type": "object", "properties": {
            "status": {"type": "string", "enum": ["open", "all", *TASK_STATUSES]}}},
    },
    {
        "name": "task_create",
        "description": "Create a task or reminder Alfred should do or remind about later. Use `due` (ISO 8601 "
                       "with timezone) for a one-off moment, `schedule` (5-field cron, local time) for "
                       "recurring ones. The proactive scheduler picks them up automatically.",
        "input_schema": {"type": "object", "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "due": {"type": "string", "description": "ISO 8601, e.g. 2026-09-26T09:00:00+02:00"},
            "schedule": {"type": "string", "description": "cron, e.g. '0 8 * * 1-5'"},
            "priority": {"type": "string", "enum": ["low", "normal", "high"]},
            "module": {"type": "string", "description": "Module that should handle it when it fires"}},
            "required": ["title"]},
    },
    {
        "name": "task_update",
        "description": "Update a task: change status (todo, in_progress, waiting, done, cancelled), due date, "
                       "schedule, or add a progress note.",
        "input_schema": {"type": "object", "properties": {
            "task_id": {"type": "string"},
            "status": {"type": "string", "enum": list(TASK_STATUSES)},
            "note": {"type": "string"},
            "due": {"type": "string"},
            "schedule": {"type": "string"}},
            "required": ["task_id"]},
    },
    {
        "name": "confirm_action",
        "description": "Ask the user for a spoken yes/no before an irreversible step that has no dedicated "
                       "tool (e.g. pressing the final 'Book' button in a browser). Returns approved or declined.",
        "input_schema": {"type": "object", "properties": {
            "summary": {"type": "string", "description": "One sentence: exactly what will happen"}},
            "required": ["summary"]},
    },
]

# Always goes through the guard, whatever the module says.
CONFIRM_TOOL = "confirm_action"

# Tools that change memory - recorded as session actions (but never need confirmation).
MUTATING = {"memory_remember", "task_create", "task_update"}


def select(patterns: list[str]) -> list[dict[str, Any]]:
    return [t for t in BUILTIN_TOOLS if any(fnmatch.fnmatch(t["name"], p) for p in patterns)]


def is_builtin(name: str) -> bool:
    return any(t["name"] == name for t in BUILTIN_TOOLS)


def make_handlers(store: MemoryStore) -> dict[str, Callable[[dict[str, Any], str | None], Awaitable[str]]]:
    async def memory_search(args, sid):
        return json.dumps(store.search(args["query"], int(args.get("limit", 8))), ensure_ascii=False)

    async def memory_read(args, sid):
        return store.read(args["path"])[:12000]

    async def memory_remember(args, sid):
        path = store.remember(args["category"], args["title"], args["content"], sid)
        return f"Remembered in {path.relative_to(store.root).as_posix()}"

    async def task_list(args, sid):
        tasks = store.list_tasks(args.get("status", "open"))
        return json.dumps([{k: v for k, v in t.to_dict().items() if k != "history"} for t in tasks],
                          ensure_ascii=False) or "[]"

    async def task_create(args, sid):
        task = store.create_task(args["title"], args.get("description", ""), args.get("due"),
                                 args.get("schedule"), args.get("module"), args.get("priority", "normal"), sid)
        return f"Created task {task.id}"

    async def task_update(args, sid):
        task = store.update_task(args["task_id"], args.get("status"), args.get("note"),
                                 args.get("due"), None, args.get("schedule"), sid)
        return f"Task {task.id} is now {task.status}" + (" (still open)" if task.status in OPEN_STATUSES else "")

    return {f.__name__: f for f in (memory_search, memory_read, memory_remember, task_list, task_create, task_update)}
