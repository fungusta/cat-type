from __future__ import annotations

import sys
import tkinter as tk
import tempfile
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import font as tkfont
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from app_version import APP_VERSION, IS_BETA_BUILD
from cat_settings import CAT_VARIANTS, AppSettings, SettingsStore
from settings_window import CatScale, SettingsWindow
from usage_metrics import UsageMetrics
from ui_surfaces import RoundedAction, RoundedBadge, soft_pill_radius


class SettingsWindowSizingTests(unittest.TestCase):
    def test_window_is_resizable_in_both_dimensions(self) -> None:
        window = Mock()
        with ExitStack() as stack:
            stack.enter_context(
                patch("settings_window.tk.Toplevel", return_value=window)
            )
            for variable_type in (
                "BooleanVar",
                "StringVar",
                "IntVar",
                "DoubleVar",
            ):
                stack.enter_context(patch(f"settings_window.tk.{variable_type}"))
            for method_name in (
                "_configure_fonts",
                "_configure_styles",
                "_load_preview_frames",
                "_build",
                "_center",
                "_animate_preview",
                "_settings_from_controls",
            ):
                stack.enter_context(patch.object(SettingsWindow, method_name))

            SettingsWindow(Mock(), AppSettings(), Mock())

        window.geometry.assert_called_once_with("920x800")
        window.minsize.assert_called_once_with(700, 480)
        window.resizable.assert_called_once_with(True, True)

    def test_preferred_size_is_clamped_to_available_screen(self) -> None:
        fit_to_screen = getattr(
            SettingsWindow,
            "_fit_to_screen",
            lambda *_args: None,
        )

        self.assertEqual(
            fit_to_screen(920, 800, 1920, 1080),
            (920, 800),
        )
        self.assertEqual(
            fit_to_screen(920, 800, 1366, 768),
            (920, 688),
        )
        self.assertEqual(
            fit_to_screen(920, 800, 800, 600),
            (760, 520),
        )
        self.assertEqual(
            fit_to_screen(920, 800, 640, 480),
            (600, 400),
        )

    def test_content_fitted_height_adds_only_overflow_within_screen(self) -> None:
        fitted_height = getattr(
            SettingsWindow,
            "_content_fitted_height",
            lambda *_args: None,
        )

        self.assertEqual(fitted_height(800, 800, 775, 724, 1120), 851)
        self.assertEqual(fitted_height(800, 800, 677, 736, 1120), 800)
        self.assertEqual(fitted_height(800, 800, 1228, 736, 1120), 1120)
        self.assertEqual(fitted_height(600, 1268, 667, 1205, 1920), 730)

    def test_content_viewport_height_excludes_footer_and_padding(self) -> None:
        viewport_height = getattr(
            SettingsWindow,
            "_content_viewport_height",
            lambda *_args: None,
        )

        self.assertEqual(viewport_height(300, 35), 239)
        self.assertEqual(viewport_height(514, 35), 453)
        self.assertEqual(viewport_height(363, 35), 302)
        self.assertEqual(viewport_height(20, 35), 1)

    def test_center_reduces_minimum_when_screen_is_too_small(self) -> None:
        settings_window = SettingsWindow.__new__(SettingsWindow)
        window = Mock()
        window.winfo_width.return_value = 920
        window.winfo_height.side_effect = [800, 400]
        window.winfo_screenwidth.return_value = 640
        window.winfo_screenheight.return_value = 480
        window.maxsize.return_value = (625, 450)
        settings_window.window = window
        scroll_canvas = Mock()
        scroll_canvas.bbox.return_value = None
        scroll_canvas.winfo_height.return_value = 400
        settings_window.scroll_canvas = scroll_canvas
        settings_window._settle_content_layout = Mock()
        settings_window.footer = Mock()
        settings_window.footer.winfo_reqheight.return_value = 35

        settings_window._center()

        window.minsize.assert_called_once_with(600, 400)
        settings_window._settle_content_layout.assert_called_once_with(600, 339)
        self.assertEqual(
            window.geometry.call_args_list,
            [call("600x400"), call("600x400+20+24")],
        )

    def test_content_layout_settles_canvas_width_before_measurement(self) -> None:
        settings_window = SettingsWindow.__new__(SettingsWindow)
        events: list[tuple[str, int | None]] = []
        settings_window.window = Mock()
        settings_window.scroll_canvas = Mock()
        settings_window.scrollbar = Mock()
        settings_window.scrollbar.winfo_manager.side_effect = ["pack", ""]
        settings_window.scrollbar.winfo_reqwidth.return_value = 16
        settings_window.scroll_canvas.itemconfigure.side_effect = (
            lambda _item, *, width: events.append(("canvas", width))
        )
        settings_window._scroll_content_id = 42
        settings_window._apply_responsive_layout = Mock(
            side_effect=lambda width: events.append(("layout", width))
        )
        settings_window.window.update_idletasks.side_effect = lambda: (
            events.append(("idle", None))
        )
        settings_window._sync_scrollbar_visibility = Mock(
            side_effect=lambda viewport_height: events.append(
                ("scrollbar", viewport_height)
            )
        )

        try:
            settings_window._settle_content_layout(855, 453)
        except TypeError as error:
            self.fail(
                "_settle_content_layout must accept the target window width: "
                f"{error}"
            )

        expected_events: list[tuple[str, int | None]] = []
        for width in (839, 855):
            expected_events.extend(
                [
                    ("canvas", width),
                    ("layout", width),
                    ("idle", None),
                    ("scrollbar", 453),
                    ("idle", None),
                ]
            )
        self.assertEqual(
            events,
            expected_events,
        )


class SettingsWindowMetricsGeometryTests(unittest.TestCase):
    def test_line_positions_use_exact_bucket_endpoints(self) -> None:
        self.assertEqual(
            SettingsWindow._metric_line_positions(
                [0, 50, 100],
                300,
                200,
                left=40,
                right=20,
                top=20,
                bottom=30,
            ),
            [(40.0, 170.0), (160.0, 95.0), (280.0, 20.0)],
        )

    def test_column_positions_center_discrete_buckets(self) -> None:
        self.assertEqual(
            SettingsWindow._metric_column_positions(
                [0, 50, 100],
                300,
                200,
                left=40,
                right=20,
                top=20,
                bottom=30,
            ),
            [
                (80.0, 170.0, 170.0),
                (160.0, 170.0, 95.0),
                (240.0, 170.0, 20.0),
            ],
        )

    def test_metric_axis_uses_nice_ticks_and_peak_headroom(self) -> None:
        self.assertEqual(
            SettingsWindow._metric_axis(1),
            (2, [0, 1, 2]),
        )
        self.assertEqual(
            SettingsWindow._metric_axis(100),
            (150, [0, 50, 100, 150]),
        )
        self.assertEqual(
            SettingsWindow._metric_axis(274),
            (400, [0, 200, 400]),
        )

        positions = SettingsWindow._metric_line_positions(
            [0, 50, 100],
            300,
            200,
            left=40,
            right=20,
            top=20,
            bottom=30,
            maximum=125,
        )

        self.assertEqual(
            positions,
            [(40.0, 170.0), (160.0, 110.0), (280.0, 50.0)],
        )


