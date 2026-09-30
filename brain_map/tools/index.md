---
{type: Index, title: Tools, description: 'Every tool the brain can call, by server.',
  timestamp: '2026-09-29T19:36:03+02:00'}
---

# Tools
Every tool the brain can call, by server.
* [confirm_action](alfred/confirm-action.md) - Ask the user for a spoken yes/no before an irreversible step that has no dedicated tool (e.g. pressing the final 'Book' 
* [memory_read](alfred/memory-read.md) - Read one page of Alfred's memory by the path returned from memory_search (e.g. 'sessions/2026/09/s-....md', 'tasks/<id>.
* [memory_remember](alfred/memory-remember.md) - Store a durable fact about the user (a person, place, preference or project) for future sessions.
* [memory_search](alfred/memory-search.md) - Search Alfred's own memory (past sessions, tasks, facts about the user) by keywords. Returns titles, descriptions and pa
* [task_create](alfred/task-create.md) - Create tasks or reminders Alfred should do or remind about later. Always pass a `tasks` list - several tasks go in ONE c
* [task_list](alfred/task-list.md) - List tasks Alfred tracks for the user. status: open (default), all, or one status.
* [task_update](alfred/task-update.md) - Update a task: change status (todo, in_progress, waiting, done, cancelled), due date, schedule, category, or add a progr
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
