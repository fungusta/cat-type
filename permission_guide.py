"""A guided, three-step window for turning on macOS Input Monitoring.

macOS only lets Cat Type hear key presses once the person switches it on in
System Settings. Like the setup windows of other keyboard utilities, this
window explains why before asking, shows exactly which switch to flip, opens
the right System Settings pane, and notices on its own when access arrives.
"""

from __future__ import annotations

import sys
import tkinter as tk
from collections.abc import Callable
from tkinter import font as tkfont
from typing import Literal

from PIL import Image, ImageDraw, ImageTk

from help_links import (  # re-exported for existing callers
    HELP_URL,
    INPUT_MONITORING_HELP_URL,
    SECURE_KEYBOARD_ENTRY_HELP_URL,
)
from ui_surfaces import (
    BUTTON_ACCENT,
    BUTTON_INK,
    RoundedAction,
    blend,
    prefers_reduced_motion,
)


Stage = Literal["start", "waiting", "granted"]
StepState = Literal["todo", "current", "done"]

STEPS: tuple[tuple[str, str], ...] = (
    (
        "Open System Settings",
        "Cat Type takes you straight to Privacy & Security › Input Monitoring. "
        "If macOS shows a popup first, choose Open System Settings.",
    ),
    (
        "Switch on Cat Type",
        "Turn on the switch next to Cat Type. Not in the list? Click +, "
        "then choose Cat Type from Applications.",
    ),
    (
        "Come back to your cat",
        "If macOS offers Quit & Reopen, choose it. Cat Type opens again by itself.",
    ),
)

STATUS_COPY: dict[Stage, str] = {
    "start": "Cat Type counts key presses. It never sees what you type.",
    "waiting": "Waiting for Cat Type to be switched on",
    "granted": "All set. Your cat can see you type now.",
}

PRIMARY_LABELS: dict[Stage, str] = {
    "start": "Open System Settings",
    "waiting": "Open System Settings Again",
    "granted": "Done",
}


def guide_stage(*, granted: bool, opened: bool) -> Stage:
    if granted:
        return "granted"
    return "waiting" if opened else "start"


def step_states(stage: Stage) -> tuple[StepState, ...]:
    if stage == "granted":
        return ("done", "done", "done")
    if stage == "waiting":
        return ("done", "current", "todo")
    return ("current", "todo", "todo")


def _pick_fonts(window: tk.Misc) -> dict[str, tkfont.Font]:
    available = set(tkfont.families(window))

    def pick(*families: str) -> str:
        return next((family for family in families if family in available), "TkDefaultFont")

    display = pick("Segoe UI Variable Display Semib", "Avenir Next Demi Bold", "Segoe UI Semibold")
    strong = pick("Segoe UI Variable Text Semibold", "Avenir Next Medium", "Segoe UI Semibold")
    body = pick("Segoe UI Variable Text", "Avenir Next", "Helvetica Neue", "Segoe UI", "Arial")

    def face(family: str, size: int) -> tkfont.Font:
        weight = "bold" if family == "TkDefaultFont" else "normal"
        return tkfont.Font(window, family=family, size=size, weight=weight)

    return {
        "title": face(display, 20),
        "step": face(strong, 12),
        "body": tkfont.Font(window, family=body, size=11),
        "small": tkfont.Font(window, family=body, size=10),
        "mark": face(strong, 11),
    }


