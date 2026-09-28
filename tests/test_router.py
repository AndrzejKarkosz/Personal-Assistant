from pathlib import Path

import pytest

from brain.atlas import BrainMap, MapBuilder
from brain.config import ROOT
from brain.executor import MCPHub
from brain.modules import ModuleRegistry
from brain.router import JevClient, Router


class FakeJev(JevClient):
    def __init__(self, answers):
        super().__init__("key", "http://jev", "typesafe/jev-1.13")
        self.answers = answers
        self.sent = None

    async def ask(self, state, questions):
        self.sent = questions
        return {"answers": self.answers, "usage": {"input_tokens": 300, "output_tokens": 20}}


@pytest.fixture
def brain_map(tmp_path) -> BrainMap:
    empty = tmp_path / "mcp.json"
    empty.write_text('{"mcpServers": {}}')
    topics = tmp_path / "topics"
    topics.mkdir()
    (topics / "spanish.md").write_text("---\ntype: Topic\ntitle: Spanish\ndescription: Learning Spanish\n---\n# Spanish\n",
                                       encoding="utf-8")
    MapBuilder(tmp_path / "map", ModuleRegistry(ROOT / "modules"), MCPHub(empty),
               [{"server": "knowledge-base", "capability": "knowledge.search", "path": str(topics)}]).build()
    return BrainMap(tmp_path / "map")


def test_registry_loads_capabilities_and_skills():
    reg = ModuleRegistry(ROOT / "modules")
    assert {"calendar", "knowledge", "tasks", "bookings", "smalltalk"} <= set(reg.modules)
    assert reg.skill("bookings.restaurant-table").uses[0] == "memory.recall"
    assert reg.capability("calendar.write").confirm
    assert "tasks.manage" in [c.id for c in reg.module_capabilities("calendar")]


def test_map_relations(brain_map):
    # module -> own + borrowed capabilities, capability -> tools, tool -> server
    assert brain_map.capabilities_of(["tasks"]) == ["tasks.manage", "memory.recall"]
    assert brain_map.tools_of(["tasks.manage"]) == ["task_create", "task_list", "task_update"]
    assert brain_map.tools["task_create"]["server"] == "alfred"
    assert brain_map.needs_confirmation("confirm_action") is False     # guarded by the executor itself
    assert "topic:spanish" in brain_map.topics
    g = brain_map.graph()
    rels = {(e["source"], e["rel"], e["target"]) for e in g["edges"]}
    assert ("module:tasks", "has", "cap:tasks.manage") in rels
    assert ("cap:tasks.manage", "includes", "tool:task_create") in rels
    assert ("tool:task_create", "served by", "mcp:alfred") in rels
    assert ("module:calendar", "uses", "cap:tasks.manage") in rels


def test_rebuild_keeps_curation_and_logs_changes(tmp_path, brain_map):
    page = tmp_path / "map" / "capabilities" / "tasks.manage.md"
    text = page.read_text(encoding="utf-8").replace("available:", "examples_extra: [nie zapomnij o fakturze]\navailable:")
    page.write_text(text + "\n## Notes\nKeep reminders short.\n", encoding="utf-8")
    empty = tmp_path / "mcp.json"
    MapBuilder(tmp_path / "map", ModuleRegistry(ROOT / "modules"), MCPHub(empty)).build()
    kept = page.read_text(encoding="utf-8")
    assert "nie zapomnij o fakturze" in kept and "Keep reminders short." in kept
    assert "removed topics/knowledge-base/spanish.md" in (tmp_path / "map" / "log.md").read_text(encoding="utf-8")


async def test_jev_categories_come_from_the_map(settings, brain_map):
    jev = FakeJev({
        "module": {"choice": "bookings", "confidence": 0.9, "probabilities": {"bookings": 0.9, "calendar": 0.1}},
        "capability": {"choice": "bookings.browse",
                       "probabilities": {"bookings.browse": 0.7, "research.web": 0.2, "calendar.read": 0.1}},
        "skill": {"choice": "bookings.restaurant-table"},
        "topic": {"choice": "none"},
        "urgency": {"score": 1.2},
        "acts_on_world": {"noul": 0.95},
        "needs_history": {"noul": 0.1},
    })
    route = await Router(brain_map, jev, settings).classify("zarezerwuj stolik na piątek")
    assert set(jev.sent) == {"module", "capability", "skill", "topic", "urgency", "acts_on_world", "needs_history"}
    assert "calendar.write" in jev.sent["capability"]["criteria"]
    assert "topic:spanish" in jev.sent["topic"]["criteria"]
    assert route.module == "bookings" and route.skill == "bookings.restaurant-table" and route.topic is None
    # top capabilities until 80% coverage + the skill's capabilities + "always" ones
    assert route.capabilities[:2] == ["bookings.browse", "research.web"]
    assert "calendar.write" in route.capabilities and "bookings.confirm" in route.capabilities
    assert "calendar.read" not in route.capabilities


async def test_close_call_loads_second_module(settings, brain_map):
    jev = FakeJev({"module": {"choice": "bookings", "confidence": 0.45,
                              "probabilities": {"bookings": 0.5, "calendar": 0.4, "tasks": 0.1}}})
    route = await Router(brain_map, jev, settings).classify("stolik i wpisz do kalendarza")
    assert route.modules == ["bookings", "calendar"] and not route.clarify


async def test_rules_fallback_without_keys(settings, brain_map):
    route = await Router(brain_map, JevClient(None, "", ""), settings).classify("przypomnij mi jutro żeby zadzwonić")
    assert route.source == "rules" and route.module == "tasks" and route.capabilities == []


async def test_yes_no_keywords(settings, brain_map):
    router = Router(brain_map, JevClient(None, "", ""), settings)
    assert await router.is_yes("tak, dawaj", "?") is True
    assert await router.is_yes("nie, anuluj", "?") is False
    assert await router.is_yes("yes please", "?") is True
