"""The executor does the actual work: Claude (through your Claude Code subscription) with ONLY the tools of the
capabilities the router picked, the module's instructions and the chosen skill.

Every tool call Claude makes goes through run_tool(), which
  1. asks the security layer whether the call is safe (once outside content - a web page, an MCP result - is in play),
  2. asks you for a spoken "tak" first when the tool changes the world (Guard),
  3. runs the tool and reports it on the event bus.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

import claude_agent_sdk as sdk

from . import fitness, llm, persona
from .atlas import BrainMap
from .mcp_hub import MCPHub
from .memory import MemoryStore, Session
from .modules import ModuleRegistry
from .router import OTHER_PRODUCT, Route
from .tools import ADD_CATEGORY, ASK_FIRST, CONFIRM_TOOL, MUTATING, TOOLS, WEB_TOOLS, make_handlers

SERVER = "alfred"   # our tools reach Claude Code as an in-process MCP server with this name
FAILED = {"pl": "Coś poszło nie tak po mojej stronie, {addr}. Spróbuj proszę za chwilę.",
          "en": "Something went wrong on my side, {addr}. Please try again in a moment."}
# The executor's system prompt starts with this (config models.executor_directive overrides it).
DIRECTIVE = ("Wykonaj dokładnie działanie opisane w <request>, na podstawie planu Jev.\n"
             "- <user_said> to polecenie - ono rozstrzyga. <jev_plan> mówi, które moduły, możliwości i funkcje "
             "(serwer › funkcja) są potrzebne: z kroków wywołaj te, których wymaga polecenie, w tej kolejności; "
             "sygnały traktuj jako wskazówki.\n"
             "- <instructions> to zasady modułów, <routing> - aktualny czas i szczegóły, reszta to kontekst.\n"
             "- Nie rób nic ponad polecenie. Gdy plan nie pasuje do polecenia, idź za poleceniem; gdy polecenie jest "
             "niejasne, zadaj jedno krótkie pytanie.")
# A training-plan change: Jev picks the type, the discipline and whether it adds load - each picks a fixed block below.
PLAN_CHANGE_STEPS = (
    "1. training_status (weeks 4): phase, this week's sessions, what was done, work load; the calendar for the weeks "
    "the change touches.\n"
    "2. Research it: web_search for current evidence (reviews, meta-analyses, national federations) on this change "
    "for age-group triathletes - at most 2 searches, cite the best 1-2 sources.\n"
    "3. Propose exactly 3 options, each in one or two sentences: what changes in the week (sport, sessions, hours), "
    "what it does for the half Ironman on 2027-09-02, the risk, and the evidence with its source.\n"
    "4. Recommend one option and say why in one sentence. Change nothing yet.\n"
    "5. Only after his yes: training_plan_update (it asks for a yes; `why` = the chosen option) and the new sessions "
    "as tasks.")
PLAN_CHANGE_RULES = {
    "add_activity": "A new activity: fit it in without raising total weekly load by more than ~10%; count it as strength "
                    "or easy aerobic work and take its time from the same kind of session - never from the long ride or "
                    "the long run.",
    "volume": "More or less training: change total weekly hours by at most 10% a week; keep the long ride, the long run "
              "and one quality session per sport; with less time cut easy sessions first.",
    "pause": "A pause: up to 7 days off costs almost nothing; 1-3 weeks: keep 2-3 short easy sessions if he can; after an "
             "illness come back at 50-70% volume for a week; move the phases only for pauses over 2 weeks. With pain or an "
             "injury send him to a physio and offer cross-training that does not load it.",
    "race": "A race change: the phases are counted back from the race - with a sooner race shorten base and build, never "
            "the 3-week peak or the taper; a second race needs a mini-taper of 3-7 days.",
    "focus": "Improving one thing: move one session from the strongest discipline to the weakest; technique = drills, "
             "speed = one quality session, strength = the strength block of the current phase.",
    "body": "A body goal: the weight module rules apply - deficit 300-500 kcal, protein 1.8-2.0 g/kg, food around hard "
            "sessions; never a deficit in the peak or the taper.",
}
PLAN_SPORT_RULES = {
    "swim": "It is about swimming: technique gives the most; open water and the wetsuit before the race.",
    "bike": "It is about cycling: the long ride and the bike-run brick are the key sessions.",
    "run": "It is about running: it loads the body most - raise run volume slowest (max 10% a week); calf and Achilles "
           "strength protects it.",
    "strength": "It is about strength: 2 sessions a week in the base (heavy, 4-6 reps, plus jumps), 1-2 short heavy ones "
                "in build and peak; strength on an easy day or 6+ hours after a hard endurance session, never the day "
                "before the long run.",
    "all": "It touches the whole plan: keep the 80/20 split and the 3:1 cycle.",
}
ADDS_LOAD = ("It adds load: show the new weekly total in hours against now and against his 4-6 h budget, and the work "
             "load of those weeks; at least one option must keep the total unchanged.")

DECLINED = "The user declined this action. Do not retry; acknowledge briefly."
BLOCKED = "The security layer blocked this action as unsafe. Do not retry it; tell the user briefly why."


class Guard:
    """Holds a tool call until the user says yes or no. Silence for 2 minutes counts as no."""

    def __init__(self, bus, timeout_s: float = 120.0):
        self.bus = bus
        self.timeout_s = timeout_s
        self.pending: dict[str, Any] | None = None     # {"question": ..., "tool": ..., "future": ...}

    async def confirm(self, request_id: str, session_id: str | None, tool: str, question: str,
                      audio_b64: str | None = None) -> bool:
        self.pending = {"question": question, "tool": tool, "future": asyncio.get_running_loop().create_future()}
        self.bus.emit("confirm_request", "guard", request_id, session_id, tool=tool, text=question, audio_b64=audio_b64)
        try:
            approved = await asyncio.wait_for(self.pending["future"], self.timeout_s)
        except asyncio.TimeoutError:
            approved = False
        self.bus.emit("confirm_result", "guard", request_id, session_id, tool=tool, approved=approved)
        self.pending = None
        return approved

    def resolve(self, approved: bool) -> bool:
        """The user's answer (from the UI button or recognised speech). False if nothing was waiting."""
        if self.pending and not self.pending["future"].done():
            self.pending["future"].set_result(approved)
            return True
        return False


