"""Sparkle-style update prompt and progress window for macOS."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Callable, Literal, Protocol

if TYPE_CHECKING:
    from auto_update import AvailableUpdate


UpdateChoice = Literal["install", "skip", "later"]

TITLE = "A new version of Cat Type is available"
INSTALL = "Install Update"
LATER = "Remind Me Later"
SKIP = "Skip This Version"
CANCEL = "Cancel"
DOWNLOAD_MANUALLY = "Download Manually"
CLOSE = "Close"

BACKGROUND = "#FFF9F3"
INK = "#302A33"
MUTED = "#575059"
ACCENT = "#F2D66B"
PEACH = "#FFF1B8"
CARD = "#FFFFFF"
BLUSH = "#FAF7F2"
TRACK = "#ECE5DE"

BUTTON_STYLE = "CatUpdate.TButton"
ACCENT_STYLE = "CatUpdate.Accent.TButton"
PROGRESS_STYLE = "CatUpdate.Horizontal.TProgressbar"


class UpdatePromptView(Protocol):
    def show_progress(self, text: str, fraction: float | None) -> None: ...

    def show_error(self, message: str) -> None: ...

    def bring_to_front(self, take_focus: bool) -> None: ...

    def close(self) -> None: ...


class MacUpdatePrompt:
    """A non-modal prompt that becomes the install progress and error window.

    When ``take_focus`` is false the window appears without taking keyboard
    focus and ignores keys until the user clicks it, so typing in another app
    can never answer it.
    """

    def __init__(
        self,
        root: tk.Misc,
        update: AvailableUpdate,
        current_version: str,
        *,
        take_focus: bool,
        on_choice: Callable[[UpdateChoice], None],
        on_cancel: Callable[[], None],
        on_download_manually: Callable[[], None],
        on_activate: Callable[[], None] | None = None,
        on_closed: Callable[[], None] | None = None,
    ) -> None:
        self._on_choice = on_choice
        self._on_cancel = on_cancel
        self._on_download_manually = on_download_manually
        self._on_activate = on_activate or (lambda: None)
        self._on_closed = on_closed or (lambda: None)
        self._accepts_keys = take_focus
        self._state: Literal["offer", "progress", "error"] = "offer"
        self._open = True

        self.window = tk.Toplevel(root)
        self.window.withdraw()
        self.window.title(TITLE)
        self.window.configure(background=BACKGROUND, padx=24, pady=20)
        self.window.resizable(False, False)
        self.window.attributes("-topmost", True)
        self.window.protocol("WM_DELETE_WINDOW", self.request_close)
        self._configure_styles()

        self._heading = tk.Label(
            self.window,
            text=TITLE,
            background=BACKGROUND,
            foreground=INK,
            font=("TkDefaultFont", 14, "bold"),
            anchor="w",
            justify="left",
        )
        self._heading.pack(fill="x")
        self._message = tk.StringVar(
            master=self.window,
            value=f"Cat Type {update.version} is available — you have {current_version}.",
        )
        tk.Label(
            self.window,
            textvariable=self._message,
            background=BACKGROUND,
            foreground=MUTED,
            anchor="w",
            justify="left",
            wraplength=380,
        ).pack(fill="x", pady=(8, 14))
        self._progress = ttk.Progressbar(
            self.window,
            style=PROGRESS_STYLE,
            mode="determinate",
            maximum=1.0,
            length=380,
        )
        self._buttons_frame = tk.Frame(self.window, background=BACKGROUND)
        self._buttons_frame.pack(fill="x")
        self._buttons: dict[str, ttk.Button] = {}
        self._visible: list[str] = []
        self._default: str | None = None
        for label, command in (
            (SKIP, lambda: self._choose("skip")),
            (LATER, lambda: self._choose("later")),
            (INSTALL, lambda: self._choose("install")),
            (CANCEL, self._cancel),
            (DOWNLOAD_MANUALLY, self._on_download_manually),
            (CLOSE, self.close),
        ):
            self._buttons[label] = ttk.Button(
                self._buttons_frame,
                text=label,
                style=ACCENT_STYLE if label in {INSTALL, DOWNLOAD_MANUALLY} else BUTTON_STYLE,
                command=command,
                takefocus=False,
            )
        self._show_buttons([SKIP, LATER, INSTALL], default=INSTALL)

        self.window.bind("<Return>", self._on_return)
        self.window.bind("<KP_Enter>", self._on_return)
        self.window.bind("<Escape>", self._on_escape)
        self.window.bind("<Button-1>", self._on_click, add="+")

        self.window.deiconify()
        self.window.lift()
        if take_focus:
            self.window.focus_force()

    def _configure_styles(self) -> None:
        style = ttk.Style(self.window)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        for name, background in ((BUTTON_STYLE, CARD), (ACCENT_STYLE, ACCENT)):
            style.configure(
                name,
                background=background,
                foreground=INK,
                bordercolor=INK,
                lightcolor=background,
                darkcolor=INK,
                padding=(14, 8),
                relief="raised",
                borderwidth=2,
            )
            style.map(
                name,
                background=[("active", PEACH), ("pressed", BLUSH)],
                relief=[("pressed", "sunken"), ("!pressed", "raised")],
            )
        style.configure(
            PROGRESS_STYLE,
            troughcolor=TRACK,
            background=ACCENT,
            bordercolor=TRACK,
            lightcolor=ACCENT,
            darkcolor=ACCENT,
        )

    def _show_buttons(self, labels: list[str], *, default: str | None) -> None:
        for button in self._buttons.values():
            button.pack_forget()
        for label in reversed(labels):
            self._buttons[label].pack(side="right", padx=(8, 0))
        self._visible = list(labels)
        self._default = default

    def _choose(self, choice: UpdateChoice) -> None:
        if self._open and self._state == "offer":
            self._on_choice(choice)

    def _cancel(self) -> None:
        if self._open and CANCEL in self._visible:
            self._on_cancel()

    def _on_return(self, _event: object = None) -> str:
        if self._accepts_keys and self._state == "offer":
            self._choose("install")
        return "break"

    def _on_escape(self, _event: object = None) -> str:
        if self._accepts_keys:
            if self._state == "offer":
                self._choose("later")
            elif self._state == "error":
                self.close()
        return "break"

    def _on_click(self, _event: object = None) -> None:
        if not self._accepts_keys and self._open:
            self._accepts_keys = True
            self._on_activate()
            try:
                self.window.focus_force()
            except tk.TclError:
                pass

    def request_close(self) -> None:
        """Handle the window's close button like Sparkle's dismiss actions."""
        if self._state == "offer":
            self._choose("later")
        elif self._state == "error":
            self.close()
        elif CANCEL in self._visible:
            self._cancel()

    def show_progress(self, text: str, fraction: float | None) -> None:
        if not self._open:
            return
        self._state = "progress"
        self._message.set(text)
        if not self._progress.winfo_ismapped():
            self._progress.pack(before=self._buttons_frame, fill="x", pady=(0, 14))
        if fraction is None:
            if str(self._progress.cget("mode")) != "indeterminate":
                self._progress.configure(mode="indeterminate")
                self._progress.start(15)
            self._show_buttons([], default=None)
        else:
            if str(self._progress.cget("mode")) != "determinate":
                self._progress.stop()
                self._progress.configure(mode="determinate")
            self._progress.configure(value=max(0.0, min(1.0, fraction)))
            self._show_buttons([CANCEL], default=None)

    def show_error(self, message: str) -> None:
        if not self._open:
            return
        self._state = "error"
        self._progress.stop()
        self._progress.pack_forget()
        self._heading.configure(text="Cat Type couldn't be updated")
        self._message.set(message)
        self._show_buttons([DOWNLOAD_MANUALLY, CLOSE], default=DOWNLOAD_MANUALLY)

    def bring_to_front(self, take_focus: bool) -> None:
        if not self._open:
            return
        self.window.deiconify()
        self.window.lift()
        if take_focus:
            self._accepts_keys = True
            self._on_activate()
            self.window.focus_force()

    def close(self) -> None:
        if not self._open:
            return
        self._open = False
        try:
            self._progress.stop()
            self.window.destroy()
        except tk.TclError:
            pass
        self._on_closed()

    # Introspection used by tests and accessibility checks.
    def is_open(self) -> bool:
        return self._open

    def message_text(self) -> str:
        return self._message.get()

    def visible_buttons(self) -> list[str]:
        return list(self._visible)

    def default_button(self) -> str | None:
        return self._default

    def press(self, label: str) -> None:
        if label not in self._visible:
            raise ValueError(f"{label!r} is not visible")
        self._buttons[label].invoke()
