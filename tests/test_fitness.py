from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from fastapi.testclient import TestClient

from brain import fitness
from brain.executor import ExecResult

RACE = date(2027, 6, 13)
CFG = {"race": {"name": "Gdynia", "date": RACE.isoformat(), "distance": "half"}, "easy_hr_max": 145,
       "weekly": {"swim": {"sessions": 2, "hours": 1.0}, "run": {"sessions": 2, "hours": 2.0}},
       "busy_week": {"meeting_hours": 10, "work_tasks_due": 5}}


def test_season_phases_count_back_from_the_race():
    before = lambda days: fitness.phase(RACE - timedelta(days=days), RACE, "half")
    assert before(0) == before(14) == "taper"                       # 14-day taper for a half
    assert before(15) == before(35) == "peak"                       # 3 weeks of peak
    assert before(36) == "recovery"                                 # 3:1 - the lighter week before the peak
    assert before(43) == before(57) == "build"
    assert before(64) == "recovery"
    assert before(99) == "base"
    assert fitness.phase(RACE + timedelta(days=3), RACE) == "recovery"
    assert fitness.phase(RACE + timedelta(days=30), RACE) == fitness.phase(RACE, None) == "base"


def test_week_realisation_from_strava():
    today = date(2026, 10, 7)                                       # Wednesday; the week starts on Monday 5.10
    acts = [{"sport": "swim", "start_date_local": "2026-10-05T07:00:00Z", "moving_time": 1800, "average_heartrate": 130},
            {"sport": "run", "start_date_local": "2026-10-06T18:00:00Z", "moving_time": 3600, "average_heartrate": 160},
            {"sport": "other", "start_date_local": "2026-10-06T20:00:00Z", "moving_time": 1800},
            {"sport": "run", "start_date_local": "2026-09-30T18:00:00Z", "moving_time": 3600}]   # last week
    r = fitness.report(acts, CFG, today, weeks=2)
    this, last = r["weeks"]
    assert this["start"] == "2026-10-05" and this["phase"] == "base" and this["volume"] == 0.85
    assert this["sports"]["swim"] == {"target_h": 0.8, "target_sessions": 2, "done_h": 0.5, "done_sessions": 1}
    assert this["target_h"] == 2.5 and this["done_h"] == 1.5 and this["other_h"] == 0.5 and this["pct"] == 60
    assert this["easy_share"] == 0.33                               # 30 easy minutes of 90 with heart rate
    assert last["done_h"] == 1.0 and last["easy_share"] is None
    assert len(r["activities"]) == 4 and r["activities"][0]["sport"] == "other"
    assert r["race"]["days_to"] == (RACE - today).days


def test_a_heavy_work_week_means_less_training():
    meeting = lambda h: {"start": {"dateTime": "2026-10-05T09:00:00+02:00"},
                         "end": {"dateTime": f"2026-10-05T{9 + h:02d}:00:00+02:00"}}
    calm = fitness.work_load([meeting(2), {"start": {"date": "2026-10-06"}, "end": {"date": "2026-10-07"}}], 1, CFG)
    assert calm == {"meeting_h": 2.0, "work_tasks_due": 1, "busy": False, "advice": None}
    assert fitness.work_load([meeting(6), meeting(5)], 0, CFG)["busy"]
    assert fitness.work_load([], 5, CFG)["advice"].startswith("Ciężki tydzień")


def test_training_tab_without_strava_or_nutrition(make_brain, monkeypatch):
    from brain import app as server

    brain, _ = make_brain()
    monkeypatch.setattr(server, "brain", brain)
    client = TestClient(server.app)
    t = client.get("/api/training").json()
    assert t["strava"]["status"] == "error" and "strava" in t["strava"]["error"]
    assert t["work"]["calendar"] == "missing" and t["steps"]["goal"] == 10000 and len(t["steps"]["days"]) == 7
    assert len(t["weeks"]) == 8 and t["weeks"][0]["sports"]["bike"]["done_h"] == 0
    assert [s["phase"] for s in t["timeline"]][-1] == "taper"
    diet = client.get("/api/diet").json()
    assert diet["status"] == "missing" and diet["log"] == []

    plan = {"race": {"name": "Gdynia 70.3", "date": "2027-06-13", "distance": "half"}, "easy_hr_max": 140,
            "weekly": {"swim": {"sessions": 2, "hours": 1}, "bike": {"sessions": 2, "hours": 2.5},
                       "run": {"sessions": 2, "hours": 1.5}}}
    saved = client.put("/api/training/plan", json=plan).json()
    assert saved["race"]["name"] == "Gdynia 70.3" and saved["plan"]["easy_hr_max"] == 140
    assert brain.settings.get("training.weekly.bike.hours") == 2.5
    assert client.put("/api/training/plan", json=plan | {"race": {"distance": "marathon"}}).status_code == 422


