"""Brain session memory - an OKF bundle separate from the Knowledge-Base library.

The Knowledge-Base is *what Alfred knows*. This bundle is *what Alfred has been doing*:

  index.md                     entry point, regenerated: open tasks, recent sessions, latest changes
  log.md                       append-only change log - every task/fact/session change, newest last
  profile.md                   who the user is, preferences (type: Profile)
  tasks/<id>.md                type: Task   status todo|in_progress|waiting|done|cancelled, due, schedule
  sessions/YYYY/MM/<id>.md     type: Session  summary, done, changed, open threads, token usage
  facts/<category>/<slug>.md   type: Fact   people | places | preferences | projects | other

The briefing() at the start of every session is built from these files, so the executor
knows what is done, what changed last time and what to pick up - in a few hundred tokens
instead of replaying old transcripts.
"""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from . import okf

TASK_STATUSES = ("todo", "in_progress", "waiting", "done", "cancelled")
OPEN_STATUSES = ("todo", "in_progress", "waiting")
FACT_CATEGORIES = ("people", "places", "preferences", "projects", "other")


def _now() -> datetime:
    return datetime.now().astimezone()


def _iso(dt: datetime | None = None) -> str:
    return (dt or _now()).isoformat(timespec="seconds")


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.astimezone()
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.astimezone()


@dataclass
class Task:
    id: str
    title: str
    status: str = "todo"
    description: str = ""
    due: str | None = None
    schedule: str | None = None       # cron expression for recurring tasks ("0 8 * * 1-5")
    module: str | None = None
    priority: str = "normal"          # low | normal | high
    created: str = field(default_factory=_iso)
    updated: str = field(default_factory=_iso)
    history: list[str] = field(default_factory=list)

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    def due_dt(self) -> datetime | None:
        return _parse_dt(self.due)

    def to_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


