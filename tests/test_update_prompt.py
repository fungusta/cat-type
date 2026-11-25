"""Widget tests for the Sparkle-style macOS update prompt."""

from __future__ import annotations

import tkinter as tk
import unittest
from unittest.mock import Mock

from auto_update import AvailableUpdate, ReleaseAsset


def update() -> AvailableUpdate:
    return AvailableUpdate(
        version="1.1.0",
        tag_name="v1.1.0",
        html_url="https://example.test/releases/v1.1.0",
        package=ReleaseAsset(
            "Cat-Type-macOS-arm64.dmg", "https://example.test/a.dmg", 100
        ),
        checksums=ReleaseAsset(
            "SHA256SUMS.txt", "https://example.test/SHA256SUMS.txt", 80
        ),
    )


class MacUpdatePromptTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as error:  # pragma: no cover - headless without Tk
            self.skipTest(f"Tk is unavailable: {error}")
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.on_choice = Mock()
        self.on_cancel = Mock()
        self.on_download_manually = Mock()
        self.on_activate = Mock()
        self.on_closed = Mock()

    def prompt(self, *, take_focus: bool = True):
        from update_prompt import MacUpdatePrompt

        prompt = MacUpdatePrompt(
            self.root,
            update(),
            "1.0.60",
            take_focus=take_focus,
            on_choice=self.on_choice,
            on_cancel=self.on_cancel,
            on_download_manually=self.on_download_manually,
            on_activate=self.on_activate,
            on_closed=self.on_closed,
        )
        self.root.update_idletasks()
        return prompt

    def key(self, prompt, sequence: str) -> None:
        """Deliver a key regardless of OS focus, so tests check the prompt's gating."""
        prompt.window.focus_force()
        self.root.update()
        prompt.window.event_generate(sequence, when="now")
        self.root.update()

    def test_prompt_copy_and_button_order(self) -> None:
        prompt = self.prompt()

        self.assertEqual(
            prompt.window.title(), "A new version of Cat Type is available"
        )
        self.assertEqual(
            prompt.message_text(), "Cat Type 1.1.0 is available — you have 1.0.60."
        )
        self.assertEqual(
            prompt.visible_buttons(),
            ["Skip This Version", "Remind Me Later", "Install Update"],
        )
        self.assertEqual(prompt.default_button(), "Install Update")

    def test_buttons_report_their_choice(self) -> None:
        for label, choice in (
            ("Install Update", "install"),
            ("Remind Me Later", "later"),
            ("Skip This Version", "skip"),
        ):
            with self.subTest(label=label):
                self.on_choice.reset_mock()
                prompt = self.prompt()
                prompt.press(label)
                self.on_choice.assert_called_once_with(choice)
                prompt.close()

    def test_escape_and_close_mean_later(self) -> None:
        prompt = self.prompt()
        self.key(prompt, "<Escape>")
        self.on_choice.assert_called_once_with("later")

        self.on_choice.reset_mock()
        second = self.prompt()
        second.request_close()
        self.on_choice.assert_called_once_with("later")

    def test_return_ignored_until_clicked_when_not_focused(self) -> None:
        prompt = self.prompt(take_focus=False)

        self.key(prompt, "<Return>")
        self.key(prompt, "<Escape>")
        self.on_choice.assert_not_called()
        self.on_activate.assert_not_called()

        prompt.window.event_generate("<Button-1>", x=5, y=5)
        self.root.update()
        self.on_activate.assert_called_once_with()
        self.key(prompt, "<Return>")
        self.on_choice.assert_called_once_with("install")

    def test_focused_prompt_accepts_return_immediately(self) -> None:
        prompt = self.prompt(take_focus=True)

        self.key(prompt, "<Return>")

        self.on_choice.assert_called_once_with("install")

    def test_cancel_only_visible_while_downloading(self) -> None:
        prompt = self.prompt()

        prompt.show_progress("Downloading update… 0%", 0.0)
        self.assertEqual(prompt.visible_buttons(), ["Cancel"])
        self.assertEqual(prompt.message_text(), "Downloading update… 0%")
        prompt.press("Cancel")
        self.on_cancel.assert_called_once_with()

        prompt.show_progress("Verifying Cat Type 1.1.0…", None)
        self.assertEqual(prompt.visible_buttons(), [])
        self.assertEqual(prompt.message_text(), "Verifying Cat Type 1.1.0…")

    def test_progress_window_ignores_return(self) -> None:
        prompt = self.prompt()
        prompt.show_progress("Downloading update… 0%", 0.0)

        self.key(prompt, "<Return>")

        self.on_choice.assert_not_called()

    def test_failure_state_shows_download_manually_and_close(self) -> None:
        prompt = self.prompt()
        prompt.show_progress("Downloading update… 0%", 0.0)

        prompt.show_error("package checksum does not match SHA256SUMS.txt")

        self.assertEqual(prompt.visible_buttons(), ["Download Manually", "Close"])
        self.assertIn("package checksum does not match", prompt.message_text())
        prompt.press("Download Manually")
        self.on_download_manually.assert_called_once_with()
        prompt.press("Close")
        self.on_closed.assert_called_once_with()
        self.on_choice.assert_not_called()

    def test_close_is_idempotent_and_reports_once(self) -> None:
        prompt = self.prompt()

        prompt.close()
        prompt.close()

        self.on_closed.assert_called_once_with()
        self.assertFalse(prompt.is_open())


if __name__ == "__main__":
    unittest.main()
