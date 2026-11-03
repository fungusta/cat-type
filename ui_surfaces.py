"""Rounded native surfaces shared by the settings destinations."""

from __future__ import annotations

import functools
import sys
import time
import tkinter as tk
from collections.abc import Callable, Mapping

from pagination import PageWindow, page_label, page_window
from tkinter import font as tkfont
from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageTk


BUTTON_SHADOW = "#4A3428"
BUTTON_BORDER = "#E2D9D0"
BUTTON_HOVER = "#FFF5D1"
BUTTON_ACCENT = "#F2D66B"
BUTTON_INK = "#302A33"
BUTTON_MUTED = "#655C66"
BUTTON_DISABLED = "#F3EFEA"
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


def _hex(widget: tk.Misc, color: str) -> str:
    """Resolve Tk-only names such as ``SystemButtonFace`` for Pillow."""
    if color.startswith("#"):
        return color
    red, green, blue = (value >> 8 for value in widget.winfo_rgb(color))
    return f"#{red:02X}{green:02X}{blue:02X}"


class RoundedChoice(tk.Radiobutton):
    """Native radio behavior with a softly rounded visual face.

    ``variant="ghost"`` keeps unselected items flush with their surface until
    hovered, which suits navigation lists.
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
        min_width = int(kwargs.pop("min_width", 0))
        padx = int(kwargs.pop("padx", 10))
        pady = int(kwargs.pop("pady", 8))
        self._size = (
            max(min_width, 60, face.measure(text) + (padx * 2) + 8),
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
        images = [
            render_soft_pill(
                self,
                self._surface,
                width,
                height,
                normal_fill,
                pressed=self._pressed,
                focused=self._focused,
                **normal,
            ),
            render_soft_pill(
                self,
                self._surface,
                width,
                height,
                self._accent,
                pressed=self._pressed,
                focused=self._focused,
                lift=hover,
            ),
        ]
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

    def cget(self, key: str) -> object:
        if key == "background":
            return self._face
        if key == "selectcolor":
            return self._accent
        if key == "highlightbackground":
            return self._edge
        return super().cget(key)


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


class PaginationControls(tk.Frame):
    """Shared pill actions with a plain page label and native tab traversal."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        on_previous: Callable[[], None],
        on_next: Callable[[], None],
        palette: Mapping[str, str],
        fonts: Mapping[str, object],
    ) -> None:
        super().__init__(parent, background=palette["background"], takefocus=False)
        self._button_font = fonts["button"]
        self._layout_key: tuple[int, int] | None = None
        self.grid_anchor("center")
        self.previous_button = RoundedAction(
            self, text="Previous page", command=on_previous, font=fonts["button"],
        )
        self.previous_button.title = "Previous page"
        self.previous_button.grid(row=0, column=0)
        self.page_label = tk.Label(
            self, background=palette["background"], foreground=palette["ink"],
            font=fonts["small"], takefocus=False,
        )
        self.page_label.grid(row=0, column=1, padx=12)
        self.next_button = RoundedAction(
            self, text="Next page", command=on_next, font=fonts["button"],
        )
        self.next_button.title = "Next page"
        self.next_button.grid(row=0, column=2)
        self.bind("<Configure>", self._layout_controls, add="+")
        self.set_state(page_window(0, 0, 1))

    def _layout_controls(self, event: tk.Event[tk.Misc] | None = None) -> None:
        if self.winfo_manager() == "pack" and self.pack_info().get("fill") != "x":
            # Keep observing the host width after a compact page grows again.
            self.pack_configure(fill="x")
        width = int(event.width) if event is not None else self.winfo_width()
        if width <= 1:
            return
        label_width = self.page_label.winfo_reqwidth()
        key = (width, label_width)
        if key == self._layout_key:
            return
        self._layout_key = key
        face = tkfont.Font(self, font=self._button_font)
        previous_width = max(68, face.measure(str(self.previous_button.cget("text"))) + 24)
        next_width = max(68, face.measure(str(self.next_button.cget("text"))) + 24)
        inline = width >= previous_width + label_width + next_width + 24
        if inline:
            for column in range(3):
                self.grid_columnconfigure(column, weight=0, uniform="")
            self.previous_button.fit_width(previous_width)
            self.next_button.fit_width(next_width)
            self.previous_button.grid(row=0, column=0, sticky="", padx=0, pady=0)
            self.page_label.grid(row=0, column=1, columnspan=1, padx=12, pady=0)
            self.next_button.grid(row=0, column=2, sticky="", padx=0, pady=0)
        else:
            self.grid_columnconfigure(0, weight=1, uniform="pager-actions")
            self.grid_columnconfigure(1, weight=1, uniform="pager-actions")
            self.grid_columnconfigure(2, weight=0, uniform="")
            button_width = max(1, (width - 8) // 2)
            self.previous_button.fit_width(button_width)
            self.next_button.fit_width(button_width)
            self.page_label.grid(row=0, column=0, columnspan=2, padx=0, pady=(0, 8))
            self.previous_button.grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=0)
            self.next_button.grid(row=1, column=1, sticky="ew", padx=(4, 0), pady=0)

    def set_state(self, window: PageWindow) -> None:
        focused = self.focus_get()
        label = page_label(window)
        self.page_label.configure(text=label)
        self.page_label.title = label
        self.page_label.accessible_name = label
        self._layout_controls()
        states = (
            (self.previous_button, window.page_count > 0 and window.index > 0),
            (self.next_button, window.index + 1 < window.page_count),
        )
        for button, enabled in states:
            button.configure(state="normal" if enabled else "disabled", takefocus=enabled)
        if any(focused == button and not enabled for button, enabled in states):
            for button, enabled in states:
                if enabled:
                    button.focus_set()
                    break
            else:
                # Both actions can disappear from traversal when data shrinks.
                # Follow the surrounding window's normal tab order instead of
                # leaving focus on a disabled canvas.
                target = focused.tk_focusNext()
                if target in (self.previous_button, self.next_button):
                    target = self.master
                target.focus_set()


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
        self._shelf_image = ImageTk.PhotoImage(
            surface,
            master=self,
        )
        self.create_image(0, 0, anchor="nw", image=self._shelf_image, tags="shelf")
        self.tag_lower("shelf")
