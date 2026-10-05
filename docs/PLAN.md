# Personal Assistant "Brain" — Master Plan

> **Historical.** This is the plan the project started from. Since 2026-10 the backend is a flat package
> (`brain/*.py`, one file per part - not the `brain/router/`, `brain/executor/` … layout of §5), and there is no
> spoken acknowledgement step. The README describes the code as it is.
>
> Status (2026-09-25): **v0.1 built.** Phases 0–4 plus the proactive core are in place: text and voice
> pipeline, Jev router, acknowledgement, executor with MCP, guard, OKF session memory, activity log,
> scheduler with the Jev gate, and the brain UI. Not yet done: the Google Calendar and browser MCP
> setup (needs your OAuth / Node), phone delivery, and always-on hosting.
> Deviation from the draft: the UI is plain HTML/JS with a 3D brain (three.js) served by FastAPI (no Node build step)
> instead of React Flow. Session memory lives in `data/memory`, separate from the Knowledge-Base.
> Working name for the assistant: **Alfred**. You are Batman.

---

## 0. What we are building (one paragraph)

A local-first "brain" that you **talk to**. It listens (speech-to-text), decides
**what kind of request** it is (typed classification with **Jev**), wakes up only
the **module** that handles that kind of request (calendar, knowledge base,
bookings, …) together with that module's MCP servers and skills, does the work,
remembers what happened in an **OKF memory bundle**, and **answers you out loud**
in Polish or English, in the voice and manner of a discreet butler. A
**proactive layer** runs in the background and speaks up on its own when
something deserves your attention. A **web UI** shows the brain as a live graph
of nodes and lets you tune every part of it.

## 1. First principles

1. **Voice is the primary interface.** Text is the fallback, not the other way round.
2. **Classify before you think.** A cheap typed decision (Jev) picks the module,
   so the expensive LLM only ever sees the tools of *one* module. That is the main
   token saver in the whole design.
3. **Modules, not a monolith.** Every capability is a plug-in module with a
   manifest: its label for the classifier, its MCP servers, its skills, its
   permission rules. You add a capability by adding a folder.
4. **Memory is files.** Sessions and facts are stored in Open Knowledge Format:
   markdown + YAML frontmatter, readable by you in Obsidian and by the brain with
   progressive disclosure (index → category → page).
5. **Ask before acting on the world.** Reading is free; anything that books,
   sends, pays or deletes requires a spoken "yes".
6. **Everything is observable.** Every step emits a trace event (with token
   counts and cost) that the UI draws on the brain graph.

## 2. Architecture overview

```
 ┌──────────── Interfaces ────────────┐
 │ Mic / speaker (desktop)            │
 │ Web UI (brain graph + settings)    │
 │ Phone (Telegram / PWA, later)      │
 └───────────────┬────────────────────┘
                 │ audio / text  (WebSocket)
 ┌───────────────▼────────────────────────────────────────────────┐
 │                          BRAIN (Python)                          │
 │                                                                  │
 │  1 EARS      VAD → streaming STT → transcript (+ language)       │
 │  2 ROUTER    Jev typed decisions: domain, intent, urgency,       │
 │              needs_confirmation, needs_memory   (+ fallback)     │
 │  3 CONTEXT   Memory recall (OKF, progressive) + session state    │
 │  4 EXECUTOR  Claude + ONLY the selected module's tools (MCP)     │
 │  5 GUARD     permission check, spoken confirmation               │
 │  6 VOICE     Alfred persona → short answer → streaming TTS       │
 │  7 MEMORY    write-back: session log, facts, open threads        │
 │                                                                  │
 │  EVENT BUS ──► trace/cost events ──► UI graph, logs              │
 │  PROACTIVE   scheduler + watchers + Jev "should I speak?" gate   │
 └───────┬──────────────────────┬──────────────────────┬───────────┘
         │ MCP                  │ MCP                  │ files
  Google Calendar,       Knowledge-Base          memory/ (OKF bundle)
  Gmail, browser,        (E:\Knowledge-Base,
  bookings, …            kb_find / kb_read …)
```

## 3. Components in detail

### 3.1 Ears — speech-to-text

| Option | Polish quality | Latency | Cost / privacy | Verdict |
|---|---|---|---|---|
| **ElevenLabs Scribe (realtime)** | very good | streaming | cloud, paid | **Recommended default** |
| Deepgram Nova-3 | good | lowest | cloud, paid | good alternative |
| OpenAI `gpt-4o-transcribe` | very good | near-streaming | cloud, paid | alternative |
| `faster-whisper large-v3` (local GPU) | very good | 0.5–2 s per utterance | free, private | **offline fallback** |

- Voice activity detection with **Silero VAD** in the browser/desktop client so we
  only send speech, not silence.
- Push-to-talk first (hotkey + UI button). Wake word ("Alfred") later with
  openWakeWord.
