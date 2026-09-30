"""Alfred speaking first. Runs inside the brain (APScheduler):

- every minute: tasks whose due time has passed -> Jev decides "worth interrupting?" -> Alfred tells you;
- recurring tasks (cron) and routines (config/routines.yaml) as scheduled jobs;
- "@start" routines once when the app starts; idle sessions closed; a heartbeat every 30 min.

What already fired is remembered in data/proactive_state.json, so a restart does not repeat it.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

if TYPE_CHECKING:
    from .pipeline import Brain

log = logging.getLogger("alfred.proactive")
START = "@start"
LAST_ACTIVITY = "last_activity"


def in_quiet_hours(now: datetime, quiet: list[str] | None) -> bool:
    """quiet = ["23:00", "07:00"]; a window may cross midnight."""
    if not quiet or len(quiet) != 2:
        return False
    start, end = (time.fromisoformat(x) for x in quiet)
    t = now.time()
    return (start <= t or t < end) if start > end else (start <= t < end)


class ProactiveEngine:
    def __init__(self, brain: Brain, state_file: Path):
        self.brain = brain
        self.settings = brain.settings
        self.state_file = state_file
        self.scheduler = AsyncIOScheduler(timezone=self.settings.get("assistant.timezone", "Europe/Warsaw"))
        self._fired: dict[str, str] = json.loads(state_file.read_text()) if state_file.exists() else {}

    def start(self) -> None:
        self.scheduler.add_job(self.check_due, "interval", minutes=1, id="due-check", coalesce=True)
        self.scheduler.add_job(self.brain.sessions.close_if_idle, "interval", minutes=1, id="idle-close")
        self.scheduler.add_job(self.heartbeat, "interval", id="heartbeat",
                               minutes=int(self.settings.get("proactive.heartbeat_minutes", 30)))
        self.scheduler.start()
        self.sync_recurring()
        for r in self.routines():
            if r["schedule"] == START:
                self.scheduler.add_job(self.run_start_routine, args=[r["id"]], id=f"start:{r['id']}",
                                       replace_existing=True)

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def status(self) -> list[dict]:
        return [{"id": j.id, "next_run": j.next_run_time.isoformat() if j.next_run_time else None}
                for j in self.scheduler.get_jobs()]

    def routines(self) -> list[dict]:
        """Valid routines from config/routines.yaml (read fresh every time, so edits apply within a minute)."""
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

    def sync_recurring(self) -> None:
        """One cron job per recurring task and per routine; jobs whose task/routine is gone are removed."""
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
                self.scheduler.add_job(func, CronTrigger.from_crontab(cron, timezone=self.scheduler.timezone),
                                       args=args, id=job_id)
            except ValueError:
                log.warning("Bad cron for %s: %s", job_id, cron)

    async def run_routine(self, routine_id: str) -> None:
        if routine := next((r for r in self.routines() if r["id"] == routine_id), None):
            await self.brain.handle_text(routine["prompt"], source="routine", module_hint=routine.get("module"))

    async def run_start_routine(self, routine_id: str) -> None:
        """Silent if you were active within `min_idle_minutes`. The full routine once a day; later starts that day
        (with `welcome_back: true`) only get the fixed welcome-back line - no tokens."""
        routine = next((r for r in self.routines() if r["id"] == routine_id), None)
        idle = self.idle()
        if not routine or (idle is not None and idle < timedelta(minutes=float(routine.get("min_idle_minutes", 0)))):
            return
        key = f"start:{routine_id}"
        if routine.get("welcome_back") and self._fired.get(key, "").startswith(f"{datetime.now():%Y-%m-%d}"):
            await self.brain.welcome_back()
            return
        self._remember(key)
        await self.run_routine(routine_id)

    def idle(self) -> timedelta | None:
        """How long since you last said anything (None = never)."""
        last = self._fired.get(LAST_ACTIVITY)
        return datetime.now() - datetime.fromisoformat(last) if last else None

    def touch(self) -> None:
        self._remember(LAST_ACTIVITY)

    async def check_due(self) -> None:
        if not self.settings.get("proactive.enabled", True):
            return
        self.sync_recurring()
        for task in self.brain.store.due_tasks():
            if (key := f"{task.id}@{task.due}") not in self._fired:
                await self.fire(task.id, "due", key)

    async def heartbeat(self) -> None:
        self.brain.bus.emit("heartbeat", "proactive", open_tasks=len(self.brain.store.list_tasks("open")),
                            overdue=len(self.brain.store.due_tasks()))

    async def fire(self, task_id: str, trigger: str, key: str | None = None) -> None:
        """A task needs attention: ask Jev if it is worth interrupting, then let Alfred handle it and speak."""
        task = self.brain.store.get_task(task_id)
        if task is None or not task.is_open:
            return
        self._remember(key or f"{task.id}@{datetime.now():%Y-%m-%dT%H:%M}")
        now = datetime.now().astimezone()
        quiet = in_quiet_hours(now, self.settings.get("proactive.quiet_hours"))
        last = self.brain.sessions.current.last_activity if self.brain.sessions.current else None
        spoke = f"{int((datetime.now() - last).total_seconds() // 60)} minutes ago" if last else "not today"
        p = await self.brain.router.should_interrupt(
            f"Time: {now:%A %H:%M}. Trigger: {trigger}. Task: {task.title} (priority {task.priority}, "
            f"due {task.due or '-'}, schedule {task.schedule or '-'}). {task.description} "
            f"User last spoke: {spoke}. Quiet hours: {'yes' if quiet else 'no'}.")
        go = p >= 0.5 and (not quiet or task.priority == "high")
        self.brain.bus.emit("proactive_gate", "proactive", task=task.title, trigger=trigger, probability=round(p, 3),
                            quiet_hours=quiet, fired=go)
        if go:
            when = f"scheduled {task.schedule}" if task.schedule else f"due {task.due}"
            await self.brain.handle_text(
                f"[Proactive - you are speaking first] The task '{task.title}' ({when}) needs attention now."
                + (f" Details: {task.description}." if task.description else "")
                + f" Task id: {task.id}. Do what you can with your tools, update the task status, then tell the user "
                  "in one or two sentences.", source="proactive", module_hint=task.module)

    def _remember(self, key: str) -> None:
        self._fired[key] = datetime.now().isoformat(timespec="seconds")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self._fired, indent=1))
