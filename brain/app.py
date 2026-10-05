"""The web server: the UI (ui/) and the HTTP + websocket API it talks to. Start with `uv run alfred serve`.

The websocket /ws streams every brain event to the UI and takes what you say or type.
Everything else is small REST endpoints, one per UI panel.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any

from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import fitness, llm, persona
from .config import ROOT
from .pipeline import Brain
from .scheduler import START
from .tools import task_category

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
brain = Brain()
claude_status: dict[str, Any] = {}
UI_DIR = ROOT / "ui"
EDITABLE_SETTINGS = ("assistant", "models", "router", "voice", "memory", "proactive")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    claude_status.update(await asyncio.to_thread(llm.subscription_status))
    await brain.start()
    yield
    await brain.stop()


app = FastAPI(title="Alfred brain", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=UI_DIR), name="static")
_running: set[asyncio.Task] = set()     # keeps background requests alive until they finish


def _in_background(coro) -> None:
    task = asyncio.create_task(coro)
    _running.add(task)
    task.add_done_callback(_running.discard)


def _not_found(what: str) -> HTTPException:
    return HTTPException(404, f"No such {what}")


@app.websocket("/ws")
async def ws(socket: WebSocket) -> None:
    await socket.accept()
    queue = brain.bus.subscribe()

    async def send_events() -> None:
        while True:
            await socket.send_json((await queue.get()).to_dict())

    sender = asyncio.create_task(send_events())
    try:
        while True:
            msg = await socket.receive_json()
            if msg.get("type") == "text" and msg.get("text", "").strip():
                _in_background(brain.handle_text(msg["text"], language=msg.get("language"), interruptible=True,
                                                 mode="chat" if msg.get("mode") == "chat" else "voice"))
            elif msg.get("type") == "audio" and msg.get("b64"):
                mime = msg.get("mime", "webm")
                ext = "webm" if "webm" in mime else "ogg" if "ogg" in mime else "wav"
                _in_background(brain.handle_audio(base64.b64decode(msg["b64"]), f"speech.{ext}", interruptible=True,
                                                  mode="chat" if msg.get("mode") == "chat" else "voice"))
            elif msg.get("type") == "confirm":
                brain.guard.resolve(bool(msg.get("approved")))
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        brain.bus.unsubscribe(queue)


# ---- status and the brain map ------------------------------------------------------------------------------------

@app.get("/api/status")
async def status() -> dict[str, Any]:
    session = brain.sessions.current
    return {
        "keys": brain.settings.keys() | {"anthropic": bool(claude_status.get("ok"))},
        "backend": "subscription",
        "claude": claude_status,
        "mcp": brain.hub.status(),
        "jobs": brain.proactive.status() if brain.proactive.scheduler.running else [],
        "session": session and {"id": session.id, "turns": len(session.turns), "usage": session.usage,
                                "language": session.language},
        "pending_confirmation": brain.guard.pending and brain.guard.pending["question"],
        "task_categories": list(brain.settings.get("tasks.categories") or {}),
    }


@app.get("/api/graph")
async def graph() -> dict[str, Any]:
    return brain.graph()


@app.get("/api/map")
async def brain_map() -> dict[str, Any]:
    m = brain.map
    groups = {"modules": m.modules, "capabilities": m.capabilities, "skills": m.skills, "tools": m.tools,
              "servers": m.servers, "topics": m.topics}
    return {"counts": {k: len(v) for k, v in groups.items()}, **{k: list(v.values()) for k, v in groups.items()},
            "jev": brain.router.questions()}


@app.get("/api/map/page")
async def brain_map_page(path: str = "index.md") -> dict[str, str]:
    try:
        return {"path": path, "content": brain.map.page(path)}
    except (ValueError, FileNotFoundError):
        raise _not_found("page") from None


@app.post("/api/map/rebuild")
@app.post("/api/modules/reload")
async def rebuild_map() -> dict[str, Any]:
    return brain.rebuild_map()


@app.get("/api/modules")
async def modules() -> list[dict[str, Any]]:
    return [{"id": m.id, "label": m.label, "description": m.description, "enabled": m.enabled,
             "examples": m.examples, "model": m.model, "effort": m.effort, "uses": m.uses,
             "servers": brain.map.modules.get(m.id, {}).get("servers", []),
             "capabilities": [{"id": c.id, "label": c.label, "confirm": c.confirm,
                               "tools": brain.map.capabilities.get(c.id, {}).get("tools", [])}
                              for c in m.capabilities.values()],
             "skills": [{"id": s.id, "name": s.name, "description": s.description} for s in m.skills]}
            for m in brain.registry.modules.values()]


class EnabledIn(BaseModel):
    enabled: bool


@app.post("/api/modules/{module_id}/enabled")
async def set_module_enabled(module_id: str, body: EnabledIn) -> dict[str, Any]:
    if not brain.registry.get(module_id):
        raise _not_found("module")
    brain.registry.set_enabled(module_id, body.enabled)
    brain.rebuild_map()
    return {"id": module_id, "enabled": body.enabled}


# ---- persona and settings ----------------------------------------------------------------------------------------

class PersonaIn(BaseModel):
    meta: dict[str, Any]
    body: str


@app.get("/api/persona")
async def get_persona() -> dict[str, Any]:
    meta, body = persona.load()
    return {"meta": meta, "body": body, "preview": persona.system_prompt(brain.settings)}


@app.put("/api/persona")
async def put_persona(data: PersonaIn) -> dict[str, Any]:
    persona.save(data.meta, data.body)
    brain.bus.emit("persona_updated", "voice", name=data.meta.get("name"))
    return await get_persona()


@app.get("/api/settings")
async def get_settings() -> dict[str, Any]:
    return {k: brain.settings.get(k) for k in EDITABLE_SETTINGS} | {"voice_id": brain.settings.voice_id}


@app.put("/api/settings")
async def put_settings(patch: dict[str, Any]) -> dict[str, Any]:
    brain.settings.update({k: v for k, v in patch.items() if k in EDITABLE_SETTINGS and isinstance(v, dict)})
    return await get_settings()


# ---- talking to Alfred -------------------------------------------------------------------------------------------

class TextIn(BaseModel):
    text: str


@app.post("/api/classify")
async def classify(body: TextIn) -> dict[str, Any]:
    return (await brain.router.classify(body.text)).to_dict()


@app.post("/api/ask")
async def ask(body: TextIn) -> dict[str, str]:
    return {"answer": await brain.handle_text(body.text)}


@app.post("/api/session/close")
async def close_session() -> dict[str, bool]:
    await brain.sessions.close()
    return {"closed": True}


# ---- tasks, calendar, routines -----------------------------------------------------------------------------------

class TaskIn(BaseModel):
    title: str
    description: str = ""
    due: str | None = None
    schedule: str | None = None
    priority: str = "normal"
    module: str | None = None
    category: str | None = None
    alfred: bool = False


class TaskPatch(BaseModel):
    status: str | None = None
    note: str | None = None
    due: str | None = None
    schedule: str | None = None
    category: str | None = None
    goal: str | None = None
    alfred: bool | None = None


@app.get("/api/tasks")
async def tasks(status: str = "open") -> list[dict[str, Any]]:
    return [t.to_dict() for t in brain.store.list_tasks(status)]


@app.post("/api/tasks")
async def create_task(body: TaskIn) -> dict[str, Any]:
    task = brain.store.create_task(body.title, body.description, body.due, body.schedule, body.module, body.priority,
                                   category=_category(body.category), alfred=body.alfred)
    if brain.proactive.scheduler.running:
        brain.proactive.sync_recurring()
    return task.to_dict()


@app.patch("/api/tasks/{task_id}")
async def patch_task(task_id: str, body: TaskPatch) -> dict[str, Any]:
    try:
        return brain.store.update_task(task_id, body.status, body.note, body.due, schedule=body.schedule,
                                       category=_category(body.category), goal=body.goal,
                                       alfred=body.alfred).to_dict()
    except KeyError:
        raise _not_found("task") from None


def _category(value: str | None) -> str | None:
    """Only the fixed categories (tasks.categories); "smart meet" -> "SmartMeet"."""
    try:
        return task_category(value, brain.settings.get("tasks.categories") or {})
    except ValueError:
        raise HTTPException(400, f"Nie ma kategorii „{value}”. Kategorie: "
                                 f"{', '.join(brain.settings.get('tasks.categories') or {})}") from None


class GoalsIn(BaseModel):
    goals: str = ""
    resolutions: str = ""


@app.get("/api/goals")
async def get_goals() -> dict[str, str]:
    return brain.store.goals()


@app.put("/api/goals")
async def put_goals(body: GoalsIn) -> dict[str, str]:
    """The Cele tab. Alfred reads them in every task request and asks how a task serves them when it is unclear."""
    brain.store.save_goals(body.goals, body.resolutions)
    return brain.store.goals()


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    url: str = Field(pattern=r"^https?://\S+$", max_length=2000)
    note: str = Field("", max_length=300)
    grams: float | None = Field(None, gt=0, le=5000)      # his usual portion; what he says overrides it


@app.get("/api/products")
async def get_products() -> list[dict[str, Any]]:
    return brain.store.products()


@app.put("/api/products")
async def put_products(items: list[ProductIn]) -> list[dict[str, Any]]:
    """The Produkty tab saves the whole list; it is a memory page, so Alfred finds it with memory_search."""
    brain.store.save_products([i.model_dump() for i in items])
    return brain.store.products()


class CategoryIn(BaseModel):
    name: str
    description: str = ""


@app.post("/api/task-categories")
async def add_task_category(body: CategoryIn) -> list[str]:
    """You add a category yourself (Ustawienia) - Alfred can only ask for one (task_category_add)."""
    name = " ".join(body.name.split())
    if name:
        brain.settings.update({"tasks": {"categories": {name: body.description.strip() or name}}})
    return list(brain.settings.get("tasks.categories") or {})


@app.get("/api/calendar")
async def calendar(start: str, end: str) -> dict[str, Any]:
    """Google Calendar events between start and end (a day up to a year), read through the google-calendar MCP
    server - in full, not cut to Claude's size."""
    server = brain.hub.servers.get("google-calendar")
    if not server or server.status != "ready":
        return {"status": server.status if server else "missing", "error": server and server.error, "events": []}
    try:
        text, is_error = await brain.hub.call("google-calendar__list-events", {
            "calendarId": "primary", "timeMin": start, "timeMax": end,
            "timeZone": brain.settings.get("assistant.timezone", "Europe/Warsaw")}, limit=None)
        events = None if is_error else json.loads(text)["events"]
    except Exception as exc:
        text, events = f"{type(exc).__name__}: {exc}", None
    if events is None:
        return {"status": "error", "error": text[:300], "events": []}
    brain.bus.emit("calendar_sync", "mcp:google-calendar", events=len(events))
    return {"status": "ready", "error": None, "events": events}


