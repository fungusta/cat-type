"""Achievement requirements and progress, separate from outfit selection."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

from PIL import ImageTk

from achievements import progress, requirement
from cat_accessories import Accessory, visible_accessories
from cat_artwork import load_frame
from usage_metrics import UsageMetrics
from ui_surfaces import RoundedPanel


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
        self.cards: dict[str, RoundedPanel] = {}
        self.new_badges: dict[str, tk.Label] = {}
        self._new_ids: set[str] = set()
        self.progress_text: dict[str, tk.StringVar] = {}
        self._thumbnails: list[ImageTk.PhotoImage] = []
        self.summary = tk.StringVar(master=self)
        tk.Label(self, textvariable=self.summary, font=fonts["section"],
                 bg=palette["background"], fg=palette["ink"]).pack(anchor="w")
        self.cards_area = tk.Frame(self, background=palette["background"])
        self.cards_area.pack(fill="x", pady=(10, 0))
        self.cards_area.bind("<Configure>", self._layout_cards, add="+")

        self.update_progress(metrics, unlocked)

    def _build_cards(self, visible: tuple[Accessory, ...]) -> None:
        for card in self.cards.values():
            card.destroy()
        self.cards.clear()
        self.new_badges.clear()
        self.progress_text.clear()
        self._thumbnails.clear()
        palette, fonts, assets_root = self.palette, self.fonts, self.assets_root
        for item in visible:
            card = RoundedPanel(
                self.cards_area,
                background=palette["background"],
                fill=palette["card"],
                border=palette["border"],
                radius=16,
                padding=10,
                takefocus=True,
            )
            self.cards[item.id] = card
            content = card.content
            with load_frame(assets_root, "white", "idle", 64, **{item.slot: item.id}) as frame:
                thumbnail = ImageTk.PhotoImage(frame, master=self)
            self._thumbnails.append(thumbnail)
            tk.Label(content, image=thumbnail, bg=palette["card"]).pack(side="left", padx=2, pady=2)
            copy = tk.Frame(content, background=palette["card"])
            copy.pack(side="left", fill="x", expand=True, padx=(0, 12), pady=10)
            heading = tk.Frame(copy, background=palette["card"])
            heading.pack(fill="x")
            tk.Label(heading, text=item.achievement, font=fonts["control"], anchor="w",
                     bg=palette["card"], fg=palette["ink"]).pack(side="left")
            badge = tk.Label(heading, text="", font=fonts["small"], anchor="e",
                             bg=palette["peach"], fg=palette["accent_dark"], padx=6, pady=1)
            badge.pack(side="right", padx=(8, 0))
            self.new_badges[item.id] = badge
            tk.Label(copy, text=f"Reward: {item.name}", font=fonts["small"], anchor="w",
                     bg=palette["card"], fg=palette["ink"]).pack(fill="x", pady=(2, 0))
            tk.Label(copy, text=requirement(item), font=fonts["small"], anchor="w",
                     wraplength=340, justify="left",
                     bg=palette["card"], fg=palette["muted"]).pack(fill="x", pady=(4, 0))
            value = tk.StringVar(master=self)
            self.progress_text[item.id] = value
            tk.Label(copy, textvariable=value, font=fonts["small"], anchor="w",
                     bg=palette["card"], fg=palette["accent_dark"]).pack(fill="x", pady=(2, 0))
        self._layout_cards()

    def _layout_cards(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        width = self.cards_area.winfo_width()
        if width <= 1:
            return
        columns = 2 if width >= 600 else 1
        for column in range(2):
            self.cards_area.grid_columnconfigure(
                column,
                weight=1 if column < columns else 0,
                uniform="achievement-cards" if column < columns else "",
            )
        for index, card in enumerate(self.cards.values()):
            row, column = divmod(index, columns)
            card.grid(
                row=row,
                column=column,
                sticky="nsew",
                padx=(0 if column == 0 else 8, 0),
                pady=(0, 10),
            )

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
            self.new_badges[item.id].configure(text="NEW" if item.id in self._new_ids else "")
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
        self._new_ids.discard(accessory_id)
        self.new_badges[accessory_id].configure(text="")
        card.focus_set()
        return card

    def mark_new(self, newly_unlocked: tuple[Accessory, ...]) -> None:
        self._new_ids.update(item.id for item in newly_unlocked)
        for item in newly_unlocked:
            badge = self.new_badges.get(item.id)
            if badge is not None:
                badge.configure(text="NEW")
