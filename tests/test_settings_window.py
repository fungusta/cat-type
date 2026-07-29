from __future__ import annotations

import tkinter as tk
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cat_settings import AppSettings
from settings_window import SettingsWindow


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

    def test_center_reduces_minimum_when_screen_is_too_small(self) -> None:
        settings_window = SettingsWindow.__new__(SettingsWindow)
        window = Mock()
        window.winfo_width.return_value = 920
        window.winfo_height.return_value = 800
        window.winfo_screenwidth.return_value = 640
        window.winfo_screenheight.return_value = 480
        window.maxsize.return_value = (625, 450)
        settings_window.window = window

        settings_window._center()

        window.minsize.assert_called_once_with(600, 400)
        window.geometry.assert_called_once_with("600x400+20+24")


class SettingsWindowCiTests(unittest.TestCase):
    def test_cross_platform_workflows_run_settings_window_tests(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        for workflow_path in (
            project_root / ".github/workflows/build.yml",
            project_root / ".github/workflows/release.yml",
        ):
            with self.subTest(workflow=workflow_path):
                workflow = workflow_path.read_text(encoding="utf-8")
                self.assertIn("tests.test_settings_window", workflow)


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


class SettingsWindowTkLayoutTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk display is unavailable: {error}")
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.settings_window = SettingsWindow(
            self.root,
            AppSettings(),
            lambda _settings: None,
        )
        self.addCleanup(self.settings_window.close)

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