@app.get("/api/training")
async def training(weeks: int = 8) -> dict[str, Any]:
    """Zadania -> Treningi: the plan and its realisation (Strava, kcal per workout) and this week's work load."""
    weeks = max(1, min(weeks, 26))
    out = await fitness.status(brain.hub, brain.settings, weeks, weight_kg=await fitness.weight_now(brain.hub))
    cfg = brain.settings.get("training") or {}
    monday = fitness.week_start(datetime.now().date())
    sunday = monday + timedelta(days=7)
    cal = await calendar(f"{monday:%Y-%m-%dT00:00:00}", f"{sunday:%Y-%m-%dT00:00:00}")
    due = [t for t in brain.store.list_tasks("open") if t.category in (cfg.get("work_categories") or [])
           and t.due and monday <= datetime.fromisoformat(t.due).date() < sunday]
    out["work"] = fitness.work_load(cal["events"], len(due), cfg) | {"calendar": cal["status"]}
    return out


@app.get("/api/diet")
async def diet() -> dict[str, Any]:
    """Zadania -> Dieta: today's macros against the goals (raised by today's training), the last 7 days and the log
    of what you said and how it was saved."""
    out: dict[str, Any] = {"status": "missing", "error": None, "log": nutrition_log()}
    server = brain.hub.servers.get("nutrition")
    if not server or server.status != "ready":
        return out | {"status": server.status if server else "missing", "error": server and server.error}
    today = datetime.now().date()
    try:
        progress = await brain.hub.call_json("nutrition__get_goal_progress", {})
        week = await brain.hub.call_json("nutrition__get_nutrition_summary", {
            "start_date": f"{today - timedelta(days=6)}", "end_date": f"{today}"})
    except Exception as exc:
        return out | {"status": "error", "error": f"{type(exc).__name__}: {exc}"[:300]}
    training = await fitness.status(brain.hub, brain.settings, 1, weight_kg=(progress.get("weight") or {}).get("current"))
    try:                                      # today's training into Nutrition MCP's goals
        base, synced = await fitness.sync_goals(brain.hub, brain.settings, progress, training["today_kcal"]), True
    except Exception:
        base, synced = None, False
    return out | {"status": "ready", "week": week, "strava": training["strava"], "goals_synced": synced,
                  "balance": fitness.day_balance(progress, training["today_kcal"],
                                                 float(brain.settings.get("training.eat_back", 0.6)), base),
                  "workouts": [a for a in training["activities"] if a["start_date_local"][:10] == f"{today}"]}


