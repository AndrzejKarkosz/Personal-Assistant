"""FastAPI server: WebSocket for voice/text + events, REST for the UI panels, static UI."""
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

from . import llm
from .config import ROOT
from .pipeline import Brain
from .proactive.scheduler import START
from .voice import persona

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
brain = Brain()
_claude_status: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if llm.backend(brain.settings) == "subscription":
        _claude_status.update(await asyncio.to_thread(llm.subscription_status))
    await brain.start()
    yield
    await brain.stop()


app = FastAPI(title="Alfred brain", lifespan=lifespan)
_background: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)


# ------------------------------------------------------------------ websocket
@app.websocket("/ws")
async def ws(socket: WebSocket) -> None:
    await socket.accept()
    queue = brain.bus.subscribe()

    async def pump() -> None:
        while True:
            event = await queue.get()
            await socket.send_json(event.to_dict())

    pump_task = asyncio.create_task(pump())
    try:
        while True:
            msg = await socket.receive_json()
            kind = msg.get("type")
            if kind == "text" and msg.get("text", "").strip():
                _spawn(brain.handle_text(msg["text"], language=msg.get("language")))
            elif kind == "audio" and msg.get("b64"):
                ext = "webm" if "webm" in msg.get("mime", "webm") else "ogg" if "ogg" in msg.get("mime", "") else "wav"
                _spawn(brain.handle_audio(base64.b64decode(msg["b64"]), f"speech.{ext}"))
            elif kind == "confirm":
                brain.guard.resolve(bool(msg.get("approved")))
    except WebSocketDisconnect:
        pass
    finally:
        pump_task.cancel()
        brain.bus.unsubscribe(queue)


# ----------------------------------------------------------------------- REST
class TextIn(BaseModel):
    text: str


class TaskIn(BaseModel):
    title: str
    description: str = ""
    due: str | None = None
    schedule: str | None = None
    priority: str = "normal"
    module: str | None = None


class TaskPatch(BaseModel):
    status: str | None = None
    note: str | None = None
    due: str | None = None
    schedule: str | None = None


class EnabledIn(BaseModel):
    enabled: bool


@app.get("/api/status")
async def status() -> dict[str, Any]:
    session = brain.sessions.current
    keys = brain.settings.status()
    backend = llm.backend(brain.settings)
    if backend == "subscription":
        keys["anthropic"] = bool(_claude_status.get("ok"))
    return {
        "keys": keys,
        "backend": backend,
        "claude": _claude_status if backend == "subscription" else {"ok": keys["anthropic"], "detail": "API key"},
        "mcp": brain.hub.status(),
        "jobs": brain.proactive.status() if brain.proactive.scheduler.running else [],
        "session": {"id": session.id, "turns": len(session.turns), "usage": session.usage,
                    "language": session.language} if session else None,
        "pending_confirmation": brain.guard.pending.question if brain.guard.pending else None,
    }


@app.get("/api/graph")
async def graph() -> dict[str, Any]:
    return brain.graph()


@app.get("/api/modules")
async def modules() -> list[dict[str, Any]]:
    out = []
    for m in brain.registry.modules.values():
        page = brain.map.modules.get(m.id, {})
        out.append({
            "id": m.id, "label": m.label, "description": m.description, "enabled": m.enabled,
            "examples": m.examples, "model": m.model, "effort": m.effort,
            "capabilities": [{"id": c.id, "label": c.label, "confirm": c.confirm,
                              "tools": brain.map.capabilities.get(c.id, {}).get("tools", [])}
                             for c in m.capabilities.values()],
            "uses": m.uses, "servers": page.get("servers", []),
            "skills": [{"id": s.id, "name": s.name, "description": s.description} for s in m.skills],
        })
    return out


@app.post("/api/modules/{module_id}/enabled")
async def set_module_enabled(module_id: str, body: EnabledIn) -> dict[str, Any]:
    if not brain.registry.get(module_id):
        raise HTTPException(404, "No such module")
    brain.registry.set_enabled(module_id, body.enabled)
    brain.rebuild_map()
    return {"id": module_id, "enabled": body.enabled}


@app.post("/api/modules/reload")
async def reload_modules() -> dict[str, Any]:
    return brain.rebuild_map()


# ------------------------------------------------------------------- brain map
@app.get("/api/map")
async def brain_map() -> dict[str, Any]:
    m = brain.map
    return {
        "counts": {"modules": len(m.modules), "capabilities": len(m.capabilities), "skills": len(m.skills),
                   "tools": len(m.tools), "servers": len(m.servers), "topics": len(m.topics)},
        "modules": list(m.modules.values()), "capabilities": list(m.capabilities.values()),
        "skills": list(m.skills.values()), "tools": list(m.tools.values()),
        "servers": list(m.servers.values()), "topics": list(m.topics.values()),
        "jev": brain.router.questions(),
    }


@app.get("/api/map/page")
async def brain_map_page(path: str = "index.md") -> dict[str, str]:
    try:
        return {"path": path, "content": brain.map.page(path)}
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, "No such page") from None


@app.post("/api/map/rebuild")
async def brain_map_rebuild() -> dict[str, Any]:
    return brain.rebuild_map()


# --------------------------------------------------------------------- persona
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


