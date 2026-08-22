from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk
from typing import Callable

from PIL import Image, ImageDraw, ImageTk

from app_version import APP_VERSION
from cat_settings import AppSettings


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
        description: str,
        background: str,
        accent: str,
        ink: str,
        muted: str,
        title_font: tkfont.Font,
        description_font: tkfont.Font,
    ) -> None:
        super().__init__(parent, background=background, cursor="hand2")
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
        tk.Label(
            copy,
            text=description,
            background=background,
            foreground=muted,
            font=description_font,
            cursor="hand2",
        ).pack(anchor="w", pady=(2, 0))

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

    def __init__(
        self,
        parent: tk.Misc,
        settings: AppSettings,
        on_save: Callable[[AppSettings], None],
        icon_path: str | None = None,
        keystroke_count: int = 0,
        on_check_for_updates: Callable[[], None] | None = None,
        on_open_release_page: Callable[[], None] | None = None,
        update_status: str = "",
        on_close: Callable[[], None] | None = None,
    ) -> None:
        self._on_save = on_save
        self._on_check_for_updates = on_check_for_updates
        self._on_open_release_page = on_open_release_page
        self._on_close = on_close
        self._after_id: str | None = None
        self._preview_step = 0
        self._preview_variant = "gray"
        self._preview_frames: dict[str, dict[str, ImageTk.PhotoImage]] = {}

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
            value=f"{keystroke_count:,}"
        )
        self.update_status_text = tk.StringVar(value=update_status)

        self._configure_styles()
        self._load_preview_frames(icon_path)
        self._build()
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
            "Comic Sans MS",
            "Trebuchet MS",
            "TkDefaultFont",
        )
        badge = pick("Trebuchet MS", body)

        self.fonts = {
            "display": tkfont.Font(
                self.window,
                family=display,
                size=32,
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
            "badge": tkfont.Font(
                self.window,
                family=badge,
                size=9,
                weight="bold",
            ),
            "button": tkfont.Font(
                self.window,
                family=heading,
                size=10,
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
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Cat.TCombobox",
            padding=9,
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
            background=self.CARD,
            troughcolor="#F1E3DC",
            bordercolor=self.CARD,
            lightcolor=self.CARD,
            darkcolor=self.CARD,
            sliderthickness=18,
            gripcount=0,
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

        self._build_header(self.scroll_content)

        columns = tk.Frame(
            self.scroll_content,
            background=self.BACKGROUND,
        )
        columns.pack(fill="x", padx=26)
        columns.grid_columnconfigure(0, weight=3, uniform="settings")
        columns.grid_columnconfigure(1, weight=2, uniform="settings")

        left = tk.Frame(columns, background=self.BACKGROUND)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right = tk.Frame(columns, background=self.BACKGROUND)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        self._build_companion_card(left)
        self._build_appearance_card(left)
        self._build_size_card(right)
        self._build_timing_card(right)
        self._build_updates_card(right)

    def _build_header(self, body: tk.Frame) -> None:
        hero = tk.Frame(
            body,
            background=self.PEACH,
            highlightbackground="#F4C6B3",
            highlightthickness=1,
            height=174,
        )
        hero.pack(fill="x", padx=26, pady=(24, 16))
        hero.pack_propagate(False)

        copy = tk.Frame(hero, background=self.PEACH)
        copy.pack(side="left", fill="both", expand=True, padx=(26, 10), pady=22)
        badge = tk.Label(
            copy,
            text="  YOUR TINY TYPING PAL  ",
            background="#FFFFFF",
            foreground=self.ACCENT_DARK,
            font=self.fonts["badge"],
        )
        badge.pack(anchor="w")
        tk.Label(
            copy,
            text="Make it feel like yours.",
            background=self.PEACH,
            foreground=self.INK,
            font=self.fonts["display"],
        ).pack(anchor="w", pady=(10, 3))
        tk.Label(
            copy,
            text="Choose your cat, its cozy corner, and how long it stays.",
            background=self.PEACH,
            foreground=self.MUTED,
            font=self.fonts["body"],
        ).pack(anchor="w")

        self.preview_canvas = tk.Canvas(
            hero,
            width=250,
            height=166,
            background=self.PEACH,
            highlightthickness=0,
        )
        self.preview_canvas.pack(side="right", padx=(0, 18), pady=10)
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
            font=("Segoe UI Symbol", 13),
        )
        self.preview_canvas.create_text(
            31,
            45,
            text="✦",
            fill="#F3A486",
            font=("Segoe UI Symbol", 8),
        )
        self._preview_image = self.preview_canvas.create_image(126, 84)

    def _build_companion_card(self, parent: tk.Frame) -> None:
        card, content = self._card(
            parent,
            "Companion",
            "The important purr-t",
        )
        Toggle(
            content,
            variable=self.enabled,
            title="Show my cat while I type",
            description="Pause anytime without quitting Cat Type.",
            background=self.CARD,
            accent=self.ACCENT,
            ink=self.INK,
            muted=self.MUTED,
            title_font=self.fonts["control"],
            description_font=self.fonts["small"],
        ).pack(fill="x")
        counter = tk.Frame(content, background=self.BLUSH)
        counter.pack(fill="x", pady=(14, 0))
        self.keystroke_count_title = tk.Label(
            counter,
            text="Keystrokes this session",
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
        Toggle(
            content,
            variable=self.launch_at_startup,
            title="Start Cat Type when I sign in",
            description="Your typing pal will be ready and waiting.",
            background=self.CARD,
            accent=self.ACCENT,
            ink=self.INK,
            muted=self.MUTED,
            title_font=self.fonts["control"],
            description_font=self.fonts["small"],
        ).pack(fill="x")
        self._divider(content).pack(fill="x", pady=13)
        tk.Label(
            content,
            text="⌨  Wakes up when your keyboard does",
            background=self.CARD,
            foreground=self.MUTED,
            font=self.fonts["small"],
        ).pack(anchor="w")
        card.pack(fill="x", pady=(0, 14))

    def _build_appearance_card(self, parent: tk.Frame) -> None:
        card, content = self._card(
            parent,
            "Cat style",
            "Pick a favorite fluff",
        )
        choices = tk.Frame(content, background=self.CARD)
        choices.pack(fill="x", pady=(0, 16))
        for index, label in enumerate(CAT_STYLE_LABELS):
            button = tk.Radiobutton(
                choices,
                text=label,
                variable=self.cat_style,
                value=label,
                indicatoron=False,
                relief="flat",
                borderwidth=0,
                highlightthickness=1,
                highlightbackground=self.BORDER,
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

        self._field_label(content, "Favorite spot").pack(anchor="w")
        ttk.Combobox(
            content,
            textvariable=self.placement,
            values=list(PLACEMENT_LABELS),
            state="readonly",
            style="Cat.TCombobox",
        ).pack(fill="x", pady=(6, 0))
        card.pack(fill="x")

    def _build_size_card(self, parent: tk.Frame) -> None:
        card, content = self._card(parent, "Cat size", "Tiny bean or big floof")
        self._slider(
            content,
            "Preview scale",
            self.size_percent,
            60,
            175,
            lambda value: f"{round(float(value))}%",
        )
        scale_labels = tk.Frame(content, background=self.CARD)
        scale_labels.pack(fill="x", pady=(5, 0))
        for side, label in (("left", "smol"), ("right", "chonky")):
            tk.Label(
                scale_labels,
                text=label,
                background=self.CARD,
                foreground=self.MUTED,
                font=self.fonts["tiny"],
            ).pack(side=side)
        card.pack(fill="x", pady=(0, 14))

    def _build_timing_card(self, parent: tk.Frame) -> None:
        card, content = self._card(parent, "Timing", "Settle in, then fade")
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
        card, content = self._card(
            parent,
            "Updates",
            "Keep your typing pal current",
        )
        self.update_version_label = tk.Label(
            content,
            text=f"Version {APP_VERSION}",
            background=self.CARD,
            foreground=self.INK,
            font=self.fonts["control"],
        )
        self.update_version_label.pack(anchor="w")
        tk.Label(
            content,
            textvariable=self.update_status_text,
            background=self.CARD,
            foreground=self.MUTED,
            font=self.fonts["small"],
            justify="left",
            wraplength=280,
        ).pack(anchor="w", fill="x", pady=(5, 10))
        self.check_for_updates_button = tk.Button(
            content,
            text="Check for updates",
            command=self._on_check_for_updates,
            state="normal" if self._on_check_for_updates else "disabled",
            relief="flat",
            borderwidth=0,
            background=self.PEACH,
            activebackground="#F4C6B3",
            foreground=self.ACCENT_DARK,
            activeforeground=self.ACCENT_DARK,
            disabledforeground=self.MUTED,
            font=self.fonts["button"],
            padx=14,
            pady=8,
            cursor="hand2",
        )
        self.check_for_updates_button.pack(anchor="w")
        self.open_release_page_button = tk.Button(
            content,
            text="Open release page",
            command=self._on_open_release_page,
            state="normal" if self._on_open_release_page else "disabled",
            relief="flat",
            borderwidth=0,
            background=self.CARD,
            activebackground=self.BLUSH,
            foreground=self.ACCENT_DARK,
            activeforeground=self.ACCENT_DARK,
            disabledforeground=self.MUTED,
            font=self.fonts["small"],
            padx=0,
            pady=6,
            cursor="hand2",
        )
        self.open_release_page_button.pack(anchor="w", pady=(4, 0))
        card.pack(fill="x", pady=(0, 14))

    def _build_footer(self, body: tk.Frame) -> tk.Frame:
        footer = tk.Frame(body, background=self.BACKGROUND)
        footer.pack(
            side="bottom",
            fill="x",
            padx=28,
            pady=(12, 14),
        )
        self.footer_message = tk.Label(
            footer,
            text="♡  Only keyboard activity is detected — never what you type.",
            background=self.BACKGROUND,
            foreground=self.MUTED,
            font=self.fonts["small"],
        )

        self.footer_buttons = tk.Frame(
            footer,
            background=self.BACKGROUND,
        )
        self.footer_buttons.pack(side="right")
        tk.Button(
            self.footer_buttons,
            text="Not now",
            command=self.close,
            relief="flat",
            borderwidth=0,
            background="#F1E5DF",
            activebackground="#E8D8D0",
            foreground=self.INK,
            activeforeground=self.INK,
            font=self.fonts["button"],
            padx=18,
            pady=9,
            cursor="hand2",
        ).pack(side="left")
        tk.Button(
            self.footer_buttons,
            text="Save my setup  ♡",
            command=self._save,
            relief="flat",
            borderwidth=0,
            background=self.ACCENT,
            activebackground=self.ACCENT_DARK,
            foreground="#FFFFFF",
            activeforeground="#FFFFFF",
            font=self.fonts["button"],
            padx=18,
            pady=9,
            cursor="hand2",
        ).pack(side="left", padx=(8, 0))
        self.footer_message.pack(side="left", anchor="center")
        footer.bind("<Configure>", self._on_footer_configure)
        return footer

    def _on_footer_configure(
        self,
        event: tk.Event[tk.Misc],
    ) -> None:
        message_fits = event.width >= (
            self.footer_message.winfo_reqwidth()
            + self.footer_buttons.winfo_reqwidth()
        )
        message_is_visible = bool(self.footer_message.winfo_manager())
        if message_fits and not message_is_visible:
            self.footer_message.pack(side="left", anchor="center")
        elif not message_fits and message_is_visible:
            self.footer_message.pack_forget()

    def _card(
        self,
        parent: tk.Misc,
        title: str,
        eyebrow: str,
    ) -> tuple[tk.Frame, tk.Frame]:
        outer = tk.Frame(
            parent,
            background=self.CARD,
            highlightbackground=self.BORDER,
            highlightthickness=1,
        )
        heading = tk.Frame(outer, background=self.CARD)
        heading.pack(fill="x", padx=18, pady=(15, 11))
        tk.Label(
            heading,
            text=title,
            background=self.CARD,
            foreground=self.INK,
            font=self.fonts["section"],
        ).pack(anchor="w")
        tk.Label(
            heading,
            text=eyebrow,
            background=self.CARD,
            foreground=self.ACCENT,
            font=self.fonts["small"],
        ).pack(anchor="w", pady=(1, 0))
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

        scale = ttk.Scale(
            parent,
            from_=minimum,
            to=maximum,
            variable=variable,
            command=update,
            style="Cat.Horizontal.TScale",
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

    def _on_canvas_configure(
        self,
        event: tk.Event[tk.Misc],
    ) -> None:
        self.scroll_canvas.itemconfigure(
            self._scroll_content_id,
            width=event.width,
        )

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
        ).normalized()
        self._on_save(settings)
        self.close()

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
        height = min(self.window.winfo_height(), available_height)
        x = max(4, (screen_width - width) // 2)
        y = max(4, (screen_height - height - 32) // 2)
        self.window.geometry(f"{width}x{height}+{x}+{y}")

    def show(self) -> None:
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()

    def update_keystroke_count(self, count: int) -> None:
        self.keystroke_count_text.set(f"{count:,}")

    def set_update_status(self, text: str, checking: bool = False) -> None:
        self.update_status_text.set(text)
        state = (
            "disabled"
            if checking or self._on_check_for_updates is None
            else "normal"
        )
        self.check_for_updates_button.configure(state=state)

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
