import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from scripts import download_report as dr


SGT = timezone(timedelta(hours=8))
NOW = datetime(2026, 11, 5, 9, 0, tzinfo=SGT)


def release(**counts):
    return {"assets": [{"name": name, "download_count": count} for name, count in counts.items()]}


def snapshot(at, windows=0, mac_arm=0, mac_intel=0, sums=0):
    return {"at": at.isoformat(), "totals": {
        "Cat-Type-Windows-x64.exe": windows,
        "Cat-Type-macOS-arm64.dmg": mac_arm,
        "Cat-Type-macOS-x64.dmg": mac_intel,
        "SHA256SUMS.txt": sums,
    }}


class TotalsTests(unittest.TestCase):
    def test_sums_each_asset_across_every_release(self):
        releases = [
            release(**{"Cat-Type-Windows-x64.exe": 4, "SHA256SUMS.txt": 2}),
            release(**{"Cat-Type-Windows-x64.exe": 3, "Cat-Type-macOS-x64.dmg": 1}),
        ]
        totals = dr.totals(releases)
        self.assertEqual(totals["Cat-Type-Windows-x64.exe"], 7)
        self.assertEqual(totals["Cat-Type-macOS-x64.dmg"], 1)
        self.assertEqual(totals["SHA256SUMS.txt"], 2)
        self.assertEqual(totals["Cat-Type-Linux-x64.tar.gz"], 0)

    def test_ignores_unknown_assets(self):
        totals = dr.totals([release(**{"source.zip": 9})])
        self.assertNotIn("source.zip", totals)


class ReportTests(unittest.TestCase):
    def test_first_run_reports_a_baseline_without_inventing_a_delta(self):
        report = dr.build_report([snapshot(NOW, windows=10, sums=3)])
        self.assertIsNone(report.window)
        self.assertEqual(report.all_time_packages, 10)

    def test_day_delta_per_platform_and_new_download_estimate(self):
        history = [
            snapshot(NOW - timedelta(days=1), windows=10, mac_arm=2, sums=4),
            snapshot(NOW, windows=16, mac_arm=5, sums=6),
        ]
        report = dr.build_report(history)
        self.assertEqual(report.window.by_platform["Windows"], 6)
        self.assertEqual(report.window.by_platform["Mac (Apple Silicon)"], 3)
        self.assertEqual(report.window.packages, 9)
        self.assertEqual(report.window.updates, 2)
        self.assertEqual(report.window.new, 7)

    def test_estimate_never_goes_negative(self):
        history = [snapshot(NOW - timedelta(days=1)), snapshot(NOW, windows=1, sums=3)]
        self.assertEqual(dr.build_report(history).window.new, 0)

    def test_window_spans_since_the_previous_snapshot_even_after_a_missed_day(self):
        history = [snapshot(NOW - timedelta(days=2), windows=1), snapshot(NOW, windows=5)]
        window = dr.build_report(history).window
        self.assertEqual(window.end - window.start, timedelta(days=2))
        self.assertEqual(window.packages, 4)

    def test_week_compares_with_the_week_before_once_history_allows(self):
        history = [snapshot(NOW - timedelta(days=d), windows=100 - d * 3) for d in range(14, -1, -1)]
        report = dr.build_report(history)
        self.assertEqual(report.week.packages, 21)
        self.assertEqual(report.previous_week.packages, 21)

    def test_week_is_missing_until_seven_days_of_history_exist(self):
        history = [snapshot(NOW - timedelta(days=d), windows=10 - d) for d in range(3, -1, -1)]
        report = dr.build_report(history)
        self.assertIsNone(report.week)
        self.assertIsNone(report.previous_week)

    def test_daily_rows_list_the_last_seven_windows_newest_first(self):
        history = [snapshot(NOW - timedelta(days=d), windows=(10 - d) * 2) for d in range(9, -1, -1)]
        rows = dr.build_report(history).daily
        self.assertEqual(len(rows), 7)
        self.assertEqual(rows[0].end, NOW)
        self.assertTrue(all(row.packages == 2 for row in rows))


