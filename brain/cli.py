"""Command line:  alfred serve  (web UI)  |  alfred chat  (talk in the terminal)  |  alfred classify "text"  (test routing)
|  alfred mcp-login nutrition  (log in to an OAuth MCP server)."""
from __future__ import annotations

import argparse
import asyncio
import json


def _serve(host: str, port: int) -> None:
    import uvicorn
    uvicorn.run("brain.app:app", host=host, port=port, reload=False)


async def _chat() -> None:
    from .pipeline import Brain

    brain = Brain()
    await brain.start(with_scheduler=False)
    queue = brain.bus.subscribe()

    async def printer() -> None:
        while True:
            e = await queue.get()
            d = e.data
            if e.kind == "classified":
                print(f"  [router/{d['source']}] {d['module']}{'+' + ','.join(d['also']) if d['also'] else ''}"
                      f" skill={d['skill']} conf={d['confidence']:.2f} {d['latency_ms']}ms")
            elif e.kind == "action_check" and d["breach"]:
                print(f"  [shield] blocked {d['tool']}")
            elif e.kind == "tool_call":
                print(f"  [tool] {d['tool']} {json.dumps(d['input'], ensure_ascii=False)[:120]}")
            elif e.kind == "confirm_request":
                print(f"Alfred: {d['text']}  (answer tak/nie)")
            elif e.kind == "answer":
                print(f"Alfred: {d['text']}\n  [tokens] {d['usage']}")
            elif e.kind == "error":
                print(f"  [error] {d.get('message')}")

    printer_task = asyncio.create_task(printer())
    print("Alfred is listening. Type 'exit' to quit.\n")
    pending: set[asyncio.Task] = set()
    try:
        while True:
            line = (await asyncio.to_thread(input, "You: ")).strip()
            if line.lower() in ("exit", "quit"):
                break
            if line:
                task = asyncio.create_task(brain.handle_text(line))
                pending.add(task)
                task.add_done_callback(pending.discard)
                if not brain.guard.pending:
                    await asyncio.sleep(0.2)
                    while pending and not brain.guard.pending:
                        await asyncio.sleep(0.2)
    finally:
        printer_task.cancel()
        await brain.stop()


async def _classify(text: str) -> None:
    from .pipeline import Brain

    brain = Brain()
    route = await brain.router.classify(text)
    print(json.dumps(route.to_dict(), indent=2, ensure_ascii=False))


async def _mcp_login(name: str) -> None:
    """Log in to a remote "oauth": true server (nutrition) now: the browser opens, the tokens are saved in
    data/oauth/<name>.json and Alfred uses them on his next start."""
    from contextlib import AsyncExitStack

    from .config import Settings
    from .mcp_hub import MCPHub

    hub = MCPHub(Settings.load().path("mcp_config"))
    state = hub.servers.get(name)
    if not state or not state.config.get("oauth"):
        raise SystemExit(f"'{name}' is not an OAuth server in config/mcp.json")
    print(f"Logowanie do {name} - dokończ je w przeglądarce (czekam do 5 minut)...")
    async with AsyncExitStack() as stack:
        await asyncio.wait_for(hub._connect(stack, state), 300)
    print(f"Gotowe: {name} zalogowany, {len(state.tools)} narzędzi. Zrestartuj Alfreda.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="alfred")
    sub = parser.add_subparsers(dest="cmd", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    sub.add_parser("chat")
    cls = sub.add_parser("classify")
    cls.add_argument("text")
    login = sub.add_parser("mcp-login")
    login.add_argument("server", nargs="?", default="nutrition")
    args = parser.parse_args()
    if args.cmd == "serve":
        _serve(args.host, args.port)
    elif args.cmd == "chat":
        asyncio.run(_chat())
    elif args.cmd == "mcp-login":
        asyncio.run(_mcp_login(args.server))
    else:
        asyncio.run(_classify(args.text))


if __name__ == "__main__":
    main()
