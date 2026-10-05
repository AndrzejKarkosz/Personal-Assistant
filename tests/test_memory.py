from datetime import datetime, timedelta

import pytest

from brain.memory import MemoryStore, Session, SessionManager
from brain import okf


def test_task_lifecycle_is_logged_and_briefed(tmp_path):
    store = MemoryStore(tmp_path)
    due = (datetime.now().astimezone() - timedelta(minutes=5)).isoformat(timespec="seconds")
    task = store.create_task("Zadzwonić do mamy", "niedzielny telefon", due=due)

    assert task.status == "todo"
    assert [t.id for t in store.due_tasks()] == [task.id]

    meta, body = okf.read(tmp_path / "tasks" / f"{task.id}.md")
    assert meta["type"] == "Task" and meta["status"] == "todo"

    store.update_task(task.id, status="done", note="zadzwoniłem")
    assert store.get_task(task.id).status == "done"
    assert store.list_tasks("open") == []

    log = (tmp_path / "log.md").read_text(encoding="utf-8")
    assert "task.created" in log and "status todo -> done" in log
    assert "Open tasks: none" in store.briefing()


def test_session_page_and_changes_since(tmp_path):
    store = MemoryStore(tmp_path)
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    store.write_session("s-1", now, now, {"title": "Kolacja", "summary": "Zarezerwowano stolik.",
                                          "open_threads": ["potwierdzenie SMS"], "done": ["rezerwacja"]},
                        {"input": 10, "output": 5}, 4)
    store.create_task("Sprawdź SMS z restauracji")

    brief = store.briefing()
    assert "Kolacja" in brief and "potwierdzenie SMS" in brief
    assert "Changed since the last session" in brief and "Sprawdź SMS" in brief
    assert store.search("stolik")[0]["type"] == "Session"
    assert "Kolacja" in (tmp_path / "index.md").read_text(encoding="utf-8")


def test_facts_append_and_read_is_sandboxed(tmp_path):
    store = MemoryStore(tmp_path)
    store.remember("preferences", "Jedzenie", "nie je mięsa")
    store.remember("preferences", "Jedzenie", "lubi kuchnię włoską")
    text = store.read("facts/preferences/jedzenie.md")
    assert "nie je mięsa" in text and "włoską" in text
    try:
        store.read("../../etc/passwd")
    except ValueError:
        pass
    else:
        raise AssertionError("path traversal not blocked")


def test_okf_roundtrip_and_slugs():
    meta, body = okf.parse(okf.dump({"type": "Fact", "tags": ["a"]}, "# Zażółć\n"))
    assert meta == {"type": "Fact", "tags": ["a"]} and body == "# Zażółć\n"
    assert okf.parse("no frontmatter") == ({}, "no frontmatter")
    assert okf.slugify("Łódź — Kraków!") == "lodz-krakow" and okf.slugify("???") == "item"


def test_only_four_statuses(tmp_path):
    store = MemoryStore(tmp_path)
    task = store.create_task("Stary", status="in_progress")
    assert store.get_task(task.id).status == "in_progress" and store.list_tasks("open")[0].id == task.id
    for bad in ("waiting", "bogus"):
        with pytest.raises(ValueError):
            store.create_task("X", status=bad)


def test_task_errors_ordering_and_filters(tmp_path):
    store = MemoryStore(tmp_path)
    with pytest.raises(KeyError):
        store.update_task("nope", status="done")
    later = store.create_task("B", due="2030-01-02T10:00:00+01:00")
    sooner = store.create_task("A", due="2030-01-01T10:00:00+01:00", priority="low")
    undated = store.create_task("A", priority="high")
    assert undated.id == f"{sooner.id}-2"
    assert [t.id for t in store.list_tasks()] == [sooner.id, later.id, undated.id]

    with pytest.raises(ValueError):
        store.update_task(later.id, status="bogus")
    assert store.update_task(later.id, status="todo").history == later.history
    store.update_task(later.id, schedule="0 8 * * 1-5", note="co tydzień")
    assert store.get_task(later.id).schedule == "0 8 * * 1-5"
    tagged = store.create_task("C", category="Dom")
    assert store.get_task(tagged.id).category == "Dom"
    store.update_task(tagged.id, category="")
    assert store.get_task(tagged.id).category is None
    store.update_task(tagged.id, status="done")
    store.update_task(later.id, status="cancelled")
    assert [t.id for t in store.list_tasks("cancelled")] == [later.id] and len(store.list_tasks("all")) == 4
    assert store.due_tasks() == [] and store.get_task("missing") is None


