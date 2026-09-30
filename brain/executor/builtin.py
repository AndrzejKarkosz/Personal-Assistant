from __future__ import annotations

import fnmatch
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable

import yaml
from apscheduler.triggers.cron import CronTrigger

from ..memory import MemoryStore, okf
from ..memory.store import FACT_CATEGORIES, OPEN_STATUSES, TASK_STATUSES

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
        "description": "Create tasks or reminders Alfred should do or remind about later. Always pass a `tasks` "
                       "list - several tasks go in ONE call, never one call per task. Use `due` (ISO 8601 "
                       "with timezone) for a one-off moment, `schedule` (5-field cron, local time) for "
                       "recurring ones. The proactive scheduler picks them up automatically.",
        "input_schema": {"type": "object", "properties": {"tasks": {"type": "array", "minItems": 1, "items": {
            "type": "object", "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "due": {"type": "string", "description": "ISO 8601, e.g. 2026-09-26T09:00:00+02:00"},
                "schedule": {"type": "string", "description": "cron, e.g. '0 8 * * 1-5'"},
                "priority": {"type": "string", "enum": ["low", "normal", "high"]},
                "category": {"type": "string", "description": "Group name the user sorts tasks by, e.g. 'Praca', 'Dom'"},
                "module": {"type": "string", "description": "Module that should handle it when it fires"}},
            "required": ["title"]}}},
            "required": ["tasks"]},
    },
    {
        "name": "task_update",
        "description": "Update a task: change status (todo, in_progress, waiting, done, cancelled), due date, "
                       "schedule, category, title, or add a progress note.",
        "input_schema": {"type": "object", "properties": {
            "task_id": {"type": "string", "description": "Exact id from task_list"},
            "title": {"type": "string", "description": "New title"},
            "status": {"type": "string", "enum": list(TASK_STATUSES)},
            "note": {"type": "string"},
            "due": {"type": "string"},
            "schedule": {"type": "string"},
            "category": {"type": "string", "description": "Move to this group; empty string clears it"}},
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
    {
        "name": "routine_save",
        "description": "Create a routine or change an existing one (same id): a prompt Alfred runs by himself on a "
                       "schedule. Only for routines - one-off reminders are tasks.",
        "input_schema": {"type": "object", "properties": {
            "id": {"type": "string", "description": "Short slug, e.g. 'poranny-brief'; an existing id is replaced"},
            "schedule": {"type": "string", "description": "5-field cron in local time ('30 7 * * 1-5') or '@start'"},
            "prompt": {"type": "string", "description": "What Alfred should do when it runs, as the user would say it"},
            "module": {"type": "string", "description": "Module that should run it, e.g. calendar, tasks"}},
            "required": ["id", "schedule", "prompt"]},
    },
    {
        "name": "routine_delete",
        "description": "Remove a routine by its id.",
        "input_schema": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]},
    },
]

CONFIRM_TOOL = "confirm_action"

MUTATING = {"memory_remember", "task_create", "task_update", "routine_save", "routine_delete"}


def _check_due(due: str | None) -> None:
    """Deterministic guard: a due time must be ISO 8601 with an offset and not in the past."""
    if not due:
        return
    try:
        when = datetime.fromisoformat(due)
    except ValueError:
        raise ValueError(f"due '{due}' is not ISO 8601 (e.g. 2026-09-30T10:00:00+02:00)") from None
    now = datetime.now().astimezone()
    if when.tzinfo is None:
        raise ValueError(f"due '{due}' has no timezone offset - add {now:%z} (Europe/Warsaw)")
    if when < now - timedelta(minutes=1):
        raise ValueError(f"due {due} is in the past (now is {now:%A %Y-%m-%d %H:%M%z}). "
                         "An hour that has already gone today means tomorrow.")


def _check_cron(schedule: str | None, allow_start: bool = False) -> None:
    if schedule and not (allow_start and schedule == "@start"):
        try:
            CronTrigger.from_crontab(schedule)
        except ValueError:
            raise ValueError(f"schedule '{schedule}' is not a 5-field cron (e.g. '0 8 * * 1-5')") from None


def select(patterns: list[str]) -> list[dict[str, Any]]:
    return [t for t in BUILTIN_TOOLS if any(fnmatch.fnmatch(t["name"], p) for p in patterns)]


