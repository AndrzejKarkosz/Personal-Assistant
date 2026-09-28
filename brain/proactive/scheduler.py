"""Proactive layer: triggers + a cheap gate, so Alfred can speak first without burning tokens.

Triggers
  - one-off tasks whose `due` has passed   (checked every minute, no LLM involved)
  - recurring tasks with a cron `schedule`  (APScheduler cron jobs, re-synced every minute)
  - heartbeat                               (every N minutes: overdue tasks nudge)
  - idle session closer                     (writes the session summary to memory)

Gate
  Before waking Claude, Jev answers one yes/no question: "is this worth interrupting him now?"
  Only a yes runs the pipeline. Every decision is written to the activity log.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, time as dtime
from pathlib import Path
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

if TYPE_CHECKING:
    from ..pipeline import Brain
    from ..memory import Task

log = logging.getLogger("alfred.proactive")


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

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    # ---------------------------------------------------------------- triggers
    def sync_recurring(self) -> None:
        wanted = {f"task:{t.id}": t for t in self.brain.store.list_tasks("open") if t.schedule}
        for job in self.scheduler.get_jobs():
            if job.id.startswith("task:") and job.id not in wanted:
                job.remove()
        for job_id, task in wanted.items():
            if self.scheduler.get_job(job_id):
                continue
            try:
                trigger = CronTrigger.from_crontab(task.schedule, timezone=self.scheduler.timezone)
            except ValueError:
                log.warning("Bad cron for task %s: %s", task.id, task.schedule)
                continue
            self.scheduler.add_job(self.fire, trigger, args=[task.id, "schedule"], id=job_id)

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

    # -------------------------------------------------------------------- fire
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
