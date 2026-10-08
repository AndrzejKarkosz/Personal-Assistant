import json
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from fastapi.testclient import TestClient

from brain import fitness, meals
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


def test_this_weeks_target_comes_from_the_calendar():
    today = date(2026, 10, 8)                                       # Thursday
    mark = "Spokojnie.\nPlan treningowy Alfreda."
    ev = lambda title, day, start, end, desc=mark: {"summary": title, "description": desc,
                                                    "start": {"dateTime": f"2026-10-{day}T{start}:00+02:00"},
                                                    "end": {"dateTime": f"2026-10-{day}T{end}:00+02:00"}}
    events = [ev("Basen - technika", "07", "17:00", "17:45"), ev("Siłownia w domu - gumy oporowe", "07", "16:10", "16:35"),
              ev("Bieg z Maurycym - 35 min spokojnie", "06", "07:00", "07:35"), ev("Długi bieg - 45 min", "10", "09:00", "09:45"),
              ev("MojaFirma Sesja", "06", "19:00", "21:00", "")]
    acts = [{"sport": "run", "start_date_local": "2026-10-06T07:02:00Z", "moving_time": 2100}]
    r = fitness.report(acts, CFG, today, weeks=2, events=events)
    assert [(s["name"][:5], s["sport"], s["status"]) for s in r["planned"]] == [
        ("Bieg ", "run", "done"), ("Siłow", "strength", "missed"), ("Basen", "swim", "missed"), ("Długi", "run", "planned")]
    assert r["planned"][2] | {"kind": "technika", "minutes": 45, "date": "2026-10-07", "time": "17:00", "end": "17:45",
                              "note": "Spokojnie.", "activity": None} == r["planned"][2]
    assert r["planned"][0]["activity"]["moving_time"] == 2100                          # the Strava workout behind "done"
    this, last = r["weeks"]
    assert this["source"] == "calendar" and set(this["sports"]) == {"run", "strength", "swim"}
    assert this["sports"]["run"] == {"target_h": 1.3, "target_sessions": 2, "done_h": 0.6, "done_sessions": 1}
    assert last["source"] == "plan" and last["sports"]["swim"]["target_sessions"] == 2   # past weeks keep the plan
    assert fitness.work_load(events, 0, CFG)["meeting_h"] == 2.0                        # training is not a meeting
    assert fitness.report(acts, CFG, today, events=[])["weeks"][0]["source"] == "plan"   # an empty calendar -> the plan


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


async def test_jev_decides_the_meal_type():
    asked = {}

    async def classify_meal(request, meal, now):
        asked.update(request=request, meal=meal)
        return "breakfast"
    args = {"description": "owsianka z bananem", "meal_type": "snack", "calories": 450}
    assert await meals.fill_in(args, "zjadłem owsiankę", None, classify_meal) == "jev"
    assert args["meal_type"] == "breakfast" and asked == {"request": "zjadłem owsiankę", "meal": "owsianka z bananem"}

    async def jev_down(*a):
        raise RuntimeError("no Jev")
    args["meal_type"] = "lunch"
    assert await meals.fill_in(args, "obiad", None, jev_down) == "claude"
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
    from brain import app as server
    brain, _ = make_brain()
    progress = {"date": date.today().isoformat(), "meal_count": 1, "weight": {"current": 80, "target": 75, "unit": "kg"},
                "goals": {"calories": 2000, "protein_g": 150}, "totals": {"calories": 500, "protein_g": 30}}
    written, logged = [], []

    async def call_json(name, args):
        if name == "nutrition__set_nutrition_goals":
            written.append(args)
            return {}
        assert name == "nutrition__get_goal_progress"
        return progress

    async def call(name, args, limit=20000):
        logged.append(args)
        return "Meal logged.", False

    async def breakfast(request, meal, now):
        return "breakfast"
    monkeypatch.setattr(brain.hub, "call_json", call_json)
    monkeypatch.setattr(brain.hub, "call", call)
    monkeypatch.setattr(brain.router, "classify_meal", breakfast)
    brain.hub._owner["nutrition__log_meal"] = ("nutrition", "log_meal")

    # Claude logs a meal: Jev's meal type goes in, the meal routine comes back in the same answer
    meal = {"description": "owsianka", "meal_type": "snack", "calories": 450}
    output, is_error = await brain.executor.run_tool("nutrition__log_meal", meal, SimpleNamespace(id="s"), "r1",
                                                     ExecResult(text="", model="m", request="zjadłem owsiankę"))
    assert not is_error and logged[0]["meal_type"] == "breakfast"
    assert "Kalorie 500/2000 kcal" in output and "Białko 30/150 g" in output and "still to do" in output
    assert written == [] and json.loads(fitness.sync_file(brain.settings).read_text())["base"] == {"calories": 2000}

    # what you said -> Jev -> what was saved, for the Dieta tab
    monkeypatch.setattr(server, "brain", brain)
    [entry] = server.nutrition_log()
    assert entry["said"] == "zjadłem owsiankę" and entry["source"] == "jev" and entry["ok"] is True
    assert entry["input"]["meal_type"] == "breakfast" and entry["balance"]["calories"] == [500, 2000]


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
    base = json.loads(fitness.sync_file(brain.settings).read_text())["base"]
    b = fitness.day_balance({"goals": dict(goals), "totals": {"calories": 800}}, 500, base=base)
    assert b["rows"][0]["goal"] == 2200 and b["rows"][0]["base_goal"] == 1900 and b["extra_kcal"] == 300
    assert "nutrition_base" not in json.dumps(brain.settings.data)            # Alfred's state, not a setting


