from datetime import datetime, timedelta

from brain.memory import MemoryStore
from brain.memory import okf


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
