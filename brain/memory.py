"""Alfred's own diary in data/memory/ (plain Markdown files you can read):

    index.md                  overview, rewritten on every change
    log.md                    append-only list of every change (task.created, fact.created, session.closed ...)
    profile.md                who Alfred works for
    tasks/<id>.md             one file per task / reminder
    sessions/YYYY/MM/<id>.md  summary of each conversation
    facts/<category>/*.md     people, places, preferences, projects

MemoryStore reads and writes these files. Session is the conversation going on right now; SessionManager closes it
after 15 idle minutes and writes its summary.
"""
from __future__ import annotations

import re
import threading
from collections import Counter
from dataclasses import dataclass, field, fields
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from . import llm, okf
from .events import new_id, now_iso

TASK_STATUSES = ("todo", "in_progress", "done", "cancelled")   # do zrobienia, w toku, zrobione, anulowane
OPEN_STATUSES = ("todo", "in_progress")
FACT_CATEGORIES = ("people", "places", "preferences", "projects", "other")


def parse_time(value: Any) -> datetime | None:
    """ISO text -> datetime with a timezone (times without one are taken as local)."""
    try:
        dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value)) if value else None
    except ValueError:
        return None
    return dt if dt is None or dt.tzinfo else dt.astimezone()


@dataclass
class Task:
    id: str
    title: str
    status: str = "todo"
    description: str = ""
    due: str | None = None          # one-off moment, ISO 8601
    schedule: str | None = None     # recurring, cron ("0 8 * * 1-5")
    module: str | None = None       # module that handles it when it fires
    priority: str = "normal"
    category: str | None = None     # the user's own grouping, e.g. "Dom"
    goal: str | None = None         # how it brings him closer to one of his goals (goals.md), in his words
    alfred: bool = False            # on Alfred's board: reminders and things Alfred does himself at a time
    created: str = field(default_factory=now_iso)
    updated: str = field(default_factory=now_iso)
    history: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.alfred = self.alfred or self.title.casefold().startswith("przypomn")   # reminders are always Alfred's

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    def to_dict(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


class MemoryStore:
    def __init__(self, root: Path):
        self.root = root
        self._lock = threading.RLock()
        for sub in ("tasks", "sessions", *(f"facts/{c}" for c in FACT_CATEGORIES)):
            (root / sub).mkdir(parents=True, exist_ok=True)
        if not (root / "profile.md").exists():
            okf.write(root / "profile.md", {"type": "Profile", "title": "Andrzej", "timestamp": now_iso(),
                                            "description": "Who I serve and how he likes things done."},
                      "# Profile\n\n## Preferences\n\n## Facts\n")
        if not (root / "log.md").exists():
            okf.write(root / "log.md", {"type": "Log", "title": "Brain change log",
                                        "description": "Append-only record of everything Alfred changed."},
                      "# Change log\n")
        if not (root / "index.md").exists():
            self.rebuild_index()

    # ---- change log -------------------------------------------------------------------------------------------

    def log(self, action: str, detail: str, session_id: str | None = None) -> None:
        line = f"- {now_iso()} **{action}** {detail}" + (f" _(session {session_id})_" if session_id else "")
        with self._lock, (self.root / "log.md").open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def log_since(self, since: datetime | None, limit: int = 30) -> list[str]:
        lines = [l for l in (self.root / "log.md").read_text(encoding="utf-8").splitlines() if l.startswith("- ")]
        if since:
            lines = [l for l in lines if (t := parse_time(l.split()[1])) and t >= since]
        return lines[-limit:]

    # ---- tasks ------------------------------------------------------------------------------------------------

    def _task_file(self, task_id: str) -> Path:
        return self.root / "tasks" / f"{task_id}.md"

    def _save_task(self, t: Task) -> None:
        meta = {"type": "Task", "title": t.title, "description": t.description[:200], "status": t.status,
                "priority": t.priority, "due": t.due, "schedule": t.schedule, "module": t.module,
                "category": t.category, "goal": t.goal, "alfred": t.alfred, "created": t.created, "timestamp": t.updated,
                "tags": ["task", t.status] + [x for x in (t.module, t.category) if x]}
        history = "\n".join(f"- {h}" for h in t.history)
        okf.write(self._task_file(t.id), meta, f"# {t.title}\n\n{t.description}\n\n## History\n{history}")

    def get_task(self, task_id: str) -> Task | None:
        path = self._task_file(task_id)
        if not path.exists():
            return None
        meta, body = okf.read(path)
        text, _, history = body.partition("## History")
        return Task(id=path.stem, title=meta.get("title", path.stem), status=meta.get("status", "todo"),
                    description=re.sub(r"^# .*\n", "", text).strip(), due=meta.get("due"),
                    schedule=meta.get("schedule"), module=meta.get("module"), priority=meta.get("priority", "normal"),
                    category=meta.get("category"), goal=meta.get("goal"), alfred=bool(meta.get("alfred")), created=str(meta.get("created", "")),
                    updated=str(meta.get("timestamp", "")),
                    history=[l[2:] for l in history.splitlines() if l.startswith("- ")])

    def list_tasks(self, status: str | None = "open") -> list[Task]:
        """status: "open" (todo/in_progress), "all", or one status. Soonest due first, then priority."""
        tasks = [self.get_task(p.stem) for p in sorted((self.root / "tasks").glob("*.md"))]
        if status == "open":
            tasks = [t for t in tasks if t.is_open]
        elif status and status != "all":
            tasks = [t for t in tasks if t.status == status]
        never = datetime.now().astimezone() + timedelta(days=3650)
        rank = {"high": 0, "normal": 1, "low": 2}
        return sorted(tasks, key=lambda t: (parse_time(t.due) or never, rank.get(t.priority, 1)))

    def due_tasks(self, within: timedelta = timedelta(0)) -> list[Task]:
        """Open tasks due by now (+ `within`, for reminders ahead of time)."""
        limit = datetime.now().astimezone() + within
        return [t for t in self.list_tasks("open") if (due := parse_time(t.due)) and due <= limit]

    def create_task(self, title: str, description: str = "", due: str | None = None, schedule: str | None = None,
                    module: str | None = None, priority: str = "normal", session_id: str | None = None,
                    category: str | None = None, status: str = "todo", goal: str | None = None,
                    alfred: bool = False) -> Task:
        if status not in TASK_STATUSES:
            raise ValueError(f"status must be one of {TASK_STATUSES}")
        with self._lock:
            task_id = base = f"{datetime.now():%Y%m%d}-{okf.slugify(title, 32)}"
            n = 2
            while self._task_file(task_id).exists():
                task_id, n = f"{base}-{n}", n + 1
            task = Task(task_id, title, description=description, due=due, schedule=schedule, module=module,
                        priority=priority, category=category or None, status=status, goal=goal or None,
                        alfred=alfred)
            task.history.append(f"{task.created} created")
            self._save_task(task)
            self.log("task.created", f"[{title}](tasks/{task_id}.md)" + (f" due {due}" if due else ""), session_id)
            self.rebuild_index()
            return task

    def update_task(self, task_id: str, status: str | None = None, note: str | None = None, due: str | None = None,
                    title: str | None = None, schedule: str | None = None, session_id: str | None = None,
                    category: str | None = None, goal: str | None = None, alfred: bool | None = None) -> Task:
        """Only the given fields change. An empty string clears due / schedule / category / goal."""
        with self._lock:
            task = self.get_task(task_id)
            if task is None:
                raise KeyError(f"No task {task_id}")
            if status and status not in TASK_STATUSES:
                raise ValueError(f"status must be one of {TASK_STATUSES}")
            changes = []
            if status and status != task.status:
                changes.append(f"status {task.status} -> {status}")
                task.status = status
            for name, value in (("due", due), ("schedule", schedule), ("category", category), ("goal", goal)):
                if value is not None and (value or None) != getattr(task, name):
                    changes.append(f"{name} -> {value or 'none'}")
                    setattr(task, name, value or None)
            if alfred is not None and alfred != task.alfred:
                changes.append("moved to Alfred's board" if alfred else "moved to the user's board")
                task.alfred = alfred
            if title and title != task.title:
                changes.append(f"renamed to {title}")
                task.title = title
            if note:
                changes.append(f"note: {note}")
            if not changes:
                return task
            task.updated = now_iso()
            task.history.append(f"{task.updated} " + "; ".join(changes))
            self._save_task(task)
            self.log("task.updated", f"[{task.title}](tasks/{task_id}.md): " + "; ".join(changes), session_id)
            self.rebuild_index()
            return task

    def roll_over(self, today: date | None = None) -> list[Task]:
        """Not done by the end of its day -> moved to today, same hour. Only open one-off tasks (a cron task
        comes back by itself). Returns the moved tasks."""
        today = today or datetime.now().astimezone().date()
        moved = []
        for t in self.list_tasks("open"):
            due = parse_time(t.due)
            if due and not t.schedule and (old := due.astimezone()).date() < today:
                new = datetime.combine(today, old.time()).astimezone()     # local hour, right offset after DST
                moved.append(self.update_task(t.id, due=new.isoformat(timespec="seconds"), session_id="rollover",
                                              note=f"niezrobione {old:%Y-%m-%d} - przeniesione na {today:%Y-%m-%d}"))
        return moved

    # ---- summary of a period ----------------------------------------------------------------------------------

    def summary(self, start: datetime, end: datetime) -> dict[str, Any]:
        """What happened between start and end, read from the tasks' history and the saved sessions."""
        inside = lambda when: when is not None and start <= when < end
        stamp = lambda line: parse_time(line.split(" ", 1)[0])
        tasks = self.list_tasks("all")
        changed_to = lambda status: [t for t in tasks if any(inside(stamp(h)) and f"-> {status}" in h for h in t.history)]
        done = changed_to("done")
        cost = {"cost_usd": 0.0, "jev_usd": 0.0, "elevenlabs_usd": 0.0, "input": 0, "output": 0, "cache_read": 0,
                "cache_write": 0, "jev": 0, "tts_chars": 0, "stt_s": 0.0}
        sessions = [m for m, _ in (okf.read(p) for p in (self.root / "sessions").rglob("*.md"))
                    if inside(parse_time(m.get("ended")))]
        for m in sessions:
            for k, v in (m.get("tokens") or {}).items():
                if k in cost and isinstance(v, (int, float)):
                    cost[k] += v
        return {
            "tasks": {"created": sum(inside(parse_time(t.created)) for t in tasks), "done": len(done),
                      "cancelled": len(changed_to("cancelled")),
                      "planned": sum(inside(parse_time(t.due)) for t in tasks),
                      "rolled": sum(inside(stamp(h)) and "przeniesione na" in h for t in tasks for h in t.history),
                      "done_by_category": dict(Counter(t.category or "bez kategorii" for t in done).most_common()),
                      "done_titles": [t.title for t in done][:8]},
            "sessions": {"count": len(sessions), "turns": sum(int(m.get("turns") or 0) for m in sessions)},
            "cost": cost,
        }

    # ---- goals and resolutions --------------------------------------------------------------------------------

    def goals(self) -> dict[str, str]:
        """{"goals": ..., "resolutions": ...} - what he wrote in the Cele tab (goals.md), free Markdown each."""
        path = self.root / "goals.md"
        body = okf.read(path)[1] if path.exists() else ""
        parts = re.split(r"^## (Cele|Postanowienia)\s*$", body, flags=re.M)
        found = dict(zip(parts[1::2], (p.strip() for p in parts[2::2])))
        return {"goals": found.get("Cele", ""), "resolutions": found.get("Postanowienia", "")}

    def goals_text(self, limit: int = 1500) -> str:
        """Goals + resolutions for Claude's prompt ("" when he has written none)."""
        g = self.goals()
        parts = [f"His goals:\n{g['goals']}" if g["goals"] else "", f"His resolutions:\n{g['resolutions']}"
                 if g["resolutions"] else ""]
        return "\n\n".join(p for p in parts if p)[:limit]

    def save_goals(self, goals: str, resolutions: str) -> None:
        okf.write(self.root / "goals.md", {"type": "Goals", "title": "Cele i postanowienia", "timestamp": now_iso(),
                                           "description": "What he is working towards - tasks should serve it."},
                  f"# Cele i postanowienia\n\n## Cele\n\n{goals.strip()}\n\n## Postanowienia\n\n{resolutions.strip()}")
        self.log("goals.updated", "[Cele i postanowienia](goals.md)")

    def products(self) -> list[dict[str, Any]]:
        """Products he uses regularly (the Produkty tab, products.md): [{name, url, note, grams}]."""
        path = self.root / "products.md"
        return (okf.read(path)[0].get("items") or []) if path.exists() else []

    def save_products(self, items: list[dict[str, Any]]) -> None:
        """The whole list at once; the body lists them too, so memory_search finds a product by name or note."""
        lines = "\n".join(f"- [{i['name']}]({i['url']})" + (f" - porcja {i['grams']:g} g" if i.get("grams") else "")
                          + (f" - {i['note']}" if i.get("note") else "") for i in items)
        okf.write(self.root / "products.md", {"type": "Products", "title": "Stałe produkty", "timestamp": now_iso(),
                                              "description": "Products he buys or uses regularly, with links to "
                                                             "reorder them.", "items": items},
                  f"# Stałe produkty\n\n{lines}")
        self.log("products.updated", "[Stałe produkty](products.md)")

    # ---- facts and sessions -----------------------------------------------------------------------------------

    def remember(self, category: str, title: str, content: str, session_id: str | None = None) -> Path:
        """Save a fact about the user. The same title again adds a line to the same page."""
        category = category if category in FACT_CATEGORIES else "other"
        path = self.root / "facts" / category / f"{okf.slugify(title)}.md"
        with self._lock:
            existed = path.exists()
            if existed:
                meta, body = okf.read(path)
                okf.write(path, meta | {"timestamp": now_iso()}, body.rstrip() + f"\n\n- {now_iso()}: {content}")
            else:
                okf.write(path, {"type": "Fact", "title": title, "description": content[:200], "tags": [category],
                                 "timestamp": now_iso()}, f"# {title}\n\n- {now_iso()}: {content}")
            self.log("fact.updated" if existed else "fact.created",
                     f"[{title}]({path.relative_to(self.root).as_posix()})", session_id)
        return path

    def write_session(self, session_id: str, started: str, ended: str, summary: dict[str, Any],
                      usage: dict[str, Any], turns: int) -> Path:
        start = parse_time(started) or datetime.now().astimezone()
        path = self.root / "sessions" / f"{start:%Y}" / f"{start:%m}" / f"{session_id}.md"
        title = summary.get("title") or f"Session {start:%Y-%m-%d %H:%M}"
        meta = {"type": "Session", "title": title, "description": summary.get("summary", "")[:240],
                "tags": summary.get("domains", []), "timestamp": ended, "started": started, "ended": ended,
                "turns": turns, "tokens": usage, "open_threads": summary.get("open_threads", [])}
        sections = [f"# {title}", "## Summary", summary.get("summary", "")]
        for key, heading in (("done", "Done"), ("changed", "Changed"), ("open_threads", "Open threads"),
                             ("facts", "Facts learned")):
            if summary.get(key):
                sections += [f"## {heading}", "\n".join(f"- {item}" for item in summary[key])]
        okf.write(path, meta, "\n\n".join(sections))
        self.log("session.closed", f"[{title}]({path.relative_to(self.root).as_posix()})", session_id)
        self.rebuild_index()
        return path

    def recent_sessions(self, n: int = 3) -> list[tuple[dict[str, Any], str]]:
        pages = [okf.read(p) for p in (self.root / "sessions").rglob("*.md")]
        return sorted(pages, key=lambda page: str(page[0].get("ended", "")), reverse=True)[:n]

    # ---- reading ----------------------------------------------------------------------------------------------

    def search(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        """Plain keyword search: the more often the words appear on a page, the higher it ranks."""
        words = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 2]
        hits = []
        for path in self.root.rglob("*.md"):
            if path.name in ("log.md", "index.md"):
                continue
            meta, body = okf.read(path)
            text = (" ".join(map(str, meta.values())) + " " + body).lower()
            if score := sum(text.count(w) for w in words):
                hits.append({"path": path.relative_to(self.root).as_posix(), "type": meta.get("type"),
                             "title": meta.get("title"), "description": meta.get("description"),
                             "timestamp": str(meta.get("timestamp", "")), "score": score})
        return sorted(hits, key=lambda h: (h["score"], h["timestamp"]), reverse=True)[:limit]

    def read(self, relative_path: str) -> str:
        return okf.read_inside(self.root, relative_path)

    def briefing(self, recall_sessions: int = 3) -> str:
        """The short note Alfred gets at the start of every session: open tasks, recent sessions, what changed."""
        now = datetime.now().astimezone()
        out = [f"Now: {now:%A %Y-%m-%d %H:%M %Z}"]
        profile = okf.read(self.root / "profile.md")[1].strip()
        if len(profile) > 40:
            out.append("Profile:\n" + profile[:1200])
        if goals := self.goals_text():
            out.append(goals)
        lines = []
        for t in self.list_tasks("open")[:15]:
            overdue = " OVERDUE" if (due := parse_time(t.due)) and due < now else ""
            lines.append(f"- [{t.id}] {t.title} ({t.status}{', due ' + t.due if t.due else ''}"
                         f"{', every ' + t.schedule if t.schedule else ''}){overdue}")
        out.append("Open tasks:\n" + "\n".join(lines) if lines else "Open tasks: none")
        sessions = self.recent_sessions(recall_sessions)
        if sessions:
            out.append("Recent sessions:\n" + "\n".join(
                f"- {str(m.get('ended', ''))[:16]} {m.get('title')}: {m.get('description', '')}"
                + (f" | open: {'; '.join(m['open_threads'])}" if m.get("open_threads") else "") for m, _ in sessions))
            changes = [l for l in self.log_since(parse_time(sessions[0][0].get("ended"))) if "session.closed" not in l]
            if changes:
                out.append("Changed since the last session:\n" + "\n".join(changes))
        return "\n\n".join(out)

    def rebuild_index(self) -> None:
        with self._lock:
            tasks = [f"- [{t.title}](tasks/{t.id}.md) - {t.status}" + (f", due {t.due}" if t.due else "")
                     for t in self.list_tasks("open")]
            sessions = [f"- {str(m.get('ended', ''))[:16]} {m.get('title')} - {m.get('description', '')}"
                        for m, _ in self.recent_sessions(10)]
            body = ["# Alfred's memory", "", "Start here, then open a task, session or fact page.", "",
                    "## Open tasks", *(tasks or ["- none"]), "", "## Recent sessions", *(sessions or ["- none yet"]),
                    "", "## Sections", "- [profile](profile.md)", "- [goals and resolutions](goals.md)",
                    "- [change log](log.md)",
                    "- tasks/, sessions/YYYY/MM/, facts/<category>/"]
            okf.write(self.root / "index.md", {"type": "Index", "title": "Alfred's memory", "timestamp": now_iso(),
                                               "description": "Brain session memory: tasks, sessions, facts."},
                      "\n".join(body))


# ---- the conversation going on right now -------------------------------------------------------------------------

@dataclass
class Turn:
    role: str                       # "user" or "assistant"
    text: str
    module: str | None = None
    ts: str = field(default_factory=now_iso)


@dataclass
class Session:
    id: str = field(default_factory=lambda: new_id(f"s-{datetime.now():%Y%m%d-%H%M}-"))
    started: str = field(default_factory=now_iso)
    last_activity: datetime = field(default_factory=datetime.now)
    turns: list[Turn] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)     # what Alfred changed, for the summary
    usage: dict[str, float] = field(default_factory=lambda: {"input": 0, "output": 0, "cache_read": 0, "jev": 0})
    briefing: str = ""
    language: str = "pl"

    def add(self, role: str, text: str, module: str | None = None) -> None:
        self.turns.append(Turn(role, text, module))
        self.last_activity = datetime.now()

    def add_usage(self, usage: dict[str, Any]) -> None:
        for key, value in usage.items():
            if isinstance(value, (int, float)):
                self.usage[key] = self.usage.get(key, 0) + value

    def recent_text(self, n: int = 6) -> str:
        return "\n".join(f"{t.role}: {t.text}" for t in self.turns[-n:])

    def history_messages(self, n: int = 8) -> list[dict[str, str]]:
        """The last turns as user/assistant messages: same-role turns merged, always starting with the user."""
        messages: list[dict[str, str]] = []
        for turn in self.turns[-n:]:
            if messages and messages[-1]["role"] == turn.role:
                messages[-1]["content"] += "\n" + turn.text
            else:
                messages.append({"role": turn.role, "content": turn.text})
        while messages and messages[0]["role"] != "user":
            messages.pop(0)
        return messages


