import io
import queue
import sys
import unittest
from dataclasses import fields
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cat_type
from cat_settings import AppSettings
from cat_type import (
    AppEvent,
    AnimationState,
    CaretLocator,
    CaretSnapshot,
    CatTypeApp,
    KeyboardMonitor,
    MonitorArea,
    ScreenRect,
    classify_portable_key,
    classify_windows_key,
    choose_overlay_position,
)
from usage_metrics import UsageMetrics


class FakePortableKey:
    def __init__(
        self,
        char: str | None = None,
        name: str | None = None,
        vk: int | None = None,
    ) -> None:
        self.char = char
        self.name = name
        self.vk = vk


class KeyboardClassificationTests(unittest.TestCase):
    def test_windows_keys_follow_the_physical_keyboard_split(self) -> None:
        cases = (
            ((0x51, 0, 0), "left"),       # Q
            ((0x54, 0, 0), "left"),       # T
            ((0x59, 0, 0), "right"),      # Y
            ((0x4D, 0, 0), "right"),      # M
            ((0x20, 0, 0), "both"),       # Space
            ((0x70, 0, 0), "left"),       # F1
            ((0x76, 0, 0), "right"),      # F7
            ((0x10, 0x2A, 0), "left"),    # Generic left Shift
            ((0x10, 0x36, 0), "right"),   # Generic right Shift
            ((0x11, 0, 0), "left"),       # Generic left Ctrl
            ((0x11, 0, 1), "right"),      # Extended right Ctrl
            ((0x25, 0, 0), "right"),      # Left-arrow key cluster
            ((0x60, 0, 0), "right"),      # Numpad 0
            ((0xAD, 0, 0), "alternate"),  # Media mute
        )

        for arguments, expected in cases:
            with self.subTest(arguments=arguments):
                self.assertEqual(classify_windows_key(*arguments), expected)

    def test_portable_keys_follow_the_physical_keyboard_split(self) -> None:
        cases = (
            (FakePortableKey(char="q"), "left"),
            (FakePortableKey(char="!"), "left"),
            (FakePortableKey(char="y"), "right"),
            (FakePortableKey(char="^"), "right"),
            (FakePortableKey(char=" "), "both"),
            (FakePortableKey(name="space"), "both"),
            (FakePortableKey(name="shift_l"), "left"),
            (FakePortableKey(name="shift_r"), "right"),
            (FakePortableKey(name="alt_gr"), "right"),
            (FakePortableKey(name="f6"), "left"),
            (FakePortableKey(name="f7"), "right"),
            (FakePortableKey(name="left"), "right"),
            (FakePortableKey(name="media_volume_up"), "alternate"),
        )

        for key, expected in cases:
            with self.subTest(key=vars(key)):
                self.assertEqual(classify_portable_key(key), expected)

    def test_shifted_semicolon_stays_on_the_right(self) -> None:
        self.assertEqual(
            classify_portable_key(FakePortableKey(char=":")),
            "right",
        )

    def test_macos_keypad_metadata_takes_precedence_over_characters(self) -> None:
        keypad_keys = {
            0x41: ".",
            0x43: "*",
            0x45: "+",
            0x47: None,
            0x4B: "/",
            0x4C: "\r",
            0x4E: "-",
            0x51: "=",
            0x52: "0",
            0x53: "1",
            0x54: "2",
            0x55: "3",
            0x56: "4",
            0x57: "5",
            0x58: "6",
            0x59: "7",
            0x5B: "8",
            0x5C: "9",
        }

        with patch("cat_type.IS_MACOS", True):
            for vk, char in keypad_keys.items():
                with self.subTest(vk=vk, char=char):
                    self.assertEqual(
                        classify_portable_key(FakePortableKey(char=char, vk=vk)),
                        "right",
                    )

    def test_macos_top_row_digits_keep_the_qwerty_split(self) -> None:
        with patch("cat_type.IS_MACOS", True):
            self.assertEqual(
                classify_portable_key(FakePortableKey(char="1", vk=0x12)),
                "left",
            )
            self.assertEqual(
                classify_portable_key(FakePortableKey(char="6", vk=0x16)),
                "right",
            )

    def test_app_event_carries_a_paw_action_but_no_key_identity(self) -> None:
        event = AppEvent("key", 12.5, "left")

        self.assertEqual(event.paw, "left")
        self.assertEqual(
            {field.name for field in fields(event)},
            {"kind", "happened_at", "paw"},
        )


