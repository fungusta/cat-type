"""Tk outfit choices and preview, independent of app persistence."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Callable

from PIL import ImageTk

from cat_accessories import ACCESSORY_BY_ID, ACCESSORY_SLOTS, SLOT_LABELS, Accessory, visible_accessories
from cat_artwork import load_frame


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
        self.buttons: dict[str, tk.Radiobutton] = {}
        self.none_buttons: dict[str, tk.Radiobutton] = {}
        self.status_text: dict[str, tk.StringVar] = {}
        self.new_badges: dict[str, tk.Label] = {}
        self._new_ids: set[str] = set()
        self.achievement_links: dict[str, tk.Button] = {}
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
        tk.Label(preview_copy, text="One outfit for all cats.\nChanges save automatically.",
                 justify="left", font=fonts["body"], bg=palette["peach"],
                 fg=palette["ink"]).pack(anchor="w", pady=(8, 0))
        tk.Label(preview_copy, textvariable=self.notice, justify="left", wraplength=300,
                 font=fonts["small"], bg=palette["peach"],
                 fg=palette["accent_dark"]).pack(anchor="w", pady=(8, 0))

        self.choices_area = tk.Frame(self, background=palette["background"])
        self.choices_area.pack(fill="x")
        self.update_unlocks(unlocked)

    def _build_choices(self, visible: tuple[Accessory, ...]) -> None:
        for child in self.choices_area.winfo_children():
            child.destroy()
        self.buttons.clear()
        self.none_buttons.clear()
        self.status_text.clear()
        self.new_badges.clear()
        self.achievement_links.clear()
        self._thumbnails.clear()
        palette, fonts, assets_root = self.palette, self.fonts, self.assets_root
        for slot in ACCESSORY_SLOTS:
            items = [item for item in visible if item.slot == slot]
            if not items:
                continue
            header = tk.Frame(self.choices_area, background=palette["background"])
            header.pack(fill="x", pady=(6, 8))
            tk.Label(header, text=SLOT_LABELS[slot], font=fonts["section"],
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
            choices = tk.Frame(self.choices_area, background=palette["background"])
            choices.pack(fill="x", pady=(0, 10))
            for column in range(3):
                choices.grid_columnconfigure(column, weight=1, uniform=slot)
            for index, item in enumerate(items):
                row, column = divmod(index, 3)
                tile = tk.Frame(choices, background=palette["card"],
                                highlightthickness=1, highlightbackground=palette["border"])
                tile.grid(row=row, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0), pady=(0, 8))
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
                value = tk.StringVar(master=self)
                self.status_text[item.id] = value
                status_row = tk.Frame(tile, background=palette["card"])
                status_row.pack(fill="x", padx=5, pady=(4, 2))
                tk.Label(status_row, textvariable=value, font=fonts["small"],
                         bg=palette["card"], fg=palette["accent_dark"],
                         wraplength=145).pack(side="left", expand=True)
                badge = tk.Label(status_row, text="", font=fonts["small"],
                                  bg=palette["peach"], fg=palette["accent_dark"], padx=4, pady=1)
                badge.pack(side="right")
                self.new_badges[item.id] = badge
                link = tk.Button(
                    tile, text="View achievement →", font=fonts["small"],
                    command=lambda accessory_id=item.id: self.on_achievement(accessory_id),
                    bg=palette["card"], fg=palette["accent_dark"],
                    activebackground=palette["peach"], activeforeground=palette["ink"],
                    relief="flat", borderwidth=0, highlightthickness=1,
                    highlightbackground=palette["card"], highlightcolor=palette["accent"],
                    cursor="hand2", takefocus=True, wraplength=140,
                )
                link.pack(padx=5, pady=(0, 6))
                self.achievement_links[item.id] = link

    def _choose(self) -> None:
        self._refresh_selection()
        for item_id, badge in self.new_badges.items():
            item = ACCESSORY_BY_ID[item_id]
            if self.slots[item.slot].get() == item_id:
                self._new_ids.discard(item_id)
                badge.configure(text="")
        self.on_change()

    def _refresh_selection(self) -> None:
        for item_id in self.buttons:
            item = ACCESSORY_BY_ID[item_id]
            selected = self.slots[item.slot].get() == item.id
            self.buttons[item.id].configure(
                highlightbackground=self.palette["accent"] if selected else self.palette["card"],
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
                    badge.configure(text="NEW")
            self.notice.set("Unlocked: " + ", ".join(item.name for item in newly_unlocked))
        self._refresh_selection()
