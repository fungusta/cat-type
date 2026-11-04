"""Rounded native surfaces shared by the settings destinations."""

from __future__ import annotations

import functools
import sys
import time
import tkinter as tk
from collections.abc import Callable

from tkinter import font as tkfont
from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageTk


BUTTON_SHADOW = "#4A3428"
BUTTON_BORDER = "#E2D9D0"
BUTTON_HOVER = "#FFF5D1"
BUTTON_ACCENT = "#F2D66B"
BUTTON_INK = "#302A33"
BUTTON_MUTED = "#575059"
BUTTON_DISABLED = "#F3EFEA"
UNREAD_DOT = "#D9822B"
BUTTON_DISABLED_EDGE = "#E8E1DA"
SOFT_PILL_MAX_RADIUS = 14
# Fluent motion timings: hover/press feedback is "fast", state changes "normal".
MOTION_FAST_MS = 120
MOTION_NORMAL_MS = 167
MOTION_FRAME_MS = 16
_SUPERSAMPLE = 4


def soft_pill_radius(height: int) -> int:
    """Return a soft corner radius without turning short buttons into capsules."""
    return min(SOFT_PILL_MAX_RADIUS, max(4, round(height / 2.6)))


def blend(start: str, end: str, amount: float) -> str:
    """Mix two Tk colors, returning a hex color ``amount`` of the way to ``end``."""
    amount = min(1.0, max(0.0, amount))
    first = ImageColor.getrgb(start)[:3]
    second = ImageColor.getrgb(end)[:3]
    return "#{:02X}{:02X}{:02X}".format(
        *(round(a + (b - a) * amount) for a, b in zip(first, second))
    )


def ease_out(progress: float) -> float:
    """Decelerating curve: quick response that settles gently."""
    return 1 - (1 - progress) ** 3


@functools.lru_cache(maxsize=1)
def prefers_reduced_motion() -> bool:
    """Respect the platform's "show animations" accessibility preference."""
    if sys.platform == "win32":
        try:
            import ctypes

            enabled = ctypes.c_int(1)
            # SPI_GETCLIENTAREAANIMATION mirrors Settings > Accessibility >
            # Visual effects > Animation effects.
            if ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0):
                return not enabled.value
        except (AttributeError, OSError):
            pass
    return False


class Tween:
    """Ease a 0..1 value toward a target on the Tk event loop.

    Frames are delivered through ``on_frame``. Unmapped widgets and reduced
    motion jump straight to the target, so state never waits on animation.
    """

    def __init__(
        self,
        widget: tk.Misc,
        on_frame: Callable[[float], None],
        *,
        duration_ms: int = MOTION_FAST_MS,
        value: float = 0.0,
    ) -> None:
        self.widget = widget
        self.on_frame = on_frame
        self.duration_ms = duration_ms
        self.value = value
        self.target = value
        self._after_id: str | None = None

    def cancel(self) -> None:
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def to(self, target: float) -> None:
        target = float(target)
        if target == self.target and (self._after_id is not None or target == self.value):
            return
        self.cancel()
        self.target = target
        start = self.value
        try:
            animate = bool(self.widget.winfo_ismapped()) and not prefers_reduced_motion()
        except tk.TclError:
            return
        if not animate or start == target:
            self.value = target
            self.on_frame(target)
            return
        # A reversal part-way through only replays the distance it covers.
        duration = max(MOTION_FRAME_MS, self.duration_ms * abs(target - start))
        began = time.perf_counter()

        def step() -> None:
            self._after_id = None
            progress = min(1.0, (time.perf_counter() - began) * 1000 / duration)
            self.value = start + (target - start) * ease_out(progress)
            if progress >= 1.0:
                self.value = target
            try:
                self.on_frame(self.value)
                if progress < 1.0:
                    self._after_id = self.widget.after(MOTION_FRAME_MS, step)
            except tk.TclError:
                pass  # The widget closed mid-animation.

        step()


_pill_cache: dict[tuple[object, ...], Image.Image] = {}
_PILL_CACHE_LIMIT = 384


def _quantized(value: float) -> float:
    return round(min(1.0, max(0.0, value)) * 8) / 8


