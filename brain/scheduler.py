"""Alfred speaking first. Runs inside the brain (APScheduler):

- every minute: tasks whose due time has passed -> Jev decides "worth interrupting?" -> Alfred tells you;
- recurring tasks (cron) and routines (data/routines.yaml) as scheduled jobs;
- "@start" routines once when the app starts; idle sessions closed.

What already fired is remembered in data/proactive_state.json, so a restart does not repeat it.
The routines file is read and written only here (Alfred's routine tools and the UI use the functions below).
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

from . import okf
from .events import new_id
from .memory import parse_time

if TYPE_CHECKING:
    from .pipeline import Brain

log = logging.getLogger("alfred.proactive")
START = "@start"
LAST_ACTIVITY = "last_activity"


def check_cron(schedule: str | None, allow_start: bool = False) -> None:
    if schedule and not (allow_start and schedule == START):
        try:
            CronTrigger.from_crontab(schedule)
        except ValueError:
            raise ValueError(f"schedule '{schedule}' is not a 5-field cron (e.g. '0 8 * * 1-5')") from None


# ---- routines.yaml -------------------------------------------------------------------------------------------------

def routines_file(settings) -> Path | None:
    return settings.path("proactive.routines") if settings.get("proactive.routines") else None


def read_routines(path: Path) -> list[dict]:
    """Every routine in the file as it is written ([] without the file). A broken file raises (yaml.YAMLError), so
    a save never overwrites what it could not read."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None
    items = data.get("routines") if isinstance(data, dict) else None
    return [r for r in items if isinstance(r, dict)] if isinstance(items, list) else []


def valid_routines(path: Path | None) -> list[dict]:
    """The routines that can run - with an id, a prompt and a schedule. Read fresh every time, so edits apply within
    a minute; a broken file means none (and a warning in the log)."""
    try:
        items = read_routines(path) if path else []
    except yaml.YAMLError as exc:
        log.warning("Ignoring %s: %s", path, exc)
        return []
    good = [r for r in items if r.get("id") and r.get("prompt") and isinstance(r.get("schedule"), str)]
    if len(good) != len(items):
        log.warning("%s: skipped %d routine(s) without id, prompt or schedule", path, len(items) - len(good))
    return good


def _write_routines(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"routines": items}, allow_unicode=True, sort_keys=False), encoding="utf-8")


def save_routine(path: Path | None, rid: str, schedule: str, prompt: str, module: str | None = None) -> str:
    """Create a routine, or change the one with the same id (its other keys, e.g. min_idle_minutes, stay)."""
    if not path:
        raise ValueError("No routines file configured (proactive.routines)")
    rid = okf.slugify(rid)
    check_cron(schedule, allow_start=True)
    if not str(prompt or "").strip():
        raise ValueError("a routine needs a prompt")
    new = {"id": rid, "schedule": schedule, "prompt": prompt.strip()} | ({"module": module} if module else {})
    items = read_routines(path)
    old = next((r for r in items if r.get("id") == rid), None)
    if old:
        old.update(new)
    else:
        items.append(new)
    _write_routines(path, items)
    return f"{'Updated' if old else 'Created'} routine {rid} ({schedule})"


def delete_routine(path: Path | None, rid: str) -> str:
    if not path:
        raise ValueError("No routines file configured (proactive.routines)")
    items = read_routines(path)
    kept = [r for r in items if r.get("id") != rid]
    if len(kept) == len(items):
        raise KeyError(f"No routine '{rid}'. Routines: {', '.join(str(r.get('id')) for r in items) or 'none'}")
    _write_routines(path, kept)
    return f"Deleted routine {rid}"


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
        self.scheduler.add_job(self.roll_over, "cron", hour=0, minute=1, id="rollover")
        self.scheduler.start()
        self.roll_over()                   # catch up on the days the app was off
        self.sync_recurring()
        for r in self.routines():
            if r["schedule"] == START:
                self.scheduler.add_job(self.run_start_routine, args=[r["id"]], id=f"start:{r['id']}",
                                       replace_existing=True)

    def roll_over(self) -> None:
        """What was not done yesterday (or earlier) moves to today, same hour."""
        if moved := self.brain.store.roll_over():
            self.brain.bus.emit("tasks_rolled", "proactive", tasks=[{"id": t.id, "title": t.title, "due": t.due}
                                                                     for t in moved])

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def status(self) -> list[dict]:
        return [{"id": j.id, "next_run": j.next_run_time.isoformat() if j.next_run_time else None}
                for j in self.scheduler.get_jobs()]

    def routines(self) -> list[dict]:
        return valid_routines(routines_file(self.settings))

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
            request_id = new_id("r-")     # the UI finds this run's answer or error by it
            self.brain.bus.emit("routine_run", "proactive", request_id, routine=routine_id)
            await self.brain.handle_text(routine["prompt"], source="routine", module_hint=routine.get("module"),
                                         request_id=request_id)

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
        lead = timedelta(minutes=float(self.settings.get("proactive.reminders.lead_minutes", 0)))
        for task in self.brain.store.due_tasks(within=lead):
            if f"{task.id}@{task.due}" in self._fired:
                continue
            if parse_time(task.due) > datetime.now().astimezone():      # a reminder ahead of time, then on time
                if (key := f"pre:{task.id}@{task.due}") not in self._fired:
                    await self.fire(task.id, "upcoming", key)
            else:
                await self.fire(task.id, "due", f"{task.id}@{task.due}")

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
            soon = trigger == "upcoming"
            fastest = self.settings.get("proactive.reminders.fastest_path", False)
            await self.brain.handle_text(
                f"[Proactive - you are speaking first] The task '{task.title}' ({when}) "
                + ("is coming up soon - this is a reminder ahead of time." if soon else "needs attention now.")
                + (f" Details: {task.description}." if task.description else "")
                + f" Task id: {task.id}. "
                + ("Do not change its status yet. " if soon else "Do what you can with your tools, update the task status, ")
                + ("Propose the fastest way to get it done: the first concrete step and what can be skipped or "
                   "batched. " if fastest else "")
                + "Tell the user in one or two sentences.", source="proactive", module_hint=task.module)

    def _remember(self, key: str) -> None:
        self._fired[key] = datetime.now().isoformat(timespec="seconds")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self._fired, indent=1))