def test_history_is_plain_alternating_turns():
    s = Session()
    for role, text in [("assistant", "hej"), ("user", "a"), ("user", "b"), ("assistant", "c")]:
        s.add(role, text)
    assert s.history_messages() == [{"role": "user", "content": "a\nb"}, {"role": "assistant", "content": "c"}]
    s.add_usage({"input": 5, "note": "not a number"})
    assert s.usage["input"] == 5 and "note" not in s.usage


async def test_idle_session_is_saved_even_when_the_summary_fails(tmp_path, settings):   # Claude is offline
    store = MemoryStore(tmp_path)
    manager = SessionManager(store, settings)
    await manager.close()
    first = await manager.get()
    assert await manager.get() is first
    first.add("user", "Zarezerwuj stolik")
    first.add("assistant", "Gotowe")
    first.last_activity -= timedelta(hours=1)

    await manager.close_if_idle()
    assert manager.current is None
    meta, _ = store.recent_sessions(1)[0]
    assert meta["title"] == "Zarezerwuj stolik" and meta["turns"] == 2
    assert await manager.get() is not first


def test_undone_tasks_move_to_the_next_day_same_hour(tmp_path):
    from datetime import date
    store = MemoryStore(tmp_path)
    late = store.create_task("Fryzjer", due="2026-09-29T10:00:00+02:00", category="Reszta")
    done = store.create_task("Trening", due="2026-09-29T18:00:00+02:00")
    store.update_task(done.id, status="done")
    weekly = store.create_task("Brief", due="2026-09-29T08:00:00+02:00", schedule="0 8 * * 1")
    later = store.create_task("Dentysta", due="2026-11-03T09:00:00+01:00")

    moved = store.roll_over(date(2026, 10, 30))                 # past the clock change on 25.10
    assert [t.id for t in moved] == [late.id]
    assert store.get_task(late.id).due == "2026-10-30T10:00:00+01:00"     # same local hour, winter offset
    assert "niezrobione 2026-09-29 - przeniesione na 2026-10-30" in store.get_task(late.id).history[-1]
    assert store.get_task(done.id).due.startswith("2026-09-29")            # done, cron and future tasks stay
    assert store.get_task(weekly.id).due.startswith("2026-09-29") and store.get_task(later.id).due.startswith("2026-11-03")
    assert store.roll_over(date(2026, 10, 30)) == []                       # once per day


def test_goals_and_resolutions_are_saved_and_briefed(tmp_path):
    store = MemoryStore(tmp_path)
    assert store.goals() == {"goals": "", "resolutions": ""} and store.goals_text() == ""
    store.save_goals("- Wrócić do biegania\n- Skończyć SmartMeet MVP", "- Bez telefonu po 22")
    assert store.goals() == {"goals": "- Wrócić do biegania\n- Skończyć SmartMeet MVP", "resolutions": "- Bez telefonu po 22"}
    assert "His goals:\n- Wrócić do biegania" in store.briefing() and "His resolutions:" in store.briefing()
    task = store.create_task("Fizjo", goal="żeby wrócić do biegania")
    assert store.get_task(task.id).goal == "żeby wrócić do biegania"
    assert store.update_task(task.id, goal="").goal is None


def test_alfreds_board(tmp_path):
    from brain.memory import MemoryStore
    store = MemoryStore(tmp_path)
    assert store.get_task(store.create_task("Przypomnienie o taskach na dzisiaj").id).alfred is True   # always
    mine = store.create_task("Fizjo")
    assert store.update_task(mine.id, alfred=True).alfred is True and "Alfred's board" in store.get_task(mine.id).history[-1]
