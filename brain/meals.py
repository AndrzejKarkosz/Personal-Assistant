"""Logging what he eats in Nutrition MCP. Jev decides - the meal type, and which of his regular products the food is
(or "other") - the system writes those decisions into the nutrition__log_meal call, Claude only estimates the numbers.
After every logged meal comes the meal routine: today's intake against the goals, raised by today's training.

The executor calls fill_in() before the call and after_meal() after it.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Awaitable, Callable

from . import fitness
from .router import OTHER_PRODUCT

log = logging.getLogger("alfred.meals")


def grams_said(text: str) -> float | None:
    """The amount he gave in digits: "150 g", "0,5 kg", "250 ml" (ml counted as grams). None if he gave none.
    ponytail: digits only and the first amount; "sto pięćdziesiąt gramów" or two products in one sentence fall back
    to the product's usual portion / Claude."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|kilo\w*|g|gr|gram\w*|ml|mililitr\w*)\b", text, re.I)
    if not m:
        return None
    value = float(m.group(1).replace(",", "."))
    return value * 1000 if m.group(2).lower().startswith("k") else value


def regular_product(store, picked: str | None) -> dict | str | None:
    """Jev's product answer (Route.product): his regular product itself, "other", or None (no answer / no products)."""
    if picked == OTHER_PRODUCT:
        return OTHER_PRODUCT
    return next((p for p in store.products() if p["name"] == picked), None)


def product_note(product: dict | str, said: str) -> str:
    """Fixed templates for Claude: his regular product with its grams, or "other" = log exactly what he said.
    Claude only adds the calories and macros."""
    if product == OTHER_PRODUCT:
        return ("<product jev=\"other\">None of his regular products. For nutrition__log_meal the description is "
                "exactly what he said (the system puts his words in); estimate the nutrition from it.</product>")
    told, usual = grams_said(said), product.get("grams")
    grams = told or usual
    head = (f"<product jev=\"{product['name']}\">His regular product: {product['name']}"
            + (f" ({product['note']})" if product.get("note") else "") + f", {product['url']}.")
    if not grams:
        return (head + " He gave no amount and the product has no usual portion - ask him how many grams before "
                       "nutrition__log_meal.</product>")
    return (head + f" Amount: {grams:g} g ({'he said it' if told else 'his usual portion'}). For "
            f"nutrition__log_meal the system sets the description to \"{product['name']} ({grams:g} g)\"; you fill "
            f"in calories, protein, carbs, fat, fiber and sugars for exactly {grams:g} g - per 100 g from the "
            "product page (web_fetch the link if you can) or its label, scaled to the grams.</product>")


async def fill_in(args: dict[str, Any], said: str, product: dict | str | None,
                  classify_meal: Callable[[str, str, str], Awaitable[str | None]]) -> str:
    """Jev's decisions into a nutrition__log_meal call: the meal type, and the description - his own words for
    "other", his regular product with its grams. Returns who picked the meal type: "jev", or "claude" (Claude's own
    value stays when Jev cannot answer)."""
    try:
        kind = await classify_meal(said, str(args.get("description", "")), f"{datetime.now():%A %H:%M}")
    except Exception as exc:
        log.warning("Jev did not pick the meal type: %s: %s", type(exc).__name__, exc)
        kind = None
    if kind:
        args["meal_type"] = kind
    if product == OTHER_PRODUCT:
        args["description"] = said
    elif isinstance(product, dict):
        name = product["name"]
        grams = grams_said(said) or product.get("grams")
        if grams:                                    # the template: product + grams; Claude only adds the numbers
            args["description"] = f"{name} ({grams:g} g)"
        elif name.lower() not in str(args.get("description", "")).lower():
            args["description"] = f"{name} - {args.get('description', '')}".rstrip(" -")
        args["notes"] = "\n".join(filter(None, [args.get("notes"), f"Stały produkt: {product['url']}"]))
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
