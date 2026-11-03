"""Achievement requirements and progress, separate from outfit selection."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from typing import Callable

from PIL import ImageTk

from achievements import progress, requirement
from cat_accessories import Accessory, visible_accessories
from cat_artwork import load_frame
from usage_metrics import UsageMetrics
from ui_surfaces import RoundedBadge, RoundedPanel, PaginationControls
from pagination import page_window, page_slice


class RewardEntry(tk.Frame):
    """A quiet album entry with a visible native keyboard focus outline."""

    def __init__(self, parent: tk.Misc, *, palette: dict[str, str]) -> None:
        super().__init__(
            parent, background=palette["card"], borderwidth=0,
            highlightthickness=2, highlightbackground=palette["card"],
            highlightcolor=palette["accent_dark"], takefocus=True,
            padx=8, pady=12,
        )
        self.content = self
        self._focused = False
        self._surface = palette["card"]
        self._focus_color = palette["accent_dark"]
        self.bind("<FocusIn>", lambda _event: self._set_focus(True), add="+")
        self.bind("<FocusOut>", lambda _event: self._set_focus(False), add="+")

    def _set_focus(self, focused: bool) -> None:
        self._focused = focused
        self.configure(highlightbackground=self._focus_color if focused else self._surface)


class AchievementsView(tk.Frame):
    def __init__(
        self, parent: tk.Misc, *, assets_root: Path, metrics: UsageMetrics,
        unlocked: set[str], palette: dict[str, str], fonts: dict,
        responsive_width: Callable[[int], int] | None = None,
        on_content_change: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent, background=palette["background"])
        self.palette = palette
        self.fonts = fonts
        self._responsive_width = responsive_width or (lambda width: width)
        self._on_content_change = on_content_change or (lambda: None)
        self.assets_root = assets_root
        self._visible_ids: tuple[str, ...] = ()
        self._visible_items: tuple[Accessory, ...] = ()
        self._page_index = 0
        self._page_size = 4
        self.cards: dict[str, RewardEntry] = {}
        self.new_badges: dict[str, RoundedBadge] = {}
        self._title_labels: dict[str, tk.Label] = {}
        self._reward_heading_keys: dict[str, tuple[int, bool]] = {}
        self.status_badges: dict[str, tk.Label] = {}
        self._progress_labels: dict[str, tk.Label] = {}
        self._separators: list[tk.Frame] = []
        self._new_ids: set[str] = set()
        self.progress_text: dict[str, tk.StringVar] = {}
        self._thumbnails: list[ImageTk.PhotoImage] = []
        self._album_layout_after_id: str | None = None
        self._heading_layout_key: tuple[int, str] | None = None
        self._cards_layout_key: tuple[int, tuple[str, ...]] | None = None
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
        self.album_heading = tk.Frame(album_content, background=palette["card"])
        self.album_heading.pack(fill="x", padx=14, pady=(12, 8))
        self.album_heading.grid_columnconfigure(0, weight=1)
        self.album_title = tk.Label(
            self.album_heading,
            text="Reward album",
            font=fonts["section"],
            bg=palette["card"],
            fg=palette["ink"],
            anchor="w", justify="left", wraplength=240,
            padx=0, pady=0, borderwidth=0,
        )
        self.album_title.grid(row=0, column=0, sticky="w")
        self.summary_label = tk.Label(
            self.album_heading,
            textvariable=self.summary,
            font=fonts["small"],
            bg=palette["card"],
            fg=palette["muted"],
            anchor="w", justify="left", wraplength=240,
            padx=0, pady=0, borderwidth=0,
        )
        self.summary_label.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.album_heading.bind("<Configure>", self._layout_heading, add="+")
        self.cards_area = tk.Frame(album_content, background=palette["card"])
        self.cards_area.pack(fill="x", padx=6, pady=(0, 8))
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

    def _layout_heading(self, event: tk.Event[tk.Misc] | None = None) -> None:
        # Stacking the count keeps the album heading readable at high scaling.
        width = int(event.width) if event is not None else self.album_heading.winfo_width()
        if width <= 1:
            return
        key = (width, self.summary.get())
        if key == self._heading_layout_key:
            return
        self._heading_layout_key = key
        natural_count_width = tkfont.Font(self, font=self.fonts["small"]).measure(self.summary.get()) + 4
        natural_title_width = tkfont.Font(self, font=self.fonts["section"]).measure("Reward album")
        inline = width >= natural_title_width + natural_count_width + 24
        if inline:
            self.summary_label.grid(row=0, column=1, columnspan=1, sticky="e", padx=(20, 0), pady=0)
        else:
            self.summary_label.grid(row=1, column=0, columnspan=2, sticky="ew", padx=0, pady=(4, 0))
        wraplength = max(1, width - 4)
        for label in (self.album_title, self.summary_label):
            if int(label.cget("wraplength")) != wraplength:
                label.configure(wraplength=wraplength)
        self._schedule_album_layout()

    def _build_cards(self, visible: tuple[Accessory, ...]) -> None:
        self._cards_layout_key = None
        for card in self.cards.values():
            card.destroy()
        self.cards.clear()
        self.new_badges.clear()
        self._title_labels.clear()
        self._reward_heading_keys.clear()
        self.status_badges.clear()
        self._progress_labels.clear()
        for separator in self._separators:
            separator.destroy()
        self._separators.clear()
        self._thumbnails.clear()
        palette, fonts, assets_root = self.palette, self.fonts, self.assets_root
        for item in visible:
            card = RewardEntry(self.cards_area, palette=palette)
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
            ).grid(row=0, column=0, padx=(0, 12), pady=2, sticky="n")
            copy = tk.Frame(content, background=palette["card"])
            copy.grid(row=0, column=1, sticky="ew")
            heading = tk.Frame(copy, background=palette["card"])
            heading.pack(fill="x")
            title = tk.Label(heading, text=item.achievement, font=fonts["control"], anchor="w",
                             justify="left", wraplength=180, bg=palette["card"], fg=palette["ink"],
                             padx=0, pady=0, borderwidth=0)
            self._title_labels[item.id] = title
            heading.grid_columnconfigure(0, weight=1)
            title.grid(row=0, column=0, sticky="ew")
            title.bind(
                "<Configure>",
                lambda event, label=title: self._fit_reward_copy(event, (label,)),
                add="+",
            )
            badge = RoundedBadge(
                heading,
                text="NEW",
                font=fonts["small"],
            )
            self.new_badges[item.id] = badge
            heading.bind(
                "<Configure>", lambda _event, item_id=item.id: self._layout_reward_heading(item_id),
                add="+",
            )
            reward_label = tk.Label(
                copy,
                text=f"Reward · {item.name}",
                font=fonts["small"],
                anchor="w",
                justify="left",
                wraplength=180,
                bg=palette["card"],
                fg=palette["muted"],
                padx=0, pady=0, borderwidth=0,
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
                padx=0, pady=0, borderwidth=0,
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
                padx=0, pady=0, borderwidth=0,
            )
            progress_label.pack(fill="x", pady=(6, 0))
            self._progress_labels[item.id] = progress_label
            status = tk.Label(
                copy, text="Locked", font=fonts["small"],
                bg=palette["card"], fg=palette["muted"],
                anchor="w", justify="left", wraplength=180,
                padx=0, pady=0, borderwidth=0,
            )
            status.pack(fill="x", pady=(2, 0))
            self.status_badges[item.id] = status
            copy.bind(
                "<Configure>",
                lambda event, labels=(reward_label, requirement_label, progress_label, status):
                    self._fit_reward_copy(event, labels),
                add="+",
            )
        for _ in range(max(0, len(visible) - 1)):
            self._separators.append(tk.Frame(
                self.cards_area, background=palette["border"], height=1,
                borderwidth=0, takefocus=False,
            ))
        self._layout_cards()
        # The album owns a nested grid, so its first size negotiation can
        # happen before the reward rows have requested their full height.
        # Re-sync the shelf after the rows exist to keep scrolling accurate.
        self._sync_album_size()
        self._schedule_album_layout()

    def _layout_reward_heading(self, item_id: str) -> None:
        badge = self.new_badges[item_id]
        title = self._title_labels[item_id]
        width = badge.master.winfo_width()
        shown = item_id in self._new_ids
        key = (width, shown)
        if key == self._reward_heading_keys.get(item_id):
            return
        self._reward_heading_keys[item_id] = key
        # A badge must never squeeze the title below a readable word. At
        # large system scaling the compact column gives it a separate line.
        minimum_title_width = tkfont.Font(self, font=self.fonts["control"]).measure("Reward")
        inline = width >= badge.winfo_reqwidth() + minimum_title_width + 12
        title.grid_configure(columnspan=1 if shown and inline else 2)
        if not shown:
            badge.grid_remove()
        elif inline:
            badge.grid(row=0, column=1, columnspan=1, padx=(8, 0), pady=0, sticky="ne")
        else:
            badge.grid(row=1, column=0, columnspan=2, padx=0, pady=(6, 0), sticky="w")
        self._schedule_album_layout()

    def _fit_reward_copy(
        self,
        event: tk.Event[tk.Misc],
        labels: tuple[tk.Label, ...],
    ) -> None:
        wraplength = max(1, int(event.width) - 4)
        changed = False
        for label in labels:
            if int(label.cget("wraplength")) != wraplength:
                label.configure(wraplength=wraplength)
                changed = True
        if changed:
            self._schedule_album_layout()

    def _schedule_album_layout(self) -> None:
        if not self.winfo_exists():
            return
        if self._album_layout_after_id is None:
            self._album_layout_after_id = self.after_idle(self._run_album_layout)

    def _run_album_layout(self) -> None:
        self._album_layout_after_id = None
        if not self.winfo_exists():
            return
        self.refresh_layout()

    def _layout_cards(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        width = self.cards_area.winfo_width()
        if width <= 1:
            return
        layout_width = self._responsive_width(width)
        size = 4 if layout_width >= 520 else 2
        if size != self._page_size:
            start = self._page_index * self._page_size
            self._page_size = size
            self.show_page(start // size, reflow=True)
            return
        # Keep two cards at high Tk scaling when the rail grows for its
        # longer unread label; the narrow 620 px layout remains one column.
        columns = 2 if layout_width >= 520 else 1
        key = (columns, tuple(self.cards))
        if key == self._cards_layout_key:
            return
        self._cards_layout_key = key
        for column in range(2):
            self.cards_area.grid_columnconfigure(
                column,
                weight=1 if column < columns else 0,
                uniform="achievement-cards" if column < columns else "",
            )
        for index, card in enumerate(self.cards.values()):
            row, column = divmod(index, columns)
            card.grid(
                row=row * 2,
                column=column,
                sticky="nsew",
                padx=(0 if column == 0 else 8, 0),
                pady=0,
            )
        for separator in self._separators:
            separator.grid_remove()
        for row in range((len(self.cards) - 1) // columns):
            self._separators[row].grid(
                row=row * 2 + 1, column=0, columnspan=columns,
                sticky="ew", padx=8,
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
        self._layout_heading()
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

    def show_page(self, page_index: int, *, reflow: bool = False) -> None:
        if not reflow:
            self._on_content_change()
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
                value = f"{current:,} / {item.target:,}{unit}"
            if self.progress_text[item.id].get() != value:
                self.progress_text[item.id].set(value)
        self.show_page(self._page_index)

    def _refresh_badges(self) -> None:
        for item_id, badge in self.new_badges.items():
            self._layout_reward_heading(item_id)
            earned = item_id in self._unlocked
            self.status_badges[item_id].configure(
                text="Unlocked" if earned else "Locked",
                foreground=self.palette["accent_dark"] if earned else self.palette["muted"],
            )
            label = self._progress_labels[item_id]
            if earned:
                label.pack_forget()
            elif not label.winfo_manager():
                label.pack(fill="x", pady=(6, 0), before=self.status_badges[item_id])

    def focus_reward(self, accessory_id: str) -> tk.Frame:
        self.show_page(self.page_for_item(accessory_id))
        self.update_idletasks()
        if self.page_for_item(accessory_id) != self._page_index:
            self.show_page(self.page_for_item(accessory_id), reflow=True)
            self.update_idletasks()
        card = self.cards[accessory_id]
        self._new_ids.discard(accessory_id)
        self._layout_reward_heading(accessory_id)
        card.focus_set()
        return card

    def mark_new(self, newly_unlocked: tuple[Accessory, ...]) -> None:
        self._on_content_change()
        self._new_ids.update(item.id for item in newly_unlocked)
        for item in newly_unlocked:
            if item.id in self.new_badges:
                self._layout_reward_heading(item.id)
