# Alfred — personal assistant brain

You talk, Alfred listens, does the work with the right tools, and answers you out loud — then remembers what he
did so the next session picks up where this one ended.

```
 mic ─► Ears (ElevenLabs Scribe) ─► Shield + Router (Jev) ─► Executor (Claude + only this module's tools)
                                                                        │        ├─ MCP: Calendar, Strava, Nutrition, Browser…
                                                                        │        ├─ built-in: tasks, memory
                                                                        │        └─ Guard: spoken "yes" before booking/sending
                                                                        ▼
                             Session memory (OKF) ◄── Voice (ElevenLabs) ◄── answer
                                    ▲
                          Proactive scheduler (due tasks, cron) ─► Jev gate "worth interrupting?" ─► Alfred speaks first
```

## Quick start

You need [uv](https://docs.astral.sh/uv/) and [Claude Code](https://claude.com/claude-code), logged in with your
Claude subscription (run `claude` once). Then, in the cloned folder:

```bash
uv run alfred
```

That is the only command. It installs what is missing, starts Alfred on http://127.0.0.1:8765 and, on the first
start, opens your browser. A start screen checks Claude Code and asks for the `JEV_API_KEY` (required - Jev is the
shield and the router) and optionally `ELEVENLABS_API_KEY` (Alfred's voice; without it the browser's voice is used);
it saves them in `.env`. Then Alfred walks you through the rest in the chat: your name, how he addresses you,
language, timezone, task categories, goals, which modules and integrations you want, and his first routines. You
can change all of it later - just tell him ("zmień moje kategorie", "włącz moduł treningów") or use the tabs.

Other entry points: `uv run alfred chat` (terminal conversation), `uv run alfred classify "zarezerwuj stolik"` (see
how the router classifies a sentence), `uv run alfred serve --port 9000 --no-browser`. Tests: `uv run pytest`.

If Jev's routing fails, Claude Haiku routes; if that fails too, Alfred asks what you mean. Without a Jev key the
shield lets nothing through, so Alfred does nothing with what you say (the log says why).

## Yours vs. the repository

The repository holds only defaults and templates. Everything that is yours lives in `data/` (git-ignored) and `.env`:

| File | What | Template |
|---|---|---|
| `data/settings.json` | your settings - only what differs from `config/brain.yaml` (the setup, the UI and Alfred write it) | `config/brain.yaml` |
| `data/persona.md` | Alfred's character, once you edit it in the Osobowość tab | `config/persona.md` |
| `data/mcp.json` | your MCP servers (copied from the template on the first start, all off) | `config/mcp.json` |
| `data/routines.yaml` | Alfred's routines | - |
| `data/memory/` | his diary: tasks, sessions, facts, your goals | - |
| `data/brain_map/` | the brain map, rebuilt at every start | - |
| `data/logs/` | every event, one JSONL file a day | - |

To start over, stop Alfred and delete `data/` (and `.env` for the keys).

## How it thinks

Start reading at `brain/pipeline.py` → `Brain.handle_text()`: it is the whole story of one request, top to bottom.

| Step | Where | What happens |
|---|---|---|
| Listen | `brain/voice.py` | Scribe transcribes the recording and detects PL/EN |
| Check | `brain/router.py` | the shield asks **only Jev** whether this is a prompt injection. Nothing goes further until it passes; if Jev does not answer, Alfred does nothing (only an error in the log) |
| Classify | `brain/router.py` | **one** Jev call over the categories of the **brain map**: `module`, `capability`, `skill`, `topic` (choices), `urgency` (score), `acts_on_world` and `needs_history` (noul). A close call loads the runner-up module too; a very unsure one makes Alfred ask. |
| Execute | `brain/executor.py` | Claude sees only the tools of the chosen capabilities (plus the skill's and "always" ones), the module prompt and the chosen skill |
| Confirm | `brain/executor.py` (`Guard`) | tools in a `confirm: true` capability, destructive tools (unless their capability says `confirm: false`) and `confirm_action` wait for your spoken "tak" / "nie" |
| Speak | `brain/voice.py` | the answer, 1–3 sentences written to be heard |
| Remember | `brain/memory.py` | turns are kept in the session; after 15 min idle the session is summarised into an OKF page |

The other files: `app.py` (web server + API for the UI), `cli.py` (command line), `config.py` (settings),
`events.py` (event bus + log), `llm.py` (Claude calls), `persona.py` (who Alfred is), `modules.py` (loads
`modules/`), `tools.py` (Alfred's own tools), `mcp_hub.py` (MCP servers), `atlas.py` (brain map),
`scheduler.py` (reminders and routines, the only code that touches `routines.yaml`), `fitness.py` (the training
plan), `meals.py` (logging meals), `okf.py` (Markdown files with a YAML header). Each file starts with a short
note saying what it does.

Settings: `config/brain.yaml` (defaults), plus yours in `data/settings.json` (it wins over the yaml for those keys -
the UI saves only the fields you actually changed).

## Claude account: your subscription

The Claude Agent SDK runs your logged-in Claude Code, so requests count against your Pro/Max plan limits, not
API billing. Alfred's tools are passed in as an in-process MCP server. Claude Code's own tools (Bash, file
editing…) are switched off; only WebSearch/WebFetch stay on, and only when the route needs them. No
`CLAUDE.md`, hooks or settings are loaded. An `ANTHROPIC_API_KEY` in the environment is ignored, so the plan is
always used. Each request starts a Claude Code process, which adds roughly 1–2 s.

## Brain map: what the brain is connected to (`data/brain_map/`, OKF)

`brain/atlas.py` compiles `modules/*/module.yaml`, the skills, the **live** tool lists of the MCP servers and the
topics of your knowledge library into an OKF bundle. It is rebuilt at every start, from the **Mapa** tab, or
with `POST /api/map/rebuild`.

```
data/brain_map/
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
keeps that edit and any `## Notes` section. Whether a tool needs your "yes" comes only from the module
manifest (`confirm:` of its capability). Tools of a server that is offline stay on the map, marked `offline`.

Capabilities are defined per module:

```yaml
capabilities:
  write:
    label: Change the calendar
    description: Create, move, update, cancel events and answer invitations.
    tools: ["google-calendar__create-*", "google-calendar__update-*"]   # patterns over live tool names
    examples: ["przesuń spotkanie na piątek"]
    confirm: true      # every tool here needs a "yes"; false: none does, not even a destructive one;
                       # left out: only the tools the server marks destructive
uses: [tasks.manage, memory.recall]                                     # borrowed from other modules
```

## Personality and role (`config/persona.md` → `data/persona.md`)

Who Alfred is lives in one OKF file that you can edit in the **Osobowość** tab (saved to `data/persona.md`; until
then the template `config/persona.md` is used):
- **Frontmatter:** the confirmation question (PL/EN).
- **Markdown body:** the system prompt, with sections *Role*, *Character*, *How you speak* and *How you work*.
  `{name}`, `{user}`, `{addr_pl}` and `{addr_en}` are filled in from the settings (`assistant.name`,
  `assistant.user_name`, `assistant.address`), which the setup asks you for.

Changes apply from the next request.

## Session memory (separate from the Knowledge-Base)

Your knowledge library (if you connect one as the `knowledge-base` MCP server) is what Alfred knows; he reads it
read-only. `data/memory/` is **his own diary** of what he does, stored as an OKF bundle:

```
data/memory/
  index.md                   entry point, regenerated on every change
  log.md                     append-only change log (task.created, task.updated, fact.created, session.closed …)
  profile.md
  goals.md                   your goals and resolutions (Cele)
  tasks/<id>.md              type: Task — status todo | in_progress | done | cancelled, due, cron schedule
  sessions/YYYY/MM/<id>.md   type: Session — summary, done, changed, open threads, token usage
  facts/<category>/*.md      type: Fact — people, places, preferences, projects
```

At the start of every session Alfred gets a **briefing** of a few hundred tokens: open and overdue tasks, the
last sessions with their open threads, and everything in `log.md` that changed since the last session.
He does not replay old transcripts.

## Logging

Every event (transcript, route, each LLM call with token usage, each tool call and result, confirmations,
proactive decisions, errors) goes to `data/logs/YYYY-MM-DD.jsonl`, and you can browse it in the **Log** tab.
When Jev or Claude fail and a fallback is taken, the event says why (`error` on `classified`, `shield`,
`tasks_classified`). Memory changes are also written in human-readable form to `data/memory/log.md`.

## Modules

A module is a folder in `modules/`:

```
modules/bookings/
  module.yaml      label/description/examples (these become the Jev criteria), capabilities (tool patterns,
                   confirm, always), uses, model/effort, enabled
  prompt.md        instructions for the executor when this module is active
  skills/*.md      procedures (frontmatter name + description become the Jev skill criteria)
```

Included modules: `setup` (the first-run setup, later changes to it), `calendar`, `knowledge`, `tasks`, `memory`,
`research` (web search), `bookings`
(restaurant-table skill), `training` (triathlon plan from Strava, planned around work - training-week skill),
`weight` (meals, weigh-ins and goals in Nutrition MCP; Jev picks each logged meal's type - weight-goal skill) and
`smalltalk`. Modules that need an outside service (`calendar`, `knowledge`, `training`, `weight`, `bookings`)
ship switched off; the setup or the **Moduły** tab switches them on (saved in `data/settings.json → modules`). To add
a capability, add a folder and press reload, or restart.

**Treningi** (Zadania → Treningi, `GET /api/training`, `brain/fitness.py`): the plan from `config/brain.yaml →
training` (race, weekly hours per sport, 80/20 heart-rate limit) scaled by the season phase (base / build / peak /
taper, 3:1 recovery weeks counted back from the race), what Strava says is done, the work week (meetings + work
tasks due: a heavy week = 20-30% less training), estimated kcal per workout (power, else ~1 kcal/kg/km running,
else MET) and the daily steps you tell Alfred (`steps_log`, `data/memory/steps.json`, goal `training.steps_goal`).

**Droga do startu** (Treningi): the season's phases with focus, milestones and this week's concrete sessions
(minutes from your weekly hours; strength periodised per `docs/triathlon-motor-prep.md`). Training events Alfred
puts in the calendar end with `training.mark` - that is how they are found again. **Plan changes**: say
what you want (or use "Chcę coś zmienić w planie") - Jev classifies the change type, the discipline and whether it
adds load, each answer picks a fixed procedure block in the prompt (`fitness.PLAN_*`, the race taken from the plan):
research, 3 options, a recommendation; `training_plan_update` changes the plan only after your yes, and the change
with its reason goes to `data/memory/log.md` (the next briefing shows it).

**Dieta** (Zadania → Dieta, `GET /api/diet`): today's kcal and macros against the Nutrition MCP goals - raised on a
training day by 60% of the burnt kcal (`training.eat_back`) - and the log of what you said, the meal type Jev picked
and what was saved (`nutrition_logged` events). The meal routine: after every `log_meal` the executor recalculates
the day and the week's training sessions left and hands it to Claude in the same answer (`brain/meals.py`). The
base goals Alfred raises live in `data/nutrition_sync.json`.

## MCP servers — `data/mcp.json`

Your copy of `config/mcp.json`, made on the first start with every server off. Alfred switches one on when you ask
for it in the setup (or set `"enabled": true` yourself); it connects after a restart.

- **google-calendar** (module `calendar`): needs Node.js. Create a Google Cloud OAuth client (Desktop app, Calendar
  API enabled, your e-mail added as a test user), save the JSON and put its path in `GOOGLE_OAUTH_CREDENTIALS`, sign
  in once with `npx @cocal/google-calendar-mcp auth` (with that variable set). The same connection feeds the
  **Kalendarz** page (`GET /api/calendar`). In test mode Google tokens expire after 7 days; run `auth` again.
- **strava** (module `training`): `server/strava_server.py`, a small stdio server of our own. Put
  `STRAVA_CLIENT_ID` / `STRAVA_CLIENT_SECRET` of your [Strava API app](https://www.strava.com/settings/api) in `.env`
  (callback domain `localhost`) and log in once: `uv run python server/strava_server.py --login`. The token lives in
  `~/.config/strava-mcp/token.json` and refreshes itself.
- **nutrition** (module `weight`): the remote [Nutrition MCP](https://github.com/akutishevsky/nutrition-mcp). Log in
  once with `uv run alfred mcp-login nutrition` (the browser opens); tokens are kept in `data/oauth/nutrition.json`.
- **knowledge-base** (module `knowledge`): your own notes as an MCP server with `kb_find`, `kb_read`, `kb_list` …
  tools - put its command in. Its topics can go on the brain map: `map.topic_sources` in your settings.
- **browser** (module `bookings`): Playwright MCP. Needs Node.js.

Claude.ai connectors themselves are not visible to Alfred (`strict_mcp_config`).

## Proactive

The scheduler runs inside the brain:
- every minute it checks for due tasks;
- recurring tasks run as cron jobs;
- idle sessions are closed.

Before Claude is woken, Jev answers one question: is this worth interrupting you for? This takes the time,
your quiet hours (`23:00–07:00`) and when you last spoke into account. Only a "yes" calls Claude, and every
decision is logged. To try it, say *"przypomnij mi za 2 minuty, żeby się napić wody"* and keep the UI open.

**Routines** (`data/routines.yaml`) are things Alfred does on his own, without the gate: at a set time
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
  (skills, routines), modules, and Alfred's personality at the crown. Each level keeps its
  contents in folders. White threads fire like neurons, the levels that are working light up, and events
  travel as labelled packets. Click a level or a node to see what it is; **▶ Pokaż przepływ** plays a sample
  restaurant booking without any API keys. The side tabs hold memory, the brain map, persona, modules, the
  log and settings.
