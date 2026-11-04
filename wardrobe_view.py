"""Tk outfit locker: filterable accessory tiles with a live try-on preview."""

from __future__ import annotations

import random
import tkinter as tk
from tkinter import font as tkfont
from pathlib import Path
from typing import Callable

from PIL import Image, ImageTk

from achievements import progress
from cat_accessories import ACCESSORY_BLURBS, ACCESSORY_BY_ID, ACCESSORY_SLOTS, Accessory, visible_accessories
from cat_artwork import load_frame
from usage_metrics import UsageMetrics
from ui_surfaces import (
    BUTTON_HOVER, RoundedChoice, RoundedPanel, Tween, blend, faded_art, flow_choices,
    progress_bar_image, soft_pill_image, status_mark_image,
)


FILTER_LABELS = {"all": "All", "hat": "Hats", "glasses": "Glasses",
                 "neck": "Neckwear", "back": "Back", "ears": "Ears"}
SECTION_LABELS = {"hat": "Hats", "glasses": "Glasses", "neck": "Neckwear",
                  "back": "Back accessories", "ears": "Ear accessories"}
LOCKED_FILL = "#FAF7F3"
# Leaving one tile for its neighbour emits Leave then Enter; holding the
# restore briefly keeps the stage from flashing the saved outfit between them.
TRY_ON_RESTORE_MS = 90