def nutrition_log(days: int = 3, limit: int = 40) -> list[dict[str, Any]]:
    """What you said -> how Jev classified it -> what went into Nutrition MCP, newest first (from the activity log)."""
    events = [e for day in reversed(brain.bus.log.days()[:days]) for e in brain.bus.log.read(day, limit=100_000)]
    said = {e["request_id"]: e["data"].get("text") for e in events if e["kind"] == "transcript"}
    classified: dict[str, dict] = {}
    out: list[dict[str, Any]] = []
    for e in events:
        rid, d = e["request_id"], e["data"]
        tool = str(d.get("tool", ""))
        if e["kind"] == "meal_classified":
            classified[f"{rid}|{d.get('meal')}"] = d
        elif e["kind"] == "tool_call" and tool.startswith("nutrition__log_"):
            args = d.get("input") or {}
            jev = classified.get(f"{rid}|{args.get('description')}") or {}
            out.append({"ts": e["ts"], "request_id": rid, "said": said.get(rid), "tool": tool.split("__", 1)[1],
                        "input": args, "source": jev.get("source"), "ok": None,
                        "items": fitness.meal_items(args.get("notes"))})
        elif e["kind"] == "tool_result" and tool.startswith("nutrition__log_"):
            entry = next((o for o in reversed(out) if o["request_id"] == rid and o["ok"] is None), None)
            if entry:
                entry["ok"] = not d.get("is_error")
        elif e["kind"] == "meal_balance":
            entry = next((o for o in reversed(out) if o["request_id"] == rid and o["tool"] == "log_meal"), None)
            if entry:
                entry["balance"] = {r["key"]: [r["eaten"], r["goal"]] for r in d.get("rows", [])}
    return out[::-1][:limit]


