---
type: Tool
title: start_meal_import
description: 'Open an importer the user can drive themselves to load a meal-history
  export (MyFitnessPal, Cronometer, Lose It!, MacroFactor). Prefer this over bulk_import_meals
  whenever the user has an actual file: the importer reads and maps it in the b'
id: nutrition__start_meal_import
server: nutrition
kind: mcp
short: start_meal_import
capabilities: []
modules: []
side_effect: read
requires_confirmation: false
status: online
params: []
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# start_meal_import

Open an importer the user can drive themselves to load a meal-history export (MyFitnessPal, Cronometer, Lose It!, MacroFactor). Prefer this over bulk_import_meals whenever the user has an actual file: the importer reads and maps it in the browser, so the rows never pass through you and cannot be mistranscribed, and it handles column mapping, batching and retries. Call it when the user says they want to import, upload, or bring in their history from another app. Fall back to bulk_import_meals if the user cannot use the importer, if they have already pasted the data into the conversation, or if the importer reports that this client will not let it save. If the user has alcohol tracking off but wants alcohol from the file, turn it on with set_alcohol_tracking BEFORE importing: the importer skips the alcohol column while tracking is off, and re-importing afterwards will not backfill it.

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- not assigned to any capability yet - add a pattern to a module's capabilities
