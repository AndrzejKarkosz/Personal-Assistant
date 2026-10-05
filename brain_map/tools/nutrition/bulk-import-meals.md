---
type: Tool
title: bulk_import_meals
description: Import many past meals in one call, for backfilling history from a file
  the user exported from another app (MyFitnessPal, Cronometer, Lose It!, MacroFactor)
  or from a list they pasted. Parse the source yourself and map it to the row schema;
id: nutrition__bulk_import_meals
server: nutrition
kind: mcp
short: bulk_import_meals
capabilities: []
modules: []
side_effect: read
requires_confirmation: false
status: online
params: [meals, expected_row_count, expected_total_kcal, dry_run, on_error, rows_skipped,
  unmapped_columns, source_app]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# bulk_import_meals

Import many past meals in one call, for backfilling history from a file the user exported from another app (MyFitnessPal, Cronometer, Lose It!, MacroFactor) or from a list they pasted. Parse the source yourself and map it to the row schema; the server validates every row and reports per-row results, so you can fix and re-send only the rows that failed. Prefer this over calling log_meal in a loop: one call writes up to 50 rows with per-row validation, a dry run and keys that make a replay a no-op while the saved timezone is unchanged, none of which a loop of log_meal calls has. Three rules matter for correctness. (1) Compute expected_row_count, and expected_total_kcal when every row has calories, FROM THE SOURCE FILE using deterministic tooling (a script, or counting the actual lines) — never by re-reading the JSON you just wrote, which would only compare your output against itself and catch nothing. (2) Call once with dry_run: true first whenever the rows came from parsing a CSV, a screenshot, or free text; c

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- not assigned to any capability yet - add a pattern to a module's capabilities

## Parameters
| name | type | required | description |
|---|---|---|---|
| `meals` | array | yes | The rows to import, in source-file order. 1 to 50 per call. |
| `expected_row_count` | number | yes | How many rows THIS call carries, counted from the source file. The server rejects the batch if it disagrees, which is how a dropped or truncated row gets caught |
| `expected_total_kcal` | number |  | Sum of calories across this call's rows, from the source file. Supply it whenever every row has calories; the server reconciles it within 0.5%. |
| `dry_run` | boolean |  | Validate and report what would happen without writing anything. |
| `on_error` | string |  | continue: import the valid rows and report the rest. abort: if ANY row fails validation, write nothing. Note writes are not transactional — once writing starts, |
| `rows_skipped` | number |  | How many source rows you deliberately did not send (deleted entries, totals rows, unparseable lines). Explains gaps in source_line so they are not reported as d |
| `unmapped_columns` | array |  | Source columns you could not map to any field. Report them here rather than inventing a place for them. |
| `source_app` | string |  | Which app the file came from, e.g. myfitnesspal. Used to label rows that have no food name of their own. |