async def test_jev_decides_the_meal_type(make_brain):
    brain, _ = make_brain()
    asked = {}

    async def classify_meal(request, meal, now):
        asked.update(request=request, meal=meal)
        return "breakfast"
    brain.executor.classify_meal = classify_meal
    args = {"description": "owsianka z bananem", "meal_type": "snack", "calories": 450}
    await brain.executor._jev_meal(args, ExecResult(text="", model="m", request="zjadłem owsiankę"), SimpleNamespace(id="s"), "r")
    assert args["meal_type"] == "breakfast" and asked == {"request": "zjadłem owsiankę", "meal": "owsianka z bananem"}

    async def jev_down(*a):
        raise RuntimeError("no Jev")
    brain.executor.classify_meal = jev_down
    args["meal_type"] = "lunch"
    await brain.executor._jev_meal(args, ExecResult(text="", model="m", request="obiad"), SimpleNamespace(id="s"), "r")
    assert args["meal_type"] == "lunch"                             # Claude's own value stays


def test_workout_calories():
    assert fitness.burned({"sport": "bike", "kilojoules": 812.4}, None) == (812, "moc")
    assert fitness.burned({"sport": "run", "distance": 10000, "moving_time": 3000}, 80) == (800, "dystans")
    assert fitness.burned({"sport": "swim", "moving_time": 3600, "average_heartrate": 130}, 80) == (480, "MET")
    assert fitness.burned({"sport": "swim", "moving_time": 3600, "average_heartrate": 160}, 80) == (784, "MET")
    assert fitness.burned({"sport": "swim", "moving_time": 3600}, None) == (None, "")


def test_a_training_day_raises_the_goals():
    progress = {"date": "2026-10-04", "meal_count": 2, "weight": {"current": 84, "target": 78, "unit": "kg"},
                "goals": {"calories": 2100, "protein_g": 160, "carbs_g": 220, "fat_g": 70},
                "totals": {"calories": 900.4, "protein_g": 60, "carbs_g": 100, "fat_g": 30, "fiber_g": 12}}
    b = fitness.day_balance(progress, 500)
    rows = {r["key"]: r for r in b["rows"]}
    assert b["extra_kcal"] == 300 and rows["calories"] == {"key": "calories", "label": "Kalorie", "unit": "kcal",
                                                           "eaten": 900, "goal": 2400, "base_goal": 2100}
    assert rows["carbs_g"]["goal"] == 220 + 52 and rows["protein_g"]["goal"] == 160 and rows["fiber_g"]["goal"] is None
    assert fitness.day_balance({"goals": None, "totals": {}}, 500)["extra_kcal"] == 0


def test_season_timeline():
    today = date(2026, 10, 4)
    parts = fitness.timeline(date(2027, 9, 2), "half", today)
    assert [p["phase"] for p in parts] == ["base", "build", "peak", "taper"]
    assert parts[0]["start"] == "2026-10-04" and [p["days"] for p in parts[1:]] == [56, 21, 14]
    assert sum(p["days"] for p in parts) == (date(2027, 9, 2) - today).days
    assert fitness.timeline(date(2026, 10, 20), "half", today)[0]["phase"] == "peak"
    assert fitness.timeline(None, "half", today) == []


async def test_steps_are_logged_against_the_goal(make_brain):
    brain, _ = make_brain()
    log = brain.executor.handlers["steps_log"]
    out = await log({"steps": 8500}, "s")
    assert "8500 steps" in out and "85%" in out
    await log({"steps": 12000, "date": (date.today() - timedelta(days=1)).isoformat()}, "s")
    days = fitness.steps_week(fitness.steps_file(brain.settings), date.today())
    assert [d["steps"] for d in days[-2:]] == [12000, 8500] and days[0]["steps"] is None
    with pytest.raises(ValueError):
        await log({"steps": 1, "date": (date.today() + timedelta(days=1)).isoformat()}, "s")