class RaceIn(BaseModel):
    name: str = ""
    date: str = Field("", pattern=r"^(\d{4}-\d{2}-\d{2})?$")
    distance: str = Field("half", pattern=r"^(sprint|olympic|half|full)$")


class SportIn(BaseModel):
    sessions: int = Field(ge=0, le=14)
    hours: float = Field(ge=0, le=40)


class TrainingPlanIn(BaseModel):
    race: RaceIn
    weekly: dict[str, SportIn]
    easy_hr_max: int = Field(145, ge=90, le=210)
    steps_goal: int = Field(10000, ge=1000, le=50000)


@app.put("/api/training/plan")
async def put_training_plan(body: TrainingPlanIn) -> dict[str, Any]:
    """The race and the weekly targets from the Treningi tab - Alfred plans with them too (training_status)."""
    brain.settings.update({"training": body.model_dump()})
    return await training()


PERIODS = {"day": "Dzień", "month": "Miesiąc", "quarter": "Kwartał", "year": "Rok"}


def period_range(period: str, offset: int = 0, now: datetime | None = None) -> tuple[datetime, datetime]:
    """The day / month / quarter / year containing now, moved by `offset` periods (-1 = the previous one)."""
    now = (now or datetime.now()).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    if period == "day":
        start = now + timedelta(days=offset)
        return start.astimezone(), (start + timedelta(days=1)).astimezone()
    months = {"month": 1, "quarter": 3, "year": 12}[period]
    first = (now.month - 1) // months * months + offset * months          # months since January of this year
    start = datetime(now.year + first // 12, first % 12 + 1, 1)
    after = start.month - 1 + months
    return start.astimezone(), datetime(start.year + after // 12, after % 12 + 1, 1).astimezone()


@app.get("/api/summary")
async def summary(period: str = "day", offset: int = 0) -> dict[str, Any]:
    """Podsumowanie of a day, month, quarter or year: tasks, calendar, sessions and what they cost."""
    if period not in PERIODS:
        raise HTTPException(400, f"period: {', '.join(PERIODS)}")
    start, end = period_range(period, offset)
    out = brain.store.summary(start, end)
    session = brain.sessions.current               # not saved yet - counts in the period it is happening in
    if session and start <= datetime.now().astimezone() < end:
        for k, v in session.usage.items():
            if k in out["cost"] and isinstance(v, (int, float)):
                out["cost"][k] += v
        out["sessions"]["turns"] += len(session.turns)
    cal = await calendar(f"{start:%Y-%m-%dT%H:%M:%S}", f"{end:%Y-%m-%dT%H:%M:%S}")
    return out | {"period": period, "offset": offset, "start": start.isoformat(), "end": end.isoformat(),
                  "events": len(cal["events"]) if cal["status"] == "ready" else None}


@app.get("/api/routines")
async def routines() -> list[dict[str, Any]]:
    """Each routine with its last run today (from the log): answer or error, and when it runs next."""
    events = brain.bus.log.read(limit=100_000)
    tz = brain.proactive.scheduler.timezone
    now = datetime.now(tz)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    out = []
    for r in brain.proactive.routines():
        runs = [e for e in events if e["kind"] == "transcript" and e["data"].get("source") == "routine"
                and e["data"].get("text") == r["prompt"]]
        last = runs[-1] if runs else None
        of_last_run = [e for e in events if last and e["request_id"] == last["request_id"]]
        error = next((e["data"].get("message") for e in reversed(of_last_run) if e["kind"] == "error"), None)
        answer = next((e["data"].get("text") for e in of_last_run if e["kind"] == "answer"), None)
        first_today = next_run = None
        if r["schedule"] != START:
            try:
                trigger = CronTrigger.from_crontab(r["schedule"], timezone=tz)
                first_today, next_run = trigger.get_next_fire_time(None, midnight), trigger.get_next_fire_time(None, now)
            except ValueError:
                pass
        out.append({**r, "ran_at": last and last["ts"], "result": "error" if error else "answer" if answer else None,
                    "answer": error or answer, "due_today": bool(first_today and first_today <= now),
                    "next_run": next_run and next_run.isoformat()})
    return out


class RoutineIn(BaseModel):
    id: str
    schedule: str
    prompt: str
    module: str | None = None


async def _routine(tool: str, args: dict[str, Any]) -> str:
    """The same code as Alfred's routine_save / routine_delete tools; their errors become a 400 for the UI."""
    try:
        done = await brain.executor.handlers[tool](args, None)
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc).strip("'\"")) from None
    if brain.proactive.scheduler.running:
        brain.proactive.sync_recurring()
    return done