def soft_pill_image(
    surface: str,
    width: int,
    height: int,
    fill: str,
    *,
    pressed: bool = False,
    focused: bool = False,
    disabled: bool = False,
    lift: float = 0.0,
    flat: bool = False,
    border: str | None = None,
) -> Image.Image:
    """Rasterize a hairline pill with a soft ambient shadow.

    ``lift`` (0..1) raises the shadow for hover; ``flat`` drops elevation for
    chips and quiet navigation items. A Butter outer ring and ink hairline
    mark keyboard focus.
    """
    width, height = max(1, int(width)), max(1, int(height))
    lift = _quantized(lift)
    if disabled:
        fill, border = BUTTON_DISABLED, BUTTON_DISABLED_EDGE
    elif border is None:
        border = (
            BUTTON_BORDER
            if ImageColor.getrgb(fill)[:3] == (255, 255, 255)
            else blend(fill, "#7A5C2E", 0.2)
        )
    if focused and not disabled:
        border = BUTTON_INK
    key = (surface, width, height, fill, pressed, focused, disabled, lift, flat, border)
    cached = _pill_cache.get(key)
    if cached is not None:
        return cached

    pad_x, pad_top, pad_bottom = (1, 1, 1) if flat and not focused else (3, 3, 4)
    press = 1 if pressed and not disabled else 0
    left, right = pad_x, max(pad_x + 1, width - pad_x)
    top = min(height - 1, pad_top + press)
    bottom = max(top + 1, height - pad_bottom + press)
    radius = soft_pill_radius(bottom - top)

    image = Image.new("RGBA", (width, height), ImageColor.getrgb(surface)[:3] + (255,))
    if not flat and not disabled:
        if pressed:
            offset, blur, alpha = 0.5, 1.0, 22
        else:
            offset, blur, alpha = 1 + lift * 1.5, 1.6 + lift * 1.4, 26 + round(lift * 20)
        mask = Image.new("L", (width, height), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (left, top + offset, right, bottom + offset), radius=radius, fill=alpha,
        )
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
        image.paste(BUTTON_SHADOW, (0, 0, width, height), mask)

    scale = _SUPERSAMPLE
    face = Image.new("RGBA", (width * scale, height * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(face)
    if focused and not disabled:
        ring = 2.5
        draw.rounded_rectangle(
            (max(0, left - ring) * scale, max(0, top - ring) * scale,
             min(width, right + ring) * scale, min(height, bottom + ring) * scale),
            radius=(radius + ring) * scale,
            outline=BUTTON_ACCENT,
            width=2 * scale,
        )
    draw.rounded_rectangle(
        (left * scale, top * scale, right * scale, bottom * scale),
        radius=radius * scale,
        fill=fill,
        outline=border,
        width=scale,
    )
    face = face.resize((width, height), Image.Resampling.LANCZOS)
    image.alpha_composite(face)
    image = image.convert("RGB")
    if len(_pill_cache) >= _PILL_CACHE_LIMIT:
        _pill_cache.pop(next(iter(_pill_cache)))
    _pill_cache[key] = image
    return image


def render_soft_pill(
    master: tk.Misc,
    surface: str,
    width: int,
    height: int,
    fill: str,
    **options: object,
) -> ImageTk.PhotoImage:
    """Render the one shared pill surface used by every settings control."""
    return ImageTk.PhotoImage(
        soft_pill_image(_hex(master, surface), width, height, _hex(master, fill), **options),
        master=master,
    )


PROGRESS_TRACK = "#EFE8E1"
_mark_cache: dict[tuple[object, ...], Image.Image] = {}
_MARK_CACHE_LIMIT = 256


def _cached_mark(key: tuple[object, ...], draw: Callable[[], Image.Image]) -> Image.Image:
    cached = _mark_cache.get(key)
    if cached is None:
        if len(_mark_cache) >= _MARK_CACHE_LIMIT:
            _mark_cache.pop(next(iter(_mark_cache)))
        cached = _mark_cache[key] = draw()
    return cached


def progress_bar_image(
    surface: str, width: int, height: int, fraction: float, *,
    track: str = PROGRESS_TRACK, fill: str = BUTTON_ACCENT,
) -> Image.Image:
    """Rasterize an anti-aliased pill meter; Tk canvas lines are aliased."""
    width, height = max(2, int(width)), max(2, int(height))
    fraction = min(1.0, max(0.0, fraction))
    # Any progress at all shows, so a just-started goal never reads as empty.
    filled = max(1, round(fraction * width)) if fraction > 0 else 0

    def draw() -> Image.Image:
        scale = _SUPERSAMPLE
        image = Image.new("RGB", (width * scale, height * scale), surface)
        pen = ImageDraw.Draw(image)
        radius = height * scale / 2
        pen.rounded_rectangle((0, 0, width * scale - 1, height * scale - 1), radius=radius, fill=track)
        if filled:
            # A sliver keeps its rounded ends instead of collapsing to a dot.
            end = max(filled, height) * scale - 1
            pen.rounded_rectangle((0, 0, end, height * scale - 1), radius=radius, fill=fill,
                                  outline=blend(fill, "#7A5C2E", 0.2), width=scale)
        return image.resize((width, height), Image.Resampling.LANCZOS)

    return _cached_mark(("bar", surface, width, height, filled, track, fill), draw)


def status_mark_image(surface: str, size: int, kind: str) -> Image.Image:
    """A small round badge: a Butter check for earned, a quiet padlock for locked."""
    size = max(8, int(size))

    def draw() -> Image.Image:
        scale = _SUPERSAMPLE
        side = size * scale
        image = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        pen = ImageDraw.Draw(image)
        if kind == "check":
            pen.ellipse((0, 0, side - 1, side - 1), fill=BUTTON_ACCENT,
                        outline=blend(BUTTON_ACCENT, "#7A5C2E", 0.25), width=scale)
            pen.line(((side * .28, side * .52), (side * .44, side * .67), (side * .73, side * .35)),
                     fill=BUTTON_INK, width=max(scale, round(side * .1)), joint="curve")
        else:
            pen.ellipse((0, 0, side - 1, side - 1), fill=BUTTON_DISABLED,
                        outline=BUTTON_DISABLED_EDGE, width=scale)
            stroke = max(scale, round(side * .08))
            pen.arc((side * .36, side * .2, side * .64, side * .52), 180, 360,
                    fill=BUTTON_MUTED, width=stroke)
            pen.line(((side * .36, side * .37), (side * .36, side * .46)), fill=BUTTON_MUTED, width=stroke)
            pen.line(((side * .64, side * .37), (side * .64, side * .46)), fill=BUTTON_MUTED, width=stroke)
            pen.rounded_rectangle((side * .29, side * .44, side * .71, side * .76),
                                  radius=side * .06, fill=BUTTON_MUTED)
        backdrop = Image.new("RGBA", (side, side), ImageColor.getrgb(surface)[:3] + (255,))
        backdrop.alpha_composite(image)
        return backdrop.convert("RGB").resize((size, size), Image.Resampling.LANCZOS)

    return _cached_mark(("mark", surface, size, kind), draw)


def faded_art(image: Image.Image, surface: str = "#FFFFFF") -> Image.Image:
    """Desaturate and lighten artwork so locked rewards read as not yet earned."""
    rgba = image.convert("RGBA")
    gray = rgba.convert("L").convert("RGB")
    washed = Image.blend(gray, Image.new("RGB", rgba.size, surface), 0.4)
    washed.putalpha(rgba.getchannel("A"))
    return washed


def _hex(widget: tk.Misc, color: str) -> str:
    """Resolve Tk-only names such as ``SystemButtonFace`` for Pillow."""
    if color.startswith("#"):
        return color
    red, green, blue = (value >> 8 for value in widget.winfo_rgb(color))
    return f"#{red:02X}{green:02X}{blue:02X}"


def nav_icon_image(kind: str, size: int, color: str = BUTTON_INK) -> Image.Image:
    """A small line icon for a navigation item, on a transparent background."""
    size = max(8, int(size))

    def draw() -> Image.Image:
        side = size * _SUPERSAMPLE
        image = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        pen = ImageDraw.Draw(image)
        stroke = max(_SUPERSAMPLE, round(side * .09))

        def at(*points: float) -> list[tuple[float, float]]:
            return [(points[i] * side, points[i + 1] * side) for i in range(0, len(points), 2)]

        def dot(x: float, y: float, radius: float) -> None:
            pen.ellipse((side * (x - radius), side * (y - radius),
                         side * (x + radius), side * (y + radius)), fill=color)

        if kind == "settings":  # three sliders
            for y, knob in ((.24, .34), (.5, .66), (.76, .44)):
                pen.line(at(.1, y, .9, y), fill=color, width=stroke)
                dot(knob, y, .11)
        elif kind == "metrics":  # rising columns
            for left, top in ((.12, .56), (.4, .34), (.68, .12)):
                pen.rounded_rectangle((side * left, side * top, side * (left + .2), side * .88),
                                      radius=side * .05, fill=color)
        elif kind == "wardrobe":  # coat hanger
            pen.arc((side * .4, side * .1, side * .6, side * .3), 180, 90, fill=color, width=stroke)
            pen.line(at(.5, .3, .5, .38, .08, .72, .92, .72, .5, .38), fill=color,
                     width=stroke, joint="curve")
        else:  # trophy
            pen.chord((side * .26, side * -.08, side * .74, side * .6), 0, 180, fill=color)
            pen.rectangle((side * .26, side * .1, side * .74, side * .26), fill=color)
            for box, start, end in (((.1, .14, .36, .42), 90, 270), ((.64, .14, .9, .42), 270, 90)):
                pen.arc(tuple(side * value for value in box), start, end, fill=color, width=stroke)
            pen.line(at(.5, .5, .5, .74), fill=color, width=stroke)
            pen.rounded_rectangle((side * .3, side * .74, side * .7, side * .9),
                                  radius=side * .04, fill=color)
        return image.resize((size, size), Image.Resampling.LANCZOS)

    return _cached_mark(("nav", kind, size, color), draw)


class RoundedChoice(tk.Radiobutton):
    """Native radio behavior with a softly rounded visual face.

    ``variant="ghost"`` keeps unselected items flush with their surface until
    hovered, which suits navigation lists. ``icon`` names a ``nav_icon_image``
    drawn just before the centred label.
    """

    def __init__(self, parent: tk.Misc, **kwargs: object) -> None:
        self._surface = str(parent.cget("background"))
        self._face = str(kwargs.pop("background", self._surface))
        self._accent = str(kwargs.pop("selectcolor", self._face))
        self._edge = str(kwargs.pop("highlightbackground", self._face))
        self._ghost = kwargs.pop("variant", "") == "ghost"
        self._hover_fill = BUTTON_HOVER
        self._shadow = BUTTON_SHADOW
        self._hovered = False
        self._pressed = False
        self._focused = False
        self._hover = Tween(self, lambda _value: self._render())
        kwargs.pop("activebackground", None)
        kwargs.pop("highlightcolor", None)
        kwargs.pop("highlightthickness", None)
        text = str(kwargs.get("text", ""))
        variable = kwargs.get("textvariable")
        if variable is not None:
            text = str(variable.get())
        face = tkfont.Font(parent, font=kwargs.get("font"))
        self._icon = kwargs.pop("icon", None)
        self._label_var = variable
        self._label_face = face
        self._icon_pad = ""
        self._compact = False
        self._display: tk.StringVar | None = None
        self._plain_label = text
        if self._icon:
            # Tk centres a button's text over its image, so leading spaces
            # open room for the icon, which the face then draws in that gap.
            self._icon_size = round(face.metrics("linespace") * .8)
            self._icon_gap = max(5, round(self._icon_size * .35))
            space = max(1, face.measure(" "))
            self._icon_pad = " " * -(-(self._icon_size + self._icon_gap) // space)
            if variable is not None:
                display = self._display = tk.StringVar(master=parent, value=self._icon_pad + text)
                variable.trace_add("write", lambda *_args: self._sync_icon_label())
                kwargs["textvariable"] = display
            else:
                kwargs["text"] = self._icon_pad + text
        min_width = int(kwargs.pop("min_width", 0))
        padx = int(kwargs.pop("padx", 10))
        pady = int(kwargs.pop("pady", 8))
        self._size = (
            max(min_width, 60, face.measure(self._icon_pad + text) + (padx * 2) + 8),
            face.metrics("linespace") + (pady * 2) + 6,
        )
        self._natural_size = self._size
        self._text_padding = padx
        self._vertical_padding = pady
        super().__init__(
            parent,
            background=self._surface,
            activebackground=self._surface,
            selectcolor=self._surface,
            highlightthickness=0,
            padx=0,
            pady=0,
            compound="center",
            **kwargs,
        )
        self.bind("<Enter>", lambda _event: self._set_hover(True), add="+")
        self.bind("<Leave>", lambda _event: self._set_hover(False), add="+")
        self.bind("<ButtonPress-1>", lambda _event: self._set_pressed(True), add="+")
        self.bind("<ButtonRelease-1>", lambda _event: self._set_pressed(False), add="+")
        self.bind("<FocusIn>", lambda _event: self._set_focus(True), add="+")
        self.bind("<FocusOut>", lambda _event: self._set_focus(False), add="+")
        self._render()

    def _label(self) -> str:
        if self._label_var is not None:
            return str(self._label_var.get())
        return self._plain_label

    def _sync_icon_label(self) -> None:
        # A compact item shows only its icon; the label stays the accessible name.
        shown = "" if self._compact else self._icon_pad + self._label()
        if self._display is not None:
            self._display.set(shown)
        else:
            super().configure(text=shown)
        self._render()

    def set_compact(self, compact: bool) -> None:
        """Show just the icon, for a navigation rail collapsed on narrow windows."""
        if not self._icon or compact == self._compact:
            return
        self._compact = compact
        self._size = ((max(44, self._icon_size + self._text_padding * 2 + 8), self._natural_size[1])
                      if compact else self._natural_size)
        self._sync_icon_label()

    def _with_icon(self, image: Image.Image) -> Image.Image:
        """Draw the icon in the gap the leading spaces leave before the label."""
        width, height = self._size
        size = self._icon_size
        face = self._label_face
        top = (height - 1 - size) // 2 + (1 if self._pressed else 0)
        if self._compact:
            left = (width - size) // 2
        else:
            line = face.measure(self._icon_pad + self._label())
            left = (width - line) // 2 + face.measure(self._icon_pad) - self._icon_gap - size
        composed = image.convert("RGBA")
        composed.alpha_composite(nav_icon_image(self._icon, size), (max(0, left), max(0, top)))
        if self._compact and "New" in self._label():
            # Without its label, an unread item keeps a small marker by its icon.
            dot = max(4, size // 4)
            x, y = left + size - dot // 2, top - dot // 2
            ImageDraw.Draw(composed).ellipse((x, y, x + dot, y + dot), fill=UNREAD_DOT)
        return composed.convert("RGB")

    def fit_width(self, width: int) -> None:
        """Wrap the label when the available width cannot fit its natural face."""
        width = min(self._natural_size[0], max(1, width))
        if width == self._size[0]:
            return
        wrap = max(1, width - self._text_padding * 2 - 8) if width < self._natural_size[0] else 0
        if wrap:
            measure = tk.Label(self, text=self.cget("text"), font=self.cget("font"),
                               wraplength=wrap, justify="center")
            height = measure.winfo_reqheight() + self._vertical_padding * 2 + 4
            measure.destroy()
        else:
            height = self._natural_size[1]
        size = (width, height)
        self._size = size
        super().configure(wraplength=wrap)
        self._render()

    def _set_hover(self, hovered: bool) -> None:
        self._hovered = hovered
        self._hover.to(1.0 if hovered else 0.0)

    def _set_pressed(self, pressed: bool) -> None:
        self._pressed = pressed
        self._render()

    def _set_focus(self, focused: bool) -> None:
        self._focused = focused
        self._render()

    def _render(self) -> None:
        width, height = self._size
        hover = self._hover.value
        if self._ghost:
            normal_fill = blend(self._surface, self._hover_fill, hover)
            normal = dict(flat=True, border=normal_fill)
        else:
            normal_fill = blend(self._face, self._hover_fill, hover)
            normal = dict(lift=hover)
        faces = [
            soft_pill_image(
                _hex(self, self._surface), width, height, _hex(self, normal_fill),
                pressed=self._pressed, focused=self._focused, **normal,
            ),
            soft_pill_image(
                _hex(self, self._surface), width, height, _hex(self, self._accent),
                pressed=self._pressed, focused=self._focused, lift=hover,
            ),
        ]
        if self._icon:
            faces = [self._with_icon(face) for face in faces]
        images = [ImageTk.PhotoImage(face, master=self) for face in faces]
        self._images = images
        super().configure(image=images[0], selectimage=images[1])

    def configure(self, cnf: dict | None = None, **kwargs: object) -> object:
        if cnf is not None:
            return super().configure(cnf, **kwargs)
        redraw = False
        for name, attribute in (
            ("background", "_face"),
            ("selectcolor", "_accent"),
            ("highlightbackground", "_edge"),
        ):
            if name in kwargs:
                setattr(self, attribute, str(kwargs.pop(name)))
                redraw = True
        result = super().configure(**kwargs) if kwargs else None
        if redraw:
            self._render()
        return result

    config = configure

    def __getitem__(self, key: str) -> object:
        return self.cget(key)

    def cget(self, key: str) -> object:
        if key == "text" and self._icon:
            return self._label()
        if key == "textvariable" and self._icon and self._label_var is not None:
            # Report the caller's variable; the padded one is display only.
            return str(self._label_var)
        if key == "background":
            return self._face
        if key == "selectcolor":
            return self._accent
        if key == "highlightbackground":
            return self._edge
        return super().cget(key)


def flow_choices(bar: tk.Frame, buttons: list[RoundedChoice], width: int, gap: int = 6) -> None:
    """Wrap a row of choice chips onto as many lines as ``width`` needs.

    Chips are placed rather than gridded so wrapped rows never share column
    widths; the bar is given the height of the rows it holds.
    """
    x = y = row_height = 0
    for button in buttons:
        # Native chrome can add a pixel or two around the drawn face.
        chrome = max(0, button.winfo_reqwidth() - button._size[0])
        button.fit_width(width - chrome)
        needed = max(button._size[0], button.winfo_reqwidth())
        if x and x + needed > width:
            x, y, row_height = 0, y + row_height + gap, 0
        button.place(x=x, y=y)
        x += needed + gap
        row_height = max(row_height, button.winfo_reqheight())
    bar.configure(height=max(1, y + row_height))


class RoundedAction(tk.Canvas):
    """A keyboard-usable soft pill with a subtle, shared lift.

    Tk canvases do not expose native accessibility roles, so the custom
    ``accessible_*`` options provide a stable role, name, and state for
    accessibility adapters while preserving the drawn surface.
    """

    def __init__(self, parent: tk.Misc, **kwargs: object) -> None:
        self._text = str(kwargs.pop("text", ""))
        self._command = kwargs.pop("command", None)
        self._state = str(kwargs.pop("state", "normal"))
        style = str(kwargs.pop("style", ""))
        self._accent = BUTTON_ACCENT
        self._ink = BUTTON_INK
        self._muted = BUTTON_MUTED
        self._shadow = BUTTON_SHADOW
        self._border = BUTTON_BORDER
        self._fill = self._accent if "Accent" in style else "#FFFFFF"
        self._font = kwargs.pop("font", "TkDefaultFont")
        self._pressed = False
        self._focused = False
        self._hovered = False
        self._hover = Tween(self, lambda _value: self._draw())
        face = tkfont.Font(parent, font=self._font)
        self._width = max(68, face.measure(self._text) + 24)
        self._height = max(34, face.metrics("linespace") + 18)
        self._max_width: int | None = None
        self._wrap_width = 0
        super().__init__(
            parent,
            width=self._width,
            height=self._height,
            background=str(parent.cget("background")),
            highlightthickness=0,
            borderwidth=0,
            takefocus=kwargs.pop("takefocus", True),
            cursor=kwargs.pop("cursor", "hand2"),
            **kwargs,
        )
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<FocusIn>", lambda _event: self._focus_changed(True), add="+")
        self.bind("<FocusOut>", lambda _event: self._focus_changed(False), add="+")
        self.bind("<Enter>", lambda _event: self._set_hover(True), add="+")
        self.bind("<Leave>", lambda _event: self._set_hover(False), add="+")
        self.bind("<Return>", self._activate)
        self.bind("<space>", self._activate)
        self._draw()

    def _focus_changed(self, focused: bool) -> None:
        self._focused = focused
        self._draw()

    def _set_hover(self, hovered: bool) -> None:
        self._hovered = hovered
        self._hover.to(1.0 if hovered and self._state != "disabled" else 0.0)

    def _press(self, _event: tk.Event[tk.Misc]) -> None:
        if self._state != "disabled":
            self._pressed = True
            self.focus_set()
            self._draw()

    def _release(self, _event: tk.Event[tk.Misc]) -> None:
        was_pressed = self._pressed
        self._pressed = False
        self._draw()
        if was_pressed:
            self.invoke()

    def _activate(self, _event: tk.Event[tk.Misc]) -> str:
        self.invoke()
        return "break"

    def invoke(self) -> object:
        if self._state == "disabled" or self._command is None:
            return None
        return self._command()

    def fit_width(self, width: int) -> None:
        """Fit and wrap button text within the available width."""
        self._max_width = max(1, width)
        face = tkfont.Font(self, font=self._font)
        natural_width = max(68, face.measure(self._text) + 24)
        new_width = min(natural_width, self._max_width)
        wrap_width = max(1, new_width - 24) if new_width < natural_width else 0
        if wrap_width:
            measure = tk.Label(self, text=self._text, font=self._font,
                               wraplength=wrap_width, justify="center")
            new_height = max(34, measure.winfo_reqheight() + 16)
            measure.destroy()
        else:
            new_height = max(34, face.metrics("linespace") + 18)
        if (new_width, new_height, wrap_width) != (self._width, self._height, self._wrap_width):
            self._width, self._height = new_width, new_height
            self._wrap_width = wrap_width
            super().configure(width=new_width, height=new_height)
            self._draw()

    def _draw(self) -> None:
        self.delete("all")
        width, height = self._width, self._height
        hover = getattr(self, "_hover", None)
        lift = hover.value if hover is not None else 0.0
        fill = self._fill if self._fill == self._accent else blend(self._fill, BUTTON_HOVER, lift)
        self._pill_image = render_soft_pill(
            self,
            str(self.cget("background")),
            width,
            height,
            fill,
            pressed=self._pressed,
            focused=self._focused,
            disabled=self._state == "disabled",
            lift=lift,
        )
        self.create_image(0, 0, anchor="nw", image=self._pill_image)
        # The face sits 3px from the top and 4px from the bottom to leave
        # room for its shadow; centre the label on the face, not the canvas.
        self.create_text(
            width // 2,
            (height - 1) // 2 + (1 if self._pressed else 0),
            text=self._text,
            fill=self._ink if self._state != "disabled" else self._muted,
            font=self._font,
            width=self._wrap_width,
            justify="center",
        )

    def create_round_rect(self, x1: int, y1: int, x2: int, y2: int, *, radius: int, **kwargs: object) -> int:
        points = (
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        )
        return self.create_polygon(*points, smooth=True, splinesteps=20, **kwargs)

    def configure(self, cnf: dict | None = None, **kwargs: object) -> object:
        if cnf is not None:
            return super().configure(cnf, **kwargs)
        redraw = False
        if "text" in kwargs:
            self._text = str(kwargs.pop("text"))
            face = tkfont.Font(self, font=self._font)
            self._width = max(68, face.measure(self._text) + 24)
            super().configure(width=self._width)
            if self._max_width is not None:
                self.fit_width(self._max_width)
            redraw = True
        if "state" in kwargs:
            self._state = str(kwargs.pop("state"))
            if self._state == "disabled":
                self._hover.cancel()
                self._hover.value = self._hover.target = 0.0
            redraw = True
        if "style" in kwargs:
            style = str(kwargs.pop("style"))
            self._fill = self._accent if "Accent" in style else "#FFFFFF"
            redraw = True
        result = super().configure(**kwargs) if kwargs else None
        if redraw:
            self._draw()
        return result

    config = configure

    def cget(self, key: str) -> object:
        if key == "text":
            return self._text
        if key == "state":
            return self._state
        if key == "accessible_role":
            return "button"
        if key == "accessible_name":
            return self._text
        if key == "accessible_state":
            return self._state
        return super().cget(key)


class RoundedBadge(tk.Canvas):
    """A non-interactive value chip for compact setting and reward states."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        text: str,
        font: object,
        fill: str = BUTTON_ACCENT,
        foreground: str = BUTTON_INK,
    ) -> None:
        self._text = str(text)
        self._font = font
        self._fill = fill
        self._foreground = foreground
        face = tkfont.Font(parent, font=font)
        self._width = max(42, face.measure(self._text) + 18)
        self._height = max(28, face.metrics("linespace") + 10)
        super().__init__(
            parent,
            width=self._width,
            height=self._height,
            background=str(parent.cget("background")),
            highlightthickness=0,
            borderwidth=0,
            takefocus=False,
        )
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        image = render_soft_pill(
            self,
            str(self.cget("background")),
            self._width,
            self._height,
            self._fill,
            flat=True,
            border=self._fill,
        )
        self._image = image
        self.create_image(0, 0, anchor="nw", image=image)
        self.create_text(
            self._width // 2,
            self._height // 2,
            text=self._text,
            fill=self._foreground,
            font=self._font,
        )

    def configure(self, cnf: dict | None = None, **kwargs: object) -> object:
        if cnf is not None:
            return super().configure(cnf, **kwargs)
        if "text" in kwargs:
            self._text = str(kwargs.pop("text"))
            face = tkfont.Font(self, font=self._font)
            self._width = max(42, face.measure(self._text) + 18)
            super().configure(width=self._width)
            self._draw()
        if "fill" in kwargs:
            self._fill = str(kwargs.pop("fill"))
            self._draw()
        if "foreground" in kwargs:
            self._foreground = str(kwargs.pop("foreground"))
            self._draw()
        return super().configure(**kwargs) if kwargs else None

    config = configure

    def cget(self, key: str) -> object:
        if key == "text":
            return self._text
        return super().cget(key)

class RoundedPanel(tk.Canvas):
    """A soft shelf surface that keeps native child widgets intact."""

    _raster_cache: dict[tuple[object, ...], Image.Image] = {}
    _raster_cache_limit = 128

    def __init__(
        self,
        parent: tk.Misc,
        *,
        background: str,
        fill: str,
        border: str,
        radius: int = 18,
        padding: int = 12,
        takefocus: bool = False,
    ) -> None:
        super().__init__(
            parent,
            background=background,
            highlightthickness=0,
            borderwidth=0,
            height=1,
            takefocus=takefocus,
        )
        self._fill = fill
        self._border = border
        self._radius = radius
        self._padding = padding
        self._focused = False
        self._last_draw_key: tuple[object, ...] | None = None
        self.content = tk.Frame(self, background=fill)
        self._content_id = self.create_window(
            padding,
            padding,
            anchor="nw",
            window=self.content,
        )
        self.content.bind("<Configure>", self._sync_size, add="+")
        self.bind("<Configure>", self._draw, add="+")
        self.bind("<FocusIn>", lambda _event: self._set_focus(True), add="+")
        self.bind("<FocusOut>", lambda _event: self._set_focus(False), add="+")
        self.after_idle(self._sync_size)

    def _set_focus(self, focused: bool) -> None:
        self._focused = focused
        self._draw()

    def _sync_size(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        if not self.winfo_exists():
            return
        current_width = self.winfo_width()
        width = (
            max(1, self.content.winfo_reqwidth())
            if current_width <= 1
            else max(1, current_width - self._padding * 2)
        )
        height = max(1, self.content.winfo_reqheight())
        # Leave the embedded frame's height driven by its children. Pinning
        # it to an earlier request suppresses Configure events when nested
        # shelves grow, so the outer canvas can retain a clipped old height.
        self.itemconfigure(self._content_id, width=width, height=0)
        if current_width <= 1:
            self.configure(width=width + self._padding * 2)
        self.configure(height=height + self._padding * 2)
        if current_width > 1:
            self._draw()

    def _paint_face(
        self, width: int, height: int, box: tuple[int, int, int, int], radius: int,
    ) -> Image.Image:
        scale = _SUPERSAMPLE
        left, top, right, bottom = box
        face = Image.new("RGBA", (width * scale, height * scale), (0, 0, 0, 0))
        draw = ImageDraw.Draw(face)
        draw.rounded_rectangle(
            (left * scale, top * scale, right * scale, bottom * scale),
            radius=radius * scale,
            fill=self._fill,
            outline=BUTTON_ACCENT if self._focused else self._border,
            width=(2 if self._focused else 1) * scale,
        )
        if self._focused:
            draw.rounded_rectangle(
                ((left + 2) * scale, (top + 2) * scale,
                 max((left + 3) * scale, (right - 2) * scale),
                 max((top + 3) * scale, (bottom - 2) * scale)),
                radius=max(1, radius - 2) * scale,
                outline=BUTTON_INK,
                width=scale,
            )
        return face.resize((width, height), Image.Resampling.LANCZOS)

    def _render_face(
        self, width: int, height: int, box: tuple[int, int, int, int], radius: int,
    ) -> Image.Image:
        """Supersample only the corners, then stretch the straight edges.

        A tall shelf at 4x is millions of pixels and made every height change
        visibly stall; the edges between corners are uniform, so a one-pixel
        strip stretched with NEAREST reproduces them exactly.
        """
        left, top, right, bottom = box
        edge = radius + 4
        small_width = left + edge * 2 + 1 + (width - right)
        small_height = top + edge * 2 + 1 + (height - bottom)
        if width <= small_width or height <= small_height:
            return self._paint_face(width, height, box, radius)
        small = self._paint_face(
            small_width, small_height,
            (left, top, small_width - (width - right), small_height - (height - bottom)),
            radius,
        )
        source_x = (0, left + edge, left + edge + 1, small_width)
        source_y = (0, top + edge, top + edge + 1, small_height)
        target_x = (0, left + edge, width - (small_width - source_x[2]), width)
        target_y = (0, top + edge, height - (small_height - source_y[2]), height)
        face = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        for column in range(3):
            for row in range(3):
                piece = small.crop((source_x[column], source_y[row],
                                    source_x[column + 1], source_y[row + 1]))
                size = (target_x[column + 1] - target_x[column],
                        target_y[row + 1] - target_y[row])
                if piece.size != size:
                    piece = piece.resize(size, Image.Resampling.NEAREST)
                face.paste(piece, (target_x[column], target_y[row]))
        return face

    def _draw(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        key = (
            width,
            height,
            self.cget("background"),
            self._fill,
            self._border,
            self._radius,
            self._focused,
        )
        if key == self._last_draw_key:
            return
        self._last_draw_key = key
        self.itemconfigure(self._content_id, width=max(1, width - self._padding * 2))
        self.delete("shelf")
        # Long shelves are painted as two short caps and a run of solid
        # rectangles between them: one full-height image can exceed what an
        # X server will allocate for a pixmap (BadAlloc) once a page grows long.
        cap = min(self._radius, max(1, (width - 4) // 2)) + 12
        self._shelf_images = []
        if height <= cap * 2 + 1:
            self._place_shelf_image(self._shelf_surface(width, height), 0)
        else:
            short = self._shelf_surface(width, cap * 2 + 1)
            self._place_shelf_image(short.crop((0, 0, width, cap)), 0)
            self._place_shelf_image(short.crop((0, cap + 1, width, cap * 2 + 1)), height - cap)
            middle = [short.getpixel((x, cap)) for x in range(width)]
            start = 0
            for x in range(1, width + 1):
                if x == width or middle[x] != middle[start]:
                    self.create_rectangle(
                        start, cap, x, height - cap, outline="", width=0,
                        fill="#{:02X}{:02X}{:02X}".format(*middle[start][:3]), tags="shelf",
                    )
                    start = x
        self.tag_lower("shelf")

    def _place_shelf_image(self, image: Image.Image, y: int) -> None:
        photo = ImageTk.PhotoImage(image, master=self)
        self._shelf_images.append(photo)
        self.create_image(0, y, anchor="nw", image=photo, tags="shelf")

    def _shelf_surface(self, width: int, height: int) -> Image.Image:
        key = (width, height, self.cget("background"), self._fill, self._border,
               self._radius, self._focused)
        surface = self._raster_cache.get(key)
        if surface is None:
            # Face inset leaves a few pixels below for a soft ambient shadow,
            # which is blurred at 1x: tall shelves would be costly at 4x.
            left, top = 2, 1
            right, bottom = max(left + 1, width - 2), max(top + 1, height - 4)
            radius = min(self._radius, max(1, min(right - left, bottom - top) // 2))
            surface = Image.new("RGBA", (width, height),
                                ImageColor.getrgb(self.cget("background"))[:3] + (255,))
            mask = Image.new("L", (width, height), 0)
            ImageDraw.Draw(mask).rounded_rectangle(
                (left, top + 2, right, bottom + 2), radius=radius, fill=20,
            )
            surface.paste(BUTTON_SHADOW, (0, 0, width, height),
                          mask.filter(ImageFilter.GaussianBlur(3)))
            surface.alpha_composite(self._render_face(width, height, (left, top, right, bottom), radius))
            surface = surface.convert("RGB")
            if len(self._raster_cache) >= self._raster_cache_limit:
                self._raster_cache.pop(next(iter(self._raster_cache)))
            self._raster_cache[key] = surface
        return surface
