---
type: Tool
title: set_alcohol_tracking
description: Turn alcohol tracking on or off for the user, and optionally choose whether
  drinks are counted in US standard drinks (14 g of ethanol) or UK units (7.9 g).
  Off by default. Alcohol grams passed to log_meal, update_meal or bulk_import_meals
  a
id: nutrition__set_alcohol_tracking
server: nutrition
kind: mcp
short: set_alcohol_tracking
capabilities: []
modules: []
side_effect: read
requires_confirmation: false
status: online
params: [enabled, drink_unit]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# set_alcohol_tracking

Turn alcohol tracking on or off for the user, and optionally choose whether drinks are counted in US standard drinks (14 g of ethanol) or UK units (7.9 g). Off by default. Alcohol grams passed to log_meal, update_meal or bulk_import_meals are stored either way — this setting controls whether alcohol is shown in meals, goals and progress. One exception, which matters BEFORE a backfill: the file importer (start_meal_import) skips the file's alcohol column entirely while tracking is off, because it will not write a figure the user was never shown for review — and re-importing the same file later does not backfill it. So if the user wants alcohol from an export, turn this on first. Offer it when the user asks to track drinking; do not enable it on your own initiative, and if they ask to stop seeing alcohol, disable it here rather than deleting their meals. The change is live immediately — the next tool call in this same conversation already honours it, with nothing to reconnect or restart.

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- not assigned to any capability yet - add a pattern to a module's capabilities

## Parameters
| name | type | required | description |
|---|---|---|---|
| `enabled` | boolean | yes | true to show alcohol in meals, goals and progress; false to hide it (stored values are kept either way). |
| `drink_unit` | string |  | Which standard drink to show alongside grams: 'us' (14 g per drink) or 'uk' (7.9 g per unit). Defaults to 'us' when never set. Ask the user rather than inferrin |