@dataclass
class ExecResult:
    text: str
    model: str
    request: str = ""                                   # what the user asked (the security check compares to it)
    usage: dict[str, int] = field(default_factory=dict)
    cost_usd: float | None = None
    actions: list[str] = field(default_factory=list)    # changes made, remembered in the session summary
    tools_used: list[str] = field(default_factory=list)
    untrusted: bool = False                             # outside content (MCP / web results) entered this request
    task_category: str | None = None                    # what Jev heard: the task's category and status
    task_status: str | None = None
    product: dict | str | None = None                   # Jev: his regular product ({name, url, note}) or "other"


def said_text(request: str) -> str:
    """What he actually said: the request without the chat-mode note in front."""
    return re.sub(r"^<reply_mode>.*?</reply_mode>\s*", "", request, flags=re.S).strip()


def grams_said(text: str) -> float | None:
    """The amount he gave in digits: "150 g", "0,5 kg", "250 ml" (ml counted as grams). None if he gave none.
    ponytail: digits only and the first amount; "sto pięćdziesiąt gramów" or two products in one sentence fall back
    to the product's usual portion / Claude."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|kilo\w*|g|gr|gram\w*|ml|mililitr\w*)\b", text, re.I)
    if not m:
        return None
    value = float(m.group(1).replace(",", "."))
    return value * 1000 if m.group(2).lower().startswith("k") else value


def _describe(name: str, args: dict[str, Any]) -> str:
    return f"{name.split('__')[-1]} {json.dumps(args, ensure_ascii=False)[:160]}"


class Executor:
    def __init__(self, settings, registry: ModuleRegistry, brain_map: BrainMap, hub: MCPHub, store: MemoryStore,
                 guard: Guard, bus, tts=None, shield: Callable | None = None, routines: Callable = lambda: [],
                 classify_tasks: Callable | None = None, classify_meal: Callable | None = None):
        self.settings, self.registry, self.map, self.hub = settings, registry, brain_map, hub
        self.guard, self.bus, self.tts, self.shield, self.routines = guard, bus, tts, shield, routines
        self.classify_tasks = classify_tasks     # Jev: category + status of each task (router.classify_tasks)
        self.classify_meal = classify_meal       # Jev: the meal type of a logged meal (router.classify_meal)
        routines_file = settings.path("proactive.routines") if settings.get("proactive.routines") else None
        self.store = store
        self.handlers = make_handlers(store, routines_file, settings, hub)
        self.acted: set[str] = set()             # requests that already changed something (see Brain.handle_text)

    def capabilities(self, route: Route) -> list[str]:
        """The route's capabilities + the skill's + the modules' "always" ones + the context sources from config."""
        caps = list(route.capabilities) or self.map.capabilities_of(route.modules)
        extra = (self.map.skills.get(route.skill or "", {}).get("uses", []) + self.map.always_capabilities(route.modules)
                 + [c for c in self.settings.get("assistant.context_capabilities") or [] if c in self.map.capabilities])
        return list(dict.fromkeys(caps + extra))

    def tool_names(self, route: Route) -> list[str]:
        return self.map.tools_of(self.capabilities(route))

    def _instructions(self, route: Route) -> str:
        """System prompt: the directive (execute exactly what the request describes) + who Alfred is and how he
        speaks. Everything about THIS request - Jev's plan, module rules, context - is in the one <request>."""
        return self.settings.get("models.executor_directive", DIRECTIVE) + "\n\n" + persona.system_prompt(self.settings)

    def _module_rules(self, route: Route) -> str:
        modules = [m for m in map(self.registry.get, route.modules) if m]
        parts = [f"## Module: {m.label}\n{m.prompt}".strip() for m in modules]
        if skill := self.registry.skill(route.skill):
            parts.append(f"## Procedure to follow: {skill.name}\n{skill.body}")
        if route.plan_change in PLAN_CHANGE_RULES:      # Jev's picks -> fixed blocks, nothing left to Claude's taste
            rules = [PLAN_CHANGE_RULES[route.plan_change], PLAN_SPORT_RULES.get(route.plan_sport or ""),
                     ADDS_LOAD if route.adds_load >= 0.5 else None]
            parts.append("## Procedure to follow: training plan change\n" + PLAN_CHANGE_STEPS + "\nRules:\n"
                         + "\n".join(f"- {r}" for r in rules if r))
        if routines := [f"- {r['id']} ({r['schedule']}): {r['prompt']}" for r in self.routines()]:
            parts.append("## Your routines (config/routines.yaml)\nYour own scheduled prompts, NOT the user's tasks: "
                         "never list them among his tasks or in his plan for today; mention them only when he asks "
                         "about routines.\n" + "\n".join(routines))
        return "\n\n".join(parts) or "No module instructions."

    def _prompt(self, text: str, route: Route, session: Session) -> str:
        """ONE exact request glued from everything: what was said before, memory, the modules' rules, Jev's plan,
        the context - and, last, what the user said now."""
        history = "\n".join(f"{m['role']}: {m['content']}" for m in session.history_messages())
        blocks = [f"<conversation_so_far>\n{history}\n</conversation_so_far>"] if history else []
        briefed = not session.turns or route.needs_history >= 0.5
        if briefed:
            blocks.append(f"<memory_briefing>\n{session.briefing}\n</memory_briefing>")   # has the goals too
        if not briefed and "task_create" in self.tool_names(route) and (goals := self.store.goals_text()):
            blocks.append(f"<goals>\n{goals}\n</goals>")    # tasks should serve them - see the tasks module rules
        blocks.append(f"<instructions>\n{self._module_rules(route)}\n</instructions>")
        hints = [f"now={datetime.now().astimezone():%A %Y-%m-%d %H:%M%z}", f"module={','.join(route.modules)}",
                 f"urgency={route.urgency:.1f}"]
        if route.topic:
            hints.append(f"knowledge topic={self.map.topics.get(route.topic, {}).get('title', route.topic)}")
        if route.clarify:
            hints.append("routing is unsure - ask one short clarifying question if needed")
        if route.plan_change:
            hints.append(f"plan change={route.plan_change}" + (f", about={route.plan_sport}" if route.plan_sport else "")
                         + f", adds load={round(route.adds_load * 100)}%")
        if "task_create" in self.tool_names(route):
            categories = ", ".join(self.settings.get("tasks.categories") or {})
            hints.append(f"task categories={categories} (fixed; Jev assigns them to each task - a new category only "
                         f"if the user wants it, via {ADD_CATEGORY}, which asks him)")
            hints += [f"{k}={v}" for k, v in (("task category", route.task_category),
                                               ("task status", route.task_status)) if v]
        if any(n.endswith("__log_meal") for n in self.tool_names(route)) and (product := self.product(route)):
            blocks.append(self._product_note(product, text))
        blocks += [self._plan(route), f"<routing>{'; '.join(hints)}</routing>", f"<user_said>\n{text}\n</user_said>"]
        return "<request>\n" + "\n\n".join(blocks) + "\n</request>"

    def product(self, route: Route) -> dict | str | None:
        """Jev's product answer: the product itself, "other", or None (Jev did not answer / no products)."""
        if route.product == OTHER_PRODUCT:
            return OTHER_PRODUCT
        return next((p for p in self.store.products() if p["name"] == route.product), None)

    @staticmethod
    def _product_note(product: dict | str, text: str) -> str:
        """Fixed templates for Nutrition MCP: his regular product with its grams, or "other" = log exactly what he
        said. Claude only adds the calories and macros."""
        if product == OTHER_PRODUCT:
            return ("<product jev=\"other\">None of his regular products. For nutrition__log_meal the description is "
                    "exactly what he said (the system puts his words in); estimate the nutrition from it.</product>")
        said, usual = grams_said(said_text(text)), product.get("grams")
        grams = said or usual
        head = (f"<product jev=\"{product['name']}\">His regular product: {product['name']}"
                + (f" ({product['note']})" if product.get("note") else "") + f", {product['url']}.")
        if not grams:
            return (head + " He gave no amount and the product has no usual portion - ask him how many grams before "
                           "nutrition__log_meal.</product>")
        return (head + f" Amount: {grams:g} g ({'he said it' if said else 'his usual portion'}). For "
                f"nutrition__log_meal the system sets the description to \"{product['name']} ({grams:g} g)\"; you fill "
                f"in calories, protein, carbs, fat, fiber and sugars for exactly {grams:g} g - per 100 g from the "
                "product page (web_fetch the link if you can) or its label, scaled to the grams.</product>")

    def _plan(self, route: Route) -> str:
        """What Jev worked out, laid out for Claude: modules -> capabilities -> server › function, then signals."""
        pct = lambda p: f"{round(p * 100)}%"
        tool = lambda n: self.map.tools.get(n, {})
        lines = ["Modules: " + ", ".join(f"{m} {pct(route.probabilities.get(m, 0))}" + (" (lead)" if m == route.module
                                                                                     else "") for m in route.modules)]
        lines.append("Capabilities: " + ", ".join(
            c + (f" {pct(route.capability_probabilities[c])}" if c in route.capability_probabilities else "")
            + (" [named by the user]" if c in route.forced else "") for c in self.capabilities(route)))
        available = set(self.tool_names(route))
        ranked = [(n, p) for n, p in route.tool_probabilities.items() if n in available]
        if steps := [(n, p) for n, p in ranked if p >= 0.6]:
            lines.append("Steps - the functions Jev expects, most likely first (call the ones the request needs, "
                         "in this order; of near-duplicates pick one):")
            lines += [f"  {i}. {tool(n).get('server', '?')} › {tool(n).get('short', n)} - {pct(p)}"
                      for i, (n, p) in enumerate(steps, 1)]
        if maybe := [(n, p) for n, p in ranked if 0.3 <= p < 0.6]:
            lines.append("Maybe: " + ", ".join(f"{tool(n).get('short', n)} {pct(p)}" for n, p in maybe))
        signals = [f"urgency {route.urgency:.1f}/2"]
        for p, note in ((route.acts_on_world, "changes something in the world - one sentence on what you will do, "
                                              "then the tool call; the system asks for the yes"),
                        (route.changes_existing, "changes something that already exists - find it (task_list, search) "
                                                 "and update it; do not create a new one"),
                        (route.multi_step, "several things at once - do every part; independent calls together"),
                        (route.needs_history, "needs what happened before - check memory and open tasks first")):
            if p >= 0.5:
                signals.append(f"{note} ({pct(p)})")
        lines.append("Signals: " + "; ".join(signals))
        return f"<jev_plan source={route.source}>\n" + "\n".join(lines) + "\n</jev_plan>"

    async def run(self, text: str, route: Route, session: Session, request_id: str) -> ExecResult:
        lead = self.registry.get(route.module)
        model = (lead and lead.model) or self.settings.get("models.executor")
        effort = (lead and lead.effort) or self.settings.get("models.executor_effort")
        result = ExecResult(text="", model=model, request=text, task_category=route.task_category,
                            task_status=route.task_status, product=self.product(route))

        names = self.tool_names(route)
        live = self.hub.all_tools()
        ours = [TOOLS.get(n) or live[n] for n in names if n in TOOLS or n in live]
        web = [WEB_TOOLS[n][0] for n in names if n in WEB_TOOLS]

        def as_sdk_tool(spec: dict):
            async def handler(args: dict[str, Any]) -> dict[str, Any]:
                output, is_error = await self.run_tool(spec["name"], dict(args or {}), session, request_id, result)
                return {"content": [{"type": "text", "text": output}], "is_error": is_error}
            return sdk.tool(spec["name"], spec["description"], spec["input_schema"])(handler)

        options = llm.options(
            self.settings, system_prompt=self._instructions(route), model=model, effort=effort, tools=web,
            mcp_servers={SERVER: sdk.create_sdk_mcp_server(SERVER, tools=[as_sdk_tool(t) for t in ours])} if ours else {},
            allowed_tools=[f"mcp__{SERVER}__{t['name']}" for t in ours] + web,
            max_turns=int(self.settings.get("models.max_tool_rounds", 8)) + 1)
        self.bus.emit("executor_start", "executor", request_id, session.id, model=model, effort=effort,
                      backend="subscription", modules=route.modules, capabilities=self.capabilities(route),
                      tools=[t["name"] for t in ours] + web)

        started, last_text, round_no = time.perf_counter(), "", 0
        try:
            async for message in sdk.query(prompt=self._prompt(text, route, session), options=options):
                if isinstance(message, sdk.AssistantMessage):     # one round of Claude thinking / calling tools
                    if said := " ".join(b.text for b in message.content if isinstance(b, sdk.TextBlock)).strip():
                        last_text = said
                    for b in message.content:                       # Claude Code searched / read the web itself
                        if getattr(b, "name", None) in web:
                            result.untrusted = True                 # a web page is now in the context
                            result.tools_used.append(b.name)
                            self.bus.emit("tool_call", "executor", request_id, session.id, tool=b.name,
                                          input=getattr(b, "input", {}))
                    usage = message.usage or {}
                    self.bus.emit("llm_call", "executor", request_id, session.id, round=round_no,
                                  stop_reason=message.stop_reason or "", ms=int((time.perf_counter() - started) * 1000),
                                  usage={"input": int(usage.get("input_tokens") or 0),
                                         "output": int(usage.get("output_tokens") or 0)})
                    round_no += 1
                elif isinstance(message, sdk.ResultMessage):      # the end: final answer and the bill
                    usage = llm.usage_of(message)
                    result.cost_usd = usage.pop("cost_usd")
                    result.usage = usage
                    result.text = (message.result or "").strip()
                    if message.is_error:
                        self.bus.emit("error", "executor", request_id, session.id,
                                      message=f"Claude Code: {message.subtype} {message.errors or ''}"[:500])
        except Exception as exc:
            self.bus.emit("error", "executor", request_id, session.id, message=f"{type(exc).__name__}: {exc}"[:500])
            addr = (self.settings.get("assistant.address") or {}).get(session.language, "")
            result.text = FAILED.get(session.language, FAILED["en"]).format(addr=addr)
            return result
        result.text = result.text or last_text or ("Gotowe." if session.language == "pl" else "Done.")
        return result

    async def _jev_classifies(self, tasks: list[dict], result: ExecResult, session: Session, request_id: str,
                              update: bool = False) -> None:
        """Sets each task's category (and, for new tasks, status) from Jev - one question per task. Where Jev has
        no answer for a task: what Jev heard for the whole request, then Claude's own value. Jev down: Claude's."""
        labels = [" - ".join(str(v) for v in (t.get("title") or t.get("task_id"), t.get("description")) if v)
                  for t in tasks]
        try:
            verdicts, source = await self.classify_tasks(result.request, labels), "jev"
        except Exception:                        # no Jev: Claude does the classifier's job (the tools still check)
            verdicts, source = [("?", "?")] * len(tasks), "claude"
        for task, (category, status) in zip(tasks, verdicts):
            if category == "?":
                category = result.task_category or task.get("category")
            if update and not category:          # Jev sees no fitting category: leave the task where it is
                task.pop("category", None)
            else:
                task["category"] = category
            if not update:
                task["status"] = (status if status != "?" else None) or result.task_status or task.get("status") or "todo"
        self.bus.emit("tasks_classified", "router", request_id, session.id, source=source, tasks=[
            {"task": label, "category": t.get("category"), "status": t.get("status")} for label, t in zip(labels, tasks)])

    async def _jev_meal(self, args: dict[str, Any], result: ExecResult, session: Session, request_id: str) -> None:
        """The meal type of a logged meal is Jev's call; Claude's own value only when Jev cannot answer."""
        try:
            kind = await self.classify_meal(result.request, str(args.get("description", "")),
                                            f"{datetime.now():%A %H:%M}")
        except Exception:
            kind = None
        if kind:
            args["meal_type"] = kind
        # Jev's product decides the description: "other" = his own words, a regular product = its name and link
        if result.product == OTHER_PRODUCT:
            args["description"] = said_text(result.request)
        elif isinstance(result.product, dict):
            name = result.product["name"]
            grams = grams_said(said_text(result.request)) or result.product.get("grams")
            if grams:                                    # the template: product + grams; Claude only adds the numbers
                args["description"] = f"{name} ({grams:g} g)"
            elif name.lower() not in str(args.get("description", "")).lower():
                args["description"] = f"{name} - {args.get('description', '')}".rstrip(" -")
            args["notes"] = "\n".join(filter(None, [args.get("notes"), f"Stały produkt: {result.product['url']}"]))
        self.bus.emit("meal_classified", "router", request_id, session.id, source="jev" if kind else "claude",
                      meal=args.get("description"), meal_type=args.get("meal_type"),
                      product=result.product if isinstance(result.product, str) else (result.product or {}).get("name"))

    async def run_tool(self, name: str, args: dict[str, Any], session: Session, request_id: str,
                       result: ExecResult) -> tuple[str, bool]:
        """Run one tool call from Claude; returns (text for Claude, is_error)."""
        # Jev classifies, Claude executes: the category (and a new task's status) is Jev's call - Claude's own
        # values are used only when Jev cannot answer.
        if name == "task_create":
            await self._jev_classifies(args.get("tasks") or [], result, session, request_id)
        elif name == "task_update" and args.get("category"):     # moving a task to a category
            await self._jev_classifies([args], result, session, request_id, update=True)
        elif name == "task_update" and result.task_status and not (set(args) - {"task_id", "note"}):
            args["status"] = result.task_status                  # "zrobione" said about a task
        elif name.endswith("__log_meal") and self.classify_meal:
            await self._jev_meal(args, result, session, request_id)

        # Alfred's own tools act on the user's own (already checked) words - they are checked only once outside
        # content has entered this request and could have planted instructions.
        if self.shield and (result.untrusted or name not in TOOLS):
            verdict = await self.shield(result.request, name, args)
            self.bus.emit("action_check", "shield", request_id, session.id, tool=name, **verdict)
            if verdict["breach"]:
                result.actions.append(f"blocked: {_describe(name, args)}")
                return BLOCKED, True

        if name in ASK_FIRST or self.map.needs_confirmation(name):
            summary = (str(args.get("summary", "")) if name == CONFIRM_TOOL
                       else f"dodam nową kategorię zadań „{args.get('name', '')}”" if name == ADD_CATEGORY
                       else "") or _describe(name, args)
            question = persona.confirm_prompt(session.language, summary.rstrip("."))
            audio = await self.tts.synthesize(question) if self.tts else None
            if not await self.guard.confirm(request_id, session.id, name, question, audio):
                return DECLINED, False
            result.actions.append(f"approved: {summary}")
            if name == CONFIRM_TOOL:
                return "approved - the user said yes, proceed.", False

        if name in MUTATING or name in ASK_FIRST or self.map.needs_confirmation(name):
            self.acted.add(request_id)
        node = f"tool:{name}" if name in self.map.tools else "memory" if name in TOOLS else "executor"
        self.bus.emit("tool_call", node, request_id, session.id, tool=name, input=args)
        result.tools_used.append(name)
        started, is_error = time.perf_counter(), False
        try:
            if name in self.handlers:
                output = await self.handlers[name](args, session.id)
                if name in MUTATING:
                    result.actions.append(f"{name}: {_describe(name, args)}")
            elif self.hub.owns(name):
                result.untrusted = True
                output, is_error = await self.hub.call(name, args)
            else:
                output, is_error = f"Unknown tool {name}", True
        except Exception as exc:
            output, is_error = f"{type(exc).__name__}: {exc}", True
        self.bus.emit("tool_result", node, request_id, session.id, tool=name, is_error=is_error,
                      ms=int((time.perf_counter() - started) * 1000), preview=str(output)[:300])
        if name.endswith("__log_meal") and not is_error:
            output = f"{output}\n\n{await self._after_meal(request_id, session)}"
        return str(output), is_error

    async def _after_meal(self, request_id: str, session: Session) -> str:
        """The meal routine: after every logged meal, today's intake against the goals - raised by today's training
        from Strava - and the training sessions left this week. Claude says what is left; the Dieta tab shows it."""
        try:
            progress = await self.hub.call_json("nutrition__get_goal_progress", {})
            training = await fitness.status(self.hub, self.settings, weeks=1,
                                            weight_kg=(progress.get("weight") or {}).get("current"))
            base = await fitness.sync_goals(self.hub, self.settings, progress, training["today_kcal"])
            balance = fitness.day_balance(progress, training["today_kcal"],
                                          float(self.settings.get("training.eat_back", 0.6)), base)
        except Exception as exc:
            return f"(Meal routine: recalculation failed - {type(exc).__name__}: {exc})"
        self.bus.emit("meal_balance", "executor", request_id, session.id, **balance)
        return fitness.balance_text(balance, training)
