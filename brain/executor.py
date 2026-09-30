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
from typing import Any, Callable

import claude_agent_sdk as sdk

from . import llm, persona
from .atlas import BrainMap
from .mcp_hub import MCPHub
from .memory import MemoryStore, Session
from .modules import ModuleRegistry
from .router import Route
from .tools import CONFIRM_TOOL, MUTATING, TOOLS, WEB_TOOLS, make_handlers

SERVER = "alfred"   # our tools reach Claude Code as an in-process MCP server with this name
FAILED = {"pl": "Coś poszło nie tak po mojej stronie, {addr}. Spróbuj proszę za chwilę.",
          "en": "Something went wrong on my side, {addr}. Please try again in a moment."}
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


def _describe(name: str, args: dict[str, Any]) -> str:
    return f"{name.split('__')[-1]} {json.dumps(args, ensure_ascii=False)[:160]}"


class Executor:
    def __init__(self, settings, registry: ModuleRegistry, brain_map: BrainMap, hub: MCPHub, store: MemoryStore,
                 guard: Guard, bus, tts=None, shield: Callable | None = None, routines: Callable = lambda: []):
        self.settings, self.registry, self.map, self.hub = settings, registry, brain_map, hub
        self.guard, self.bus, self.tts, self.shield, self.routines = guard, bus, tts, shield, routines
        routines_file = settings.path("proactive.routines") if settings.get("proactive.routines") else None
        self.handlers = make_handlers(store, routines_file)

    def capabilities(self, route: Route) -> list[str]:
        """The route's capabilities + the skill's + the modules' "always" ones + the context sources from config."""
        caps = list(route.capabilities) or self.map.capabilities_of(route.modules)
        extra = (self.map.skills.get(route.skill or "", {}).get("uses", []) + self.map.always_capabilities(route.modules)
                 + [c for c in self.settings.get("assistant.context_capabilities") or [] if c in self.map.capabilities])
        return list(dict.fromkeys(caps + extra))

    def tool_names(self, route: Route) -> list[str]:
        return self.map.tools_of(self.capabilities(route))

    def _instructions(self, route: Route) -> str:
        modules = [m for m in map(self.registry.get, route.modules) if m]
        parts = [f"## Module: {m.label}\n{m.prompt}".strip() for m in modules]
        if skill := self.registry.skill(route.skill):
            parts.append(f"## Procedure to follow: {skill.name}\n{skill.body}")
        if routines := [f"- {r['id']} ({r['schedule']}): {r['prompt']}" for r in self.routines()]:
            parts.append("## Your routines (config/routines.yaml)\n" + "\n".join(routines))
        return persona.system_prompt(self.settings) + "\n\n" + ("\n\n".join(parts) or "No module instructions.")

    def _prompt(self, text: str, route: Route, session: Session) -> str:
        history = "\n".join(f"{m['role']}: {m['content']}" for m in session.history_messages())
        blocks = [f"<conversation_so_far>\n{history}\n</conversation_so_far>"] if history else []
        if not session.turns or route.needs_history >= 0.5:
            blocks.append(f"<memory_briefing>\n{session.briefing}\n</memory_briefing>")
        hints = [f"now={datetime.now().astimezone():%A %Y-%m-%d %H:%M%z}", f"module={','.join(route.modules)}",
                 f"urgency={route.urgency:.1f}"]
        if route.topic:
            hints.append(f"knowledge topic={self.map.topics.get(route.topic, {}).get('title', route.topic)}")
        if route.clarify:
            hints.append("routing is unsure - ask one short clarifying question if needed")
        return "\n\n".join([*blocks, f"<routing>{'; '.join(hints)}</routing>", text])

    async def run(self, text: str, route: Route, session: Session, request_id: str) -> ExecResult:
        lead = self.registry.get(route.module)
        model = (lead and lead.model) or self.settings.get("models.executor")
        effort = (lead and lead.effort) or self.settings.get("models.executor_effort")
        result = ExecResult(text="", model=model, request=text)

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

    async def run_tool(self, name: str, args: dict[str, Any], session: Session, request_id: str,
                       result: ExecResult) -> tuple[str, bool]:
        """Run one tool call from Claude; returns (text for Claude, is_error)."""
        # Alfred's own tools act on the user's own (already checked) words - they are checked only once outside
        # content has entered this request and could have planted instructions.
        if self.shield and (result.untrusted or name not in TOOLS):
            verdict = await self.shield(result.request, name, args)
            self.bus.emit("action_check", "shield", request_id, session.id, tool=name, **verdict)
            if verdict["breach"]:
                result.actions.append(f"blocked: {_describe(name, args)}")
                return BLOCKED, True

        if name == CONFIRM_TOOL or self.map.needs_confirmation(name):
            summary = (str(args.get("summary", "")) if name == CONFIRM_TOOL else "") or _describe(name, args)
            question = persona.confirm_prompt(session.language, summary.rstrip("."))
            audio = await self.tts.synthesize(question) if self.tts else None
            if not await self.guard.confirm(request_id, session.id, name, question, audio):
                return DECLINED, False
            result.actions.append(f"approved: {summary}")
            if name == CONFIRM_TOOL:
                return "approved - the user said yes, proceed.", False

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
        return str(output), is_error