- Transcript carries the detected language; the answer comes back in the same language.

### 3.2 Router — classification with Jev

Jev (TypeSafe AI, model `typesafe/jev-1.13`, endpoint `/v1/systemone`) takes a
`state` (text) and a set of typed `questions` and returns answers **with
probabilities**. The question types are `choice`, `score` and `noul` (yes/no). That
maps directly onto routing:

```json
{
  "model": "typesafe/jev-1.13",
  "state": "<transcript> + <2-line summary of the current session>",
  "questions": {
    "domain":   { "type": "choice", "options": ["calendar", "knowledge", "bookings",
                  "tasks", "communication", "research", "memory", "smalltalk", "system"],
                  "instructions": "Which assistant module should handle this?" },
    "urgency":  { "type": "score", "levels": ["low", "medium", "high"] },
    "acts_on_world": { "type": "noul", "instructions": "Will this book, send, pay or delete something?" },
    "needs_history": { "type": "noul", "instructions": "Does answering require earlier conversations?" }
  }
}
```

- The `domain` options are **generated from the module manifests**, so adding a
  module automatically extends the classifier.
- **Confidence policy:** if the top probability is ≥ 0.7, route. Between 0.4 and 0.7,
  load the top two modules. Below 0.4, Alfred asks one short clarifying question.
- **Multi-step requests** ("book a table and put it in my calendar") are handled
  by a `multi` flag. The executor then gets the union of both modules' tools.
- **Fallback chain** (Jev is cloud-only): Jev → Claude Haiku 4.5 with the same
  JSON schema → keyword rules. Every classification is logged, so later we can
  train a local classifier on your real requests.

> ⚠ You said you would send the Jev repository. I found `jev-ai/jev-ai-llm`
> (the hosted API above) and `ryantsai/jev-llm-router`. **Please confirm which
> one you meant**; the plan assumes the hosted Jev API.

### 3.3 Modules (the brain's "lobes")

Each module is a folder:

```
modules/bookings/
  module.yaml     # id, label, description for Jev, MCP servers, skills, permissions
  prompt.md       # module-specific instructions for the executor
  skills/         # optional SKILL.md files (procedures, e.g. "book a restaurant")
```

```yaml
id: bookings
label: "Reservations: restaurants, appointments, tickets"
examples: ["zarezerwuj stolik na 19", "book a table for two tomorrow"]
mcp_servers: [browser, google-calendar]
permissions:
  default: read
  confirm: [submit_booking, send_message]
model: claude-sonnet-5
```

First set of modules:

| Module | Tools / MCP | Notes |
|---|---|---|
| `calendar` | Google Calendar MCP | read schedule, create/move events |
| `knowledge` | your **E:\Knowledge-Base** MCP (`kb_find`, `kb_read`, `kb_graph`, …) | already exists and is already OKF |
| `tasks` | local task list (OKF pages) and/or Todoist | reminders feed the proactive layer |
| `communication` | Gmail MCP | drafts only, sending needs confirmation |
| `bookings` | browser automation (Playwright MCP) and later booking APIs | the "restaurant table" case |
| `research` | web search/fetch | summarised answers |
| `memory` | internal: "what did we talk about…", "remember that…" | |
| `smalltalk` | no tools, Haiku | cheap, fast, stays in persona |
| `system` | brain settings by voice ("speak English", "quieter") | |

### 3.4 Executor — the thinking step

- **Claude via the Anthropic SDK**: `claude-sonnet-5` for tool-heavy modules,
  `claude-haiku-4-5` for smalltalk, memory and simple lookups. The model can be
  set per module in `module.yaml`.
- **MCP hub:** one long-lived MCP client manager connects to all configured
  servers at startup and exposes **only the selected module's tools** to each call.
- **Prompt caching** on the static parts (persona, module prompt, tool
  definitions) to cut cost on repeated calls.
- Hard limits per request: max tool calls, max tokens, and a timeout. When a limit
  is hit, Alfred reports what he managed to do.

### 3.5 Guard — permissions

Each tool is `read`, `write` or `irreversible`. Read tools run freely. Write and
irreversible tools pause, and Alfred reads back a one-sentence summary
("Stolik dla dwóch w Nolita, piątek 19:00 — potwierdzasz?") and waits for yes or no.
All actions are written to an audit log.

### 3.6 Voice — Alfred speaks

- **Persona prompt:** calm, brief, a little dry wit, addresses you by name,
  gives the result first and the details only when asked. The answer is written
  *for the ear*: at most 2–3 sentences, no markdown, no lists.
- **TTS:**

| Option | Polish | Verdict |
|---|---|---|
| **ElevenLabs (multilingual v2 / v3, streaming)** | best natural Polish | **Recommended** |
| OpenAI `gpt-4o-mini-tts` | good, steerable tone | cheaper alternative |
| Azure Neural `pl-PL-MarekNeural` | good, reliable | alternative |
| Piper (local) | acceptable | offline fallback |

