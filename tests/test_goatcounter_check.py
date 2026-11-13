import io
import unittest
from datetime import datetime, timezone

from scripts import goatcounter_check as gc


NOW = datetime(2026, 11, 14, 8, 30, tzinfo=timezone.utc)
TOKEN = "secret-token-value"


def fake_get(responses):
    calls = []

    def get(url, token):
        calls.append((url, token))
        path = url.split("/api/v0", 1)[1]
        for prefix, response in responses.items():
            if path.startswith(prefix):
                return response
        return gc.Response(200, {})

    return get, calls


class ProbeTests(unittest.TestCase):
    def test_uses_the_reports_exact_hour_queries(self):
        paths = dict(gc.probes(NOW))
        self.assertEqual(paths["hits, report's last day"],
                         "/stats/hits?start=2026-11-13T08%3A00%3A00Z&end=2026-11-14T09%3A00%3A00Z&limit=100")
        self.assertIn("start=2026-11-07&end=2026-11-14", paths["hits, last 7 days as dates"])

    def test_reports_failures_with_goatcounters_error_and_exits_nonzero(self):
        get, calls = fake_get({"/stats/hits?": gc.Response(404, {"error": "not found"})})
        out = io.StringIO()
        code = gc.run("cat-type", TOKEN, NOW, get=get, pause=0, out=out)
        self.assertEqual(code, 1)
        self.assertIn("FAIL 404  hits, report's last day", out.getvalue())
        self.assertIn("not found", out.getvalue())
        self.assertIn("3 of 8 requests failed", out.getvalue())
        self.assertTrue(all(url.startswith("https://cat-type.goatcounter.com/api/v0/") for url, _ in calls))

    def test_summaries_show_counts_and_site_access_but_never_the_token(self):
        get, _ = fake_get({
            "/sites": gc.Response(200, {"sites": [{"code": "other"}]}),
            "/stats/hits": gc.Response(200, {"total": 3, "hits": [
                {"path": "/cat-type/", "count": 3, "event": False},
                {"path": "download-hero-windows", "count": 1, "event": True}]}),
        })
        out = io.StringIO()
        self.assertEqual(gc.run("cat-type", TOKEN, NOW, get=get, pause=0, out=out), 0)
        text = out.getvalue()
        self.assertIn("does NOT include 'cat-type'", text)
        self.assertIn("2 path(s), total=3: /cat-type/=3, download-hero-windows (event)=1", text)
        self.assertNotIn(TOKEN, text)

    def test_network_errors_are_reported_not_raised(self):
        def get(url, token):
            raise OSError("connection refused")

        out = io.StringIO()
        self.assertEqual(gc.run("cat-type", TOKEN, NOW, get=get, pause=0, out=out), 1)
        self.assertIn("OSError: connection refused", out.getvalue())

    def test_non_json_error_pages_are_trimmed(self):
        self.assertEqual(gc._error("<html>\n  <title>Error</title>\n</html>"), "<html> <title>Error</title> </html>")


if __name__ == "__main__":
    unittest.main()
