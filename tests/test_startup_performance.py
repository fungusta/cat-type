import unittest
import tkinter as tk
from time import perf_counter
from unittest.mock import patch
from contextlib import ExitStack
import settings_window
import wardrobe_view
import achievements_view
from pathlib import Path
from cat_settings import AppSettings
from settings_window import SettingsWindow

class StartupPerformanceTests(unittest.TestCase):
    def test_shell_defers_shelves_and_destinations(self):
        root = tk.Tk()
        root.withdraw()
        root.update()
        started = perf_counter()
        try:
            with ExitStack() as stack:
                counters = [stack.enter_context(patch.object(module, "load_frame", wraps=module.load_frame))
                            for module in (settings_window, wardrobe_view, achievements_view)]
                shell_started = perf_counter()
                view = SettingsWindow(root, AppSettings(), lambda value: None,
                    icon_path=str(Path(__file__).resolve().parents[1] / 'assets' / 'cat-type.png'))
                print(f"Settings shell only: {perf_counter() - shell_started:.4f}s")
                self.assertEqual([counter.call_count for counter in counters], [0, 0, 0])
            self.assertFalse(hasattr(view, 'wardrobe'))
            self.assertFalse(hasattr(view, 'achievements'))
            self.assertFalse(hasattr(view, 'metrics_page'))
            self.assertFalse(hasattr(view, 'preview_canvas'))
            root.update()
            self.assertTrue(hasattr(view, 'preview_canvas'))
            view.active_page.set('Metrics')
            view._switch_page()
            first = view.metrics_page
            view.active_page.set('Settings')
            view._switch_page()
            view.active_page.set('Metrics')
            view._switch_page()
            self.assertIs(view.metrics_page, first)
            view.close()
        finally:
            root.update_idletasks()
            root.destroy()
            print(f'Settings shell/navigation: {perf_counter() - started:.3f}s')

class OverlayFrameStagingTests(unittest.TestCase):
    def test_missing_variant_is_loaded_once_without_replacing_active_frames(self):
        from cat_type import CatTypeApp
        from unittest.mock import Mock
        app = CatTypeApp.__new__(CatTypeApp)
        app.settings = AppSettings()
        app.frames = {'gray': {'idle': object()}}
        original = app.frames['gray']
        app._load_frames = Mock(return_value={'orange': {'idle': object()}})
        ensure = getattr(app, '_ensure_frame_variant', lambda variant: None)
        ensure('orange')
        ensure('orange')
        self.assertIn('orange', app.frames)
        self.assertIs(app.frames['gray'], original)
        app._load_frames.assert_called_once_with(app.settings.size_percent, ('orange',))

    def test_deferred_pages_receive_latest_metrics_and_new_rewards_independently(self):
        from cat_accessories import ACCESSORY_BY_ID
        from usage_metrics import UsageMetrics
        root = tk.Tk()
        root.withdraw()
        root.update()
        try:
            view = SettingsWindow(root, AppSettings(), lambda value: None)
            reward = next(iter(ACCESSORY_BY_ID.values()))
            metrics = UsageMetrics(total_keystrokes=12345)
            view.update_usage_metrics(metrics)
            view.set_new_achievements((reward,))
            view.update_achievements({reward.id}, (reward,))
            achievements = view._ensure_page('Achievements')
            wardrobe = view._ensure_page('Wardrobe')
            self.assertIn(reward.id, achievements._new_ids)
            self.assertIn(reward.id, wardrobe._new_ids)
            self.assertIs(view.usage_metrics, metrics)
            self.assertIn(reward.id, view.unlocked_accessories)
            view.close()
        finally:
            root.update_idletasks()
            root.destroy()

    def test_close_cancels_owned_widget_idle_callbacks(self):
        root = tk.Tk()
        root.withdraw()
        root.update()
        try:
            view = SettingsWindow(root, AppSettings(), lambda value: None)
            fired = []
            pending = view.columns.after_idle(lambda: fired.append(True))
            view.close()
            self.assertNotIn(pending, root.tk.call("after", "info"))
            root.update()
            self.assertEqual(fired, [])
        finally:
            root.update_idletasks()
            root.destroy()


    def test_preview_hydrates_one_pose_per_idle_step(self):
        root = tk.Tk()
        root.withdraw()
        root.update()
        try:
            view = SettingsWindow(root, AppSettings(cat_style='white'), lambda value: None)
            if view._preview_hydration_after_id is not None:
                view.window.after_cancel(view._preview_hydration_after_id)
            with patch.object(settings_window, 'load_frame', wraps=settings_window.load_frame) as render:
                view._hydrate_preview_step()
            self.assertEqual(render.call_count, 1)
            self.assertEqual(set(view._preview_frames), {'white'})
            self.assertEqual(set(view._preview_frames['white']), {'idle'})
            view.close()
        finally:
            root.update_idletasks()
            root.destroy()

class StartupReviewRegressionTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.update()
        self.view = SettingsWindow(self.root, AppSettings(cat_style='white'), lambda value: None,
                                   on_check_for_updates=lambda: None)
        self.addCleanup(self.root.destroy)
        self.addCleanup(self.view.close)

    def test_early_wardrobe_navigation_has_preview_without_appearance(self):
        self.view.active_page.set('Wardrobe')
        self.view._switch_page()
        self.root.update()
        self.assertFalse(hasattr(self.view, 'preview_canvas'))
        self.assertTrue(self.view.rail_preview.itemcget(self.view._rail_preview_image, 'image'))
        self.assertIsNotNone(self.view.wardrobe._preview_frame)

    def test_new_wardrobe_receives_already_hydrated_preview(self):
        self.view.active_page.set('Metrics')
        self.view._switch_page()
        self.root.update()
        wardrobe = self.view._ensure_page('Wardrobe')
        self.assertIsNotNone(wardrobe._preview_frame)

    def test_update_checking_state_survives_deferred_controls(self):
        self.view.set_update_status('Checking...', checking=True)
        self.root.update()
        self.assertEqual(self.view.check_for_updates_button.cget('state'), 'disabled')
        self.view.set_update_status('Ready', checking=False)
        self.assertEqual(self.view.check_for_updates_button.cget('state'), 'normal')

    def test_outfit_refresh_renders_each_variant_pose_only_once(self):
        self.root.update()
        with patch.object(settings_window, 'load_frame', wraps=settings_window.load_frame) as render:
            self.view._refresh_outfit_preview()
            self.root.update()
        keys = [(call.args[1], call.args[2]) for call in render.call_args_list]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(keys), 24)

    def test_first_mapped_frame_has_current_cat_placeholder_and_live_navigation(self):
        observed = []
        def first_map(event):
            if event.widget is self.view.rail_preview:
                canvas = self.view.rail_preview
                texts = [canvas.itemcget(item, 'text') for item in canvas.find_all()
                         if canvas.type(item) == 'text' and canvas.itemcget(item, 'state') != 'hidden']
                observed.append((texts, render.call_count, canvas.winfo_ismapped()))
                self.view.page_buttons['Metrics'].invoke()
        self.view.rail_preview.bind('<Map>', first_map, add='+')
        with patch.object(settings_window, 'load_frame', wraps=settings_window.load_frame) as render:
            self.root.update()
        self.assertTrue(observed)
        self.assertEqual(observed[0][1], 0)
        self.assertTrue(observed[0][2])
        self.assertTrue(any('White' in text for text in observed[0][0]))
        # Aqua can dispatch the child's Map before updating its toplevel's
        # mapped flag. Check ancestor visibility after the event loop settles;
        # the child-map snapshot still proves the shell precedes rendering.
        self.assertTrue(self.view.window.winfo_viewable())
        self.assertTrue(self.view.rail_preview.winfo_viewable())
        self.assertEqual(self.view.active_page.get(), 'Metrics')
        self.assertFalse(hasattr(self.view, 'preview_canvas'))

    def test_alternate_wardrobe_uses_available_pose_during_partial_hydration(self):
        self.view.active_page.set('Metrics')
        self.view._switch_page()
        self.root.update()
        self.view.cat_style.set('Mix it up')
        self.view._preview_frames = {'gray': self.view._preview_frames['gray']}
        self.view._rail_preview_frames = {'gray': self.view._rail_preview_frames['gray']}
        self.view._preview_variant = 'gray'
        self.view._preview_step = 0
        wardrobe = self.view._ensure_page('Wardrobe')
        self.assertIsNotNone(wardrobe._preview_frame)

class PreviewRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.update()
        self.view = SettingsWindow(self.root, AppSettings(cat_style='white'), lambda value: None)
        self.addCleanup(self.root.destroy)
        self.addCleanup(self.view.close)

    def test_transient_render_failure_recovers_and_keeps_other_poses_loading(self):
        real_render = settings_window.load_frame
        failed = False
        def render(*args, **kwargs):
            nonlocal failed
            if not failed:
                failed = True
                raise OSError('temporary renderer failure')
            return real_render(*args, **kwargs)
        errors = []
        self.root.report_callback_exception = lambda *info: errors.append(info)
        with patch.object(settings_window, 'load_frame', side_effect=render) as load:
            self.root.update()
        self.assertEqual(errors, [])
        self.assertEqual(load.call_count, 25)
        self.assertEqual(sum(len(frames) for frames in self.view._preview_frames.values()), 24)
        self.assertFalse(self.view.preview_error_surface.winfo_manager())
        self.assertIsNone(self.view._preview_hydration_after_id)

    def test_persistent_photo_failure_is_bounded_visible_and_user_retry_recovers(self):
        errors = []
        self.root.report_callback_exception = lambda *info: errors.append(info)
        real_photo = settings_window.ImageTk.PhotoImage
        failed_photos = []
        def photo(*args, **kwargs):
            if kwargs.get('master') is self.view.window:
                failed_photos.append(True)
                raise tk.TclError('renderer unavailable')
            return real_photo(*args, **kwargs)
        with patch.object(settings_window.ImageTk, 'PhotoImage', side_effect=photo):
            self.root.update()
        self.assertEqual(errors, [])
        self.assertEqual(len(failed_photos), 48)
        self.assertIsNone(self.view._preview_hydration_after_id)
        self.assertTrue(self.view.preview_error_surface.winfo_ismapped())
        self.assertIn('preview', self.view.preview_error_text.get().lower())
        self.view.page_buttons['Metrics'].invoke()
        self.assertEqual(self.view.active_page.get(), 'Metrics')
        self.view.preview_retry_button.invoke()
        self.assertIsNotNone(self.view._preview_hydration_after_id)
        self.root.update()
        self.assertEqual(sum(len(frames) for frames in self.view._preview_frames.values()), 24)
        self.assertFalse(self.view.preview_error_surface.winfo_manager())

    def test_close_cancels_queued_manual_retry(self):
        with patch.object(settings_window, 'load_frame', side_effect=OSError('unavailable')):
            self.root.update()
        self.view.preview_retry_button.invoke()
        pending = self.view._preview_hydration_after_id
        self.assertIsNotNone(pending)
        self.view.close()
        self.assertNotIn(pending, self.root.tk.call('after', 'info'))
        self.root.update()

    def test_svg_parser_failure_uses_the_same_bounded_recovery(self):
        from xml.etree.ElementTree import ParseError
        errors = []
        self.root.report_callback_exception = lambda *info: errors.append(info)
        real_render = settings_window.load_frame
        attempts = 0
        def render(*args, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise ParseError('temporary invalid SVG')
            return real_render(*args, **kwargs)
        with patch.object(settings_window, 'load_frame', side_effect=render):
            self.root.update()
        self.assertEqual(errors, [])
        self.assertEqual(attempts, 25)
        self.assertFalse(self.view.preview_error_surface.winfo_manager())