class KeyboardMonitorEventTests(unittest.TestCase):
    def test_emitted_key_event_contains_only_time_and_paw(self) -> None:
        events: queue.SimpleQueue[AppEvent] = queue.SimpleQueue()
        monitor = KeyboardMonitor(events)

        monitor._emit_key("left", happened_at=12.5)

        self.assertEqual(events.get_nowait(), AppEvent("key", 12.5, "left"))

    @unittest.skipUnless(sys.platform.startswith("linux"), "Xorg-only behavior")
    def test_xorg_listener_replaces_every_keypad_keysym_with_one_marker(
        self,
    ) -> None:
        from pynput import keyboard
        from pynput.keyboard import _xorg

        if keyboard.Listener.__module__ != "pynput.keyboard._xorg":
            self.skipTest("pynput Xorg backend is not active")
        listener_type = KeyboardMonitor._portable_listener_type(keyboard.Listener)
        listener = listener_type.__new__(listener_type)

        markers = set()
        required_names = {
            "KP_1",
            "KP_Add",
            "KP_Begin",
            "KP_Down",
            "KP_Enter",
            "KP_F1",
            "KP_F2",
            "KP_F3",
            "KP_F4",
            "KP_Separator",
            "KP_Space",
            "KP_Tab",
        }
        self.assertLessEqual(required_names, _xorg.KEYPAD_KEYS.keys())
        keypad_keysyms = frozenset(_xorg.KEYPAD_KEYS.values())
        for keysym in keypad_keysyms:
            display = FakeXorgDisplay(keysym, keysym)
            event = SimpleNamespace(detail=87, state=0)

            with self.subTest(keysym=keysym):
                key = listener._event_to_key(display, event)
                self.assertTrue(key._cat_type_keypad)
                self.assertFalse(hasattr(key, "__dict__"))
                self.assertFalse(hasattr(key, "char"))
                self.assertFalse(hasattr(key, "name"))
                self.assertFalse(hasattr(key, "vk"))
                self.assertNotIn(
                    key,
                    {
                        keyboard.Key.ctrl,
                        keyboard.Key.ctrl_l,
                        keyboard.Key.ctrl_r,
                        keyboard.Key.alt,
                        keyboard.Key.alt_l,
                        keyboard.Key.alt_r,
                        keyboard.Key.alt_gr,
                    },
                )
                markers.add(key)
                self.assertEqual(classify_portable_key(key), "right")
        self.assertEqual(len(markers), 1)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Xorg-only behavior")
    def test_xorg_keypad_marker_survives_numlock_and_center_mapping(
        self,
    ) -> None:
        from pynput import keyboard
        from pynput.keyboard import _xorg

        if keyboard.Listener.__module__ != "pynput.keyboard._xorg":
            self.skipTest("pynput Xorg backend is not active")
        listener_type = KeyboardMonitor._portable_listener_type(keyboard.Listener)
        listener = listener_type.__new__(listener_type)
        numlock_mask = 0x02
        key_pairs = (
            ("KP_End", "KP_1"),
            ("KP_Begin", "KP_5"),
        )

        for off_name, on_name in key_pairs:
            display = FakeXorgDisplay(
                _xorg.KEYPAD_KEYS[off_name],
                _xorg.KEYPAD_KEYS[on_name],
                numlock_mask=numlock_mask,
            )
            for state in (0, numlock_mask):
                event = SimpleNamespace(detail=87, state=state)

                with self.subTest(
                    off_name=off_name,
                    on_name=on_name,
                    numlock=bool(state),
                ):
                    key = listener._event_to_key(display, event)
                    self.assertTrue(key._cat_type_keypad)
                    self.assertEqual(classify_portable_key(key), "right")

    @unittest.skipUnless(sys.platform.startswith("linux"), "Xorg-only behavior")
    def test_xorg_ordinary_qwerty_keys_keep_the_physical_split(self) -> None:
        from pynput import keyboard

        if keyboard.Listener.__module__ != "pynput.keyboard._xorg":
            self.skipTest("pynput Xorg backend is not active")
        listener_type = KeyboardMonitor._portable_listener_type(keyboard.Listener)
        listener = listener_type.__new__(listener_type)
        cases = (
            (ord("1"), "left"),
            (ord("6"), "right"),
            (ord("q"), "left"),
            (ord("y"), "right"),
        )
        for keysym, expected in cases:
            display = FakeXorgDisplay(keysym, keysym)
            event = SimpleNamespace(detail=10, state=0)

            with self.subTest(keysym=keysym):
                key = listener._event_to_key(display, event)
                self.assertEqual(classify_portable_key(key), expected)

    def test_alt_gr_counts_as_alt_for_ctrl_alt_q_quit(self) -> None:
        from pynput import keyboard

        events: queue.SimpleQueue[AppEvent] = queue.SimpleQueue()
        monitor = KeyboardMonitor(events)

        class PlaybackListener:
            def __init__(self, on_press: object, on_release: object) -> None:
                self.on_press = on_press
                self.on_release = on_release

            def run(self) -> None:
                self.on_press(keyboard.Key.ctrl)
                self.on_press(keyboard.Key.alt_gr)
                self.on_press(keyboard.KeyCode.from_char("q"))
                self.on_release(keyboard.Key.alt_gr)
                self.on_release(keyboard.Key.ctrl)

        with patch.object(keyboard, "Listener", PlaybackListener):
            monitor._run_portable()

        emitted = []
        while not events.empty():
            event = events.get_nowait()
            emitted.append((event.kind, event.paw))
        self.assertEqual(
            emitted,
            [("key", "left"), ("key", "right"), ("quit", None)],
        )


class FakeXorgDisplay:
    def __init__(
        self,
        unshifted_keysym: int,
        shifted_keysym: int,
        numlock_mask: int = 0,
    ) -> None:
        self._keysyms = (unshifted_keysym, shifted_keysym)
        setattr(self, "__altgr_mask", 0)
        setattr(self, "__numlock_mask", numlock_mask)

    def keycode_to_keysym(self, _keycode: int, index: int) -> int:
        return self._keysyms[index & 1]


