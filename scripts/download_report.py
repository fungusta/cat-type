"""Email a daily report of Cat Type downloads and website visits.

GitHub only keeps a running ``download_count`` for each release asset, so every
run records a snapshot of the totals and reports the change since the previous
one. The in-app updater fetches the same packages as people downloading from
the website, but it also always fetches ``SHA256SUMS.txt`` first, which the
website never links to. Package downloads minus checksum downloads is
therefore a fair estimate of new downloads.

Website visitors and download-button clicks come from GoatCounter's API when
GOATCOUNTER_CODE and GOATCOUNTER_TOKEN are set. GoatCounter counts visitors
(one per browser session), not raw page views.

Standard library only, so the workflow needs no dependencies.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import smtplib
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path


SGT = timezone(timedelta(hours=8), "SGT")
CHECKSUMS = "SHA256SUMS.txt"
PLATFORMS = {
    "Cat-Type-Windows-x64.exe": "Windows",
    "Cat-Type-macOS-arm64.dmg": "Mac (Apple Silicon)",
    "Cat-Type-macOS-x64.dmg": "Mac (Intel)",
    "Cat-Type-Linux-x64.tar.gz": "Linux (x64)",
    "Cat-Type-Linux-arm64.tar.gz": "Linux (arm64)",
}
TRACKED = (*PLATFORMS, CHECKSUMS)
# Scheduled runs can start late, so a snapshot a little after the target
# still counts as "a week ago".
LATE_RUN_ALLOWANCE = timedelta(hours=6)


def now() -> datetime:
    return datetime.now(SGT)


def fetch_releases(repo: str, token: str | None) -> list[dict]:
    releases: list[dict] = []
    page = 1
    while True:
        request = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/releases?per_page=100&page={page}",
            headers={"Accept": "application/vnd.github+json", "User-Agent": "cat-type-download-report",
                     **({"Authorization": f"Bearer {token}"} if token else {})},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            batch = json.load(response)
        releases.extend(batch)
        if len(batch) < 100:
            return releases
        page += 1


def totals(releases: list[dict]) -> dict[str, int]:
    counts = dict.fromkeys(TRACKED, 0)
    for item in releases:
        for asset in item.get("assets", []):
            if asset.get("name") in counts:
                counts[asset["name"]] += int(asset.get("download_count", 0))
    return counts


@dataclass(frozen=True)
class Window:
    start: datetime
    end: datetime
    by_platform: dict[str, int]
    updates: int

    @property
    def packages(self) -> int:
        return sum(self.by_platform.values())

    @property
    def new(self) -> int:
        return max(0, self.packages - self.updates)


SLUG_LABELS = {"windows": "Windows", "mac-arm64": "Mac (Apple Silicon)", "mac-intel": "Mac (Intel)"}
PLACEMENT_LABELS = {"hero": "Main button", "footer": "Footer"}


def _button_label(name: str) -> str:
    """'download-hero-windows' -> 'Main button · Windows'."""
    if name.endswith("-see-platforms"):
        placement = name.removesuffix("-see-platforms")
        return f"{PLACEMENT_LABELS.get(placement, placement)} · see all platforms"
    parts = name.split("-", 2)
    if len(parts) == 3 and parts[0] == "download":
        return f"{PLACEMENT_LABELS.get(parts[1], parts[1])} · {SLUG_LABELS.get(parts[2], parts[2])}"
    return name


@dataclass(frozen=True)
class Website:
    pages: dict[str, int]
    events: dict[str, int]
    referrers: list[tuple[str, int]]

    @property
    def landing_visitors(self) -> int:
        return sum(count for path, count in self.pages.items() if path.endswith(("/", "/index.html")))

    @property
    def download_clicks(self) -> int:
        return sum(count for name, count in self.events.items() if name.startswith("download-"))

    @property
    def rate(self) -> str:
        if not self.landing_visitors:
            return "n/a"
        return f"{round(100 * self.download_clicks / self.landing_visitors)}%"

    @property
    def buttons(self) -> list[tuple[str, int]]:
        # Downloads first, busiest first; other clicks after.
        ordered = sorted(self.events.items(), key=lambda item: (not item[0].startswith("download-"), -item[1]))
        return [(_button_label(name), count) for name, count in ordered]


def website_from(hits: dict, refs: dict) -> Website:
    pages = {hit["path"]: hit["count"] for hit in hits.get("hits", []) if not hit.get("event")}
    events = {hit["path"]: hit["count"] for hit in hits.get("hits", []) if hit.get("event")}
    referrers = sorted(((stat.get("name") or "Direct or unknown", stat["count"]) for stat in refs.get("stats", [])),
                       key=lambda item: -item[1])
    return Website(pages, events, referrers[:5])


def _get_json(url: str, token: str) -> dict:
    request = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json",
        "User-Agent": "cat-type-download-report"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def _hour(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_website(code: str, token: str, start: datetime, end: datetime, get=_get_json, pause: float = 0.3) -> Website:
    api = f"https://{code}.goatcounter.com/api/v0/stats"
    query = urllib.parse.urlencode({"start": _hour(start), "end": _hour(end), "limit": 100})
    hits = get(f"{api}/hits?{query}", token)
    time.sleep(pause)  # GoatCounter allows 4 requests a second.
    refs = get(f"{api}/toprefs?{query}", token)
    return website_from(hits, refs)


@dataclass(frozen=True)
class Report:
    at: datetime
    window: Window | None
    week: Window | None
    previous_week: Window | None
    daily: list[Window]
    all_time: dict[str, int]
    website: Website | None = None
    website_week: Website | None = None
    website_error: str | None = None

    @property
    def all_time_packages(self) -> int:
        return sum(self.all_time.get(name, 0) for name in PLATFORMS)


def _parse(entry: dict) -> tuple[datetime, dict[str, int]]:
    return datetime.fromisoformat(entry["at"]).astimezone(SGT), entry["totals"]


def _between(older: dict, newer: dict) -> Window:
    start, before = _parse(older)
    end, after = _parse(newer)
    change = lambda name: max(0, after.get(name, 0) - before.get(name, 0))  # noqa: E731
    return Window(start, end, {label: change(name) for name, label in PLATFORMS.items()}, change(CHECKSUMS))


def _at_or_before(history: list[dict], moment: datetime) -> dict | None:
    candidates = [entry for entry in history if _parse(entry)[0] <= moment + LATE_RUN_ALLOWANCE]
    return candidates[-1] if candidates else None


def build_report(history: list[dict]) -> Report:
    latest = history[-1]
    at, all_time = _parse(latest)
    window = _between(history[-2], latest) if len(history) > 1 else None
    week_ago = _at_or_before(history[:-1], at - timedelta(days=7))
    fortnight_ago = _at_or_before(history[:-1], at - timedelta(days=14))
    week = _between(week_ago, latest) if week_ago else None
    previous_week = _between(fortnight_ago, week_ago) if week_ago and fortnight_ago and fortnight_ago is not week_ago else None
    daily = [_between(a, b) for a, b in zip(history[:-1], history[1:])][-7:][::-1]
    return Report(at, window, week, previous_week, daily, all_time)


def with_website(report: Report, day: Website | None = None, week: Website | None = None,
                 error: str | None = None) -> Report:
    return replace(report, website=day, website_week=week, website_error=error)


def _day(moment: datetime) -> str:
    return f"{moment:%a} {moment.day} {moment:%b}"


def _span(window: Window) -> str:
    if window.end - window.start <= timedelta(hours=30):
        return f"on {_day(window.start)}"
    return f"since {_day(window.start)}"


def subject(report: Report) -> str:
    if report.window is None:
        return "Cat Type downloads: tracking started"
    if report.website is not None:
        return (f"Cat Type: {report.window.new} new downloads, "
                f"{report.website.landing_visitors} visitors {_span(report.window)}")
    return f"Cat Type downloads: {report.window.new} new {_span(report.window)}"


def _change(week: Window, previous: Window | None) -> str:
    if previous is None:
        return ""
    difference = week.new - previous.new
    return f" ({'+' if difference >= 0 else ''}{difference} vs the week before)"


EXPLANATION = (
    "New downloads are package downloads minus SHA256SUMS.txt downloads: the in-app "
    "updater fetches that checksum file with every update, and the website never links to it. "
    "Counts come from GitHub release assets, so they also include downloads from the "
    "GitHub releases page and any bots."
)


WEBSITE_EXPLANATION = (
    "Website numbers come from GoatCounter and count visitors (one per browser session), "
    "not page views. Each button counts the visitors who pressed it, and the click rate is "
    "download clicks divided by landing page visitors. Ad blockers hide some visits."
)


def _website_text(site: Website) -> list[str]:
    lines = [f"  {'Landing page visitors':<30}{site.landing_visitors:>6}",
             f"  {'Download clicks':<30}{site.download_clicks:>6}",
             f"  {'Click rate':<30}{site.rate:>6}"]
    lines += [f"    {label:<28}{count:>6}" for label, count in site.buttons]
    if site.referrers:
        lines += ["  Top referrers:"] + [f"    {name:<28}{count:>6}" for name, count in site.referrers]
    return lines


def format_text(report: Report) -> str:
    lines = [subject(report), ""]
    if report.window is None:
        lines += ["This is the first snapshot. Tomorrow's email will show the change since now.", ""]
    else:
        window = report.window
        lines += [f"{_day(window.start)} {window.start:%H:%M} to {_day(window.end)} {window.end:%H:%M} SGT", ""]
        lines += [f"  {label:<22}{count:>6}" for label, count in window.by_platform.items()]
        lines += [
            f"  {'All packages':<22}{window.packages:>6}",
            f"  {'Updates (estimated)':<22}{window.updates:>6}",
            f"  {'New (estimated)':<22}{window.new:>6}",
            "",
        ]
    if report.website_error:
        lines += [f"Website stats unavailable: {report.website_error}", ""]
    if report.website:
        lines += ["Website, same period:"] + _website_text(report.website) + [""]
    if report.week:
        lines += [f"Last 7 days: {report.week.new} new, {report.week.packages} packages{_change(report.week, report.previous_week)}", ""]
    if report.website_week:
        lines += ["Website, last 7 days:"] + _website_text(report.website_week) + [""]
    if len(report.daily) > 1:
        lines += ["Recent days (new / packages):"]
        lines += [f"  {_day(row.start):<12}{row.new:>4} / {row.packages}" for row in report.daily]
        lines += [""]
    lines += [f"All time: {report.all_time_packages} package downloads across every release.", "", EXPLANATION]
    if report.website or report.website_week:
        lines += ["", WEBSITE_EXPLANATION]
    return "\n".join(lines) + "\n"


def format_html(report: Report) -> str:
    e = html.escape
    cell = 'style="padding:4px 12px;border-bottom:1px solid #eee"'
    num = 'style="padding:4px 12px;border-bottom:1px solid #eee;text-align:right"'
    parts = [f'<div style="font-family:Segoe UI,Avenir Next,Arial,sans-serif;color:#222;max-width:560px">',
             f"<h2 style=\"margin:0 0 4px\">{e(subject(report))}</h2>"]
    if report.window is None:
        parts.append("<p>This is the first snapshot. Tomorrow's email will show the change since now.</p>")
    else:
        window = report.window
        parts.append(f'<p style="color:#666;margin:0 0 12px">{e(_day(window.start))} {window.start:%H:%M} '
                     f"to {e(_day(window.end))} {window.end:%H:%M} SGT</p>")
        rows = [*window.by_platform.items(), ("All packages", window.packages),
                ("Updates (estimated)", window.updates)]
        parts.append('<table style="border-collapse:collapse">')
        parts += [f"<tr><td {cell}>{e(label)}</td><td {num}>{count}</td></tr>" for label, count in rows]
        parts.append(f"<tr><td {cell}><b>New (estimated)</b></td><td {num}><b>{window.new}</b></td></tr></table>")
    if report.website_error:
        parts.append(f'<p style="color:#a33">Website stats unavailable: {e(report.website_error)}</p>')
    if report.website:
        parts.append(_website_html("Website, same period", report.website, cell, num))
    if report.week:
        parts.append(f"<p><b>Last 7 days:</b> {report.week.new} new, {report.week.packages} packages"
                     f"{e(_change(report.week, report.previous_week))}</p>")
    if report.website_week:
        parts.append(_website_html("Website, last 7 days", report.website_week, cell, num))
    if len(report.daily) > 1:
        parts.append(f'<table style="border-collapse:collapse"><tr><th {cell}>Day</th><th {num}>New</th><th {num}>Packages</th></tr>')
        parts += [f"<tr><td {cell}>{e(_day(row.start))}</td><td {num}>{row.new}</td><td {num}>{row.packages}</td></tr>"
                  for row in report.daily]
        parts.append("</table>")
    parts.append(f"<p>All time: {report.all_time_packages} package downloads across every release.</p>")
    parts.append(f'<p style="color:#888;font-size:12px">{e(EXPLANATION)}</p>')
    if report.website or report.website_week:
        parts.append(f'<p style="color:#888;font-size:12px">{e(WEBSITE_EXPLANATION)}</p>')
    parts.append("</div>")
    return "".join(parts)


def _website_html(title: str, site: Website, cell: str, num: str) -> str:
    e = html.escape
    indent = 'style="padding:4px 12px 4px 28px;border-bottom:1px solid #eee"'
    rows = [("Landing page visitors", site.landing_visitors), ("Download clicks", site.download_clicks),
            ("Click rate", site.rate)]
    parts = [f'<h3 style="margin:16px 0 4px">{e(title)}</h3><table style="border-collapse:collapse">']
    parts += [f"<tr><td {cell}>{e(label)}</td><td {num}>{value}</td></tr>" for label, value in rows]
    parts += [f"<tr><td {indent}>{e(label)}</td><td {num}>{count}</td></tr>" for label, count in site.buttons]
    parts.append("</table>")
    if site.referrers:
        listed = ", ".join(f"{e(name)} ({count})" for name, count in site.referrers)
        parts.append(f'<p style="margin:8px 0 0">Top referrers: {listed}</p>')
    return "".join(parts)


def send_email(env: dict[str, str], recipient: str, subject_line: str, text: str, body_html: str) -> None:
    message = EmailMessage()
    message["Subject"] = subject_line
    message["From"] = env.get("SMTP_FROM") or env["SMTP_USERNAME"]
    message["To"] = recipient
    message.set_content(text)
    message.add_alternative(body_html, subtype="html")
    host = env.get("SMTP_HOST") or "smtp.gmail.com"
    port = int(env.get("SMTP_PORT") or 465)
    with smtplib.SMTP_SSL(host, port, timeout=30) as server:
        server.login(env["SMTP_USERNAME"], env["SMTP_PASSWORD"])
        server.send_message(message)


def add_website(report: Report, env: dict[str, str]) -> Report:
    code, token = env.get("GOATCOUNTER_CODE", "").strip(), env.get("GOATCOUNTER_TOKEN", "")
    if not (code and token) or report.window is None:
        return report
    try:
        day = fetch_website(code, token, report.window.start, report.window.end)
        week = fetch_website(code, token, report.week.start, report.week.end) if report.week else None
    except Exception as error:  # noqa: BLE001 - website stats must never stop the download report
        status = getattr(error, "code", None)
        reason = f"GoatCounter returned HTTP {status}" if isinstance(status, int) else f"{type(error).__name__}: {error}"
        print(f"Website stats unavailable: {reason}", file=sys.stderr)
        return with_website(report, error=reason)
    return with_website(report, day=day, week=week)


def main(argv: list[str] | None = None, env: dict[str, str] | None = None) -> int:
    env = dict(os.environ) if env is None else env
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--history", type=Path, required=True, help="JSON file of earlier snapshots")
    parser.add_argument("--repo", default=env.get("GITHUB_REPOSITORY", "fungusta/cat-type"))
    parser.add_argument("--dry-run", action="store_true", help="print the report without emailing or saving")
    args = parser.parse_args(argv)

    history = json.loads(args.history.read_text()) if args.history.exists() else []
    history.append({"at": now().isoformat(timespec="seconds"),
                    "totals": totals(fetch_releases(args.repo, env.get("GITHUB_TOKEN")))})
    report = add_website(build_report(history), env)
    text = format_text(report)
    print(text)
    if summary := env.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(f"```\n{text}```\n")
    if args.dry_run:
        return 0

    if env.get("SMTP_USERNAME") and env.get("SMTP_PASSWORD"):
        # Send before saving: if delivery fails, the next report covers both days.
        send_email(env, env.get("REPORT_TO") or env["SMTP_USERNAME"], subject(report), text, format_html(report))
    else:
        print("SMTP_USERNAME and SMTP_PASSWORD are not set; recording the snapshot without emailing.", file=sys.stderr)
    args.history.parent.mkdir(parents=True, exist_ok=True)
    args.history.write_text(json.dumps(history, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