- Streaming from end to end: TTS starts on the first sentence while the rest is
  still being generated. Target: **under 1.5 s** from the end of your speech to
  Alfred's first word, for simple requests.
- Barge-in: when you start speaking, Alfred stops talking.

### 3.7 Memory — sessions in OKF

Your Knowledge-Base already uses **OKF v0.2**, so the brain's memory uses the same
conventions and the same tooling. It lives in a **separate bundle**
(`memory/`), so assistant chatter never pollutes your curated wiki:

```
memory/
  index.md                 # entry point: what is in here, latest sessions, open threads
  log.md                   # chronological change log (append-only)
  profile.md               # who you are, preferences (voice, language, habits)
  sessions/2026/09/2026-09-25-1930-restaurant.md
  threads/                 # open loops: "waiting for the restaurant to confirm"
  people/  places/  projects/  preferences/
  domains/                 # one index per module: calendar.md, bookings.md, …
```

A session page:

```yaml
---
type: Session
title: Booking dinner at Nolita
description: Booked a table for 2, Fri 19:00; waiting for SMS confirmation.
tags: [bookings, calendar]
timestamp: 2026-09-25T19:42:00+02:00
domains: [bookings, calendar]
open_threads: [threads/nolita-confirmation.md]
tokens: { in: 8420, out: 610 }
---
## Summary
## Decisions
## Facts learned   → linked to people/ places/ preferences/
## Open threads
```

How this saves tokens:

1. **Working memory** holds the current session turns in RAM and is compacted every N turns.
2. **Session close:** Haiku writes the session page, splits the new facts into
   categories (people, places, preferences, …) and updates `index.md` and the
   matching `domains/*.md`.
3. **Recall:** when the router says `needs_history`, the brain reads only
   `index.md` → the matching `domains/<module>.md` → at most *k* session pages,
   instead of the whole history. A small SQLite FTS index over the frontmatter
   (and embeddings later, if needed) finds pages without reading them.
4. **Session resume:** on startup, and whenever you come back after a pause,
   the brain loads `profile.md` and the **open threads**, so Alfred can pick up
   where you left off ("Wracając do Nolity — potwierdzili rezerwację.").

We keep OKF as the *storage format*. As you asked, we do **not** build the
separate Karpathy "LLM wiki" maintenance workflow on top of it.

### 3.8 Proactive layer

My recommendation is to **build a lightweight proactive engine inside the brain**
rather than run OpenClaw or Hermes Agent as a second brain.

- Both are full agent frameworks with their own memory, skills and a large system
  prompt. Running either next to our brain means two memories, two personas and
  a lot of duplicated context per heartbeat. Hermes in particular is known for a
  high token overhead per task.
- What proactivity needs is cheap: **triggers + a gate**.
  - **Triggers** (APScheduler): morning brief, 15 minutes before calendar events,
    open threads that are due, reminders, new important emails, and a periodic
    heartbeat.
  - **Gate:** each trigger first asks **Jev** a `noul` question ("Is this worth
    interrupting Andrzej right now?", with time of day, your calendar and your
    "do not disturb" state). Only a *yes* wakes the LLM. Most heartbeats cost a
    few hundred Jev tokens and no Claude call at all.
- **Delivery:** spoken if you are at the desk, otherwise a push to your phone.
- **Always on:** the brain runs as a service (Docker) on your PC now, and later on
  an always-on box (mini-PC or a small VPS) reachable through Tailscale.
- **OpenClaw, optionally, later** as a *messaging gateway only*
  (WhatsApp/Telegram/Discord). It forwards messages to our brain through a
  single tool, if you want those channels without writing adapters.

### 3.9 UI — the brain view

- **Stack:** FastAPI (REST + WebSocket) on the back end; React + Vite +
  **React Flow** (or Cytoscape.js) on the front end.
- **Centre canvas:** the brain graph. Nodes are Ears → Router → modules → MCP
  servers/tools → Memory → Voice, plus Proactive. On every request the active
  path **lights up live**: the chosen module, the Jev probabilities on the edges,
  the tool calls, and the tokens/cost per node.
- **Side panels:**
  - **Conversation:** transcript, a mic button, and playback of Alfred's answers.
  - **Modules:** enable/disable, edit `module.yaml` and prompts, test the classifier
    on a sentence and see the probabilities.
  - **Memory:** browse the OKF bundle as a graph or as pages, and edit or delete facts.
  - **Settings:** STT/TTS provider, voice, language, speaking speed, persona
    strength, models per module, confidence thresholds, quiet hours.
  - **Proactive:** list of triggers, their schedule and gate, and a history of
    what fired and why.
  - **Traces and costs:** each request as a timeline, plus daily token spend.

