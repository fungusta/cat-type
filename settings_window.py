from __future__ import annotations

import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk
from typing import Callable

from PIL import Image, ImageDraw, ImageTk

from app_version import APP_VERSION
from cat_settings import AppSettings
from usage_metrics import UsageMetrics


CAT_STYLE_LABELS = {
    "Mix it up": "alternate",
    "Gray tabby": "gray",
    "Ginger tabby": "ginger",
}
PLACEMENT_LABELS = {
    "Above · right": "above-right",
    "Above · left": "above-left",
    "Below · right": "below-right",
    "Below · left": "below-left",
}


class Toggle(tk.Frame):
    """A small, friendly switch with a full-row click target."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        variable: tk.BooleanVar,
        title: str,
        background: str,
        accent: str,
        ink: str,
        title_font: tkfont.Font,
    ) -> None:
        super().__init__(
            parent,
            background=background,
            cursor="hand2",
            takefocus=True,
            highlightthickness=1,
            highlightbackground=background,
            highlightcolor=accent,
        )
        self.variable = variable
        self.accent = accent

        copy = tk.Frame(self, background=background, cursor="hand2")
        copy.pack(side="left", fill="x", expand=True)
        tk.Label(
            copy,
            text=title,
            background=background,
            foreground=ink,
            font=title_font,
            cursor="hand2",
        ).pack(anchor="w")

        self.switch = tk.Canvas(
            self,
            width=52,
            height=30,
            background=background,
            highlightthickness=0,
            cursor="hand2",
        )
        self.switch.pack(side="right", padx=(12, 0))

        for widget in (self, copy, *copy.winfo_children(), self.switch):
            widget.bind("<Button-1>", self._toggle)
        for sequence in ("<space>", "<Return>", "<KP_Enter>"):
            self.bind(sequence, self._toggle)
        self.variable.trace_add("write", lambda *_args: self._draw())
        self._draw()

    def _toggle(self, _event: tk.Event[tk.Misc]) -> None:
        self.variable.set(not self.variable.get())

    def _draw(self) -> None:
        on = self.variable.get()
        track = self.accent if on else "#D9D1C8"
        scale = 4
        width = 52
        height = 30
        image = Image.new(
            "RGBA",
            (width * scale, height * scale),
            (0, 0, 0, 0),
        )
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle(
            (1 * scale, 2 * scale, 51 * scale, 28 * scale),
            radius=13 * scale,
            fill=track,
        )
        knob_left = 27 if on else 4
        knob_box = (
            knob_left * scale,
            4 * scale,
            (knob_left + 22) * scale,
            26 * scale,
        )
        shadow_box = (
            knob_box[0],
            knob_box[1] + scale,
            knob_box[2],
            knob_box[3] + scale,
        )
        draw.ellipse(shadow_box, fill=(78, 55, 48, 35))
        draw.ellipse(
            knob_box,
            fill="#FFFFFF",
            outline=(235, 225, 219, 255),
            width=scale,
        )
        image = image.resize(
            (width, height),
            getattr(Image, "Resampling", Image).LANCZOS,
        )
        self._switch_image = ImageTk.PhotoImage(image, master=self.switch)
        self.switch.delete("all")
        self.switch.create_image(0, 0, anchor="nw", image=self._switch_image)


class CatScale(tk.Canvas):
    """A theme-stable slider with mouse and keyboard controls."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        variable: tk.Variable,
        minimum: float,
        maximum: float,
        command: Callable[[str], None],
        background: str,
        trough: str,
        accent: str,
        accent_dark: str,
    ) -> None:
        super().__init__(
            parent,
            height=24,
            background=background,
            highlightthickness=0,
            cursor="hand2",
            takefocus=True,
        )
        self.variable = variable
        self.minimum = float(minimum)
        self.maximum = float(maximum)
        self.command = command
        self.trough = trough
        self.accent = accent
        self.accent_dark = accent_dark
        self._integer_value = isinstance(variable, tk.IntVar)
        self._step = 1.0 if self._integer_value else 0.1

        self.bind("<Configure>", lambda _event: self._draw())
        self.bind("<Button-1>", self._set_from_pointer)
        self.bind("<B1-Motion>", self._set_from_pointer)
        self.bind("<FocusIn>", lambda _event: self._draw())
        self.bind("<FocusOut>", lambda _event: self._draw())
        self.bind("<Left>", lambda event: self._nudge(event, -self._step))
        self.bind("<Down>", lambda event: self._nudge(event, -self._step))
        self.bind("<Right>", lambda event: self._nudge(event, self._step))
        self.bind("<Up>", lambda event: self._nudge(event, self._step))
        self.bind("<Home>", lambda event: self._set_from_key(event, self.minimum))
        self.bind("<End>", lambda event: self._set_from_key(event, self.maximum))
        self.variable.trace_add("write", self._on_variable_changed)
        self.after_idle(self._draw)

    def _fraction(self) -> float:
        span = self.maximum - self.minimum
        if span <= 0:
            return 0.0
        value = min(self.maximum, max(self.minimum, float(self.variable.get())))
        return (value - self.minimum) / span

    def _draw(self) -> None:
        if not self.winfo_exists():
            return
        self.delete("all")
        left = 10
        right = max(left, self.winfo_width() - 10)
        y = 12
        knob_x = left + ((right - left) * self._fraction())
        self.create_line(
            left,
            y,
            right,
            y,
            fill=self.trough,
            width=6,
            capstyle="round",
        )
        if knob_x > left:
            self.create_line(
                left,
                y,
                knob_x,
                y,
                fill=self.accent,
                width=6,
                capstyle="round",
            )
        outline = (
            self.accent_dark
            if self.focus_get() is self
            else self.accent
        )
        self.create_oval(
            knob_x - 8,
            y - 8,
            knob_x + 8,
            y + 8,
            fill="#FFFFFF",
            outline=outline,
            width=2,
        )

    def _set_value(self, value: float) -> None:
        clamped = min(self.maximum, max(self.minimum, value))
        self.variable.set(round(clamped) if self._integer_value else clamped)

    def _set_from_pointer(self, event: tk.Event[tk.Misc]) -> str:
        self.focus_set()
        left = 10
        right = max(left + 1, self.winfo_width() - 10)
        fraction = min(1.0, max(0.0, (event.x - left) / (right - left)))
        self._set_value(self.minimum + ((self.maximum - self.minimum) * fraction))
        return "break"

    def _nudge(self, event: tk.Event[tk.Misc], amount: float) -> str:
        return self._set_from_key(event, float(self.variable.get()) + amount)

    def _set_from_key(
        self,
        _event: tk.Event[tk.Misc],
        value: float,
    ) -> str:
        self._set_value(value)
        return "break"

    def _on_variable_changed(self, *_args: object) -> None:
        self._draw()
        self.command(str(self.variable.get()))


