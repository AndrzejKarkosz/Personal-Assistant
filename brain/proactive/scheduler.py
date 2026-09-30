from __future__ import annotations

import json
import logging
from datetime import datetime, time as dtime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

if TYPE_CHECKING:
    from ..pipeline import Brain
    from ..memory import Task

log = logging.getLogger("alfred.proactive")

START = "@start"
LAST_ACTIVITY = "last_activity"


def in_quiet_hours(now: datetime, quiet: list[str] | None) -> bool:
    if not quiet or len(quiet) != 2:
        return False
    start, end = (dtime.fromisoformat(x) for x in quiet)
    t = now.time()
    return (start <= t or t < end) if start > end else (start <= t < end)


class ProactiveEngine:
    def __init__(self, brain: "Brain", state_file: Path):
        self.brain = brain
        self.settings = brain.settings
        self.state_file = state_file
        self.scheduler = AsyncIOScheduler(timezone=self.settings.get("assistant.timezone", "Europe/Warsaw"))
        self._fired: dict[str, str] = json.loads(state_file.read_text()) if state_file.exists() else {}

    def start(self) -> None:
        self.scheduler.add_job(self.check_due, "interval", minutes=1, id="due-check", coalesce=True)
        self.scheduler.add_job(self.brain.sessions.close_if_idle, "interval", minutes=1, id="idle-close")
        self.scheduler.add_job(self.heartbeat, "interval",
                               minutes=int(self.settings.get("proactive.heartbeat_minutes", 30)), id="heartbeat")
        self.scheduler.start()
        self.sync_recurring()
        for r in self.routines():
            if r["schedule"] == START:
                self.scheduler.add_job(self.run_start_routine, args=[r["id"]], id=f"start:{r['id']}",
                                       replace_existing=True)

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def sync_recurring(self) -> None:
        wanted = {f"task:{t.id}@{t.schedule}": (t.schedule, self.fire, [t.id, "schedule"])
                  for t in self.brain.store.list_tasks("open") if t.schedule}
        wanted |= {f"routine:{r['id']}@{r['schedule']}": (r["schedule"], self.run_routine, [r["id"]])
                   for r in self.routines() if r["schedule"] != START}
        for job in self.scheduler.get_jobs():
            if job.id.startswith(("task:", "routine:")) and job.id not in wanted:
                job.remove()
        for job_id, (cron, func, args) in wanted.items():
            if self.scheduler.get_job(job_id):
                continue
            try:
                trigger = CronTrigger.from_crontab(cron, timezone=self.scheduler.timezone)
            except ValueError:
                log.warning("Bad cron for %s: %s", job_id, cron)
                continue
            self.scheduler.add_job(func, trigger, args=args, id=job_id)

    def routines(self) -> list[dict]:
        path = self.settings.path("proactive.routines") if self.settings.get("proactive.routines") else None
        if not path or not path.exists():
            return []
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            log.warning("Ignoring %s: %s", path, exc)
            return []
        items = (data.get("routines") if isinstance(data, dict) else None) or []
        good = [r for r in items if isinstance(r, dict) and r.get("id") and r.get("prompt")
                and isinstance(r.get("schedule"), str)]
        if len(good) != len(items):
            log.warning("%s: skipped %d routine(s) without id, prompt or schedule", path, len(items) - len(good))
        return good

    async def run_routine(self, routine_id: str) -> None:
        routine = next((r for r in self.routines() if r["id"] == routine_id), None)
        if routine:
            await self.brain.handle_text(routine["prompt"], source="routine", module_hint=routine.get("module"))

    async def run_start_routine(self, routine_id: str) -> None:
        """@start: silent if Alfred was active within `min_idle_minutes`; the full (LLM) routine once a day,
        afterwards (with `welcome_back: true`) just the static welcome-back line - no tokens."""
        routine = next((r for r in self.routines() if r["id"] == routine_id), None)
        if not routine:
            return
        idle = self.idle()
        if idle is not None and idle < timedelta(minutes=float(routine.get("min_idle_minutes", 0))):
            return
        key = f"start:{routine_id}"
        if routine.get("welcome_back") and self._fired.get(key, "").startswith(f"{datetime.now():%Y-%m-%d}"):
            await self.brain.welcome_back()
            return
        self._remember(key)
        await self.run_routine(routine_id)

    def idle(self) -> timedelta | None:
        last = self._fired.get(LAST_ACTIVITY)
        return datetime.now() - datetime.fromisoformat(last) if last else None

    def touch(self) -> None:
        self._remember(LAST_ACTIVITY)

    async def check_due(self) -> None:
        if not self.settings.get("proactive.enabled", True):
            return
        self.sync_recurring()
        for task in self.brain.store.due_tasks():
            key = f"{task.id}@{task.due}"
            if key not in self._fired:
                await self.fire(task.id, "due", key)

    async def heartbeat(self) -> None:
        overdue = self.brain.store.due_tasks()
        self.brain.bus.emit("heartbeat", "proactive", open_tasks=len(self.brain.store.list_tasks("open")),
                            overdue=len(overdue))

    async def fire(self, task_id: str, trigger: str, key: str | None = None) -> None:
        task = self.brain.store.get_task(task_id)
        if task is None or not task.is_open:
            return
        key = key or f"{task.id}@{datetime.now():%Y-%m-%dT%H:%M}"
        self._remember(key)
        now = datetime.now().astimezone()
        quiet = in_quiet_hours(now, self.settings.get("proactive.quiet_hours"))
        state = self._state(task, trigger, now, quiet)
        p = await self.brain.router.should_interrupt(state)
        go = p >= 0.5 and (not quiet or task.priority == "high")
        self.brain.bus.emit("proactive_gate", "proactive", task=task.title, trigger=trigger,
                            probability=round(p, 3), quiet_hours=quiet, fired=go)
        if not go:
            return
        prompt = (f"[Proactive - you are speaking first] The task '{task.title}' "
                  f"({'scheduled ' + task.schedule if task.schedule else 'due ' + str(task.due)}) needs attention now."
                  + (f" Details: {task.description}." if task.description else "")
                  + f" Task id: {task.id}. Do what you can with your tools, update the task status, then tell "
                    "the user in one or two sentences.")
        await self.brain.handle_text(prompt, source="proactive", module_hint=task.module)

    def _state(self, task: "Task", trigger: str, now: datetime, quiet: bool) -> str:
        last = self.brain.sessions.current.last_activity if self.brain.sessions.current else None
        idle = f"{int((datetime.now() - last).total_seconds() // 60)} minutes ago" if last else "not today"
        return (f"Time: {now:%A %H:%M}. Trigger: {trigger}. Task: {task.title} (priority {task.priority}, "
                f"due {task.due or '-'}, schedule {task.schedule or '-'}). {task.description} "
                f"User last spoke: {idle}. Quiet hours: {'yes' if quiet else 'no'}.")

    def _remember(self, key: str) -> None:
        self._fired[key] = datetime.now().isoformat(timespec="seconds")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self._fired, indent=1))

    def status(self) -> list[dict]:
        return [{"id": j.id, "next_run": j.next_run_time.isoformat() if j.next_run_time else None}
                for j in self.scheduler.get_jobs()]
