"""Executors: Claude with only the tools the route needs, and the guard in front of side effects.

Two backends share everything except the loop:
  ApiExecutor           Anthropic Messages API, billed per token (ANTHROPIC_API_KEY)
  SubscriptionExecutor  Claude Agent SDK -> your logged-in Claude Code (Pro/Max subscription)
                        (brain/executor/agent.py)

Which tools a request gets comes from the brain map: the route's capabilities (or every capability of
the routed modules), plus "always" capabilities and the chosen skill's. Confirmation rules come from
the map too (capability `confirm`, destructive tools, or `confirm_override` on a tool page).
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import anthropic

from ..memory import MemoryStore, Session
from ..modules import Module, ModuleRegistry
from ..router import Route
from ..voice import persona
from . import builtin
from .guard import Guard
from .mcp_hub import MCPHub

if TYPE_CHECKING:
    from ..atlas import BrainMap

SERVER_TOOLS = builtin.SERVER_TOOLS
# Models that get the server-side refusal fallback (re-run on a fallback model instead of stopping).
FALLBACK_MODELS = ("claude-opus-5", "claude-fable-5")
NO_EFFORT_MODELS = ("claude-haiku-4-5",)

REFUSAL = {"pl": "Niestety, z tym nie mogę pomóc.", "en": "I'm afraid I can't help with that one."}
FAILED = {"pl": "Coś poszło nie tak po mojej stronie, {addr}. Spróbuj proszę za chwilę.",
          "en": "Something went wrong on my side, {addr}. Please try again in a moment."}
DECLINED = "The user declined this action. Do not retry; acknowledge briefly."


@dataclass
class ExecResult:
    text: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    actions: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    declined: bool = False
    cost_usd: float | None = None


class BaseExecutor:
    backend = "base"

    def __init__(self, settings, registry: ModuleRegistry, brain_map: "BrainMap", hub: MCPHub,
                 store: MemoryStore, guard: Guard, bus, tts=None):
        self.settings = settings
        self.registry = registry
        self.map = brain_map
        self.hub = hub
        self.guard = guard
        self.bus = bus
        self.tts = tts
        self.handlers = builtin.make_handlers(store)

    # ---------------------------------------------------------------- selection
    def modules(self, route: Route) -> list[Module]:
        return [m for m in (self.registry.get(mid) for mid in route.modules) if m]

    def capabilities(self, route: Route) -> list[str]:
        caps = list(route.capabilities) or self.map.capabilities_of(route.modules)
        skill = self.map.skills.get(route.skill or "")
        extra = (skill or {}).get("uses", []) + self.map.always_capabilities(route.modules)
        return caps + [c for c in extra if c not in caps]

    def tool_names(self, route: Route) -> list[str]:
        return self.map.tools_of(self.capabilities(route))

    def model_and_effort(self, route: Route) -> tuple[str, str | None]:
        lead = next(iter(self.modules(route)), None)
        model = (lead.model if lead and lead.model else None) or self.settings.get("models.executor")
        effort = (lead.effort if lead and lead.effort else None) or self.settings.get("models.executor_effort")
        return model, effort

    def needs_confirmation(self, name: str) -> bool:
        return name == builtin.CONFIRM_TOOL or self.map.needs_confirmation(name)

    # ----------------------------------------------------------------- prompts
    def system_text(self, route: Route) -> tuple[str, str]:
        """(persona, module + skill instructions) - kept stable per module so they cache well."""
        parts = [f"## Module: {m.label}\n{m.prompt}".strip() for m in self.modules(route)]
        skill = self.registry.skill(route.skill)
        if skill:
            parts.append(f"## Procedure to follow: {skill.name}\n{skill.body}")
        return persona.system_prompt(self.settings), "\n\n".join(parts) or "No module instructions."

    def user_message(self, text: str, route: Route, session: Session) -> str:
        blocks = []
        if not session.turns or route.needs_history >= 0.5:
            blocks.append(f"<memory_briefing>\n{session.briefing}\n</memory_briefing>")
        hints = [f"module={','.join(route.modules)}", f"urgency={route.urgency:.1f}"]
        if route.topic:
            topic = self.map.topics.get(route.topic, {})
            hints.append(f"knowledge topic={topic.get('title', route.topic)}")
        if route.clarify:
            hints.append("routing is unsure - ask one short clarifying question if needed")
        blocks.append(f"<routing>{'; '.join(hints)}</routing>")
        blocks.append(text)
        return "\n\n".join(blocks)

    # ------------------------------------------------------------------- tools
    async def run_tool(self, name: str, args: dict[str, Any], session: Session, request_id: str,
                       result: ExecResult, spoken: str = "") -> tuple[str, bool]:
        """Runs one tool behind the guard. Returns (output text, is_error)."""
        if self.needs_confirmation(name):
            summary = str(args.get("summary", "")) if name == builtin.CONFIRM_TOOL else ""
            summary = summary or spoken or _describe(name, args)
            question = persona.confirm_prompt(self.settings, session.language, summary.rstrip("."))
            audio = await self.tts.synthesize(question) if self.tts else None
            approved = await self.guard.confirm(request_id, session.id, name, question, audio)
            if not approved:
                result.declined = True
                return DECLINED, False
            result.actions.append(f"approved: {summary}")
            if name == builtin.CONFIRM_TOOL:
                return "approved - the user said yes, proceed.", False

        node = self.node_of(name)
        self.bus.emit("tool_call", node, request_id, session.id, tool=name, input=args)
        result.tools_used.append(name)
        started = time.perf_counter()
        is_error = False
        try:
            if builtin.is_builtin(name):
                output = await self.handlers[name](args, session.id)
                if name in builtin.MUTATING:
                    result.actions.append(f"{name}: {_describe(name, args)}")
            elif self.hub.owns(name):
                output, is_error = await self.hub.call(name, args)
            else:
                output, is_error = f"Unknown tool {name}", True
        except Exception as exc:  # noqa: BLE001 - errors go back to Claude, not up the stack
            output, is_error = f"{type(exc).__name__}: {exc}", True
        self.bus.emit("tool_result", node, request_id, session.id, tool=name, is_error=is_error,
                      ms=int((time.perf_counter() - started) * 1000), preview=str(output)[:300])
        return str(output), is_error

    def node_of(self, name: str) -> str:
        tool = self.map.tools.get(name)
        return f"tool:{name}" if tool else ("memory" if builtin.is_builtin(name) else "executor")

    def no_backend_text(self, lang: str) -> str | None:
        return None

    async def run(self, text: str, route: Route, session: Session, request_id: str) -> ExecResult:
        raise NotImplementedError


class ApiExecutor(BaseExecutor):
    """Anthropic Messages API with a manual tool loop (billed per token)."""
    backend = "api"

    def __init__(self, client: anthropic.AsyncAnthropic | None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = client

    def tool_definitions(self, route: Route) -> list[dict[str, Any]]:
        live = self.hub.all_tools()
        defs = []
        for name in self.tool_names(route):
            if builtin.is_builtin(name):
                defs.append(next(t for t in builtin.BUILTIN_TOOLS if t["name"] == name))
            elif name in SERVER_TOOLS:
                defs.append(SERVER_TOOLS[name])
            elif name in live:
                defs.append(live[name])
        return defs

    async def run(self, text: str, route: Route, session: Session, request_id: str) -> ExecResult:
        model, effort = self.model_and_effort(route)
        lang = session.language
        addr = (self.settings.get("assistant.address", {}) or {}).get(lang, "")
        result = ExecResult(text="", model=model)
        if self.client is None:
            result.text = ("Brakuje klucza ANTHROPIC_API_KEY w pliku .env (tryb api)." if lang == "pl"
                           else "ANTHROPIC_API_KEY is missing from .env (api mode).")
            return result

        tools = self.tool_definitions(route)
        persona_text, module_text = self.system_text(route)
        system = [{"type": "text", "text": persona_text},
                  {"type": "text", "text": module_text, "cache_control": {"type": "ephemeral"}}]
        messages: list[dict[str, Any]] = session.history_messages() + [
            {"role": "user", "content": self.user_message(text, route, session)}]
        self.bus.emit("executor_start", "executor", request_id, session.id, model=model, effort=effort,
                      backend=self.backend, modules=route.modules, capabilities=self.capabilities(route),
                      tools=[t["name"] for t in tools])

        max_rounds = int(self.settings.get("models.max_tool_rounds", 8))
        response = None
        for round_no in range(max_rounds + 1):
            started = time.perf_counter()
            try:
                response = await self._create(model, effort, system, messages, tools)
            except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
                self.bus.emit("error", "executor", request_id, session.id, message=str(exc)[:500])
                result.text = FAILED[lang].format(addr=addr)
                return result
            usage = _usage_dict(response.usage)
            for k, v in usage.items():
                result.usage[k] = result.usage.get(k, 0) + v
            self.bus.emit("llm_call", "executor", request_id, session.id, round=round_no,
                          stop_reason=response.stop_reason, ms=int((time.perf_counter() - started) * 1000),
                          usage=usage)
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "tool_use" and round_no < max_rounds:
                messages.append({"role": "user", "content": await self._tool_results(
                    response.content, session, request_id, result)})
                continue
            if response.stop_reason == "pause_turn" and round_no < max_rounds:
                continue
            break

        if response is not None and response.stop_reason == "refusal":
            result.text = REFUSAL[lang]
        else:
            result.text = " ".join(b.text for b in response.content if b.type == "text").strip() if response else ""
        result.text = result.text or ("Gotowe." if lang == "pl" else "Done.")
        return result

    async def _create(self, model, effort, system, messages, tools):
        kwargs: dict[str, Any] = {"model": model, "max_tokens": 16000, "system": system, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        if effort and not model.startswith(NO_EFFORT_MODELS):
            kwargs["output_config"] = {"effort": effort}
        if model.startswith(FALLBACK_MODELS):
            return await self.client.beta.messages.create(
                betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
        return await self.client.messages.create(**kwargs)

    async def _tool_results(self, content, session, request_id, result) -> list[dict[str, Any]]:
        calls = [b for b in content if b.type == "tool_use"]
        spoken = " ".join(b.text for b in content if b.type == "text").strip()
        guarded = [c for c in calls if self.needs_confirmation(c.name)]
        outputs: dict[str, tuple[str, bool]] = {}
        for c in guarded:                          # one question at a time
            outputs[c.id] = await self.run_tool(c.name, dict(c.input or {}), session, request_id, result, spoken)
        free = [c for c in calls if c not in guarded]
        for c, out in zip(free, await asyncio.gather(
                *(self.run_tool(c.name, dict(c.input or {}), session, request_id, result) for c in free))):
            outputs[c.id] = out
        blocks = []
        for c in calls:                            # same order, all in one user message
            text, is_error = outputs[c.id]
            block: dict[str, Any] = {"type": "tool_result", "tool_use_id": c.id, "content": text}
            if is_error:
                block["is_error"] = True
            blocks.append(block)
        return blocks


# Backwards-compatible name.
Executor = ApiExecutor


def _usage_dict(usage) -> dict[str, int]:
    return {
        "input": int(getattr(usage, "input_tokens", 0) or 0),
        "output": int(getattr(usage, "output_tokens", 0) or 0),
        "cache_read": int(getattr(usage, "cache_read_input_tokens", 0) or 0),
        "cache_write": int(getattr(usage, "cache_creation_input_tokens", 0) or 0),
    }


def _describe(name: str, args: dict[str, Any]) -> str:
    return f"{name.split('__')[-1]} {json.dumps(args, ensure_ascii=False)[:160]}"
