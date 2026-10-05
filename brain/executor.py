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
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import claude_agent_sdk as sdk

from . import fitness, llm, meals, persona
from .atlas import BrainMap
from .mcp_hub import MCPHub
from .memory import MemoryStore, Session
from .modules import ModuleRegistry
from .router import Route, Router
from .scheduler import routines_file, valid_routines
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
# Chat mode: the answer is read on screen, so the spoken-length rules of the persona step aside.
CHAT_NOTE = ("<reply_mode>text chat - the user reads your answer on screen, nothing is spoken. Answer fully and in "
             "depth, like a knowledgeable assistant explaining a topic. Use Markdown (headings, lists, tables, code "
             "blocks, links) where it helps. The 'How you speak' rules about length, markdown and URLs do not apply "
             "here; keep your character.</reply_mode>")

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
    request: str = ""                                   # what the user said (the security check compares to it)
    usage: dict[str, int] = field(default_factory=dict)
    cost_usd: float | None = None
    actions: list[str] = field(default_factory=list)    # changes made, remembered in the session summary
    tools_used: list[str] = field(default_factory=list)
    untrusted: bool = False                             # outside content (MCP / web results) entered this request
    task_category: str | None = None                    # what Jev heard: the task's category and status
    task_status: str | None = None
    product: dict | str | None = None                   # Jev: his regular product ({name, url, note}) or "other"


def _describe(name: str, args: dict[str, Any]) -> str:
    return f"{name.split('__')[-1]} {json.dumps(args, ensure_ascii=False)[:160]}"


