from __future__ import annotations

import tkinter as tk
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app_version import APP_VERSION
from cat_settings import AppSettings
from settings_window import CatScale, SettingsWindow


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


class SettingsWindowTkLayoutTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk display is unavailable: {error}")
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.on_check_for_updates = Mock()
        self.on_open_release_page = Mock()
        self.settings_window = SettingsWindow(
            self.root,
            AppSettings(),
            lambda _settings: None,
            keystroke_count=1_234,
            on_check_for_updates=self.on_check_for_updates,
            on_open_release_page=self.on_open_release_page,
            update_status="Ready to check.",
        )
        self.addCleanup(self.settings_window.close)

    def test_updates_card_shows_version_status_and_invokes_callback_once(
        self,
    ) -> None:
        self.assertEqual(
            self.settings_window.update_version_label.cget("text"),
            f"Version {APP_VERSION}",
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

    def test_session_keystroke_counter_is_visible_and_updates_live(self) -> None:
        self.assertEqual(
            self.settings_window.keystroke_count_title.cget("text"),
            "Keystrokes this session",
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
        buttons = self.settings_window.footer_buttons.winfo_children()

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

        required_width = (
            self.settings_window.footer_message.winfo_reqwidth()
            + self.settings_window.footer_buttons.winfo_reqwidth()
        )
        self.settings_window._on_footer_configure(
            SimpleNamespace(width=required_width - 1)
        )
        self.assertFalse(self.settings_window.footer_message.winfo_ismapped())

    def test_narrow_layout_stacks_cards_without_clipping_the_header(self) -> None:
        self.settings_window.window.geometry("700x480")
        self.settings_window.window.update()

        self.assertEqual(self.settings_window._layout_mode, "narrow")
        self.assertEqual(
            int(self.settings_window.left_column.grid_info()["row"]),
            0,
        )
        self.assertEqual(
            int(self.settings_window.right_column.grid_info()["row"]),
            1,
        )
        self.assertEqual(
            int(self.settings_window.right_column.grid_info()["column"]),
            0,
        )
        self.assertFalse(self.settings_window.preview_canvas.winfo_ismapped())
        self.assertEqual(
            self.settings_window.hero_headline.winfo_width(),
            self.settings_window.hero_headline.winfo_reqwidth(),
        )

    def test_wide_layout_keeps_the_preview_and_two_columns(self) -> None:
        self.settings_window.window.geometry("920x800")
        self.settings_window.window.update()

        self.assertEqual(self.settings_window._layout_mode, "wide")
        self.assertEqual(
            int(self.settings_window.right_column.grid_info()["row"]),
            0,
        )
        self.assertEqual(
            int(self.settings_window.right_column.grid_info()["column"]),
            1,
        )
        self.assertTrue(self.settings_window.preview_canvas.winfo_ismapped())

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

    def test_custom_toggles_are_keyboard_focusable(self) -> None:
        enabled_before = self.settings_window.enabled.get()

        self.assertTrue(
            bool(int(self.settings_window.enabled_toggle.cget("takefocus")))
        )
        self.settings_window.enabled_toggle.focus_force()
        self.settings_window.window.update()
        self.settings_window.enabled_toggle.event_generate("<space>")
        self.settings_window.window.update()

        self.assertEqual(
            self.settings_window.enabled.get(),
            not enabled_before,
        )

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
                    self.settings_window.ACCENT
                    if label == "Ginger tabby"
                    else self.settings_window.BORDER
                )
                self.assertEqual(button.cget("highlightbackground"), expected)
                self.assertEqual(button.winfo_reqwidth(), widths_before[label])

    def test_footer_actions_use_settings_language(self) -> None:
        self.assertEqual(self.settings_window.cancel_button.cget("text"), "Cancel")
        self.assertEqual(
            self.settings_window.save_button.cget("text"),
            "Save changes",
        )
