from __future__ import annotations

import tkinter as tk
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app_version import APP_VERSION
from cat_settings import AppSettings
from settings_window import CatScale, SettingsWindow
from usage_metrics import UsageMetrics


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
        self.on_save = Mock()
        self.on_metrics_view_change = Mock()
        self.on_check_for_updates = Mock()
        self.on_open_release_page = Mock()
        self.settings_window = SettingsWindow(
            self.root,
            AppSettings(),
            self.on_save,
            keystroke_count=1_234,
            on_metrics_view_change=self.on_metrics_view_change,
            on_check_for_updates=self.on_check_for_updates,
            on_open_release_page=self.on_open_release_page,
            update_status="Ready to check.",
        )
        self.addCleanup(self.settings_window.close)

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

    def test_settings_uses_only_functional_copy_and_starts_with_switcher(
        self,
    ) -> None:
        texts = self._widget_texts(self.settings_window.window)
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
            "Companion",
            "Cat style",
            "Cat size",
            "Timing",
            "Updates",
            "Activity",
            "Above · right",
            "All time",
            "All-time keystrokes",
            "Cancel",
            "Check for updates",
            "Columns",
            "Favorite spot",
            "Ginger tabby",
            "Gray tabby",
            "Hang around",
            "Last 7 days",
            "Line",
            "Mix it up",
            "Open release page",
            "Preview scale",
            "Range",
            "Ready to check.",
            "Show my cat while I type",
            "Soft fade",
            "Start Cat Type when I sign in",
            "Save changes",
            "Today",
            f"Version {APP_VERSION}",
            "View",
            "keystrokes",
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
            self.settings_window.PEACH,
        )

        self.settings_window.metrics_range_days.set(30)
        self.settings_window._change_metrics_range()

        self.assertEqual(self.settings_window.metrics_range_days.get(), 30)
        self.assertEqual(
            self.settings_window.metrics_range_buttons[30].cget("background"),
            self.settings_window.PEACH,
        )

    def test_metrics_view_switches_without_resetting_range(self) -> None:
        today = datetime.now().astimezone().date()
        self.settings_window.update_usage_metrics(
            UsageMetrics(
                total_keystrokes=30,
                daily={today.isoformat(): 30},
                hourly={f"{today.isoformat()}T09": 30},
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
        self.on_metrics_view_change.assert_not_called()

        self.settings_window.metrics_range_days.set(1)
        self.settings_window.metrics_view.set("columns")
        self.settings_window._change_metrics_view()

        self.assertEqual(self.settings_window.metrics_range_days.get(), 1)
        self.on_metrics_view_change.assert_called_once_with("columns")
        self.assertTrue(
            self.settings_window.metrics_chart.find_withtag("metric-column")
        )
        self.assertFalse(
            self.settings_window.metrics_chart.find_withtag("metric-line")
        )

        self.settings_window.metrics_range_days.set(30)
        self.settings_window._change_metrics_range()

        self.assertEqual(self.settings_window.metrics_view.get(), "columns")
        self.on_metrics_view_change.assert_called_once_with("columns")

    def test_columns_cover_every_bucket_with_exact_scaled_bounds(self) -> None:
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

        for days, expected_count in ((1, 24), (7, 7), (30, 30)):
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
                expected_positions = SettingsWindow._metric_column_positions(
                    values,
                    width,
                    height,
                    left=46,
                    right=14,
                    top=24,
                    bottom=34,
                )
                expected_width = max(
                    3,
                    min(22, ((width - 46 - 14) / expected_count) * 0.56),
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

        for days, expected_count in ((1, 24), (7, 7), (30, 30)):
            with self.subTest(days=days):
                self.settings_window.metrics_range_days.set(days)
                self.settings_window.metrics_view.set("line")
                self.settings_window._draw_metrics()
                line_id = canvas.find_withtag("metric-line")[0]
                line_coordinates = canvas.coords(line_id)
                line_points = list(
                    zip(line_coordinates[::2], line_coordinates[1::2])
                )
                marker_centers = []
                for marker_id in canvas.find_withtag("metric-point"):
                    x0, y0, x1, y1 = canvas.coords(marker_id)
                    marker_centers.append(((x0 + x1) / 2, (y0 + y1) / 2))

                self.assertEqual(len(line_points), expected_count)
                self.assertEqual(marker_centers, line_points)

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

                    updated = UsageMetrics(
                        total_keystrokes=9,
                        daily={today.isoformat(): 9},
                        hourly={f"{today.isoformat()}T09": 9},
                    )
                    self.settings_window.update_usage_metrics(updated)
                    self.assertEqual(
                        self.settings_window.metrics_range_days.get(),
                        days,
                    )
                    self.assertEqual(self.settings_window.metrics_view.get(), view)
                    self.assertTrue(
                        canvas.find_withtag(
                            "metric-line" if view == "line" else "metric-column"
                        )
                    )

            self.assertEqual(texts_by_view["line"], texts_by_view["columns"])

    def test_saved_metrics_view_is_restored_and_included_on_save(self) -> None:
        on_save = Mock()
        on_metrics_view_change = Mock()
        saved_window = SettingsWindow(
            self.root,
            AppSettings(metrics_view="columns"),
            on_save,
            on_metrics_view_change=on_metrics_view_change,
        )
        self.addCleanup(saved_window.close)

        self.assertEqual(saved_window.metrics_view.get(), "columns")
        self.assertEqual(
            saved_window.metrics_view_buttons["columns"].cget("background"),
            saved_window.PEACH,
        )
        on_metrics_view_change.assert_not_called()

        saved_window._save()

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

        self.assertFalse(hasattr(self.settings_window, "footer_message"))
        self.assertFalse(hasattr(self.settings_window, "_on_footer_configure"))

    def test_narrow_layout_stacks_cards_and_keeps_preview_visible(self) -> None:
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
        self.assertTrue(self.settings_window.preview_canvas.winfo_ismapped())
        self.assertFalse(hasattr(self.settings_window, "hero_headline"))

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
                    [title],
                )
                self.assertEqual(copy.winfo_reqheight(), labels[0].winfo_reqheight())
                self.assertTrue(bool(int(toggle.cget("takefocus"))))

                value_before = variable.get()
                toggle.focus_force()
                self.settings_window.window.update()
                toggle.event_generate("<space>")
                self.settings_window.window.update()

                self.assertEqual(variable.get(), not value_before)

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