@app.post("/api/routines")
async def save_routine(body: RoutineIn) -> dict[str, str]:
    """Przegląd → Rutyny: add one, or change it (same id)."""
    return {"result": await _routine("routine_save", body.model_dump(exclude_none=True))}


@app.delete("/api/routines/{routine_id}")
async def delete_routine(routine_id: str) -> dict[str, str]:
    return {"result": await _routine("routine_delete", {"id": routine_id})}


HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"


class PlanIn(BaseModel):
    """His productivity plan (Cele → Rutyna produktywności): the routines run at these times and read these notes."""
    peak_start: str = Field("09:00", pattern=HHMM)      # deep work while energy is at its peak
    peak_end: str = Field("12:00", pattern=HHMM)
    shallow: str = Field("14:00", pattern=HHMM)         # admin in one batch when energy drops
    weekly_day: str = Field("0", pattern=r"^[0-6]$")    # cron weekday, 0 = Sunday
    weekly_time: str = Field("19:00", pattern=HHMM)
    close: str = Field("18:30", pattern=HHMM)           # closing the day, rest
    training: str = Field("17:30", pattern=HHMM)        # his usual training time on weekdays (Treningi)
    if_then: str = ""
    triggers: str = ""
    distractions: str = ""
    hours_limit: int = Field(50, ge=1, le=100)