class Executor:
    def __init__(self, settings, registry: ModuleRegistry, brain_map: BrainMap, hub: MCPHub, store: MemoryStore,
                 guard: Guard, bus, router: Router, tts=None):
        self.settings, self.registry, self.map, self.hub = settings, registry, brain_map, hub
        self.store, self.guard, self.bus, self.router, self.tts = store, guard, bus, router, tts
        self.routines_file = routines_file(settings)
        self.handlers = make_handlers(store, self.routines_file, settings, hub)
        self.acted: set[str] = set()             # requests that already changed something (see Brain.handle_text)

    def capabilities(self, route: Route) -> list[str]:
        """The route's capabilities (router.apply_policy) + the context sources from config."""
        context = [c for c in self.settings.get("assistant.context_capabilities") or [] if c in self.map.capabilities]
        return list(dict.fromkeys(route.capabilities + context))

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
        if route.plan_change in fitness.PLAN_CHANGE_RULES:   # Jev's picks -> fixed blocks, nothing left to Claude's taste
            parts.append(fitness.plan_change_procedure(route.plan_change, route.plan_sport, route.adds_load,
                                                       self.settings.get("training") or {}))
        if routines := [f"- {r['id']} ({r['schedule']}): {r['prompt']}" for r in valid_routines(self.routines_file)]:
            parts.append("## Your routines (config/routines.yaml)\nYour own scheduled prompts, NOT the user's tasks: "
                         "never list them among his tasks or in his plan for today; mention them only when he asks "
                         "about routines.\n" + "\n".join(routines))
        return "\n\n".join(parts) or "No module instructions."

    def _prompt(self, text: str, route: Route, session: Session, chat: bool = False) -> str:
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
        logs_meals = any(n.endswith("__log_meal") for n in self.tool_names(route))
        if logs_meals and (product := meals.regular_product(self.store, route.product)):
            blocks.append(meals.product_note(product, text))
        blocks += [self._plan(route), f"<routing>{'; '.join(hints)}</routing>"]
        if chat:
            blocks.append(CHAT_NOTE)
        blocks.append(f"<user_said>\n{text}\n</user_said>")
        return "<request>\n" + "\n\n".join(blocks) + "\n</request>"

    def _plan(self, route: Route) -> str:
        """What Jev worked out, laid out for Claude: modules -> capabilities -> server › function, then signals."""
        pct = lambda p: f"{round(p * 100)}%"
        tool = lambda n: self.map.tools.get(n, {})

        def module(m: str) -> str:
            return f"{m} {pct(route.probabilities.get(m, 0))}" + (" (lead)" if m == route.module else "")

        def capability(c: str) -> str:
            p = route.capability_probabilities.get(c)
            return c + (f" {pct(p)}" if p is not None else "") + (" [named by the user]" if c in route.forced else "")

        lines = ["Modules: " + ", ".join(map(module, route.modules)),
                 "Capabilities: " + ", ".join(map(capability, self.capabilities(route)))]
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

    async def run(self, text: str, route: Route, session: Session, request_id: str, chat: bool = False) -> ExecResult:
        """`text` is what he said; chat=True: the answer is read on screen (long, Markdown), not spoken."""
        lead = self.registry.get(route.module)
        model = (lead and lead.model) or self.settings.get("models.executor")
        effort = (lead and lead.effort) or self.settings.get("models.executor_effort")
        result = ExecResult(text="", model=model, request=text, task_category=route.task_category,
                            task_status=route.task_status, product=meals.regular_product(self.store, route.product))

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
                      modules=route.modules, capabilities=self.capabilities(route),
                      tools=[t["name"] for t in ours] + web)

        started, last_text, round_no = time.perf_counter(), "", 0
        try:
            async for message in sdk.query(prompt=self._prompt(text, route, session, chat), options=options):
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
        error = None
        try:
            verdicts, source = await self.router.classify_tasks(result.request, labels), "jev"
        except Exception as exc:                 # no Jev: Claude does the classifier's job (the tools still check)
            verdicts, source, error = [("?", "?")] * len(tasks), "claude", f"{type(exc).__name__}: {exc}"[:300]
        for task, (category, status) in zip(tasks, verdicts):
            if category == "?":
                category = result.task_category or task.get("category")
            if update and not category:          # no category to move it to: leave the task where it is
                task.pop("category", None)
            else:
                task["category"] = category
            if not update:
                if status == "?":
                    status = result.task_status or task.get("status") or "todo"
                task["status"] = status
        self.bus.emit("tasks_classified", "router", request_id, session.id, source=source, error=error, tasks=[
            {"task": label, "category": t.get("category"), "status": t.get("status")} for label, t in zip(labels, tasks)])

    async def run_tool(self, name: str, args: dict[str, Any], session: Session, request_id: str,
                       result: ExecResult) -> tuple[str, bool]:
        """Run one tool call from Claude; returns (text for Claude, is_error)."""
        # Jev classifies, Claude executes: the category (and a new task's status) and a meal's type and description
        # are Jev's call - Claude's own values are used only when Jev cannot answer.
        meal_type_by = None
        if name == "task_create":
            await self._jev_classifies(args.get("tasks") or [], result, session, request_id)
        elif name == "task_update" and args.get("category"):     # moving a task to a category
            await self._jev_classifies([args], result, session, request_id, update=True)
        elif name == "task_update" and result.task_status and not (set(args) - {"task_id", "note"}):
            args["status"] = result.task_status                  # "zrobione" said about a task
        elif name.endswith("__log_meal"):
            meal_type_by = await meals.fill_in(args, result.request, result.product, self.router.classify_meal)

        # Alfred's own tools act on the user's own (already checked) words - they are checked only once outside
        # content has entered this request and could have planted instructions.
        if result.untrusted or name not in TOOLS:
            verdict = await self.router.check_action(result.request, name, args)
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

        if name.startswith("nutrition__log_"):          # what he said -> what was saved, for the Dieta tab
            balance = None
            if name.endswith("__log_meal") and not is_error:      # the meal routine
                note, balance = await meals.after_meal(self.hub, self.settings)
                output = f"{output}\n\n{note}"
            self.bus.emit("nutrition_logged", "executor", request_id, session.id, said=result.request, tool=name,
                          input=args, source=meal_type_by, ok=not is_error, balance=balance)
        return str(output), is_error