class SettingsWindow:
    BACKGROUND = "#FFF8F2"
    CARD = "#FFFFFF"
    INK = "#342B2A"
    MUTED = "#85716C"
    ACCENT = "#E86F51"
    ACCENT_DARK = "#C95238"
    PEACH = "#FFE4D8"
    BLUSH = "#FFF0E9"
    BORDER = "#F0DCD2"
    PREFERRED_WIDTH = 920
    PREFERRED_HEIGHT = 800
    MIN_WIDTH = 700
    MIN_HEIGHT = 480
    SCREEN_HORIZONTAL_MARGIN = 40
    SCREEN_VERTICAL_MARGIN = 80
    TWO_COLUMN_BREAKPOINT = 840
    CONTENT_LAYOUT_SETTLE_PASSES = 2
    CONTENT_FIT_SETTLE_PASSES = 4
    FOOTER_VERTICAL_PADDING: tuple[int, int] = (12, 14)

    def __init__(
        self,
        parent: tk.Misc,
        settings: AppSettings,
        on_save: Callable[[AppSettings], None],
        icon_path: str | None = None,
        keystroke_count: int = 0,
        usage_metrics: UsageMetrics | None = None,
        on_metrics_view_change: Callable[[str], None] | None = None,
        on_check_for_updates: Callable[[], None] | None = None,
        on_open_release_page: Callable[[], None] | None = None,
        update_status: str = "",
        on_close: Callable[[], None] | None = None,
    ) -> None:
        self._on_save = on_save
        self._on_metrics_view_change = on_metrics_view_change
        self._on_check_for_updates = on_check_for_updates
        self._on_open_release_page = on_open_release_page
        self._on_close = on_close
        self._after_id: str | None = None
        self._preview_step = 0
        self._preview_variant = "gray"
        self._preview_frames: dict[str, dict[str, ImageTk.PhotoImage]] = {}
        self._layout_mode: str | None = None
        self.usage_metrics = (usage_metrics or UsageMetrics()).normalized()
        if keystroke_count > self.usage_metrics.total_keystrokes:
            self.usage_metrics.total_keystrokes = keystroke_count

        self.window = tk.Toplevel(parent)
        self.window.title("Cat Type Settings")
        self.window.geometry(
            f"{self.PREFERRED_WIDTH}x{self.PREFERRED_HEIGHT}"
        )
        self.window.minsize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self.window.resizable(True, True)
        self.window.configure(background=self.BACKGROUND)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self._configure_fonts()
        if icon_path:
            try:
                self.window.iconbitmap(default=icon_path)
            except tk.TclError:
                pass

        self.enabled = tk.BooleanVar(value=settings.enabled)
        self.cat_style = tk.StringVar(
            value=self._label_for(CAT_STYLE_LABELS, settings.cat_style)
        )
        self.size_percent = tk.IntVar(value=settings.size_percent)
        self.hold_seconds = tk.DoubleVar(value=settings.hold_seconds)
        self.fade_seconds = tk.DoubleVar(value=settings.fade_seconds)
        self.placement = tk.StringVar(
            value=self._label_for(PLACEMENT_LABELS, settings.placement)
        )
        self.launch_at_startup = tk.BooleanVar(value=settings.launch_at_startup)
        self.keystroke_count_text = tk.StringVar(
            value=f"{self.usage_metrics.total_keystrokes:,}"
        )
        self.active_page = tk.StringVar(value="Settings")
        self.metrics_range_days = tk.IntVar(value=7)
        self.metrics_view = tk.StringVar(value=settings.metrics_view)
        self.metrics_today_text = tk.StringVar(value="0")
        self.metrics_week_text = tk.StringVar(value="0")
        self.metrics_total_text = tk.StringVar(
            value=f"{self.usage_metrics.total_keystrokes:,}"
        )
        self.update_status_text = tk.StringVar(value=update_status)

        self._configure_styles()
        self._load_preview_frames(icon_path)
        self._build()
        self.window.bind("<Escape>", self._close_from_shortcut)
        self.window.bind("<Control-s>", self._save_from_shortcut)
        if sys.platform == "darwin":
            self.window.bind("<Command-s>", self._save_from_shortcut)
        self._center()
        self.window.lift()
        self.window.focus_force()
        self._animate_preview()

    def _configure_fonts(self) -> None:
        available = set(tkfont.families(self.window))

        def pick(*families: str) -> str:
            return next(
                (family for family in families if family in available),
                "TkDefaultFont",
            )

        display = pick(
            "Cooper Black",
            "Arial Rounded MT Bold",
            "Comic Sans MS",
            "TkDefaultFont",
        )
        heading = pick(
            "Kristen ITC",
            "Comic Sans MS",
            "Segoe Print",
            "TkDefaultFont",
        )
        body = pick(
            "Trebuchet MS",
            "Avenir Next",
            "Helvetica Neue",
            "Segoe UI",
            "Arial",
            "TkDefaultFont",
        )
        self.fonts = {
            "display_compact": tkfont.Font(
                self.window,
                family=display,
                size=24,
            ),
            "section": tkfont.Font(
                self.window,
                family=heading,
                size=12,
            ),
            "control": tkfont.Font(
                self.window,
                family=body,
                size=10,
                weight="bold",
            ),
            "body": tkfont.Font(
                self.window,
                family=body,
                size=10,
            ),
            "small": tkfont.Font(
                self.window,
                family=body,
                size=9,
            ),
            "tiny": tkfont.Font(
                self.window,
                family=body,
                size=8,
            ),
            "button": tkfont.Font(
                self.window,
                family=body,
                size=10,
                weight="bold",
            ),
            "symbol": tkfont.Font(
                self.window,
                family=pick(
                    "Apple Symbols",
                    "Segoe UI Symbol",
                    "Noto Sans Symbols",
                    body,
                ),
                size=12,
            ),
        }

    @staticmethod
    def _label_for(mapping: dict[str, str], value: str) -> str:
        return next(
            (label for label, stored in mapping.items() if stored == value),
            next(iter(mapping)),
        )

    def _configure_styles(self) -> None:
        style = ttk.Style(self.window)
        themes = style.theme_names()
        if "clam" in themes:
            style.theme_use("clam")

        self.combobox_style = "Cat.TCombobox"
        self.scale_style = "Cat.Horizontal.TScale"
        self.scrollbar_style = "Cat.Vertical.TScrollbar"
        self.primary_button_style = "Cat.Accent.TButton"
        self.secondary_button_style = "Cat.TButton"
        style.configure(
            "Cat.TRadiobutton",
            background=self.CARD,
            foreground=self.INK,
            indicatorcolor=self.BLUSH,
            font=self.fonts["control"],
            padding=(0, 4),
        )
        style.map(
            "Cat.TRadiobutton",
            background=[("active", self.CARD)],
            foreground=[("disabled", self.MUTED)],
            indicatorcolor=[
                ("selected", self.ACCENT),
                ("active", self.PEACH),
                ("!selected", self.BLUSH),
            ],
        )
        style.configure(
            "Cat.TCombobox",
            padding=7,
            fieldbackground=self.BLUSH,
            background=self.BLUSH,
            foreground=self.INK,
            bordercolor=self.BORDER,
            lightcolor=self.BORDER,
            darkcolor=self.BORDER,
            arrowcolor=self.ACCENT_DARK,
            font=self.fonts["body"],
        )
        style.map(
            "Cat.TCombobox",
            fieldbackground=[("readonly", self.BLUSH)],
            selectbackground=[("readonly", self.BLUSH)],
            selectforeground=[("readonly", self.INK)],
        )
        style.configure(
            "Cat.Horizontal.TScale",
            background=self.ACCENT,
            troughcolor="#E8D8D0",
            bordercolor=self.CARD,
            lightcolor="#E8D8D0",
            darkcolor="#D9C5BC",
            sliderthickness=18,
            sliderlength=18,
            sliderrelief="flat",
            gripcount=0,
        )
        style.configure(
            "Cat.Vertical.TScrollbar",
            background=self.PEACH,
            troughcolor=self.BACKGROUND,
            bordercolor=self.BACKGROUND,
            lightcolor=self.PEACH,
            darkcolor=self.PEACH,
            arrowcolor=self.ACCENT_DARK,
        )
        style.configure(
            "Cat.TButton",
            background="#F1E5DF",
            foreground=self.INK,
            bordercolor=self.BORDER,
            lightcolor="#F1E5DF",
            darkcolor=self.BORDER,
            font=self.fonts["button"],
            padding=(14, 7),
        )
        style.map(
            "Cat.TButton",
            background=[
                ("active", self.BLUSH),
                ("pressed", self.BORDER),
                ("disabled", self.BLUSH),
            ],
            foreground=[("disabled", self.MUTED)],
        )
        style.configure(
            "Cat.Accent.TButton",
            background=self.ACCENT,
            foreground="#FFFFFF",
            bordercolor=self.ACCENT_DARK,
            font=self.fonts["button"],
            padding=(14, 7),
        )
        style.map(
            "Cat.Accent.TButton",
            background=[
                ("active", self.ACCENT_DARK),
                ("pressed", self.ACCENT_DARK),
                ("disabled", "#D9D1C8"),
            ],
            foreground=[("disabled", "#FFFFFF")],
        )

    def _load_preview_frames(self, icon_path: str | None) -> None:
        if not icon_path:
            return
        frames_root = Path(icon_path).parent / "tabby-frames"
        resampling = getattr(Image, "Resampling", Image).LANCZOS
        for variant in ("gray", "ginger"):
            variant_frames: dict[str, ImageTk.PhotoImage] = {}
            for name in ("idle", "tap-left", "tap-right", "excited"):
                path = frames_root / variant / f"{name}.png"
                if not path.exists():
                    continue
                with Image.open(path) as image:
                    scaled = image.convert("RGBA").resize((148, 148), resampling)
                    variant_frames[name] = ImageTk.PhotoImage(
                        scaled,
                        master=self.window,
                    )
            if variant_frames:
                self._preview_frames[variant] = variant_frames

    def _build(self) -> None:
        self.body = tk.Frame(self.window, background=self.BACKGROUND)
        self.body.pack(fill="both", expand=True)

        self.footer = self._build_footer(self.body)

        self.scroll_host = tk.Frame(
            self.body,
            background=self.BACKGROUND,
        )
        self.scroll_host.pack(side="top", fill="both", expand=True)

        self.scrollbar = ttk.Scrollbar(
            self.scroll_host,
            orient="vertical",
            style=self.scrollbar_style,
        )
        self.scrollbar.pack(side="right", fill="y")

        self.scroll_canvas = tk.Canvas(
            self.scroll_host,
            background=self.BACKGROUND,
            highlightthickness=0,
            yscrollcommand=self.scrollbar.set,
        )
        self.scroll_canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.configure(command=self.scroll_canvas.yview)

        self.scroll_content = tk.Frame(
            self.scroll_canvas,
            background=self.BACKGROUND,
        )
        self._scroll_content_id = self.scroll_canvas.create_window(
            (0, 0),
            window=self.scroll_content,
            anchor="nw",
        )
        self.scroll_content.bind(
            "<Configure>",
            self._on_content_configure,
        )
        self.scroll_canvas.bind(
            "<Configure>",
            self._on_canvas_configure,
        )
        self.window.bind(
            "<MouseWheel>",
            self._on_mouse_wheel,
            add="+",
        )
        self.window.bind(
            "<Button-4>",
            self._on_mouse_wheel,
            add="+",
        )
        self.window.bind(
            "<Button-5>",
            self._on_mouse_wheel,
            add="+",
        )

        self._build_page_switcher(self.scroll_content)

        self.columns = tk.Frame(
            self.scroll_content,
            background=self.BACKGROUND,
        )
        self.columns.pack(fill="x", padx=26)
        self.columns.grid_columnconfigure(0, weight=1, uniform="settings")
        self.columns.grid_columnconfigure(1, weight=1, uniform="settings")

        self.left_column = tk.Frame(
            self.columns,
            background=self.BACKGROUND,
        )
        self.left_column.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 8),
        )
        self.right_column = tk.Frame(
            self.columns,
            background=self.BACKGROUND,
        )
        self.right_column.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=(8, 0),
        )

        self._build_companion_card(self.left_column)
        self._build_appearance_card(self.left_column)
        self._build_size_card(self.right_column)
        self._build_timing_card(self.right_column)
        self._build_updates_card(self.right_column)
        self._build_metrics_page(self.scroll_content)
        self._refresh_usage_metrics()

    def _build_page_switcher(self, parent: tk.Frame) -> None:
        self.page_switcher = tk.Frame(parent, background=self.BACKGROUND)
        self.page_switcher.pack(fill="x", padx=26, pady=(24, 14))
        tabs = tk.Frame(self.page_switcher, background=self.BLUSH)
        tabs.pack(anchor="w")
        self.page_buttons: dict[str, tk.Radiobutton] = {}
        for index, label in enumerate(("Settings", "Metrics")):
            button = tk.Radiobutton(
                tabs,
                text=label,
                variable=self.active_page,
                value=label,
                command=self._switch_page,
                indicatoron=False,
                relief="flat",
                borderwidth=0,
                highlightthickness=2,
                highlightbackground=self.BORDER,
                highlightcolor=self.ACCENT,
                background=self.BLUSH,
                selectcolor=self.PEACH,
                activebackground=self.PEACH,
                activeforeground=self.INK,
                foreground=self.INK,
                font=self.fonts["control"],
                padx=22,
                pady=8,
                cursor="hand2",
                takefocus=True,
            )
            button.grid(row=0, column=index, sticky="ew")
            tabs.grid_columnconfigure(index, weight=1)
            self.page_buttons[label] = button
        self._refresh_page_buttons()

    def _refresh_page_buttons(self) -> None:
        selected = self.active_page.get()
        for label, button in self.page_buttons.items():
            is_selected = label == selected
            button.configure(
                background=self.PEACH if is_selected else self.BLUSH,
                foreground=self.ACCENT_DARK if is_selected else self.INK,
                highlightbackground=self.ACCENT if is_selected else self.BORDER,
            )

    def _switch_page(self) -> None:
        show_metrics = self.active_page.get() == "Metrics"
        self._refresh_page_buttons()
        if show_metrics:
            self.columns.pack_forget()
            self.metrics_page.pack(fill="x", padx=26)
            self._refresh_usage_metrics()
        else:
            self.metrics_page.pack_forget()
            self.columns.pack(fill="x", padx=26)
        self.scroll_canvas.yview_moveto(0)
        self.window.after_idle(self._sync_scrollbar_visibility)

    def _build_companion_card(self, parent: tk.Frame) -> None:
        card, content = self._card(parent, "Companion")
        self.enabled_toggle = Toggle(
            content,
            variable=self.enabled,
            title="Show my cat while I type",
            background=self.CARD,
            accent=self.ACCENT,
            ink=self.INK,
            title_font=self.fonts["control"],
        )
        self.enabled_toggle.pack(fill="x")
        counter = tk.Frame(content, background=self.BLUSH)
        counter.pack(fill="x", pady=(14, 0))
        self.keystroke_count_title = tk.Label(
            counter,
            text="All-time keystrokes",
            background=self.BLUSH,
            foreground=self.MUTED,
            font=self.fonts["small"],
        )
        self.keystroke_count_title.pack(
            side="left",
            padx=(12, 6),
            pady=10,
        )
        tk.Label(
            counter,
            textvariable=self.keystroke_count_text,
            background=self.BLUSH,
            foreground=self.ACCENT_DARK,
            font=self.fonts["section"],
        ).pack(side="right", padx=(6, 12), pady=8)
        self._divider(content).pack(fill="x", pady=13)
        self.launch_at_startup_toggle = Toggle(
            content,
            variable=self.launch_at_startup,
            title="Start Cat Type when I sign in",
            background=self.CARD,
            accent=self.ACCENT,
            ink=self.INK,
            title_font=self.fonts["control"],
        )
        self.launch_at_startup_toggle.pack(fill="x")
        card.pack(fill="x", pady=(0, 14))

    def _build_metrics_page(self, parent: tk.Frame) -> None:
        self.metrics_page = tk.Frame(parent, background=self.BACKGROUND)

        summary = tk.Frame(self.metrics_page, background=self.BACKGROUND)
        summary.pack(fill="x", pady=(0, 14))
        for column in range(3):
            summary.grid_columnconfigure(column, weight=1, uniform="metrics")
        self._metric_stat(
            summary,
            column=0,
            label="Today",
            value=self.metrics_today_text,
            detail="keystrokes",
            padx=(0, 5),
        )
        self._metric_stat(
            summary,
            column=1,
            label="Last 7 days",
            value=self.metrics_week_text,
            detail="keystrokes",
            padx=5,
        )
        self._metric_stat(
            summary,
            column=2,
            label="All time",
            value=self.metrics_total_text,
            detail="keystrokes",
            padx=(5, 0),
        )

        activity_card, activity_content = self._card(
            self.metrics_page,
            "Activity",
            heading_actions=self._build_metrics_controls,
        )
        self.metrics_chart = tk.Canvas(
            activity_content,
            height=250,
            background=self.CARD,
            highlightthickness=0,
        )
        self.metrics_chart.pack(fill="x")
        self.metrics_chart.bind(
            "<Configure>",
            lambda _event: self._draw_metrics(),
        )
        activity_card.pack(fill="x", pady=(0, 14))

    def _build_metrics_controls(self, parent: tk.Frame) -> None:
        controls = tk.Frame(parent, background=self.CARD)
        controls.pack(side="right")

        range_control = tk.Frame(controls, background=self.CARD)
        range_control.pack(side="left", padx=(0, 12))
        self.metrics_range_label = tk.Label(
            range_control,
            text="Range",
            background=self.CARD,
            foreground=self.MUTED,
            font=self.fonts["tiny"],
        )
        self.metrics_range_label.pack(anchor="w", pady=(0, 4))
        ranges = tk.Frame(range_control, background=self.CARD)
        ranges.pack()
        self.metrics_range_buttons: dict[int, tk.Radiobutton] = {}
        for index, (label, days) in enumerate(
            (("1d", 1), ("7d", 7), ("30d", 30))
        ):
            button = tk.Radiobutton(
                ranges,
                text=label,
                variable=self.metrics_range_days,
                value=days,
                command=self._change_metrics_range,
                indicatoron=False,
                relief="flat",
                borderwidth=0,
                highlightthickness=1,
                highlightbackground=self.BORDER,
                background=self.BLUSH,
                selectcolor=self.PEACH,
                activebackground=self.PEACH,
                foreground=self.INK,
                font=self.fonts["small"],
                padx=12,
                pady=5,
                cursor="hand2",
                takefocus=True,
            )
            button.grid(row=0, column=index)
            self.metrics_range_buttons[days] = button

        view_control = tk.Frame(controls, background=self.CARD)
        view_control.pack(side="left")
        self.metrics_view_label = tk.Label(
            view_control,
            text="View",
            background=self.CARD,
            foreground=self.MUTED,
            font=self.fonts["tiny"],
        )
        self.metrics_view_label.pack(anchor="w", pady=(0, 4))
        views = tk.Frame(view_control, background=self.CARD)
        views.pack()
        self.metrics_view_buttons: dict[str, tk.Radiobutton] = {}
        for index, (label, view) in enumerate(
            (("Line", "line"), ("Columns", "columns"))
        ):
            button = tk.Radiobutton(
                views,
                text=label,
                variable=self.metrics_view,
                value=view,
                command=self._change_metrics_view,
                indicatoron=False,
                relief="flat",
                borderwidth=0,
                highlightthickness=1,
                highlightbackground=self.BORDER,
                background=self.BLUSH,
                selectcolor=self.PEACH,
                activebackground=self.PEACH,
                foreground=self.INK,
                font=self.fonts["small"],
                padx=12,
                pady=5,
                cursor="hand2",
                takefocus=True,
            )
            button.grid(row=0, column=index)
            self.metrics_view_buttons[view] = button

        self._refresh_metrics_range_buttons()
        self._refresh_metrics_view_buttons()

    def _metric_stat(
        self,
        parent: tk.Frame,
        *,
        column: int,
        label: str,
        value: tk.StringVar,
        detail: str,
        padx: int | tuple[int, int],
    ) -> None:
        card = tk.Frame(
            parent,
            background=self.CARD,
            highlightbackground=self.BORDER,
            highlightthickness=1,
        )
        card.grid(row=0, column=column, sticky="nsew", padx=padx)
        tk.Label(
            card,
            text=label,
            background=self.CARD,
            foreground=self.MUTED,
            font=self.fonts["small"],
        ).pack(anchor="w", padx=16, pady=(14, 4))
        tk.Label(
            card,
            textvariable=value,
            background=self.CARD,
            foreground=self.ACCENT_DARK,
            font=self.fonts["display_compact"],
        ).pack(anchor="w", padx=16)
        tk.Label(
            card,
            text=detail,
            background=self.CARD,
            foreground=self.MUTED,
            font=self.fonts["tiny"],
        ).pack(anchor="w", padx=16, pady=(2, 14))

    def _change_metrics_range(self) -> None:
        self._refresh_metrics_range_buttons()
        self._draw_metrics()

    def _refresh_metrics_range_buttons(self) -> None:
        selected = self.metrics_range_days.get()
        for days, button in self.metrics_range_buttons.items():
            button.configure(
                background=self.PEACH if days == selected else self.BLUSH,
                foreground=self.ACCENT_DARK if days == selected else self.INK,
            )

    def _change_metrics_view(self) -> None:
        self._refresh_metrics_view_buttons()
        self._draw_metrics()

        if self._on_metrics_view_change is not None:
            self._on_metrics_view_change(self.metrics_view.get())

    def _refresh_metrics_view_buttons(self) -> None:
        selected = self.metrics_view.get()
        for view, button in self.metrics_view_buttons.items():
            button.configure(
                background=self.PEACH if view == selected else self.BLUSH,
                foreground=self.ACCENT_DARK if view == selected else self.INK,
            )

    @staticmethod
    def _metric_line_positions(
        values: list[int],
        width: int,
        height: int,
        *,
        left: int,
        right: int,
        top: int,
        bottom: int,
    ) -> list[tuple[float, float]]:
        if not values:
            return []
        usable_width = max(1, width - left - right)
        usable_height = max(1, height - top - bottom)
        maximum = max(1, max(values))
        step = usable_width / max(1, len(values) - 1)
        baseline = height - bottom
        return [
            (
                left + step * index,
                baseline - usable_height * value / maximum,
            )
            for index, value in enumerate(values)
        ]

    @staticmethod
    def _metric_column_positions(
        values: list[int],
        width: int,
        height: int,
        *,
        left: int,
        right: int,
        top: int,
        bottom: int,
    ) -> list[tuple[float, float, float]]:
        if not values:
            return []
        usable_width = max(1, width - left - right)
        usable_height = max(1, height - top - bottom)
        maximum = max(1, max(values))
        step = usable_width / len(values)
        baseline = height - bottom
        return [
            (
                left + step * (index + 0.5),
                baseline,
                baseline - usable_height * value / maximum,
            )
            for index, value in enumerate(values)
        ]

    def _draw_metrics(self) -> None:
        canvas = self.metrics_chart
        canvas.delete("all")
        today = datetime.now().astimezone().date()
        days = self.metrics_range_days.get()
        if days == 1:
            values = self.usage_metrics.hourly_series(today)
            labels = [
                {0: "12a", 6: "6a", 12: "12p", 18: "6p", 23: "11p"}.get(hour)
                for hour in range(24)
            ]
            empty_message = "No activity recorded today yet"
        else:
            series = self.usage_metrics.daily_series(days, ending_on=today)
            values = [count for _day, count in series]
            labels = [
                (
                    day.strftime("%a")
                    if days == 7
                    else day.strftime("%d %b")
                    if index % 5 == 0 or index == days - 1
                    else None
                )
                for index, (day, _count) in enumerate(series)
            ]
            empty_message = "Start typing to see your daily rhythm"
        width = max(320, canvas.winfo_width())
        height = max(180, canvas.winfo_height())
        left = 46
        right = 14
        top = 24
        bottom = 34
        maximum = max(values, default=0)
        baseline = height - bottom
        for fraction in (0, 0.5, 1):
            y = baseline - (height - top - bottom) * fraction
            canvas.create_line(
                left,
                y,
                width - right,
                y,
                fill=self.BORDER,
            )
            canvas.create_text(
                left - 8,
                y,
                text=f"{round(maximum * fraction):,}",
                anchor="e",
                fill=self.MUTED,
                font=self.fonts["tiny"],
            )
        if self.metrics_view.get() == "columns":
            column_positions = self._metric_column_positions(
                values,
                width,
                height,
                left=left,
                right=right,
                top=top,
                bottom=bottom,
            )
            label_positions = [
                (x, y) for x, _column_baseline, y in column_positions
            ]
            step = (width - left - right) / max(1, len(values))
            bar_width = max(3, min(22, step * 0.56))
            if maximum:
                for value, (x, column_baseline, y) in zip(
                    values,
                    column_positions,
                ):
                    if value:
                        half_width = bar_width / 2
                        corner_radius = min(
                            4.0,
                            half_width,
                            (column_baseline - y) / 2,
                        )
                        column_left = x - half_width
                        column_right = x + half_width
                        canvas.create_polygon(
                            column_left + corner_radius,
                            y,
                            column_right - corner_radius,
                            y,
                            column_right,
                            y,
                            column_right,
                            y + corner_radius,
                            column_right,
                            column_baseline - corner_radius,
                            column_right,
                            column_baseline,
                            column_right - corner_radius,
                            column_baseline,
                            column_left + corner_radius,
                            column_baseline,
                            column_left,
                            column_baseline,
                            column_left,
                            column_baseline - corner_radius,
                            column_left,
                            y + corner_radius,
                            column_left,
                            y,
                            fill=self.ACCENT_DARK,
                            outline="",
                            smooth=True,
                            splinesteps=12,
                            tags=("metric-column",),
                        )
        else:
            line_positions = self._metric_line_positions(
                values,
                width,
                height,
                left=left,
                right=right,
                top=top,
                bottom=bottom,
            )
            label_positions = line_positions
            if maximum and len(line_positions) > 1:
                canvas.create_line(
                    *[
                        coordinate
                        for point in line_positions
                        for coordinate in point
                    ],
                    fill=self.ACCENT_DARK,
                    width=3,
                    smooth=False,
                    capstyle="round",
                    joinstyle="round",
                    tags=("metric-line",),
                )
                for x, y in line_positions:
                    canvas.create_oval(
                        x - 3,
                        y - 3,
                        x + 3,
                        y + 3,
                        fill=self.ACCENT_DARK,
                        outline=self.CARD,
                        width=1,
                        tags=("metric-point",),
                    )
        for (x, _y), label in zip(label_positions, labels):
            if label is not None:
                canvas.create_text(
                    x,
                    height - 13,
                    text=label,
                    fill=self.MUTED,
                    font=self.fonts["tiny"],
                )
        if not maximum:
            canvas.create_text(
                width / 2,
                height / 2 - 8,
                text=empty_message,
                fill=self.MUTED,
                font=self.fonts["body"],
            )

    def _refresh_usage_metrics(self) -> None:
        today = datetime.now().astimezone().date()
        week = self.usage_metrics.daily_series(7, ending_on=today)
        today_count = self.usage_metrics.count_for_day(today)
        self.keystroke_count_text.set(
            f"{self.usage_metrics.total_keystrokes:,}"
        )
        self.metrics_today_text.set(f"{today_count:,}")
        self.metrics_week_text.set(f"{sum(count for _day, count in week):,}")
        self.metrics_total_text.set(
            f"{self.usage_metrics.total_keystrokes:,}"
        )
        if (
            hasattr(self, "metrics_chart")
            and self.active_page.get() == "Metrics"
        ):
            self._change_metrics_range()

    def _build_appearance_card(self, parent: tk.Frame) -> None:
        self.cat_style_card, self.cat_style_content = self._card(
            parent,
            "Cat style",
        )
        content = self.cat_style_content
        self.preview_canvas = tk.Canvas(
            content,
            width=250,
            height=166,
            background=self.PEACH,
            highlightthickness=0,
        )
        self.preview_canvas.pack(anchor="center", pady=(0, 16))
        self.preview_canvas.create_oval(
            24,
            132,
            228,
            160,
            fill="#F4C7B5",
            outline="",
        )
        self.preview_canvas.create_text(
            218,
            24,
            text="✦",
            fill=self.ACCENT,
            font=self.fonts["symbol"],
        )
        self.preview_canvas.create_text(
            31,
            45,
            text="✦",
            fill="#F3A486",
            font=self.fonts["symbol"],
        )
        self._preview_image = self.preview_canvas.create_image(126, 84)
        choices = tk.Frame(content, background=self.CARD)
        choices.pack(fill="x", pady=(0, 16))
        self.cat_style_buttons: dict[str, tk.Radiobutton] = {}
        for index, label in enumerate(CAT_STYLE_LABELS):
            button = tk.Radiobutton(
                choices,
                text=label,
                variable=self.cat_style,
                value=label,
                indicatoron=False,
                relief="flat",
                borderwidth=0,
                highlightthickness=2,
                highlightbackground=self.BORDER,
                highlightcolor=self.ACCENT,
                background=self.BLUSH,
                selectcolor=self.PEACH,
                activebackground=self.PEACH,
                activeforeground=self.INK,
                foreground=self.INK,
                font=self.fonts["control"],
                padx=8,
                pady=8,
                cursor="hand2",
            )
            button.grid(
                row=0,
                column=index,
                sticky="ew",
                padx=(0 if index == 0 else 4, 0),
            )
            choices.grid_columnconfigure(index, weight=1)
            self.cat_style_buttons[label] = button
        self.cat_style.trace_add(
            "write",
            lambda *_args: self._refresh_cat_style_buttons(),
        )
        self._refresh_cat_style_buttons()

        self._field_label(content, "Favorite spot").pack(anchor="w")
        ttk.Combobox(
            content,
            textvariable=self.placement,
            values=list(PLACEMENT_LABELS),
            state="readonly",
            style=self.combobox_style,
        ).pack(fill="x", pady=(6, 0))
        self.cat_style_card.pack(fill="x")

    def _refresh_cat_style_buttons(self) -> None:
        selected = self.cat_style.get()
        for label, button in self.cat_style_buttons.items():
            is_selected = label == selected
            button.configure(
                background=self.PEACH if is_selected else self.BLUSH,
                foreground=self.ACCENT_DARK if is_selected else self.INK,
                highlightbackground=self.ACCENT if is_selected else self.BORDER,
            )

    def _build_size_card(self, parent: tk.Frame) -> None:
        card, content = self._card(parent, "Cat size")
        self._slider(
            content,
            "Preview scale",
            self.size_percent,
            60,
            175,
            lambda value: f"{round(float(value))}%",
        )
        card.pack(fill="x", pady=(0, 14))

    def _build_timing_card(self, parent: tk.Frame) -> None:
        card, content = self._card(parent, "Timing")
        self._slider(
            content,
            "Hang around",
            self.hold_seconds,
            0.5,
            5.0,
            lambda value: f"{float(value):.1f}s",
        )
        self._slider(
            content,
            "Soft fade",
            self.fade_seconds,
            0.0,
            1.5,
            lambda value: f"{float(value):.1f}s",
            top_padding=18,
        )
        card.pack(fill="x", pady=(0, 14))

    def _build_updates_card(self, parent: tk.Frame) -> None:
        card, content = self._card(parent, "Updates")
        self.update_version_label = tk.Label(
            content,
            text=f"Version {APP_VERSION}",
            background=self.CARD,
            foreground=self.INK,
            font=self.fonts["control"],
        )
        self.update_version_label.pack(anchor="w")
        self.update_status_label = tk.Label(
            content,
            textvariable=self.update_status_text,
            background=self.CARD,
            foreground=self.MUTED,
            font=self.fonts["small"],
            justify="left",
            anchor="w",
            wraplength=1,
        )
        self.update_status_label.pack(anchor="w", fill="x", pady=(5, 10))
        content.bind("<Configure>", self._on_update_card_configure, add="+")
        update_actions = tk.Frame(content, background=self.CARD)
        update_actions.pack(fill="x")
        self.check_for_updates_button = ttk.Button(
            update_actions,
            text="Check for updates",
            command=self._on_check_for_updates,
            state="normal" if self._on_check_for_updates else "disabled",
            style=self.secondary_button_style,
            cursor="arrow",
            takefocus=True,
        )
        self.check_for_updates_button.pack(side="left")
        self.open_release_page_button = ttk.Button(
            update_actions,
            text="Open release page",
            command=self._on_open_release_page,
            state="normal" if self._on_open_release_page else "disabled",
            style=self.secondary_button_style,
            cursor="arrow",
            takefocus=True,
        )
        self.open_release_page_button.pack(side="left", padx=(8, 0))
        card.pack(fill="x", pady=(0, 14))

    def _build_footer(self, body: tk.Frame) -> tk.Frame:
        footer = tk.Frame(body, background=self.BACKGROUND)
        footer.pack(
            side="bottom",
            fill="x",
            padx=28,
            pady=self.FOOTER_VERTICAL_PADDING,
        )
        self.footer_buttons = tk.Frame(
            footer,
            background=self.BACKGROUND,
        )
        self.footer_buttons.pack(side="right")
        self.cancel_button = ttk.Button(
            self.footer_buttons,
            text="Cancel",
            command=self.close,
            style=self.secondary_button_style,
            cursor="arrow",
            takefocus=True,
        )
        self.cancel_button.pack(side="left")
        self.save_button = ttk.Button(
            self.footer_buttons,
            text="Save changes",
            command=self._save,
            style=self.primary_button_style,
            cursor="arrow",
            takefocus=True,
        )
        self.save_button.pack(side="left", padx=(8, 0))
        return footer

    def _card(
        self,
        parent: tk.Misc,
        title: str,
        heading_actions: Callable[[tk.Frame], None] | None = None,
    ) -> tuple[tk.Frame, tk.Frame]:
        outer = tk.Frame(
            parent,
            background=self.CARD,
            highlightbackground=self.BORDER,
            highlightthickness=1,
        )
        heading = tk.Frame(outer, background=self.CARD)
        heading.pack(fill="x", padx=18, pady=(15, 11))
        if heading_actions is not None:
            heading_actions(heading)
        tk.Label(
            heading,
            text=title,
            background=self.CARD,
            foreground=self.INK,
            font=self.fonts["section"],
        ).pack(anchor="w")
        content = tk.Frame(outer, background=self.CARD)
        content.pack(fill="x", padx=18, pady=(0, 16))
        return outer, content

    def _divider(self, parent: tk.Misc) -> tk.Frame:
        return tk.Frame(parent, background="#F3E8E2", height=1)

    def _field_label(self, parent: tk.Misc, text: str) -> tk.Label:
        return tk.Label(
            parent,
            text=text,
            background=self.CARD,
            foreground=self.INK,
            font=self.fonts["control"],
        )

    def _slider(
        self,
        parent: tk.Misc,
        label: str,
        variable: tk.Variable,
        minimum: float,
        maximum: float,
        formatter: Callable[[str], str],
        top_padding: int = 0,
    ) -> None:
        row = tk.Frame(parent, background=self.CARD)
        row.pack(fill="x", pady=(top_padding, 0))
        self._field_label(row, label).pack(side="left")
        value_label = tk.Label(
            row,
            background=self.PEACH,
            foreground=self.ACCENT_DARK,
            font=self.fonts["control"],
            padx=7,
            pady=2,
        )
        value_label.pack(side="right")

        def update(value: str) -> None:
            value_label.configure(text=formatter(value))

        scale = CatScale(
            parent,
            variable=variable,
            minimum=minimum,
            maximum=maximum,
            command=update,
            background=self.CARD,
            trough="#E8D8D0",
            accent=self.ACCENT,
            accent_dark=self.ACCENT_DARK,
        )
        scale.pack(fill="x", pady=(9, 0))
        update(str(variable.get()))

    def _on_content_configure(
        self,
        _event: tk.Event[tk.Misc],
    ) -> None:
        bounds = self.scroll_canvas.bbox("all")
        if bounds is not None:
            self.scroll_canvas.configure(scrollregion=bounds)
        self._sync_scrollbar_visibility()

    def _on_canvas_configure(
        self,
        event: tk.Event[tk.Misc],
    ) -> None:
        self.scroll_canvas.itemconfigure(
            self._scroll_content_id,
            width=event.width,
        )
        self._apply_responsive_layout(event.width)
        self._sync_scrollbar_visibility()

    @classmethod
    def _is_narrow_layout(cls, width: int) -> bool:
        return width < cls.TWO_COLUMN_BREAKPOINT

    def _apply_responsive_layout(self, width: int) -> None:
        mode = "narrow" if self._is_narrow_layout(width) else "wide"
        if mode == self._layout_mode:
            return
        self._layout_mode = mode
        if mode == "narrow":
            self.columns.grid_columnconfigure(0, weight=1, uniform="")
            self.columns.grid_columnconfigure(1, weight=0, uniform="")
            self.left_column.grid_configure(
                row=0,
                column=0,
                padx=0,
                pady=0,
            )
            self.right_column.grid_configure(
                row=1,
                column=0,
                padx=0,
                pady=(14, 0),
            )
            return

        self.columns.grid_columnconfigure(0, weight=1, uniform="settings")
        self.columns.grid_columnconfigure(1, weight=1, uniform="settings")
        self.left_column.grid_configure(
            row=0,
            column=0,
            padx=(0, 8),
            pady=0,
        )
        self.right_column.grid_configure(
            row=0,
            column=1,
            padx=(8, 0),
            pady=0,
        )

    def _sync_scrollbar_visibility(
        self,
        viewport_height: int | None = None,
    ) -> None:
        bounds = self.scroll_canvas.bbox("all")
        available_height = (
            self.scroll_canvas.winfo_height()
            if viewport_height is None
            else viewport_height
        )
        overflows = bool(
            bounds
            and bounds[3] - bounds[1] > available_height
        )
        is_visible = bool(self.scrollbar.winfo_manager())
        if overflows and not is_visible:
            self.scrollbar.pack(
                side="right",
                fill="y",
                before=self.scroll_canvas,
            )
        elif not overflows and is_visible:
            self.scrollbar.pack_forget()
            self.scroll_canvas.yview_moveto(0)

    def _on_update_card_configure(
        self,
        event: tk.Event[tk.Misc],
    ) -> None:
        wraplength = max(1, event.width)
        if int(float(self.update_status_label.cget("wraplength"))) != wraplength:
            self.update_status_label.configure(wraplength=wraplength)

    @staticmethod
    def _wheel_scroll_units(event: tk.Event[tk.Misc]) -> int:
        delta = int(getattr(event, "delta", 0) or 0)
        if delta:
            magnitude = max(1, abs(delta) // 120)
            return -magnitude if delta > 0 else magnitude
        return {
            4: -1,
            5: 1,
        }.get(getattr(event, "num", None), 0)

    def _event_is_over_scroll_content(
        self,
        widget: tk.Misc | None,
    ) -> bool:
        while widget is not None:
            if widget is self.scroll_canvas:
                return True
            widget = getattr(widget, "master", None)
        return False

    def _on_mouse_wheel(
        self,
        event: tk.Event[tk.Misc],
    ) -> str | None:
        if not self._event_is_over_scroll_content(
            getattr(event, "widget", None)
        ):
            return None
        bounds = self.scroll_canvas.bbox("all")
        if (
            bounds is None
            or bounds[3] - bounds[1] <= self.scroll_canvas.winfo_height()
        ):
            return None
        units = self._wheel_scroll_units(event)
        if not units:
            return None
        self.scroll_canvas.yview_scroll(units, "units")
        return "break"

    def _animate_preview(self) -> None:
        sequence = ("idle", "tap-left", "idle", "tap-right", "excited", "idle")
        if self._preview_frames:
            selected = CAT_STYLE_LABELS.get(self.cat_style.get(), "alternate")
            if selected in ("gray", "ginger"):
                self._preview_variant = selected
            elif self._preview_step % len(sequence) == 0:
                self._preview_variant = (
                    "ginger" if self._preview_variant == "gray" else "gray"
                )
            frames = self._preview_frames.get(self._preview_variant, {})
            frame = frames.get(sequence[self._preview_step % len(sequence)])
            if frame is not None:
                self.preview_canvas.itemconfigure(self._preview_image, image=frame)
        self._preview_step += 1
        self._after_id = self.window.after(520, self._animate_preview)

    def _save(self) -> None:
        settings = AppSettings(
            enabled=self.enabled.get(),
            cat_style=CAT_STYLE_LABELS[self.cat_style.get()],
            size_percent=round(self.size_percent.get()),
            hold_seconds=round(self.hold_seconds.get(), 1),
            fade_seconds=round(self.fade_seconds.get(), 1),
            placement=PLACEMENT_LABELS[self.placement.get()],
            launch_at_startup=self.launch_at_startup.get(),
            metrics_view=self.metrics_view.get(),
        ).normalized()
        self._on_save(settings)
        self.close()

    def _save_from_shortcut(self, _event: tk.Event[tk.Misc]) -> str:
        self._save()
        return "break"

    def _close_from_shortcut(self, _event: tk.Event[tk.Misc]) -> str:
        self.close()
        return "break"

    @staticmethod
    def _content_fitted_height(
        opening_height: int,
        measured_height: int,
        content_height: int,
        viewport_height: int,
        available_height: int,
    ) -> int:
        required_height = measured_height + content_height - viewport_height
        return min(max(opening_height, required_height), available_height)

    @classmethod
    def _content_viewport_height(
        cls,
        window_height: int,
        footer_height: int,
    ) -> int:
        return max(
            1,
            window_height
            - footer_height
            - sum(cls.FOOTER_VERTICAL_PADDING),
        )

    @classmethod
    def _fit_to_screen(
        cls,
        width: int,
        height: int,
        screen_width: int,
        screen_height: int,
    ) -> tuple[int, int]:
        available_width = max(
            1,
            screen_width - cls.SCREEN_HORIZONTAL_MARGIN,
        )
        available_height = max(
            1,
            screen_height - cls.SCREEN_VERTICAL_MARGIN,
        )
        return min(width, available_width), min(height, available_height)

    def _settle_content_layout(
        self,
        window_width: int,
        viewport_height: int,
    ) -> None:
        """Synchronize width-driven layout before measuring its height."""
        for _ in range(self.CONTENT_LAYOUT_SETTLE_PASSES):
            scrollbar_width = (
                self.scrollbar.winfo_reqwidth()
                if self.scrollbar.winfo_manager()
                else 0
            )
            canvas_width = max(1, window_width - scrollbar_width)
            self.scroll_canvas.itemconfigure(
                self._scroll_content_id,
                width=canvas_width,
            )
            self._apply_responsive_layout(canvas_width)
            self.window.update_idletasks()
            self._sync_scrollbar_visibility(viewport_height)
            self.window.update_idletasks()

    def _center(self) -> None:
        self.window.update_idletasks()
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        available_width, available_height = self._fit_to_screen(
            screen_width,
            screen_height,
            screen_width,
            screen_height,
        )
        maximum_width, maximum_height = self.window.maxsize()
        if maximum_width > 0:
            available_width = min(available_width, maximum_width)
        if maximum_height > 0:
            available_height = min(available_height, maximum_height)
        self.window.minsize(
            min(self.MIN_WIDTH, available_width),
            min(self.MIN_HEIGHT, available_height),
        )
        width = min(self.window.winfo_width(), available_width)
        opening_height = min(self.window.winfo_height(), available_height)
        height = opening_height

        # Scrollbar visibility can change the responsive layout width. Settle
        # and remeasure until the content-fit height stabilizes.
        for _ in range(self.CONTENT_FIT_SETTLE_PASSES):
            self.window.geometry(f"{width}x{height}")
            self.window.update_idletasks()
            measured_height = self.window.winfo_height()
            viewport_height = self._content_viewport_height(
                measured_height,
                self.footer.winfo_reqheight(),
            )
            self._settle_content_layout(width, viewport_height)
            bounds = self.scroll_canvas.bbox("all")
            content_height = bounds[3] - bounds[1] if bounds is not None else 0
            fitted_height = self._content_fitted_height(
                opening_height,
                measured_height,
                content_height,
                viewport_height,
                available_height,
            )
            if fitted_height == measured_height:
                height = fitted_height
                break
            height = fitted_height

        x = max(4, (screen_width - width) // 2)
        y = max(4, (screen_height - height - 32) // 2)
        self.window.geometry(f"{width}x{height}+{x}+{y}")

    def show(self) -> None:
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()

    def update_keystroke_count(self, count: int) -> None:
        self.usage_metrics.total_keystrokes = max(0, count)
        self._refresh_usage_metrics()

    def update_usage_metrics(self, metrics: UsageMetrics) -> None:
        self.usage_metrics = metrics
        self._refresh_usage_metrics()

    def set_update_status(self, text: str, checking: bool = False) -> None:
        self.update_status_text.set(text)
        state = (
            "disabled"
            if checking or self._on_check_for_updates is None
            else "normal"
        )
        self.check_for_updates_button.configure(state=state)
        self.check_for_updates_button.configure(cursor="arrow")

    def close(self) -> None:
        try:
            if self._after_id is not None:
                self.window.after_cancel(self._after_id)
                self._after_id = None
            self.window.destroy()
        except tk.TclError:
            pass
        finally:
            on_close = self._on_close
            self._on_close = None
            if on_close is not None:
                on_close()
