"""Claude, run through your logged-in Claude Code (Claude Agent SDK): it counts against your Pro/Max plan, there is
no API key and no per-token bill. Every call starts a Claude Code process (~1-2 s).

- ask_json(): one quick question whose answer must be JSON (router and security fallbacks, session summaries).
- The executor (executor.py) uses the same SDK to run the full agent with tools.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from typing import Any

import claude_agent_sdk as sdk

log = logging.getLogger("alfred.llm")


def hide_api_key() -> None:
    """With ANTHROPIC_API_KEY set, Claude Code would bill the API per token instead of using your plan."""
    if os.environ.pop("ANTHROPIC_API_KEY", None):
        log.info("Ignoring ANTHROPIC_API_KEY so Claude Code uses your subscription.")


def options(settings, **extra: Any) -> sdk.ClaudeAgentOptions:
    """Claude Code with everything of its own switched off: no Bash or file tools, no CLAUDE.md, hooks or settings."""
    bare = {"tools": [], "allowed_tools": [], "permission_mode": "dontAsk", "setting_sources": [],
            "strict_mcp_config": True, "cwd": str(settings.path("memory.dir").parent)}
    return sdk.ClaudeAgentOptions(**bare | extra)


def usage_of(message: sdk.ResultMessage) -> dict[str, Any]:
    u = message.usage or {}
    return {"input": int(u.get("input_tokens") or 0), "output": int(u.get("output_tokens") or 0),
            "cache_read": int(u.get("cache_read_input_tokens") or 0),
            "cache_write": int(u.get("cache_creation_input_tokens") or 0), "cost_usd": message.total_cost_usd}


async def ask_json(settings, prompt: str, schema: dict, system: str = "") -> tuple[dict, dict]:
    """Ask the light model one question; returns (answer matching `schema`, usage). Raises if Claude fails."""
    opts = options(settings, system_prompt=system or None, model=settings.get("models.light"), max_turns=3,
                   output_format={"type": "json_schema", "schema": schema})
    async for message in sdk.query(prompt=prompt, options=opts):
        if isinstance(message, sdk.ResultMessage) and isinstance(message.structured_output, dict):
            return message.structured_output, usage_of(message)
    raise RuntimeError("Claude returned no JSON answer")


def subscription_status() -> dict[str, Any]:
    """Is Claude Code installed and logged in? Shown in the UI header."""
    exe = shutil.which("claude")
    if not exe:
        return {"ok": False, "detail": "Claude Code CLI not found - install it and run `claude` once to log in."}
    try:
        data = json.loads(subprocess.run([exe, "auth", "status"], capture_output=True, text=True, timeout=20).stdout
                          or "{}")
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError) as exc:
        return {"ok": False, "detail": f"Could not read `claude auth status`: {exc}"}
    method = data.get("authMethod")
    return {"ok": bool(data.get("loggedIn")), "method": method,
            "detail": "subscription (claude.ai)" if method == "claude.ai" else method}