@app.post("/api/classify")
async def classify(body: TextIn) -> dict[str, Any]:
    route = await brain.router.classify(body.text)
    return route.to_dict()


@app.post("/api/ask")
async def ask(body: TextIn) -> dict[str, str]:
    return {"answer": await brain.handle_text(body.text)}


@app.get("/api/tasks")
async def tasks(status: str = "open") -> list[dict[str, Any]]:
    return [t.to_dict() for t in brain.store.list_tasks(status)]


@app.post("/api/tasks")
async def create_task(body: TaskIn) -> dict[str, Any]:
    task = brain.store.create_task(body.title, body.description, body.due, body.schedule, body.module,
                                   body.priority)
    brain.proactive.sync_recurring() if brain.proactive.scheduler.running else None
    return task.to_dict()


@app.patch("/api/tasks/{task_id}")
async def patch_task(task_id: str, body: TaskPatch) -> dict[str, Any]:
    try:
        task = brain.store.update_task(task_id, body.status, body.note, body.due, None, body.schedule)
    except KeyError:
        raise HTTPException(404, "No such task") from None
    return task.to_dict()


@app.get("/api/calendar")
async def calendar(start: str, end: str) -> dict[str, Any]:
    """Google Calendar events between two local times ("2026-09-28T00:00:00"), read through the
    google-calendar MCP server - the same connection Claude uses, so there is one sign-in."""
    server = brain.hub.servers.get("google-calendar")
    if not server or server.status != "ready":
        return {"status": server.status if server else "missing", "error": server.error if server else None,
                "events": []}
    try:
        text, is_error = await brain.hub.call("google-calendar__list-events", {
            "calendarId": "primary", "timeMin": start, "timeMax": end,
            "timeZone": brain.settings.get("assistant.timezone", "Europe/Warsaw")})
        events = None if is_error else json.loads(text)["events"]
    except Exception as exc:  # noqa: BLE001 - an outside server; the UI shows why
        text, events = f"{type(exc).__name__}: {exc}", None
    if events is None:
        return {"status": "error", "error": text[:300], "events": []}
    brain.bus.emit("calendar_sync", "mcp:google-calendar", events=len(events))
    return {"status": "ready", "error": None, "events": events}


@app.get("/api/routines")
async def routines() -> list[dict[str, Any]]:
    """Routines with today's state, read from the activity log: ran (answer / error), due, next run."""
    events = brain.bus.log.read(limit=100_000)
    tz = brain.proactive.scheduler.timezone
    now = datetime.now(tz)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    out = []
    for r in brain.proactive.routines():
        runs = [e for e in events if e["kind"] == "transcript" and e["data"].get("source") == "routine"
                and e["data"].get("text") == r["prompt"]]
        rid = runs[-1]["request_id"] if runs else None
        errors = [e for e in events if e["kind"] == "error" and rid and e["request_id"] == rid]
        answer = next((e for e in events if e["kind"] == "answer" and rid and e["request_id"] == rid), None)
        first = next_run = None
        if r["schedule"] != START:
            try:
                trigger = CronTrigger.from_crontab(r["schedule"], timezone=tz)
                first, next_run = trigger.get_next_fire_time(None, midnight), trigger.get_next_fire_time(None, now)
            except ValueError:
                pass
        # a failed run still ends with an (apologising) answer, so any error decides the result
        out.append({**r, "ran_at": runs[-1]["ts"] if runs else None,
                    "result": "error" if errors else "answer" if answer else None,
                    "answer": errors[-1]["data"].get("message") if errors else answer["data"].get("text") if answer else None,
                    "due_today": bool(first and first <= now),
                    "next_run": next_run.isoformat() if next_run else None})
    return out


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
        raise HTTPException(404, "No such page") from None


@app.get("/api/memory/sessions")
async def memory_sessions(limit: int = 20) -> list[dict[str, Any]]:
    return [meta for meta, _ in brain.store.recent_sessions(limit)]


@app.post("/api/session/close")
async def close_session() -> dict[str, bool]:
    await brain.sessions.close()
    return {"closed": True}


@app.get("/api/logs")
async def logs(day: str | None = None, kind: str | None = None, limit: int = 300) -> list[dict[str, Any]]:
    return brain.bus.log.read(day, limit, kind)


@app.get("/api/logs/days")
async def log_days() -> list[str]:
    return brain.bus.log.days()


EDITABLE = ("llm", "assistant", "models", "router", "voice", "memory", "proactive")


@app.get("/api/settings")
async def get_settings() -> dict[str, Any]:
    return {k: brain.settings.get(k) for k in EDITABLE} | {"voice_id": brain.settings.voice_id}


@app.put("/api/settings")
async def put_settings(patch: dict[str, Any]) -> dict[str, Any]:
    clean = {k: v for k, v in patch.items() if k in EDITABLE and isinstance(v, dict)}
    brain.settings.update(clean)
    return await get_settings()


# ------------------------------------------------------------------------- UI
UI_DIR = ROOT / "ui"
app.mount("/static", StaticFiles(directory=UI_DIR), name="static")


@app.middleware("http")
async def fresh_ui(request, call_next):
    """Revalidate UI files on every load, so an updated UI never mixes with cached old files."""
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(UI_DIR / "index.html")
