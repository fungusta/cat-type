"""Achievement requirements and progress, separate from outfit selection."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from typing import Callable

from PIL import Image, ImageTk

from achievements import progress, requirement
from cat_accessories import Accessory, visible_accessories
from cat_artwork import load_frame
from usage_metrics import UsageMetrics
from ui_surfaces import (
    RoundedChoice, RoundedPanel, faded_art, flow_choices, progress_bar_image, soft_pill_image,
    status_mark_image,
)


FILTER_LABELS = {"all": "All", "progress": "In progress", "unlocked": "Unlocked"}
# Secrets stay out of the album until earned; then they join Discoveries.
GROUPS = (
    ("milestones", "Typing milestones"),
    ("days", "Active days"),
    ("discoveries", "Discoveries"),
)


def group_for(item: Accessory) -> str:
    if item.hidden:
        return "discoveries"
    return "days" if item.metric == "days" else "milestones"


class RewardEntry(tk.Canvas):
    """One album entry drawn on a single canvas with a native focus outline."""

    THUMBNAIL = 64
    PAD = 12

    def __init__(
        self, parent: tk.Misc, *, item: Accessory, art: Image.Image,
        palette: dict[str, str], fonts: dict, fill: str | None = None,
        thumbnail: int | None = None,
    ) -> None:
        self._surface = fill or palette["card"]
        super().__init__(
            parent, width=1, height=1, background=self._surface, borderwidth=0,
            highlightthickness=2, highlightbackground=self._surface,
            highlightcolor=palette["accent_dark"], takefocus=True,
        )
        self.item = item
        self.palette = palette
        self.fonts = fonts
        self._thumbnail = thumbnail or self.THUMBNAIL
        self._art = art
        self._faded: Image.Image | None = None
        self.earned = False
        self.is_new = False
        self.progress: tuple[int, int] = (0, item.target)
        self._focused = False
        self._focus_color = palette["accent_dark"]
        self._layout_width = 0
        self._drawn_key: tuple[object, ...] | None = None
        self._draw_after_id: str | None = None
        self._images: list[ImageTk.PhotoImage] = []
        self.bind("<FocusIn>", lambda _event: self._set_focus(True), add="+")
        self.bind("<FocusOut>", lambda _event: self._set_focus(False), add="+")
        self.bind("<Configure>", lambda _event: self._queue_draw(), add="+")
        self.bind("<Destroy>", self._cancel_draw, add="+")

    @property
    def status(self) -> str:
        return "Unlocked" if self.earned else "Locked"

    def cget(self, key: str) -> object:
        if key == "accessible_name":
            current, target = self.progress
            detail = "unlocked" if self.earned else f"{current:,} of {target:,}"
            return (f"{self.item.achievement}, reward {self.item.name}, "
                    f"{requirement(self.item)}, {detail}")
        return super().cget(key)

    def set_state(self, *, earned: bool, is_new: bool, progress_value: tuple[int, int]) -> None:
        state = (earned, is_new, progress_value)
        if state == (self.earned, self.is_new, self.progress):
            return
        self.earned, self.is_new, self.progress = state
        if self._layout_width:
            self.configure(height=self.required_height(self._layout_width))
        self._queue_draw()

    def _set_focus(self, focused: bool) -> None:
        self._focused = focused
        self.configure(highlightbackground=self._focus_color if focused else self._surface)

    def fit_width(self, width: int) -> None:
        if width == self._layout_width:
            return
        self._layout_width = width
        self.configure(width=width - 4, height=self.required_height(width))

    def fit_height(self, width: int) -> None:
        """Size to the copy at an allotted ``width`` (for pack-filled entries)."""
        if width > 1 and width != self._layout_width:
            self._layout_width = width
            self.configure(height=self.required_height(width))

    def _stacked(self, width: int) -> bool:
        """Put the copy under the thumbnail once beside it would be too cramped."""
        beside = width - 4 - self.PAD * 2 - self._thumbnail - 14
        return beside < self.fonts["control"].measure("Bells and Whiskers") * .7

    def _copy_width(self, width: int) -> int:
        if self._stacked(width):
            return max(1, width - 4 - self.PAD * 2)
        return max(1, width - 4 - self.PAD * 2 - self._thumbnail - 14)

    def _text_height(self, text: str, font: tkfont.Font, width: int) -> int:
        """Height of ``text`` wrapped exactly as this canvas will wrap it."""
        probe = self.create_text(-10_000, 0, anchor="nw", text=text, font=font, width=max(1, width))
        bounds = self.bbox(probe)
        self.delete(probe)
        return (bounds[3] - bounds[1]) if bounds else font.metrics("linespace")

    def _title_width(self, wrap: int) -> int:
        if not self.is_new:
            return wrap
        return max(1, wrap - self._new_pill_size()[0] - 8)

    def _new_pill_size(self) -> tuple[int, int]:
        font = self.fonts["tiny"]
        return font.measure("NEW") + 14, font.metrics("linespace") + 6

    def required_height(self, width: int) -> int:
        fonts = self.fonts
        wrap = self._copy_width(width)
        copy = (self._text_height(self.item.achievement, fonts["control"], self._title_width(wrap))
                + 2 + self._text_height(f"Reward · {self.item.name}", fonts["small"], wrap)
                + 2 + self._text_height(requirement(self.item), fonts["small"], wrap)
                + 2 + 8 + 12 + self._text_height(self._detail()[0], fonts["tiny"], wrap))
        if self._stacked(width):
            return self._thumbnail + 10 + copy + self.PAD * 2
        return max(self._thumbnail, copy) + self.PAD * 2

    def _detail(self) -> tuple[str, str]:
        """The meter caption and, while locked, its percentage."""
        current, target = self.progress
        if self.earned:
            return "Unlocked", ""
        unit = " days" if self.item.metric == "days" else ""
        percent = f"{current / target:.0%}" if target else ""
        return f"{current:,} / {target:,}{unit}", percent

    def _queue_draw(self) -> None:
        if self._draw_after_id is None:
            self._draw_after_id = self.after_idle(self._draw)

    def _cancel_draw(self, _event: tk.Event | None = None) -> None:
        if self._draw_after_id is not None:
            self.after_cancel(self._draw_after_id)
            self._draw_after_id = None

    def _draw(self) -> None:
        self._cancel_draw()
        width, height = self.winfo_width() - 4, self.winfo_height() - 4
        if width <= 1 or height <= 1:
            return
        key = (width, height, self.earned, self.is_new, self.progress)
        if key == self._drawn_key:
            return
        self._drawn_key = key
        palette, fonts = self.palette, self.fonts
        surface = self._surface
        self.delete("all")
        self._images = []
        origin = 2 + self.PAD
        art = self._art
        if not self.earned:
            if self._faded is None:
                self._faded = faded_art(self._art, surface)
            art = self._faded
        thumbnail = ImageTk.PhotoImage(art, master=self)
        self._images.append(thumbnail)
        self.create_image(origin, origin, anchor="nw", image=thumbnail)
        mark_size = max(16, fonts["tiny"].metrics("linespace") + 4)
        mark = ImageTk.PhotoImage(
            status_mark_image(surface, mark_size, "check" if self.earned else "lock"), master=self,
        )
        self._images.append(mark)
        self.create_image(origin + self._thumbnail + 2, origin + self._thumbnail + 2,
                          anchor="se", image=mark)
        stacked = self._stacked(width + 4)
        x = origin if stacked else origin + self._thumbnail + 14
        top = origin + self._thumbnail + 10 if stacked else origin
        wrap = self._copy_width(width + 4)
        title = self.create_text(
            x, top, anchor="nw", text=self.item.achievement, font=fonts["control"],
            width=self._title_width(wrap), fill=palette["ink"],
        )
        if self.is_new:
            pill_width, pill_height = self._new_pill_size()
            pill = ImageTk.PhotoImage(soft_pill_image(
                surface, pill_width, pill_height, palette["accent"], flat=True,
                border=palette["accent"],
            ), master=self)
            self._images.append(pill)
            right = x + wrap
            self.create_image(right, top, anchor="ne", image=pill)
            self.create_text(right - pill_width // 2, top + pill_height // 2, text="NEW",
                             font=fonts["tiny"], fill=palette["ink"])
        y = self.bbox(title)[3] + 2
        for text in (f"Reward · {self.item.name}", requirement(self.item)):
            line = self.create_text(x, y, anchor="nw", text=text, font=fonts["small"],
                                    width=wrap, fill=palette["muted"])
            y = self.bbox(line)[3] + 2
        y += 8
        current, target = self.progress
        fraction = 1.0 if self.earned else (current / target if target else 0.0)
        bar = ImageTk.PhotoImage(progress_bar_image(surface, wrap, 6, fraction), master=self)
        self._images.append(bar)
        self.create_image(x, y, anchor="nw", image=bar)
        detail, percent = self._detail()
        tiny = fonts["tiny"]
        self.create_text(x, y + 12, anchor="nw", text=detail, font=tiny, width=wrap,
                         fill=palette["accent_dark"] if self.earned else palette["muted"])
        # The percentage is a convenience; narrow cards keep only the count.
        if percent and tiny.measure(detail) + tiny.measure(percent) + 12 <= wrap:
            self.create_text(x + wrap, y + 12, anchor="ne", text=percent,
                             font=tiny, fill=palette["muted"])


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
        self._unlocked: set[str] = set()
        self._metrics = metrics
        self._art: dict[str, Image.Image] = {}
        self.cards: dict[str, RewardEntry] = {}
        self._new_ids: set[str] = set()
        self.progress_text: dict[str, tk.StringVar] = {}
        self._layout_key: tuple[object, ...] | None = None
        self._album_layout_after_id: str | None = None
        self.summary = tk.StringVar(master=self)
        self.filter = tk.StringVar(master=self, value="all")
        self.up_next_id: str | None = None

        self.album_shelf = RoundedPanel(
            self, background=palette["background"], fill=palette["card"],
            border=palette["border"], radius=18, padding=10,
        )
        self.album_shelf.pack(fill="x")
        album_content = self.album_shelf.content
        self.album_heading = tk.Frame(album_content, background=palette["card"])
        self.album_heading.pack(fill="x", padx=14, pady=(12, 8))
        self.album_heading.grid_columnconfigure(0, weight=1)
        self.album_title = tk.Label(
            self.album_heading, text="Reward album", font=fonts["section"],
            bg=palette["card"], fg=palette["ink"], anchor="w", justify="left",
            wraplength=240, padx=0, pady=0, borderwidth=0,
        )
        self.album_title.grid(row=0, column=0, sticky="w")
        self.summary_label = tk.Label(
            self.album_heading, textvariable=self.summary, font=fonts["small"],
            bg=palette["card"], fg=palette["muted"], anchor="w", justify="left",
            wraplength=240, padx=0, pady=0, borderwidth=0,
        )
        self.summary_label.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self._heading_layout_key: tuple[int, str] | None = None
        self.album_heading.bind("<Configure>", self._layout_heading, add="+")

        # Overall completion, so the album reads as a collection at a glance.
        self.completion = tk.Canvas(album_content, height=10, background=palette["card"],
                                    highlightthickness=0, borderwidth=0)
        self.completion.pack(fill="x", padx=14, pady=(2, 14))
        self.completion.bind("<Configure>", lambda _event: self._draw_completion(), add="+")
        self._completion_image: ImageTk.PhotoImage | None = None

        # The locked reward nearest to completion, as a quiet next goal.
        self.up_next = tk.Frame(album_content, background=palette["card"])
        self.up_next_label = tk.Label(
            self.up_next, text="Up next", font=fonts["tiny"], bg=palette["card"],
            fg=palette["muted"], anchor="w",
        )
        self.up_next_label.pack(fill="x", padx=4, pady=(0, 4))
        self.up_next_host = RoundedPanel(
            self.up_next, background=palette["card"], fill=palette["peach"],
            border=palette["peach"], radius=16, padding=4,
        )
        self.up_next_host.pack(fill="x")
        self.up_next_card: RewardEntry | None = None

        self.filter_bar = tk.Frame(album_content, background=palette["card"])
        self.filter_bar.pack(fill="x", padx=14, pady=(0, 6))
        self.filter_buttons: dict[str, RoundedChoice] = {}
        for key, label in FILTER_LABELS.items():
            self.filter_buttons[key] = RoundedChoice(
                self.filter_bar, text=label, variable=self.filter, value=key,
                command=self._apply_filter, indicatoron=False, font=fonts["small"],
                background=palette["card"], selectcolor=palette["accent"],
                activebackground=palette["peach"], foreground=palette["ink"],
                relief="flat", borderwidth=0, padx=12, pady=5, highlightthickness=1,
                highlightcolor=palette["accent_dark"], highlightbackground=palette["border"],
                takefocus=True, cursor="hand2",
            )
        self.filter_bar.bind(
            "<Configure>",
            lambda event: flow_choices(self.filter_bar, list(self.filter_buttons.values()), event.width)
            if event.width > 1 else None,
            add="+",
        )

        self.cards_area = tk.Frame(album_content, background=palette["card"])
        self.cards_area.pack(fill="x", padx=6, pady=(0, 10))
        self.cards_area.bind("<Configure>", lambda _event: self._layout_cards(), add="+")
        self.sections: dict[str, tk.Frame] = {}
        self._section_grids: dict[str, tk.Frame] = {}
        self._section_counts: dict[str, tk.StringVar] = {}
        for key, title in GROUPS:
            section = self.sections[key] = tk.Frame(self.cards_area, background=palette["card"])
            header = tk.Frame(section, background=palette["card"])
            header.pack(fill="x", padx=8, pady=(12, 6))
            header.grid_columnconfigure(0, weight=1)
            tk.Label(header, text=title, font=fonts["section"], bg=palette["card"],
                     fg=palette["ink"], anchor="w").grid(row=0, column=0, sticky="w")
            count = self._section_counts[key] = tk.StringVar(master=self)
            tk.Label(header, textvariable=count, font=fonts["small"], bg=palette["card"],
                     fg=palette["muted"], anchor="e").grid(row=0, column=1, sticky="e", padx=(12, 0))
            self._section_grids[key] = tk.Frame(section, background=palette["card"])
            self._section_grids[key].pack(fill="x")
        self.empty_label = tk.Label(
            self.cards_area, font=fonts["small"], bg=palette["card"], fg=palette["muted"],
            justify="center", wraplength=320, pady=24,
        )
        self.update_progress(metrics, unlocked)

    # Layout ----------------------------------------------------------------

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
        if width >= natural_title_width + natural_count_width + 24:
            self.summary_label.grid(row=0, column=1, sticky="e", padx=(20, 0), pady=0)
        else:
            self.summary_label.grid(row=1, column=0, columnspan=2, sticky="ew", padx=0, pady=(4, 0))
        for label in (self.album_title, self.summary_label):
            if int(label.cget("wraplength")) != max(1, width - 4):
                label.configure(wraplength=max(1, width - 4))

    def _draw_completion(self) -> None:
        width = self.completion.winfo_width()
        if width <= 1:
            return
        total = len(self._visible_items)
        earned = sum(item.id in self._unlocked for item in self._visible_items)
        image = progress_bar_image(self.palette["card"], width, 10, earned / total if total else 0)
        self._completion_image = ImageTk.PhotoImage(image, master=self.completion)
        self.completion.delete("all")
        self.completion.create_image(0, 0, anchor="nw", image=self._completion_image)

    def _shown_items(self) -> tuple[Accessory, ...]:
        selected = self.filter.get()
        return tuple(
            item for item in self._visible_items
            if selected == "all" or (item.id in self._unlocked) == (selected == "unlocked")
        )

    def _layout_cards(self) -> None:
        width = self.cards_area.winfo_width()
        if width <= 1:
            return
        # Keep two cards at high Tk scaling when the rail grows for its
        # longer unread label; the narrow 620 px layout remains one column.
        columns = 2 if self._responsive_width(width) >= 520 else 1
        gap = 8
        # Every card carries half the gap on each side so columns stay equal.
        card_width = max(1, width // columns - gap)
        shown = self._shown_items()
        key = (columns, card_width, tuple(item.id for item in shown), self._visible_ids)
        if key == self._layout_key:
            return
        self._layout_key = key
        shown_ids = {item.id for item in shown}
        # Repack shown sections in their natural order, whatever reappeared.
        for section in self.sections.values():
            section.pack_forget()
        self.empty_label.pack_forget()
        for group, _title in GROUPS:
            members = [item for item in shown if group_for(item) == group]
            if not members:
                continue
            self.sections[group].pack(fill="x")
            grid = self._section_grids[group]
            for column in range(2):
                grid.grid_columnconfigure(column, weight=1 if column < columns else 0,
                                          uniform="reward-cards" if column < columns else "")
            for index, item in enumerate(members):
                row, column = divmod(index, columns)
                card = self.cards[item.id]
                card.fit_width(card_width)
                card.grid(row=row, column=column, sticky="nsew", padx=gap // 2, pady=(0, 4))
        for item_id, card in self.cards.items():
            if item_id not in shown_ids:
                card.grid_remove()
        if not shown:
            self.empty_label.configure(text=(
                "Nothing unlocked yet. Your first reward arrives at 250 keystrokes."
                if self.filter.get() == "unlocked" else "Every reward is unlocked. Nicely done."
            ))
            self.empty_label.pack(fill="x")
        self._schedule_album_layout()

    def _apply_filter(self) -> None:
        self._on_content_change()
        self._layout_cards()

    def _schedule_album_layout(self) -> None:
        if not self.winfo_exists():
            return
        if self._album_layout_after_id is None:
            self._album_layout_after_id = self.after_idle(self._run_album_layout)

    def _run_album_layout(self) -> None:
        self._album_layout_after_id = None
        if self.winfo_exists():
            self.album_shelf._sync_size()

    def refresh_layout(self) -> None:
        """Reconcile the album shelf after it is mapped into the scroll canvas."""
        available_width = self.winfo_width()
        if available_width > 1 and self.album_shelf.winfo_width() != available_width:
            # RoundedPanel keeps an explicit width once it has measured its
            # first content pass; re-anchor it so high scaling cannot leave a
            # stale wide request behind.
            self.album_shelf.configure(width=available_width)
        self._layout_cards()
        self._layout_heading()
        self.album_shelf._sync_size()

    def destroy(self) -> None:
        if self._album_layout_after_id is not None:
            try:
                self.after_cancel(self._album_layout_after_id)
            except tk.TclError:
                pass
            self._album_layout_after_id = None
        super().destroy()

    # State -----------------------------------------------------------------

    def _art_for(self, item: Accessory, size: int = RewardEntry.THUMBNAIL) -> Image.Image:
        key = f"{item.id}:{size}"
        if key not in self._art:
            with load_frame(self.assets_root, "white", "idle", size, **{item.slot: item.id}) as frame:
                self._art[key] = frame.convert("RGBA").copy()
        return self._art[key]

    def _progress_value(self, item: Accessory) -> tuple[int, int]:
        if item.id in self._unlocked:
            return item.target, item.target
        return progress(item, self._metrics), item.target

    def _choose_up_next(self) -> Accessory | None:
        candidates = [item for item in self._visible_items
                      if item.id not in self._unlocked and item.metric != "beta"]
        if not candidates:
            return None
        return max(candidates, key=lambda item: (progress(item, self._metrics) / item.target, -item.target))

    def _refresh_up_next(self) -> None:
        item = self._choose_up_next()
        if item is None:
            self.up_next_id = None
            self.up_next.pack_forget()
            return
        if item.id != self.up_next_id:
            self.up_next_id = item.id
            if self.up_next_card is not None:
                self.up_next_card.destroy()
            self.up_next_card = RewardEntry(
                self.up_next_host.content, item=item, art=self._art_for(item, 76),
                palette=self.palette, fonts=self.fonts, fill=self.palette["peach"], thumbnail=76,
            )
            self.up_next_card.pack(fill="x")
            self.up_next_card.bind(
                "<Configure>", lambda event, card=self.up_next_card: card.fit_height(event.width),
                add="+",
            )
        self.up_next_card.set_state(earned=False, is_new=False, progress_value=self._progress_value(item))
        if not self.up_next.winfo_manager():
            self.up_next.pack(fill="x", padx=14, pady=(0, 14), before=self.filter_bar)

    def update_progress(self, metrics: UsageMetrics, unlocked: set[str]) -> None:
        self._metrics = metrics
        self._visible_items = visible_accessories(unlocked)
        visible_ids = tuple(item.id for item in self._visible_items)
        if visible_ids != self._visible_ids:
            self._on_content_change()
        self._visible_ids = visible_ids
        self._unlocked = set(unlocked)
        earned_count = sum(item.id in unlocked for item in self._visible_items)
        self.summary.set(f"{earned_count} of {len(self._visible_items)} achievements unlocked")
        for item in self._visible_items:
            if item.id not in self.cards:
                group = self._section_grids[group_for(item)]
                self.cards[item.id] = RewardEntry(group, item=item, art=self._art_for(item),
                                                  palette=self.palette, fonts=self.fonts)
            if item.id not in self.progress_text:
                self.progress_text[item.id] = tk.StringVar(master=self)
            current, target = self._progress_value(item)
            unit = " days" if item.metric == "days" else ""
            value = "Unlocked" if item.id in unlocked else f"{current:,} / {target:,}{unit}"
            if self.progress_text[item.id].get() != value:
                self.progress_text[item.id].set(value)
        for item_id in [item_id for item_id in self.cards if item_id not in visible_ids]:
            self.cards.pop(item_id).destroy()
        for group, _title in GROUPS:
            members = [item for item in self._visible_items if group_for(item) == group]
            earned = sum(item.id in unlocked for item in members)
            self._section_counts[group].set(f"{earned} of {len(members)}")
        self._refresh_cards()
        self._refresh_up_next()
        self._draw_completion()
        self._layout_cards()

    def _refresh_cards(self) -> None:
        for item in self._visible_items:
            self.cards[item.id].set_state(
                earned=item.id in self._unlocked, is_new=item.id in self._new_ids,
                progress_value=self._progress_value(item),
            )

    def focus_reward(self, accessory_id: str) -> RewardEntry:
        if accessory_id not in self.cards:
            raise KeyError(accessory_id)
        if accessory_id not in {item.id for item in self._shown_items()}:
            self.filter.set("all")
            self._apply_filter()
        self.update_idletasks()
        card = self.cards[accessory_id]
        self._new_ids.discard(accessory_id)
        self._refresh_cards()
        card.focus_set()
        return card

    def mark_new(self, newly_unlocked: tuple[Accessory, ...]) -> None:
        self._on_content_change()
        self._new_ids.update(item.id for item in newly_unlocked)
        self._refresh_cards()