def is_builtin(name: str) -> bool:
    return any(t["name"] == name for t in BUILTIN_TOOLS)


def make_handlers(store: MemoryStore, routines_file: Path | None = None
                  ) -> dict[str, Callable[[dict[str, Any], str | None], Awaitable[str]]]:
    def resolve(ref: str) -> str:
        """Exact id, else the one open task whose id starts with / title contains `ref`; otherwise an error that
        lists the open tasks so the model can retry with the right id."""
        if store.get_task(ref):
            return ref
        open_tasks = store.list_tasks("open")
        hits = ([t for t in open_tasks if t.id.startswith(ref)]
                or [t for t in open_tasks if ref.casefold() in t.title.casefold()])
        if len(hits) == 1:
            return hits[0].id
        listing = "; ".join(f"{t.id}: {t.title}" + (f" (due {t.due})" if t.due else "") for t in open_tasks[:25])
        raise KeyError(f"{'Several' if hits else 'No'} task(s) match '{ref}'. Use one exact id. Open tasks: {listing}")

    def load_routines() -> dict[str, Any]:
        if not routines_file:
            raise ValueError("No routines file configured (proactive.routines)")
        data = yaml.safe_load(routines_file.read_text(encoding="utf-8")) if routines_file.exists() else None
        return data if isinstance(data, dict) and isinstance(data.get("routines"), list) else {"routines": []}

    def save_routines(data: dict[str, Any]) -> None:
        routines_file.parent.mkdir(parents=True, exist_ok=True)
        routines_file.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")

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
        items = args.get("tasks") or [args]  # a bare single task still works
        for a in items:  # validate the whole batch first: all or nothing
            if not str(a.get("title", "")).strip():
                raise ValueError("every task needs a title")
            _check_due(a.get("due"))
            _check_cron(a.get("schedule"))
        existing = {(t.title.casefold(), t.due): t.id for t in store.list_tasks("open")}
        created, skipped = [], []
        for a in items:
            same = existing.get((a["title"].casefold(), a.get("due")))
            if same:
                skipped.append(same)
                continue
            created.append(store.create_task(a["title"], a.get("description", ""), a.get("due"), a.get("schedule"),
                                             a.get("module"), a.get("priority", "normal"), sid, a.get("category")).id)
        out = f"Created task{'s' if len(created) > 1 else ''} {', '.join(created)}" if created else "Nothing created"
        return out + (f"; already open, not duplicated: {', '.join(skipped)}" if skipped else "")

    async def task_update(args, sid):
        _check_due(args.get("due"))
        _check_cron(args.get("schedule"))
        task = store.update_task(resolve(args["task_id"]), args.get("status"), args.get("note"),
                                 args.get("due"), args.get("title"), args.get("schedule"), sid, args.get("category"))
        return f"Task {task.id} is now {task.status}" + (" (still open)" if task.status in OPEN_STATUSES else "")

    async def routine_save(args, sid):
        rid = okf.slugify(args["id"])
        _check_cron(args["schedule"], allow_start=True)
        if not str(args.get("prompt", "")).strip():
            raise ValueError("a routine needs a prompt")
        routine = {"id": rid, "schedule": args["schedule"], "prompt": args["prompt"].strip()}
        if args.get("module"):
            routine["module"] = args["module"]
        data = load_routines()
        old = next((r for r in data["routines"] if isinstance(r, dict) and r.get("id") == rid), None)
        if old:
            old.update(routine)  # keeps extra keys such as min_idle_minutes
        else:
            data["routines"].append(routine)
        save_routines(data)
        return f"{'Updated' if old else 'Created'} routine {rid} ({args['schedule']})"

    async def routine_delete(args, sid):
        data = load_routines()
        kept = [r for r in data["routines"] if not (isinstance(r, dict) and r.get("id") == args["id"])]
        if len(kept) == len(data["routines"]):
            ids = ", ".join(str(r.get("id")) for r in data["routines"] if isinstance(r, dict))
            raise KeyError(f"No routine '{args['id']}'. Routines: {ids or 'none'}")
        save_routines({**data, "routines": kept})
        return f"Deleted routine {args['id']}"

    return {f.__name__: f for f in (memory_search, memory_read, memory_remember, task_list, task_create,
                                    task_update, routine_save, routine_delete)}