class MemoryStore:
    def __init__(self, root: Path):
        self.root = root
        self._lock = threading.RLock()
        self.ensure()

    # ------------------------------------------------------------------ setup
    def ensure(self) -> None:
        for sub in ("tasks", "sessions", *(f"facts/{c}" for c in FACT_CATEGORIES)):
            (self.root / sub).mkdir(parents=True, exist_ok=True)
        if not (self.root / "profile.md").exists():
            okf.write(self.root / "profile.md", {
                "type": "Profile", "title": "Andrzej",
                "description": "Who I serve and how he likes things done.", "timestamp": _iso(),
            }, "# Profile\n\n## Preferences\n\n## Facts\n")
        if not (self.root / "log.md").exists():
            okf.write(self.root / "log.md", {
                "type": "Log", "title": "Brain change log",
                "description": "Append-only record of everything Alfred changed in his memory.",
            }, "# Change log\n")
        if not (self.root / "index.md").exists():
            self.rebuild_index()

    # -------------------------------------------------------------------- log
    def log(self, action: str, detail: str, session_id: str | None = None) -> None:
        line = f"- {_iso()} **{action}** {detail}" + (f" _(session {session_id})_" if session_id else "")
        with self._lock, (self.root / "log.md").open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def log_since(self, since: datetime | None, limit: int = 30) -> list[str]:
        lines = [l for l in (self.root / "log.md").read_text(encoding="utf-8").splitlines() if l.startswith("- ")]
        if since:
            kept = []
            for line in lines:
                m = re.match(r"- (\S+)", line)
                dt = _parse_dt(m.group(1)) if m else None
                if dt and dt >= since:
                    kept.append(line)
            lines = kept
        return lines[-limit:]

    # ------------------------------------------------------------------ tasks
    def _task_path(self, task_id: str) -> Path:
        return self.root / "tasks" / f"{task_id}.md"

    def _save_task(self, task: Task) -> None:
        meta = {
            "type": "Task", "title": task.title, "description": task.description[:200],
            "status": task.status, "priority": task.priority, "due": task.due, "schedule": task.schedule,
            "module": task.module, "created": task.created, "timestamp": task.updated,
            "tags": ["task", task.status] + ([task.module] if task.module else []),
        }
        body = f"# {task.title}\n\n{task.description}\n\n## History\n" + "\n".join(f"- {h}" for h in task.history)
        okf.write(self._task_path(task.id), meta, body)

    def _load_task(self, path: Path) -> Task:
        meta, body = okf.read(path)
        description = body.split("## History")[0]
        description = re.sub(r"^# .*\n", "", description).strip()
        history = [l[2:] for l in body.split("## History", 1)[-1].splitlines() if l.startswith("- ")]
        return Task(
            id=path.stem, title=meta.get("title", path.stem), status=meta.get("status", "todo"),
            description=description, due=meta.get("due"), schedule=meta.get("schedule"),
            module=meta.get("module"), priority=meta.get("priority", "normal"),
            created=str(meta.get("created", "")), updated=str(meta.get("timestamp", "")), history=history,
        )

    def create_task(self, title: str, description: str = "", due: str | None = None,
                    schedule: str | None = None, module: str | None = None, priority: str = "normal",
                    session_id: str | None = None) -> Task:
        with self._lock:
            base = f"{_now():%Y%m%d}-{okf.slugify(title, 32)}"
            task_id, n = base, 2
            while self._task_path(task_id).exists():
                task_id, n = f"{base}-{n}", n + 1
            task = Task(id=task_id, title=title, description=description, due=due, schedule=schedule,
                        module=module, priority=priority)
            task.history.append(f"{task.created} created")
            self._save_task(task)
            self.log("task.created", f"[{title}](tasks/{task_id}.md)" + (f" due {due}" if due else ""), session_id)
            self.rebuild_index()
            return task

    def update_task(self, task_id: str, status: str | None = None, note: str | None = None,
                    due: str | None = None, title: str | None = None, schedule: str | None = None,
                    session_id: str | None = None) -> Task:
        with self._lock:
            path = self._task_path(task_id)
            if not path.exists():
                raise KeyError(f"No task {task_id}")
            task = self._load_task(path)
            changes = []
            if status and status != task.status:
                if status not in TASK_STATUSES:
                    raise ValueError(f"status must be one of {TASK_STATUSES}")
                changes.append(f"status {task.status} -> {status}")
                task.status = status
            if due is not None and due != task.due:
                changes.append(f"due -> {due}")
                task.due = due or None
            if schedule is not None and schedule != task.schedule:
                changes.append(f"schedule -> {schedule}")
                task.schedule = schedule or None
            if title and title != task.title:
                changes.append(f"renamed to {title}")
                task.title = title
            if note:
                changes.append(f"note: {note}")
            if not changes:
                return task
            task.updated = _iso()
            task.history.append(f"{task.updated} " + "; ".join(changes))
            self._save_task(task)
            self.log("task.updated", f"[{task.title}](tasks/{task_id}.md): " + "; ".join(changes), session_id)
            self.rebuild_index()
            return task

    def get_task(self, task_id: str) -> Task | None:
        path = self._task_path(task_id)
        return self._load_task(path) if path.exists() else None

    def list_tasks(self, status: str | None = "open") -> list[Task]:
        tasks = [self._load_task(p) for p in sorted((self.root / "tasks").glob("*.md"))]
        if status == "open":
            tasks = [t for t in tasks if t.is_open]
        elif status and status != "all":
            tasks = [t for t in tasks if t.status == status]
        far = _now() + timedelta(days=3650)
        prio = {"high": 0, "normal": 1, "low": 2}
        return sorted(tasks, key=lambda t: (t.due_dt() or far, prio.get(t.priority, 1)))

    def due_tasks(self, horizon: timedelta = timedelta(0)) -> list[Task]:
        limit = _now() + horizon
        return [t for t in self.list_tasks("open") if t.due_dt() and t.due_dt() <= limit]

    # ------------------------------------------------------------------ facts
    def remember(self, category: str, title: str, content: str, session_id: str | None = None) -> Path:
        category = category if category in FACT_CATEGORIES else "other"
        path = self.root / "facts" / category / f"{okf.slugify(title)}.md"
        with self._lock:
            if path.exists():
                meta, body = okf.read(path)
                body = body.rstrip() + f"\n\n- {_iso()}: {content}"
                meta["timestamp"] = _iso()
                okf.write(path, meta, body)
                action = "fact.updated"
            else:
                okf.write(path, {
                    "type": "Fact", "title": title, "description": content[:200],
                    "tags": [category], "timestamp": _iso(),
                }, f"# {title}\n\n- {_iso()}: {content}")
                action = "fact.created"
            self.log(action, f"[{title}]({path.relative_to(self.root).as_posix()})", session_id)
        return path

    # --------------------------------------------------------------- sessions
    def write_session(self, session_id: str, started: str, ended: str, summary: dict[str, Any],
                      usage: dict[str, int], turns: int) -> Path:
        start_dt = _parse_dt(started) or _now()
        path = self.root / "sessions" / f"{start_dt:%Y}" / f"{start_dt:%m}" / f"{session_id}.md"
        meta = {
            "type": "Session", "title": summary.get("title") or f"Session {start_dt:%Y-%m-%d %H:%M}",
            "description": summary.get("summary", "")[:240], "tags": summary.get("domains", []),
            "timestamp": ended, "started": started, "ended": ended, "turns": turns,
            "tokens": usage, "open_threads": summary.get("open_threads", []),
        }
        sections = [f"# {meta['title']}", "## Summary", summary.get("summary", "")]
        for key, heading in (("done", "Done"), ("changed", "Changed"), ("open_threads", "Open threads"),
                             ("facts", "Facts learned")):
            items = summary.get(key) or []
            if items:
                sections += [f"## {heading}", "\n".join(f"- {i}" for i in items)]
        okf.write(path, meta, "\n\n".join(sections))
        self.log("session.closed", f"[{meta['title']}]({path.relative_to(self.root).as_posix()})", session_id)
        self.rebuild_index()
        return path

    def recent_sessions(self, n: int = 3) -> list[tuple[dict[str, Any], str]]:
        files = sorted((self.root / "sessions").rglob("*.md"),
                       key=lambda p: str(okf.read(p)[0].get("ended", "")), reverse=True)
        return [okf.read(p) for p in files[:n]]

    # ------------------------------------------------------------ retrieval
    def search(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        terms = [t for t in re.findall(r"\w+", query.lower()) if len(t) > 2]
        hits = []
        for path in self.root.rglob("*.md"):
            if path.name in ("log.md", "index.md"):
                continue
            meta, body = okf.read(path)
            haystack = (" ".join(str(v) for v in meta.values()) + " " + body).lower()
            score = sum(haystack.count(t) for t in terms)
            if score:
                hits.append({
                    "path": path.relative_to(self.root).as_posix(), "type": meta.get("type"),
                    "title": meta.get("title"), "description": meta.get("description"),
                    "timestamp": str(meta.get("timestamp", "")), "score": score,
                })
        return sorted(hits, key=lambda h: (h["score"], h["timestamp"]), reverse=True)[:limit]

    def read(self, rel_path: str) -> str:
        path = (self.root / rel_path).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError("Path outside memory bundle")
        return path.read_text(encoding="utf-8")

    def profile(self) -> str:
        return okf.read(self.root / "profile.md")[1]

    # -------------------------------------------------------------- briefing
    def briefing(self, recall_sessions: int = 3) -> str:
        """Compact state for the start of a session: what is open, what happened, what changed."""
        now = _now()
        out = [f"Now: {now:%A %Y-%m-%d %H:%M %Z}"]
        profile = self.profile().strip()
        if profile and len(profile) > 40:
            out.append("Profile:\n" + profile[:1200])
        tasks = self.list_tasks("open")
        if tasks:
            lines = []
            for t in tasks[:15]:
                due = t.due_dt()
                flag = " OVERDUE" if due and due < now else ""
                lines.append(f"- [{t.id}] {t.title} ({t.status}{', due ' + t.due if t.due else ''}"
                             f"{', every ' + t.schedule if t.schedule else ''}){flag}")
            out.append("Open tasks:\n" + "\n".join(lines))
        else:
            out.append("Open tasks: none")
        sessions = self.recent_sessions(recall_sessions)
        if sessions:
            lines = []
            for meta, body in sessions:
                threads = meta.get("open_threads") or []
                lines.append(f"- {meta.get('ended', '')[:16]} {meta.get('title')}: {meta.get('description', '')}"
                             + (f" | open: {'; '.join(threads)}" if threads else ""))
            out.append("Recent sessions:\n" + "\n".join(lines))
            last_end = _parse_dt(sessions[0][0].get("ended"))
            changes = [l for l in self.log_since(last_end) if "session.closed" not in l]
            if changes:
                out.append("Changed since the last session:\n" + "\n".join(changes))
        return "\n\n".join(out)

    # ----------------------------------------------------------------- index
    def rebuild_index(self) -> None:
        with self._lock:
            tasks = self.list_tasks("open") if (self.root / "tasks").exists() else []
            sessions = self.recent_sessions(10) if (self.root / "sessions").exists() else []
            body = ["# Alfred's memory", "",
                    "Progressive disclosure: start here, then open a task, session or fact page.", "",
                    "## Open tasks"]
            body += [f"- [{t.title}](tasks/{t.id}.md) - {t.status}" + (f", due {t.due}" if t.due else "")
                     for t in tasks] or ["- none"]
            body += ["", "## Recent sessions"]
            for meta, _ in sessions:
                body.append(f"- {str(meta.get('ended', ''))[:16]} {meta.get('title')} - {meta.get('description', '')}")
            if not sessions:
                body.append("- none yet")
            body += ["", "## Sections", "- [profile](profile.md)", "- [change log](log.md)",
                     "- tasks/, sessions/YYYY/MM/, facts/<category>/"]
            okf.write(self.root / "index.md", {
                "type": "Index", "title": "Alfred's memory",
                "description": "Brain session memory: tasks, sessions, facts.", "timestamp": _iso(),
            }, "\n".join(body))
