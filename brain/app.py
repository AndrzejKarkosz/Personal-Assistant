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
from datetime import datetime
from typing import Any

from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import llm, persona
from .config import ROOT
from .pipeline import Brain
from .scheduler import START

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
                _in_background(brain.handle_text(msg["text"], language=msg.get("language"),
                                                 mode="chat" if msg.get("mode") == "chat" else "voice"))
            elif msg.get("type") == "audio" and msg.get("b64"):
                mime = msg.get("mime", "webm")
                ext = "webm" if "webm" in mime else "ogg" if "ogg" in mime else "wav"
                _in_background(brain.handle_audio(base64.b64decode(msg["b64"]), f"speech.{ext}"))
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


class TaskPatch(BaseModel):
    status: str | None = None
    note: str | None = None
    due: str | None = None
    schedule: str | None = None
    category: str | None = None


@app.get("/api/tasks")
async def tasks(status: str = "open") -> list[dict[str, Any]]:
    return [t.to_dict() for t in brain.store.list_tasks(status)]


@app.post("/api/tasks")
async def create_task(body: TaskIn) -> dict[str, Any]:
    task = brain.store.create_task(body.title, body.description, body.due, body.schedule, body.module, body.priority,
                                   category=body.category)
    if brain.proactive.scheduler.running:
        brain.proactive.sync_recurring()
    return task.to_dict()


@app.patch("/api/tasks/{task_id}")
async def patch_task(task_id: str, body: TaskPatch) -> dict[str, Any]:
    try:
        return brain.store.update_task(task_id, body.status, body.note, body.due, schedule=body.schedule,
                                       category=body.category).to_dict()
    except KeyError:
        raise _not_found("task") from None


@app.get("/api/calendar")
async def calendar(start: str, end: str) -> dict[str, Any]:
    """This week's Google Calendar events, read through the google-calendar MCP server."""
    server = brain.hub.servers.get("google-calendar")
    if not server or server.status != "ready":
        return {"status": server.status if server else "missing", "error": server and server.error, "events": []}
    try:
        text, is_error = await brain.hub.call("google-calendar__list-events", {
            "calendarId": "primary", "timeMin": start, "timeMax": end,
            "timeZone": brain.settings.get("assistant.timezone", "Europe/Warsaw")})
        events = None if is_error else json.loads(text)["events"]
    except Exception as exc:
        text, events = f"{type(exc).__name__}: {exc}", None
    if events is None:
        return {"status": "error", "error": text[:300], "events": []}
    brain.bus.emit("calendar_sync", "mcp:google-calendar", events=len(events))
    return {"status": "ready", "error": None, "events": events}


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