class AccessoryTile(tk.Canvas):
    """One locker tile drawn on a single canvas.

    A tray holds every accessory at once, so each tile is one native window
    rather than a frame of labels and buttons; the whole locker builds fast.
    """

    THUMBNAIL = 88
    PAD = 10

    def __init__(
        self, parent: tk.Misc, *, item_id: str | None, slot: str, name: str,
        blurb: str, art: Image.Image, palette: dict[str, str], fonts: dict,
        command: Callable[[], None], on_hover: Callable[[AccessoryTile, bool], None],
    ) -> None:
        super().__init__(
            parent, width=1, height=1, background=palette["card"],
            highlightthickness=0, borderwidth=0, takefocus=True, cursor="hand2",
        )
        self.item_id = item_id
        self.slot = slot
        self.name = name
        self.blurb = blurb
        self.palette = palette
        self.fonts = fonts
        self._command = command
        self._on_hover = on_hover
        self._art = art
        self._faded: Image.Image | None = None
        self.state = "unlocked"
        self.is_new = False
        self.progress: tuple[int, int] | None = None
        self._focused = False
        self._pressed = False
        self._drawn_key: tuple[object, ...] | None = None
        self._layout_width = 0
        self._images: list[ImageTk.PhotoImage] = []
        self._hover = Tween(self, lambda _value: self._draw())
        self.bind("<Enter>", lambda _event: self._set_hover(True), add="+")
        self.bind("<Leave>", lambda _event: self._set_hover(False), add="+")
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Return>", self._activate)
        self.bind("<space>", self._activate)
        self.bind("<FocusIn>", lambda _event: self._set_focus(True), add="+")
        self.bind("<FocusOut>", lambda _event: self._set_focus(False), add="+")
        self._draw_after_id: str | None = None
        self.bind("<Configure>", lambda _event: self._queue_draw(), add="+")
        self.bind("<Destroy>", self._cancel_draw, add="+")

    @property
    def status(self) -> str:
        if self.state == "equipped":
            return "Equipped"
        return "Unlocked" if self.state == "unlocked" else "Locked"

    def set_state(self, state: str, *, is_new: bool = False,
                  progress_value: tuple[int, int] | None = None) -> None:
        if (state, is_new, progress_value) == (self.state, self.is_new, self.progress):
            return
        self.state, self.is_new, self.progress = state, is_new, progress_value
        if self._layout_width:
            # Only a locked tile with known progress carries a meter.
            self.configure(height=self.required_height(self._layout_width))
        self._queue_draw()

    def invoke(self) -> object:
        return self._command()

    def cget(self, key: str) -> object:
        if key == "accessible_role":
            return "button"
        if key == "accessible_name":
            return f"{self.name}, {self.status}"
        if key == "accessible_state":
            return "selected" if self.state == "equipped" else "normal"
        return super().cget(key)

    def _set_hover(self, hovered: bool) -> None:
        self._hover.to(1.0 if hovered else 0.0)
        self._on_hover(self, hovered)

    def _set_focus(self, focused: bool) -> None:
        self._focused = focused
        self._draw()

    def _press(self, _event: tk.Event[tk.Misc]) -> None:
        self._pressed = True
        self.focus_set()
        self._draw()

    def _release(self, event: tk.Event[tk.Misc]) -> None:
        was_pressed, self._pressed = self._pressed, False
        self._draw()
        inside = 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height()
        if was_pressed and inside:
            self.invoke()

    def _activate(self, _event: tk.Event[tk.Misc]) -> str:
        self.invoke()
        return "break"

    def fit_width(self, width: int) -> None:
        """Request the height that this tile's copy needs at ``width``."""
        if width == self._layout_width:
            return
        self._layout_width = width
        self.configure(width=width, height=self.required_height(width))

    def required_height(self, width: int) -> int:
        wrap = width - self.PAD * 2
        name = self._text_height(self.name, self.fonts["control"], wrap)
        meter = self._meter_text()
        if meter:
            footer = 4 + 12 + self._text_height(meter, self.fonts["tiny"], wrap)
        elif self.state != "locked":
            footer = 3 + self._text_height(self.blurb, self.fonts["small"], wrap)
        else:
            footer = 0
        return self.PAD + 3 + self.THUMBNAIL + 8 + name + footer + self.PAD + 4

    def _meter_text(self) -> str:
        """The locked tile's progress count, shown where earned tiles have a blurb."""
        if self.state != "locked" or self.progress is None:
            return ""
        current, target = self.progress
        return f"{current:,} / {target:,}"

    def _text_height(self, text: str, font: tkfont.Font, width: int) -> int:
        """Height of ``text`` wrapped exactly as this canvas will wrap it."""
        probe = self.create_text(-10_000, 0, anchor="nw", text=text, font=font, width=max(1, width))
        bounds = self.bbox(probe)
        self.delete(probe)
        return (bounds[3] - bounds[1]) if bounds else font.metrics("linespace")

    def _queue_draw(self) -> None:
        # A new grid settles over several Configure events; paint once after.
        if self._draw_after_id is None:
            self._draw_after_id = self.after_idle(self._draw)

    def _cancel_draw(self, _event: tk.Event | None = None) -> None:
        if self._draw_after_id is not None:
            self.after_cancel(self._draw_after_id)
            self._draw_after_id = None

    def _draw(self) -> None:
        self._cancel_draw()
        width, height = self.winfo_width(), self.winfo_height()
        if width <= 1 or height <= 1:
            return
        hover = self._hover.value
        key = (width, height, self.state, self.is_new, self.progress,
               hover, self._focused, self._pressed)
        if key == self._drawn_key:
            return
        self._drawn_key = key
        palette, fonts = self.palette, self.fonts
        surface = palette["card"]
        base = {"equipped": palette["peach"], "unlocked": "#FFFFFF"}.get(self.state, LOCKED_FILL)
        # Hover lifts the tile; only the equipped tile carries the accent fill.
        lift_toward = "#FFFFFF" if self.state == "locked" else BUTTON_HOVER
        fill = base if self.state == "equipped" else blend(base, lift_toward, hover * 0.45)
        self.delete("all")
        self._images = []
        face = ImageTk.PhotoImage(soft_pill_image(
            surface, width, height, fill, pressed=self._pressed,
            focused=self._focused, lift=hover,
        ), master=self)
        self._images.append(face)
        self.create_image(0, 0, anchor="nw", image=face)
        shift = 1 if self._pressed else 0
        top = self.PAD + 3 + shift
        art = self._art
        if self.state == "locked":
            if self._faded is None:
                self._faded = faded_art(self._art, LOCKED_FILL)
            art = self._faded
        thumbnail = ImageTk.PhotoImage(art, master=self)
        self._images.append(thumbnail)
        self.create_image(width // 2, top, anchor="n", image=thumbnail)
        mark = {"equipped": "check", "locked": "lock"}.get(self.state)
        if mark is not None:
            size = max(18, fonts["small"].metrics("linespace") + 2)
            badge = ImageTk.PhotoImage(status_mark_image(fill, size, mark), master=self)
            self._images.append(badge)
            self.create_image(width - self.PAD - 1, top, anchor="ne", image=badge)
        if self.is_new:
            new_font = fonts["tiny"]
            pill_width = new_font.measure("NEW") + 14
            pill_height = new_font.metrics("linespace") + 6
            pill = ImageTk.PhotoImage(soft_pill_image(
                fill, pill_width, pill_height, palette["accent"], flat=True,
                border=palette["accent"],
            ), master=self)
            self._images.append(pill)
            self.create_image(self.PAD, top, anchor="nw", image=pill)
            self.create_text(self.PAD + pill_width // 2, top + pill_height // 2, text="NEW",
                             font=new_font, fill=palette["ink"])
        y = top + self.THUMBNAIL + 8
        name = self.create_text(
            width // 2, y, anchor="n", text=self.name, justify="center",
            width=max(1, width - self.PAD * 2), font=fonts["control"],
            fill=palette["ink"] if self.state != "locked" else palette["muted"],
        )
        bounds = self.bbox(name)
        y = (bounds[3] if bounds else y) + 4
        meter = self._meter_text()
        if self.state != "locked":
            self.create_text(width // 2, y - 1, anchor="n", text=self.blurb, font=fonts["small"],
                             fill=palette["muted"], justify="center",
                             width=max(1, width - self.PAD * 2))
        elif meter:
            current, target = self.progress
            bar_width = max(24, width - self.PAD * 4)
            bar = ImageTk.PhotoImage(progress_bar_image(
                fill, bar_width, 6, current / target if target else 0,
            ), master=self)
            self._images.append(bar)
            self.create_image(width // 2, y + 2, anchor="n", image=bar)
            self.create_text(width // 2, y + 12, anchor="n", text=meter,
                             font=fonts["tiny"], fill=palette["muted"], justify="center",
                             width=max(1, width - self.PAD * 2))


class WardrobeView(tk.Frame):
    def __init__(
        self, parent: tk.Misc, *, assets_root: Path,
        slots: dict[str, tk.StringVar], unlocked: set[str],
        on_change: Callable[[], None], on_achievement: Callable[[str], None],
        palette: dict[str, str], fonts: dict,
        responsive_width: Callable[[int], int] | None = None,
        on_content_change: Callable[[], None] | None = None,
        on_try_on: Callable[[dict[str, str] | None, str], None] | None = None,
        metrics: Callable[[], UsageMetrics] | None = None,
    ) -> None:
        super().__init__(parent, background=palette["background"])
        self.palette = palette
        self.slots = slots
        self.assets_root = assets_root
        self.fonts = fonts
        self._responsive_width = responsive_width or (lambda width: width)
        self._on_content_change = on_content_change or (lambda: None)
        self._on_try_on = on_try_on or (lambda _outfit, _name: None)
        self._metrics = metrics
        self.on_achievement = on_achievement
        self.on_change = on_change
        self.unlocked = set(unlocked)
        self._visible_items: tuple[Accessory, ...] = ()
        self._visible_ids: tuple[str, ...] = ()
        self._new_ids: set[str] = set()
        self.tiles: dict[str, AccessoryTile] = {}
        self.none_tiles: dict[str, AccessoryTile] = {}
        self.sections: dict[str, tk.Frame] = {}
        self._section_counts: dict[str, tk.StringVar] = {}
        self._section_grids: dict[str, tk.Frame] = {}
        self._layout_key: tuple[object, ...] | None = None
        self._try_on_tile: AccessoryTile | None = None
        self._restore_after_id: str | None = None
        self._preview_frame: ImageTk.PhotoImage | None = None
        self.notice = tk.StringVar(master=self, value="")
        self.filter = tk.StringVar(master=self, value="all")
        self.bind("<Destroy>", self._cancel_restore, add="+")

        self.tray_shelf = RoundedPanel(
            self, background=palette["background"], fill=palette["card"],
            border=palette["border"], radius=18, padding=10,
        )
        self.tray_shelf.pack(fill="x")
        tray_content = self.tray_shelf.content
        self.tray_heading = tk.Frame(tray_content, background=palette["card"])
        self.tray_heading.pack(fill="x", padx=20, pady=(17, 10))
        tray_title = tk.Label(self.tray_heading, text="Accessory tray", font=fonts["section"],
                              bg=palette["card"], fg=palette["ink"])
        self.tray_count = tk.StringVar(master=self, value="")
        tray_count = tk.Label(self.tray_heading, textvariable=self.tray_count, font=fonts["small"],
                              bg=palette["card"], fg=palette["muted"])
        self._bind_heading_layout(self.tray_heading, tray_title, tray_count)

        self.notice_label = tk.Label(
            tray_content, textvariable=self.notice, font=fonts["small"], anchor="w",
            justify="left", bg=palette["peach"], fg=palette["accent_dark"], padx=12, pady=8,
        )
        self.notice_label.bind(
            "<Configure>",
            lambda event: self._rewrap(self.notice_label, event.width - 24),
            add="+",
        )

        self.filter_bar = tk.Frame(tray_content, background=palette["card"])
        self.filter_bar.pack(fill="x", padx=20, pady=(0, 12))
        self.filter_buttons: dict[str, RoundedChoice] = {}
        for key, label in FILTER_LABELS.items():
            self.filter_buttons[key] = RoundedChoice(
                self.filter_bar, text=label, variable=self.filter, value=key,
                command=self._apply_filter, indicatoron=False, font=fonts["small"],
                background=palette["card"], selectcolor=palette["accent"],
                activebackground=palette["peach"], foreground=palette["ink"],
                relief="flat", borderwidth=0, padx=12, pady=5,
                highlightthickness=1, highlightcolor=palette["accent_dark"],
                highlightbackground=palette["border"], takefocus=True, cursor="hand2",
            )
        self._filter_width = 0
        self.filter_bar.bind("<Configure>", self._flow_filters, add="+")

        self.choices_area = tk.Frame(tray_content, background=palette["card"])
        self.choices_area.pack(fill="x", padx=15, pady=(0, 19))
        self.choices_area.bind("<Configure>", lambda _event: self._layout_tiles(), add="+")
        self._none_art = self._thumbnail()
        for slot in ACCESSORY_SLOTS:
            self._build_section(slot)
        self.update_unlocks(unlocked)

    # Layout ----------------------------------------------------------------

    def _bind_heading_layout(self, header: tk.Frame, title: tk.Label, trailing: tk.Label) -> None:
        """Keep a heading and its count on one line, stacking them when narrow."""
        trailing_font = tkfont.Font(trailing, font=trailing.cget("font"))
        header.grid_columnconfigure(0, weight=1)
        title.configure(anchor="w", justify="left")
        title.grid(row=0, column=0, sticky="ew")
        trailing.grid(row=0, column=1, sticky="e", padx=(16, 0))
        previous_mode = None

        def arrange(_event: tk.Event) -> None:
            nonlocal previous_mode
            width = header.winfo_width()
            if width <= 1:
                return
            trailing_width = trailing_font.measure(str(trailing.cget("text"))) + 4
            title_width = tkfont.Font(title, font=title.cget("font")).measure(str(title.cget("text")))
            stacked = self._responsive_width(width) < title_width + trailing_width + 16
            if previous_mode != stacked:
                previous_mode = stacked
                title.grid_configure(columnspan=2 if stacked else 1)
                trailing.grid_configure(
                    row=1 if stacked else 0, column=0 if stacked else 1,
                    columnspan=2 if stacked else 1, sticky="w" if stacked else "e",
                    padx=0 if stacked else (16, 0), pady=(4, 0) if stacked else 0,
                )
            self._rewrap(title, width - 4 if stacked else width - trailing_width - 20)
            self._rewrap(trailing, width - 4)

        header.bind("<Configure>", arrange)
        trailing.bind("<Configure>", arrange, add="+")

    @staticmethod
    def _rewrap(label: tk.Label, width: int) -> None:
        # Wrapping changes height, which emits Configure again; reapplying the
        # same width can keep Tk's geometry queue alive on macOS.
        width = max(1, int(width))
        if int(str(label.cget("wraplength"))) != width:
            label.configure(wraplength=width)

    def _flow_filters(self, event: tk.Event[tk.Misc] | None = None) -> None:
        """Wrap the filter chips onto as many rows as the tray width needs."""
        width = event.width if event is not None else self.filter_bar.winfo_width()
        if width <= 1 or width == self._filter_width:
            return
        self._filter_width = width
        flow_choices(self.filter_bar, list(self.filter_buttons.values()), width)

    def _build_section(self, slot: str) -> None:
        palette, fonts = self.palette, self.fonts
        section = tk.Frame(self.choices_area, background=palette["card"])
        self.sections[slot] = section
        header = tk.Frame(section, background=palette["card"])
        header.pack(fill="x", padx=5, pady=(4, 10))
        title = tk.Label(header, text=SECTION_LABELS[slot], font=fonts["section"],
                         bg=palette["card"], fg=palette["ink"])
        count = self._section_counts[slot] = tk.StringVar(master=self)
        count_label = tk.Label(header, textvariable=count, font=fonts["small"],
                               bg=palette["card"], fg=palette["muted"])
        self._bind_heading_layout(header, title, count_label)
        grid = self._section_grids[slot] = tk.Frame(section, background=palette["card"])
        grid.pack(fill="x", pady=(0, 16))
        self.none_tiles[slot] = AccessoryTile(
            grid, item_id=None, slot=slot, name="None", blurb="Just the cat.", art=self._none_art,
            palette=palette, fonts=fonts,
            command=lambda slot=slot: self._choose_none(slot),
            on_hover=self._hover_tile,
        )

    def _thumbnail(self, slot: str | None = None, item_id: str | None = None) -> Image.Image:
        outfit = {slot: item_id} if slot and item_id else {}
        with load_frame(self.assets_root, "white", "idle", AccessoryTile.THUMBNAIL, **outfit) as frame:
            return frame.convert("RGBA").copy()

    def _tile_for(self, item: Accessory) -> AccessoryTile:
        tile = self.tiles.get(item.id)
        if tile is None:
            tile = self.tiles[item.id] = AccessoryTile(
                self._section_grids[item.slot], item_id=item.id, slot=item.slot,
                name=item.name, blurb=ACCESSORY_BLURBS[item.id],
                art=self._thumbnail(item.slot, item.id),
                palette=self.palette, fonts=self.fonts,
                command=lambda item_id=item.id: self._activate_item(item_id),
                on_hover=self._hover_tile,
            )
        return tile

    def _tile_minimum(self) -> int:
        line = self.fonts["control"].metrics("linespace")
        return max(AccessoryTile.THUMBNAIL + 32, round(line * 6.5))

    def _layout_tiles(self) -> None:
        width = self.choices_area.winfo_width()
        if width <= 1:
            return
        gap = 10
        layout_width = self._responsive_width(width)
        columns = max(1, min(5, (layout_width + gap) // (self._tile_minimum() + gap)))
        # Every tile carries half the gap on each side so columns stay equal.
        tile_width = max(1, width // columns - gap)
        selected = self.filter.get()
        shown = tuple(slot for slot in ACCESSORY_SLOTS
                      if selected in ("all", slot) and self._slot_items(slot))
        key = (columns, tile_width, shown, self._visible_ids)
        if key == self._layout_key:
            return
        self._layout_key = key
        for slot in ACCESSORY_SLOTS:
            section = self.sections[slot]
            if slot not in shown:
                section.pack_forget()
                continue
            if not section.winfo_manager():
                section.pack(fill="x", before=self._next_packed_section(slot))
            grid = self._section_grids[slot]
            tiles = [self.none_tiles[slot], *(self.tiles[item.id] for item in self._slot_items(slot))]
            for column in range(5):
                grid.grid_columnconfigure(
                    column, weight=1 if column < columns else 0,
                    uniform="tiles" if column < columns else "", minsize=0,
                )
            for index, tile in enumerate(tiles):
                row, column = divmod(index, columns)
                tile.fit_width(tile_width)
                tile.grid(row=row, column=column, sticky="nsew",
                          padx=gap // 2, pady=(0 if row == 0 else gap, 0))

    def _next_packed_section(self, slot: str) -> tk.Misc | None:
        later = ACCESSORY_SLOTS[ACCESSORY_SLOTS.index(slot) + 1:]
        return next((self.sections[name] for name in later if self.sections[name].winfo_manager()), None)

    def _slot_items(self, slot: str) -> tuple[Accessory, ...]:
        return tuple(item for item in self._visible_items if item.slot == slot)

    def _apply_filter(self) -> None:
        self._on_content_change()
        self._layout_tiles()

    # State -----------------------------------------------------------------

    def _progress_for(self, item: Accessory) -> tuple[int, int] | None:
        if self._metrics is None or item.metric == "beta":
            return None
        return progress(item, self._metrics()), item.target

    def refresh_progress(self) -> None:
        """Redraw locked tiles' meters from the latest activity totals."""
        self._refresh_status()

    def _refresh_status(self) -> None:
        for item in self._visible_items:
            tile = self.tiles[item.id]
            if item.id not in self.unlocked:
                tile.set_state("locked", is_new=False, progress_value=self._progress_for(item))
            else:
                equipped = self.slots[item.slot].get() == item.id
                tile.set_state("equipped" if equipped else "unlocked", is_new=item.id in self._new_ids)
        for slot, tile in self.none_tiles.items():
            tile.set_state("equipped" if self.slots[slot].get() == "none" else "unlocked")
        for slot in ACCESSORY_SLOTS:
            items = self._slot_items(slot)
            earned = sum(item.id in self.unlocked for item in items)
            self._section_counts[slot].set(f"{earned} of {len(items)} unlocked")
        earned_total = sum(item.id in self.unlocked for item in self._visible_items)
        self.tray_count.set(f"{earned_total} of {len(self._visible_items)} unlocked")

    def _activate_item(self, item_id: str) -> None:
        if item_id not in self.unlocked:
            self._end_try_on()
            self.on_achievement(item_id)
            return
        item = ACCESSORY_BY_ID[item_id]
        if self.slots[item.slot].get() == item_id:
            return
        self.slots[item.slot].set(item_id)
        self._choose()

    def _choose_none(self, slot: str) -> None:
        if self.slots[slot].get() == "none":
            return
        self.slots[slot].set("none")
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
            choices = [item.id for item in visible if item.slot == slot and item.id in self.unlocked]
            if choices:
                choice = random.choice(choices)
                if variable.get() != choice:
                    variable.set(choice)
                    changed = True
        if changed:
            self._choose()

    # Try-on ----------------------------------------------------------------

    def _hover_tile(self, tile: AccessoryTile, hovered: bool) -> None:
        if hovered:
            self._cancel_restore()
            self._try_on_tile = tile
            outfit = {slot: variable.get() for slot, variable in self.slots.items()}
            outfit[tile.slot] = tile.item_id or "none"
            label = "No " + FILTER_LABELS[tile.slot].lower() if tile.item_id is None else tile.name
            self._on_try_on(outfit, label)
        elif tile is self._try_on_tile and self._restore_after_id is None:
            self._restore_after_id = self.after(TRY_ON_RESTORE_MS, self._end_try_on)

    def _end_try_on(self) -> None:
        self._cancel_restore()
        if self._try_on_tile is not None:
            self._try_on_tile = None
            self._on_try_on(None, "")

    def _cancel_restore(self, event: tk.Event | None = None) -> None:
        if event is not None and event.widget is not self:
            return
        if self._restore_after_id is not None:
            self.after_cancel(self._restore_after_id)
            self._restore_after_id = None

    # Public ----------------------------------------------------------------

    def focus_item(self, item_id: str) -> AccessoryTile:
        item = ACCESSORY_BY_ID[item_id]
        if self.filter.get() not in ("all", item.slot):
            self.filter.set("all")
            self._apply_filter()
        tile = self.tiles[item_id]
        tile.focus_set()
        return tile

    def set_preview(self, frame: ImageTk.PhotoImage) -> None:
        # The cat stage shows the outfit; the latest frame is kept for callers.
        self._preview_frame = frame

    def update_unlocks(self, unlocked: set[str], newly_unlocked: tuple[Accessory, ...] = ()) -> None:
        self.unlocked = set(unlocked)
        visible = visible_accessories(self.unlocked)
        self._visible_items = visible
        visible_ids = tuple(item.id for item in visible)
        for item in visible:
            self._tile_for(item)
        for item_id in [item_id for item_id in self.tiles if item_id not in visible_ids]:
            self.tiles.pop(item_id).destroy()
        if visible_ids != self._visible_ids:
            self._on_content_change()
        self._visible_ids = visible_ids
        if newly_unlocked:
            self._new_ids.update(item.id for item in newly_unlocked)
            self.notice.set("New in your tray: " + ", ".join(item.name for item in newly_unlocked))
            if not self.notice_label.winfo_manager():
                self.notice_label.pack(fill="x", padx=20, pady=(0, 12), before=self.filter_bar)
        self._refresh_status()
        self._layout_tiles()
