"""Check what GoatCounter's API returns for the daily report's queries.

The daily report sometimes gets HTTP 404 "not found" from ``/stats/hits`` and
otherwise shows no visitors. This sends the same requests the report sends,
plus a few simpler ones that narrow down the cause, and prints the status and
a short summary of each response:

- ``/me``: is the token valid?
- ``/sites``: can the token see the site code it is used with?
- ``/stats/total`` and ``/stats/hits`` with GoatCounter's default range: does
  the site have any recorded visits at all?
- ``/stats/hits`` and ``/stats/toprefs`` with the report's exact queries for the
  last day and the last 7 days, and once with plain dates instead of hours.

The token is never printed. Run with GOATCOUNTER_TOKEN set, or it asks for it:

    python -m scripts.goatcounter_check
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from scripts.download_report import stats_query


DEFAULT_CODE = "fungusta"


@dataclass(frozen=True)
class Response:
    status: int
    body: object  # Parsed JSON, or the raw text when it isn't JSON.


def request(url: str, token: str) -> Response:
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json",
        "User-Agent": "cat-type-goatcounter-check"})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as error:
        status, raw = error.code, error.read()
    text = raw.decode("utf-8", "replace")
    try:
        return Response(status, json.loads(text))
    except ValueError:
        return Response(status, text)


def _error(body: object) -> str:
    if isinstance(body, dict):
        detail = body.get("error") or body.get("errors")
        if detail:
            return detail if isinstance(detail, str) else json.dumps(detail)
    text = body if isinstance(body, str) else json.dumps(body)
    return " ".join(text.split())[:300]


def summarize(path: str, body: object, code: str) -> str:
    """One line on what a successful response holds, without secrets."""
    if not isinstance(body, dict):
        return "not JSON: " + _error(body)
    if path == "/me":
        return "token is valid"
    if path == "/sites":
        codes = [site.get("code") for site in body.get("sites", [])]
        seen = "includes" if code in codes else "does NOT include"
        return f"token sees {len(codes)} site(s); {seen} '{code}'"
    if path.startswith("/stats/total"):
        return f"total={body.get('total')} total_events={body.get('total_events')} total_utc={body.get('total_utc')}"
    if path.startswith("/stats/hits"):
        hits = body.get("hits") or []
        listed = ", ".join(f"{hit.get('path')}{' (event)' if hit.get('event') else ''}={hit.get('count')}"
                           for hit in hits[:8])
        return f"{len(hits)} path(s), total={body.get('total')}" + (f": {listed}" if listed else "")
    if path.startswith("/stats/toprefs"):
        return f"{len(body.get('stats') or [])} referrer(s)"
    return f"keys: {', '.join(body)}"


def probes(now: datetime) -> list[tuple[str, str]]:
    """(label, API path) pairs, simplest first."""
    day, week = stats_query(now - timedelta(days=1), now), stats_query(now - timedelta(days=7), now)
    dates = urllib.parse.urlencode({"start": f"{now - timedelta(days=7):%Y-%m-%d}", "end": f"{now:%Y-%m-%d}"})
    return [
        ("token", "/me"),
        ("site access", "/sites"),
        ("total, default range", "/stats/total"),
        ("hits, default range", "/stats/hits"),
        ("hits, report's last day", f"/stats/hits?{day}"),
        ("hits, report's last 7 days", f"/stats/hits?{week}"),
        ("hits, last 7 days as dates", f"/stats/hits?{dates}"),
        ("referrers, report's last 7 days", f"/stats/toprefs?{week}"),
    ]


def run(code: str, token: str, now: datetime, get=request, pause: float = 0.3, out=sys.stdout) -> int:
    api = f"https://{code}.goatcounter.com/api/v0"
    failures = 0
    for index, (label, path) in enumerate(probes(now)):
        if index:
            time.sleep(pause)  # GoatCounter allows 4 requests a second.
        try:
            response = get(api + path, token)
        except OSError as error:
            failures += 1
            print(f"FAIL ---  {label}\n          {path}\n          {type(error).__name__}: {error}", file=out)
            continue
        ok = 200 <= response.status < 300
        failures += not ok
        detail = summarize(path, response.body, code) if ok else _error(response.body)
        print(f"{'ok  ' if ok else 'FAIL'} {response.status}  {label}\n          {path}\n          {detail}", file=out)
    print(f"\n{failures} of {len(probes(now))} requests failed." if failures else "\nAll requests succeeded.", file=out)
    return 1 if failures else 0


def main(argv: list[str] | None = None, env: dict[str, str] | None = None) -> int:
    env = dict(os.environ) if env is None else env
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--code", default=env.get("GOATCOUNTER_CODE", "").strip() or DEFAULT_CODE,
                        help=f"GoatCounter site code (default: GOATCOUNTER_CODE or {DEFAULT_CODE})")
    args = parser.parse_args(argv)
    token = env.get("GOATCOUNTER_TOKEN", "").strip()
    if not token:
        if not sys.stdin.isatty():
            print("Set GOATCOUNTER_TOKEN to a GoatCounter API key.", file=sys.stderr)
            return 2
        token = getpass.getpass("GoatCounter API key (not shown): ").strip()
    return run(args.code, token, datetime.now(timezone.utc))


if __name__ == "__main__":
    raise SystemExit(main())