class SettingsIllustration(tk.Canvas):
    """A small picture of the System Settings row to look for.

    The switch beside Cat Type flips on and off until access is granted, so the
    person knows exactly which control to use before they leave the window.
    """

    WIDTH = 412
    HEIGHT = 134
    _SCALE = 3
    _BLUE = "#0A84FF"
    _OFF = "#D9D4CE"
    _ROW = "#F6F3EF"

    def __init__(
        self,
        parent: tk.Misc,
        *,
        background: str,
        icon_path: str | None,
        fonts: dict[str, tkfont.Font],
    ) -> None:
        super().__init__(
            parent,
            width=self.WIDTH,
            height=self.HEIGHT,
            background=background,
            highlightthickness=0,
            borderwidth=0,
        )
        self._surface = background
        self._fonts = fonts
        self._frames: dict[int, ImageTk.PhotoImage] = {}
        self._icon: ImageTk.PhotoImage | None = None
        if icon_path:
            try:
                with Image.open(icon_path) as source:
                    self._icon = ImageTk.PhotoImage(
                        source.convert("RGBA").resize((24, 24), Image.Resampling.LANCZOS),
                        master=self,
                    )
            except (OSError, ValueError):
                self._icon = None
        self._position = 0.0
        self._animating = False
        self._after_id: str | None = None
        self._phase = 0
        self._image_id = self.create_image(0, 0, anchor="nw")
        self._draw_labels()
        self.set_switch(0.0)
        self.bind("<Destroy>", lambda _event: self.stop(), add="+")

    def _toggle_box(self) -> tuple[int, int, int, int]:
        return (self.WIDTH - 72, 70, self.WIDTH - 30, 94)

    def _render(self, position: float) -> Image.Image:
        s = self._SCALE
        image = Image.new("RGB", (self.WIDTH * s, self.HEIGHT * s), self._surface)
        pen = ImageDraw.Draw(image)
        pen.rounded_rectangle(
            (1 * s, 1 * s, (self.WIDTH - 2) * s, (self.HEIGHT - 2) * s),
            radius=14 * s,
            fill="#FFFFFF",
            outline="#E8E1DA",
            width=s,
        )
        for index, color in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
            cx, cy = (18 + index * 16) * s, 16 * s
            pen.ellipse((cx - 5 * s, cy - 5 * s, cx + 5 * s, cy + 5 * s), fill=color)
        pen.line((1 * s, 32 * s, (self.WIDTH - 2) * s, 32 * s), fill="#F1ECE7", width=s)
        pen.rounded_rectangle(
            (16 * s, 60 * s, (self.WIDTH - 16) * s, 104 * s),
            radius=10 * s,
            fill=self._ROW,
        )
        # The + and − buttons under the list, for when Cat Type is missing.
        pen.rounded_rectangle(
            (16 * s, 110 * s, 66 * s, 128 * s),
            radius=5 * s,
            fill="#FFFFFF",
            outline="#E2D9D0",
            width=s,
        )
        pen.line((41 * s, 112 * s, 41 * s, 126 * s), fill="#E2D9D0", width=s)
        x1, y1, x2, y2 = self._toggle_box()
        halo = 5
        pen.rounded_rectangle(
            ((x1 - halo) * s, (y1 - halo) * s, (x2 + halo) * s, (y2 + halo) * s),
            radius=(y2 - y1 + 2 * halo) // 2 * s,
            outline=BUTTON_ACCENT,
            width=3 * s,
        )
        pen.rounded_rectangle(
            (x1 * s, y1 * s, x2 * s, y2 * s),
            radius=(y2 - y1) // 2 * s,
            fill=blend(self._OFF, self._BLUE, position),
        )
        knob = y2 - y1 - 4
        left = x1 + 2 + (x2 - x1 - 4 - knob) * position
        pen.ellipse(
            (left * s, (y1 + 2) * s, (left + knob) * s, (y1 + 2 + knob) * s),
            fill="#FFFFFF",
            outline="#CFC8C1",
            width=max(1, s // 2),
        )
        # A pointer resting on the switch.
        tip_x, tip_y = x2 - 8, y2 - 4
        arrow = [(0, 0), (0, 17), (4.5, 13), (7.5, 20), (10, 19), (7, 12), (13, 12)]
        pen.polygon(
            [((tip_x + dx) * s, (tip_y + dy) * s) for dx, dy in arrow],
            fill=BUTTON_INK,
            outline="#FFFFFF",
        )
        return image.resize((self.WIDTH, self.HEIGHT), Image.Resampling.LANCZOS)

    def _draw_labels(self) -> None:
        self.create_text(66, 16, text="‹  Input Monitoring", anchor="w",
                         fill=BUTTON_INK, font=self._fonts["step"])
        self.create_text(18, 46, text="Allow the apps below to monitor input from your keyboard.",
                         anchor="w", fill="#6E6770", font=self._fonts["small"])
        if self._icon is not None:
            self.create_image(28, 82, anchor="w", image=self._icon)
        self.create_text(60 if self._icon is not None else 30, 82, text="Cat Type", anchor="w",
                         fill=BUTTON_INK, font=self._fonts["step"])
        self.create_text(28, 119, text="+", fill=BUTTON_INK, font=self._fonts["mark"])
        self.create_text(54, 119, text="−", fill=BUTTON_INK, font=self._fonts["mark"])

    def set_switch(self, position: float) -> None:
        self._position = max(0.0, min(1.0, position))
        key = round(self._position * 8)
        frame = self._frames.get(key)
        if frame is None:
            frame = ImageTk.PhotoImage(self._render(key / 8), master=self)
            self._frames[key] = frame
        self.itemconfigure(self._image_id, image=frame)
        self.tag_lower(self._image_id)

    def animate(self) -> None:
        if self._animating:
            return
        if prefers_reduced_motion():
            self.set_switch(1.0)
            return
        self._animating = True
        self._phase = 0
        self._step()

    def _step(self) -> None:
        self._after_id = None
        if not self._animating:
            return
        # 0–11 off, 12–19 slide on, 20–43 hold on, 44–51 slide off.
        phase = self._phase % 52
        if phase < 12:
            position = 0.0
        elif phase < 20:
            position = (phase - 12) / 8
        elif phase < 44:
            position = 1.0
        else:
            position = 1 - (phase - 44) / 8
        self.set_switch(position)
        self._phase += 1
        self._after_id = self.after(40 if 12 <= phase < 20 or phase >= 44 else 70, self._step)

    def stop(self, *, position: float | None = None) -> None:
        self._animating = False
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        if position is not None:
            self.set_switch(position)


class PermissionGuideWindow:
    BACKGROUND = "#FFF9F3"
    CARD = "#FFFFFF"
    INK = "#302A33"
    MUTED = "#575059"
    BLUSH = "#FAF7F2"
    BORDER = "#E8E1DA"
    TODO = "#F3EFEA"
    WIDTH = 460

    def __init__(
        self,
        root: tk.Misc,
        *,
        granted: bool,
        opened: bool,
        on_open_settings: Callable[[], object],
        on_help: Callable[[], object],
        on_close: Callable[[], object],
        icon_path: str | None = None,
    ) -> None:
        self._on_open_settings = on_open_settings
        self._on_help = on_help
        self._on_close = on_close
        self._dots = 0
        self._dots_after_id: str | None = None
        self.window = tk.Toplevel(root)
        self.window.withdraw()
        self.window.title("Set Up Cat Type")
        self.window.configure(background=self.BACKGROUND)
        self.window.resizable(False, False)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.bind("<Escape>", lambda _event: self.close())
        self.fonts = _pick_fonts(self.window)
        self.stage: Stage = guide_stage(granted=granted, opened=opened)
        self._build(icon_path)
        self._apply_stage(self.stage)
        self._center()
        self.show()

    def _build(self, icon_path: str | None) -> None:
        body = tk.Frame(self.window, background=self.BACKGROUND)
        body.pack(fill="both", expand=True, padx=24, pady=(22, 20))
        wrap = self.WIDTH - 48

        tk.Label(
            body,
            text="Let your cat see you type",
            background=self.BACKGROUND,
            foreground=self.INK,
            font=self.fonts["title"],
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            body,
            text=(
                "macOS asks you to allow Input Monitoring before any app can "
                "notice key presses. It takes three quick steps."
            ),
            background=self.BACKGROUND,
            foreground=self.MUTED,
            font=self.fonts["body"],
            justify="left",
            anchor="w",
            wraplength=wrap,
        ).pack(fill="x", pady=(4, 14))

        self.illustration = SettingsIllustration(
            body,
            background=self.BACKGROUND,
            icon_path=icon_path,
            fonts=self.fonts,
        )
        self.illustration.pack(anchor="w")

        steps = tk.Frame(body, background=self.BACKGROUND)
        steps.pack(fill="x", pady=(16, 4))
        self.step_marks: list[tk.Canvas] = []
        self.step_titles: list[tk.Label] = []
        self.step_details: list[tk.Label] = []
        for title, detail in STEPS:
            row = tk.Frame(steps, background=self.BACKGROUND)
            row.pack(fill="x", pady=(0, 10))
            mark = tk.Canvas(row, width=26, height=26, background=self.BACKGROUND,
                             highlightthickness=0, borderwidth=0)
            mark.pack(side="left", anchor="n", padx=(0, 12))
            copy = tk.Frame(row, background=self.BACKGROUND)
            copy.pack(side="left", fill="x", expand=True)
            heading = tk.Label(copy, text=title, background=self.BACKGROUND, foreground=self.INK,
                               font=self.fonts["step"], anchor="w")
            heading.pack(fill="x")
            detail_label = tk.Label(copy, text=detail, background=self.BACKGROUND,
                                    foreground=self.MUTED, font=self.fonts["small"],
                                    justify="left", anchor="w", wraplength=wrap - 38)
            detail_label.pack(fill="x")
            self.step_marks.append(mark)
            self.step_titles.append(heading)
            self.step_details.append(detail_label)

        status = tk.Frame(body, background=self.BLUSH, highlightthickness=1,
                          highlightbackground=self.BORDER)
        status.pack(fill="x", pady=(4, 16))
        self.status_text = tk.StringVar(value="")
        self.status_label = tk.Label(status, textvariable=self.status_text, background=self.BLUSH,
                                     foreground=self.INK, font=self.fonts["small"],
                                     justify="left", anchor="w", wraplength=wrap - 24)
        self.status_label.pack(fill="x", padx=12, pady=9)

        actions = tk.Frame(body, background=self.BACKGROUND)
        actions.pack(fill="x")
        self.help_button = RoundedAction(actions, text="Having trouble?", command=self._on_help,
                                         style="Cat.TButton")
        self.help_button.pack(side="left")
        self.primary_button = RoundedAction(actions, text=PRIMARY_LABELS["start"],
                                            command=self._primary, style="Cat.Accent.TButton")
        self.primary_button.pack(side="right")
        self.later_button = RoundedAction(actions, text="Not Now", command=self.close,
                                          style="Cat.TButton")
        self.later_button.pack(side="right", padx=(0, 8))

    def _draw_mark(self, mark: tk.Canvas, number: int, state: StepState) -> None:
        mark.delete("all")
        if state == "done":
            mark.create_oval(1, 1, 25, 25, fill=BUTTON_ACCENT, outline=blend(BUTTON_ACCENT, "#7A5C2E", 0.25))
            mark.create_line(8, 13.5, 11.5, 17, 18.5, 9.5, fill=BUTTON_INK, width=2.4,
                             capstyle="round", joinstyle="round")
            return
        current = state == "current"
        mark.create_oval(1, 1, 25, 25, fill=self.INK if current else self.TODO,
                         outline=self.INK if current else self.BORDER)
        mark.create_text(13, 13, text=str(number),
                         fill="#FFFFFF" if current else self.MUTED, font=self.fonts["mark"])

    def _apply_stage(self, stage: Stage) -> None:
        self.stage = stage
        states = step_states(stage)
        for number, (mark, title, state) in enumerate(zip(self.step_marks, self.step_titles, states), 1):
            self._draw_mark(mark, number, state)
            title.configure(foreground=self.MUTED if state == "todo" else self.INK)
        self.primary_button.configure(text=PRIMARY_LABELS[stage])
        self.later_button.configure(text="Close" if stage == "granted" else "Not Now")
        if stage == "granted":
            self.later_button.pack_forget()
            self.illustration.stop(position=1.0)
        else:
            self.illustration.animate()
        self._cancel_dots()
        self.status_text.set(STATUS_COPY[stage])
        if stage == "waiting":
            self._tick_dots()

    def _tick_dots(self) -> None:
        self._dots_after_id = None
        if self.stage != "waiting":
            return
        self._dots = (self._dots % 3) + 1
        self.status_text.set(f"{STATUS_COPY['waiting']}{'.' * self._dots}")
        self._dots_after_id = self.window.after(500, self._tick_dots)

    def _cancel_dots(self) -> None:
        if self._dots_after_id is not None:
            try:
                self.window.after_cancel(self._dots_after_id)
            except tk.TclError:
                pass
            self._dots_after_id = None

    def _primary(self) -> None:
        if self.stage == "granted":
            self.close()
            return
        self._on_open_settings()

    def set_status(self, *, granted: bool, opened: bool) -> None:
        if not self.exists():
            return
        stage = guide_stage(granted=granted, opened=opened)
        if stage == self.stage:
            return
        self._apply_stage(stage)
        if stage == "granted":
            # The person is probably still in System Settings: bring the good
            # news to the front.
            self.show(activate=True)

    def _center(self) -> None:
        self.window.update_idletasks()
        width = max(self.WIDTH, self.window.winfo_reqwidth())
        height = self.window.winfo_reqheight()
        x = max(0, (self.window.winfo_screenwidth() - width) // 2)
        y = max(0, (self.window.winfo_screenheight() - height) // 3)
        self.window.geometry(f"{width}x{height}+{x}+{y}")

    def exists(self) -> bool:
        try:
            return bool(self.window.winfo_exists())
        except tk.TclError:
            return False

    def show(self, *, activate: bool = False) -> None:
        if not self.exists():
            return
        self.window.deiconify()
        self.window.lift()
        if activate:
            _activate_this_app()
        self.window.focus_force()

    def close(self) -> None:
        if not self.exists():
            return
        self._cancel_dots()
        self.illustration.stop()
        self.window.destroy()
        self._on_close()


def _activate_this_app() -> None:
    if sys.platform != "darwin":
        return
    try:
        from AppKit import NSApplication

        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
    except (AttributeError, ImportError, OSError):
        pass