class FormatTests(unittest.TestCase):
    def history(self):
        return [
            snapshot(NOW - timedelta(days=1), windows=10, mac_arm=2, sums=4),
            snapshot(NOW, windows=16, mac_arm=5, sums=6),
        ]

    def test_subject_names_the_singapore_day_and_new_downloads(self):
        report = dr.build_report(self.history())
        self.assertEqual(dr.subject(report), "Cat Type downloads: 7 new on Wed 4 Nov")

    def test_text_body_lists_platforms_and_explains_the_estimate(self):
        text = dr.format_text(dr.build_report(self.history()))
        self.assertIn("Windows", text)
        self.assertIn("6", text)
        self.assertIn("SHA256SUMS", text)

    def test_html_escapes_nothing_unexpected_and_has_a_table(self):
        html = dr.format_html(dr.build_report(self.history()))
        self.assertIn("<table", html)
        self.assertIn("Mac (Apple Silicon)", html)

    def test_baseline_subject(self):
        report = dr.build_report([snapshot(NOW, windows=3)])
        self.assertIn("tracking started", dr.subject(report))


HITS = {"more": False, "hits": [
    {"path": "/cat-type/", "count": 40, "event": False},
    {"path": "/cat-type/privacy.html", "count": 3, "event": False},
    {"path": "download-hero-windows", "count": 5, "event": True},
    {"path": "download-footer-mac-intel", "count": 1, "event": True},
    {"path": "hero-see-platforms", "count": 2, "event": True},
]}
REFS = {"more": False, "stats": [{"name": "reddit.com", "count": 10}, {"name": "", "count": 20}]}


class WebsiteTests(unittest.TestCase):
    def test_summarises_landing_visitors_download_clicks_and_rate(self):
        site = dr.website_from(HITS, REFS)
        self.assertEqual(site.landing_visitors, 40)
        self.assertEqual(site.pages, {"/cat-type/": 40, "/cat-type/privacy.html": 3})
        self.assertEqual(site.download_clicks, 6)
        self.assertEqual(site.rate, "15%")
        self.assertEqual(site.buttons, [("Main button · Windows", 5), ("Footer · Mac (Intel)", 1),
                                        ("Main button · see all platforms", 2)])
        self.assertEqual(site.referrers, [("Direct or unknown", 20), ("reddit.com", 10)])

    def test_landing_page_counts_however_goatcounter_writes_the_path(self):
        # GoatCounter drops the trailing slash: the browser sends /cat-type/, the API returns /cat-type.
        for path in ("/cat-type", "/cat-type/", "/cat-type/index.html", "/", "/index.html"):
            site = dr.website_from({"hits": [{"path": path, "count": 7, "event": False}]}, {"stats": []})
            self.assertEqual(site.landing_visitors, 7, path)

    def test_other_pages_are_not_the_landing_page(self):
        hits = {"hits": [{"path": path, "count": 1, "event": False}
                         for path in ("/cat-type/privacy.html", "/privacy.html", "/cat-type/docs/")]}
        self.assertEqual(dr.website_from(hits, {"stats": []}).landing_visitors, 0)

    def test_rate_is_unavailable_without_visitors(self):
        site = dr.website_from({"hits": []}, {"stats": []})
        self.assertEqual(site.rate, "n/a")

    def test_fetch_queries_whole_utc_hours_with_the_token(self):
        calls = []

        def get(url, token):
            calls.append((url, token))
            return HITS if "/stats/hits" in url else REFS

        start = datetime(2026, 11, 4, 9, 7, tzinfo=SGT)
        dr.fetch_website("cat-type", "tok", start, NOW, get=get, pause=0)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(url.startswith("https://cat-type.goatcounter.com/api/v0/stats/") for url, _ in calls))
        self.assertIn("start=2026-11-04T01%3A00%3A00Z", calls[0][0])
        self.assertIn("end=2026-11-05T02%3A00%3A00Z", calls[0][0])
        self.assertEqual({token for _, token in calls}, {"tok"})

    def test_email_shows_the_website_section(self):
        history = [snapshot(NOW - timedelta(days=1), windows=10, sums=4), snapshot(NOW, windows=16, sums=6)]
        report = dr.with_website(dr.build_report(history), day=dr.website_from(HITS, REFS), week=None)
        text = dr.format_text(report)
        self.assertIn("Landing page visitors", text)
        self.assertIn("Main button · Windows", text)
        self.assertIn("reddit.com", text)
        self.assertIn("Main button · Windows", dr.format_html(report))
        self.assertEqual(dr.subject(report), "Cat Type: 4 new downloads, 40 visitors on Wed 4 Nov")

    def test_email_says_when_website_stats_were_unavailable(self):
        report = dr.with_website(dr.build_report([snapshot(NOW - timedelta(days=1)), snapshot(NOW)]),
                                 error="GoatCounter returned HTTP 401")
        self.assertIn("Website stats unavailable: GoatCounter returned HTTP 401", dr.format_text(report))


