"""Achievement requirements and progress, separate from outfit selection."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

from PIL import ImageTk

from achievements import progress, requirement
from cat_accessories import Accessory, visible_accessories
from cat_artwork import load_frame
from usage_metrics import UsageMetrics
from ui_surfaces import RoundedBadge, RoundedPanel


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
        self.new_badges: dict[str, RoundedBadge] = {}
        self.status_badges: dict[str, RoundedBadge] = {}
        self._new_ids: set[str] = set()
        self.progress_text: dict[str, tk.StringVar] = {}
        self._thumbnails: list[ImageTk.PhotoImage] = []
        self._album_layout_after_id: str | None = None
        self._pending_resize_card: RoundedPanel | None = None
        self.summary = tk.StringVar(master=self)
        self.album_shelf = RoundedPanel(
            self,
            background=palette["background"],
            fill=palette["card"],
            border=palette["border"],
            radius=18,
            padding=10,
        )
        self.album_shelf.pack(fill="x")
        album_content = self.album_shelf.content
        album_heading = tk.Frame(album_content, background=palette["card"])
        album_heading.pack(fill="x", padx=10, pady=(8, 10))
        tk.Label(
            album_heading,
            text="Reward album",
            font=fonts["section"],
            bg=palette["card"],
            fg=palette["ink"],
        ).pack(side="left")
        tk.Label(
            album_heading,
            textvariable=self.summary,
            font=fonts["small"],
            bg=palette["card"],
            fg=palette["muted"],
        ).pack(side="right")
        self.cards_area = tk.Frame(album_content, background=palette["card"])
        self.cards_area.pack(fill="x", padx=10, pady=(0, 10))
        self.cards_area.bind("<Configure>", self._layout_cards, add="+")
        self.cards_area.bind(
            "<Configure>",
            lambda _event: self._schedule_album_layout(),
            add="+",
        )

        self.update_progress(metrics, unlocked)

    def _build_cards(self, visible: tuple[Accessory, ...]) -> None:
        for card in self.cards.values():
            card.destroy()
        self.cards.clear()
        self.new_badges.clear()
        self.status_badges.clear()
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
                padding=8,
                takefocus=True,
            )
            self.cards[item.id] = card
            content = card.content
            with load_frame(assets_root, "white", "idle", 54, **{item.slot: item.id}) as frame:
                thumbnail = ImageTk.PhotoImage(frame, master=self)
            self._thumbnails.append(thumbnail)
            content.grid_columnconfigure(1, weight=1)
            tk.Label(
                content,
                image=thumbnail,
                bg=palette["card"],
            ).grid(row=0, column=0, rowspan=2, padx=(2, 12), pady=2)
            copy = tk.Frame(content, background=palette["card"])
            copy.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=(4, 2))
            heading = tk.Frame(copy, background=palette["card"])
            heading.pack(fill="x")
            tk.Label(heading, text=item.achievement, font=fonts["control"], anchor="w",
                     bg=palette["card"], fg=palette["ink"]).pack(side="left")
            badge = RoundedBadge(
                heading,
                text="NEW",
                font=fonts["small"],
            )
            self.new_badges[item.id] = badge
            reward_label = tk.Label(
                copy,
                text=f"Reward · {item.name}",
                font=fonts["small"],
                anchor="w",
                wraplength=180,
                bg=palette["card"],
                fg=palette["ink"],
            )
            reward_label.pack(fill="x", pady=(2, 0))
            requirement_label = tk.Label(
                copy,
                text=requirement(item),
                font=fonts["small"],
                anchor="w",
                justify="left",
                wraplength=180,
                bg=palette["card"],
                fg=palette["muted"],
            )
            requirement_label.pack(fill="x", pady=(4, 0))
            value = tk.StringVar(master=self)
            self.progress_text[item.id] = value
            progress_label = tk.Label(
                copy,
                textvariable=value,
                font=fonts["small"],
                anchor="w",
                justify="left",
                wraplength=180,
                bg=palette["card"],
                fg=palette["accent_dark"],
            )
            progress_label.pack(fill="x", pady=(2, 0))
            copy.bind(
                "<Configure>",
                lambda event, labels=(reward_label, requirement_label, progress_label),
                    reward_card=card: self._fit_reward_copy(event, labels, reward_card),
                add="+",
            )
            status = RoundedBadge(
                content,
                text="Locked",
                font=fonts["small"],
                fill=palette["card"],
                foreground=palette["muted"],
            )
            status.grid(row=0, column=2, rowspan=2, padx=(4, 2), pady=4, sticky="e")
            self.status_badges[item.id] = status
        self._layout_cards()
        # The album owns a nested grid, so its first size negotiation can
        # happen before the reward rows have requested their full height.
        # Re-sync the shelf after the rows exist to keep scrolling accurate.
        self._sync_album_size()
        self._schedule_album_layout()

    def _fit_reward_copy(
        self,
        event: tk.Event[tk.Misc],
        labels: tuple[tk.Label, ...],
        card: RoundedPanel,
    ) -> None:
        wraplength = max(110, int(event.width) - 4)
        changed = False
        for label in labels:
            if int(label.cget("wraplength")) != wraplength:
                label.configure(wraplength=wraplength)
                changed = True
        if changed:
            self._schedule_album_layout(card)

    def _schedule_album_layout(self, card: RoundedPanel | None = None) -> None:
        if not self.winfo_exists():
            return
        if card is not None:
            self._pending_resize_card = card
        if self._album_layout_after_id is None:
            self._album_layout_after_id = self.after_idle(self._run_album_layout)

    def _run_album_layout(self) -> None:
        self._album_layout_after_id = None
        if not self.winfo_exists():
            return
        card = getattr(self, "_pending_resize_card", None)
        self._pending_resize_card = None
        if card is not None and card.winfo_exists():
            card._sync_size()
        self.refresh_layout()

    def _layout_cards(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        width = self.cards_area.winfo_width()
        if width <= 1:
            return
        # Keep two cards at high Tk scaling when the rail grows for its
        # longer unread label; the narrow 620 px layout remains one column.
        columns = 2 if width >= 520 else 1
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

    def refresh_layout(self) -> None:
        """Reconcile the album shelf after it is mapped into the scroll canvas."""
        available_width = self.winfo_width()
        if available_width > 1:
            # RoundedPanel keeps an explicit width once it has measured its
            # first content pass. Re-anchor that width to the page host so a
            # high display scale cannot leave a stale wide request behind.
            if self.album_shelf.winfo_width() != available_width:
                self.album_shelf.configure(width=available_width)
        self._layout_cards()
        self._sync_album_size()

    def _sync_album_size(self) -> None:
        """Let the nested reward grid contribute its full requested height."""
        self.cards_area.update_idletasks()
        requested_height = self.cards_area.winfo_reqheight()
        self.cards_area.pack_propagate(False)
        height = max(1, requested_height)
        if self.cards_area.winfo_height() != height:
            self.cards_area.configure(height=height)
        self.album_shelf._sync_size()

    def destroy(self) -> None:
        if self._album_layout_after_id is not None:
            try:
                self.after_cancel(self._album_layout_after_id)
            except tk.TclError:
                pass
            self._album_layout_after_id = None
        super().destroy()

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
            badge = self.new_badges[item.id]
            if item.id in self._new_ids:
                badge.pack(side="right", padx=(8, 0))
            else:
                badge.pack_forget()
            if item.id in unlocked:
                value = "Unlocked"
                self.status_badges[item.id].configure(
                    text="Unlocked",
                    fill=self.palette["accent"],
                    foreground=self.palette["ink"],
                )
            else:
                current = progress(item, metrics)
                unit = " days" if item.metric == "days" else ""
                value = f"{current:,} / {item.target:,}{unit} · Locked"
                self.status_badges[item.id].configure(
                    text="Locked",
                    fill=self.palette["card"],
                    foreground=self.palette["muted"],
                )
            if self.progress_text[item.id].get() != value:
                self.progress_text[item.id].set(value)

    def focus_reward(self, accessory_id: str) -> tk.Frame:
        card = self.cards[accessory_id]
        self._new_ids.discard(accessory_id)
        self.new_badges[accessory_id].pack_forget()
        card.focus_set()
        return card

    def mark_new(self, newly_unlocked: tuple[Accessory, ...]) -> None:
        self._new_ids.update(item.id for item in newly_unlocked)
        for item in newly_unlocked:
            badge = self.new_badges.get(item.id)
            if badge is not None:
                badge.pack(side="right", padx=(8, 0))