async def test_the_meal_routine_recalculates_after_each_meal(make_brain, monkeypatch):
    brain, _ = make_brain()
    progress = {"date": date.today().isoformat(), "meal_count": 1, "weight": {"current": 80, "target": 75, "unit": "kg"},
                "goals": {"calories": 2000, "protein_g": 150}, "totals": {"calories": 500, "protein_g": 30}}

    written = []

    async def call_json(name, args):
        if name == "nutrition__set_nutrition_goals":
            written.append(args)
            return {}
        assert name == "nutrition__get_goal_progress"
        return progress
    monkeypatch.setattr(brain.hub, "call_json", call_json)
    note = await brain.executor._after_meal("r1", SimpleNamespace(id="s"))
    assert "Kalorie 500/2000 kcal" in note and "Białko 30/150 g" in note and "still to do" in note
    balance = brain.bus.log.read(kind="meal_balance")[-1]["data"]
    assert balance["rows"][0]["eaten"] == 500

    # what you said -> Jev -> what was saved, for the Dieta tab
    from brain import app as server
    monkeypatch.setattr(server, "brain", brain)
    brain.bus.emit("transcript", "ears", "r1", text="zjadłem owsiankę")
    brain.bus.emit("meal_classified", "router", "r1", meal="owsianka", meal_type="breakfast", source="jev")
    brain.bus.emit("tool_call", "tool", "r1", tool="nutrition__log_meal", input={"description": "owsianka",
                                                                                 "meal_type": "breakfast", "calories": 450})
    brain.bus.emit("tool_result", "tool", "r1", tool="nutrition__log_meal", is_error=False)
    brain.bus.emit("meal_balance", "executor", "r1", **fitness.day_balance(progress, 0))
    [entry] = server.nutrition_log()
    assert entry["said"] == "zjadłem owsiankę" and entry["source"] == "jev" and entry["ok"] is True
    assert entry["input"]["meal_type"] == "breakfast" and entry["balance"]["calories"] == [500, 2000]
    assert written == [] and brain.settings.get("training.nutrition_base") == {"calories": 2000}   # no training today


async def test_training_raises_the_goals_in_nutrition_mcp(make_brain, monkeypatch):
    brain, _ = make_brain()
    goals = {"calories": 2000, "carbs_g": 200, "protein_g": 150}
    written = []

    async def call_json(name, args):
        written.append(args)
        goals.update({k.removeprefix("daily_"): v for k, v in args.items()})
        return {}
    monkeypatch.setattr(brain.hub, "call_json", call_json)
    sync = lambda kcal: fitness.sync_goals(brain.hub, brain.settings, {"goals": dict(goals)}, kcal)

    assert await sync(500) == {"calories": 2000, "carbs_g": 200}            # training day: base + 60% of 500 kcal
    assert written[-1] == {"daily_calories": 2300, "daily_carbs_g": 252} and goals["calories"] == 2300
    await sync(500)                                                         # nothing new - nothing written
    assert len(written) == 1
    assert await sync(0) == {"calories": 2000, "carbs_g": 200}              # rest day: back to the base
    assert written[-1] == {"daily_calories": 2000, "daily_carbs_g": 200}
    goals["calories"] = 1900                                                # he set a new goal himself
    assert (await sync(500))["calories"] == 1900 and written[-1]["daily_calories"] == 2200
    b = fitness.day_balance({"goals": dict(goals), "totals": {"calories": 800}}, 500, base=brain.settings.get("training.nutrition_base"))
    assert b["rows"][0]["goal"] == 2200 and b["rows"][0]["base_goal"] == 1900 and b["extra_kcal"] == 300


