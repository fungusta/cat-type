from __future__ import annotations

import tkinter as tk
import unittest
from unittest.mock import Mock

from permission_guide import (
    INPUT_MONITORING_HELP_URL,
    PRIMARY_LABELS,
    STATUS_COPY,
    PermissionGuideWindow,
    guide_stage,
    step_states,
)


class PermissionGuideStateTests(unittest.TestCase):
    def test_stage_follows_access_and_whether_settings_were_opened(self) -> None:
        self.assertEqual(guide_stage(granted=False, opened=False), "start")
        self.assertEqual(guide_stage(granted=False, opened=True), "waiting")
        self.assertEqual(guide_stage(granted=True, opened=False), "granted")
        self.assertEqual(guide_stage(granted=True, opened=True), "granted")

    def test_exactly_one_step_is_current_until_everything_is_done(self) -> None:
        self.assertEqual(step_states("start"), ("current", "todo", "todo"))
        self.assertEqual(step_states("waiting"), ("done", "current", "todo"))
        self.assertEqual(step_states("granted"), ("done", "done", "done"))

    def test_help_link_points_at_the_input_monitoring_section(self) -> None:
        self.assertTrue(INPUT_MONITORING_HELP_URL.endswith("help.html#input-monitoring"))


class PermissionGuideWindowTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk display is unavailable: {error}")
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.open_settings = Mock()
        self.on_help = Mock()
        self.on_close = Mock()

    def guide(self, *, granted: bool = False, opened: bool = False) -> PermissionGuideWindow:
        guide = PermissionGuideWindow(
            self.root,
            granted=granted,
            opened=opened,
            on_open_settings=self.open_settings,
            on_help=self.on_help,
            on_close=self.on_close,
        )
        self.addCleanup(guide.close)
        return guide

    def test_primary_action_opens_system_settings_until_granted(self) -> None:
        guide = self.guide()
        self.assertEqual(guide.primary_button.cget("text"), PRIMARY_LABELS["start"])
        self.assertEqual(guide.status_text.get(), STATUS_COPY["start"])

        guide.primary_button.invoke()

        self.open_settings.assert_called_once_with()

    def test_waiting_then_granted_updates_steps_and_closes_on_done(self) -> None:
        guide = self.guide()
        guide.set_status(granted=False, opened=True)
        self.assertEqual(guide.stage, "waiting")
        self.assertEqual(guide.primary_button.cget("text"), PRIMARY_LABELS["waiting"])
        self.assertTrue(guide.status_text.get().startswith(STATUS_COPY["waiting"]))

        guide.set_status(granted=True, opened=True)
        self.assertEqual(guide.stage, "granted")
        self.assertEqual(guide.status_text.get(), STATUS_COPY["granted"])
        self.assertEqual(guide.later_button.winfo_manager(), "")

        guide.primary_button.invoke()

        self.open_settings.assert_not_called()
        self.on_close.assert_called_once_with()
        self.assertFalse(guide.exists())

    def test_help_and_not_now(self) -> None:
        guide = self.guide()
        guide.help_button.invoke()
        self.on_help.assert_called_once_with()

        guide.later_button.invoke()
        self.on_close.assert_called_once_with()
        guide.close()
        self.on_close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