class SettingsWindowCiTests(unittest.TestCase):
    def test_cross_platform_workflows_run_settings_window_tests(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        runner = (project_root / "scripts/run_ci_tests.py").read_text(encoding="utf-8")
        self.assertIn("tests.test_settings_window", runner)
        for workflow_path in (
            project_root / ".github/workflows/build.yml",
            project_root / ".github/workflows/release.yml",
        ):
            with self.subTest(workflow=workflow_path):
                workflow = workflow_path.read_text(encoding="utf-8")
                self.assertTrue(
                    "tests.test_settings_window" in workflow
                    or "scripts/run_ci_tests.py" in workflow
                )


class SettingsWindowScrollingTests(unittest.TestCase):
    def test_wheel_events_are_normalized_across_platforms(self) -> None:
        wheel_units = getattr(
            SettingsWindow,
            "_wheel_scroll_units",
            lambda _event: None,
        )

        cases = (
            (SimpleNamespace(delta=120, num=None), -1),
            (SimpleNamespace(delta=-120, num=None), 1),
            (SimpleNamespace(delta=240, num=None), -2),
            (SimpleNamespace(delta=1, num=None), -1),
            (SimpleNamespace(delta=0, num=4), -1),
            (SimpleNamespace(delta=0, num=5), 1),
            (SimpleNamespace(delta=0, num=None), 0),
        )
        for event, expected in cases:
            with self.subTest(event=event):
                self.assertEqual(wheel_units(event), expected)

    def test_wheel_scrolls_overflowing_content_under_pointer(self) -> None:
        settings_window = SettingsWindow.__new__(SettingsWindow)
        canvas = Mock()
        canvas.bbox.return_value = (0, 0, 700, 900)
        canvas.winfo_height.return_value = 400
        canvas.master = None
        settings_window.scroll_canvas = canvas
        content = SimpleNamespace(master=canvas)
        child = SimpleNamespace(master=content)
        event = SimpleNamespace(widget=child, delta=-120, num=None)
        handle_wheel = getattr(
            settings_window,
            "_on_mouse_wheel",
            lambda _event: None,
        )

        result = handle_wheel(event)

        canvas.yview_scroll.assert_called_once_with(1, "units")
        self.assertEqual(result, "break")

    def test_wheel_ignores_footer_and_content_that_fits(self) -> None:
        settings_window = SettingsWindow.__new__(SettingsWindow)
        canvas = Mock()
        canvas.bbox.return_value = (0, 0, 700, 300)
        canvas.winfo_height.return_value = 400
        canvas.master = None
        settings_window.scroll_canvas = canvas
        content = SimpleNamespace(master=canvas)
        footer_child = SimpleNamespace(master=None)
        handle_wheel = getattr(
            settings_window,
            "_on_mouse_wheel",
            lambda _event: None,
        )

        result_over_footer = handle_wheel(
            SimpleNamespace(
                widget=footer_child,
                delta=-120,
                num=None,
            )
        )
        result_when_content_fits = handle_wheel(
            SimpleNamespace(
                widget=content,
                delta=-120,
                num=None,
            )
        )

        canvas.yview_scroll.assert_not_called()
        self.assertIsNone(result_over_footer)
        self.assertIsNone(result_when_content_fits)

    def test_scrollbar_is_hidden_when_content_fits(self) -> None:
        settings_window = SettingsWindow.__new__(SettingsWindow)
        canvas = Mock()
        canvas.bbox.return_value = (0, 0, 700, 300)
        canvas.winfo_height.return_value = 400
        scrollbar = Mock()
        scrollbar.winfo_manager.return_value = "pack"
        settings_window.scroll_canvas = canvas
        settings_window.scrollbar = scrollbar

        settings_window._sync_scrollbar_visibility()

        scrollbar.pack_forget.assert_called_once_with()
        canvas.yview_moveto.assert_called_once_with(0)

    def test_scrollbar_uses_deterministic_viewport_during_opening(self) -> None:
        settings_window = SettingsWindow.__new__(SettingsWindow)
        canvas = Mock()
        canvas.bbox.return_value = (0, 0, 700, 453)
        canvas.winfo_height.return_value = 239
        scrollbar = Mock()
        scrollbar.winfo_manager.return_value = "pack"
        settings_window.scroll_canvas = canvas
        settings_window.scrollbar = scrollbar

        try:
            settings_window._sync_scrollbar_visibility(453)
        except TypeError as error:
            self.fail(
                "_sync_scrollbar_visibility must accept viewport height: "
                f"{error}"
            )

        scrollbar.pack_forget.assert_called_once_with()
        canvas.yview_moveto.assert_called_once_with(0)

    def test_scrollbar_is_restored_for_overflowing_content(self) -> None:
        settings_window = SettingsWindow.__new__(SettingsWindow)
        canvas = Mock()
        canvas.bbox.return_value = (0, 0, 700, 900)
        canvas.winfo_height.return_value = 400
        scrollbar = Mock()
        scrollbar.winfo_manager.return_value = ""
        settings_window.scroll_canvas = canvas
        settings_window.scrollbar = scrollbar

        settings_window._sync_scrollbar_visibility()

        scrollbar.pack.assert_called_once_with(
            side="right",
            fill="y",
            before=canvas,
        )


class SettingsWindowUpdateCardTests(unittest.TestCase):
    def test_one_pixel_wraplength_jitter_does_not_reconfigure_label(self) -> None:
        settings_window = SettingsWindow.__new__(SettingsWindow)
        label = Mock()
        label.cget.return_value = "381"
        settings_window.update_status_label = label

        settings_window._on_update_card_configure(SimpleNamespace(width=380))

        label.configure.assert_not_called()


class SettingsWindowTkLayoutTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk display is unavailable: {error}")
        self.root.withdraw()
        self._tk_scaling = (
            float(self.root.tk.call("tk", "scaling"))
            if sys.platform == "win32"
            else None
        )
        self.addCleanup(self.root.destroy)
        self.on_save = Mock()
        self.on_check_for_updates = Mock()
        self.on_open_release_page = Mock()
        self.settings_window = SettingsWindow(
            self.root,
            AppSettings(),
            self.on_save,
            keystroke_count=1_234,
            on_check_for_updates=self.on_check_for_updates,
            on_open_release_page=self.on_open_release_page,
            update_status="Ready to check.",
        )
        self.addCleanup(self.settings_window.close)

    def tearDown(self) -> None:
        if self._tk_scaling is not None:
            try:
                self.root.tk.call("tk", "scaling", self._tk_scaling)
            except tk.TclError:
                pass

    @staticmethod
    def _widget_texts(widget: tk.Misc) -> set[str]:
        texts: set[str] = set()
        for child in widget.winfo_children():
            try:
                textvariable = (
                    child.cget("textvariable")
                    if "textvariable" in child.keys()
                    else ""
                )
                text = (
                    child.getvar(textvariable)
                    if textvariable
                    else child.cget("text")
                )
            except tk.TclError:
                text = ""
            if text:
                texts.add(str(text))
            texts.update(SettingsWindowTkLayoutTests._widget_texts(child))
        return texts

    def test_settings_uses_companion_and_behavior_shelves(self) -> None:
        texts = self._widget_texts(self.settings_window.columns)
        self.assertIn("Companion", texts)
        self.assertIn("Behavior", texts)
        self.assertIn("Choose the look that follows your outfit.", texts)
        self.assertIn("Where your typing companion settles in.", texts)
        self.assertIn("Set how large your cat looks.", texts)
        self.assertIn("Keep the companion visible as you work.", texts)
        self.assertIn("Have the companion ready when your day starts.", texts)
        self.assertNotIn("Keep the cat close, calm, and easy to personalize.", texts)
        self.assertNotIn("Make it feel like yours.", texts)

    def test_metrics_keeps_summary_above_one_activity_shelf(self) -> None:
        self.settings_window.active_page.set("Metrics")
        self.settings_window._switch_page()
        self.settings_window.window.update()
        self.assertEqual(len(self.settings_window.metric_stat_cards), 3)
        self.assertTrue(self.settings_window.metrics_chart.winfo_ismapped())

    def test_wardrobe_heading_owns_the_mix_action(self) -> None:
        self.assertFalse(self.settings_window.mix_it_up_button.winfo_ismapped())
        self.settings_window.page_buttons["Wardrobe"].invoke()
        self.settings_window.window.update()
        self.assertTrue(self.settings_window.mix_it_up_button.winfo_ismapped())
        self.assertEqual(
            self.settings_window.mix_it_up_button.cget("text"),
            "Mix it up",
        )

    def test_settings_rows_keep_controls_on_the_right(self) -> None:
        self.settings_window.active_page.set("Settings")
        self.settings_window._switch_page()
        self.settings_window.window.update_idletasks()
        self.assertLess(
            self.settings_window.cat_style_control.winfo_rootx(),
            self.settings_window.columns.winfo_rootx() + self.settings_window.columns.winfo_width(),
        )

    def test_settings_page_matches_companion_studio_shelf_layout(self) -> None:
        self.settings_window.active_page.set("Settings")
        self.settings_window._switch_page()
        self.settings_window.window.update_idletasks()

        self.assertEqual(
            tuple(self.settings_window.settings_shelf_titles),
            ("Companion", "Behavior", "Updates"),
        )
        self.assertTrue(
            all(
                shelf.master is self.settings_window.columns
                for shelf in self.settings_window.settings_shelves
            )
        )
        self.assertFalse(self.settings_window.preview_canvas.winfo_ismapped())
        self.assertNotIn(
            "All-time keystrokes",
            self._widget_texts(self.settings_window.columns),
        )

        texts = self._widget_texts(self.settings_window.columns)
        self.assertIn("Choose the look that follows your outfit.", texts)
        self.assertIn("Where your typing companion settles in.", texts)
        self.assertIn("How long the cat stays after typing.", texts)

    def test_settings_placement_control_uses_the_shared_soft_pill(self) -> None:
        self.assertIsInstance(self.settings_window.placement_control, RoundedAction)

    def test_settings_slider_values_use_shared_pill_badges(self) -> None:
        self.assertTrue(self.settings_window._slider_value_badges)
        self.assertTrue(
            all(isinstance(badge, RoundedBadge)
                for badge in self.settings_window._slider_value_badges)
        )

    def test_settings_uses_only_functional_copy_and_starts_with_switcher(
        self,
    ) -> None:
        # Wardrobe copy and reward progress are covered in test_wardrobe.py.
        texts = set().union(*(self._widget_texts(widget) for widget in (
            self.settings_window.columns, self.settings_window.metrics_page,
            self.settings_window.footer, self.settings_window.page_switcher,
        )))
        filler_copy = {
            "  YOUR TINY TYPING PAL  ",
            "Make it feel like yours.",
            "Choose your cat, its cozy corner, and how long it stays.",
            "See your typing rhythm.",
            "A private view of when your tiny pal has been busiest.",
            "The important purr-t",
            "Pause anytime without quitting Cat Type.",
            "Your typing pal will be ready and waiting.",
            "Pick a favorite fluff",
            "Tiny bean or big floof",
            "smol",
            "chonky",
            "Settle in, then fade",
            "Keep your typing pal current",
            "Your typing rhythm over time",
            (
                "Only activity counts while Cat Type is enabled are stored — "
                "never key names, text, apps, or window titles."
            ),
            "♡  Only keyboard activity is detected — never what you type.",
        }
        expected_texts = {
            "0",
            "0.3s",
            "1,234",
            "1.5s",
            "100%",
            "1d",
            "7d",
            "30d",
            "Settings",
            "Metrics",
            "Wardrobe",
            "Achievements",
            "Cat Type",
            "companion studio",
            "Companion",
            "Behavior",
            "Cat style",
            "Choose the look that follows your outfit.",
            "Updates",
            "Activity",
            "Above · right",
            "All time",
            "All-time keystrokes",
            "Black & white",
            "Brown tabby",
            "Close",
            "Charcoal",
            "Check for updates",
            "Columns",
            "Favorite spot",
            "Where your typing companion settles in.",
            "Ginger tabby",
            "Gray tabby",
            "Hang around",
            "How long the cat stays after typing.",
            "Let the cat fade away gently.",
            "Last 7 days",
            "Line",
            "Mix it up",
            "Next →",
            "Open release page",
            "Preview scale",
            "Set how large your cat looks.",
            "Range",
            "Ready to check.",
            "Retry",
            "Show my cat while I type",
            "Keep the companion visible as you work.",
            "Soft fade",
            "Start Cat Type when I sign in",
            "Have the companion ready when your day starts.",
            "Today",
            "White",
            f"Version {APP_VERSION}" + (" · Beta" if IS_BETA_BUILD else ""),
            "View",
            "keystrokes",
            "← Previous",
        }

        self.assertTrue(filler_copy.isdisjoint(texts))
        self.assertEqual(texts, expected_texts)
        self.assertIs(
            self.settings_window.scroll_content.winfo_children()[0],
            self.settings_window.page_switcher,
        )
        self.assertIs(
            self.settings_window.preview_canvas.master,
            self.settings_window.cat_style_content,
        )
        self.assertFalse(hasattr(self.settings_window, "hero"))

    def test_companion_studio_shell_puts_preview_in_the_rail(self) -> None:
        rail = self.settings_window.page_switcher
        self.assertIs(self.settings_window.rail_preview.master, rail.content)
        self.assertEqual(self.settings_window.rail_brand_title.cget("text"), "Cat Type")
        self.assertFalse(hasattr(self.settings_window, "companion_header"))

    def test_rail_preview_matches_the_compact_prototype_brand(self) -> None:
        self.settings_window.window.update_idletasks()
        self.assertLessEqual(int(self.settings_window.rail_preview.cget("width")), 64)
        self.assertLessEqual(int(self.settings_window.rail_preview.cget("height")), 64)
        self.assertEqual(self.settings_window.rail_brand_title.grid_info()["column"], 1)

    def test_navigation_pills_share_one_face_width(self) -> None:
        widths = {button._size[0] for button in self.settings_window.page_buttons.values()}
        self.assertEqual(len(widths), 1)
        self.settings_window.window.update_idletasks()
        self.assertLessEqual(
            next(iter(widths)),
            self.settings_window.page_switcher.content.winfo_width() - 8,
        )

    def test_page_content_starts_in_the_main_host(self) -> None:
        self.settings_window.active_page.set("Settings")
        self.settings_window._switch_page()
        self.settings_window.window.update_idletasks()
        self.assertIs(self.settings_window.columns.master, self.settings_window.page_host)
        self.assertIs(self.settings_window.metrics_page.master, self.settings_window.page_host)

    def test_scaled_opening_grows_to_remove_avoidable_scrolling(self) -> None:
        self.root.tk.call("tk", "scaling", 2.5)
        fitted_window = SettingsWindow(
            self.root,
            AppSettings(),
            Mock(),
        )
        self.addCleanup(fitted_window.close)
        fitted_window.window.update()

        bounds = fitted_window.scroll_canvas.bbox("all")
        self.assertIsNotNone(bounds)
        assert bounds is not None
        actual_height = fitted_window.window.winfo_height()
        viewport_height = fitted_window.scroll_canvas.winfo_height()
        content_height = bounds[3] - bounds[1]
        non_scroll_height = actual_height - viewport_height
        available_height = (
            fitted_window.window.winfo_screenheight()
            - fitted_window.SCREEN_VERTICAL_MARGIN
        )
        maximum_height = fitted_window.window.maxsize()[1]
        if maximum_height > 0:
            available_height = min(available_height, maximum_height)
        expected_height = min(
            max(
                min(fitted_window.PREFERRED_HEIGHT, available_height),
                content_height + non_scroll_height,
            ),
            available_height,
        )

        self.assertEqual(actual_height, expected_height)
        if content_height > viewport_height:
            self.assertEqual(actual_height, available_height)
            self.assertTrue(fitted_window.scrollbar.winfo_ismapped())
        else:
            self.assertFalse(fitted_window.scrollbar.winfo_ismapped())

    def test_narrow_opening_fits_content_within_available_height(
        self,
    ) -> None:
        self.root.tk.call("tk", "scaling", 1.0)
        with (
            patch.object(SettingsWindow, "PREFERRED_WIDTH", 760),
            patch.object(SettingsWindow, "PREFERRED_HEIGHT", 600),
        ):
            fitted_window = SettingsWindow(
                self.root,
                AppSettings(),
                Mock(),
            )
        self.addCleanup(fitted_window.close)
        fitted_window.window.geometry("760x600")
        fitted_window.window.minsize(
            fitted_window.MIN_WIDTH,
            fitted_window.MIN_HEIGHT,
        )
        fitted_window.window.update()
        fitted_window.window.winfo_screenwidth = lambda: 800
        fitted_window.window.winfo_screenheight = lambda: 800
        fitted_window.window.maxsize = lambda: (5000, 5000)

        fitted_window._center()
        fitted_window.window.update()

        self.assertEqual(fitted_window._layout_mode, "narrow")
        bounds = fitted_window.scroll_canvas.bbox("all")
        self.assertIsNotNone(bounds)
        assert bounds is not None
        actual_height = fitted_window.window.winfo_height()
        viewport_height = fitted_window.scroll_canvas.winfo_height()
        content_height = bounds[3] - bounds[1]
        available_height = 800 - fitted_window.SCREEN_VERTICAL_MARGIN

        self.assertGreaterEqual(actual_height, 600)
        self.assertLessEqual(actual_height, available_height)
        if content_height > viewport_height:
            self.assertTrue(fitted_window.scrollbar.winfo_ismapped())
        else:
            self.assertFalse(fitted_window.scrollbar.winfo_ismapped())

    def test_opening_measures_after_reducing_minimum_for_small_screen(
        self,
    ) -> None:
        self.root.tk.call("tk", "scaling", 1.0)
        with patch.object(SettingsWindow, "PREFERRED_HEIGHT", 600):
            fitted_window = SettingsWindow(
                self.root,
                AppSettings(),
                Mock(),
                update_status="Status " * 100,
            )
        self.addCleanup(fitted_window.close)
        fitted_window.window.geometry("920x600")
        fitted_window.window.minsize(
            fitted_window.MIN_WIDTH,
            fitted_window.MIN_HEIGHT,
        )
        fitted_window.window.update()
        fitted_window.window.winfo_screenwidth = lambda: 660
        fitted_window.window.winfo_screenheight = lambda: 800
        fitted_window.window.maxsize = lambda: (5000, 5000)

        original_fitted_height = SettingsWindow._content_fitted_height
        with patch.object(
            SettingsWindow,
            "_content_fitted_height",
            wraps=original_fitted_height,
        ) as fitted_height:
            fitted_window._center()
        fitted_window.window.update()

        bounds = fitted_window.scroll_canvas.bbox("all")
        self.assertIsNotNone(bounds)
        assert bounds is not None
        self.assertEqual(fitted_window.window.winfo_width(), 620)
        actual_height = fitted_window.window.winfo_height()
        available_height = 800 - fitted_window.SCREEN_VERTICAL_MARGIN
        self.assertGreaterEqual(actual_height, 600)
        self.assertLessEqual(actual_height, available_height)
        self.assertLess(
            fitted_window.window.winfo_width(),
            fitted_window.MIN_WIDTH,
        )
        measured_content_heights = {
            measurement.args[2]
            for measurement in fitted_height.call_args_list
        }
        self.assertIn(
            bounds[3] - bounds[1],
            measured_content_heights,
        )
        self.assertGreater(
            bounds[3] - bounds[1],
            fitted_window.scroll_canvas.winfo_height(),
        )
        self.assertTrue(fitted_window.scrollbar.winfo_ismapped())

    def test_opening_remeasures_after_scrollbar_changes_layout_mode(
        self,
    ) -> None:
        self.root.tk.call("tk", "scaling", 1.0)
        original_center = SettingsWindow._center
        with (
            patch.object(SettingsWindow, "PREFERRED_HEIGHT", 300),
            patch.object(SettingsWindow, "MIN_HEIGHT", 200),
            patch.object(SettingsWindow, "_center"),
        ):
            fitted_window = SettingsWindow(
                self.root,
                AppSettings(),
                Mock(),
            )
            self.addCleanup(fitted_window.close)
            fitted_window.settings_shelves[0].pack_forget()
            for card in fitted_window.settings_shelves[1:]:
                card.pack_forget()
            # Give the remeasure pass enough virtual screen height to hide
            # the scrollbar after the content grows; native runner displays
            # otherwise disagree about the available desktop height.
            fitted_window.window.winfo_screenwidth = lambda: 2000
            fitted_window.window.winfo_screenheight = lambda: 2000
            fitted_window.window.maxsize = lambda: (5000, 5000)
            scrollbar_width = fitted_window.scrollbar.winfo_reqwidth()
            opening_width = (
                fitted_window.TWO_COLUMN_BREAKPOINT + scrollbar_width - 1
            )
            fitted_window.window.geometry(f"{opening_width}x300")
            fitted_window.window.update()
            self.assertEqual(fitted_window.window.winfo_height(), 300)
            self.assertTrue(fitted_window.scrollbar.winfo_ismapped())
            self.assertEqual(fitted_window._layout_mode, "narrow")
            self.assertLess(
                fitted_window.scroll_canvas.winfo_width(),
                fitted_window.TWO_COLUMN_BREAKPOINT,
            )

            original_center(fitted_window)
            fitted_window.window.update()

        bounds = fitted_window.scroll_canvas.bbox("all")
        self.assertIsNotNone(bounds)
        assert bounds is not None
        actual_height = fitted_window.window.winfo_height()
        viewport_height = fitted_window.scroll_canvas.winfo_height()
        content_height = bounds[3] - bounds[1]
        non_scroll_height = actual_height - viewport_height
        self.assertEqual(fitted_window._layout_mode, "wide")
        self.assertGreaterEqual(
            actual_height,
            max(300, content_height + non_scroll_height),
        )
        self.assertFalse(fitted_window.scrollbar.winfo_ismapped())

    def test_updates_card_shows_version_status_and_invokes_callback_once(
        self,
    ) -> None:
        self.assertEqual(
            self.settings_window.update_version_label.cget("text"),
            f"Version {APP_VERSION}" + (" · Beta" if IS_BETA_BUILD else ""),
        )
        self.assertEqual(
            self.settings_window.update_status_text.get(),
            "Ready to check.",
        )
        self.assertEqual(
            self.settings_window.check_for_updates_button.cget("text"),
            "Check for updates",
        )

        self.settings_window.check_for_updates_button.invoke()
        self.settings_window.open_release_page_button.invoke()

        self.on_check_for_updates.assert_called_once_with()
        self.on_open_release_page.assert_called_once_with()

    def test_macos_updates_card_keeps_direct_download_controls(self) -> None:
        macos_window = SettingsWindow(
            self.root,
            AppSettings(),
            Mock(),
            requires_input_monitoring=True,
            on_check_for_updates=self.on_check_for_updates,
            on_open_release_page=self.on_open_release_page,
        )
        self.addCleanup(macos_window.close)

        texts = self._widget_texts(macos_window.window)

        self.assertIn("Check for updates", texts)
        self.assertIn("Open release page", texts)
        self.assertEqual(
            macos_window.launch_at_startup_toggle.winfo_manager(),
            "pack",
        )
        macos_window.check_for_updates_button.invoke()
        macos_window.open_release_page_button.invoke()
        self.on_check_for_updates.assert_called_once_with()
        self.on_open_release_page.assert_called_once_with()

    def test_macos_permission_control_uses_native_request_then_settings(
        self,
    ) -> None:
        request_permission = Mock(return_value=False)
        open_system_settings = Mock(return_value=True)
        macos_window = SettingsWindow(
            self.root,
            AppSettings(enabled=False),
            Mock(),
            requires_input_monitoring=True,
            input_monitoring_granted=False,
            on_request_input_monitoring=request_permission,
            on_open_input_monitoring_settings=open_system_settings,
        )
        self.addCleanup(macos_window.close)

        texts = self._widget_texts(macos_window.window)
        self.assertIn(
            "Input Monitoring is required to show the cat.",
            texts,
        )
        self.assertEqual(
            macos_window.input_monitoring_button.cget("text"),
            "Enable Input Monitoring",
        )

        macos_window.input_monitoring_button.invoke()

        request_permission.assert_called_once_with()
        self.assertEqual(
            macos_window.input_monitoring_button.cget("text"),
            "Open System Settings",
        )
        self.assertFalse(macos_window.enabled.get())

        macos_window.input_monitoring_button.invoke()

        open_system_settings.assert_called_once_with()

    def test_macos_privacy_explanation_toggles_from_details_button(
        self,
    ) -> None:
        macos_window = SettingsWindow(
            self.root,
            AppSettings(enabled=False),
            Mock(),
            requires_input_monitoring=True,
        )
        self.addCleanup(macos_window.close)

        self.assertEqual(macos_window.privacy_explanation.winfo_manager(), "")
        self.assertEqual(
            macos_window.privacy_details_button.cget("text"),
            "Privacy details",
        )

        macos_window.privacy_details_button.invoke()
        macos_window.window.update_idletasks()

        self.assertEqual(
            macos_window.privacy_explanation.winfo_manager(),
            "pack",
        )
        self.assertEqual(
            macos_window.privacy_details_button.cget("text"),
            "Hide privacy details",
        )

        macos_window.privacy_details_button.invoke()
        macos_window.window.update_idletasks()

        self.assertEqual(macos_window.privacy_explanation.winfo_manager(), "")

    def test_update_status_changes_live_and_disables_button_while_checking(
        self,
    ) -> None:
        self.settings_window.set_update_status(
            "Checking for updates…",
            checking=True,
        )

        self.assertEqual(
            self.settings_window.update_status_text.get(),
            "Checking for updates…",
        )
        self.assertEqual(
            str(self.settings_window.check_for_updates_button.cget("state")),
            "disabled",
        )
        self.assertEqual(
            str(self.settings_window.check_for_updates_button.cget("cursor")),
            "arrow",
        )

        self.settings_window.set_update_status("Cat Type is up to date.")

        self.assertEqual(
            self.settings_window.update_status_text.get(),
            "Cat Type is up to date.",
        )
        self.assertEqual(
            str(self.settings_window.check_for_updates_button.cget("state")),
            "normal",
        )
        self.assertEqual(
            str(self.settings_window.check_for_updates_button.cget("cursor")),
            "arrow",
        )

    def test_persistent_keystroke_counter_is_visible_and_updates_live(self) -> None:
        self.assertEqual(
            self.settings_window.keystroke_count_title.cget("text"),
            "All-time keystrokes",
        )
        self.assertEqual(
            self.settings_window.keystroke_count_text.get(),
            "1,234",
        )

        self.settings_window.update_keystroke_count(5_678)

        self.assertEqual(
            self.settings_window.keystroke_count_text.get(),
            "5,678",
        )

    def test_metrics_screen_shows_aggregate_activity_and_switches_ranges(
        self,
    ) -> None:
        today = datetime.now().astimezone().date()
        yesterday = today - timedelta(days=1)
        metrics = UsageMetrics(
            total_keystrokes=3_000,
            daily={
                yesterday.isoformat(): 1_000,
                today.isoformat(): 2_000,
            },
            hourly={f"{today.isoformat()}T09": 2_000},
        )

        self.settings_window.update_usage_metrics(metrics)
        self.settings_window.active_page.set("Metrics")
        self.settings_window._switch_page()
        self.settings_window.window.update()

        self.assertTrue(self.settings_window.metrics_page.winfo_ismapped())
        self.assertFalse(self.settings_window.columns.winfo_ismapped())
        self.assertEqual(self.settings_window.metrics_today_text.get(), "2,000")
        self.assertEqual(self.settings_window.metrics_week_text.get(), "3,000")
        self.assertEqual(self.settings_window.metrics_total_text.get(), "3,000")
        self.assertGreater(
            len(self.settings_window.metrics_chart.find_all()),
            0,
        )
        self.assertFalse(hasattr(self.settings_window, "daily_metrics_chart"))
        self.assertFalse(hasattr(self.settings_window, "hourly_metrics_chart"))
        self.assertEqual(
            set(self.settings_window.metrics_range_buttons),
            {1, 7, 30},
        )

        self.settings_window.metrics_range_days.set(1)
        self.settings_window._change_metrics_range()

        self.assertEqual(self.settings_window.metrics_range_days.get(), 1)
        self.assertEqual(
            self.settings_window.metrics_range_buttons[1].cget("background"),
            self.settings_window.ACCENT,
        )
        self.assertEqual(
            self.settings_window.metrics_range_buttons[1].cget(
                "highlightbackground"
            ),
            self.settings_window.FOCUS,
        )

        self.settings_window.metrics_range_days.set(30)
        self.settings_window._change_metrics_range()

        self.assertEqual(self.settings_window.metrics_range_days.get(), 30)
        self.assertEqual(
            self.settings_window.metrics_range_buttons[30].cget("background"),
            self.settings_window.ACCENT,
        )

    def test_metrics_view_switches_without_resetting_range(self) -> None:
        now = datetime.now().astimezone()
        today = now.date()
        self.settings_window.update_usage_metrics(
            UsageMetrics(
                total_keystrokes=30,
                daily={today.isoformat(): 30},
                hourly={f"{today.isoformat()}T{now.hour:02d}": 30},
            )
        )
        self.settings_window.active_page.set("Metrics")
        self.settings_window._switch_page()
        self.settings_window.window.update()

        self.assertEqual(self.settings_window.metrics_view.get(), "line")
        self.assertEqual(
            set(self.settings_window.metrics_view_buttons),
            {"line", "columns"},
        )
        self.assertEqual(
            self.settings_window.metrics_range_label.cget("text"),
            "Range",
        )
        self.assertEqual(
            self.settings_window.metrics_view_label.cget("text"),
            "View",
        )
        self.assertTrue(self.settings_window.metrics_interval_text.get())
        line_ids = self.settings_window.metrics_chart.find_withtag(
            "metric-line"
        )
        self.assertEqual(len(line_ids), 1)
        self.assertEqual(
            self.settings_window.metrics_chart.itemcget(
                line_ids[0],
                "smooth",
            ),
            "0",
        )
        self.on_save.assert_not_called()

        self.settings_window.metrics_range_days.set(1)
        self.settings_window.metrics_view.set("columns")
        self.settings_window._change_metrics_view()

        self.assertEqual(self.settings_window.metrics_range_days.get(), 1)
        self.assertEqual(self.on_save.call_count, 1)
        self.assertEqual(self.on_save.call_args.args[0].metrics_view, "columns")
        self.assertTrue(
            self.settings_window.metrics_chart.find_withtag("metric-column")
        )
        self.assertFalse(
            self.settings_window.metrics_chart.find_withtag("metric-line")
        )

        self.settings_window.metrics_range_days.set(30)
        self.settings_window._change_metrics_range()

        self.assertEqual(self.settings_window.metrics_view.get(), "columns")
        self.assertEqual(self.on_save.call_count, 1)

    def test_metrics_navigation_shows_previous_days_and_weeks(self) -> None:
        today = datetime.now().astimezone().date()
        yesterday = today - timedelta(days=1)
        previous_week_start = today - timedelta(days=13)
        previous_week_end = today - timedelta(days=7)
        previous_week = {
            (previous_week_start + timedelta(days=offset)).isoformat(): offset + 1
            for offset in range(7)
        }
        yesterday_hours = {
            f"{yesterday.isoformat()}T{hour:02d}": hour + 1
            for hour in range(24)
        }
        self.settings_window.update_usage_metrics(
            UsageMetrics(
                daily=previous_week,
                hourly=yesterday_hours,
            )
        )
        self.settings_window.active_page.set("Metrics")
        self.settings_window._switch_page()
        self.settings_window.window.update()

        self.settings_window.metrics_range_days.set(1)
        self.settings_window._change_metrics_range()
        self.assertEqual(
            str(self.settings_window.metrics_next_button.cget("state")),
            "disabled",
        )

        self.settings_window._navigate_metrics_period(-1)

        self.assertEqual(self.settings_window.metrics_period_offset, -1)
        self.assertEqual(
            self.settings_window.metrics_interval_text.get(),
            f"{yesterday.strftime('%a')} · "
            f"{yesterday.day} {yesterday.strftime('%b %Y')}",
        )
        self.assertEqual(self.settings_window._metrics_values, list(range(1, 25)))
        self.assertEqual(len(self.settings_window._metrics_positions), 24)
        self.assertFalse(
            self.settings_window.metrics_chart.find_withtag("metric-partial")
        )
        self.assertEqual(
            str(self.settings_window.metrics_next_button.cget("state")),
            "normal",
        )

        self.settings_window._navigate_metrics_period(1)

        self.assertEqual(self.settings_window.metrics_period_offset, 0)
        self.assertEqual(
            str(self.settings_window.metrics_next_button.cget("state")),
            "disabled",
        )

        self.settings_window.metrics_range_days.set(7)
        self.settings_window._change_metrics_range()
        self.settings_window._navigate_metrics_period(-1)

        self.assertEqual(self.settings_window.metrics_period_offset, -1)
        self.assertEqual(self.settings_window._metrics_values, list(range(1, 8)))
        self.assertIn(
            str(previous_week_start.day),
            self.settings_window.metrics_interval_text.get(),
        )
        self.assertIn(
            str(previous_week_end.day),
            self.settings_window.metrics_interval_text.get(),
        )
        self.assertFalse(
            self.settings_window.metrics_chart.find_withtag("metric-partial")
        )

        self.settings_window.metrics_range_days.set(30)
        self.settings_window._change_metrics_range()

        self.assertEqual(self.settings_window.metrics_period_offset, 0)

    def test_columns_cover_observed_buckets_with_exact_scaled_bounds(self) -> None:
        today = datetime.now().astimezone().date()
        daily = {
            (today - timedelta(days=offset)).isoformat(): offset + 1
            for offset in range(30)
        }
        hourly = {
            f"{today.isoformat()}T{hour:02d}": hour + 1
            for hour in range(24)
        }
        metrics = UsageMetrics(
            total_keystrokes=sum(daily.values()) + sum(hourly.values()),
            daily=daily,
            hourly=hourly,
        )
        self.settings_window.update_usage_metrics(metrics)
        self.settings_window.active_page.set("Metrics")
        self.settings_window._switch_page()
        self.settings_window.window.update()
        canvas = self.settings_window.metrics_chart

        observed_hours = datetime.now().astimezone().hour + 1
        for days, expected_count in (
            (1, observed_hours),
            (7, 7),
            (30, 30),
        ):
            with self.subTest(days=days):
                self.settings_window.metrics_range_days.set(days)
                self.settings_window.metrics_view.set("columns")
                self.settings_window._draw_metrics()

                width = max(320, canvas.winfo_width())
                height = max(180, canvas.winfo_height())
                values = (
                    metrics.hourly_series(today)
                    if days == 1
                    else [
                        count
                        for _day, count in metrics.daily_series(
                            days,
                            ending_on=today,
                        )
                    ]
                )
                visible_values = values[:expected_count]
                axis_maximum, _ticks = SettingsWindow._metric_axis(
                    max(visible_values, default=0)
                )
                expected_positions = SettingsWindow._metric_column_positions(
                    values,
                    width,
                    height,
                    left=46,
                    right=14,
                    top=24,
                    bottom=34,
                    maximum=axis_maximum,
                )
                expected_width = max(
                    3,
                    min(22, ((width - 46 - 14) / len(values)) * 0.56),
                )
                column_ids = canvas.find_withtag("metric-column")

                self.assertEqual(len(column_ids), expected_count)
                for item_id, (x, baseline, value_y) in zip(
                    column_ids,
                    expected_positions,
                ):
                    self.assertEqual(canvas.type(item_id), "polygon")
                    coordinates = canvas.coords(item_id)
                    x_coordinates = coordinates[::2]
                    y_coordinates = coordinates[1::2]
                    self.assertAlmostEqual(
                        min(x_coordinates),
                        x - expected_width / 2,
                    )
                    self.assertAlmostEqual(
                        max(x_coordinates),
                        x + expected_width / 2,
                    )
                    self.assertAlmostEqual(min(y_coordinates), value_y)
                    self.assertAlmostEqual(max(y_coordinates), baseline)

    def test_line_points_and_columns_share_each_range_scale(self) -> None:
        today = datetime.now().astimezone().date()
        daily = {
            (today - timedelta(days=offset)).isoformat(): offset + 1
            for offset in range(30)
        }
        hourly = {
            f"{today.isoformat()}T{hour:02d}": hour + 1
            for hour in range(24)
        }
        self.settings_window.update_usage_metrics(
            UsageMetrics(
                total_keystrokes=sum(daily.values()) + sum(hourly.values()),
                daily=daily,
                hourly=hourly,
            )
        )
        self.settings_window.active_page.set("Metrics")
        self.settings_window._switch_page()
        self.settings_window.window.update()
        canvas = self.settings_window.metrics_chart

        observed_hours = datetime.now().astimezone().hour + 1
        for days, expected_count in (
            (1, observed_hours),
            (7, 7),
            (30, 30),
        ):
            with self.subTest(days=days):
                self.settings_window.metrics_range_days.set(days)
                self.settings_window.metrics_view.set("line")
                self.settings_window._draw_metrics()
                if expected_count == 1:
                    point_id = canvas.find_withtag("metric-single-point")[0]
                    x0, y0, x1, y1 = canvas.coords(point_id)
                    line_points = [((x0 + x1) / 2, (y0 + y1) / 2)]
                else:
                    line_id = canvas.find_withtag("metric-line")[0]
                    line_coordinates = canvas.coords(line_id)
                    line_points = list(
                        zip(line_coordinates[::2], line_coordinates[1::2])
                    )
                    self.assertEqual(canvas.itemcget(line_id, "width"), "2.0")
                self.assertEqual(len(line_points), expected_count)
                self.assertFalse(canvas.find_withtag("metric-point"))

                self.settings_window.metrics_view.set("columns")
                self.settings_window._draw_metrics()
                column_tops = []
                column_baselines = []
                for column_id in canvas.find_withtag("metric-column"):
                    coordinates = canvas.coords(column_id)
                    column_tops.append(min(coordinates[1::2]))
                    column_baselines.append(max(coordinates[1::2]))

                self.assertEqual(column_tops, [y for _x, y in line_points])
                self.assertEqual(len(set(column_baselines)), 1)

    def test_line_chart_reveals_exact_values_on_hover_and_keyboard_focus(
        self,
    ) -> None:
        today = datetime.now().astimezone().date()
        daily = {
            (today - timedelta(days=offset)).isoformat(): (offset + 1) * 100
            for offset in range(7)
        }
        self.settings_window.update_usage_metrics(
            UsageMetrics(
                total_keystrokes=sum(daily.values()),
                daily=daily,
            )
        )
        self.settings_window.active_page.set("Metrics")
        self.settings_window._switch_page()
        self.settings_window.window.update()
        canvas = self.settings_window.metrics_chart

        self.assertFalse(canvas.find_withtag("metric-point"))
        self.assertTrue(canvas.find_withtag("metric-partial"))
        self.assertEqual(
            canvas.itemcget(canvas.find_withtag("metric-partial-label")[0], "text"),
            "so far",
        )

        self.settings_window._show_metrics_inspection(6)

        self.assertTrue(canvas.find_withtag("metric-crosshair"))
        self.assertTrue(canvas.find_withtag("metric-active-point"))
        tooltip_id = canvas.find_withtag("metric-tooltip-text")[0]
        tooltip_text = canvas.itemcget(tooltip_id, "text")
        self.assertIn(
            f"{today.strftime('%a')}, {today.day} {today.strftime('%b %Y')}",
            tooltip_text,
        )
        self.assertIn(f"{daily[today.isoformat()]:,} keystrokes", tooltip_text)
        self.assertIn("so far", tooltip_text)

        canvas.focus_force()
        self.settings_window._move_metrics_inspection(
            SimpleNamespace(),
            -1,
        )

        self.assertEqual(self.settings_window._metrics_selected_index, 5)
        tooltip_id = canvas.find_withtag("metric-tooltip-text")[0]
        self.assertNotIn("so far", canvas.itemcget(tooltip_id, "text"))

    def test_one_day_line_stops_at_the_current_partial_hour(self) -> None:
        now = datetime.now().astimezone()
        today = now.date()
        hourly = {
            f"{today.isoformat()}T{hour:02d}": hour + 1
            for hour in range(24)
        }
        self.settings_window.update_usage_metrics(
            UsageMetrics(
                total_keystrokes=sum(hourly.values()),
                hourly=hourly,
            )
        )
        self.settings_window.active_page.set("Metrics")
        self.settings_window._switch_page()
        self.settings_window.metrics_range_days.set(1)
        self.settings_window._change_metrics_range()
        self.settings_window.window.update()

        if now.hour == 0:
            self.assertTrue(
                self.settings_window.metrics_chart.find_withtag(
                    "metric-single-point"
                )
            )
        else:
            line_id = self.settings_window.metrics_chart.find_withtag(
                "metric-line"
            )[0]
            line_coordinates = self.settings_window.metrics_chart.coords(line_id)
            self.assertEqual(len(line_coordinates) // 2, now.hour + 1)
        self.settings_window._show_metrics_inspection(now.hour)
        tooltip_id = self.settings_window.metrics_chart.find_withtag(
            "metric-tooltip-text"
        )[0]
        self.assertIn(
            "so far",
            self.settings_window.metrics_chart.itemcget(tooltip_id, "text"),
        )

    def test_both_views_keep_empty_labels_resize_and_live_refresh(self) -> None:
        today = datetime.now().astimezone().date()
        self.settings_window.active_page.set("Metrics")
        self.settings_window._switch_page()
        self.settings_window.window.update()
        canvas = self.settings_window.metrics_chart

        for days, empty_message in (
            (1, "No activity recorded today yet"),
            (7, "Start typing to see your daily rhythm"),
            (30, "Start typing to see your daily rhythm"),
        ):
            texts_by_view: dict[str, set[str]] = {}
            for view in ("line", "columns"):
                with self.subTest(days=days, view=view):
                    self.settings_window.update_usage_metrics(UsageMetrics())
                    self.settings_window.metrics_range_days.set(days)
                    self.settings_window.metrics_view.set(view)
                    self.settings_window._draw_metrics()

                    self.assertFalse(canvas.find_withtag("metric-line"))
                    self.assertFalse(canvas.find_withtag("metric-point"))
                    self.assertFalse(canvas.find_withtag("metric-column"))
                    self.assertFalse(canvas.find_withtag("metric-partial"))
                    texts = {
                        canvas.itemcget(item_id, "text")
                        for item_id in canvas.find_all()
                        if canvas.type(item_id) == "text"
                    }
                    self.assertIn(empty_message, texts)
                    texts_by_view[view] = texts

                    previous_item_ids = set(canvas.find_all())
                    canvas.event_generate("<Configure>")
                    self.settings_window.window.update()
                    self.assertTrue(
                        set(canvas.find_all()).isdisjoint(previous_item_ids)
                    )
                    self.assertEqual(
                        self.settings_window.metrics_range_days.get(),
                        days,
                    )
                    self.assertEqual(self.settings_window.metrics_view.get(), view)

                    now = datetime.now().astimezone()
                    updated = UsageMetrics(
                        total_keystrokes=9,
                        daily={today.isoformat(): 9},
                        hourly={f"{today.isoformat()}T{now.hour:02d}": 9},
                    )
                    self.settings_window.update_usage_metrics(updated)
                    self.assertEqual(
                        self.settings_window.metrics_range_days.get(),
                        days,
                    )
                    self.assertEqual(self.settings_window.metrics_view.get(), view)
                    expected_tag = "metric-column"
                    if view == "line":
                        expected_tag = (
                            "metric-single-point"
                            if days == 1 and now.hour == 0
                            else "metric-line"
                        )
                    self.assertTrue(canvas.find_withtag(expected_tag))

            self.assertEqual(texts_by_view["line"], texts_by_view["columns"])

    def test_saved_metrics_view_is_restored_and_included_on_save(self) -> None:
        on_save = Mock()
        saved_window = SettingsWindow(
            self.root,
            AppSettings(metrics_view="columns"),
            on_save,
        )
        self.addCleanup(saved_window.close)

        self.assertEqual(saved_window.metrics_view.get(), "columns")
        self.assertEqual(
            saved_window.metrics_view_buttons["columns"].cget("background"),
            saved_window.ACCENT,
        )
        on_save.assert_not_called()

        saved_window.enabled.set(False)

        saved_settings = on_save.call_args.args[0]
        self.assertEqual(saved_settings.metrics_view, "columns")

    def test_footer_is_outside_scrollable_content(self) -> None:
        self.assertTrue(hasattr(self.settings_window, "footer"))
        self.assertTrue(hasattr(self.settings_window, "scroll_host"))
        self.assertTrue(hasattr(self.settings_window, "scroll_content"))
        self.assertTrue(hasattr(self.settings_window, "scroll_canvas"))
        self.settings_window.window.geometry("700x480")
        self.settings_window.window.update()

        self.assertIs(
            self.settings_window.footer.master,
            self.settings_window.body,
        )
        self.assertIs(
            self.settings_window.scroll_host.master,
            self.settings_window.body,
        )
        self.assertIs(
            self.settings_window.scroll_content.master,
            self.settings_window.scroll_canvas,
        )
        self.assertIsNot(
            self.settings_window.footer.master,
            self.settings_window.scroll_content,
        )
        content_bounds = self.settings_window.scroll_canvas.bbox("all")
        self.assertIsNotNone(content_bounds)
        assert content_bounds is not None
        self.assertGreater(
            content_bounds[3] - content_bounds[1],
            self.settings_window.scroll_canvas.winfo_height(),
        )

    def test_narrow_footer_keeps_actions_fully_visible(self) -> None:
        self.settings_window.window.minsize(1, 1)
        self.settings_window.window.geometry("600x480")
        self.settings_window.window.update()
        buttons = [
            button
            for button in self.settings_window.footer_buttons.winfo_children()
            if button.winfo_ismapped()
        ]

        for button in buttons:
            with self.subTest(button=button.cget("text")):
                self.assertEqual(
                    button.winfo_width(),
                    button.winfo_reqwidth(),
                )
                self.assertGreaterEqual(
                    button.winfo_rootx(),
                    self.settings_window.window.winfo_rootx(),
                )
                self.assertLessEqual(
                    button.winfo_rootx() + button.winfo_width(),
                    self.settings_window.window.winfo_rootx()
                    + self.settings_window.window.winfo_width(),
                )

        self.assertFalse(hasattr(self.settings_window, "footer_message"))
        self.assertFalse(hasattr(self.settings_window, "_on_footer_configure"))

    def test_narrow_layout_keeps_the_studio_shelves_in_one_column(self) -> None:
        self.settings_window.window.geometry("700x480")
        self.settings_window.window.update()

        self.assertEqual(self.settings_window._layout_mode, "narrow")
        self.assertTrue(
            all(shelf.master is self.settings_window.columns
                for shelf in self.settings_window.settings_shelves)
        )
        self.assertFalse(self.settings_window.preview_canvas.winfo_ismapped())
        self.assertFalse(hasattr(self.settings_window, "hero_headline"))

    def test_narrow_layout_can_scroll_to_every_cat_style_choice(self) -> None:
        self.settings_window.window.geometry("700x480")
        self.settings_window.window.update()
        last_button = self.settings_window.cat_style_buttons["Black & white"]
        fully_visible = False
        for step in range(21):
            self.settings_window.scroll_canvas.yview_moveto(step / 20)
            self.settings_window.window.update()
            viewport_top = self.settings_window.scroll_canvas.winfo_rooty()
            viewport_bottom = (
                viewport_top + self.settings_window.scroll_canvas.winfo_height()
            )
            button_top = last_button.winfo_rooty()
            button_bottom = button_top + last_button.winfo_height()
            if button_top >= viewport_top and button_bottom <= viewport_bottom:
                fully_visible = True
                break
        self.assertTrue(fully_visible)

    def test_wide_layout_keeps_the_studio_shelves_in_one_column(self) -> None:
        self.settings_window.window.geometry("920x800")
        self.settings_window.window.update()

        self.assertEqual(self.settings_window._layout_mode, "wide")
        self.assertTrue(
            all(shelf.master is self.settings_window.columns
                for shelf in self.settings_window.settings_shelves)
        )
        self.assertFalse(self.settings_window.preview_canvas.winfo_ismapped())

    def test_shelf_content_fits_when_window_is_resized(self) -> None:
        from settings_window import RoundedPanel

        for width in (920, 700, 600):
            self.settings_window.window.minsize(1, 1)
            self.settings_window.window.geometry(f"{width}x600")
            self.settings_window.window.update()
            for shelf in self.settings_window.settings_shelves:
                if isinstance(shelf, RoundedPanel):
                    with self.subTest(width=width, shelf=shelf):
                        self.assertLessEqual(
                            shelf.content.winfo_x() + shelf.content.winfo_width(),
                            shelf.winfo_width() - shelf._padding,
                        )

    def test_rounded_shelf_reuses_image_when_geometry_is_unchanged(self) -> None:
        shelf = self.settings_window.page_switcher
        self.settings_window.window.update()
        first_image = shelf._shelf_image
        shelf._draw()
        self.assertIs(first_image, shelf._shelf_image)

    def test_update_status_wraps_to_the_available_card_width(self) -> None:
        self.settings_window.set_update_status(
            "A longer update status that needs to wrap cleanly inside the card."
        )
        self.settings_window.window.geometry("700x480")
        self.settings_window.window.update()

        self.assertEqual(
            int(float(self.settings_window.update_status_label.cget("wraplength"))),
            self.settings_window.update_status_label.master.winfo_width(),
        )
        self.assertLessEqual(
            self.settings_window.update_status_label.winfo_reqwidth(),
            self.settings_window.update_status_label.winfo_width(),
        )

    def test_custom_toggles_are_keyboard_focusable_and_title_only(self) -> None:
        cases = (
            (
                self.settings_window.enabled_toggle,
                self.settings_window.enabled,
                "Show my cat while I type",
            ),
            (
                self.settings_window.launch_at_startup_toggle,
                self.settings_window.launch_at_startup,
                "Start Cat Type when I sign in",
            ),
        )

        for toggle, variable, title in cases:
            with self.subTest(title=title):
                copy = next(
                    child
                    for child in toggle.winfo_children()
                    if isinstance(child, tk.Frame)
                )
                labels = copy.winfo_children()
                self.assertEqual(
                    [label.cget("text") for label in labels],
                    [
                        title,
                        (
                            "Keep the companion visible as you work."
                            if title == "Show my cat while I type"
                            else "Have the companion ready when your day starts."
                        ),
                    ],
                )
                self.assertGreater(copy.winfo_reqheight(), labels[0].winfo_reqheight())
                self.assertTrue(bool(int(toggle.cget("takefocus"))))

                value_before = variable.get()
                toggle.focus_force()
                self.settings_window.window.update()
                toggle.event_generate("<space>")
                self.settings_window.window.update()

                self.assertEqual(variable.get(), not value_before)

    def test_soft_pill_focus_highlight_tracks_pressed_face(self) -> None:
        button = self.settings_window.check_for_updates_button
        button._focused = True
        button._pressed = False
        button._draw()
        normal_surface = button._pill_image

        button._pressed = True
        button._draw()
        pressed_surface = button._pill_image

        self.assertIsNot(normal_surface, pressed_surface)

    def test_soft_pill_actions_do_not_draw_a_dark_lower_rail(self) -> None:
        button = self.settings_window.check_for_updates_button
        button._focused = False
        button._pressed = False
        button._draw()

        polygon_fills = [
            str(button.itemcget(item, "fill"))
            for item in button.find_all()
            if button.type(item) == "polygon"
        ]

        self.assertNotIn(self.settings_window.INK, polygon_fills)

    def test_soft_pill_corners_are_rounded_without_becoming_capsules(self) -> None:
        radius = soft_pill_radius(35)
        self.assertGreater(radius, 0)
        self.assertLess(radius, 35 // 2)

    def test_soft_pill_style_switch_keeps_primary_and_secondary_faces_consistent(
        self,
    ) -> None:
        button = self.settings_window.check_for_updates_button

        button.configure(style=self.settings_window.primary_button_style)
        self.assertEqual(button._fill, self.settings_window.ACCENT)

        button.configure(style=self.settings_window.secondary_button_style)
        self.assertEqual(button._fill, self.settings_window.CARD)

    def test_cat_scale_uses_the_full_clickable_range(self) -> None:
        scales: list[CatScale] = []

        def collect(widget: tk.Misc) -> None:
            for child in widget.winfo_children():
                if isinstance(child, CatScale):
                    scales.append(child)
                collect(child)

        collect(self.settings_window.window)
        self.assertEqual(len(scales), 3)
        scale = scales[0]
        self.settings_window.window.update()

        scale.event_generate(
            "<Button-1>",
            x=scale.winfo_width() - 1,
            y=12,
        )
        self.settings_window.window.update()

        self.assertEqual(self.settings_window.size_percent.get(), 175)

    def test_selected_cat_style_has_a_stable_accent_border(self) -> None:
        widths_before = {
            label: button.winfo_reqwidth()
            for label, button in self.settings_window.cat_style_buttons.items()
        }

        self.settings_window.cat_style_buttons["Ginger tabby"].invoke()
        self.settings_window.window.update()

        self.assertEqual(self.settings_window.cat_style.get(), "Ginger tabby")
        for label, button in self.settings_window.cat_style_buttons.items():
            with self.subTest(label=label):
                expected = (
                    self.settings_window.FOCUS
                    if label == "Ginger tabby"
                    else self.settings_window.BORDER
                )
                self.assertEqual(button.cget("highlightbackground"), expected)
                self.assertEqual(button.winfo_reqwidth(), widths_before[label])

    def test_preview_loader_includes_every_cat_variant(self) -> None:
        icon_path = (
            Path(__file__).resolve().parents[1] / "assets" / "cat-type.png"
        )
        self.settings_window._preview_frames.clear()

        self.settings_window._load_preview_frames(str(icon_path))

        self.assertEqual(
            set(self.settings_window._preview_frames),
            set(CAT_VARIANTS),
        )
        for variant, frames in self.settings_window._preview_frames.items():
            with self.subTest(variant=variant):
                self.assertEqual(
                    set(frames),
                    {"idle", "tap-left", "tap-right", "excited"},
                )

    def test_all_cats_have_four_real_148_pixel_svg_previews(self) -> None:
        icon_path = (
            Path(__file__).resolve().parents[1] / "assets" / "cat-type.png"
        )
        self.settings_window._preview_frames.clear()

        self.settings_window._load_preview_frames(str(icon_path))

        for variant in CAT_VARIANTS:
            frames = self.settings_window._preview_frames[variant]
            self.assertEqual(
                set(frames),
                {"idle", "tap-left", "tap-right", "excited"},
            )
            for name, frame in frames.items():
                with self.subTest(variant=variant, name=name):
                    self.assertEqual((frame.width(), frame.height()), (148, 148))

    def test_settings_offer_six_cats_and_mix_it_up(self) -> None:
        self.assertEqual(
            tuple(self.settings_window.cat_style_buttons),
            (
                "Mix it up",
                "Gray tabby",
                "Ginger tabby",
                "Charcoal",
                "Brown tabby",
                "White",
                "Black & white",
            ),
        )

    def test_non_white_cat_choice_is_applied_automatically(self) -> None:
        self.settings_window.cat_style_buttons["Black & white"].invoke()

        saved_settings = self.on_save.call_args.args[0]
        self.assertEqual(saved_settings.cat_style, "black-white")

    def test_settings_are_persisted_on_change_without_closing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            self.settings_window._on_save = lambda settings: store.save(settings)
            self.assertFalse(store.path.exists())
            cases = (
                ("enabled", False, False),
                ("cat_style", "Black & white", "black-white"),
                ("size_percent", 125, 125),
                ("hold_seconds", 2.0, 2.0),
                ("fade_seconds", 1.5, 1.5),
                ("hold_seconds", 0.5, 0.5),
                ("placement", "Below · left", "below-left"),
                ("launch_at_startup", True, True),
            )
            for field, value, expected in cases:
                with self.subTest(field=field, value=value):
                    getattr(self.settings_window, field).set(value)
                    if field == "size_percent":
                        self.root.after(300, self.root.quit)
                        self.root.mainloop()
                    self.assertTrue(store.path.exists())
                    self.assertEqual(getattr(store.load(), field), expected)
                    self.assertTrue(self.settings_window.window.winfo_exists())
            self.assertEqual(store.load().fade_seconds, 0.5)
            self.settings_window.close()
            self.assertEqual(store.load().placement, "below-left")
            self.assertTrue(store.load().launch_at_startup)

    def test_opening_or_reselecting_settings_does_not_save(self) -> None:
        self.settings_window.enabled.set(True)
        self.settings_window.cat_style_buttons["Mix it up"].invoke()
        self.settings_window.size_percent.set(100)
        self.on_save.assert_not_called()

    def test_metrics_view_autosaves_with_other_settings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            self.settings_window._on_save = store.save
            self.settings_window.size_percent.set(125)
            self.settings_window.metrics_view_buttons["columns"].invoke()
            self.assertEqual(store.load().metrics_view, "columns")
            self.assertEqual(store.load().size_percent, 125)
            self.assertTrue(self.settings_window.window.winfo_exists())

    def test_metrics_autosave_failure_is_retried_on_close(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            self.settings_window._on_save = lambda settings: store.save(settings)
            with patch.object(store, "save", side_effect=OSError("disk full")):
                self.settings_window.metrics_view_buttons["columns"].invoke()
                self.assertIn("Couldn't save", self.settings_window.save_status.get())
            self.settings_window.close()
            self.assertEqual(store.load().metrics_view, "columns")

    def test_size_drag_saves_latest_value_after_a_short_pause(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            self.settings_window._on_save = store.save
            for size in (110, 120, 125):
                self.settings_window.size_percent.set(size)
            self.assertFalse(store.path.exists())
            self.root.after(300, self.root.quit)
            self.root.mainloop()
            self.assertEqual(store.load().size_percent, 125)
            self.assertTrue(self.settings_window.window.winfo_exists())

    def test_closing_immediately_after_a_size_change_saves_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            self.settings_window._on_save = store.save
            self.settings_window.size_percent.set(140)
            self.settings_window.close()
            self.assertEqual(store.load().size_percent, 140)
            self.assertFalse(self.settings_window.window.winfo_exists())

    def test_failed_autosave_is_reported_and_retried_before_close(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            self.settings_window._on_save = lambda settings: store.save(settings)
            with patch.object(store, "save", side_effect=OSError("disk full")):
                self.settings_window.enabled.set(False)
                self.assertIn("Couldn't save", self.settings_window.save_status.get())
                self.assertFalse(store.path.exists())
                self.settings_window.close()
                self.assertTrue(self.settings_window.window.winfo_exists())
            self.settings_window.close()
            self.assertFalse(store.load().enabled)
            self.assertFalse(self.settings_window.window.winfo_exists())

    def test_failed_autosave_exposes_inline_retry_action(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            self.settings_window._on_save = lambda settings: store.save(settings)
            with patch.object(store, "save", side_effect=OSError("disk full")):
                self.settings_window.enabled.set(False)
                self.assertEqual(
                    self.settings_window.save_status.get(),
                    "Couldn't save this change. Try again.",
                )
                self.assertEqual(
                    str(self.settings_window.retry_button.cget("state")),
                    "normal",
                )
            self.settings_window._on_save = lambda settings: store.save(settings)
            self.settings_window.retry_button.invoke()
            self.assertEqual(
                self.settings_window.save_status.get(),
                "Saved!",
            )
            self.assertEqual(str(self.settings_window.retry_button.cget("state")), "disabled")

    def test_save_feedback_is_empty_until_a_change_saves(self) -> None:
        self.assertEqual(self.settings_window.save_status.get(), "")
        self.assertFalse(self.settings_window.save_status_surface.winfo_ismapped())
        self.settings_window.enabled.set(not self.settings_window.enabled.get())
        self.settings_window.window.update()
        self.assertEqual(self.settings_window.save_status.get(), "Saved!")
        self.assertTrue(self.settings_window.save_status_surface.winfo_ismapped())
        self.assertEqual(self.settings_window.save_status_surface._fill, self.settings_window.ACCENT)
        self.assertEqual(self.settings_window.save_status_label.cget("foreground"), self.settings_window.INK)
        self.assertGreaterEqual(
            self.settings_window.save_status_surface.winfo_width(),
            self.settings_window.save_status_label.winfo_reqwidth()
            + (self.settings_window.save_status_surface._padding * 2),
        )

    def test_successful_save_schedules_status_clear(self) -> None:
        with patch.object(self.settings_window.window, "after", wraps=self.settings_window.window.after) as after:
            self.settings_window.enabled.set(not self.settings_window.enabled.get())
            self.settings_window._save()
        self.assertIn(call(1600, self.settings_window._clear_save_feedback), after.call_args_list)
        self.settings_window._clear_save_feedback()

    def test_saved_feedback_text_is_centered_inside_its_pill(self) -> None:
        self.assertEqual(self.settings_window.save_status_label.cget("anchor"), "center")
        self.assertEqual(self.settings_window.save_status_label.cget("justify"), "center")
        pack_info = self.settings_window.save_status_label.pack_info()
        self.assertEqual(pack_info.get("fill"), "both")
        self.assertTrue(bool(int(pack_info.get("expand", 0))))

    def test_failure_status_surface_has_room_for_retry_copy(self) -> None:
        self.settings_window.save_status.set("Couldn't save this change. Try again.")
        self.settings_window.window.update_idletasks()
        self.assertGreaterEqual(
            self.settings_window.save_status_surface.winfo_width(),
            self.settings_window.save_status_label.winfo_reqwidth()
            + (self.settings_window.save_status_surface._padding * 2),
        )

    def test_achievements_new_indicator_has_room_for_long_label(self) -> None:
        button = self.settings_window.page_buttons["Achievements"]
        short_width = button.winfo_reqwidth()
        self.settings_window._achievements_unread = True
        self.settings_window._refresh_achievement_indicator()
        self.settings_window.window.update_idletasks()
        self.assertGreaterEqual(button.winfo_reqwidth(), short_width)
        expected_width = tkfont.Font(
            button,
            font=button.cget("font"),
        ).measure("Achievements · New") + (14 * 2) + 8
        self.assertGreaterEqual(button.winfo_reqwidth(), expected_width)
        self.assertLessEqual(
            button.winfo_reqwidth(),
            self.settings_window.page_switcher.content.winfo_width(),
        )

    def test_achievements_new_indicator_scales_with_tk_font(self) -> None:
        root_scaling = float(self.root.tk.call("tk", "scaling"))
        scaled_root = tk.Tk()
        scaled_root.withdraw()
        previous_scaling = float(scaled_root.tk.call("tk", "scaling"))
        scaled_root.tk.call("tk", "scaling", 2.5)
        try:
            scaled = SettingsWindow(scaled_root, AppSettings(), Mock())
            scaled._achievements_unread = True
            scaled._refresh_achievement_indicator()
            scaled.window.update_idletasks()
            button = scaled.page_buttons["Achievements"]
            expected_width = tkfont.Font(
                button,
                font=button.cget("font"),
            ).measure("Achievements · New") + (14 * 2) + 8
            self.assertGreaterEqual(button.winfo_reqwidth(), expected_width)
            self.assertLessEqual(
                button.winfo_reqwidth(),
                scaled.page_switcher.content.winfo_width(),
            )
        finally:
            if "scaled" in locals():
                scaled.close()
            self.root.tk.call("tk", "scaling", root_scaling)
            scaled_root.tk.call("tk", "scaling", previous_scaling)
            scaled_root.destroy()

    def test_custom_actions_expose_button_accessibility_metadata(self) -> None:
        button = self.settings_window.check_for_updates_button
        self.assertEqual(button.cget("accessible_role"), "button")
        self.assertEqual(button.cget("accessible_name"), "Check for updates")
        self.assertEqual(button.cget("accessible_state"), "normal")
        button.configure(state="disabled")
        self.assertEqual(button.cget("accessible_state"), "disabled")

    def test_save_feedback_clears_after_success_timeout(self) -> None:
        self.settings_window.save_status.set("Saved!")
        self.settings_window._clear_save_feedback()
        self.assertEqual(self.settings_window.save_status.get(), "")

    def test_save_failure_keeps_actionable_status_and_retry(self) -> None:
        self.on_save.side_effect = OSError("disk full")
        self.settings_window._save_feedback_after_id = "stale-success"
        with patch.object(self.settings_window.window, "after_cancel") as cancel:
            self.settings_window.enabled.set(not self.settings_window.enabled.get())
            self.settings_window._save()
        cancel.assert_called_with("stale-success")
        self.assertEqual(
            self.settings_window.save_status.get(),
            "Couldn't save this change. Try again.",
        )
        self.assertEqual(str(self.settings_window.retry_button.cget("state")), "normal")

    def test_footer_closes_without_reverting_changes(self) -> None:
        self.settings_window.window.update()
        self.assertEqual(
            [
                button.cget("text")
                for button in self.settings_window.footer_buttons.winfo_children()
                if button.winfo_ismapped()
            ],
            ["Close"],
        )
        self.assertFalse(self.settings_window.retry_button.winfo_ismapped())
        self.settings_window.enabled.set(False)
        self.settings_window.close_button.invoke()
        self.assertFalse(self.on_save.call_args.args[0].enabled)
        self.assertFalse(self.settings_window.window.winfo_exists())
