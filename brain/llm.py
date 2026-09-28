"""Which Claude account the brain uses.

  subscription (default)  Claude Agent SDK -> your logged-in Claude Code (Pro/Max plan limits)
  api                     Anthropic Messages API with ANTHROPIC_API_KEY (billed per token)

The light calls (fallback router, session summaries) go through `light_client()`, which exposes the
same `messages.create(...)` shape in both modes.
"""
from __future__ import annotations

import json
import logging
import os
from types import SimpleNamespace
from typing import Any

log = logging.getLogger("alfred.llm")


# $ per 1M tokens: input, output, cache read, cache write (5-min TTL). Anthropic list prices, 2026-06.
# First matching prefix wins, so longer ids come first.
PRICES = {
    "claude-fable-5-1": (10, 50, 0.25, 12.5),
    "claude-fable-5": (10, 50, 1, 12.5),
    "claude-opus-5-5": (4, 20, 0.2, 5),
    "claude-opus-5": (5, 25, 0.5, 6.25),
    "claude-opus-4-8": (5, 25, 0.5, 6.25),
    "claude-opus-4-7": (5, 25, 0.5, 6.25),
    "claude-opus-4-6": (5, 25, 0.5, 6.25),
    "claude-sonnet-5": (2, 10, 0.2, 2.5),
    "claude-sonnet-4": (3, 15, 0.3, 3.75),
    "claude-haiku-4-5": (1, 5, 0.1, 1.25),
}


def cost_usd(model: str, usage: dict[str, int]) -> float | None:
    """What a call costs at API list prices; None for a model missing from PRICES."""
    price = next((p for prefix, p in PRICES.items() if (model or "").startswith(prefix)), None)
    if price is None:
        return None
    tokens = [usage.get(k, 0) for k in ("input", "output", "cache_read", "cache_write")]
    return sum(t * p for t, p in zip(tokens, price)) / 1e6


def backend(settings) -> str:
    return settings.get("llm.backend", "subscription")


def prepare_environment(settings) -> None:
    """In subscription mode an ANTHROPIC_API_KEY in the environment would make Claude Code bill the
    API account instead of the plan, so it is removed from this process (and its children)."""
    if backend(settings) == "subscription" and os.environ.pop("ANTHROPIC_API_KEY", None):
        log.info("Subscription mode: ignoring ANTHROPIC_API_KEY so Claude Code uses your plan.")


class _SubscriptionMessages:
    def __init__(self, settings):
        self.settings = settings

    async def create(self, *, model: str, system: str = "", messages: list[dict[str, Any]],
                     output_config: dict[str, Any] | None = None, max_tokens: int | None = None, **_: Any):
        from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query

        prompt = "\n\n".join(m["content"] if isinstance(m["content"], str) else json.dumps(m["content"])
                             for m in messages if m["role"] == "user")
        fmt = (output_config or {}).get("format")
        options = ClaudeAgentOptions(
            system_prompt=system or None, tools=[], allowed_tools=[], permission_mode="dontAsk",
            setting_sources=[], strict_mcp_config=True, model=model, max_turns=3,
            output_format={"type": "json_schema", "schema": fmt["schema"]} if fmt else None,
            cwd=str(self.settings.path("memory.dir").parent),
        )
        text, usage, cost = "", {}, None
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                parts = [b.text for b in message.content if isinstance(b, TextBlock)]
                text = " ".join(parts) or text
            elif isinstance(message, ResultMessage):
                usage, cost = message.usage or {}, message.total_cost_usd
                if fmt and message.structured_output is not None:
                    text = json.dumps(message.structured_output, ensure_ascii=False)
                elif message.result:
                    text = message.result
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=text)],
            usage=SimpleNamespace(input_tokens=int(usage.get("input_tokens", 0) or 0),
                                  output_tokens=int(usage.get("output_tokens", 0) or 0),
                                  cost_usd=cost),        # Claude Code's own figure, cache included
        )


class SubscriptionClient:
    """Mimics `anthropic.AsyncAnthropic().messages.create` on top of the Agent SDK."""

    def __init__(self, settings):
        self.messages = _SubscriptionMessages(settings)


def light_client(settings):
    if backend(settings) == "subscription":
        return SubscriptionClient(settings)
    if settings.anthropic_key:
        import anthropic
        return anthropic.AsyncAnthropic()
    return None


def subscription_status() -> dict[str, Any]:
    """`claude auth status` - is Claude Code logged in, and with what."""
    import shutil
    import subprocess

    exe = shutil.which("claude")
    if not exe:
        return {"ok": False, "detail": "Claude Code CLI not found - install it and run `claude` once to log in."}
    try:
        out = subprocess.run([exe, "auth", "status"], capture_output=True, text=True, timeout=20)
        data = json.loads(out.stdout or "{}")
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError) as exc:
        return {"ok": False, "detail": f"Could not read `claude auth status`: {exc}"}
    return {"ok": bool(data.get("loggedIn")), "method": data.get("authMethod"),
            "detail": "subscription (claude.ai)" if data.get("authMethod") == "claude.ai" else data.get("authMethod")}