class CatTypeKeyActivityTests(unittest.TestCase):
    @staticmethod
    def make_app(enabled: bool = True) -> CatTypeApp:
        app = CatTypeApp.__new__(CatTypeApp)
        app.settings = AppSettings(enabled=enabled)
        app.animation = Mock()
        app.animation.is_visible.return_value = False
        app.tracker = Mock()
        app._anchor_position = (20, 30)
        app._last_key_at = 0.0
        app.keystroke_count = 0
        app._settings_window = None
        metrics = UsageMetrics()
        app.usage_tracker = Mock()
        app.usage_tracker.metrics = metrics

        def record_usage() -> UsageMetrics:
            metrics.record(
                datetime(2026, 8, 25, 10, tzinfo=timezone.utc)
            )
            return metrics

        app.usage_tracker.record.side_effect = record_usage
        return app

    def test_enabled_key_updates_animation_and_persistent_count(self) -> None:
        app = self.make_app()

        app._handle_key_activity(10.0, "left")

        self.assertEqual(app.keystroke_count, 1)
        self.assertIsNone(app._anchor_position)
        self.assertEqual(app._last_key_at, 10.0)
        app.animation.record_key.assert_called_once_with(10.0, "left")
        app.tracker.notify_activity.assert_called_once_with(10.0)
        self.assertEqual(app.usage_tracker.metrics.daily["2026-08-25"], 1)

    def test_disabled_key_does_not_increment_or_animate(self) -> None:
        app = self.make_app(enabled=False)

        app._handle_key_activity(10.0, "right")

        self.assertEqual(app.keystroke_count, 0)
        app.animation.record_key.assert_not_called()
        app.tracker.notify_activity.assert_not_called()

    def test_open_settings_counter_updates_live(self) -> None:
        app = self.make_app()
        settings_window = Mock()
        settings_window.window.winfo_exists.return_value = True
        app._settings_window = settings_window

        app._handle_key_activity(10.0, "both")

        settings_window.update_usage_metrics.assert_called_once()
        self.assertEqual(
            settings_window.update_usage_metrics.call_args.args[0].total_keystrokes,
            1,
        )

    def test_repeated_keydowns_count_individually(self) -> None:
        app = self.make_app()

        app._handle_key_activity(10.0, "right")
        app._handle_key_activity(10.1, "right")

        self.assertEqual(app.keystroke_count, 2)

    def test_open_settings_receives_the_persistent_metrics(self) -> None:
        app = self.make_app()
        app.root = Mock()
        app.keystroke_count = 42
        app.usage_tracker.metrics = UsageMetrics(total_keystrokes=42)

        with (
            patch("cat_type.SettingsWindow") as settings_window,
            patch("cat_type.APP_ICON") as app_icon,
            patch(
                "cat_type._macos_activation_policy_accessors_for_app",
                return_value=None,
            ) as activation_policy,
        ):
            app_icon.exists.return_value = False
            app.open_settings()

        activation_policy.assert_called_once_with()
        settings_window.assert_called_once()
        arguments, keywords = settings_window.call_args
        self.assertEqual(
            arguments,
            (app.root, app.settings, app.apply_settings, None),
        )
        self.assertEqual(keywords["keystroke_count"], 42)
        self.assertEqual(keywords["usage_metrics"].total_keystrokes, 42)
        self.assertEqual(
            keywords["on_metrics_view_change"],
            app._persist_metrics_view,
        )
        self.assertEqual(
            keywords["update_status"],
            "Ready to check for updates.",
        )
        self.assertTrue(callable(keywords["on_check_for_updates"]))
        self.assertTrue(callable(keywords["on_open_release_page"]))
        with patch("cat_type.webbrowser.open") as open_browser:
            keywords["on_open_release_page"]()
        open_browser.assert_called_once_with(
            "https://github.com/fungusta/cat-type/releases/latest"
        )

    def test_metrics_view_persistence_preserves_saved_companion_settings(
        self,
    ) -> None:
        app = CatTypeApp.__new__(CatTypeApp)
        app.settings = AppSettings(size_percent=125, metrics_view="line")
        app.settings_store = Mock()
        app.settings_store.save.side_effect = (
            lambda settings: settings.normalized()
        )

        app._persist_metrics_view("columns")

        saved = app.settings_store.save.call_args.args[0]
        self.assertEqual(saved.metrics_view, "columns")
        self.assertEqual(saved.size_percent, 125)
        self.assertEqual(app.settings.metrics_view, "columns")

    def test_metrics_view_write_failure_leaves_application_usable(
        self,
    ) -> None:
        app = CatTypeApp.__new__(CatTypeApp)
        app.settings = AppSettings(metrics_view="line")
        app.settings_store = Mock()
        app.settings_store.save.side_effect = OSError("read-only settings")

        app._persist_metrics_view("columns")

        self.assertEqual(app.settings.metrics_view, "line")

    def test_run_uses_startup_feedback_without_recording_a_key(self) -> None:
        app = CatTypeApp.__new__(CatTypeApp)
        app._start_tray = Mock()
        app.keyboard = Mock()
        app.tracker = Mock()
        app.animation = Mock()
        app.root = Mock()
        app._tick = Mock()
        app._first_run = False
        app._platform_name = "linux"
        app.settings = AppSettings()
        app.usage_tracker = Mock()

        with patch("cat_type.time.monotonic", return_value=12.5):
            app.run()

        app.animation.show_startup.assert_called_once_with(12.5)
        app.animation.record_key.assert_not_called()
        app.tracker.notify_activity.assert_called_once_with(12.5)
        app.root.after.assert_any_call(2000, app.check_for_updates)
        app.root.after.assert_any_call(
            app.USAGE_FLUSH_INTERVAL_MS,
            app._flush_usage_periodically,
        )

    def test_app_store_first_run_waits_for_explicit_monitoring_consent(self) -> None:
        app = CatTypeApp.__new__(CatTypeApp)
        app._start_tray = Mock()
        app.keyboard = Mock()
        app.tracker = Mock()
        app.animation = Mock()
        app.root = Mock()
        app._tick = Mock()
        app._first_run = False
        app._platform_name = "darwin"
        app._app_store_distribution = True
        app.settings = AppSettings(
            enabled=False,
            monitoring_consent=False,
        )
        app._request_monitoring_consent = Mock()
        app.usage_tracker = Mock()

        app.run()

        app.keyboard.start.assert_not_called()
        app.tracker.start.assert_not_called()
        app.root.after.assert_any_call(300, app._request_monitoring_consent)

    def test_direct_distribution_preserves_disabled_global_hotkey_listener(self) -> None:
        app = CatTypeApp.__new__(CatTypeApp)
        app.settings = AppSettings(enabled=False)
        app._app_store_distribution = False
        app._activity_monitoring_started = False
        app._tray_icon = None
        app.keyboard = Mock()
        app.tracker = Mock()

        app._ensure_activity_monitoring()

        app.keyboard.start.assert_called_once_with()
        app.tracker.start.assert_called_once_with()

    def test_app_store_permission_poll_starts_monitoring_after_access(self) -> None:
        app = CatTypeApp.__new__(CatTypeApp)
        app.settings = AppSettings(enabled=True, monitoring_consent=True)
        app._app_store_distribution = True
        app._platform_name = "darwin"
        app._activity_monitoring_started = False
        app._input_monitoring_requested = False
        app._monitoring_permission_poll_id = None
        app._input_monitoring_preflight = Mock(side_effect=[False, True])
        app._input_monitoring_request = Mock(return_value=False)
        app.keyboard = Mock()
        app.tracker = Mock()
        app._tray_icon = None
        app.root = Mock()
        app.root.after.return_value = "permission-poll"
        app._shutting_down = False

        app._ensure_activity_monitoring()

        app._input_monitoring_request.assert_called_once_with()
        app.keyboard.start.assert_not_called()
        self.assertEqual(
            app._monitoring_permission_poll_id,
            "permission-poll",
        )

        app._poll_input_monitoring_permission()

        app.keyboard.start.assert_called_once_with()
        app.tracker.start.assert_called_once_with()
        self.assertTrue(app._activity_monitoring_started)

    def test_app_store_tray_title_indicates_monitoring_status(self) -> None:
        app = CatTypeApp.__new__(CatTypeApp)
        app._app_store_distribution = True
        app._activity_monitoring_started = False
        app.settings = AppSettings(enabled=True, monitoring_consent=True)

        self.assertEqual(
            app._tray_title(),
            "Cat Type — Input monitoring paused",
        )

        app._activity_monitoring_started = True

        self.assertEqual(
            app._tray_title(),
            "Cat Type — Input monitoring active",
        )

    def test_app_store_consent_is_persisted_before_monitoring_starts(self) -> None:
        app = CatTypeApp.__new__(CatTypeApp)
        app.settings = AppSettings(enabled=False, monitoring_consent=False)
        app.settings_store = Mock()
        app.settings_store.save.side_effect = lambda value: value.normalized()
        app._confirm_monitoring = Mock(return_value=True)
        app._ensure_activity_monitoring = Mock()
        app._settings_window = None
        app._tray_icon = None
        app._hide = Mock()

        self.assertTrue(app._request_monitoring_consent())

        saved = app.settings_store.save.call_args.args[0]
        self.assertTrue(saved.monitoring_consent)
        self.assertTrue(saved.enabled)
        app._ensure_activity_monitoring.assert_called_once_with()

    def test_periodic_usage_flush_reschedules_while_app_is_running(self) -> None:
        app = CatTypeApp.__new__(CatTypeApp)
        app.usage_tracker = Mock()
        app.root = Mock()
        app.root.winfo_exists.return_value = True
        app._shutting_down = False

        app._flush_usage_periodically()

        app.usage_tracker.flush.assert_called_once_with()
        app.root.after.assert_called_once_with(
            app.USAGE_FLUSH_INTERVAL_MS,
            app._flush_usage_periodically,
        )


