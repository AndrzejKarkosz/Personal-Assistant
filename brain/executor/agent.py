"""SubscriptionExecutor: runs Claude through the Claude Agent SDK, i.e. through your logged-in
Claude Code (`claude auth status` -> claude.ai), so requests use your Pro/Max subscription limits
instead of per-token API billing.

The brain stays in charge of the tools: every tool the route allows (built-ins and the MCP tools the
hub is already connected to) is exposed through one in-process SDK MCP server called "alfred", with
the guard inside the handler. Claude Code's own tools are switched off except WebSearch / WebFetch
when the route needs them, and no user/project settings, hooks or CLAUDE.md files are loaded.
"""
from __future__ import annotations

import time
from typing import Any

from ..memory import Session
from ..router import Route
from . import builtin
from .claude import FAILED, BaseExecutor, ExecResult

SDK_SERVER = "alfred"
WEB_TOOLS = {"web_search": "WebSearch", "web_fetch": "WebFetch"}


def sdk_name(tool: str) -> str:
    return f"mcp__{SDK_SERVER}__{tool}"


class SubscriptionExecutor(BaseExecutor):
    backend = "subscription"

    def _sdk_tools(self, names: list[str], session: Session, request_id: str, result: ExecResult):
        from claude_agent_sdk import tool

        live = self.hub.all_tools()
        tools = []
        for name in names:
            if builtin.is_builtin(name):
                spec = next(t for t in builtin.BUILTIN_TOOLS if t["name"] == name)
            elif name in live:
                spec = live[name]
            else:
                continue          # web tools are Claude Code built-ins, offline tools are skipped

            async def handler(args: dict[str, Any], _name: str = name) -> dict[str, Any]:
                text, is_error = await self.run_tool(_name, dict(args or {}), session, request_id, result)
                return {"content": [{"type": "text", "text": text}], "is_error": is_error}

            tools.append(tool(name, spec["description"], spec["input_schema"])(handler))
        return tools

    async def run(self, text: str, route: Route, session: Session, request_id: str) -> ExecResult:
        from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock,
                                      create_sdk_mcp_server, query)

        model, effort = self.model_and_effort(route)
        lang = session.language
        addr = (self.settings.get("assistant.address", {}) or {}).get(lang, "")
        result = ExecResult(text="", model=model)

        names = self.tool_names(route)
        sdk_tools = self._sdk_tools(names, session, request_id, result)
        web = [WEB_TOOLS[n] for n in names if n in WEB_TOOLS]
        persona_text, module_text = self.system_text(route)
        history = "\n".join(f"{m['role']}: {m['content']}" for m in session.history_messages())
        prompt = (f"<conversation_so_far>\n{history}\n</conversation_so_far>\n\n" if history else "") + \
            self.user_message(text, route, session)

        options = ClaudeAgentOptions(
            system_prompt=f"{persona_text}\n\n{module_text}",
            mcp_servers={SDK_SERVER: create_sdk_mcp_server(SDK_SERVER, tools=sdk_tools)} if sdk_tools else {},
            tools=web,                                     # Claude Code built-ins: only web, if routed
            allowed_tools=[sdk_name(t.name) for t in sdk_tools] + web,
            permission_mode="dontAsk",                     # anything not listed above is denied
            setting_sources=[],                            # no user settings, hooks or CLAUDE.md
            model=model,
            effort=effort,
            max_turns=int(self.settings.get("models.max_tool_rounds", 8)) + 1,
            cwd=str(self.settings.path("memory.dir").parent),
        )
        self.bus.emit("executor_start", "executor", request_id, session.id, model=model, effort=effort,
                      backend=self.backend, modules=route.modules, capabilities=self.capabilities(route),
                      tools=[t.name for t in sdk_tools] + web)

        started = time.perf_counter()
        last_text = ""
        round_no = 0
        try:
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    texts = [b.text for b in message.content if isinstance(b, TextBlock)]
                    if texts:
                        last_text = " ".join(texts).strip()
                    usage = message.usage or {}
                    self.bus.emit("llm_call", "executor", request_id, session.id, round=round_no,
                                  stop_reason=message.stop_reason or "", ms=int((time.perf_counter() - started) * 1000),
                                  usage={"input": int(usage.get("input_tokens", 0) or 0),
                                         "output": int(usage.get("output_tokens", 0) or 0)})
                    round_no += 1
                elif isinstance(message, ResultMessage):
                    u = message.usage or {}
                    result.usage = {"input": int(u.get("input_tokens", 0) or 0),
                                    "output": int(u.get("output_tokens", 0) or 0),
                                    "cache_read": int(u.get("cache_read_input_tokens", 0) or 0),
                                    "cache_write": int(u.get("cache_creation_input_tokens", 0) or 0)}
                    result.cost_usd = message.total_cost_usd
                    if message.is_error:
                        self.bus.emit("error", "executor", request_id, session.id,
                                      message=f"Claude Code: {message.subtype} {message.errors or ''}"[:500])
                    result.text = (message.result or last_text or "").strip()
        except Exception as exc:  # noqa: BLE001 - CLI missing, not logged in, rate limit ...
            self.bus.emit("error", "executor", request_id, session.id, message=f"{type(exc).__name__}: {exc}"[:500])
            result.text = FAILED[lang].format(addr=addr)
            return result
        result.text = result.text or last_text or ("Gotowe." if lang == "pl" else "Done.")
        return result
