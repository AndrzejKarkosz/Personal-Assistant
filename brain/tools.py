"""Alfred's own tools (memory, tasks, routines, "ask before doing it"), handed to Claude next to the MCP servers'.

TOOLS describes each tool to Claude; make_handlers() returns the Python code that runs when Claude calls one.
A handler gets (arguments, session id) and returns text for Claude. Raising an error sends the message back to
Claude, which then usually fixes its call.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable

from . import fitness
from .memory import FACT_CATEGORIES, OPEN_STATUSES, TASK_STATUSES, MemoryStore
from .scheduler import check_cron, delete_routine, save_routine

CONFIRM_TOOL = "confirm_action"
ADD_CATEGORY = "task_category_add"
ASK_FIRST = {CONFIRM_TOOL, ADD_CATEGORY}            # always a spoken yes/no before they run
MUTATING = {"memory_remember", "task_create", "task_update", "routine_save", "routine_delete",
            ADD_CATEGORY, "steps_log", "training_plan_update"}                          # noted in the session
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
         category={"type": "string", "description": "Jev decides the category of each task - you may leave it "
                                                    "out; used only if Jev is down (then one of the fixed ones)"},
         status={"type": "string", "enum": list(TASK_STATUSES), "description": "Jev decides; used only if Jev is down"},
         goal={"type": "string", "description": "How this task brings him closer to one of his goals, in his words - "
                                                "only when you know it (else ask him and save it with task_update)"},
         module={"type": "string", "description": "Module that should handle it when it fires"},
         alfred={"type": "boolean", "description": "true = Alfred's own board: a reminder (\"przypomnij mi\") or "
                                                   "something Alfred does himself at that time; false (default) = "
                                                   "the user's own to-do"})})},
    {"name": "task_update",
     "description": "Update a task: change status (todo, in_progress, done, cancelled), due date, "
                    "schedule, category, title, or add a progress note.",
     "input_schema": _schema(["task_id"], task_id={"type": "string", "description": "Exact id from task_list"},
                             title={"type": "string", "description": "New title"},
                             status={"type": "string", "enum": list(TASK_STATUSES)}, note=_str, due=_str,
                             schedule=_str,
                             category={"type": "string", "description": "Set it (any value) when the user wants the "
                                                                        "task moved - Jev picks the category"},
                             goal={"type": "string", "description": "How the task brings him closer to his goal - "
                                                                    "what he told you when you asked"},
                             alfred={"type": "boolean", "description": "Move to Alfred's board (true) or the "
                                                                      "user's (false)"})},
    {"name": ADD_CATEGORY,
     "description": "Add a NEW task category. Only when the user clearly wants a category that is not in the fixed "
                    "list; the user is asked for a spoken yes first. Then use it in task_create / task_update.",
     "input_schema": _schema(["name"], name={"type": "string", "description": "Short name, e.g. 'Dom'"},
                             description={"type": "string", "description": "When a task belongs here, in Polish"})},
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
    {"name": "training_status",
     "description": "The user's triathlon plan and how it goes: the race and days to it, the season phase (base, build, "
                    "peak, taper, recovery), per week target vs done hours and sessions for swim / bike / run from "
                    "Strava, the easy (80/20) share and the activities of the last 14 days with estimated kcal "
                    "(today_kcal = burnt today).",
     "input_schema": _schema([], weeks={"type": "integer", "minimum": 1, "maximum": 12,
                                        "description": "How many weeks back, this one included (default 4)"})},
    {"name": "training_plan_update",
     "description": "Change the user's training plan after he agreed to a proposal: the race, weekly sessions and hours "
                    "per sport (swim, bike, run, strength), the easy heart-rate limit, the daily step goal. Pass only "
                    "what changes; `why` is kept with the change.",
     "input_schema": _schema(["why"], why={"type": "string", "description": "One sentence: what changes and why"},
                             race={"type": "object", "properties": {"name": _str, "date": _str,
                                   "distance": {"type": "string", "enum": ["sprint", "olympic", "half", "full"]}}},
                             weekly={"type": "object", "description": "sport -> {sessions, hours}", "additionalProperties": {
                                 "type": "object", "properties": {"sessions": {"type": "integer", "minimum": 0, "maximum": 14},
                                                                  "hours": {"type": "number", "minimum": 0, "maximum": 40}}}},
                             easy_hr_max={"type": "integer", "minimum": 90, "maximum": 210},
                             steps_goal={"type": "integer", "minimum": 1000, "maximum": 50000})},
    {"name": "steps_log",
     "description": "Save how many steps the user walked on a day (he tells you; a later number for the same day "
                    "replaces it). Returns the day against his daily step goal and the last 7 days.",
     "input_schema": _schema(["steps"], steps={"type": "integer", "minimum": 0, "maximum": 200000},
                             date={"type": "string", "description": "YYYY-MM-DD, default today; 'wczoraj' = yesterday"})},
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


def task_category(value: str | None, allowed: dict | list | None) -> str | None:
    """The fixed category `value` means ("smart meet" -> "SmartMeet"); None / "" pass through (no category).
    Anything else is an error that lists the categories - Claude then picks one or asks to add a new one.
    allowed=None (no settings at all) checks nothing."""
    if not value or allowed is None:
        return value
    key = lambda s: re.sub(r"\s+", "", str(s)).casefold()
    if match := next((c for c in allowed if key(c) == key(value)), None):
        return match
    raise ValueError(f"'{value}' is not a task category. Categories: {', '.join(allowed) or 'none'}. Use one of "
                     f"them; a new one only if the user wants it - call {ADD_CATEGORY} (it asks him first).")


Handler = Callable[[dict[str, Any], str | None], Awaitable[str]]


def make_handlers(store: MemoryStore, routines_file: Path | None = None, settings=None, hub=None) -> dict[str, Handler]:
    categories = lambda: (settings.get("tasks.categories") or {}) if settings else None
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
            a["category"] = task_category(a.get("category"), categories())
        already_open = {(t.title.casefold(), t.due): t.id for t in store.list_tasks("open")}
        created, skipped = [], []
        for a in items:
            if same := already_open.get((a["title"].casefold(), a.get("due"))):
                skipped.append(same)
            else:
                created.append(store.create_task(a["title"], a.get("description", ""), a.get("due"),
                                                 a.get("schedule"), a.get("module"), a.get("priority", "normal"),
                                                 sid, a.get("category"), a.get("status") or "todo", a.get("goal"),
                                                 bool(a.get("alfred"))).id)
        out = f"Created task{'s' if len(created) > 1 else ''} {', '.join(created)}" if created else "Nothing created"
        return out + (f"; already open, not duplicated: {', '.join(skipped)}" if skipped else "")

    async def task_update(args, sid):
        check_due(args.get("due"))
        check_cron(args.get("schedule"))
        task = store.update_task(find_task(args["task_id"]), args.get("status"), args.get("note"), args.get("due"),
                                 args.get("title"), args.get("schedule"), sid,
                                 task_category(args.get("category"), categories()), args.get("goal"),
                                 args.get("alfred"))
        return f"Task {task.id} is now {task.status}" + (" (still open)" if task.status in OPEN_STATUSES else "")

    async def task_category_add(args, sid):    # runs only after the user said yes (tools.ASK_FIRST)
        name = " ".join(str(args.get("name", "")).split())
        if not name:
            raise ValueError("a category needs a name")
        if settings is None:
            raise ValueError("no settings to store the category in")
        try:
            return f"'{task_category(name, categories())}' already exists - use it"
        except ValueError:
            settings.update({"tasks": {"categories": {name: str(args.get("description") or name)}}})
            return f"Added task category '{name}'. Categories now: {', '.join(categories() or {})}"

    async def routine_save(args, sid):
        return save_routine(routines_file, args["id"], args["schedule"], args.get("prompt", ""), args.get("module"))

    async def routine_delete(args, sid):
        return delete_routine(routines_file, args["id"])

    async def training_status(args, sid):
        if hub is None or settings is None:
            raise ValueError("training_status needs the MCP hub and settings")
        out = await fitness.status(hub, settings, int(args.get("weeks", 4)), weight_kg=await fitness.weight_now(hub))
        if (server := hub.servers.get("nutrition")) and server.status == "ready":
            try:                                  # today's training into Nutrition MCP's kcal / carbs goals
                progress = await hub.call_json("nutrition__get_goal_progress", {})
                out["nutrition_goals"] = fitness.raised(
                    await fitness.sync_goals(hub, settings, progress, out["today_kcal"]), out["today_kcal"],
                    float(settings.get("training.eat_back", 0.6)))
            except Exception as exc:
                out["nutrition_goals"] = f"not synced: {exc}"
        return json.dumps(out, ensure_ascii=False)

    async def training_plan_update(args, sid):     # the training.plan capability asks him for a yes first
        if settings is None:
            raise ValueError("training_plan_update needs settings")
        patch = {k: args[k] for k in ("race", "weekly", "easy_hr_max", "steps_goal") if args.get(k) is not None}
        if not patch:
            raise ValueError("nothing to change - pass race, weekly, easy_hr_max or steps_goal")
        if (race := patch.get("race")) and race.get("date"):
            datetime.fromisoformat(race["date"])        # ValueError for a bad date
        settings.update({"training": patch})
        store.log("plan.updated", f"{', '.join(patch)}: {args['why']}", sid)   # the next briefing shows it
        return f"Plan updated ({', '.join(patch)}): {args['why']}"

    async def steps_log(args, sid):
        if settings is None:
            raise ValueError("steps_log needs settings")
        day = datetime.fromisoformat(args.get("date") or datetime.now().date().isoformat()).date()
        if day > datetime.now().date():
            raise ValueError(f"{day} is in the future - steps are logged for today or earlier")
        path = fitness.steps_file(settings)
        saved = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        saved[day.isoformat()] = int(args["steps"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(saved, indent=1, sort_keys=True), encoding="utf-8")
        goal = int(settings.get("training.steps_goal", 10000))
        week = ", ".join(f"{d['date'][5:]}: {'-' if d['steps'] is None else d['steps']}"
                         for d in fitness.steps_week(path, datetime.now().date()))
        return (f"Saved {args['steps']} steps on {day} - goal {goal} ({round(100 * int(args['steps']) / goal)}%). "
                f"Last 7 days: {week}")

    return {f.__name__: f for f in (memory_search, memory_read, memory_remember, task_list, task_create,
                                    task_update, task_category_add, routine_save, routine_delete, training_status,
                                    steps_log, training_plan_update)}
