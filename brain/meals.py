"""Logging what he eats in Nutrition MCP. Jev decides first - which of his regular products he named (one yes/no per
product) and the meal type - and the system writes those decisions into the nutrition__log_meal call: his products'
numbers come from their labels (per 100 g in products.md, from the product links), Claude only estimates the rest.
After every logged meal comes the meal routine: today's intake against the goals, raised by today's training.

The executor calls fill_in() before the call and after_meal() after it.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Awaitable, Callable

from . import fitness

log = logging.getLogger("alfred.meals")
PER_100G = ("kcal", "protein_g", "carbs_g", "fat_g", "fiber_g", "sugar_g")     # a product's label, per 100 g
TOTALS = {"kcal": "calories", "protein_g": "protein_g", "carbs_g": "carbs_g", "fat_g": "fat_g",
          "fiber_g": "fiber_g", "sugar_g": "sugar_g"}


def regular_products(store, named: list[str] | None) -> list[dict] | None:
    """Jev's product answer (Route.products) as his products themselves; [] = none of them, None = Jev did not answer."""
    return None if named is None else [p for p in store.products() if p["name"] in named]


def _label(p: dict) -> str:
    if p.get("kcal") is None:
        return f"no label values stored - web_fetch {p['url']} for its values per 100 g"
    return (f"per 100 g: {p['kcal']:g} kcal, B {p['protein_g']:g} g, W {p['carbs_g']:g} g, T {p['fat_g']:g} g"
            + "".join(f", {k[:-2]} {p[k]:g} g" for k in ("fiber_g", "sugar_g") if p.get(k) is not None))


def product_note(products: list[dict]) -> str:
    """The fixed template for Claude: the regular products Jev heard, with their label values."""
    lines = "\n".join(f"- {p['name']}" + (f" ({p['note']})" if p.get("note") else "") + f": {_label(p)}"
                      + (f"; his usual portion {p['grams']:g} g" if p.get("grams") else "") for p in products)
    return ("<regular_products jev=\"named\">Jev heard these of his regular products in what he said. In the notes of "
            "nutrition__log_meal / update_meal write one line for each, with EXACTLY this name and the grams he said "
            "(no amount said -> his usual portion; no usual portion -> ask him how many grams first): "
            "`- <name> (<grams> g): <kcal> kcal, B <protein> g, W <carbs> g, T <fat> g`. The system recomputes these "
            "lines and the meal's totals from the labels below - you estimate only the other foods.\n"
            f"{lines}\n</regular_products>")


def recount(args: dict[str, Any], products: list[dict]) -> list[str]:
    """His regular products' lines in the notes get their numbers from the label (per 100 g x the grams in the line),
    and the meal's calories / protein / carbs / fat become the sum of all product lines. Fiber and sugar too, but only
    when every line is a labelled product (the lines carry no fiber or sugar for Claude's estimates).
    Returns the products recounted."""
    labelled = {p["name"].casefold(): p for p in products if p.get("kcal") is not None}
    lines, done, extra = [], [], {"fiber_g": 0.0, "sugar_g": 0.0}
    for line in str(args.get("notes") or "").splitlines():
        m = fitness._ITEM.match(line)
        if m and (p := labelled.get(m["name"].strip().casefold())):
            grams = float(m["grams"].replace(",", "."))
            v = {k: (p.get(k) or 0) * grams / 100 for k in PER_100G}
            line = (f"- {p['name']} ({grams:g} g): {v['kcal']:.0f} kcal, B {v['protein_g']:.1f} g, "
                    f"W {v['carbs_g']:.1f} g, T {v['fat_g']:.1f} g")
            done.append(p["name"])
            for k in extra:
                extra[k] = None if extra[k] is None or p.get(k) is None else extra[k] + v[k]
        lines.append(line)
    if not done:
        return done
    args["notes"] = "\n".join(lines)
    items = fitness.meal_items(args["notes"])
    args["calories"] = round(sum(i["kcal"] for i in items))
    for k in ("protein_g", "carbs_g", "fat_g"):
        args[k] = round(sum(i[k] or 0 for i in items), 1)
    if len(done) == len(items):          # only his products: fiber and sugar are exact too
        args |= {k: round(v, 1) for k, v in extra.items() if v is not None}
    return done


async def fill_in(args: dict[str, Any], said: str, products: list[dict] | None,
                  classify_meal: Callable[[str, str, str], Awaitable[str | None]]) -> str:
    """Jev's decisions into a nutrition__log_meal call: the meal type; none of his products -> the description is his
    own words; his products -> their lines and the totals from the labels (recount). Returns who picked the meal
    type: "jev", or "claude" (Claude's own value stays when Jev cannot answer)."""
    try:
        kind = await classify_meal(said, str(args.get("description", "")), f"{datetime.now():%A %H:%M}")
    except Exception as exc:
        log.warning("Jev did not pick the meal type: %s: %s", type(exc).__name__, exc)
        kind = None
    if kind:
        args["meal_type"] = kind
    if products == []:
        args["description"] = said
    elif products:
        recount(args, products)
    return "jev" if kind else "claude"


async def after_meal(hub, settings) -> tuple[str, dict | None]:
    """The meal routine: today's intake against the goals - raised by today's training from Strava - and the training
    sessions left this week. Returns the note for Claude (he tells what is left) and the balance (the Dieta tab)."""
    try:
        progress = await hub.call_json("nutrition__get_goal_progress", {})
        training = await fitness.status(hub, settings, weeks=1, weight_kg=(progress.get("weight") or {}).get("current"))
        base = await fitness.sync_goals(hub, settings, progress, training["today_kcal"])
        balance = fitness.day_balance(progress, training["today_kcal"], float(settings.get("training.eat_back", 0.6)),
                                      base)
    except Exception as exc:
        return f"(Meal routine: recalculation failed - {type(exc).__name__}: {exc})", None
    return fitness.balance_text(balance, training), balance
