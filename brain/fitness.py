"""Treningi: the triathlon plan (config/brain.yaml -> training), where the season is and how much of the plan is done -
from Strava (the strava MCP server) - plus how heavy the work week is. Used by the Treningi tab and training_status.

What the plan rests on (research, 2026-10):
- 80/20: ~80% of training time easy (Z1-2), ~20% hard; a 2024 meta-analysis (17 studies, 437 athletes) found a small
  VO2peak advantage over other intensity splits.
- Periodisation base -> build -> peak -> taper, in a 3:1 cycle: 3 weeks of load, then 1 week with 30-40% less volume.
- Taper: 8 days for a sprint, 10 olympic, 14 for a half / full distance; volume -40-60%, intensity and frequency kept.
- Life stress counts as training load: in a heavy work week cut volume 20-30% and keep one quality session.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

TAPER_DAYS = {"sprint": 8, "olympic": 10, "half": 14, "full": 14}
PEAK_WEEKS, BUILD_WEEKS = 3, 8              # counted back from the start of the taper
VOLUME = {"base": 0.85, "build": 1.0, "peak": 1.1, "taper": 0.5, "recovery": 0.65}   # x the plan's weekly hours
PHASE_PL = {"base": "baza", "build": "budowanie", "peak": "szczyt", "taper": "taper", "recovery": "regeneracja"}
# MET (Compendium of Physical Activities) without power data: (easy, hard - average HR above easy_hr_max)
MET = {"swim": (6.0, 9.8), "bike": (6.8, 10.0), "run": (8.0, 11.0), "strength": (3.5, 6.0), "other": (5.0, 8.0)}
MACROS = (("calories", "Kalorie", "kcal"), ("protein_g", "Białko", "g"), ("carbs_g", "Węglowodany", "g"),
          ("fat_g", "Tłuszcz", "g"), ("fiber_g", "Błonnik", "g"), ("water_ml", "Woda", "ml"))


def burned(activity: dict, weight_kg: float | None, easy_hr_max: int = 145) -> tuple[int | None, str]:
    """Estimated kcal of one workout and how it was estimated: power (a ride with a power meter: ~1 kJ of work = ~1
    kcal burnt, at ~24% efficiency), distance (running costs ~1 kcal per kg per km) or MET x weight x hours."""
    if activity.get("kilojoules"):
        return round(activity["kilojoules"]), "moc"
    if not weight_kg:
        return None, ""
    if activity.get("sport") == "run" and activity.get("distance"):
        return round(weight_kg * activity["distance"] / 1000), "dystans"
    # ponytail: average HR picks easy/hard MET; a per-second HR model (Keytel) needs age, sex and the HR stream
    easy, hard = MET.get(activity.get("sport"), MET["other"])
    met = hard if (activity.get("average_heartrate") or 0) > easy_hr_max else easy
    return round(met * weight_kg * activity.get("moving_time", 0) / 3600), "MET"


RAISED = ("calories", "carbs_g")           # the goals a training day raises


def raised(base: dict, training_kcal: int, eat_back: float = 0.6) -> dict[str, int]:
    """Base kcal / carbs goals + `eat_back` of the kcal burnt in training, eaten back mostly as carbs - the deficit stays
    moderate and training does not suffer."""
    extra = round(training_kcal * eat_back)
    raise_by = {"calories": extra, "carbs_g": round(extra * 0.7 / 4)}       # 4 kcal per gram of carbs
    return {k: round(base[k] + raise_by[k]) for k in RAISED if base.get(k)}


def base_goals(goals_now: dict, cfg: dict) -> dict:
    """His own kcal / carbs goals without training. Alfred writes base + training into Nutrition MCP every day, so
    the base is kept in training.nutrition_base; goals that differ from what Alfred last wrote were set by him (the
    weight-goal talk, claude.ai, the app) and become the new base."""
    last, base = cfg.get("nutrition_synced") or {}, cfg.get("nutrition_base") or {}
    if not base or any(goals_now.get(k) != last.get(k) for k in RAISED):
        base = {k: goals_now[k] for k in RAISED if goals_now.get(k)}
    return base


async def sync_goals(hub, settings, progress: dict, training_kcal: int) -> dict:
    """Today's training into the diet: Nutrition MCP's daily kcal / carbs goals = base + training (back to the base on
    a rest day). Returns the base goals."""
    cfg = settings.get("training") or {}
    goals_now = progress.get("goals") or {}
    base = base_goals(goals_now, cfg)
    target = raised(base, training_kcal, float(cfg.get("eat_back", 0.6)))
    if target and any(goals_now.get(k) != v for k, v in target.items()):
        await hub.call_json("nutrition__set_nutrition_goals", {f"daily_{k}": v for k, v in target.items()})
    settings.update({"training": {"nutrition_base": base, "nutrition_synced": target}})
    return base


def day_balance(progress: dict, training_kcal: int, eat_back: float = 0.6, base: dict | None = None) -> dict[str, Any]:
    """Today's intake (nutrition get_goal_progress) against the goals: kcal and carbs = base + today's training."""
    goals, eaten = progress.get("goals") or {}, progress.get("totals") or {}
    base = {**goals, **(base or {})}
    up = raised(base, training_kcal, eat_back)
    rows = [{"key": k, "label": label, "unit": unit, "eaten": round(eaten.get(k) or 0),
             "goal": up.get(k) or (round(base[k]) if base.get(k) else None), "base_goal": base.get(k)}
            for k, label, unit in MACROS]
    return {"training_kcal": training_kcal, "extra_kcal": up["calories"] - round(base["calories"]) if "calories" in up else 0,
            "rows": rows, "meal_count": progress.get("meal_count", 0), "weight": progress.get("weight"),
            "date": progress.get("date")}


_ITEM = re.compile(r"^\s*[-*•]?\s*(?P<name>.+?)\s*\(\s*(?P<approx>~)?\s*(?P<grams>\d+(?:[.,]\d+)?)\s*(?:g|ml)\s*\)\s*:"
                   r"\s*(?P<kcal>\d+(?:[.,]\d+)?)\s*kcal(?P<rest>.*)$", re.I)
_MACRO = {"protein_g": r"\bB\s*(\d+(?:[.,]\d+)?)", "carbs_g": r"\bW\s*(\d+(?:[.,]\d+)?)", "fat_g": r"\bT\s*(\d+(?:[.,]\d+)?)"}


def meal_items(notes: str | None) -> list[dict[str, Any]]:
    """The per-product lines Claude writes into a meal's notes (modules/weight/prompt.md):
    "- Kajzerka (60 g): 165 kcal, B 5.4 g, W 33 g, T 1.2 g" -> {name, grams, approx, kcal, protein_g, carbs_g, fat_g}.
    Other lines are skipped; a macro that is missing stays None."""
    num = lambda s: float(s.replace(",", "."))
    out = []
    for line in (notes or "").splitlines():
        if m := _ITEM.match(line):
            item = {"name": m["name"], "grams": num(m["grams"]), "approx": bool(m["approx"]), "kcal": num(m["kcal"])}
            for key, pattern in _MACRO.items():
                found = re.search(pattern, m["rest"])
                item[key] = num(found.group(1)) if found else None
            out.append(item)
    return out


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def phase(day: date, race: date | None, distance: str = "half") -> str:
    """Season phase on `day`. Recovery weeks (3:1) are counted back from the race, so the cycle lands on race day."""
    if race is None:
        return "base"
    days = (race - day).days
    if days < 0:
        return "recovery" if days >= -14 else "base"
    taper = TAPER_DAYS.get(distance, 14)
    if days <= taper:
        return "taper"
    weeks = (days - taper - 1) // 7            # whole weeks before the taper: 0 = the last week of the peak
    if weeks < PEAK_WEEKS:
        return "peak"
    if weeks % 4 == 3:
        return "recovery"
    return "build" if weeks < PEAK_WEEKS + BUILD_WEEKS else "base"


def _day(activity: dict) -> date:
    return date.fromisoformat(activity["start_date_local"][:10])


def _hours(activities: list[dict]) -> float:
    return round(sum(a.get("moving_time", 0) for a in activities) / 3600, 1)


def week(activities: list[dict], cfg: dict, monday: date, race: date | None) -> dict[str, Any]:
    """Target vs done for the week starting `monday`: hours and sessions per sport, and the easy (80/20) share."""
    ph = phase(monday, race, (cfg.get("race") or {}).get("distance", "half"))
    factor = VOLUME[ph]
    done = [a for a in activities if monday <= _day(a) < monday + timedelta(days=7)]
    sports = {}
    for sport, t in (cfg.get("weekly") or {}).items():
        mine = [a for a in done if a.get("sport") == sport]
        sports[sport] = {"target_h": round(t["hours"] * factor, 1), "target_sessions": t["sessions"],
                         "done_h": _hours(mine), "done_sessions": len(mine)}
    target = round(sum(s["target_h"] for s in sports.values()), 1)
    planned = _hours([a for a in done if a.get("sport") in sports])
    # ponytail: the activity's average HR stands for its intensity; per-zone time needs the HR streams
    with_hr = [a for a in done if a.get("average_heartrate")]
    hr_time = sum(a.get("moving_time", 0) for a in with_hr)
    easy = sum(a.get("moving_time", 0) for a in with_hr if a["average_heartrate"] <= cfg.get("easy_hr_max", 145))
    return {"start": monday.isoformat(), "phase": ph, "phase_pl": PHASE_PL[ph], "volume": factor, "sports": sports,
            "target_h": target, "done_h": planned, "other_h": round(_hours(done) - planned, 1),
            "kcal": sum(a.get("kcal") or 0 for a in done),
            "pct": round(100 * planned / target) if target else None,
            "easy_share": round(easy / hr_time, 2) if hr_time else None}


def timeline(race: date | None, distance: str, today: date) -> list[dict[str, Any]]:
    """The season from today to the race as phase segments (base, build, peak, taper) - for the timeline bar."""
    if race is None or race < today:
        return []
    taper = race - timedelta(days=TAPER_DAYS.get(distance, 14))
    peak = taper - timedelta(weeks=PEAK_WEEKS)
    build = peak - timedelta(weeks=BUILD_WEEKS)
    edges = [("base", today), ("build", build), ("peak", peak), ("taper", taper), ("race", race)]
    out = []
    for (ph, start), (_, end) in zip(edges, edges[1:]):
        start = max(start, today)
        if end > start:
            out.append({"phase": ph, "phase_pl": PHASE_PL[ph], "start": start.isoformat(), "days": (end - start).days})
    return out


# The road to a half Ironman, phase by phase: focus, the two weekly sessions per sport (short / long - the long one
# gets 60% of the sport's time; strength splits evenly) and the milestones to reach by the end of the phase.
# Strength follows docs/triathlon-motor-prep.md: general -> maximal strength (+ plyometrics) -> maintenance -> taper.
ROAD = {
    "base": {
        "focus": "Baza tlenowa, technika i siła: prawie wszystko spokojnie (Z2), technika pływania; siła 2 × w tygodniu - "
                 "6 tygodni ogólnej, potem ciężka (4-6 powtórzeń) ze skokami.",
        "sessions": {"swim": [("Technika: ćwiczenia + spokojny kraul", "technika"), ("Pływanie ciągiem, spokojnie", "spokojnie")],
                     "bike": [("Spokojna jazda Z2, kadencja 85-95", "spokojnie"), ("Długa jazda Z2", "spokojnie")],
                     "run": [("Spokojny bieg + 6 przebieżek po 20 s", "spokojnie"), ("Długi bieg spokojnie", "spokojnie")],
                     "strength": [("Siła maksymalna A: przysiad 4 × 4-6 ciężko (RPE 8), martwy ciąg rumuński 3 × 6, podciąganie 3 × 5-8, plank kopenhaski", "siła"), ("Siła maksymalna B + skoki: przysiad bułgarski 3 × 6 na nogę, wspięcia jednonóż z ciężarem 3 × 8, pogo jumps 3 × 20 s, skoki na skrzynię 3 × 5, Pallof press", "siła")]},
        "milestones": ["1500 m kraulem bez zatrzymania", "2 h na rowerze w Z2 (~50 km)", "12 km biegu spokojnie"]},
    "build": {
        "focus": "Dokładamy intensywność: jedna jednostka progowa w tygodniu na dyscyplinę i co tydzień brick (rower → bieg); "
                 "siła tylko utrzymywana - krótko i ciężko.",
        "sessions": {"swim": [("Interwały 8-10 × 100 m w tempie progowym", "jakość"), ("Pływanie ciągiem do 1900 m", "spokojnie")],
                     "bike": [("Interwały progowe 3 × 10 min", "jakość"), ("Długa jazda + 15 min biegu (brick)", "brick")],
                     "run": [("Tempo: 3 × 8 min w progu", "jakość"), ("Długi bieg spokojnie", "spokojnie")],
                     "strength": [("Utrzymanie siły: przysiad 3 × 4-5 (~80-85%), martwy ciąg rumuński 3 × 5, podciąganie 3 × 5, skoki na skrzynię 3 × 5", "siła"), ("Stabilizacja: przysiad bułgarski 2 × 8, wspięcia jednonóż 3 × 10, rotacje zewnętrzne barku, plank kopenhaski", "siła")]},
        "milestones": ["1900 m ciągiem (dystans startowy)", "75 km roweru + 20 min biegu", "16-18 km biegu"]},
    "peak": {
        "focus": "Specyfika startu: tempo startowe, symulacje i jedzenie na trasie (60-90 g węglowodanów na godzinę).",
        "sessions": {"swim": [("3 × 600 m w tempie startowym, najlepiej na wodach otwartych", "jakość"), ("Pływanie ciągiem 2000 m", "spokojnie")],
                     "bike": [("2 × 20 min w tempie startowym", "jakość"), ("Symulacja: długa jazda w tempie startowym + 30 min biegu", "brick")],
                     "run": [("Bieg w tempie startowym 5-8 km", "jakość"), ("Długi bieg 18-20 km, ostatnie 5 km w tempie startowym", "spokojnie")],
                     "strength": [("Utrzymanie siły: przysiad 3 × 3 (~85%), martwy ciąg rumuński 2 × 5, 3 × 5 skoków - krótko i ciężko, raz w tygodniu", "siła"), ("Mobilność bioder i odcinka piersiowego, rotatory barku, core", "mobilność")]},
        "milestones": ["Symulacja 90 km roweru + 30 min biegu", "Przetestowane żywienie: 60-90 g węgli/h", "Start kontrolny (np. olimpijka)"]},
    "taper": {
        "focus": "Świeżość: objętość -40-60%, intensywność zostaje - krótkie odcinki w tempie startowym, dużo snu.",
        "sessions": {"swim": [("Krótko: 4 × 200 m w tempie startowym", "jakość"), ("Spokojne pływanie, ostatni test pianki", "spokojnie")],
                     "bike": [("Krótka jazda z 3 × 3 min w tempie startowym", "jakość"), ("Spokojna jazda, sprawdzenie roweru", "spokojnie")],
                     "run": [("Krótki bieg z 4 × 1 min w tempie startowym", "jakość"), ("Spokojny rozruch 20-30 min", "spokojnie")],
                     "strength": [("Aktywacja: przysiad 2 × 5 lekko, 2 × 5 skoków, gumy na barki", "siła"), ("Mobilność 15-20 min", "mobilność")]},
        "milestones": ["Sprzęt i rower sprawdzone", "Plan żywienia i strefy zmian rozpisane", "Sen 8 h przez ostatni tydzień"]},
}
ROAD["recovery"] = {**ROAD["base"], "focus": "Lżejszy tydzień (3:1): ta sama struktura, ~65% objętości - ciało nadrabia adaptację."}
# The first weeks of the season: general strength - technique, tendons and joints get used to load before heavy lifting.
GENERAL_WEEKS = 6
GENERAL_STRENGTH = [("Siła ogólna A: goblet squat, martwy ciąg rumuński z hantlami, wiosłowanie, pompki, dead bug - "
                     "3 × 12-15", "siła"),
                    ("Siła ogólna B: wykroki, hip thrust, wspięcia na palce z opuszczaniem 3 s, rotacje zewnętrzne z "
                     "gumą, plank boczny - 3 × 12-15", "siła")]


def week_sessions(ph: str, weekly: dict, factor: float, general: bool = False) -> list[dict[str, Any]]:
    """This phase's sessions with minutes from his weekly hours x the phase volume (short 40% / long 60%).
    general = the first weeks of the season: general strength instead of heavy lifting."""
    out = []
    for sport, plan in weekly.items():
        templates = GENERAL_STRENGTH if general and sport == "strength" else ROAD[ph]["sessions"].get(sport)
        if not templates:
            continue
        minutes = plan["hours"] * factor * 60
        for (name, kind), share in zip(templates, (0.5, 0.5) if sport == "strength" else (0.4, 0.6)):
            out.append({"sport": sport, "name": name, "kind": kind, "minutes": max(15, round(minutes * share / 5) * 5)})
    return out


def general_weeks(cfg: dict, day: date) -> bool:
    """Still in the first GENERAL_WEEKS of the season (training.season_start)?"""
    start = cfg.get("season_start")
    return bool(start) and 0 <= (day - date.fromisoformat(start)).days < GENERAL_WEEKS * 7


def roadmap(cfg: dict, today: date, race: date | None) -> list[dict[str, Any]]:
    """The way to the race: each phase of the season with its dates, focus, milestones and a sample week; the current
    phase also has `this_week` - the sessions for this week (recovery weeks and general strength included)."""
    out, weekly = [], cfg.get("weekly") or {}
    for i, seg in enumerate(timeline(race, (cfg.get("race") or {}).get("distance", "half"), today)):
        road = ROAD[seg["phase"]]
        end = date.fromisoformat(seg["start"]) + timedelta(days=seg["days"] - 1)
        item = seg | {"end": end.isoformat(), "weeks": max(1, round(seg["days"] / 7)), "focus": road["focus"],
                      "milestones": road["milestones"], "sessions": week_sessions(seg["phase"], weekly, VOLUME[seg["phase"]])}
        if i == 0:
            now = phase(today, race, (cfg.get("race") or {}).get("distance", "half"))
            item["this_week"] = {"phase": now, "phase_pl": PHASE_PL[now], "focus": ROAD[now]["focus"],
                                 "sessions": week_sessions(now, weekly, VOLUME[now], general_weeks(cfg, today))}
        out.append(item)
    return out


def steps_week(path: Path, today: date, days: int = 7) -> list[dict[str, Any]]:
    """The steps he told Alfred (steps_log), one row per day, oldest first."""
    saved = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return [{"date": d, "steps": saved.get(d)} for d in ((today - timedelta(days=i)).isoformat()
                                                          for i in range(days - 1, -1, -1))]


def report(activities: list[dict], cfg: dict, today: date, weeks: int = 8,
           weight_kg: float | None = None) -> dict[str, Any]:
    """The plan and its realisation: this week first, then the `weeks - 1` before it; activities of the last 14 days,
    each with its estimated kcal (weight from Nutrition MCP, else training.weight_kg)."""
    race_cfg = cfg.get("race") or {}
    race = date.fromisoformat(race_cfg["date"]) if race_cfg.get("date") else None
    this = week_start(today)
    weight_kg = weight_kg or cfg.get("weight_kg")
    activities = [a | dict(zip(("kcal", "kcal_source"), burned(a, weight_kg, cfg.get("easy_hr_max", 145))))
                  for a in activities]
    recent = sorted((a for a in activities if _day(a) > today - timedelta(days=14)), key=lambda a: a["start_date_local"],
                    reverse=True)
    return {"today": today.isoformat(), "race": race_cfg | {"days_to": (race - today).days if race else None},
            "phase": phase(today, race, race_cfg.get("distance", "half")), "easy_target": cfg.get("easy_share", 0.8),
            "plan": {"weekly": cfg.get("weekly") or {}, "easy_hr_max": cfg.get("easy_hr_max", 145),
                     "steps_goal": cfg.get("steps_goal", 10000)},
            "weeks": [week(activities, cfg, this - timedelta(weeks=i), race) for i in range(weeks)],
            "activities": recent, "weight_kg": weight_kg,
            "timeline": timeline(race, race_cfg.get("distance", "half"), today),
            "roadmap": roadmap(cfg, today, race),
            "today_kcal": sum(a.get("kcal") or 0 for a in recent if _day(a) == today)}


def work_load(events: list[dict], work_tasks_due: int, cfg: dict) -> dict[str, Any]:
    """Meetings in the calendar this week + work tasks due: a busy week means less training volume."""
    hours = 0.0
    for e in events:
        start, end = (e.get("start") or {}).get("dateTime"), (e.get("end") or {}).get("dateTime")
        if start and end:                       # all-day events are not meetings
            hours += (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() / 3600
    limits = cfg.get("busy_week") or {}
    busy = hours >= limits.get("meeting_hours", 15) or work_tasks_due >= limits.get("work_tasks_due", 8)
    return {"meeting_h": round(hours, 1), "work_tasks_due": work_tasks_due, "busy": busy,
            "advice": "Ciężki tydzień w pracy: zetnij objętość treningów o 20-30%, zostaw jedną jednostkę jakościową."
            if busy else None}


def balance_text(balance: dict, training: dict) -> str:
    """The meal routine's note for Claude: today against the goals (raised by training) and the week's sessions left."""
    rows = "; ".join(f"{r['label']} {r['eaten']}" + (f"/{r['goal']}" if r["goal"] else "") + f" {r['unit']}"
                     for r in balance["rows"] if r["goal"] or r["eaten"])
    today = [f"{a.get('name')} ~{a['kcal']} kcal" for a in training.get("activities", [])
             if a.get("kcal") and _day(a).isoformat() == training.get("today")]
    left = [f"{s} {v['target_sessions'] - v['done_sessions']}x ({max(0, v['target_h'] - v['done_h']):.1f} h)"
            for s, v in training["weeks"][0]["sports"].items() if v["done_sessions"] < v["target_sessions"]]
    return ("Meal routine - recalculated after this meal (tell him in one sentence what is left for today):\n"
            f"Today: {rows or 'nothing logged'}."
            + (f" Goals include +{balance['extra_kcal']} kcal eaten back for today's training ({', '.join(today)})."
               if balance["extra_kcal"] else f" Training today: {', '.join(today)}." if today else "")
            + ("" if any(r["goal"] for r in balance["rows"]) else " No nutrition goals yet - offer the weight-goal interview.")
            + (f"\nThis week's sessions still to do: {', '.join(left)}." if left else "\nThis week's plan is done."))


async def weight_now(hub) -> float | None:
    """The latest weigh-in from Nutrition MCP, if it is connected."""
    server = hub.servers.get("nutrition")
    if not server or server.status != "ready":
        return None
    try:
        return ((await hub.call_json("nutrition__get_goal_progress", {})).get("weight") or {}).get("current")
    except Exception:
        return None


async def status(hub, settings, weeks: int = 8, today: date | None = None,
                 weight_kg: float | None = None) -> dict[str, Any]:
    """report() over the Strava activities of those weeks; without Strava the plan still shows, with the reason."""
    today = today or date.today()
    server = hub.servers.get("strava")
    activities, error = [], None
    if not server or server.status != "ready":
        error = (server and server.error) or f"serwer strava: {server.status if server else 'brak w config/mcp.json'}"
    else:
        try:
            activities = await hub.call_json("strava__activities", {
                "start_date": (week_start(today) - timedelta(weeks=weeks - 1)).isoformat(),
                "end_date": today.isoformat()})
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"[:300]
    cfg = settings.get("training") or {}
    return report(activities, cfg, today, weeks, weight_kg) | {
        "strava": {"status": "error" if error else "ready", "error": error},
        "steps": {"goal": cfg.get("steps_goal", 10000), "days": steps_week(steps_file(settings), today)}}


def steps_file(settings) -> Path:
    return settings.path("memory.dir") / "steps.json"
