import sys
import unittest
from dataclasses import fields
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from macos_pointer import MacOSPointerMonitor, PointerClick, RecentPointerClick


class RecentPointerClickTests(unittest.TestCase):
    def test_latest_click_is_available_for_eight_seconds(self) -> None:
        clicks = RecentPointerClick(max_age_seconds=8.0)
        clicks.record(120.4, 240.6, happened_at=10.0)

        self.assertEqual(
            clicks.latest(now=18.0),
            PointerClick(120.4, 240.6, 10.0),
        )
        self.assertIsNone(clicks.latest(now=18.001))

    def test_future_or_missing_click_is_not_returned(self) -> None:
        clicks = RecentPointerClick(max_age_seconds=8.0)

        self.assertIsNone(clicks.latest(now=10.0))
        clicks.record(10, 20, happened_at=11.0)
        self.assertIsNone(clicks.latest(now=10.0))

    def test_only_pointer_coordinates_and_time_are_retained(self) -> None:
        self.assertEqual(
            {field.name for field in fields(PointerClick)},
            {"x", "y", "happened_at"},
        )


class MacOSPointerMonitorTests(unittest.TestCase):
    def test_monitor_records_only_primary_button_presses(self) -> None:
        primary = object()
        secondary = object()
        listeners = []

        class FakeListener:
            def __init__(self, on_click: object) -> None:
                self.on_click = on_click
                self.started = False
                self.stopped = False
                listeners.append(self)

            def start(self) -> None:
                self.started = True

            def stop(self) -> None:
                self.stopped = True

            def join(self, timeout: float) -> None:
                self.timeout = timeout

        fake_pynput = ModuleType("pynput")
        fake_pynput.mouse = SimpleNamespace(
            Button=SimpleNamespace(left=primary),
            Listener=FakeListener,
        )
        clicks = RecentPointerClick()
        monitor = MacOSPointerMonitor(clicks)

        with (
            patch.dict(sys.modules, {"pynput": fake_pynput}),
            patch("macos_pointer.time.monotonic", return_value=12.5),
        ):
            self.assertTrue(monitor.start())
            listener = listeners[0]
            listener.on_click(10, 20, secondary, True)
            listener.on_click(30, 40, primary, False)
            self.assertIsNone(clicks.latest(now=12.5))

            listener.on_click(50.25, 60.75, primary, True)

        self.assertEqual(
            clicks.latest(now=12.5),
            PointerClick(50.25, 60.75, 12.5),
        )
        monitor.stop()
        self.assertTrue(listener.stopped)
        self.assertEqual(listener.timeout, 1.0)

    def test_monitor_failure_keeps_pointer_fallback_available(self) -> None:
        class BrokenListener:
            def __init__(self, on_click: object) -> None:
                del on_click

            def start(self) -> None:
                raise RuntimeError("mouse monitoring unavailable")

        fake_pynput = ModuleType("pynput")
        fake_pynput.mouse = SimpleNamespace(
            Button=SimpleNamespace(left=object()),
            Listener=BrokenListener,
        )
        monitor = MacOSPointerMonitor(RecentPointerClick())

        with patch.dict(sys.modules, {"pynput": fake_pynput}):
            self.assertFalse(monitor.start())

        monitor.stop()


if __name__ == "__main__":
    unittest.main()
