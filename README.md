# Alfred — personal assistant brain

You talk, Alfred listens, says *"Oczywiście, szefie. Już się tym zajmuję."*, does the work with the right
tools, and answers you out loud — then remembers what he did so the next session picks up where this one ended.

```
 mic ─► Ears (ElevenLabs Scribe) ─► Router (Jev) ─► "On it, boss" ─► Executor (Claude + only this module's tools)
                                                                        │        ├─ MCP: Knowledge-Base, Calendar, Browser…
                                                                        │        ├─ built-in: tasks, memory
                                                                        │        └─ Guard: spoken "yes" before booking/sending
                                                                        ▼
                             Session memory (OKF) ◄── Voice (ElevenLabs) ◄── answer
                                    ▲
                          Proactive scheduler (due tasks, cron) ─► Jev gate "worth interrupting?" ─► Alfred speaks first
```

The full design and roadmap is in [docs/PLAN.md](docs/PLAN.md).

## Quick start

1. Install dependencies (Python 3.11+, [uv](https://docs.astral.sh/uv/)):
   ```bash
   uv sync --native-tls
   ```
2. Make sure Claude Code is logged in with your subscription (`claude auth status` shows `claude.ai`). Alfred
   runs Claude through it, so there is no per-token billing.
3. Paste `JEV_API_KEY` and `ELEVENLABS_API_KEY` (optionally `ELEVENLABS_VOICE_ID`) into `.env`.
4. Run it:
   ```bash
   uv run alfred serve
   ```
   Open http://127.0.0.1:8765. Hold **Space** (or click the mic) to talk, or type.

Other entry points: `uv run alfred chat` (terminal conversation) and `uv run alfred classify "zarezerwuj stolik"`
(see how the router classifies a sentence). Tests: `uv run pytest`.

Every key is optional for a first look. Without Jev the router falls back to Claude Haiku, then keyword rules.
Without ElevenLabs the UI uses the browser's speech recognition and voice.

## How it thinks

Start reading at `brain/pipeline.py` → `Brain.handle_text()`: it is the whole story of one request, top to bottom.

| Step | Where | What happens |
|---|---|---|
| Listen | `brain/voice.py` | Scribe transcribes the recording and detects PL/EN |
| Check | `brain/router.py` | the shield asks **only Jev** whether this is a prompt injection. Nothing goes further until it passes; if Jev does not answer, Alfred does nothing (only an error in the log) |
| Classify | `brain/router.py` | **one** Jev call over the categories of the **brain map**: `module`, `capability`, `skill`, `topic` (choices), `urgency` (score), `acts_on_world` and `needs_history` (noul). A close call loads the runner-up module too; a very unsure one makes Alfred ask. |
| Execute | `brain/executor.py` | Claude sees only the tools of the chosen capabilities (plus the skill's and "always" ones), the module prompt and the chosen skill |
| Confirm | `brain/executor.py` (`Guard`) | tools in a `confirm: true` capability, destructive tools and `confirm_action` wait for your spoken "tak" / "nie" |
| Speak | `brain/voice.py` | the answer, 1–3 sentences written to be heard |
| Remember | `brain/memory.py` | turns are kept in the session; after 15 min idle the session is summarised into an OKF page |

The other files: `app.py` (web server + API for the UI), `cli.py` (command line), `config.py` (settings),
`events.py` (event bus + log), `llm.py` (Claude calls), `persona.py` (who Alfred is), `modules.py` (loads
`modules/`), `tools.py` (Alfred's own tools), `mcp_hub.py` (MCP servers), `atlas.py` (brain map),
`scheduler.py` (reminders and routines), `okf.py` (Markdown files with a YAML header). Each file starts with a
short note saying what it does.

## Claude account: your subscription

The Claude Agent SDK runs your logged-in Claude Code, so requests count against your Pro/Max plan limits, not
API billing. Alfred's tools are passed in as an in-process MCP server. Claude Code's own tools (Bash, file
editing…) are switched off; only WebSearch/WebFetch stay on, and only when the route needs them. No
`CLAUDE.md`, hooks or settings are loaded. An `ANTHROPIC_API_KEY` in the environment is ignored, so the plan is
always used. Each request starts a Claude Code process, which adds roughly 1–2 s.

## Brain map: what the brain is connected to (`brain_map/`, OKF)

`brain/atlas.py` compiles `modules/*/module.yaml`, the skills, the **live** tool lists of the MCP servers and the
topics of your knowledge library into an OKF bundle. It is rebuilt at every start, from the **Mapa** tab, or
with `POST /api/map/rebuild`.

```
brain_map/
  index.md  log.md                     overview, and what changed between builds
  modules/<id>.md                      Module      --has--> capabilities, --uses--> other modules' capabilities
  capabilities/<module>.<name>.md      Capability  --includes--> tools   (Jev's routing categories)
  skills/<module>.<skill>.md           Skill       --uses--> capabilities
  tools/<server>/<tool>.md             Tool        --served by--> server; side effect, confirmation, parameters
  servers/<name>.md                    MCP server / Alfred's built-ins / Claude server tools, status
  topics/<server>/<slug>.md            Topic of the knowledge library --lives in--> server
```

Relations are both markdown links, which you can follow in Obsidian or on GitHub, and ids in the
frontmatter, which the router reads. **Jev's categories are taken from these pages.** To change how
something is routed, edit the module manifest, or add `examples_extra:` to a capability page; a rebuild
keeps that edit, along with `confirm_override`, `side_effect_override` and any `## Notes` section. Tools of
a server that is offline stay on the map, marked `offline`.

Capabilities are defined per module:

```yaml
capabilities:
  write:
    label: Change the calendar
    description: Create, move, update, cancel events and answer invitations.
    tools: ["google-calendar__create-*", "google-calendar__update-*"]   # patterns over live tool names
    examples: ["przesuń spotkanie na piątek"]
    confirm: true                                                       # every tool here needs a "yes"
uses: [tasks.manage, memory.recall]                                     # borrowed from other modules
```

Note: `brain_map/topics/` lists the titles and descriptions of your knowledge-base topics. If this repository
is public, add `brain_map/topics/` to `.gitignore`.

## Personality and role (`config/persona.md`)

Who Alfred is lives in one OKF file that you can edit directly or in the **Osobowość** tab:
- **Frontmatter:** his name, your name, how he addresses you (PL/EN), the acknowledgement phrases and the
  confirmation question.
- **Markdown body:** the system prompt, with sections *Role*, *Character*, *How you speak* and *How you work*.
  `{name}`, `{user}`, `{addr_pl}` and `{addr_en}` are filled in.

Changes apply from the next request.

## Session memory (separate from the Knowledge-Base)

`E:\Knowledge-Base` is the **library** of what Alfred knows. He reads it through its MCP server, read-only.
`data/memory/` is **his own diary** of what he does, stored as an OKF bundle:

```
data/memory/
  index.md                   entry point, regenerated on every change
  log.md                     append-only change log (task.created, task.updated, fact.created, session.closed …)
  profile.md
  tasks/<id>.md              type: Task — status todo | in_progress | waiting | done | cancelled, due, cron schedule
  sessions/YYYY/MM/<id>.md   type: Session — summary, done, changed, open threads, token usage
  facts/<category>/*.md      type: Fact — people, places, preferences, projects
```

At the start of every session Alfred gets a **briefing** of a few hundred tokens: open and overdue tasks, the
last sessions with their open threads, and everything in `log.md` that changed since the last session.
He does not replay old transcripts.

## Logging

Every event (transcript, route, acknowledgement, each LLM call with token usage, each tool call and result,
confirmations, proactive decisions, errors) goes to `data/logs/YYYY-MM-DD.jsonl`, and you can browse it in
the **Log** tab. Memory changes are also written in human-readable form to `data/memory/log.md`.

## Modules

A module is a folder in `modules/`:

```
modules/bookings/
  module.yaml      label/description/examples (these become the Jev criteria), mcp_servers, builtin_tools,
                   server_tools, confirm patterns, model/effort, acknowledge
  prompt.md        instructions for the executor when this module is active
  skills/*.md      procedures (frontmatter name + description become the Jev skill criteria)
```

Included modules: `calendar`, `knowledge`, `tasks`, `memory`, `research` (web search), `bookings`
(restaurant-table skill), and `smalltalk` (no acknowledgement). To add a capability, add a folder and
press reload, or restart.

## MCP servers — `config/mcp.json`

- **knowledge-base**: enabled, runs `E:/Knowledge-Base/server/kb_server.py` read-only.
- **google-calendar**: disabled. Create a Google Cloud OAuth client (Desktop app, Calendar API enabled, your
  e-mail added as a test user), save the JSON to the path in `GOOGLE_OAUTH_CREDENTIALS`, sign in once with
  `npx @cocal/google-calendar-mcp auth` (with that variable set), then set `"enabled": true` and restart. The
  same connection feeds Claude's calendar tools and the calendar in the **Dzień** view (`GET /api/calendar`).
  In test mode Google tokens expire after 7 days; run the `auth` command again.
- **browser**: disabled. Playwright MCP for bookings. Needs Node.js; set `"enabled": true`.

## Proactive

The scheduler runs inside the brain:
- every minute it checks for due tasks;
- recurring tasks run as cron jobs;
- idle sessions are closed;
- a heartbeat runs every 30 min.

Before Claude is woken, Jev answers one question: is this worth interrupting you for? This takes the time,
your quiet hours (`23:00–07:00`) and when you last spoke into account. Only a "yes" calls Claude, and every
decision is logged. To try it, say *"przypomnij mi za 2 minuty, żeby się napić wody"* and keep the UI open.

**Routines** (`config/routines.yaml`) are things Alfred does on his own, without the gate: at a set time
(`schedule: "0 8 * * 1-5"`, cron) or once every time the app starts (`schedule: "@start"`). Each one is a
`prompt` written as if you said it, plus an optional `module`. Edits apply within a minute. Whatever
Alfred says while the UI is closed waits for you, and you get it when you open the app.

## The UI

Two views, switched in the header. In both: the **to-do list** and today's **routines** on the left (✓ ran,
✗ failed or missed, ○ next run), the **conversation** at the bottom, and next to it how **Jev classified** the
last request — module, capabilities and signals (urgency, acts on the world, needs memory) as probability
bars. The speaker icon on the right of the header lights up while Alfred talks; click it to stop him.

- **Dzień**: the week in Google Calendar together with tasks that have a due time (click an empty slot to ask
  Alfred to add an event there), a summary of the day with *Brief dnia* / *Podsumuj tydzień*, and the
  summaries of recent sessions.
- **Mózg 3D**: the app as a brain. Every vertical level is one part of it, bottom to top: the brainstem
  (the pipeline: ears, router, executor, guard, voice), memory, knowledge, MCP servers, the technical brain
  (skills, routines, code, tests), modules, and Alfred's personality at the crown. Each level keeps its
  contents in folders. White threads fire like neurons, the levels that are working light up, and events
  travel as labelled packets. Click a level or a node to see what it is; **▶ Pokaż przepływ** plays a sample
  restaurant booking without any API keys. The side tabs hold memory, the brain map, persona, modules, the
  log and settings.
