"""Achievement requirements and progress, separate from outfit selection."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

from PIL import ImageTk

from achievements import progress, requirement
from cat_accessories import Accessory, visible_accessories
from cat_artwork import load_frame
from usage_metrics import UsageMetrics
from ui_surfaces import RoundedBadge, RoundedPanel, PaginationControls
from pagination import page_window, page_slice


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
        self._visible_items: tuple[Accessory, ...] = ()
        self._page_index = 0
        self._page_size = 4
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

        self.pagination_controls = PaginationControls(
            album_content, on_previous=lambda: self.show_page(self._page_index - 1),
            on_next=lambda: self.show_page(self._page_index + 1),
            palette={**palette, "background": palette["card"]},
            fonts={**fonts, "button": fonts["small"]},
        )
        self.pagination_controls.pack(anchor="center", pady=(0, 12))
        self.update_progress(metrics, unlocked)

    def _build_cards(self, visible: tuple[Accessory, ...]) -> None:
        for card in self.cards.values():
            card.destroy()
        self.cards.clear()
        self.new_badges.clear()
        self.status_badges.clear()
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
            title = tk.Label(heading, text=item.achievement, font=fonts["control"], anchor="w",
                             justify="left", wraplength=180, bg=palette["card"], fg=palette["ink"])
            title.pack(side="left", fill="x", expand=True)
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
            value = self.progress_text[item.id]
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
                lambda event, labels=(title, reward_label, requirement_label, progress_label),
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
        wraplength = max(1, int(event.width) - 4)
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
        size = 4 if width >= 520 else 2
        if size != self._page_size:
            start = self._page_index * self._page_size
            self._page_size = size
            self.show_page(start // size)
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

    def page_for_item(self, accessory_id: str) -> int:
        for index, item in enumerate(self._visible_items):
            if item.id == accessory_id:
                return index // self._page_size
        raise KeyError(accessory_id)

    def show_page(self, page_index: int) -> None:
        window = page_window(len(self._visible_items), page_index, self._page_size)
        self._page_index = window.index
        items = page_slice(self._visible_items, window.index, self._page_size)
        if tuple(self.cards) != tuple(item.id for item in items):
            self._build_cards(items)
        self.pagination_controls.set_state(window)
        self._refresh_badges()
        self._layout_cards()
        self._sync_album_size()
        self._schedule_album_layout()

    def update_progress(self, metrics: UsageMetrics, unlocked: set[str]) -> None:
        self._visible_items = visible_accessories(unlocked)
        self._visible_ids = tuple(item.id for item in self._visible_items)
        self._unlocked = set(unlocked)
        earned_count = sum(item.id in unlocked for item in self._visible_items)
        self.summary.set(f"{earned_count} of {len(self._visible_items)} achievements unlocked")
        for item in self._visible_items:
            if item.id not in self.progress_text:
                self.progress_text[item.id] = tk.StringVar(master=self)
            if item.id in unlocked:
                value = "Unlocked"
            else:
                current = progress(item, metrics)
                unit = " days" if item.metric == "days" else ""
                value = f"{current:,} / {item.target:,}{unit} · Locked"
            if self.progress_text[item.id].get() != value:
                self.progress_text[item.id].set(value)
        self.show_page(self._page_index)

    def _refresh_badges(self) -> None:
        for item_id, badge in self.new_badges.items():
            if item_id in self._new_ids:
                badge.pack(side="right", padx=(8, 0))
            else:
                badge.pack_forget()
            earned = item_id in self._unlocked
            self.status_badges[item_id].configure(
                text="Unlocked" if earned else "Locked",
                fill=self.palette["accent"] if earned else self.palette["card"],
                foreground=self.palette["ink"] if earned else self.palette["muted"],
            )

    def focus_reward(self, accessory_id: str) -> tk.Frame:
        self.show_page(self.page_for_item(accessory_id))
        self.update_idletasks()
        if self.page_for_item(accessory_id) != self._page_index:
            self.show_page(self.page_for_item(accessory_id))
            self.update_idletasks()
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