class MainTests(unittest.TestCase):
    def run_main(self, history, env, releases):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "history.json"
        if history is not None:
            path.write_text(json.dumps(history))
        sent = []
        with patch.object(dr, "fetch_releases", return_value=releases), \
             patch.object(dr, "send_email", side_effect=lambda *a: sent.append(a)), \
             patch.object(dr, "now", return_value=NOW), \
             patch("sys.stdout", io.StringIO()), patch("sys.stderr", io.StringIO()):
            code = dr.main(["--history", str(path), "--repo", "o/r"], env)
        return code, json.loads(path.read_text()), sent

    def test_appends_a_snapshot_and_emails_when_smtp_is_configured(self):
        env = {"SMTP_USERNAME": "me@example.com", "SMTP_PASSWORD": "x"}
        code, history, sent = self.run_main(
            [snapshot(NOW - timedelta(days=1), windows=1)], env,
            [release(**{"Cat-Type-Windows-x64.exe": 4})])
        self.assertEqual(code, 0)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[-1]["totals"]["Cat-Type-Windows-x64.exe"], 4)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0][1], "me@example.com")

    def test_report_to_overrides_the_recipient(self):
        env = {"SMTP_USERNAME": "me@example.com", "SMTP_PASSWORD": "x", "REPORT_TO": "you@example.com"}
        _, _, sent = self.run_main(None, env, [])
        self.assertEqual(sent[0][1], "you@example.com")

    def test_goatcounter_failure_does_not_stop_the_report(self):
        env = {"SMTP_USERNAME": "me@example.com", "SMTP_PASSWORD": "x",
               "GOATCOUNTER_CODE": "cat-type", "GOATCOUNTER_TOKEN": "tok"}
        with patch.object(dr, "fetch_website", side_effect=OSError("down")):
            code, history, sent = self.run_main([snapshot(NOW - timedelta(days=1))], env, [])
        self.assertEqual(code, 0)
        self.assertEqual(len(history), 2)
        self.assertIn("Website stats unavailable", sent[0][3])

    def test_without_smtp_it_still_records_the_snapshot(self):
        code, history, sent = self.run_main(None, {}, [])
        self.assertEqual(code, 0)
        self.assertEqual(len(history), 1)
        self.assertEqual(sent, [])

    def test_a_failed_send_leaves_history_untouched(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "history.json"
        before = [snapshot(NOW - timedelta(days=1))]
        path.write_text(json.dumps(before))
        env = {"SMTP_USERNAME": "me@example.com", "SMTP_PASSWORD": "x"}
        with patch.object(dr, "fetch_releases", return_value=[]), \
             patch.object(dr, "send_email", side_effect=OSError("smtp down")), \
             patch.object(dr, "now", return_value=NOW), \
             patch("sys.stdout", io.StringIO()):
            with self.assertRaises(OSError):
                dr.main(["--history", str(path), "--repo", "o/r"], env)
        self.assertEqual(json.loads(path.read_text()), before)


if __name__ == "__main__":
    unittest.main()
