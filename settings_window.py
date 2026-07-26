from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from cat_settings import AppSettings


CAT_STYLE_LABELS = {
    "Alternate gray and ginger": "alternate",
    "Gray tabby": "gray",
    "Ginger tabby": "ginger",
}
PLACEMENT_LABELS = {
    "Above and to the right": "above-right",
    "Above and to the left": "above-left",
    "Below and to the right": "below-right",
    "Below and to the left": "below-left",
}


class SettingsWindow:
    BACKGROUND = "#f6f4ef"
    CARD = "#ffffff"
    INK = "#25221f"
    MUTED = "#716b64"
    ACCENT = "#d75c37"

    def __init__(
        self,
        parent: tk.Misc,
        settings: AppSettings,
        on_save: Callable[[AppSettings], None],
        icon_path: str | None = None,
    ) -> None:
        self._on_save = on_save
        self.window = tk.Toplevel(parent)
        self.window.title("Cat Type Settings")
        self.window.geometry("570x690")
        self.window.minsize(530, 640)
        self.window.configure(background=self.BACKGROUND)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
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

        self._configure_styles()
        self._build()
        self._center()
        self.window.lift()
        self.window.focus_force()

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
            "Cat.TCheckbutton",
            background=self.CARD,
            foreground=self.INK,
            font=("Segoe UI", 10),
        )
        style.map(
            "Cat.TCheckbutton",
            background=[("active", self.CARD)],
        )
        style.configure(
            "Cat.TCombobox",
            padding=7,
            fieldbackground="#fbfaf8",
            background="#fbfaf8",
            foreground=self.INK,
        )
        style.configure(
            "Cat.Horizontal.TScale",
            background=self.CARD,
            troughcolor="#e7e1da",
        )
        style.configure(
            "Accent.TButton",
            padding=(18, 9),
            background=self.ACCENT,
            foreground="#ffffff",
            font=("Segoe UI Semibold", 10),
        )
        style.map(
            "Accent.TButton",
            background=[("active", "#bc4828"), ("pressed", "#a83e22")],
        )
        style.configure(
            "Quiet.TButton",
            padding=(18, 9),
            background="#e9e4dd",
            foreground=self.INK,
            font=("Segoe UI", 10),
        )

    def _build(self) -> None:
        canvas = tk.Canvas(
            self.window,
            background=self.BACKGROUND,
            highlightthickness=0,
        )
        scrollbar = ttk.Scrollbar(
            self.window,
            orient="vertical",
            command=canvas.yview,
        )
        body = tk.Frame(canvas, background=self.BACKGROUND)
        body.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas_window = canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(canvas_window, width=event.width),
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        self.window.bind(
            "<MouseWheel>",
            lambda event: canvas.yview_scroll(
                -1 if event.delta > 0 else 1,
                "units",
            ),
        )
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        header = tk.Frame(body, background=self.BACKGROUND)
        header.pack(fill="x", padx=30, pady=(28, 18))
        tk.Label(
            header,
            text="Cat Type",
            background=self.BACKGROUND,
            foreground=self.INK,
            font=("Segoe UI Semibold", 24),
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Tune your tiny typing companion.",
            background=self.BACKGROUND,
            foreground=self.MUTED,
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(3, 0))

        general = self._card(body, "General")
        ttk.Checkbutton(
            general,
            text="Show the cat while I type",
            variable=self.enabled,
            style="Cat.TCheckbutton",
        ).pack(anchor="w")
        ttk.Checkbutton(
            general,
            text="Start Cat Type when I sign in to Windows",
            variable=self.launch_at_startup,
            style="Cat.TCheckbutton",
        ).pack(anchor="w", pady=(12, 0))

        appearance = self._card(body, "Appearance")
        self._field_label(appearance, "Cat color").pack(anchor="w")
        ttk.Combobox(
            appearance,
            textvariable=self.cat_style,
            values=list(CAT_STYLE_LABELS),
            state="readonly",
            style="Cat.TCombobox",
        ).pack(fill="x", pady=(6, 14))
        self._field_label(appearance, "Preferred position").pack(anchor="w")
        ttk.Combobox(
            appearance,
            textvariable=self.placement,
            values=list(PLACEMENT_LABELS),
            state="readonly",
            style="Cat.TCombobox",
        ).pack(fill="x", pady=(6, 16))
        self._slider(
            appearance,
            "Cat size",
            self.size_percent,
            60,
            175,
            lambda value: f"{round(float(value))}%",
        )

        timing = self._card(body, "Timing")
        self._slider(
            timing,
            "Stay visible after typing",
            self.hold_seconds,
            0.5,
            5.0,
            lambda value: f"{float(value):.1f}s",
        )
        self._slider(
            timing,
            "Fade duration",
            self.fade_seconds,
            0.0,
            1.5,
            lambda value: f"{float(value):.1f}s",
            top_padding=16,
        )

        tk.Label(
            body,
            text="Cat Type detects keyboard activity only—it never records what you type.\n"
            "You can always quit with Ctrl+Alt+Q or from the tray icon.",
            justify="left",
            background=self.BACKGROUND,
            foreground=self.MUTED,
            font=("Segoe UI", 9),
        ).pack(fill="x", padx=32, pady=(4, 18))

        buttons = tk.Frame(body, background=self.BACKGROUND)
        buttons.pack(fill="x", padx=30, pady=(0, 28))
        ttk.Button(
            buttons,
            text="Cancel",
            command=self.close,
            style="Quiet.TButton",
        ).pack(side="right")
        ttk.Button(
            buttons,
            text="Save changes",
            command=self._save,
            style="Accent.TButton",
        ).pack(side="right", padx=(0, 10))

    def _card(self, parent: tk.Misc, title: str) -> tk.Frame:
        outer = tk.Frame(
            parent,
            background=self.CARD,
            highlightbackground="#e7e1da",
            highlightthickness=1,
        )
        outer.pack(fill="x", padx=30, pady=(0, 16))
        tk.Label(
            outer,
            text=title.upper(),
            background=self.CARD,
            foreground=self.ACCENT,
            font=("Segoe UI Semibold", 9),
        ).pack(anchor="w", padx=20, pady=(17, 13))
        content = tk.Frame(outer, background=self.CARD)
        content.pack(fill="x", padx=20, pady=(0, 19))
        return content

    def _field_label(self, parent: tk.Misc, text: str) -> tk.Label:
        return tk.Label(
            parent,
            text=text,
            background=self.CARD,
            foreground=self.INK,
            font=("Segoe UI", 10),
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
            background=self.CARD,
            foreground=self.MUTED,
            font=("Segoe UI Semibold", 9),
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
        scale.pack(fill="x", pady=(8, 0))
        update(str(variable.get()))

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

    def _center(self) -> None:
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() - width) // 2
        y = max(20, (self.window.winfo_screenheight() - height) // 2)
        self.window.geometry(f"{width}x{height}+{x}+{y}")

    def show(self) -> None:
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()

    def close(self) -> None:
        try:
            self.window.destroy()
        except tk.TclError:
            pass