class ProductivityIn(BaseModel):
    enabled: bool
    plan: PlanIn | None = None


def _plan() -> PlanIn:
    return PlanIn(**(brain.settings.get("productivity.plan") or {}))


def productivity_routines(plan: PlanIn, preset: list[dict]) -> list[dict]:
    """The preset routines (config/brain.yaml productivity) at the times of his plan, with his notes in each prompt."""
    at = lambda hhmm, days: f"{int(hhmm[3:])} {int(hhmm[:2])} * * {days}"
    slots = {"peak": at(plan.peak_start, "1-5"), "shallow": at(plan.shallow, "1-5"), "close": at(plan.close, "1-5"),
             "weekly": at(plan.weekly_time, plan.weekly_day), "training": at(plan.training, "1-5")}
    lines = lambda text: "; ".join(l.strip(" -") for l in text.splitlines() if l.strip(" -"))
    notes = [f"szczyt energii {plan.peak_start}-{plan.peak_end}", f"płytkie zadania od {plan.shallow}",
             f"najwyżej {plan.hours_limit} h pracy w tygodniu", f"pora treningu w dni robocze {plan.training}"] + [
        f"{label}: {lines(text)}" for label, text in (("jeśli-to", plan.if_then), ("wyzwalacze", plan.triggers),
                                                      ("rozpraszacze", plan.distractions)) if lines(text)]
    return [{**{k: v for k, v in r.items() if k != "slot"}, "schedule": slots.get(r.get("slot"), r["schedule"]),
             "prompt": f"{r['prompt']} Mój plan: {'. '.join(notes)}."} for r in preset]


@app.get("/api/productivity")
async def productivity() -> dict[str, Any]:
    """Cele → Rutyna produktywności: on while all its routines are in routines.yaml; his plan sets their times."""
    plan = _plan()
    built = productivity_routines(plan, brain.settings.get("productivity.routines") or [])
    have = {r["id"] for r in brain.proactive.routines()}
    return {"enabled": bool(built) and all(r["id"] in have for r in built), "routines": built,
            "plan": plan.model_dump()}


@app.put("/api/productivity")
async def set_productivity(body: ProductivityIn) -> dict[str, Any]:
    if body.plan:
        brain.settings.update({"productivity": {"plan": body.plan.model_dump()}})
    have = {r["id"] for r in brain.proactive.routines()}
    for r in productivity_routines(_plan(), brain.settings.get("productivity.routines") or []):
        if body.enabled:
            await _routine("routine_save", r)      # same id: replaced with the new times and notes
        elif r["id"] in have:
            await _routine("routine_delete", {"id": r["id"]})
    return await productivity()


# ---- memory and logs ---------------------------------------------------------------------------------------------

@app.get("/api/memory/briefing")
async def briefing() -> dict[str, str]:
    return {"briefing": brain.store.briefing(int(brain.settings.get("memory.recall_sessions", 3)))}


@app.get("/api/memory/search")
async def memory_search(q: str) -> list[dict[str, Any]]:
    return brain.store.search(q, 20)


@app.get("/api/memory/page")
async def memory_page(path: str) -> dict[str, str]:
    try:
        return {"path": path, "content": brain.store.read(path)}
    except (ValueError, FileNotFoundError):
        raise _not_found("page") from None


@app.get("/api/memory/sessions")
async def memory_sessions(limit: int = 20) -> list[dict[str, Any]]:
    return [meta for meta, _ in brain.store.recent_sessions(limit)]


@app.get("/api/logs")
async def logs(day: str | None = None, kind: str | None = None, limit: int = 300) -> list[dict[str, Any]]:
    return brain.bus.log.read(day, limit, kind)


@app.get("/api/logs/days")
async def log_days() -> list[str]:
    return brain.bus.log.days()


# ---- the UI itself -----------------------------------------------------------------------------------------------

@app.middleware("http")
async def always_fresh_ui(request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(UI_DIR / "index.html")