async def test_the_goal_base_moves_out_of_settings_without_a_second_raise(make_brain, monkeypatch):
    brain, _ = make_brain()
    brain.settings.data["training"] |= {"nutrition_base": {"calories": 2000, "carbs_g": 200},      # where it was kept
                                        "nutrition_synced": {"calories": 2300, "carbs_g": 252}}    # before 2026-10-05
    written = []

    async def call_json(name, args):
        written.append(args)
        return {}
    monkeypatch.setattr(brain.hub, "call_json", call_json)
    today = {"goals": {"calories": 2300, "carbs_g": 252}}                   # already raised for today's training
    assert await fitness.sync_goals(brain.hub, brain.settings, today, 500) == {"calories": 2000, "carbs_g": 200}
    assert written == []                                                    # not raised a second time
    assert json.loads(fitness.sync_file(brain.settings).read_text())["base"] == {"calories": 2000, "carbs_g": 200}


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
    assert "plan.updated** weekly, steps_goal: Crossfit" in brain.store.log_since(None)[-1]   # the briefing shows it
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
    assert "training plan change" in rules and fitness.PLAN_CHANGE_RULES["add_activity"] in rules
    assert fitness.PLAN_SPORT_RULES["strength"] in rules and fitness.ADDS_LOAD in rules
    race = brain.settings.get("training.race")
    assert f"what it does for {race['name']} on {race['date']}," in rules              # the race from the plan itself
    assert fitness.PLAN_CHANGES.keys() == fitness.PLAN_CHANGE_RULES.keys()              # every option Jev can pick
    assert fitness.PLAN_SPORTS.keys() == fitness.PLAN_SPORT_RULES.keys()                # has its fixed block
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
    items[0] |= {"kcal": 433, "protein_g": 76.7, "carbs_g": 9, "fat_g": 8, "fiber_g": None, "sugar_g": 4.3}
    items[1] |= dict.fromkeys(("kcal", "protein_g", "carbs_g", "fat_g", "fiber_g", "sugar_g"))
    assert client.put("/api/products", json=items).json() == items                   # the label per 100 g is kept
    assert client.get("/api/products").json() == items
    assert brain.store.search("odżywka wanilia")[0]["path"] == "products.md"      # Alfred finds it via memory_search
    assert client.put("/api/products", json=[{"name": "x", "url": "javascript:alert(1)"}]).status_code == 422
    assert client.put("/api/products", json=[{"name": "", "url": "https://a.pl"}]).status_code == 422
    assert client.put("/api/products", json=[]).json() == [] and brain.store.products() == []