## 4. Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.12, `uv` for dependencies |
| API | FastAPI, WebSockets, Pydantic |
| LLM | `anthropic` SDK (Claude Sonnet 5 / Haiku 4.5), prompt caching |
| MCP | official `mcp` Python SDK (stdio + streamable HTTP clients) |
| Classifier | Jev HTTP API (`httpx`), fallback Haiku |
| STT / TTS | ElevenLabs (Scribe + TTS), fallbacks faster-whisper / Piper |
| Scheduling | APScheduler |
| Storage | OKF markdown files + SQLite (FTS index, traces, audit log) |
| UI | React + Vite + TypeScript + React Flow |
| Packaging | Docker Compose; secrets in `.env` (never committed) |

## 5. Repository layout (proposed)

```
Personal-Assistant/
  brain/
    app.py                  # FastAPI entry, WebSocket
    pipeline.py             # ears → router → context → executor → guard → voice → memory
    events.py               # event bus + trace model
    ears/        (stt providers, vad)
    router/      (jev client, fallback, policy)
    modules/     (loader, registry)
    executor/    (claude loop, mcp hub)
    guard/       (permissions, confirmations)
    voice/       (persona, tts providers)
    memory/      (okf read/write, session writer, recall, index)
    proactive/   (scheduler, triggers, gate)
  modules/                  # capability plug-ins (module.yaml + prompt.md + skills/)
  memory/                   # OKF bundle (git-ignored by default, private)
  ui/                       # React app
  config/  brain.yaml  mcp.json
  tests/
  docs/PLAN.md
```

## 6. Delivery phases

| Phase | Goal | "Done" means |
|---|---|---|
| **0. Skeleton** | repo, config, event bus, FastAPI, CI, `.env` handling | `uvicorn` runs, `/health` is green |
| **1. Text brain** | router (Jev + fallback) → executor with MCP hub → Alfred text answer; `calendar` + `knowledge` modules | typing "co mam jutro?" gives a correct, in-persona answer using only calendar tools |
| **2. Voice** | STT in, TTS out, push-to-talk, barge-in, PL/EN | a full spoken round trip in under ~2 s for simple requests |
| **3. Memory** | OKF memory bundle, session writer, recall, resume of open threads | after a restart Alfred brings up the open thread by himself |
| **4. UI** | brain graph with live traces, module/settings/memory panels | you can watch a request travel through the graph and change the voice from the UI |
| **5. Actions** | guard + confirmations; `bookings`, `communication`, `tasks` | "book a table…" ends in a confirmed booking and a calendar entry |
| **6. Proactive** | scheduler, triggers, Jev gate, morning brief, phone delivery | Alfred reminds you before a meeting without being asked; daily heartbeat cost is visible |
| **7. Always-on** | Docker, remote host, Tailscale, optional OpenClaw gateway | reachable from your phone away from home |

Each phase ends with something you can actually use. We commit after each phase.

## 7. Costs and tokens (rough, to validate in Phase 1)

- The router runs for every utterance with Jev: small and fixed, a few hundred tokens.
- The executor sees 1 module (≈ 3–10 tools) instead of all tools (≈ 50+), which
  cuts the tool-definition context by roughly 5–10×. Cached prompts cost about
  a tenth of normal input on repeat calls.
- Memory recall reads index pages and a few session pages instead of the whole history.
- The proactive gate means most heartbeats never call Claude.

## 8. Risks

| Risk | Mitigation |
|---|---|
| Jev is cloud-only, and transcripts leave your machine | fallback chain; a local classifier trained later on the logged decisions |
| Restaurant booking sites resist automation | start with sites that have an API or email/phone; the browser flow asks you to confirm |
| Latency adds up (STT + Jev + LLM + TTS) | streaming at every stage; Haiku for simple domains; run Jev and the memory lookup in parallel |
| Memory grows noisy | the session writer only keeps facts that pass a threshold; you edit them in the UI |
| Secrets and API keys | `.env` plus the OS keychain; never in the repo; MCP servers run with least privilege |

## 9. Open questions for you

1. **Jev:** which repository did you mean (see 3.2)? Do you have an API key?
2. **Voice providers:** OK to use cloud STT/TTS (ElevenLabs) as the default, with
   local models only as a fallback? Or is privacy more important than voice
   quality?
3. **First modules:** I propose `calendar` + `knowledge` + `smalltalk` for Phase 1.
   Anything more urgent?
4. **Knowledge base:** the brain should read `E:\Knowledge-Base` through its existing
   MCP server, read-only at first. Agreed?
5. **Proactive and always-on:** do you have (or want) an always-on machine or VPS,
   and which phone channel do you prefer: Telegram, WhatsApp or a PWA?
6. **Language:** does Alfred answer in the language you spoke, or always in Polish?
