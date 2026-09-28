---
{type: Index, title: Tools, description: 'Every tool the brain can call, by server.',
  timestamp: '2026-09-25T14:22:57+02:00'}
---

# Tools
Every tool the brain can call, by server.
* [confirm_action](alfred/confirm-action.md) - Ask the user for a spoken yes/no before an irreversible step that has no dedicated tool (e.g. pressing the final 'Book' 
* [memory_read](alfred/memory-read.md) - Read one page of Alfred's memory by the path returned from memory_search (e.g. 'sessions/2026/09/s-....md', 'tasks/<id>.
* [memory_remember](alfred/memory-remember.md) - Store a durable fact about the user (a person, place, preference or project) for future sessions.
* [memory_search](alfred/memory-search.md) - Search Alfred's own memory (past sessions, tasks, facts about the user) by keywords. Returns titles, descriptions and pa
* [task_create](alfred/task-create.md) - Create a task or reminder Alfred should do or remind about later. Use `due` (ISO 8601 with timezone) for a one-off momen
* [task_list](alfred/task-list.md) - List tasks Alfred tracks for the user. status: open (default), all, or one status.
* [task_update](alfred/task-update.md) - Update a task: change status (todo, in_progress, waiting, done, cancelled), due date, schedule, or add a progress note.
* [web_fetch](anthropic/web-fetch.md) - Fetch and read a web page by URL.
* [web_search](anthropic/web-search.md) - Search the web for current information.
* [kb_audit](knowledge-base/kb-audit.md) - OKF conformance and index integrity -- the checks kb_health does not do: unparseable frontmatter, missing or out-of-voca
* [kb_due](knowledge-base/kb-due.md) - Spaced-review queue, computed from the `covered:` field on Training Session pages and the bundle's interval table. Prese
* [kb_find](knowledge-base/kb-find.md) - Start here for any question about the bundle's subject matter. Returns ranked candidate pages with trust fields, matched
* [kb_graph](knowledge-base/kb-graph.md) - Structure rather than content. With an id: inbound links (the blast radius of changing that page), outbound links by rel
* [kb_health](knowledge-base/kb-health.md) - Graph-level state: the frontier (wanted but unwritten pages, ranked by how many pages want each -- a work queue, never a
* [kb_list](knowledge-base/kb-list.md) - Frontmatter query across the bundle -- use when the question cuts across pages rather than pointing at one: everything o
* [kb_pending](knowledge-base/kb-pending.md) - The ingest work queue: raw sources that no Source Summary covers yet, and summaries whose source file has gone missing. 
* [kb_read](knowledge-base/kb-read.md) - Read one page in full: frontmatter, body, trust fields, its `# Requires` chain in learning order, and any recorded contr
* [kb_source](knowledge-base/kb-source.md) - The immutable raw sources beside the bundle. With no id: list them. With an id: read one, if it is a text format. Expose