def test_the_road_to_the_race_and_this_weeks_sessions():
    weekly = {"swim": {"sessions": 2, "hours": 1.0}, "run": {"sessions": 2, "hours": 2.0},
              "strength": {"sessions": 2, "hours": 0.8}}
    cfg = {"weekly": weekly, "race": {"distance": "half"}, "season_start": "2026-10-04"}
    road = fitness.roadmap(cfg, date(2026, 10, 4), date(2027, 9, 2))
    assert [p["phase"] for p in road] == ["base", "build", "peak", "taper"] and road[0]["weeks"] == 35
    week = road[0]["this_week"]
    assert week["phase"] == "base" and [s["minutes"] for s in week["sessions"] if s["sport"] == "run"] == [40, 60]   # 2 h x 85% base volume
    strength = [s["name"] for s in week["sessions"] if s["sport"] == "strength"]
    assert all(n.startswith("Siła ogólna") for n in strength)                   # the first 6 weeks: general strength
    later = fitness.roadmap(cfg, date(2026, 12, 1), date(2027, 9, 2))[0]["this_week"]["sessions"]
    assert any(s["name"].startswith("Siła maksymalna") for s in later)        # then heavy lifting in the base
    assert road[1]["sessions"][-1]["name"].startswith("Stabilizacja")           # build: maintenance only
    assert "1900 m" in road[1]["milestones"][0]


async def test_the_plan_changes_only_through_its_tool(make_brain):
    brain, _ = make_brain()
    update = brain.executor.handlers["training_plan_update"]
    out = await update({"why": "Crossfit raz w tygodniu zamiast drugiej siły", "weekly": {"strength": {"sessions": 1, "hours": 0.5}},
                        "steps_goal": 9000}, "s")
    assert "weekly" in out and brain.settings.get("training.weekly.strength.sessions") == 1
    assert brain.settings.get("training.weekly.run.hours") == 1.5 and brain.settings.get("training.steps_goal") == 9000
    assert brain.settings.get("training.changes")[-1]["why"].startswith("Crossfit")
    with pytest.raises(ValueError):
        await update({"why": "nic"}, "s")
    assert brain.map.needs_confirmation("training_plan_update")                # he says yes first


async def test_jev_classifies_a_plan_change_into_fixed_prompt_blocks(make_brain):
    brain, _ = make_brain()
    brain.router.jev.routing = {"module": {"choice": "training", "probabilities": {"training": 0.9, "smalltalk": 0.1}},
                                "capability": {"choice": "training.status", "probabilities": {"training.status": 0.9}},
                                "plan_change": {"choice": "add_activity"}, "plan_sport": {"choice": "strength"},
                                "adds_load": {"noul": 0.8}}
    assert {"plan_change", "plan_sport", "adds_load"} <= set(brain.router.questions())
    route = await brain.router.classify("chciałbym dodać crossfit raz w tygodniu")
    assert (route.source, route.plan_change, route.plan_sport, route.adds_load) == ("jev", "add_activity", "strength", 0.8)
    assert {"training.plan", "research.web"} <= set(route.capabilities)
    rules = brain.executor._module_rules(route)
    from brain.executor import ADDS_LOAD, PLAN_CHANGE_RULES, PLAN_SPORT_RULES
    assert "training plan change" in rules and PLAN_CHANGE_RULES["add_activity"] in rules
    assert PLAN_SPORT_RULES["strength"] in rules and ADDS_LOAD in rules
    brain.router.jev.routing["plan_change"] = {"choice": "none"}
    quiet = await brain.router.classify("ile przebiegłem w tym tygodniu?")
    assert quiet.plan_change is None and "training plan change" not in brain.executor._module_rules(quiet)


def test_products_list_is_a_memory_page(make_brain, monkeypatch):
    from brain import app as server

    brain, _ = make_brain()
    monkeypatch.setattr(server, "brain", brain)
    client = TestClient(server.app)
    assert client.get("/api/products").json() == []
    items = [{"name": "Odżywka białkowa", "url": "https://sklep.example/whey", "note": "wanilia, co 6 tygodni", "grams": 30},
             {"name": "Żele energetyczne", "url": "http://sklep.example/gel", "note": "", "grams": None}]
    assert client.put("/api/products", json=items).json() == items
    assert client.get("/api/products").json() == items
    assert brain.store.search("odżywka wanilia")[0]["path"] == "products.md"      # Alfred finds it via memory_search
    assert client.put("/api/products", json=[{"name": "x", "url": "javascript:alert(1)"}]).status_code == 422
    assert client.put("/api/products", json=[{"name": "", "url": "https://a.pl"}]).status_code == 422
    assert client.put("/api/products", json=[]).json() == [] and brain.store.products() == []


