"""Alfred's own tools (memory, tasks, routines, "ask before doing it"), handed to Claude next to the MCP servers'.

TOOLS describes each tool to Claude; make_handlers() returns the Python code that runs when Claude calls one.
A handler gets (arguments, session id) and returns text for Claude. Raising an error sends the message back to
Claude, which then usually fixes its call.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable

import yaml
from apscheduler.triggers.cron import CronTrigger

from . import okf
from .memory import FACT_CATEGORIES, OPEN_STATUSES, TASK_STATUSES, MemoryStore

CONFIRM_TOOL = "confirm_action"
MUTATING = {"memory_remember", "task_create", "task_update", "routine_save", "routine_delete"}  # noted in the session
# Web tools run inside Claude Code itself: our name -> Claude Code's name, description.
WEB_TOOLS = {"web_search": ("WebSearch", "Search the web for current information."),
             "web_fetch": ("WebFetch", "Fetch and read a web page by URL.")}


def _schema(required: list[str], **properties: dict) -> dict:
    return {"type": "object", "properties": properties, "required": required}


_str = {"type": "string"}
TOOLS: dict[str, dict[str, Any]] = {t["name"]: t for t in [
    {"name": "memory_search",
     "description": "Search Alfred's own memory (past sessions, tasks, facts about the user) by keywords. "
                    "Returns titles, descriptions and paths; open a page with memory_read.",
     "input_schema": _schema(["query"], query=_str, limit={"type": "integer", "minimum": 1, "maximum": 20})},
    {"name": "memory_read",
     "description": "Read one page of Alfred's memory by the path returned from memory_search "
                    "(e.g. 'sessions/2026/09/s-....md', 'tasks/<id>.md', 'index.md', 'log.md').",
     "input_schema": _schema(["path"], path=_str)},
    {"name": "memory_remember",
     "description": "Store a durable fact about the user (a person, place, preference or project) for future sessions.",
     "input_schema": _schema(["category", "title", "content"], category={"type": "string", "enum": list(FACT_CATEGORIES)},
                             title={"type": "string", "description": "Short name, e.g. 'Favourite restaurant'"},
                             content=_str)},
    {"name": "task_list",
     "description": "List tasks Alfred tracks for the user. status: open (default), all, or one status.",
     "input_schema": _schema([], status={"type": "string", "enum": ["open", "all", *TASK_STATUSES]})},
    {"name": "task_create",
     "description": "Create tasks or reminders Alfred should do or remind about later. Always pass a `tasks` "
                    "list - several tasks go in ONE call, never one call per task. Use `due` (ISO 8601 with "
                    "timezone) for a one-off moment, `schedule` (5-field cron, local time) for recurring ones. "
                    "The proactive scheduler picks them up automatically.",
     "input_schema": _schema(["tasks"], tasks={"type": "array", "minItems": 1, "items": _schema(
         ["title"], title=_str, description=_str,
         due={"type": "string", "description": "ISO 8601, e.g. 2026-09-26T09:00:00+02:00"},
         schedule={"type": "string", "description": "cron, e.g. '0 8 * * 1-5'"},
         priority={"type": "string", "enum": ["low", "normal", "high"]},
         category={"type": "string", "description": "Group name the user sorts tasks by, e.g. 'Praca', 'Dom'"},
         module={"type": "string", "description": "Module that should handle it when it fires"})})},
    {"name": "task_update",
     "description": "Update a task: change status (todo, in_progress, waiting, done, cancelled), due date, "
                    "schedule, category, title, or add a progress note.",
     "input_schema": _schema(["task_id"], task_id={"type": "string", "description": "Exact id from task_list"},
                             title={"type": "string", "description": "New title"},
                             status={"type": "string", "enum": list(TASK_STATUSES)}, note=_str, due=_str,
                             schedule=_str,
                             category={"type": "string", "description": "Move to this group; empty string clears it"})},
    {"name": CONFIRM_TOOL,
     "description": "Ask the user for a spoken yes/no before an irreversible step that has no dedicated tool "
                    "(e.g. pressing the final 'Book' button in a browser). Returns approved or declined.",
     "input_schema": _schema(["summary"], summary={"type": "string",
                                                   "description": "One sentence: exactly what will happen"})},
    {"name": "routine_save",
     "description": "Create a routine or change an existing one (same id): a prompt Alfred runs by himself on a "
                    "schedule. Only for routines - one-off reminders are tasks.",
     "input_schema": _schema(
         ["id", "schedule", "prompt"],
         id={"type": "string", "description": "Short slug, e.g. 'poranny-brief'; an existing id is replaced"},
         schedule={"type": "string", "description": "5-field cron in local time ('30 7 * * 1-5') or '@start'"},
         prompt={"type": "string", "description": "What Alfred should do when it runs, as the user would say it"},
         module={"type": "string", "description": "Module that should run it, e.g. calendar, tasks"})},
    {"name": "routine_delete", "description": "Remove a routine by its id.", "input_schema": _schema(["id"], id=_str)},
]}


def check_due(due: str | None) -> None:
    """A due time must be ISO 8601 with a timezone and not in the past (models love to get this wrong)."""
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


def check_cron(schedule: str | None, allow_start: bool = False) -> None:
    if schedule and not (allow_start and schedule == "@start"):
        try:
            CronTrigger.from_crontab(schedule)
        except ValueError:
            raise ValueError(f"schedule '{schedule}' is not a 5-field cron (e.g. '0 8 * * 1-5')") from None


Handler = Callable[[dict[str, Any], str | None], Awaitable[str]]


def make_handlers(store: MemoryStore, routines_file: Path | None = None) -> dict[str, Handler]:
    def find_task(ref: str) -> str:
        """Exact id, else the ONE open task whose id starts with / title contains `ref`. Otherwise an error that
        lists the open tasks, so Claude can retry with the right id."""
        if store.get_task(ref):
            return ref
        open_tasks = store.list_tasks("open")
        hits = ([t for t in open_tasks if t.id.startswith(ref)]
                or [t for t in open_tasks if ref.casefold() in t.title.casefold()])
        if len(hits) == 1:
            return hits[0].id
        listing = "; ".join(f"{t.id}: {t.title}" + (f" (due {t.due})" if t.due else "") for t in open_tasks[:25])
        raise KeyError(f"{'Several' if hits else 'No'} task(s) match '{ref}'. Use one exact id. Open tasks: {listing}")

    def load_routines() -> list[dict]:
        if not routines_file:
            raise ValueError("No routines file configured (proactive.routines)")
        data = yaml.safe_load(routines_file.read_text(encoding="utf-8")) if routines_file.exists() else None
        routines = data.get("routines") if isinstance(data, dict) else None
        return [r for r in routines if isinstance(r, dict)] if isinstance(routines, list) else []

    def save_routines(routines: list[dict]) -> None:
        routines_file.parent.mkdir(parents=True, exist_ok=True)
        routines_file.write_text(yaml.safe_dump({"routines": routines}, allow_unicode=True, sort_keys=False),
                                 encoding="utf-8")

    async def memory_search(args, sid):
        return json.dumps(store.search(args["query"], int(args.get("limit", 8))), ensure_ascii=False)

    async def memory_read(args, sid):
        return store.read(args["path"])[:12000]

    async def memory_remember(args, sid):
        path = store.remember(args["category"], args["title"], args["content"], sid)
        return f"Remembered in {path.relative_to(store.root).as_posix()}"

    async def task_list(args, sid):
        return json.dumps([{k: v for k, v in t.to_dict().items() if k != "history"}
                           for t in store.list_tasks(args.get("status", "open"))], ensure_ascii=False)

    async def task_create(args, sid):
        items = args["tasks"]
        for a in items:                             # check the whole batch first: all or nothing
            if not str(a.get("title", "")).strip():
                raise ValueError("every task needs a title")
            check_due(a.get("due"))
            check_cron(a.get("schedule"))
        already_open = {(t.title.casefold(), t.due): t.id for t in store.list_tasks("open")}
        created, skipped = [], []
        for a in items:
            if same := already_open.get((a["title"].casefold(), a.get("due"))):
                skipped.append(same)
            else:
                created.append(store.create_task(a["title"], a.get("description", ""), a.get("due"),
                                                 a.get("schedule"), a.get("module"), a.get("priority", "normal"),
                                                 sid, a.get("category")).id)
        out = f"Created task{'s' if len(created) > 1 else ''} {', '.join(created)}" if created else "Nothing created"
        return out + (f"; already open, not duplicated: {', '.join(skipped)}" if skipped else "")

    async def task_update(args, sid):
        check_due(args.get("due"))
        check_cron(args.get("schedule"))
        task = store.update_task(find_task(args["task_id"]), args.get("status"), args.get("note"), args.get("due"),
                                 args.get("title"), args.get("schedule"), sid, args.get("category"))
        return f"Task {task.id} is now {task.status}" + (" (still open)" if task.status in OPEN_STATUSES else "")

    async def routine_save(args, sid):
        rid = okf.slugify(args["id"])
        check_cron(args["schedule"], allow_start=True)
        if not str(args.get("prompt", "")).strip():
            raise ValueError("a routine needs a prompt")
        new = {"id": rid, "schedule": args["schedule"], "prompt": args["prompt"].strip()}
        if args.get("module"):
            new["module"] = args["module"]
        routines = load_routines()
        old = next((r for r in routines if r.get("id") == rid), None)
        if old:
            old.update(new)                         # keeps extra keys such as min_idle_minutes
        else:
            routines.append(new)
        save_routines(routines)
        return f"{'Updated' if old else 'Created'} routine {rid} ({args['schedule']})"

    async def routine_delete(args, sid):
        routines = load_routines()
        kept = [r for r in routines if r.get("id") != args["id"]]
        if len(kept) == len(routines):
            raise KeyError(f"No routine '{args['id']}'. Routines: {', '.join(str(r.get('id')) for r in routines) or 'none'}")
        save_routines(kept)
        return f"Deleted routine {args['id']}"

    return {f.__name__: f for f in (memory_search, memory_read, memory_remember, task_list, task_create,
                                    task_update, routine_save, routine_delete)}
