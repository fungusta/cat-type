import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from usage_metrics import UsageMetrics, UsageStore, UsageTracker


class UsageMetricsTests(unittest.TestCase):
    def test_records_only_daily_and_hourly_aggregate_counts(self) -> None:
        metrics = UsageMetrics()

        metrics.record(datetime(2026, 8, 25, 9, 15, tzinfo=timezone.utc))
        metrics.record(datetime(2026, 8, 25, 9, 59, tzinfo=timezone.utc))
        metrics.record(datetime(2026, 8, 26, 14, 0, tzinfo=timezone.utc))

        self.assertEqual(metrics.total_keystrokes, 3)
        self.assertEqual(metrics.daily, {"2026-08-25": 2, "2026-08-26": 1})
        self.assertEqual(metrics.hourly["2026-08-25T09"], 2)
        self.assertEqual(metrics.hourly["2026-08-26T14"], 1)

    def test_time_series_zero_fills_missing_days_and_hours(self) -> None:
        metrics = UsageMetrics(
            total_keystrokes=8,
            daily={"2026-08-23": 3, "2026-08-25": 5},
            hourly={"2026-08-25T09": 5},
        )

        self.assertEqual(
            metrics.daily_series(3, ending_on=date(2026, 8, 25)),
            [
                (date(2026, 8, 23), 3),
                (date(2026, 8, 24), 0),
                (date(2026, 8, 25), 5),
            ],
        )
        self.assertEqual(metrics.hourly_series(date(2026, 8, 25))[9], 5)
        self.assertEqual(sum(metrics.hourly_series(date(2026, 8, 24))), 0)

    def test_bad_and_future_payload_values_are_safely_normalized(self) -> None:
        metrics = UsageMetrics.from_payload(
            {
                "version": 99,
                "total_keystrokes": -8,
                "daily": {"2026-08-25": 4, "not-a-day": 99},
                "hourly": {"2026-08-25T09": 4, "2026-08-25T99": 99},
                "future_field": "ignored",
            }
        )

        self.assertEqual(metrics.total_keystrokes, 4)
        self.assertEqual(metrics.daily, {"2026-08-25": 4})
        self.assertEqual(metrics.hourly, {"2026-08-25T09": 4})


class UsageStoreTests(unittest.TestCase):
    def test_metrics_survive_a_new_store_instance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "usage.json"
            metrics = UsageMetrics()
            metrics.record(datetime(2026, 8, 25, 18, tzinfo=timezone.utc))

            UsageStore(path).save(metrics)
            restarted_metrics = UsageStore(path).load()

            self.assertEqual(restarted_metrics.total_keystrokes, 1)
            self.assertEqual(restarted_metrics.daily["2026-08-25"], 1)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["version"], 1)
            self.assertNotIn("keys", payload)
            self.assertNotIn("text", payload)

    def test_bad_file_falls_back_to_empty_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "usage.json"
            path.write_text("{bad json", encoding="utf-8")
            self.assertEqual(UsageStore(path).load(), UsageMetrics())

    def test_tracker_batches_writes_and_flushes_at_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "usage.json"
            tracker = UsageTracker(
                UsageStore(path),
                now=lambda: datetime(2026, 8, 25, 10, tzinfo=timezone.utc),
                flush_threshold=2,
            )

            tracker.record()
            self.assertFalse(path.exists())
            tracker.record()

            self.assertTrue(path.exists())
            self.assertEqual(UsageStore(path).load().total_keystrokes, 2)
            self.assertEqual(tracker.pending_keystrokes, 0)


if __name__ == "__main__":
    unittest.main()