SUMMARY_PROMPT = """Write the memory record of this assistant session. Be terse; the record is read by the assistant \
at the start of future sessions to know what is done and what to pick up.
- summary: 1-2 sentences
- done: completed actions
- changed: things created/updated
- open_threads: unfinished items the assistant should pick up later
- facts: durable facts about the user worth remembering (people, places, preferences, projects); skip trivia

Actions taken:
{actions}

Transcript:
{transcript}"""

_strings = {"type": "array", "items": {"type": "string"}}
SUMMARY_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["title", "summary", "domains", "done", "changed", "open_threads", "facts"],
    "properties": {
        "title": {"type": "string"}, "summary": {"type": "string"}, "domains": _strings, "done": _strings,
        "changed": _strings, "open_threads": _strings,
        "facts": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["category", "title", "content"],
            "properties": {"category": {"type": "string", "enum": list(FACT_CATEGORIES)},
                           "title": {"type": "string"}, "content": {"type": "string"}}}},
    },
}


class SessionManager:
    def __init__(self, store: MemoryStore, settings, bus=None):
        self.store = store
        self.settings = settings
        self.bus = bus
        self.current: Session | None = None

    def _idle_too_long(self) -> bool:
        limit = timedelta(minutes=float(self.settings.get("memory.session_idle_minutes", 15)))
        return self.current is not None and datetime.now() - self.current.last_activity > limit

    async def get(self) -> Session:
        """The current session; a new one (with a fresh briefing) if there is none or the old one went idle."""
        await self.close_if_idle()
        if self.current is None:
            self.current = Session(briefing=self.store.briefing(int(self.settings.get("memory.recall_sessions", 3))))
            if self.bus:
                self.bus.emit("session_started", "memory", session_id=self.current.id, briefing=self.current.briefing)
        return self.current

    async def close_if_idle(self) -> None:
        if self._idle_too_long():
            await self.close()

    async def close(self) -> None:
        """Summarise the session (light model), save the facts it learned and write the session page."""
        session, self.current = self.current, None
        if session is None or not session.turns:
            return
        transcript = "\n".join(f"[{t.ts[11:16]}] {t.role}{'/' + t.module if t.module else ''}: {t.text}"
                               for t in session.turns)
        try:
            summary, _ = await llm.ask_json(self.settings, SUMMARY_PROMPT.format(
                actions="\n".join(f"- {a}" for a in session.actions) or "- none", transcript=transcript),
                SUMMARY_SCHEMA)
        except Exception:   # no Claude right now - keep a rough record rather than nothing
            summary = {"title": session.turns[0].text[:60], "summary": transcript[:400], "done": session.actions}
        for fact in summary.get("facts", []):
            self.store.remember(fact["category"], fact["title"], fact["content"], session.id)
        path = self.store.write_session(session.id, session.started, now_iso(), summary, session.usage,
                                        len(session.turns))
        if self.bus:
            self.bus.emit("session_closed", "memory", session_id=session.id, path=str(path),
                          title=summary.get("title"), summary=summary.get("summary"))