async def test_jev_matches_his_regular_product_or_says_other(make_brain):
    from brain.router import OTHER_PRODUCT, Router
    from test_router import FakeJev

    from brain.executor import grams_said
    assert [grams_said(t) for t in ("150 g skyru", "0,5 kg ryżu", "250ml mleka", "30 gramów odżywki", "jeden baton")] \
        == [150, 500, 250, 30, None]

    brain, _ = make_brain()
    whey = {"name": "Odżywka białkowa", "url": "https://sklep.example/whey", "note": "wanilia, 30 g porcja"}
    jev = FakeJev({"module": {"choice": "weight", "probabilities": {"weight": 0.9}}, "product": {"choice": whey["name"]}})
    router = Router(brain.map, jev, brain.settings)
    router.products = lambda: [whey]
    assert (await router.classify("wypiłem shake'a z odżywką")).product == whey["name"]
    assert set(jev.sent["product"]["criteria"]) == {whey["name"], OTHER_PRODUCT}       # his products + other
    jev.answers["product"] = {"choice": OTHER_PRODUCT}
    assert (await router.classify("zjadłem schabowego")).product == OTHER_PRODUCT
    router.products = lambda: []
    assert "product" not in router.questions()                                         # no products, no question

    brain.store.save_products([whey])
    assert brain.router.products() == [whey]                                          # Jev reads the Produkty list

    async def meal_type(*a):
        return "snack"
    brain.executor.classify_meal = meal_type
    ex, session = brain.executor, SimpleNamespace(id="s")
    args = {"description": "shake 1 porcja", "meal_type": "snack", "calories": 120}
    await ex._jev_meal(args, ExecResult(text="", model="m", request="wypiłem shake'a", product=whey), session, "r")
    assert args["description"] == "Odżywka białkowa - shake 1 porcja" and args["notes"] == "Stały produkt: https://sklep.example/whey"
    note = ex._product_note(whey, "x")
    assert whey["url"] in note and "wanilia" in note

    skyr = {"name": "Skyr naturalny", "url": "https://sklep.example/skyr", "note": "", "grams": 150}
    args = {"description": "skyr", "meal_type": "snack"}
    await ex._jev_meal(args, ExecResult(text="", model="m", request="zjadłem 200 g skyru", product=skyr), session, "r")
    assert args["description"] == "Skyr naturalny (200 g)"                             # what he said wins
    await ex._jev_meal(args, ExecResult(text="", model="m", request="zjadłem skyr", product=skyr), session, "r")
    assert args["description"] == "Skyr naturalny (150 g)"                             # else his usual portion
    assert "exactly 200 g" in ex._product_note(skyr, "zjadłem 200 g skyru")
    assert "ask him how many grams" in ex._product_note(skyr | {"grams": None}, "zjadłem skyr")

    said = "<reply_mode>text chat</reply_mode>\n\nzjadłem schabowego z ziemniakami i surówką"
    args = {"description": "Schabowy z ziemniakami", "meal_type": "dinner"}
    await ex._jev_meal(args, ExecResult(text="", model="m", request=said, product=OTHER_PRODUCT), session, "r")
    assert args["description"] == "zjadłem schabowego z ziemniakami i surówką"         # his own words


def test_each_product_of_a_meal_shows_its_kcal_and_macros(make_brain, monkeypatch):
    notes = ("- Kajzerka (60 g): 165 kcal, B 5.4 g, W 33 g, T 1.2 g\n"
             "- Mleko wysokobiałkowe Pilos (~70 g): 45 kcal, B 5,6 g, W 3.4 g, T 0.7 g\n"
             "• Mozzarella Light (65g): 105 kcal, B 12 g\n"
             "Stały produkt: https://sklep.example/mozzarella")
    items = fitness.meal_items(notes)
    assert [i["name"] for i in items] == ["Kajzerka", "Mleko wysokobiałkowe Pilos", "Mozzarella Light"]
    assert items[0] == {"name": "Kajzerka", "grams": 60, "approx": False, "kcal": 165, "protein_g": 5.4,
                        "carbs_g": 33, "fat_g": 1.2}
    assert items[1]["approx"] and items[1]["protein_g"] == 5.6                     # "~70 g", comma decimals
    assert items[2]["carbs_g"] is None                                           # a missing macro stays empty
    assert fitness.meal_items(None) == fitness.meal_items("owsianka") == []

    from brain import app as server
    brain, _ = make_brain()
    monkeypatch.setattr(server, "brain", brain)
    brain.bus.emit("transcript", "ears", "r1", text="zjadłem kajzerkę i mleko")
    brain.bus.emit("tool_call", "mcp:nutrition", "r1", tool="nutrition__log_meal",
                   input={"description": "Śniadanie", "meal_type": "breakfast", "calories": 315, "notes": notes})
    entry = server.nutrition_log()[0]
    assert entry["said"] == "zjadłem kajzerkę i mleko" and len(entry["items"]) == 3


