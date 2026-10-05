"""Strava as an MCP server (stdio): Alfred reads your activities through it (config/mcp.json -> "strava").

Standalone on purpose - nothing from brain/ - so it can move to its own repository as it is.

Setup, once:
  1. https://www.strava.com/settings/api - an API application, "Authorization Callback Domain" = localhost
  2. .env: STRAVA_CLIENT_ID=...  STRAVA_CLIENT_SECRET=...
  3. uv run python server/strava_server.py --login    (opens the browser; the token is saved and refreshed by itself)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import webbrowser
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

load_dotenv()
API = "https://www.strava.com"
LOGIN_PORT = 8721
SPORT = {"Swim": "swim", "Ride": "bike", "VirtualRide": "bike", "GravelRide": "bike", "MountainBikeRide": "bike",
         "EBikeRide": "bike", "Run": "run", "TrailRun": "run", "VirtualRun": "run",
         "WeightTraining": "strength", "Crossfit": "strength", "Workout": "strength"}
KEEP = ("id", "name", "sport_type", "start_date_local", "moving_time", "distance", "total_elevation_gain",
        "average_heartrate", "max_heartrate", "average_watts", "kilojoules", "suffer_score", "trainer")


def token_file() -> Path:
    return Path(os.environ.get("STRAVA_TOKEN_FILE") or Path.home() / ".config" / "strava-mcp" / "token.json")


def _grant(**grant: str) -> dict:
    """Code or refresh token -> tokens, saved. Strava may hand out a new refresh token each time, so it is kept."""
    r = httpx.post(f"{API}/oauth/token", timeout=30, data={
        "client_id": os.environ["STRAVA_CLIENT_ID"], "client_secret": os.environ["STRAVA_CLIENT_SECRET"], **grant})
    r.raise_for_status()
    tokens = r.json()
    token_file().parent.mkdir(parents=True, exist_ok=True)
    token_file().write_text(json.dumps(tokens), encoding="utf-8")
    return tokens


def access_token() -> str:
    if not token_file().exists():
        raise RuntimeError("Not logged in to Strava - run: uv run python server/strava_server.py --login")
    tokens = json.loads(token_file().read_text(encoding="utf-8"))
    if tokens["expires_at"] < time.time() + 60:
        tokens = _grant(grant_type="refresh_token", refresh_token=tokens["refresh_token"])
    return tokens["access_token"]


mcp = MCPServer("strava")


@mcp.tool(structured_output=False)
def activities(start_date: str, end_date: str) -> str:
    """The user's Strava activities between two dates (YYYY-MM-DD, both included), oldest first, as JSON. Each has
    sport (swim / bike / run / strength / other), name, start_date_local, moving_time (s), distance (m),
    average_heartrate, kilojoules (rides with power), suffer_score (relative effort) and more."""
    after = int(datetime.fromisoformat(start_date).timestamp())
    before = int((datetime.fromisoformat(end_date) + timedelta(days=1)).timestamp())
    out, page = [], 1
    with httpx.Client(timeout=30, headers={"Authorization": f"Bearer {access_token()}"}) as http:
        while True:
            r = http.get(f"{API}/api/v3/athlete/activities",
                         params={"after": after, "before": before, "per_page": 200, "page": page})
            r.raise_for_status()
            batch = r.json()
            out += [{k: a[k] for k in KEEP if a.get(k) is not None} | {"sport": SPORT.get(a.get("sport_type"), "other")}
                    for a in batch]
            if len(batch) < 200:
                return json.dumps(out, ensure_ascii=False)
            page += 1


def login() -> None:
    """One-time OAuth: the browser asks you to allow access, Strava sends the code back to localhost."""
    got: dict[str, list[str]] = {}

    class Callback(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            got.update(parse_qs(urlparse(self.path).query))
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Strava połączona - możesz zamknąć tę kartę.".encode())

        def log_message(self, *args) -> None:
            pass

    url = f"{API}/oauth/authorize?" + urlencode({
        "client_id": os.environ["STRAVA_CLIENT_ID"], "redirect_uri": f"http://localhost:{LOGIN_PORT}/",
        "response_type": "code", "approval_prompt": "auto", "scope": "read,activity:read_all"})
    print(f"Otwieram przeglądarkę: {url}")
    webbrowser.open(url)
    with HTTPServer(("localhost", LOGIN_PORT), Callback) as server:
        while "code" not in got and "error" not in got:
            server.handle_request()
    if "code" not in got:
        sys.exit(f"Strava odmówiła dostępu: {got}")
    _grant(grant_type="authorization_code", code=got["code"][0])
    print(f"Gotowe - token zapisany w {token_file()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--login", action="store_true", help="log in to Strava once (opens the browser)")
    login() if parser.parse_args().login else mcp.run()
