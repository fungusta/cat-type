"""Tk outfit choices and preview, independent of app persistence."""

from __future__ import annotations

import random
import tkinter as tk
from pathlib import Path
from typing import Callable

from PIL import ImageTk

from cat_accessories import ACCESSORY_BY_ID, ACCESSORY_SLOTS, SLOT_LABELS, Accessory, visible_accessories
from cat_artwork import load_frame
from ui_surfaces import RoundedAction, RoundedChoice, RoundedPanel, RoundedBadge, PaginationControls
from pagination import page_window, page_slice


class WardrobeView(tk.Frame):
    def __init__(
        self, parent: tk.Misc, *, assets_root: Path,
        slots: dict[str, tk.StringVar], unlocked: set[str],
        on_change: Callable[[], None], on_achievement: Callable[[str], None],
        palette: dict[str, str], fonts: dict,
    ) -> None:
        super().__init__(parent, background=palette["background"])
        self.palette = palette
        self.slots = slots
        self.assets_root = assets_root
        self.fonts = fonts
        self.on_achievement = on_achievement
        self._visible_items: tuple[Accessory, ...] = ()
        self._page_index = 0
        self._page_size = 4
        self._visible_ids: tuple[str, ...] = ()
        self.unlocked = set(unlocked)
        self.on_change = on_change
        self.buttons: dict[str, RoundedAction] = {}
        self.none_buttons: dict[str, tk.Radiobutton] = {}
        self.choice_tiles: dict[str, RoundedPanel] = {}
        self.status_text: dict[str, tk.StringVar] = {}
        self.new_badges: dict[str, RoundedBadge] = {}
        self._new_ids: set[str] = set()
        self.achievement_links: dict[str, tk.Button] = {}
        self._thumbnails: list[ImageTk.PhotoImage] = []
        self._preview_frame: ImageTk.PhotoImage | None = None
        self.notice = tk.StringVar(master=self, value="")

        preview_card = RoundedPanel(
            self,
            background=palette["background"],
            fill=palette["card"],
            border=palette["border"],
            radius=18,
            padding=10,
        )
        self.preview_card = preview_card
        preview_content = preview_card.content
        self.preview = tk.Label(preview_content, background=palette["peach"], width=1, height=1)
        # Pixel width/height apply once an image is assigned; the settings animation
        # supplies it before the window's content is measured.
        self.preview.pack(side="left", padx=(12, 14), pady=4)
        preview_copy = tk.Frame(preview_content, background=palette["card"])
        preview_copy.pack(side="left", fill="both", expand=True, pady=20)
        tk.Label(preview_copy, text="Your outfit", font=fonts["section"],
                 bg=palette["card"], fg=palette["ink"]).pack(anchor="w")
        tk.Label(preview_copy, textvariable=self.notice, justify="left", wraplength=300,
                 font=fonts["small"], bg=palette["card"],
                 fg=palette["accent_dark"]).pack(anchor="w", pady=(8, 0))

        self.tray_shelf = RoundedPanel(
            self,
            background=palette["background"],
            fill=palette["card"],
            border=palette["border"],
            radius=18,
            padding=10,
        )
        self.tray_shelf.pack(fill="x")
        tray_content = self.tray_shelf.content
        tray_heading = tk.Frame(tray_content, background=palette["card"])
        tray_heading.pack(fill="x", padx=20, pady=(17, 12))
        tk.Label(
            tray_heading,
            text="Accessory tray",
            font=fonts["section"],
            bg=palette["card"],
            fg=palette["ink"],
        ).pack(side="left")
        self.tray_count = tk.StringVar(master=self, value="")
        tk.Label(
            tray_heading,
            textvariable=self.tray_count,
            font=fonts["small"],
            bg=palette["card"],
            fg=palette["muted"],
        ).pack(side="right")
        self.choices_area = tk.Frame(tray_content, background=palette["card"])
        self.choices_area.pack(fill="x", padx=20, pady=(0, 19))
        self.pagination_controls = PaginationControls(
            tray_content, on_previous=lambda: self.show_page(self._page_index - 1),
            on_next=lambda: self.show_page(self._page_index + 1),
            palette={**palette, "background": palette["card"]},
            fonts={**fonts, "button": fonts["small"]},
        )
        self.pagination_controls.pack(anchor="center", pady=(0, 12))
        self.choices_area.bind("<Configure>", self._resize_choices)
        self.update_unlocks(unlocked)

    def _build_choices(self, visible: tuple[Accessory, ...]) -> None:
        for child in self.choices_area.winfo_children():
            child.destroy()
        self.buttons.clear()
        self.none_buttons.clear()
        self.choice_tiles.clear()
        self.status_text.clear()
        self.new_badges.clear()
        self.achievement_links.clear()
        self._thumbnails.clear()
        palette, fonts, assets_root = self.palette, self.fonts, self.assets_root
        for slot in ACCESSORY_SLOTS:
            items = [item for item in visible if item.slot == slot]
            if not items:
                continue
            header = tk.Frame(self.choices_area, background=palette["card"])
            header.pack(fill="x", pady=(6, 8))
            tk.Label(header, text=SLOT_LABELS[slot], font=fonts["section"],
                     bg=palette["card"], fg=palette["ink"]).pack(side="left")
            none_button = RoundedChoice(
                header, text="None", variable=self.slots[slot], value="none",
                command=self._choose, indicatoron=False, font=fonts["small"],
                background=palette["card"], selectcolor=palette["accent"],
                activebackground=palette["peach"], foreground=palette["ink"],
                relief="flat", borderwidth=0, padx=12, pady=5,
                highlightthickness=1, highlightcolor=palette["accent_dark"],
                highlightbackground=palette["border"], takefocus=True,
            )
            none_button.pack(side="right")
            self.none_buttons[slot] = none_button
            choices = tk.Frame(self.choices_area, background=palette["card"])
            choices.pack(fill="x", pady=(0, 10))
            choices.grid_columnconfigure(0, weight=1)
            for index, item in enumerate(items):
                row, column = index, 0
                tile = RoundedPanel(
                    choices,
                    background=palette["background"],
                    fill=palette["card"],
                    border=palette["border"],
                    radius=16,
                    padding=6,
                )
                tile.grid(row=row, column=column, sticky="ew", pady=(0, 8))
                self.choice_tiles[item.id] = tile
                tile_content = tile.content
                with load_frame(assets_root, "white", "idle", 58, **{slot: item.id}) as frame:
                    thumbnail = ImageTk.PhotoImage(frame, master=self)
                self._thumbnails.append(thumbnail)
                tile_content.grid_columnconfigure(1, weight=1)
                thumbnail_label = tk.Label(
                    tile_content,
                    image=thumbnail,
                    background=palette["card"],
                )
                thumbnail_label.grid(
                    row=0,
                    column=0,
                    rowspan=2,
                    padx=(4, 14),
                    pady=4,
                )
                copy = tk.Frame(tile_content, background=palette["card"])
                copy.grid(row=0, column=1, sticky="ew", pady=(4, 0))
                name_label = tk.Label(
                    copy,
                    wraplength=1, justify="left",
                    text=item.name,
                    font=fonts["control"],
                    anchor="w",
                    bg=palette["card"],
                    fg=palette["ink"],
                )
                name_label.pack(anchor="w", fill="x")
                achievement_label = tk.Label(
                    copy,
                    wraplength=1, justify="left",
                    text=item.achievement,
                    font=fonts["small"],
                    anchor="w",
                    bg=palette["card"],
                    fg=palette["muted"],
                )
                achievement_label.pack(anchor="w", fill="x", pady=(2, 0))
                button = RoundedAction(
                    tile_content,
                    text="Choose",
                    command=lambda accessory_id=item.id: self._choose_item(accessory_id),
                    font=fonts["small"],
                    takefocus=True,
                    cursor="hand2",
                )
                button.grid(row=0, column=2, rowspan=2, padx=(14, 4), pady=4)
                self.buttons[item.id] = button
                value = tk.StringVar(master=self)
                self.status_text[item.id] = value
                status_row = tk.Frame(copy, background=palette["card"])
                status_row.pack(fill="x", pady=(5, 2))
                status_label = tk.Label(status_row, textvariable=value, font=fonts["small"],
                         bg=palette["card"], fg=palette["accent_dark"],
                         wraplength=1, justify="left")
                status_label.pack(side="left")
                def wrap_copy(event, labels=(name_label, achievement_label)):
                    for label in labels:
                        label.configure(wraplength=max(1, event.width - 4))
                copy.bind("<Configure>", wrap_copy)
                status_row.bind("<Configure>", lambda event, label=status_label:
                                label.configure(wraplength=max(1, event.width - 4)))
                badge = RoundedBadge(
                    status_row,
                    text="NEW",
                    font=fonts["small"],
                )
                self.new_badges[item.id] = badge
                link = RoundedAction(
                    tile_content, text="Progress →", font=fonts["small"],
                    command=lambda accessory_id=item.id: self.on_achievement(accessory_id),
                    cursor="hand2", takefocus=True,
                )
                link.grid(row=2, column=1, columnspan=2, sticky="w", padx=(0, 4), pady=(0, 4))
                self.achievement_links[item.id] = link
                def arrange(event, copy=copy, button=button, thumbnail=thumbnail_label):
                    compact = event.width < thumbnail.winfo_reqwidth() + button.winfo_reqwidth() + 178
                    copy.grid_configure(columnspan=2 if compact else 1)
                    button.grid_configure(row=1 if compact else 0,
                                          column=1 if compact else 2,
                                          rowspan=1 if compact else 2,
                                          sticky="w" if compact else "",
                                          padx=(0, 4) if compact else (14, 4))
                tile_content.bind("<Configure>", arrange, add="+")

    def _resize_choices(self, event: tk.Event) -> None:
        size = 4 if event.width >= 520 else 2
        if size == self._page_size:
            return
        start = self._page_index * self._page_size
        self._page_size = size
        self.show_page(start // size)

    def page_for_item(self, item_id: str) -> int:
        for index, item in enumerate(self._visible_items):
            if item.id == item_id:
                return index // self._page_size
        raise KeyError(item_id)

    def focus_item(self, item_id: str) -> tk.Widget:
        self.show_page(self.page_for_item(item_id))
        self.update_idletasks()
        # Geometry can change page size while idle tasks settle.
        page = self.page_for_item(item_id)
        if page != self._page_index:
            self.show_page(page)
            self.update_idletasks()
        action = self.buttons[item_id]
        action.focus_set()
        return action

    def show_page(self, page_index: int) -> None:
        window = page_window(len(self._visible_items), page_index, self._page_size)
        self._page_index = window.index
        items = page_slice(self._visible_items, window.index, self._page_size)
        if set(self.buttons) != {item.id for item in items}:
            self._build_choices(items)
        self.pagination_controls.set_state(window)
        self.tray_count.set(f"{window.start + 1 if window.end else 0}-{window.end} of {len(self._visible_items)}")
        self._refresh_status()

    def _refresh_status(self) -> None:
        for item_id, button in self.buttons.items():
            earned = item_id in self.unlocked
            button.configure(state="normal" if earned else "disabled")
            self.status_text[item_id].set("Unlocked" if earned else "Locked")
            badge = self.new_badges[item_id]
            if item_id in self._new_ids:
                badge.pack(side="right")
            else:
                badge.pack_forget()
        self._refresh_selection()

    def _choose_item(self, item_id: str) -> None:
        item = ACCESSORY_BY_ID[item_id]
        if self.slots[item.slot].get() == item_id:
            return
        self.slots[item.slot].set(item_id)
        self._choose()

    def _choose(self) -> None:
        self._new_ids.difference_update(variable.get() for variable in self.slots.values())
        self._refresh_status()
        self.on_change()

    def mix_it_up(self) -> None:
        """Choose one unlocked accessory for each slot, then persist it."""
        visible = visible_accessories(self.unlocked)
        changed = False
        for slot, variable in self.slots.items():
            choices = [
                item.id
                for item in visible
                if item.slot == slot and item.id in self.unlocked
            ]
            if choices:
                choice = random.choice(choices)
                if variable.get() != choice:
                    variable.set(choice)
                    changed = True
        if changed:
            self._choose()

    def _refresh_selection(self) -> None:
        for item_id in self.buttons:
            item = ACCESSORY_BY_ID[item_id]
            selected = self.slots[item.slot].get() == item.id
            self.buttons[item.id].configure(
                text="Equipped" if selected else "Choose",
                style="Accent" if selected else "",
            )

    def set_preview(self, frame: ImageTk.PhotoImage) -> None:
        self._preview_frame = frame
        self.preview.configure(image=frame, width=148, height=148)

    def update_unlocks(
        self, unlocked: set[str],
        newly_unlocked: tuple[Accessory, ...] = (),
    ) -> None:
        self.unlocked = set(unlocked)
        visible = visible_accessories(self.unlocked)
        self._visible_items = visible
        self._visible_ids = tuple(item.id for item in visible)
        if newly_unlocked:
            self._new_ids.update(item.id for item in newly_unlocked)
            self.notice.set("Unlocked: " + ", ".join(item.name for item in newly_unlocked))
        self.show_page(self._page_index)
