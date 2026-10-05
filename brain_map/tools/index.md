---
{type: Index, title: Tools, description: 'Every tool the brain can call, by server.',
  timestamp: '2026-10-05T10:16:01+02:00'}
---

# Tools
Every tool the brain can call, by server.

* [confirm_action](alfred/confirm-action.md) - Ask the user for a spoken yes/no before an irreversible step that has no dedicated tool (e.g. pressing the final 'Book' 
* [memory_read](alfred/memory-read.md) - Read one page of Alfred's memory by the path returned from memory_search (e.g. 'sessions/2026/09/s-....md', 'tasks/<id>.
* [memory_remember](alfred/memory-remember.md) - Store a durable fact about the user (a person, place, preference or project) for future sessions.
* [memory_search](alfred/memory-search.md) - Search Alfred's own memory (past sessions, tasks, facts about the user) by keywords. Returns titles, descriptions and pa
* [routine_delete](alfred/routine-delete.md) - Remove a routine by its id.
* [routine_save](alfred/routine-save.md) - Create a routine or change an existing one (same id): a prompt Alfred runs by himself on a schedule. Only for routines -
* [steps_log](alfred/steps-log.md) - Save how many steps the user walked on a day (he tells you; a later number for the same day replaces it). Returns the da
* [task_category_add](alfred/task-category-add.md) - Add a NEW task category. Only when the user clearly wants a category that is not in the fixed list; the user is asked fo
* [task_create](alfred/task-create.md) - Create tasks or reminders Alfred should do or remind about later. Always pass a `tasks` list - several tasks go in ONE c
* [task_list](alfred/task-list.md) - List tasks Alfred tracks for the user. status: open (default), all, or one status.
* [task_update](alfred/task-update.md) - Update a task: change status (todo, in_progress, done, cancelled), due date, schedule, category, title, or add a progres
* [training_plan_update](alfred/training-plan-update.md) - Change the user's training plan after he agreed to a proposal: the race, weekly sessions and hours per sport (swim, bike
* [training_status](alfred/training-status.md) - The user's triathlon plan and how it goes: the race and days to it, the season phase (base, build, peak, taper, recovery
* [web_fetch](anthropic/web-fetch.md) - Fetch and read a web page by URL.
* [web_search](anthropic/web-search.md) - Search the web for current information.
* [create-event](google-calendar/create-event.md) - Create a new calendar event.
* [create-events](google-calendar/create-events.md) - Create multiple calendar events in bulk. Accepts shared defaults (account, calendarId, timeZone) that apply to all event
* [delete-event](google-calendar/delete-event.md) - Delete a calendar event.
* [get-current-time](google-calendar/get-current-time.md) - Get the current date and time. Call this FIRST before creating, updating, or searching for events to ensure you have acc
* [get-event](google-calendar/get-event.md) - Get details of a specific event by ID.
* [get-freebusy](google-calendar/get-freebusy.md) - Query free/busy information for calendars. Note: Time range is limited to a maximum of 3 months between timeMin and time
* [list-calendars](google-calendar/list-calendars.md) - List all available calendars
* [list-colors](google-calendar/list-colors.md) - List available color IDs and their meanings for calendar events
* [list-events](google-calendar/list-events.md) - List events from one or more calendars. Supports both calendar IDs and calendar names.
* [manage-accounts](google-calendar/manage-accounts.md) - Manage Google account authentication. Actions: 'list' (show accounts), 'add' (authenticate new account), 'remove' (remov
* [respond-to-event](google-calendar/respond-to-event.md) - Respond to a calendar event invitation with Accept, Decline, Maybe (Tentative), or No Response.
* [search-events](google-calendar/search-events.md) - Search for events in a calendar by text query.
* [update-event](google-calendar/update-event.md) - Update an existing calendar event with recurring event modification scope support.
* [kb_audit](knowledge-base/kb-audit.md) - OKF conformance and index integrity -- the checks kb_health does not do: unparseable frontmatter, missing or out-of-voca
* [kb_due](knowledge-base/kb-due.md) - Spaced-review queue, computed from the `covered:` field on Training Session pages and the bundle's interval table. Prese
* [kb_find](knowledge-base/kb-find.md) - Start here for any question about the bundle's subject matter. Returns ranked candidate pages with trust fields, matched
* [kb_graph](knowledge-base/kb-graph.md) - Structure rather than content. With an id: inbound links (the blast radius of changing that page), outbound links by rel
* [kb_health](knowledge-base/kb-health.md) - Graph-level state: the frontier (wanted but unwritten pages, ranked by how many pages want each -- a work queue, never a
* [kb_list](knowledge-base/kb-list.md) - Frontmatter query across the bundle -- use when the question cuts across pages rather than pointing at one: everything o
* [kb_pending](knowledge-base/kb-pending.md) - The ingest work queue: raw sources that no Source Summary covers yet, and summaries whose source file has gone missing. 
* [kb_read](knowledge-base/kb-read.md) - Read one page in full: frontmatter, body, trust fields, its `# Requires` chain in learning order, and any recorded contr
* [kb_source](knowledge-base/kb-source.md) - The immutable raw sources beside the bundle. With no id: list them. With an id: read one, if it is a text format. Expose
* [bulk_import_meals](nutrition/bulk-import-meals.md) - Import many past meals in one call, for backfilling history from a file the user exported from another app (MyFitnessPal
* [delete_account](nutrition/delete-account.md) - Permanently delete the user's Nutrition MCP account and all data this service stores about them (meals, water, weight, b
* [delete_body_measurement](nutrition/delete-body-measurement.md) - Delete a body measurement by ID.
* [delete_meal](nutrition/delete-meal.md) - Delete a meal entry by ID (ids come from get_meals_today, get_meals_by_date, get_meals_by_date_range or search_meals).
* [delete_water](nutrition/delete-water.md) - Delete a water log entry by ID.
* [delete_weight](nutrition/delete-weight.md) - Delete a weight log entry by ID.
* [export_all_data](nutrition/export-all-data.md) - Export EVERYTHING this server stores about the user — meals, water, weight, body measurements, nutrition goals and every
* [get_body_measurements](nutrition/get-body-measurements.md) - Get body measurements between two dates (inclusive), optionally for one site, oldest first and grouped by local day, eac
* [get_current_time](nutrition/get-current-time.md) - Get the current date and time in the user's timezone as saved in this nutrition tracker, plus the UTC instant. Use it to
* [get_goal_progress](nutrition/get-goal-progress.md) - Get progress against daily nutrition goals for a specific date (defaults to today). Renders intake-vs-goal rings plus bo
* [get_meal_patterns](nutrition/get-meal-patterns.md) - Pre-aggregated behavioural patterns across the logged window: meal-type presence rates, breakfast effect (days with vs w
* [get_meals_by_date_range](nutrition/get-meals-by-date-range.md) - Get all meals between two dates (inclusive), grouped by day, one compact line each with ids (detail: "full" adds notes).
* [get_meals_by_date](nutrition/get-meals-by-date.md) - Get all meals for a specific date, one compact line each with ids (detail: "full" adds notes).
* [get_meals_today](nutrition/get-meals-today.md) - Get all meals logged today, one compact line each with ids (detail: "full" adds notes).
* [get_nutrition_goals](nutrition/get-nutrition-goals.md) - Get the user's current daily calorie and macro targets.
* [get_nutrition_summary](nutrition/get-nutrition-summary.md) - Get daily nutrition totals for a date range. Renders an interactive dashboard (macro tiles vs. goals and a per-day break
* [get_profile](nutrition/get-profile.md) - Get the user's current settings in one call: timezone (plus local date and time), widget language, preferred weight unit
* [get_trends](nutrition/get-trends.md) - Rolling 7/14/30-day averages, standard deviation and coefficient of variation for calories, protein, carbs, fat, fiber, 
* [get_water_by_date](nutrition/get-water-by-date.md) - Get water intake total and entries for a specific date.
* [get_water_today](nutrition/get-water-today.md) - Get today's total water intake (ml) and the list of entries.
* [get_weight_by_date_range](nutrition/get-weight-by-date-range.md) - Get all weight entries between two dates (inclusive), grouped by day with each day's average. Use this instead of multip
* [get_weight_by_date](nutrition/get-weight-by-date.md) - Get weight entries for a specific date, in the user's preferred unit.
* [get_weight_today](nutrition/get-weight-today.md) - Get today's weight entries, shown in the user's preferred unit.
* [get_weight_trends](nutrition/get-weight-trends.md) - Weight trend over a window: latest reading, overall change, a smoothed trend weight with its weekly rate over the last 2
* [log_body_measurement](nutrition/log-body-measurement.md) - Log one body circumference measurement — waist, hips, neck, chest, shoulders, upper arm, forearm, thigh or calf — in cen
* [log_meal](nutrition/log-meal.md) - Log a meal entry with nutritional information. It needs the quantity or portion eaten; if the user has not given it, ask
* [log_water](nutrition/log-water.md) - Log a hydration entry in milliliters. If the user gives a volume in another unit (cups, oz, liters), convert it: 1 cup =
* [log_weight](nutrition/log-weight.md) - Log a body-weight measurement. Provide the number in `weight` and its `unit` ('kg' or 'lb'); if you omit the unit, the u
* [lookup_barcode](nutrition/lookup-barcode.md) - Look up a packaged product's label nutrition by barcode via Open Food Facts. The figures come from the product's own lab
* [search_meals](nutrition/search-meals.md) - Search the user's past logged meals by keyword (case-insensitive match on description and notes), newest first, grouped 
* [set_alcohol_tracking](nutrition/set-alcohol-tracking.md) - Turn alcohol tracking on or off for the user, and optionally choose whether drinks are counted in US standard drinks (14
* [set_language](nutrition/set-language.md) - Set the user's UI language for in-chat widgets (dashboards, charts). Supported: 'en' (English), 'de' (Deutsch), 'es' (Es
* [set_length_unit](nutrition/set-length-unit.md) - Set the user's preferred length unit for body measurements ('cm' or 'in'), or pass null to clear it. It decides how meas
* [set_nutrition_goals](nutrition/set-nutrition-goals.md) - Set the user's daily calorie and macro targets, and optionally a target body weight. Pass only the fields you want to up
* [set_timezone](nutrition/set-timezone.md) - Set the user's IANA timezone (e.g. 'America/Los_Angeles', 'Europe/Berlin', 'Asia/Tokyo'). It decides which calendar day 
* [set_weight_unit](nutrition/set-weight-unit.md) - Set the user's preferred weight unit ('kg' or 'lb'), or pass null to clear it. This controls how weights are shown and h
* [set_widget_display](nutrition/set-widget-display.md) - Enable or disable the in-chat visual widgets (nutrition dashboard, goal progress, meal-logged rings, trends, weight char
* [start_meal_import](nutrition/start-meal-import.md) - Open an importer the user can drive themselves to load a meal-history export (MyFitnessPal, Cronometer, Lose It!, MacroF
* [update_body_measurement](nutrition/update-body-measurement.md) - Update an existing body measurement's value, unit, time or notes. The site (kind) cannot be changed; a measurement of a 
* [update_meal](nutrition/update-meal.md) - Update fields of an existing meal entry. Only the fields you pass are changed, which also makes this the way to backfill
* [update_weight](nutrition/update-weight.md) - Update fields of an existing weight entry. Provide `unit` alongside `weight` (defaults to the user's preferred unit); do
* [activities](strava/activities.md) - The user's Strava activities between two dates (YYYY-MM-DD, both included), oldest first, as JSON. Each has
sport (swim