async def test_jev_names_his_regular_products_and_their_labels_set_the_numbers(make_brain):
    from brain.router import Router
    from test_router import FakeJev

    brain, _ = make_brain()
    milk = {"name": "Mleko Pilos", "url": "https://sklep.example/mleko", "note": "", "grams": 250, "kcal": 54.2,
            "protein_g": 8, "carbs_g": 4.7, "fat_g": 0.5, "fiber_g": 0, "sugar_g": 4.7}
    ham = {"name": "Szynka z kurczaka Pikok", "url": "https://sklep.example/szynka", "note": "", "grams": None,
           "kcal": 107, "protein_g": 20, "carbs_g": 2, "fat_g": 2, "fiber_g": 0.5, "sugar_g": 1.8}
    jev = FakeJev({"module": {"choice": "weight", "probabilities": {"weight": 0.9}},
                   "product_0": {"noul": 0.92}, "product_1": {"noul": 0.81}})
    router = Router(brain.map, jev, brain.settings)
    router.products = lambda: [milk, ham]
    route = await router.classify("mleko Pilos pięćdziesiąt gramów i szynka Peacock czterdzieści")
    assert route.products == [milk["name"], ham["name"]]                               # several in one meal
    assert jev.sent["product_1"]["type"] == "noul" and ham["name"] in jev.sent["product_1"]["instructions"]
    jev.answers |= {"product_0": {"noul": 0.1}, "product_1": {"noul": 0.2}}
    assert (await router.classify("zjadłem schabowego")).products == []                # none of his products
    router.products = lambda: []
    assert not any(k.startswith("product") for k in router.questions())               # no products, no question

    brain.store.save_products([milk, ham])
    assert brain.router.products() == [milk, ham]                                     # Jev reads the Produkty list
    assert meals.regular_products(brain.store, [ham["name"]]) == [ham]
    assert meals.regular_products(brain.store, None) is None                          # Jev did not answer
    note = meals.product_note([milk, ham | {"kcal": None}])
    assert "54.2 kcal" in note and "usual portion 250 g" in note and "web_fetch https://sklep.example/szynka" in note

    async def snack(request, meal, now):
        return "snack"

    async def jev_down(request, meal, now):
        raise RuntimeError("Jev is down")
    args = {"description": "mleko, szynka, kajzerka", "meal_type": "dinner", "calories": 999, "fiber_g": 9,
            "notes": "- MLEKO PILOS (50 g): 10 kcal, B 1 g, W 1 g, T 1 g\n"
                     "- Szynka z kurczaka Pikok (40 g): 10 kcal, B 1 g, W 1 g, T 1 g\n"
                     "- Kajzerka (~60 g): 165 kcal, B 5.4 g, W 33 g, T 1.2 g\nUzupełnienie śniadania"}
    assert await meals.fill_in(args, "...", [milk, ham], snack) == "jev"
    assert args["meal_type"] == "snack"                                                # Jev's meal type, not Claude's
    assert args["notes"].splitlines() == ["- Mleko Pilos (50 g): 27 kcal, B 4.0 g, W 2.4 g, T 0.2 g",   # the label
                                          "- Szynka z kurczaka Pikok (40 g): 43 kcal, B 8.0 g, W 0.8 g, T 0.8 g",
                                          "- Kajzerka (~60 g): 165 kcal, B 5.4 g, W 33 g, T 1.2 g",     # Claude's
                                          "Uzupełnienie śniadania"]
    assert (args["calories"], args["protein_g"], args["carbs_g"], args["fat_g"]) == (235, 17.4, 36.2, 2.2)  # sums
    assert args["fiber_g"] == 9 and args["description"] == "mleko, szynka, kajzerka"   # Claude's estimate stays

    args = {"description": "mleko", "notes": "- Mleko Pilos (200 g): 1 kcal, B 1 g, W 1 g, T 1 g"}
    assert meals.recount(args, [milk]) == ["Mleko Pilos"]
    assert (args["calories"], args["fiber_g"], args["sugar_g"]) == (108, 0, 9.4)       # only his products: all exact

    args = {"description": "Schabowy z ziemniakami", "meal_type": "dinner"}
    assert await meals.fill_in(args, "zjadłem schabowego z ziemniakami i surówką", [], jev_down) == "claude"
    assert args == {"description": "zjadłem schabowego z ziemniakami i surówką", "meal_type": "dinner"}  # his words


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
    brain.bus.emit("nutrition_logged", "executor", "r1", said="zjadłem kajzerkę i mleko", tool="nutrition__log_meal",
                   input={"description": "Śniadanie", "meal_type": "breakfast", "calories": 315, "notes": notes},
                   source="jev", ok=True, balance=None)
    entry = server.nutrition_log()[0]
    assert entry["said"] == "zjadłem kajzerkę i mleko" and len(entry["items"]) == 3 and "balance" not in entry


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
