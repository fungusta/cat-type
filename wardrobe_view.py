"""Tk outfit choices and preview, independent of app persistence."""

from __future__ import annotations

import random
import tkinter as tk
from pathlib import Path
from typing import Callable

from PIL import ImageTk

from cat_accessories import ACCESSORY_BY_ID, ACCESSORY_SLOTS, SLOT_LABELS, Accessory, visible_accessories
from cat_artwork import load_frame
from ui_surfaces import RoundedAction, RoundedChoice, RoundedPanel, RoundedBadge


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
                tk.Label(
                    copy,
                    text=item.name,
                    font=fonts["control"],
                    anchor="w",
                    bg=palette["card"],
                    fg=palette["ink"],
                ).pack(anchor="w")
                tk.Label(
                    copy,
                    text=item.achievement,
                    font=fonts["small"],
                    anchor="w",
                    bg=palette["card"],
                    fg=palette["muted"],
                ).pack(anchor="w", pady=(2, 0))
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
                tk.Label(status_row, textvariable=value, font=fonts["small"],
                         bg=palette["card"], fg=palette["accent_dark"],
                         wraplength=145).pack(side="left")
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

    def _choose_item(self, item_id: str) -> None:
        item = ACCESSORY_BY_ID[item_id]
        if self.slots[item.slot].get() == item_id:
            return
        self.slots[item.slot].set(item_id)
        self._choose()

    def _choose(self) -> None:
        self._refresh_selection()
        for item_id, badge in self.new_badges.items():
            item = ACCESSORY_BY_ID[item_id]
            if self.slots[item.slot].get() == item_id:
                self._new_ids.discard(item_id)
                badge.pack_forget()
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
        unlocked_count = sum(item.id in self.unlocked for item in visible)
        self.tray_count.set(f"{unlocked_count} of {len(visible)} unlocked")
        visible_ids = tuple(item.id for item in visible)
        if visible_ids != self._visible_ids:
            self._build_choices(visible)
            self._visible_ids = visible_ids
        for item in visible:
            earned = item.id in self.unlocked
            self.buttons[item.id].configure(state="normal" if earned else "disabled")
            value = "Unlocked" if earned else "Locked"
            if self.status_text[item.id].get() != value:
                self.status_text[item.id].set(value)
        if newly_unlocked:
            self._new_ids.update(item.id for item in newly_unlocked)
            for item in newly_unlocked:
                badge = self.new_badges.get(item.id)
                if badge is not None:
                    badge.pack(side="right")
            self.notice.set("Unlocked: " + ", ".join(item.name for item in newly_unlocked))
        self._refresh_selection()