def test_todays_meals_come_from_nutrition_mcp_with_their_products():
    text = """Times are local (Europe/Warsaw).

ID: 79c68098-522b-46ac-852f-b5a7ba9adf7f
Time: 2026-10-05 09:59
Type: breakfast
Description: Śniadanie: kajzerka (60 g), mleko wysokobiałkowe Pilos (70 g)
Calories: 717
Protein: 64g
Carbs: 47g
Fat: 31.5g
Fiber: 2.6g
Sugar: 11g (1g added)
Notes: Wartości szacowane z typowych etykiet. Mleko Pilos przyjęte jako 70 g (8 g białka/100 ml).

---

ID: 0f248a87-03ab-471b-9103-9b046cf595cf
Time: 2026-10-05 13:10
Type: lunch
Description: Skyr naturalny (200 g), banan (120 g)
Calories: 237
Protein: 22g
Carbs: 33g
Fat: 0.6g
Notes: - Skyr naturalny (200 g): 130 kcal, B 22 g, W 8 g, T 0.4 g
- Banan (120 g): 107 kcal, B 1.3 g, W 25 g, T 0.2 g
Stały produkt: https://sklep.example/skyr
"""
    breakfast, lunch = fitness.meals_from_text(text)
    assert breakfast["id"].startswith("79c6") and breakfast["type"] == "breakfast" and breakfast["time"] == "2026-10-05 09:59"
    assert (breakfast["calories"], breakfast["protein_g"], breakfast["fat_g"]) == (717, 64, 31.5)
    assert breakfast["items"] == []                                       # an old meal: no split yet -> the button
    assert [i["name"] for i in lunch["items"]] == ["Skyr naturalny", "Banan"]
    assert lunch["items"][1]["kcal"] == 107 and "Stały produkt" in lunch["notes"]
    assert fitness.meals_from_text("No meals logged on 2026-10-04.") == []


def test_diet_discipline_over_time():
    today = date(2026, 10, 5)                                           # Monday
    goals = {"calories": 2000, "protein_g": 150}
    day = lambda n, kcal, protein: {"date": (today - timedelta(days=n)).isoformat(), "calories": kcal, "protein_g": protein}
    days = [day(0, 700, 60),                                            # today: shown, not scored
            day(1, 2100, 150), day(2, 1900, 140), day(3, 2000, 160),   # three hits in a row up to yesterday
            day(4, 2600, 160),                                          # kcal over by 30% -> partial
            day(5, 1200, 50),                                           # both off -> miss
            day(7, 2050, 145)]                                          # day 6 nothing logged -> empty
    x = fitness.discipline(days, goals, today, span=8)
    assert [r["status"] for r in x["days"]] == ["hit", "empty", "miss", "partial", "hit", "hit", "hit", "today"]
    assert x["total_days"] == 7 and x["logged_days"] == 6
    assert x["streak"] == 3 and x["best_streak"] == 3
    assert x["kcal_on_target"] == round(4 / 6, 2) and x["protein_on_target"] == round(5 / 6, 2)
    assert x["score"] == round((4 + 0.5) / 7, 2) and x["avg_kcal"] == round((2100 + 1900 + 2000 + 2600 + 1200 + 2050) / 6)
    assert [w["start"] for w in x["weeks"]] == ["2026-09-28"] and x["weeks"][0]["logged"] == 6
    assert fitness.discipline([], {}, today, span=3)["score"] == 0          # nothing logged, no goals
