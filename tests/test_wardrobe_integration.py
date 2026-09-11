import tempfile
import threading
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from achievements import AchievementStore, AchievementTracker
from cat_settings import AppSettings, SettingsStore
from cat_type import AnimationState, CatTypeApp, _MacOSNativeOverlaySurface
from settings_window import SettingsWindow
from usage_metrics import UsageStore, UsageTracker


class WardrobeIntegrationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)

    def app(self, count=999):
        app = CatTypeApp.__new__(CatTypeApp)
        app.settings = AppSettings()
        app.settings_store = SettingsStore(self.directory / 'settings.json')
        app.usage_tracker = UsageTracker(UsageStore(self.directory / 'usage.json'))
        app.usage_tracker.metrics.total_keystrokes = count
        app.achievement_tracker = AchievementTracker(
            AchievementStore(self.directory / 'achievements.json'), app.usage_tracker.metrics,
        )
        app.keystroke_count = count
        app.animation = AnimationState()
        app.tracker = Mock()
        app._settings_window = None
        app._tray_icon = None
        return app

    def test_accepted_key_unlocks_once_without_equipping(self):
        app = self.app()
        app._handle_key_activity(1.0, 'left')
        self.assertEqual(app.achievement_tracker.unlocked, {'ribbon-clip', 'round-glasses'})
        self.assertEqual(app.settings.glasses, 'none')
        app._handle_key_activity(1.1, 'right')
        self.assertEqual(app.achievement_tracker.unlocked, {'ribbon-clip', 'round-glasses'})

    def test_paused_activity_does_not_unlock(self):
        app = self.app()
        app.settings.enabled = False
        app._handle_key_activity(1.0, 'left')
        self.assertEqual(app.achievement_tracker.unlocked, {'ribbon-clip'})
        self.assertEqual(app.keystroke_count, 999)

    def pending_permission_app(self):
        app = self.app()
        app.settings.enabled = False
        app.root = Mock()
        app._hide = Mock()
        app._ensure_activity_monitoring = Mock()
        app._requires_input_monitoring = True
        app._platform_name = 'darwin'
        app._input_monitoring_requested = True
        app._monitoring_permission_poll_id = 'permission-poll'
        app._input_monitoring_preflight = Mock(return_value=False)
        app._shutting_down = False
        return app

    def test_autosaving_other_settings_preserves_pending_permission_request(self):
        app = self.pending_permission_app()
        with patch('cat_type.set_launch_at_startup'):
            app.apply_settings(AppSettings(enabled=False, placement='below-left'))
        self.assertTrue(app._input_monitoring_requested)
        self.assertEqual(app._monitoring_permission_poll_id, 'permission-poll')
        app._input_monitoring_preflight.return_value = True
        app._poll_input_monitoring_permission()
        self.assertTrue(app.settings_store.load().enabled)
        self.assertEqual(app.settings_store.load().placement, 'below-left')

    def test_explicit_pause_still_cancels_pending_permission_request(self):
        app = self.pending_permission_app()
        with patch('cat_type.set_launch_at_startup'):
            app._set_enabled(False)
        self.assertFalse(app._input_monitoring_requested)
        self.assertIsNone(app._monitoring_permission_poll_id)
        self.assertFalse(app.settings_store.load().enabled)

    def test_autosaving_chart_view_keeps_a_tray_pause(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        root.withdraw()
        self.addCleanup(root.destroy)
        app = self.app()
        app.root = root
        app._hide = Mock()
        app._ensure_activity_monitoring = Mock()
        window = SettingsWindow(root, app.settings, app.apply_settings)
        app._settings_window = window
        self.addCleanup(window.close)
        with patch('cat_type.set_launch_at_startup'):
            app._set_enabled(False)
            self.assertFalse(window.enabled.get())
            window.metrics_view_buttons['columns'].invoke()
        self.assertFalse(app.settings.enabled)
        self.assertFalse(app.settings_store.load().enabled)
        self.assertEqual(app.settings_store.load().metrics_view, 'columns')

    def test_unlock_notice_does_not_block_typing_or_repeat(self):
        app = self.app()
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        notices = []

        class Tray:
            HAS_NOTIFICATION = True

            def notify(self, message, title):
                notices.append((message, title))
                entered.set()
                release.wait(2)
                finished.set()

        app._tray_icon = Tray()
        try:
            app._handle_key_activity(1.0, 'left')
            self.assertTrue(entered.wait(1))
            self.assertFalse(finished.is_set(), 'Typing must return before the slow notification finishes')
            app._handle_key_activity(1.1, 'right')
            self.assertEqual(len(notices), 1)
            self.assertIn('Round glasses', notices[0][0])
        finally:
            release.set()
            self.assertTrue(finished.wait(1))

    def test_live_unlock_reaches_open_wardrobe(self):
        app = self.app()
        app._settings_window = Mock()
        app._settings_window.window.winfo_exists.return_value = True
        app._handle_key_activity(1.0, 'left')
        self.assertEqual(app._settings_window.update_achievements.call_count, 1)
        unlocked, earned = app._settings_window.update_achievements.call_args.args
        self.assertEqual(unlocked, {'ribbon-clip', 'round-glasses'})
        self.assertEqual([item.id for item in earned], ['round-glasses'])

    def test_apply_rejects_locked_outfit_and_rebuilds_for_unlocked_change(self):
        app = self.app(1000)
        app.root = Mock()
        app.label = Mock()
        app._overlay_visible = False
        app._active_variant = 'white'
        app._last_rendered_frame = ('white', 'idle')
        app._load_frames = Mock(return_value={'gray': {'idle': Mock()}, 'white': {'idle': Mock()}})
        app._ensure_activity_monitoring = Mock()
        app._macos_overlay_surface = None
        with patch('cat_type.set_launch_at_startup'):
            app.apply_settings(AppSettings(hat='crown', glasses='round-glasses'))
        self.assertEqual(app.settings.hat, 'none')
        self.assertEqual(app.settings.glasses, 'round-glasses')
        app._load_frames.assert_called_once()
        self.assertIsNone(app._last_rendered_frame)
        self.assertEqual(app.settings_store.load().glasses, 'round-glasses')

    def test_periodic_flush_retries_achievement_save(self):
        app = self.app()
        with patch.object(app.achievement_tracker.store, 'save', side_effect=OSError):
            app.achievement_tracker.evaluate(type(app.usage_tracker.metrics)(total_keystrokes=1000))
        app._shutting_down = True
        app._flush_usage_periodically()
        self.assertEqual(AchievementStore(self.directory / 'achievements.json').load(), {'ribbon-clip', 'round-glasses'})

    def test_new_slot_validation_preserves_unlocked_and_rejects_locked_items(self):
        app = self.app()
        app.achievement_tracker.unlocked.update({'beta-bandana', 'angel-wings'})
        validated = app._validated_outfit(AppSettings(neck='beta-bandana', back='angel-wings', ears='sunflower-clip'))
        self.assertEqual((validated.neck, validated.back, validated.ears), ('beta-bandana', 'angel-wings', 'none'))

    def test_native_surface_invalidates_cache_for_new_slots(self):
        import inspect
        self.assertIn('neck', inspect.signature(_MacOSNativeOverlaySurface.set_outfit).parameters)
        surface = _MacOSNativeOverlaySurface('test')
        surface._images[('white', 'idle', 120)] = object()
        surface.set_outfit('none', 'none', neck='bow-tie')
        self.assertEqual(surface._images, {})
        sentinel = object()
        surface._images[('white', 'idle', 120)] = sentinel
        surface.set_outfit('none', 'none', neck='bow-tie')
        self.assertIs(surface._images[('white', 'idle', 120)], sentinel)
        surface.set_outfit('none', 'none', neck='bow-tie', back='angel-wings', ears='sunflower-clip')
        self.assertEqual(surface._images, {})

    def test_changing_only_neckwear_rebuilds_live_frames_and_persists(self):
        app = self.app(5000)
        app.root = Mock()
        app.label = Mock()
        app._overlay_visible = False
        app._active_variant = 'white'
        app._last_rendered_frame = ('white', 'idle')
        app._load_frames = Mock(return_value={'gray': {'idle': Mock()}, 'white': {'idle': Mock()}})
        app._ensure_activity_monitoring = Mock()
        app._macos_overlay_surface = None
        with patch('cat_type.set_launch_at_startup'):
            app.apply_settings(AppSettings(neck='bow-tie'))
        self.assertEqual(app.settings_store.load().neck, 'bow-tie')
        app._load_frames.assert_called_once()
        self.assertIsNone(app._last_rendered_frame)


if __name__ == '__main__':
    unittest.main()
