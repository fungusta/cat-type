"""Tk wardrobe choices and achievement progress, independent of app persistence."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Callable

from PIL import ImageTk

from achievements import progress
from cat_accessories import ACCESSORIES, Accessory
from cat_artwork import load_frame
from usage_metrics import UsageMetrics


class WardrobeView(tk.Frame):
    def __init__(
        self, parent: tk.Misc, *, assets_root: Path,
        hat: tk.StringVar, glasses: tk.StringVar, unlocked: set[str],
        metrics: UsageMetrics, on_change: Callable[[], None],
        palette: dict[str, str], fonts: dict,
    ) -> None:
        super().__init__(parent, background=palette["background"])
        self.palette = palette
        self.slots = {"hat": hat, "glasses": glasses}
        self.unlocked = set(unlocked)
        self.on_change = on_change
        self.buttons: dict[str, tk.Radiobutton] = {}
        self.none_buttons: dict[str, tk.Radiobutton] = {}
        self.progress_text: dict[str, tk.StringVar] = {}
        self._thumbnails: list[ImageTk.PhotoImage] = []
        self._preview_frame: ImageTk.PhotoImage | None = None
        self.notice = tk.StringVar(master=self, value="")

        preview_card = tk.Frame(self, background=palette["peach"])
        preview_card.pack(fill="x", pady=(0, 12))
        self.preview = tk.Label(preview_card, background=palette["peach"], width=1, height=1)
        # Pixel width/height apply once an image is assigned; the settings animation
        # supplies it before the window's content is measured.
        self.preview.pack(side="left", padx=(12, 14), pady=4)
        preview_copy = tk.Frame(preview_card, background=palette["peach"])
        preview_copy.pack(side="left", fill="both", expand=True, pady=20)
        tk.Label(preview_copy, text="Your outfit", font=fonts["section"],
                 bg=palette["peach"], fg=palette["ink"]).pack(anchor="w")
        tk.Label(preview_copy, text="One outfit for all cats.\nSave to apply your choices.",
                 justify="left", font=fonts["body"], bg=palette["peach"],
                 fg=palette["ink"]).pack(anchor="w", pady=(8, 0))
        tk.Label(preview_copy, textvariable=self.notice, justify="left", wraplength=300,
                 font=fonts["small"], bg=palette["peach"],
                 fg=palette["accent_dark"]).pack(anchor="w", pady=(8, 0))

        for slot, title in (("hat", "Hats"), ("glasses", "Glasses")):
            header = tk.Frame(self, background=palette["background"])
            header.pack(fill="x", pady=(6, 8))
            tk.Label(header, text=title, font=fonts["section"],
                     bg=palette["background"], fg=palette["ink"]).pack(side="left")
            none_button = tk.Radiobutton(
                header, text="None", variable=self.slots[slot], value="none",
                command=self._choose, indicatoron=False, font=fonts["small"],
                background=palette["card"], selectcolor=palette["peach"],
                activebackground=palette["peach"], foreground=palette["ink"],
                relief="flat", borderwidth=0, padx=12, pady=5,
                highlightthickness=1, highlightcolor=palette["accent"],
                highlightbackground=palette["border"], takefocus=True,
            )
            none_button.pack(side="right")
            self.none_buttons[slot] = none_button
            choices = tk.Frame(self, background=palette["background"])
            choices.pack(fill="x", pady=(0, 10))
            for column, item in enumerate(item for item in ACCESSORIES if item.slot == slot):
                choices.grid_columnconfigure(column, weight=1, uniform=slot)
                tile = tk.Frame(choices, background=palette["card"],
                                highlightthickness=1, highlightbackground=palette["border"])
                tile.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0))
                with load_frame(assets_root, "white", "idle", 76, **{slot: item.id}) as frame:
                    thumbnail = ImageTk.PhotoImage(frame, master=self)
                self._thumbnails.append(thumbnail)
                button = tk.Radiobutton(
                    tile, text=item.name, image=thumbnail, compound="top",
                    variable=self.slots[slot], value=item.id, command=self._choose,
                    indicatoron=False, font=fonts["control"], foreground=palette["ink"],
                    background=palette["card"], selectcolor=palette["peach"],
                    activebackground=palette["peach"], disabledforeground=palette["muted"],
                    highlightthickness=2, highlightbackground=palette["card"],
                    highlightcolor=palette["accent"], relief="flat", borderwidth=0,
                    wraplength=140, padx=6, pady=4, takefocus=True,
                )
                button.pack(fill="x")
                self.buttons[item.id] = button
                tk.Label(tile, text=item.achievement, font=fonts["small"],
                         bg=palette["card"], fg=palette["ink"], wraplength=145).pack(padx=5, pady=(4, 2))
                requirement = (
                    f"Type on {item.target} different days"
                    if item.metric == "days" else f"{item.target:,} total keystrokes"
                )
                tk.Label(tile, text=requirement, font=fonts["tiny"],
                         bg=palette["card"], fg=palette["muted"], wraplength=145).pack(padx=5)
                value = tk.StringVar(master=self)
                self.progress_text[item.id] = value
                tk.Label(tile, textvariable=value, font=fonts["small"],
                         bg=palette["card"], fg=palette["accent_dark"],
                         wraplength=145).pack(padx=5, pady=(4, 8))
        self.update_progress(metrics, unlocked)

    def _choose(self) -> None:
        self._refresh_selection()
        self.on_change()

    def _refresh_selection(self) -> None:
        for item in ACCESSORIES:
            selected = self.slots[item.slot].get() == item.id
            self.buttons[item.id].configure(
                highlightbackground=self.palette["accent"] if selected else self.palette["card"],
            )

    def set_preview(self, frame: ImageTk.PhotoImage) -> None:
        self._preview_frame = frame
        self.preview.configure(image=frame, width=148, height=148)

    def update_progress(
        self, metrics: UsageMetrics, unlocked: set[str],
        newly_unlocked: tuple[Accessory, ...] = (),
    ) -> None:
        self.unlocked = set(unlocked)
        for item in ACCESSORIES:
            earned = item.id in self.unlocked
            self.buttons[item.id].configure(state="normal" if earned else "disabled")
            current = progress(item, metrics)
            unit = " days" if item.metric == "days" else ""
            value = "Unlocked" if earned else f"{current:,} / {item.target:,}{unit} · Locked"
            if self.progress_text[item.id].get() != value:
                self.progress_text[item.id].set(value)
        if newly_unlocked:
            self.notice.set("Unlocked: " + ", ".join(item.name for item in newly_unlocked))
        self._refresh_selection()