class CatTypeTickRenderingTests(unittest.TestCase):
    @staticmethod
    def make_app(
        *,
        overlay_visible: bool,
        snapshot: CaretSnapshot,
    ) -> CatTypeApp:
        app = CatTypeApp.__new__(CatTypeApp)
        app._shutdown_signal = None
        app.root = Mock()
        app.root.winfo_exists.return_value = True
        app._drain_update_events = Mock()
        app._shutting_down = False
        app._hook_failed = False
        app.settings = AppSettings(
            enabled=True,
            hold_seconds=1.5,
            fade_seconds=0.35,
        )
        app.animation = AnimationState(
            hide_after=1.5,
            fade_seconds=0.35,
        )
        app.animation.record_key(10.0, "left")
        app.events = queue.SimpleQueue()
        app.events.put(AppEvent("key", 10.10, "right"))
        app.keystroke_count = 1
        app._last_key_at = 10.0
        app._anchor_position = (100, 100) if overlay_visible else None
        app._overlay_visible = overlay_visible
        app._settings_window = None
        app.tracker = Mock()
        app.tracker.snapshot.return_value = snapshot
        app._show = Mock()
        app._hide = Mock()
        return app

    def test_visible_overlay_survives_briefly_stale_snapshot(self) -> None:
        snapshot = CaretSnapshot(
            captured_at=10.04,
            rect=ScreenRect(500, 300, 502, 320),
            source="test",
        )
        app = self.make_app(overlay_visible=True, snapshot=snapshot)

        with patch("cat_type.time.monotonic", return_value=10.11):
            app._tick()

        app._show.assert_called_once_with(snapshot, 10.11)
        app._hide.assert_not_called()

    def test_visible_overlay_without_anchor_waits_for_fresh_snapshot(self) -> None:
        snapshot = CaretSnapshot(
            captured_at=10.04,
            rect=ScreenRect(500, 300, 502, 320),
            source="test",
        )
        app = self.make_app(overlay_visible=True, snapshot=snapshot)
        app._anchor_position = None

        with patch("cat_type.time.monotonic", return_value=10.11):
            app._tick()

        app._show.assert_not_called()
        app._hide.assert_called_once_with(reset_anchor=False)

    def test_visible_overlay_rejects_stalled_old_snapshot(self) -> None:
        snapshot = CaretSnapshot(
            captured_at=9.0,
            rect=ScreenRect(500, 300, 502, 320),
            source="test",
        )
        app = self.make_app(overlay_visible=True, snapshot=snapshot)

        with patch("cat_type.time.monotonic", return_value=10.11):
            app._tick()

        app._show.assert_not_called()
        app._hide.assert_called_once_with(reset_anchor=False)

    def test_hidden_overlay_still_waits_for_fresh_snapshot(self) -> None:
        snapshot = CaretSnapshot(
            captured_at=10.04,
            rect=ScreenRect(500, 300, 502, 320),
            source="test",
        )
        app = self.make_app(overlay_visible=False, snapshot=snapshot)

        with patch("cat_type.time.monotonic", return_value=10.11):
            app._tick()

        app._show.assert_not_called()
        app._hide.assert_called_once_with(reset_anchor=False)

    def test_password_snapshot_hides_visible_overlay(self) -> None:
        snapshot = CaretSnapshot(
            captured_at=10.04,
            rect=None,
            is_password=True,
            source="uia-password",
        )
        app = self.make_app(overlay_visible=True, snapshot=snapshot)

        with patch("cat_type.time.monotonic", return_value=10.11):
            app._tick()

        app._show.assert_not_called()
        app._hide.assert_called_once_with(reset_anchor=True)


