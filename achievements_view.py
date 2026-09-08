"""Achievement requirements and progress, separate from outfit selection."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

from PIL import ImageTk

from achievements import progress, requirement
from cat_accessories import Accessory, visible_accessories
from cat_artwork import load_frame
from usage_metrics import UsageMetrics


class AchievementsView(tk.Frame):
    def __init__(
        self, parent: tk.Misc, *, assets_root: Path, metrics: UsageMetrics,
        unlocked: set[str], palette: dict[str, str], fonts: dict,
    ) -> None:
        super().__init__(parent, background=palette["background"])
        self.palette = palette
        self.fonts = fonts
        self.assets_root = assets_root
        self._visible_ids: tuple[str, ...] = ()
        self.cards: dict[str, tk.Frame] = {}
        self.progress_text: dict[str, tk.StringVar] = {}
        self._thumbnails: list[ImageTk.PhotoImage] = []
        self.summary = tk.StringVar(master=self)
        tk.Label(self, textvariable=self.summary, font=fonts["section"],
                 bg=palette["background"], fg=palette["ink"]).pack(anchor="w")
        tk.Label(self, text="Equip unlocked rewards in Wardrobe.", font=fonts["body"],
                 bg=palette["background"], fg=palette["muted"]).pack(anchor="w", pady=(4, 14))

        self.update_progress(metrics, unlocked)

    def _build_cards(self, visible: tuple[Accessory, ...]) -> None:
        for card in self.cards.values():
            card.destroy()
        self.cards.clear()
        self.progress_text.clear()
        self._thumbnails.clear()
        palette, fonts, assets_root = self.palette, self.fonts, self.assets_root
        for item in visible:
            card = tk.Frame(self, background=palette["card"], takefocus=True,
                            highlightthickness=2, highlightbackground=palette["border"],
                            highlightcolor=palette["accent"])
            card.pack(fill="x", pady=(0, 10))
            self.cards[item.id] = card
            with load_frame(assets_root, "white", "idle", 64, **{item.slot: item.id}) as frame:
                thumbnail = ImageTk.PhotoImage(frame, master=self)
            self._thumbnails.append(thumbnail)
            tk.Label(card, image=thumbnail, bg=palette["card"]).pack(side="left", padx=12, pady=10)
            copy = tk.Frame(card, background=palette["card"])
            copy.pack(side="left", fill="x", expand=True, padx=(0, 12), pady=10)
            tk.Label(copy, text=item.achievement, font=fonts["control"], anchor="w",
                     bg=palette["card"], fg=palette["ink"]).pack(fill="x")
            tk.Label(copy, text=f"Reward: {item.name}", font=fonts["small"], anchor="w",
                     bg=palette["card"], fg=palette["ink"]).pack(fill="x", pady=(2, 0))
            tk.Label(copy, text=requirement(item), font=fonts["small"], anchor="w",
                     wraplength=340, justify="left",
                     bg=palette["card"], fg=palette["muted"]).pack(fill="x", pady=(4, 0))
            value = tk.StringVar(master=self)
            self.progress_text[item.id] = value
            tk.Label(copy, textvariable=value, font=fonts["small"], anchor="w",
                     bg=palette["card"], fg=palette["accent_dark"]).pack(fill="x", pady=(2, 0))

    def update_progress(self, metrics: UsageMetrics, unlocked: set[str]) -> None:
        visible = visible_accessories(unlocked)
        visible_ids = tuple(item.id for item in visible)
        if visible_ids != self._visible_ids:
            self._build_cards(visible)
            self._visible_ids = visible_ids
        earned_count = sum(item.id in unlocked for item in visible)
        summary = f"{earned_count} of {len(visible)} achievements unlocked"
        if self.summary.get() != summary:
            self.summary.set(summary)
        for item in visible:
            if item.id in unlocked:
                value = "Unlocked"
            else:
                current = progress(item, metrics)
                unit = " days" if item.metric == "days" else ""
                value = f"{current:,} / {item.target:,}{unit} · Locked"
            if self.progress_text[item.id].get() != value:
                self.progress_text[item.id].set(value)

    def focus_reward(self, accessory_id: str) -> tk.Frame:
        card = self.cards[accessory_id]
        card.focus_set()
        return card
