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
                "_center_shell",
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
    def test_uneven_month_labels_do_not_overlap_after_position_clamping(self) -> None:
        # Thirty-day labels land every five days, plus the final day. Six
        # count-selected labels leave only four buckets between the last two.
        candidates = [0, 5, 10, 20, 25, 29]
        width = 540
        text_width = 76  # Includes the canvas text bounding-box inset.
        labels = [(index, 20 + index * 504 / 29, text_width) for index in candidates]
        centers = SettingsWindow._metric_label_centers(labels, width)
        self.assertIn(29, centers)
        self.assertNotIn(25, centers)
        self.assertGreaterEqual(len(centers), 2)
        bounds = sorted((x - text_width / 2, x + text_width / 2) for x in centers.values())
        self.assertGreaterEqual(bounds[0][0], 0)
        self.assertLessEqual(bounds[-1][1], width)
        for previous, following in zip(bounds, bounds[1:]):
            self.assertGreaterEqual(following[0] - previous[1], 8)

    def test_compact_axis_labels_preserve_exact_significant_digits(self) -> None:
        ticks = (0, 5_000_000_000, 10_000_000_000, 15_000_000_000, 20_000_000_000)
        self.assertEqual(
            [SettingsWindow._format_metric_tick(tick, compact=True) for tick in ticks],
            ["0", "5e9", "1e10", "1.5e10", "2e10"],
        )

    def test_axis_label_selection_can_keep_one_measured_label(self) -> None:
        labels = ["18 Dec", None, "23 Dec", None, "28 Dec"]
        self.assertEqual(
            SettingsWindow._metric_label_indices(labels, 90, minimum_spacing=80),
            {4},
        )
        self.assertEqual(
            SettingsWindow._metric_label_indices(labels, 200, minimum_spacing=80),
            {0, 4},
        )

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

    def test_scrollbar_waits_for_nested_height_requests_before_hiding(self) -> None:
        settings_window = SettingsWindow.__new__(SettingsWindow)
        canvas = Mock()
        canvas.bbox.return_value = (0, 0, 601, 580)
        canvas.winfo_height.return_value = 596
        scrollbar = Mock()
        scrollbar.winfo_manager.return_value = "pack"
        content = Mock()
        content.winfo_rooty.return_value = 0
        content.winfo_reqheight.return_value = 580
        shelf = Mock()
        shelf.winfo_ismapped.return_value = True
        shelf.winfo_rooty.return_value = 90
        shelf.winfo_height.return_value = 490
        shelf.winfo_reqheight.return_value = 558
        shelf.winfo_children.return_value = []
        hidden_shelf = Mock()
        hidden_shelf.winfo_ismapped.return_value = False
        hidden_shelf.winfo_manager.return_value = ""
        hidden_shelf.winfo_reqheight.return_value = 2000
        content.winfo_children.return_value = [shelf, hidden_shelf]
        settings_window.scroll_content = content
        settings_window.scroll_canvas = canvas
        settings_window.scrollbar = scrollbar

        # The canvas bbox still fits while a nested shelf's pending request
        # already overflows. Hiding now would reverse the width change before
        # that request has propagated through the parents.
        for origin in (0, 250, -200):
            with self.subTest(content_origin=origin):
                content.winfo_rooty.return_value = origin
                shelf.winfo_rooty.return_value = origin + 90
                settings_window._sync_scrollbar_visibility()
                scrollbar.pack_forget.assert_not_called()

        # Once the real content shrinks, the bar must still disappear.
        shelf.winfo_reqheight.return_value = 490
        settings_window._sync_scrollbar_visibility()
        scrollbar.pack_forget.assert_called_once_with()
        hidden_shelf.winfo_reqheight.assert_not_called()

        # Further content growth restores access immediately, even before
        # the outer canvas window has adopted the new requested height.
        scrollbar.winfo_manager.return_value = ""
        shelf.winfo_reqheight.return_value = 558
        settings_window._sync_scrollbar_visibility()
        scrollbar.pack.assert_called_once_with(side="right", fill="y", before=canvas)

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
    def test_preview_error_visibility_changes_release_scrollbar_latch(self):
        view = SettingsWindow.__new__(SettingsWindow)
        view._preview_errors = {("white", "idle")}
        view.preview_error_text = Mock()
        view.preview_error_surface = Mock()
        view._invalidate_scrollbar_reflow = Mock()
        view.preview_error_surface.winfo_manager.return_value = ""
        view._refresh_preview_error()
        view._invalidate_scrollbar_reflow.assert_called_once_with()
        view._invalidate_scrollbar_reflow.reset_mock()
        view.preview_error_surface.winfo_manager.return_value = "grid"
        view._refresh_preview_error()
        view._invalidate_scrollbar_reflow.assert_not_called()
        view._preview_errors.clear()
        view._refresh_preview_error()
        view._invalidate_scrollbar_reflow.assert_called_once_with()

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
        # Legacy layout cases inspect fully hydrated controls. Startup construction
        # and lazy destination reuse are exercised separately.
        original_init = SettingsWindow.__init__
        def hydrated_init(view, *args, **kwargs):
            original_init(view, *args, **kwargs)
            view.window.update()
            view._ensure_page("Metrics")
        hydration = patch.object(SettingsWindow, "__init__", hydrated_init)
        hydration.start()
        self.addCleanup(hydration.stop)
        self._tk_scaling = float(self.root.tk.call("tk", "scaling"))
        def destroy_root():
            # Save-failure tests intentionally leave the window open; stop its
            # timers before destroying the test interpreter unconditionally.
            for callback in self.root.tk.call("after", "info"):
                self.root.tk.call("after", "cancel", callback)
            self.root.destroy()
        self.addCleanup(destroy_root)
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

    def test_native_chrome_survives_initial_tk_wrapper_recreation(self):
        import sys
        if sys.platform != "win32":
            self.skipTest("Windows native wrapper")
        view = self.settings_window
        chrome = view._window_chrome
        self.assertIsNotNone(chrome.hwnd)
        self.assertEqual(chrome.hwnd, chrome.user.GetParent(view.window.winfo_id()))
        chrome.minimize()
        view.window.update()
        self.assertTrue(chrome.user.IsIconic(chrome.hwnd))
        view.show()
        view.window.update()
        self.assertFalse(chrome.user.IsIconic(chrome.hwnd))
        view._toggle_maximize()
        view.window.update()
        self.assertTrue(chrome.is_maximized())
        self.assertEqual(view.title_bar.controls[1].cget("text"), "Restore")
        view._toggle_maximize()
        view.window.update()
        self.assertFalse(chrome.is_maximized())

    def test_themed_scrollbar_colors_and_overflow_access(self):
        from tkinter import ttk
        view = self.settings_window
        style = ttk.Style(view.window)
        # A quiet neutral thumb leaves Butter Sun for active states.
        self.assertEqual(style.lookup(view.scrollbar_style, "background"), view.SCROLL_THUMB)
        self.assertEqual(style.lookup(view.scrollbar_style, "background", ("pressed",)), view.INK)
        self.assertEqual(style.lookup(view.scrollbar_style, "troughcolor"), view.BACKGROUND)
        self.assertEqual(str(view.scrollbar.cget("takefocus")), "1")
        view.window.geometry("700x480")
        view.window.update()
        view._sync_scrollbar_visibility()
        view.window.update_idletasks()
        self.assertTrue(view.scrollbar.winfo_ismapped())
        view.scrollbar.focus_force()
        self.assertEqual(view.window.focus_get(), view.scrollbar)

    def test_scrollbar_tracks_nested_growth_before_canvas_bbox_updates(self):
        shell = tk.Toplevel(self.root)
        self.addCleanup(shell.destroy)
        shell.geometry("400x300")
        view = SettingsWindow.__new__(SettingsWindow)
        view.scrollbar = tk.Scrollbar(shell)
        view.scrollbar.pack(side="right", fill="y")
        view.scroll_canvas = tk.Canvas(shell, highlightthickness=0)
        view.scroll_canvas.pack(side="left", fill="both", expand=True)
        view.scroll_content = tk.Frame(view.scroll_canvas)
        view.scroll_canvas.create_window((0, 0), anchor="nw", window=view.scroll_content)
        shelf = tk.Frame(view.scroll_content, width=100, height=100)
        shelf.pack()
        shell.update()
        view._sync_scrollbar_visibility()
        shell.update()
        self.assertFalse(view.scrollbar.winfo_ismapped())

        shelf.configure(height=500)
        view._invalidate_scrollbar_reflow()
        self.assertLess(view.scroll_canvas.bbox("all")[3], view.scroll_canvas.winfo_height())
        view._sync_scrollbar_visibility()
        shell.update()
        self.assertTrue(view.scrollbar.winfo_ismapped())

        shelf.configure(height=100)
        view._invalidate_scrollbar_reflow()
        shell.update()
        view._sync_scrollbar_visibility()
        shell.update()
        self.assertFalse(view.scrollbar.winfo_ismapped())

    def test_scrollbar_reflow_cycle_latches_and_releases_for_real_changes(self):
        import _tkinter
        shell = tk.Toplevel(self.root)
        self.addCleanup(shell.destroy)
        shell.geometry("400x200")
        view = SettingsWindow.__new__(SettingsWindow)
        view.window = shell
        view.scrollbar = tk.Scrollbar(shell)
        view.scrollbar.pack(side="right", fill="y")
        view.scroll_canvas = tk.Canvas(shell, highlightthickness=0)
        view.scroll_canvas.pack(side="left", fill="both", expand=True)
        view.scroll_content = tk.Frame(view.scroll_canvas)
        content_id = view.scroll_canvas.create_window((0, 0), anchor="nw", window=view.scroll_content)
        responsive = tk.Frame(view.scroll_content, width=100, height=50)
        responsive.pack_propagate(False)
        responsive.pack()
        label = tk.Label(responsive, text="Responsive content\nMore details")
        label.pack()
        shell.update()
        expanded = True

        def reflow(event):
            view.scroll_canvas.itemconfigure(content_id, width=event.width)
            responsive.configure(height=300 if expanded and event.width >= 395 else 50)
            view._sync_scrollbar_visibility()

        view.scroll_canvas.bind("<Configure>", reflow)
        view.scroll_content.bind("<Configure>", lambda event: view._sync_scrollbar_visibility())

        def settle():
            for _ in range(1000):
                if not shell.tk.dooneevent(_tkinter.ALL_EVENTS | _tkinter.DONT_WAIT):
                    return
            self.fail("Scrollbar visibility did not settle after responsive reflow")

        view._sync_scrollbar_visibility()
        settle()
        self.assertTrue(view.scrollbar.winfo_ismapped())

        shell.geometry("400x400")
        settle()
        self.assertFalse(view.scrollbar.winfo_ismapped())
        shell.geometry("400x200")
        settle()
        self.assertTrue(view.scrollbar.winfo_ismapped())
        shell.geometry("380x200")
        settle()
        self.assertFalse(view.scrollbar.winfo_ismapped())
        shell.geometry("400x200")
        settle()
        self.assertTrue(view.scrollbar.winfo_ismapped())

        expanded = False
        view._invalidate_scrollbar_reflow()
        label.configure(text="Short content")
        responsive.configure(height=50)
        settle()
        self.assertFalse(view.scrollbar.winfo_ismapped())

        expanded = True
        view._invalidate_scrollbar_reflow()
        label.configure(text="Responsive content\nMore details")
        responsive.configure(height=300)
        settle()
        self.assertTrue(view.scrollbar.winfo_ismapped())
        label.destroy()
        expanded = False
        view._invalidate_scrollbar_reflow()
        responsive.configure(height=50)
        label = tk.Label(responsive, text="Another page")
        label.pack()
        settle()
        self.assertFalse(view.scrollbar.winfo_ismapped())

        label.configure(text="\n".join(["Overflowing content"] * 30))
        view._invalidate_scrollbar_reflow()
        settle()
        self.assertTrue(view.scrollbar.winfo_ismapped())

    def test_scrollbar_keyboard_moves_canvas_and_clamps_at_bounds(self):
        view = self.settings_window
        view.window.geometry("700x480")
        view.window.update()
        # Native fonts can make the settings page shorter than two viewports.
        # Provide enough real content that PageDown cannot already reach End.
        spacer = tk.Frame(
            view.scroll_content, height=view.scroll_canvas.winfo_height() * 4
        )
        columns, rows = view.scroll_content.grid_size()
        spacer.grid(row=rows, column=0, columnspan=max(1, columns))
        view.window.update()
        view.scrollbar.focus_force()
        view.window.update()
        def press(key):
            view.scrollbar.event_generate(f"<KeyPress-{key}>")
            view.window.update()
            return view.scroll_canvas.yview()[0]
        self.assertEqual(press("Home"), 0.0)
        down = press("Down")
        self.assertGreater(down, 0.0)
        self.assertLess(press("Up"), down)
        page = press("Next")
        self.assertGreater(page, down)
        self.assertLess(press("Prior"), page)
        end = press("End")
        self.assertGreater(end, page)
        self.assertEqual(view.scroll_canvas.yview()[1], 1.0)
        self.assertEqual(press("Down"), end)
        self.assertEqual(press("Home"), 0.0)
        self.assertEqual(press("Up"), 0.0)

    def test_native_close_retries_pending_save_and_preserves_window_on_failure(self):
        import sys
        if sys.platform != "win32":
            self.skipTest("Windows system close command")
        view = self.settings_window
        view.size_percent.set(view.size_percent.get() + 1)
        self.on_save.side_effect = OSError("test save failure")
        chrome = view._window_chrome
        chrome.user.SendMessageW(chrome.hwnd, 0x112, 0xF060, 0)
        view.window.update()
        self.assertTrue(view.window.winfo_exists())
        self.assertTrue(view._save_failed)
        self.on_save.side_effect = None
        chrome.user.SendMessageW(chrome.hwnd, 0x112, 0xF060, 0)
        self.root.update()
        self.assertFalse(view.window.winfo_exists())
        self.assertGreaterEqual(self.on_save.call_count, 2)

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

    def test_metrics_keeps_summary_and_chart_in_one_activity_shelf(self) -> None:
        self.settings_window.active_page.set("Metrics")
        self.settings_window._switch_page()
        self.settings_window.window.update()
        self.assertEqual(len(self.settings_window.metric_stat_rows), 3)
        self.assertTrue(self.settings_window.metrics_chart.winfo_ismapped())

    def test_metric_totals_are_big_cards_that_stack_when_narrow(self) -> None:
        view = self.settings_window
        view.window.minsize(1, 1)
        view.window.geometry("920x900")
        view.page_buttons["Metrics"].invoke()
        view.window.update()
        for number in view.metric_stat_values:
            self.assertEqual(str(number.cget("font")), str(view.fonts["stat"]))
        self.assertEqual({int(card.grid_info()["column"]) for card in view.metric_stat_rows}, {0, 1, 2})
        with patch.object(view.metrics_summary, "winfo_width", return_value=160):
            view._reflow_metric_stats()
        self.assertEqual({int(card.grid_info()["column"]) for card in view.metric_stat_rows}, {0})
        self.assertEqual({int(card.grid_info()["row"]) for card in view.metric_stat_rows}, {0, 1, 2})

    def test_rail_collapses_to_icons_when_the_page_would_be_crowded(self) -> None:
        view = self.settings_window
        view.window.minsize(1, 1)
        full = view._rail_expanded_width
        roomy = full * 2 + view.RAIL_OUTER + 26 + 80
        view.window.geometry(f"{roomy}x700")
        view.window.update()
        self.assertFalse(view.rail_compact)
        view.window.geometry(f"{full * 2 + view.RAIL_OUTER + 26 - 40}x700")
        view.window.update()
        self.assertTrue(view.rail_compact)
        self.assertLess(view.page_switcher.winfo_width(), full)
        self.assertFalse(view.rail_brand_title.winfo_ismapped())
        for label, button in view.page_buttons.items():
            # Icon only, but the label stays the button's name.
            self.assertTrue(button._compact)
            self.assertEqual(button.cget("text"), label)
            self.assertTrue(button.winfo_ismapped())
        self.assertLessEqual(view._rail_stage_size, view.page_switcher.content.winfo_width())
        view.window.geometry(f"{roomy}x700")
        view.window.update()
        self.assertFalse(view.rail_compact)
        self.assertTrue(view.rail_brand_title.winfo_ismapped())

    def test_navigation_items_carry_icons(self) -> None:
        for label, button in self.settings_window.page_buttons.items():
            self.assertEqual(button._icon, label.lower())
            self.assertEqual(button.cget("text"), label)

    def test_metrics_controls_and_exact_values_fit_narrow_high_dpi_windows(self) -> None:
        metrics_clock = patch("settings_window.datetime", wraps=datetime)
        clock = metrics_clock.start()
        self.addCleanup(metrics_clock.stop)
        clock.now.return_value = datetime(2026, 2, 15, 12).astimezone()
        self.root.tk.call("tk", "scaling", 2.5)
        view = SettingsWindow(self.root, AppSettings(), Mock())
        self.addCleanup(view.close)
        today = clock.now.return_value.date()
        daily = {
            (today - timedelta(days=offset)).isoformat(): (offset + 1) * 777_000_000
            for offset in range(60)
        }
        view.update_usage_metrics(UsageMetrics(total_keystrokes=sum(daily.values()), daily=daily))
        view.page_buttons["Metrics"].invoke()
        view.window.minsize(1, 1)

        def assert_fits(widget: tk.Misc) -> None:
            content = view.metrics_activity_content
            self.assertGreaterEqual(widget.winfo_rootx(), content.winfo_rootx())
            self.assertLessEqual(widget.winfo_rootx() + widget.winfo_reqwidth(),
                                 content.winfo_rootx() + content.winfo_width())
            self.assertGreaterEqual(widget.winfo_width(), widget.winfo_reqwidth())

        for width in (600, 620):
            for _ in range(2):
                view.window.geometry(f"{width}x600")
                view.window.update()
            self.assertEqual(view.window.winfo_width(), width)
            view.metrics_range_buttons[30].invoke()
            view.metrics_view_buttons["columns"].invoke()
            view.metrics_previous_button.invoke()
            view.window.update()
            self.assertIn("2025", view.metrics_interval_text.get())
            self.assertIn("2026", view.metrics_interval_text.get())
            for widget in (
                *view.metric_stat_values,
                *view.metrics_range_buttons.values(),
                *view.metrics_view_buttons.values(),
                view.metrics_range_label, view.metrics_view_label,
                view.metrics_interval_label,
                view.metrics_previous_button, view.metrics_next_button,
            ):
                with self.subTest(width=width, widget=widget):
                    assert_fits(widget)

            canvas = view.metrics_chart
            self.assertEqual(view._metrics_values[-1], daily[(today - timedelta(days=30)).isoformat()])
            self.assertLessEqual(max(x for x, _y in view._metrics_positions), canvas.winfo_width())
            view._show_metrics_inspection(29)
            tooltip = canvas.find_withtag("metric-tooltip-text")[0]
            self.assertIn(f"{31 * 777_000_000:,} keystrokes", canvas.itemcget(tooltip, "text"))
            for tag in ("metric-tooltip", "metric-tooltip-text", "metric-y-label"):
                for item in canvas.find_withtag(tag):
                    left, top, right, bottom = canvas.bbox(item)
                    with self.subTest(width=width, tag=tag):
                        self.assertGreaterEqual(left, 0)
                        self.assertGreaterEqual(top, 0)
                        self.assertLessEqual(right, canvas.winfo_width())
                        self.assertLessEqual(bottom, canvas.winfo_height())
            x_label_bounds = sorted(
                canvas.bbox(item) for item in canvas.find_withtag("metric-x-label")
            )
            for previous, following in zip(x_label_bounds, x_label_bounds[1:]):
                self.assertLess(previous[2], following[0])
            view.metrics_next_button.invoke()
            self.assertEqual(view.metrics_period_offset, 0)
            self.assertEqual(str(view.metrics_next_button.cget("state")), "disabled")

        view.update_usage_metrics(UsageMetrics(
            total_keystrokes=600_000_000_000,
            daily={day: 10_000_000_000 for day in daily},
        ))
        view.window.update()
        axis_texts = {
            view.metrics_chart.itemcget(item, "text")
            for item in view.metrics_chart.find_withtag("metric-y-label")
        }
        # Full labels are used whenever they fit the gutter. Platforms scale
        # Tk fonts differently, so derive which form each tick must take from
        # the same measured limit instead of assuming Windows font metrics.
        canvas = view.metrics_chart
        axis_font = view.fonts["tiny"]
        gutter_limit = (canvas.winfo_width() - min(14, canvas.winfo_width() // 8)) // 2 - 12
        expected = {"0"}
        for full, compact in (("5,000,000k", "5e9"), ("10,000,000k", "1e10"),
                              ("15,000,000k", "1.5e10")):
            expected.add(compact if axis_font.measure(full) > gutter_limit else full)
        self.assertEqual(axis_texts, expected)

    def test_wardrobe_heading_owns_the_mix_action(self) -> None:
        self.assertFalse(self.settings_window.mix_it_up_button.winfo_ismapped())
        self.settings_window.page_buttons["Wardrobe"].invoke()
        self.settings_window.window.update()
        self.assertTrue(self.settings_window.mix_it_up_button.winfo_ismapped())
        self.assertEqual(
            self.settings_window.mix_it_up_button.cget("text"),
            "Mix it up",
        )

    def test_page_headings_and_save_feedback_fit_narrow_high_dpi_windows(self) -> None:
        self.root.tk.call("tk", "scaling", 2.5)
        view = SettingsWindow(self.root, AppSettings(), Mock())
        self.addCleanup(view.close)
        view.window.minsize(1, 1)
        for width in (600, 620):
            for _ in range(2):
                view.window.geometry(f"{width}x600")
                view.window.update()
            for page in ("Wardrobe", "Achievements"):
                view.page_buttons[page].invoke()
                for status in ("", "Saved!", "Couldn't save this change. Try again."):
                    view.save_status.set(status)
                    view.window.update()
                    widgets = [view.page_heading_label]
                    if page == "Wardrobe":
                        widgets.append(view.mix_it_up_button)
                    if status:
                        widgets.append(view.save_status_surface)
                        self.assertTrue(view.save_status_surface.winfo_ismapped())
                        self.assertGreaterEqual(view.save_status_label.winfo_width(),
                                                view.save_status_label.winfo_reqwidth())
                    else:
                        self.assertFalse(view.save_status_surface.winfo_ismapped())
                    for widget in widgets:
                        with self.subTest(width=width, page=page, status=status, widget=widget):
                            self.assertGreaterEqual(widget.winfo_rootx(), view.page_heading.winfo_rootx())
                            self.assertLessEqual(widget.winfo_rootx() + widget.winfo_reqwidth(),
                                                 view.page_heading.winfo_rootx() + view.page_heading.winfo_width())
                            self.assertGreaterEqual(widget.winfo_width(), widget.winfo_reqwidth())
                    if page == "Wardrobe":
                        button = view.mix_it_up_button
                        text = next(item for item in button.find_all() if button.type(item) == "text")
                        left, top, right, bottom = button.bbox(text)
                        self.assertGreaterEqual(left, 0)
                        self.assertGreaterEqual(top, 0)
                        self.assertLessEqual(right, button.winfo_width())
                        self.assertLessEqual(bottom, button.winfo_height())
                        # Narrow fonts may keep the action beside the title;
                        # wider ones stack it underneath. Either way the two
                        # must not overlap.
                        label = view.page_heading_label
                        below = button.winfo_rooty() >= label.winfo_rooty() + label.winfo_height()
                        beside = button.winfo_rootx() >= label.winfo_rootx() + label.winfo_width()
                        self.assertTrue(below or beside)

    def test_settings_rows_keep_controls_on_the_right(self) -> None:
        self.settings_window.active_page.set("Settings")
        self.settings_window._switch_page()
        self.settings_window.window.update_idletasks()
        self.assertLess(
            self.settings_window.cat_style_control.winfo_rootx(),
            self.settings_window.columns.winfo_rootx() + self.settings_window.columns.winfo_width(),
        )

    def test_settings_sliders_align_with_their_labels_at_wide_width(self) -> None:
        self.settings_window.window.geometry("920x800")
        self.settings_window.window.update()

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        widgets = list(descendants(self.settings_window.cat_style_content))
        scales = [widget for widget in widgets if isinstance(widget, CatScale)]
        self.assertEqual(len(scales), 3)
        for title, scale in zip(("Preview scale", "Hang around", "Soft fade"), scales):
            label = next(widget for widget in widgets
                         if isinstance(widget, tk.Label) and widget.cget("text") == title)
            with self.subTest(title=title):
                self.assertGreater(scale.winfo_rootx(), label.winfo_rootx() + label.winfo_width())
                self.assertLess(scale.winfo_rooty(), label.winfo_rooty() + label.master.winfo_height())

    def test_narrow_settings_rows_keep_controls_inside_the_shelf(self) -> None:
        self.settings_window.window.minsize(1, 1)
        self.settings_window.window.geometry("600x600")
        self.settings_window.window.update()
        shelf = self.settings_window.cat_style_content
        controls = (self.settings_window.cat_style_control,
                    self.settings_window.placement_control,
                    self.settings_window.enabled_toggle.switch,
                    self.settings_window.launch_at_startup_toggle.switch)
        for control in controls:
            with self.subTest(control=control):
                self.assertGreaterEqual(control.winfo_rootx(), shelf.winfo_rootx())
                self.assertLessEqual(control.winfo_rootx() + control.winfo_width(),
                                     shelf.winfo_rootx() + shelf.winfo_width())
                self.assertGreaterEqual(control.winfo_width(), control.winfo_reqwidth())

        for control in (self.settings_window.check_for_updates_button,
                        self.settings_window.open_release_page_button):
            with self.subTest(control=control):
                self.assertGreaterEqual(control.winfo_width(), control.winfo_reqwidth())
                self.assertLessEqual(control.winfo_rootx() + control.winfo_width(),
                                     shelf.winfo_rootx() + shelf.winfo_width())

    def test_scaled_narrow_settings_keep_choices_and_copy_reachable(self) -> None:
        self.root.tk.call("tk", "scaling", 2.5)
        view = SettingsWindow(self.root, AppSettings(), Mock())
        self.addCleanup(view.close)
        view.window.minsize(1, 1)
        view.window.update()

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        for width in (600, 620):
            view.window.geometry(f"{width}x600")
            view.window.update()
            # On Windows the first configure also synchronizes native minimums.
            view.window.geometry(f"{width}x600")
            view.window.update()
            self.assertEqual(view.window.winfo_width(), width)
            content = view.cat_style_content
            labels = [child for child in descendants(content)
                      if isinstance(child, tk.Label) and child.winfo_ismapped()]
            for widget in (*view.cat_style_buttons.values(), *labels):
                with self.subTest(width=width, widget=widget):
                    self.assertGreaterEqual(widget.winfo_rootx(), content.winfo_rootx())
                    self.assertLessEqual(widget.winfo_rootx() + widget.winfo_reqwidth(),
                                         content.winfo_rootx() + content.winfo_width())
                    self.assertGreaterEqual(widget.winfo_width(), widget.winfo_reqwidth())
            for choice in view.cat_style_buttons.values():
                visible = False
                for step in range(41):
                    view.scroll_canvas.yview_moveto(step / 40)
                    view.window.update()
                    top = view.scroll_canvas.winfo_rooty()
                    bottom = top + view.scroll_canvas.winfo_height()
                    if top <= choice.winfo_rooty() and (
                        choice.winfo_rooty() + choice.winfo_height() <= bottom
                    ):
                        visible = True
                        break
                self.assertTrue(visible, choice.cget("text"))

            for button in (view.placement_control, view.check_for_updates_button,
                           view.open_release_page_button):
                with self.subTest(width=width, button=button.cget("text")):
                    text_bounds = button.bbox("all")
                    self.assertLessEqual(button.winfo_rootx() + button.winfo_width(),
                                         content.winfo_rootx() + content.winfo_width())
                    self.assertGreaterEqual(button.winfo_width(), button.winfo_reqwidth())
                    self.assertGreaterEqual(text_bounds[0], 0)
                    self.assertLessEqual(text_bounds[2], button.winfo_width())

        view.window.geometry("1200x600")
        view.window.update()
        self.assertEqual(view.cat_style_buttons["Gray tabby"].grid_info()["column"], 1)

    def test_setting_action_text_fits_its_face_at_default_and_large_scaling(self) -> None:
        def assert_text_fits(button):
            text_item = next(item for item in button.find_all() if button.type(item) == "text")
            left, top, right, bottom = button.bbox(text_item)
            self.assertGreaterEqual(left, 0)
            self.assertGreaterEqual(top, 0)
            self.assertLessEqual(right, button.winfo_width())
            self.assertLessEqual(bottom, button.winfo_height())
            return bottom - top

        view = self.settings_window
        view.window.geometry("920x800")
        view.window.update()
        for placement in ("Above · right", "Above · left", "Below · right", "Below · left"):
            view.placement.set(placement)
            view.window.update()
            with self.subTest(placement=placement, scale="default"):
                height = assert_text_fits(view.placement_control)
                face = tkfont.Font(view.placement_control, font=view.placement_control._font)
                self.assertLessEqual(height, face.metrics("linespace") + 3)

        self.root.tk.call("tk", "scaling", 2.5)
        scaled = SettingsWindow(self.root, AppSettings(), Mock(),
                                on_check_for_updates=Mock(), on_open_release_page=Mock(),
                                requires_input_monitoring=True)
        self.addCleanup(scaled.close)
        scaled.window.minsize(1, 1)
        scaled.window.update()
        for _ in range(2):
            scaled.window.geometry("600x600")
            scaled.window.update()
        for placement in ("Above · right", "Above · left", "Below · right", "Below · left"):
            scaled.placement.set(placement)
            scaled.window.update()
            with self.subTest(placement=placement, scale="large"):
                assert_text_fits(scaled.placement_control)
        for checking in (True, False):
            scaled.set_update_status("Checking for updates…" if checking else "Ready", checking)
            scaled.window.update()
            for button in (scaled.check_for_updates_button, scaled.open_release_page_button):
                with self.subTest(button=button.cget("text"), checking=checking):
                    assert_text_fits(button)
        for granted, attempted in ((False, False), (False, True), (True, True)):
            scaled.set_input_monitoring_status(granted, request_attempted=attempted)
            scaled.window.update()
            with self.subTest(button=scaled.input_monitoring_button.cget("text")):
                assert_text_fits(scaled.input_monitoring_button)
        for _ in range(2):
            scaled._toggle_privacy_details()
            scaled.window.update()
            with self.subTest(button=scaled.privacy_details_button.cget("text")):
                assert_text_fits(scaled.privacy_details_button)

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
            "Retry previews",
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
            self.settings_window.page_host,
        )
        self.assertIs(
            self.settings_window.page_switcher.master,
            self.settings_window.scroll_host,
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

    def test_rail_preview_is_a_large_square_stage_above_the_brand(self) -> None:
        self.settings_window.window.geometry("920x800")
        self.settings_window.window.update()
        preview = self.settings_window.rail_preview
        width, height = int(preview.cget("width")), int(preview.cget("height"))
        self.assertEqual(width, height)
        # Fonts differ by platform, so measure against the nav pills the
        # stage spans rather than a fixed pixel size.
        pill_width = next(iter(self.settings_window.page_buttons.values()))._size[0]
        self.assertEqual(width, self.settings_window._rail_stage_max)
        self.assertGreaterEqual(width, pill_width)
        self.assertGreaterEqual(width, 120)
        self.assertGreater(
            int(self.settings_window.rail_brand_title.grid_info()["row"]),
            int(preview.grid_info()["row"]),
        )

    def test_rail_preview_stays_in_view_while_the_page_scrolls(self) -> None:
        self.settings_window.window.geometry("920x600")
        self.settings_window.window.update()
        preview = self.settings_window.rail_preview
        before = preview.winfo_rooty()
        self.settings_window.scroll_canvas.yview_moveto(1.0)
        self.settings_window.window.update()
        self.assertEqual(preview.winfo_rooty(), before)

    def test_short_window_shrinks_the_stage_to_keep_navigation_visible(self) -> None:
        view = self.settings_window
        view.window.minsize(1, 1)
        view.window.geometry("700x800")
        view.window.update()
        # Derive the height from the rail's own metrics, which vary by
        # platform: room for a stage halfway between its minimum and maximum.
        chrome_height = view.window.winfo_height() - view.scroll_host.winfo_height()
        rail_without_stage = (view.page_switcher.content.winfo_reqheight()
                              - int(view.rail_preview.cget("height")))
        host_height = (rail_without_stage + 24 + 18 + view.page_switcher._padding * 2
                       + (view._rail_stage_min + view._rail_stage_max) // 2)
        view.window.geometry(f"700x{host_height + chrome_height}")
        view.window.update()
        view.window.update()
        self.assertLess(int(view.rail_preview.cget("width")), view._rail_stage_max)
        self.assertGreaterEqual(int(view.rail_preview.cget("width")), view._rail_stage_min)
        last_tab = view.page_buttons["Achievements"]
        self.assertLessEqual(
            last_tab.winfo_rooty() + last_tab.winfo_height(),
            view.scroll_host.winfo_rooty() + view.scroll_host.winfo_height(),
        )

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
        self.root.tk.call("tk", "scaling", 0.5)
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
            opening_width = fitted_window.TWO_COLUMN_BREAKPOINT + scrollbar_width - 1
            fitted_window.window.geometry(f"{opening_width}x300")
            fitted_window.window.update()
            frame_inset = max(
                0,
                fitted_window.window.winfo_width()
                - fitted_window.scroll_canvas.winfo_width()
                - scrollbar_width,
            )
            opening_width = fitted_window.TWO_COLUMN_BREAKPOINT + frame_inset + 1
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
        canvas_width = fitted_window.scroll_canvas.winfo_width()
        expected_mode = (
            "wide"
            if canvas_width >= fitted_window.TWO_COLUMN_BREAKPOINT
            else "narrow"
        )
        self.assertEqual(fitted_window._layout_mode, expected_mode)
        self.assertGreaterEqual(actual_height, 300)
        if fitted_window.scrollbar.winfo_ismapped():
            self.assertLess(canvas_width, fitted_window.TWO_COLUMN_BREAKPOINT)
            self.assertGreater(content_height, viewport_height)
        else:
            self.assertGreaterEqual(canvas_width, fitted_window.TWO_COLUMN_BREAKPOINT)
            self.assertGreaterEqual(
                actual_height,
                content_height + non_scroll_height,
            )

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
        first_image = shelf._shelf_images
        shelf._draw()
        self.assertIs(first_image, shelf._shelf_images)

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
        # "Saved!" fits easily; it must read on one line, not "Saved" over "!".
        label = self.settings_window.save_status_label
        self.assertLessEqual(label.winfo_reqheight(),
                             self.settings_window.fonts["control"].metrics("linespace") + 8)
        self.assertGreaterEqual(
            self.settings_window.save_status_surface.winfo_width(),
            self.settings_window.save_status_label.winfo_reqwidth()
            + (self.settings_window.save_status_surface._padding * 2),
        )

    @unittest.skipUnless(sys.platform == "win32", "Windows custom frame")
    def test_window_edges_show_resize_cursor_and_start_native_resize(self) -> None:
        view = self.settings_window
        view.window.update()
        chrome = view._window_chrome
        self.assertTrue(chrome.hwnd)
        right = view.window.winfo_rootx() + view.window.winfo_width() - 2
        middle_y = view.window.winfo_rooty() + view.window.winfo_height() // 2
        # The body reaches the right edge; the border must still work over it.
        self.assertGreaterEqual(view.body.winfo_rootx() + view.body.winfo_width(), right)
        event = SimpleNamespace(x_root=right, y_root=middle_y)
        view._show_resize_cursor(event)
        self.assertEqual(str(view.window.cget("cursor")), "size_we")
        with patch.object(chrome, "begin_resize") as resize:
            self.assertEqual(view._begin_window_resize(event), "break")
        resize.assert_called_once_with(11, event)
        inside = SimpleNamespace(x_root=right - 60, y_root=middle_y)
        view._show_resize_cursor(inside)
        self.assertEqual(str(view.window.cget("cursor")), "")
        self.assertIsNone(view._begin_window_resize(inside))
        # The title bar's top edge resizes instead of moving the window.
        top = SimpleNamespace(x_root=right - 200, y_root=view.window.winfo_rooty() + 1)
        with patch.object(chrome, "begin_drag") as drag:
            view._begin_window_drag(top)
            drag.assert_not_called()
            view._begin_window_drag(SimpleNamespace(x_root=right - 200, y_root=top.y_root + 15))
            drag.assert_called_once()

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
            self.assertFalse(self.settings_window._save())
        # Updating the status also cancels pending scrollbar synchronization.
        cancel.assert_any_call("stale-success")
        self.assertIsNone(self.settings_window._save_feedback_after_id)
        self.assertTrue(self.settings_window._save_failed)
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