class FakeDegenerateTextRange:
    def __init__(
        self,
        can_move_forward: bool,
        forward_has_geometry: bool = True,
    ) -> None:
        self.can_move_forward = can_move_forward
        self.forward_has_geometry = forward_has_geometry

    def GetBoundingRectangles(self) -> tuple:
        return ()

    def Clone(self) -> "FakeTextRangeProbe":
        return FakeTextRangeProbe(
            self.can_move_forward,
            self.forward_has_geometry,
        )


class FakeTextRangeProbe:
    def __init__(
        self,
        can_move_forward: bool,
        forward_has_geometry: bool,
    ) -> None:
        self.can_move_forward = can_move_forward
        self.forward_has_geometry = forward_has_geometry
        self.rectangles: tuple = ()

    def MoveEndpointByUnit(
        self,
        endpoint: int,
        unit: int,
        count: int,
    ) -> int:
        del endpoint, unit
        if count == 1 and self.can_move_forward:
            if self.forward_has_geometry:
                self.rectangles = (100.0, 200.0, 8.0, 18.0)
            return 1
        if count == -1:
            self.rectangles = (100.0, 200.0, 8.0, 18.0)
            return -1
        return 0

    def GetBoundingRectangles(self) -> tuple:
        return self.rectangles


class CaretRangeTests(unittest.TestCase):
    def test_uses_next_character_geometry_for_degenerate_uia_caret(self) -> None:
        caret = CaretLocator._rect_from_uia_range(
            FakeDegenerateTextRange(can_move_forward=True)
        )

        self.assertEqual(caret, ScreenRect(100, 200, 102, 218))

    def test_uses_previous_character_right_edge_at_document_end(self) -> None:
        caret = CaretLocator._rect_from_uia_range(
            FakeDegenerateTextRange(can_move_forward=False)
        )

        self.assertEqual(caret, ScreenRect(108, 200, 110, 218))

    def test_uses_previous_character_when_next_character_is_invisible(self) -> None:
        caret = CaretLocator._rect_from_uia_range(
            FakeDegenerateTextRange(
                can_move_forward=True,
                forward_has_geometry=False,
            )
        )

        self.assertEqual(caret, ScreenRect(108, 200, 110, 218))


