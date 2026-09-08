"""Achievement requirements and progress, separate from outfit selection."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

from PIL import ImageTk

from achievements import progress
from cat_accessories import ACCESSORIES
from cat_artwork import load_frame
from usage_metrics import UsageMetrics


class AchievementsView(tk.Frame):
    def __init__(
        self, parent: tk.Misc, *, assets_root: Path, metrics: UsageMetrics,
        unlocked: set[str], palette: dict[str, str], fonts: dict,
    ) -> None:
        super().__init__(parent, background=palette["background"])
        self.palette = palette
        self.cards: dict[str, tk.Frame] = {}
        self.progress_text: dict[str, tk.StringVar] = {}
        self._thumbnails: list[ImageTk.PhotoImage] = []
        self.summary = tk.StringVar(master=self)
        tk.Label(self, textvariable=self.summary, font=fonts["section"],
                 bg=palette["background"], fg=palette["ink"]).pack(anchor="w")
        tk.Label(self, text="Equip unlocked rewards in Wardrobe.", font=fonts["body"],
                 bg=palette["background"], fg=palette["muted"]).pack(anchor="w", pady=(4, 14))

        for item in ACCESSORIES:
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
            requirement = (
                f"Type on {item.target} different days"
                if item.metric == "days" else f"{item.target:,} total keystrokes"
            )
            tk.Label(copy, text=requirement, font=fonts["small"], anchor="w",
                     bg=palette["card"], fg=palette["muted"]).pack(fill="x", pady=(4, 0))
            value = tk.StringVar(master=self)
            self.progress_text[item.id] = value
            tk.Label(copy, textvariable=value, font=fonts["small"], anchor="w",
                     bg=palette["card"], fg=palette["accent_dark"]).pack(fill="x", pady=(2, 0))
        self.update_progress(metrics, unlocked)

    def update_progress(self, metrics: UsageMetrics, unlocked: set[str]) -> None:
        earned_count = sum(item.id in unlocked for item in ACCESSORIES)
        summary = f"{earned_count} of {len(ACCESSORIES)} achievements unlocked"
        if self.summary.get() != summary:
            self.summary.set(summary)
        for item in ACCESSORIES:
            current = progress(item, metrics)
            unit = " days" if item.metric == "days" else ""
            value = "Unlocked" if item.id in unlocked else f"{current:,} / {item.target:,}{unit} · Locked"
            if self.progress_text[item.id].get() != value:
                self.progress_text[item.id].set(value)

    def focus_reward(self, accessory_id: str) -> tk.Frame:
        card = self.cards[accessory_id]
        card.focus_set()
        return card
