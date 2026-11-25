from __future__ import annotations

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import macos_secure_input
from cat_settings import AppSettings
from cat_type import CatTypeApp
from macos_secure_input import (
    SECURE_INPUT_OFF,
    SecureInputState,
    SecureInputWatch,
    read_secure_input_state,
)

TERMINAL = SecureInputState(True, 42, "Terminal")


class SecureInputWatchTests(unittest.TestCase):
    def test_short_password_field_stretch_is_not_mentioned(self) -> None:
        watch = SecureInputWatch(notice_after=30)
        self.assertFalse(watch.update(TERMINAL, 0))
        self.assertFalse(watch.update(TERMINAL, 10))
        self.assertFalse(watch.update(SECURE_INPUT_OFF, 12))
        self.assertFalse(watch.update(TERMINAL, 20))
        self.assertFalse(watch.update(TERMINAL, 45))

    def test_long_stretch_is_mentioned_once_per_app(self) -> None:
        watch = SecureInputWatch(notice_after=30)
        watch.update(TERMINAL, 0)
        self.assertTrue(watch.update(TERMINAL, 31))
        self.assertFalse(watch.update(TERMINAL, 90))
        watch.update(SECURE_INPUT_OFF, 91)
        watch.update(TERMINAL, 100)
        self.assertFalse(watch.update(TERMINAL, 200))

        other = SecureInputState(True, 7, "iTerm2")
        self.assertFalse(watch.update(other, 201))
        self.assertTrue(watch.update(other, 232))

    def test_unnamed_holder_reads_as_another_app(self) -> None:
        self.assertEqual(SecureInputState(True).holder_label, "another app")


class ReadSecureInputStateTests(unittest.TestCase):
    def test_off_when_carbon_reports_off(self) -> None:
        with patch.object(macos_secure_input, "_secure_event_input_enabled", return_value=False):
            self.assertEqual(read_secure_input_state(), SECURE_INPUT_OFF)

    def test_off_when_carbon_is_missing(self) -> None:
        with patch.object(macos_secure_input, "_secure_event_input_enabled", side_effect=OSError):
            self.assertEqual(read_secure_input_state(), SECURE_INPUT_OFF)

    def test_names_the_app_holding_it(self) -> None:
        quartz = SimpleNamespace(
            CGSessionCopyCurrentDictionary=lambda: {"kCGSSessionSecureInputPID": 42}
        )
        app = Mock()
        app.localizedName.return_value = "Terminal"
        running = Mock()
        running.runningApplicationWithProcessIdentifier_.return_value = app
        with patch.object(macos_secure_input, "_secure_event_input_enabled", return_value=True), \
                patch.dict(sys.modules, {"Quartz": quartz,
                                         "AppKit": SimpleNamespace(NSRunningApplication=running)}):
            self.assertEqual(read_secure_input_state(), TERMINAL)
        running.runningApplicationWithProcessIdentifier_.assert_called_once_with(42)

    def test_still_reports_on_when_holder_is_unknown(self) -> None:
        with patch.object(macos_secure_input, "_secure_event_input_enabled", return_value=True), \
                patch.dict(sys.modules, {"Quartz": None}):
            self.assertEqual(read_secure_input_state(), SecureInputState(True))


class AppSecureInputTests(unittest.TestCase):
    def app(self, *, reading: SecureInputState, enabled: bool = True) -> CatTypeApp:
        app = CatTypeApp.__new__(CatTypeApp)
        app.settings = AppSettings(enabled=enabled)
        app._requires_input_monitoring = True
        app._activity_monitoring_started = True
        app._shutting_down = False
        app._secure_input_watch = SecureInputWatch(notice_after=30)
        app._secure_input_reader = Mock(return_value=reading)
        app._secure_input_poll_id = None
        app._tray_icon = Mock()
        app.root = Mock()
        app.root.after.return_value = "secure-poll"
        app._notify_secure_input = Mock()
        return app

    def test_poll_names_the_holder_in_the_tray_and_reschedules(self) -> None:
        app = self.app(reading=TERMINAL)
        app._poll_secure_input()

        self.assertEqual(app._tray_icon.title, "Cat Type — Secure Keyboard Entry is on in Terminal")
        app._tray_icon.update_menu.assert_called_once_with()
        self.assertEqual(app._secure_input_menu_label(None), "Typing Hidden by Terminal…")
        app.root.after.assert_called_once_with(2_000, app._poll_secure_input)
        app._notify_secure_input.assert_not_called()

    def test_poll_posts_a_notice_after_a_long_stretch(self) -> None:
        app = self.app(reading=TERMINAL)
        with patch("cat_type.time.monotonic", return_value=0):
            app._poll_secure_input()
        with patch("cat_type.time.monotonic", return_value=31):
            app._poll_secure_input()
        app._notify_secure_input.assert_called_once_with()

    def test_paused_cat_does_not_check_or_report(self) -> None:
        app = self.app(reading=TERMINAL, enabled=False)
        app._poll_secure_input()

        app._secure_input_reader.assert_not_called()
        self.assertFalse(app._secure_input_blocking())
        self.assertEqual(app._tray_title(), "Cat Type — Input monitoring paused")

    def test_notice_names_the_holder_or_says_another_app(self) -> None:
        for reading, opening in ((TERMINAL, "Terminal has"), (SecureInputState(True), "Another app has")):
            app = CatTypeApp.__new__(CatTypeApp)
            app._tray_icon = None
            app._secure_input_watch = SecureInputWatch()
            app._secure_input_watch.update(reading, 0)
            with patch("cat_type.post_notice", return_value=True) as post:
                app._notify_secure_input()
            title, message, identifier = post.call_args.args[:3]
            self.assertEqual(title, "Your cat can't see your typing")
            self.assertTrue(message.startswith(opening), message)
            self.assertEqual(identifier, "secure-keyboard-entry")


if __name__ == "__main__":
    unittest.main()