class CaretFallbackTests(unittest.TestCase):
    def test_macos_prefers_detected_caret_over_pointer(self) -> None:
        locator = CaretLocator()
        caret = ScreenRect(100, 200, 102, 220)

        with (
            patch("cat_type.IS_WINDOWS", False),
            patch("cat_type.IS_MACOS", True),
            patch.object(
                locator,
                "_locate_with_macos_accessibility",
                return_value=(caret, False),
            ),
            patch.object(locator, "_locate_pointer") as locate_pointer,
        ):
            snapshot = locator.locate()

        self.assertEqual(snapshot.rect, caret)
        self.assertEqual(snapshot.source, "macos-accessibility")
        locate_pointer.assert_not_called()

    def test_macos_password_field_never_uses_pointer(self) -> None:
        locator = CaretLocator()

        with (
            patch("cat_type.IS_WINDOWS", False),
            patch("cat_type.IS_MACOS", True),
            patch.object(
                locator,
                "_locate_with_macos_accessibility",
                return_value=(None, True),
            ),
            patch.object(locator, "_locate_pointer") as locate_pointer,
        ):
            snapshot = locator.locate()

        self.assertTrue(snapshot.is_password)
        self.assertIsNone(snapshot.rect)
        locate_pointer.assert_not_called()

    def test_macos_requests_accessibility_once_then_uses_pointer(self) -> None:
        locator = CaretLocator()
        pointer = ScreenRect(320, 240, 322, 260)
        prompt = Mock(return_value=False)
        accessibility = SimpleNamespace(
            AXIsProcessTrusted=Mock(return_value=False),
            AXIsProcessTrustedWithOptions=prompt,
            kAXTrustedCheckOptionPrompt="prompt",
        )

        with (
            patch("cat_type.IS_WINDOWS", False),
            patch("cat_type.IS_MACOS", True),
            patch.dict(
                sys.modules,
                {
                    "ApplicationServices": accessibility,
                    "AppKit": SimpleNamespace(NSWorkspace=Mock()),
                    "CoreFoundation": SimpleNamespace(CFRangeMake=Mock()),
                },
            ),
            patch.object(locator, "_locate_pointer", return_value=pointer),
        ):
            first_snapshot = locator.locate()
            second_snapshot = locator.locate()

        self.assertEqual(first_snapshot.source, "pointer-fallback")
        self.assertEqual(second_snapshot.source, "pointer-fallback")
        prompt.assert_called_once_with({"prompt": True})

    def test_macos_accessibility_can_be_disabled_for_sandboxed_builds(
        self,
    ) -> None:
        locator = CaretLocator(allow_macos_accessibility=False)
        pointer = ScreenRect(320, 240, 322, 260)

        with (
            patch("cat_type.IS_WINDOWS", False),
            patch("cat_type.IS_MACOS", True),
            patch.object(
                locator,
                "_locate_with_macos_accessibility",
            ) as locate_with_accessibility,
            patch.object(locator, "_locate_pointer", return_value=pointer),
        ):
            snapshot = locator.locate()

        self.assertEqual(snapshot.source, "pointer-fallback")
        locate_with_accessibility.assert_not_called()

    def test_windows_uses_pointer_when_caret_providers_fail(self) -> None:
        locator = CaretLocator()
        pointer = ScreenRect(640, 480, 642, 500)

        with (
            patch("cat_type.IS_WINDOWS", True),
            patch.object(
                locator,
                "_locate_with_uia",
                return_value=(None, False),
            ),
            patch.object(locator, "_locate_with_win32", return_value=None),
            patch.object(locator, "_locate_pointer", return_value=pointer),
        ):
            snapshot = locator.locate()

        self.assertEqual(snapshot.rect, pointer)
        self.assertEqual(snapshot.source, "pointer-fallback")

    def test_windows_prefers_detected_caret_over_pointer(self) -> None:
        locator = CaretLocator()
        caret = ScreenRect(100, 200, 102, 220)

        with (
            patch("cat_type.IS_WINDOWS", True),
            patch.object(
                locator,
                "_locate_with_uia",
                return_value=(caret, False),
            ),
            patch.object(locator, "_locate_pointer") as locate_pointer,
        ):
            snapshot = locator.locate()

        self.assertEqual(snapshot.rect, caret)
        self.assertEqual(snapshot.source, "uia")
        locate_pointer.assert_not_called()

    def test_windows_prefers_win32_caret_over_pointer(self) -> None:
        locator = CaretLocator()
        caret = ScreenRect(200, 300, 202, 320)

        with (
            patch("cat_type.IS_WINDOWS", True),
            patch.object(
                locator,
                "_locate_with_uia",
                return_value=(None, False),
            ),
            patch.object(
                locator,
                "_locate_with_win32",
                return_value=caret,
            ),
            patch.object(locator, "_locate_pointer") as locate_pointer,
        ):
            snapshot = locator.locate()

        self.assertEqual(snapshot.rect, caret)
        self.assertEqual(snapshot.source, "win32")
        locate_pointer.assert_not_called()

    def test_password_field_never_uses_pointer(self) -> None:
        locator = CaretLocator()

        with (
            patch("cat_type.IS_WINDOWS", True),
            patch.object(
                locator,
                "_locate_with_uia",
                return_value=(None, True),
            ),
            patch.object(locator, "_locate_pointer") as locate_pointer,
        ):
            snapshot = locator.locate()

        self.assertTrue(snapshot.is_password)
        self.assertIsNone(snapshot.rect)
        locate_pointer.assert_not_called()

    def test_linux_uses_shared_pointer_provider(self) -> None:
        locator = CaretLocator()
        pointer = ScreenRect(320, 240, 322, 260)

        with (
            patch("cat_type.IS_WINDOWS", False),
            patch("cat_type.IS_MACOS", False),
            patch.object(locator, "_locate_pointer", return_value=pointer),
        ):
            snapshot = locator.locate()

        self.assertEqual(snapshot.rect, pointer)
        self.assertEqual(snapshot.source, "pointer-fallback")

    def test_pointer_coordinates_are_rounded_to_a_caret_sized_rect(self) -> None:
        locator = CaretLocator()
        controller = Mock()
        controller.position = (123.6, 456.2)

        with patch("pynput.mouse.Controller", return_value=controller):
            rect = locator._locate_pointer()

        self.assertEqual(rect, ScreenRect(124, 456, 126, 476))

    def test_pointer_failure_returns_no_position(self) -> None:
        locator = CaretLocator()

        with patch(
            "pynput.mouse.Controller",
            side_effect=RuntimeError("pointer unavailable"),
        ):
            rect = locator._locate_pointer()

        self.assertIsNone(rect)

    def test_pointer_failure_logs_only_in_debug_mode(self) -> None:
        for debug, expected in ((False, ""), (True, "Pointer lookup failed")):
            locator = CaretLocator(debug=debug)
            error_output = io.StringIO()

            with (
                patch(
                    "pynput.mouse.Controller",
                    side_effect=RuntimeError("pointer unavailable"),
                ),
                patch("sys.stderr", error_output),
            ):
                locator._locate_pointer()

            with self.subTest(debug=debug):
                self.assertIn(expected, error_output.getvalue())
                if not debug:
                    self.assertEqual(error_output.getvalue(), "")


class PortableWorkAreaTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux-only check")
    def test_linux_provider_reads_host_monitor(self) -> None:
        areas = cat_type._linux_monitor_areas()

        self.assertTrue(areas)
        self.assertTrue(
            all(
                area.bounds.width > 0 and area.bounds.height > 0
                for area in areas
            )
        )

    @unittest.skipUnless(sys.platform == "darwin", "macOS-only check")
    def test_macos_provider_reads_each_connected_screen(self) -> None:
        from AppKit import NSScreen

        screens = NSScreen.screens()
        areas = cat_type._macos_monitor_areas()

        self.assertTrue(screens)
        self.assertEqual(len(areas), len(screens))

    def test_pointer_uses_its_secondary_monitor_bounds(self) -> None:
        primary = ScreenRect(0, 0, 1920, 1080)
        secondary = ScreenRect(-1280, 0, 0, 1024)

        with (
            patch("cat_type.IS_WINDOWS", False),
            patch("cat_type.IS_MACOS", False),
            patch("cat_type.IS_LINUX", True),
            patch(
                "cat_type._linux_monitor_areas",
                return_value=(
                    MonitorArea(primary, primary),
                    MonitorArea(secondary, secondary),
                ),
                create=True,
            ),
        ):
            area = cat_type.work_area_for(
                ScreenRect(-10, 500, -8, 520)
            )

        self.assertEqual(area, secondary)

    def test_shared_edge_belongs_to_monitor_starting_at_that_edge(self) -> None:
        primary = ScreenRect(0, 0, 1920, 1080)
        secondary = ScreenRect(1920, 0, 3200, 1024)

        area = cat_type._nearest_work_area(
            ScreenRect(1920, 500, 1922, 520),
            (
                MonitorArea(primary, primary),
                MonitorArea(secondary, secondary),
            ),
        )

        self.assertEqual(area, secondary)

    def test_macos_excluded_strip_still_belongs_to_its_screen(self) -> None:
        primary_bounds = ScreenRect(0, 0, 1920, 1080)
        primary_work = ScreenRect(0, 25, 1920, 1080)
        secondary_bounds = ScreenRect(1920, 0, 3200, 1024)
        secondary_work = ScreenRect(1920, 0, 3200, 1024)

        area = cat_type._nearest_work_area(
            ScreenRect(1919, 5, 1921, 25),
            (
                MonitorArea(primary_bounds, primary_work),
                MonitorArea(secondary_bounds, secondary_work),
            ),
        )

        self.assertEqual(area, primary_work)

    def test_linux_reads_active_xrandr_monitor_rectangles(self) -> None:
        monitors = (
            SimpleNamespace(
                x=0,
                y=0,
                width_in_pixels=1920,
                height_in_pixels=1080,
            ),
            SimpleNamespace(
                x=-1280,
                y=0,
                width_in_pixels=1280,
                height_in_pixels=1024,
            ),
        )
        connection = Mock()
        root = connection.screen.return_value.root
        request = root.xrandr_get_monitors.return_value
        request.monitors = monitors
        display_module = SimpleNamespace(
            Display=Mock(return_value=connection)
        )
        xlib_module = SimpleNamespace(display=display_module)

        with patch.dict(
            sys.modules,
            {"Xlib": xlib_module, "Xlib.display": display_module},
        ):
            areas = cat_type._linux_monitor_areas()

        self.assertEqual(
            areas,
            (
                MonitorArea(
                    ScreenRect(0, 0, 1920, 1080),
                    ScreenRect(0, 0, 1920, 1080),
                ),
                MonitorArea(
                    ScreenRect(-1280, 0, 0, 1024),
                    ScreenRect(-1280, 0, 0, 1024),
                ),
            ),
        )
        connection.close.assert_called_once_with()

    def test_macos_converts_visible_frames_to_pointer_coordinates(self) -> None:
        def frame(x: int, y: int, width: int, height: int) -> object:
            return SimpleNamespace(
                origin=SimpleNamespace(x=x, y=y),
                size=SimpleNamespace(width=width, height=height),
            )

        screens = (
            Mock(
                frame=Mock(return_value=frame(0, 0, 1920, 1080)),
                visibleFrame=Mock(return_value=frame(0, 0, 1920, 1055)),
            ),
            Mock(
                frame=Mock(return_value=frame(-1280, 0, 1280, 1024)),
                visibleFrame=Mock(
                    return_value=frame(-1280, 0, 1280, 1024)
                )
            ),
        )
        appkit = SimpleNamespace(
            NSScreen=SimpleNamespace(screens=Mock(return_value=screens))
        )
        quartz = SimpleNamespace(
            CGDisplayPixelsHigh=Mock(return_value=1080)
        )

        with patch.dict(
            sys.modules,
            {"AppKit": appkit, "Quartz": quartz},
        ):
            areas = cat_type._macos_monitor_areas()

        self.assertEqual(
            areas,
            (
                MonitorArea(
                    ScreenRect(0, 0, 1920, 1080),
                    ScreenRect(0, 25, 1920, 1080),
                ),
                MonitorArea(
                    ScreenRect(-1280, 56, 0, 1080),
                    ScreenRect(-1280, 56, 0, 1080),
                ),
            ),
        )
        quartz.CGDisplayPixelsHigh.assert_called_once_with(0)


class OverlayPositionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.work = ScreenRect(0, 0, 1920, 1040)

    def test_prefers_above_and_right_of_caret(self) -> None:
        caret = ScreenRect(100, 300, 102, 320)
        self.assertEqual(
            choose_overlay_position(caret, 88, 88, self.work),
            (108, 206),
        )

    def test_flips_left_near_right_edge_but_stays_above(self) -> None:
        caret = ScreenRect(1900, 1020, 1902, 1040)
        self.assertEqual(
            choose_overlay_position(caret, 88, 88, self.work),
            (1806, 926),
        )

    def test_flips_below_when_caret_is_near_top(self) -> None:
        work = ScreenRect(-1920, 0, 0, 1040)
        caret = ScreenRect(-1918, 5, -1916, 25)
        self.assertEqual(
            choose_overlay_position(caret, 88, 88, work),
            (-1910, 31),
        )

    def test_uses_work_area_top_when_deciding_to_flip_below(self) -> None:
        work = ScreenRect(0, 40, 1920, 1080)
        caret = ScreenRect(200, 100, 202, 120)
        self.assertEqual(
            choose_overlay_position(caret, 88, 88, work),
            (208, 126),
        )

class AnimationStateTests(unittest.TestCase):
    def test_startup_feedback_does_not_count_toward_rapid_typing(self) -> None:
        animation = AnimationState()
        animation.show_startup(1.0)
        self.assertTrue(animation.is_visible(1.01))
        self.assertEqual(animation.frame_name(1.01), "tap-left")

        for timestamp in (1.05, 1.1, 1.15, 1.2):
            animation.record_key(timestamp, "left")
        self.assertEqual(animation.frame_name(1.21), "tap-left")

        animation.record_key(1.25, "left")
        self.assertEqual(animation.frame_name(1.26), "excited")

    def test_explicit_keyboard_sides_choose_matching_paws(self) -> None:
        animation = AnimationState(hide_after=0.9)

        animation.record_key(10.0, "left")
        self.assertEqual(animation.frame_name(10.01), "tap-left")
        animation.record_key(10.2, "right")
        self.assertEqual(animation.frame_name(10.21), "tap-right")

    def test_spacebar_uses_both_paws_then_settles(self) -> None:
        animation = AnimationState()

        animation.record_key(1.0, "both")

        self.assertEqual(animation.frame_name(1.01), "excited")
        self.assertEqual(animation.frame_name(1.17), "idle")

    def test_unknown_keys_keep_the_alternating_fallback(self) -> None:
        animation = AnimationState()

        animation.record_key(2.0, "alternate")
        self.assertEqual(animation.frame_name(2.01), "tap-left")
        animation.record_key(2.2, "alternate")
        self.assertEqual(animation.frame_name(2.21), "tap-right")

    def test_fast_typing_overrides_latest_side_with_both_paws(self) -> None:
        animation = AnimationState()
        for index, timestamp in enumerate((1.0, 1.05, 1.1, 1.15, 1.2)):
            paw = "left" if index % 2 == 0 else "right"
            animation.record_key(timestamp, paw)

        self.assertEqual(animation.frame_name(1.21), "excited")
        self.assertEqual(animation.frame_name(1.37), "idle")

    def test_settles_and_hides_on_the_existing_timing(self) -> None:
        animation = AnimationState(hide_after=0.9)
        animation.record_key(10.0, "left")

        self.assertEqual(animation.frame_name(10.17), "idle")
        self.assertTrue(animation.is_visible(10.8))
        self.assertFalse(animation.is_visible(11.2))

    def test_fades_during_the_end_of_the_visible_period(self) -> None:
        animation = AnimationState(hide_after=1.5, fade_seconds=0.3)
        animation.record_key(10.0, "left")

        self.assertEqual(animation.opacity(11.19), 1.0)
        self.assertAlmostEqual(animation.opacity(11.35), 0.5)
        self.assertEqual(animation.opacity(11.5), 0.0)

        animation.record_key(11.6, "right")
        self.assertEqual(animation.opacity(11.6), 1.0)


if __name__ == "__main__":
    unittest.main()
