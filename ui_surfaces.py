"""Rounded native surfaces shared by the settings destinations."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Mapping

from pagination import PageWindow, page_label, page_window
from tkinter import font as tkfont
from PIL import Image, ImageDraw, ImageTk


BUTTON_SHADOW = "#E7DED6"
BUTTON_BORDER = "#D8CEC5"
BUTTON_HOVER = "#FFF1B8"
BUTTON_ACCENT = "#F2D66B"
BUTTON_INK = "#302A33"
BUTTON_MUTED = "#655C66"
SOFT_PILL_MAX_RADIUS = 12


def soft_pill_radius(height: int) -> int:
    """Return a soft corner radius without turning short buttons into capsules."""
    return min(SOFT_PILL_MAX_RADIUS, max(4, height // 3))


def render_soft_pill(
    master: tk.Misc,
    surface: str,
    width: int,
    height: int,
    fill: str,
    *,
    pressed: bool = False,
    focused: bool = False,
    disabled: bool = False,
) -> ImageTk.PhotoImage:
    """Render the one shared pill surface used by every settings control."""
    scale = 4
    image_width = width * scale
    image_height = height * scale
    image = Image.new("RGB", (image_width, image_height), surface)
    draw = ImageDraw.Draw(image)
    offset = 2 if pressed else 0
    shadow = "#E5DDD5" if disabled else BUTTON_SHADOW
    face = "#ECE7E0" if disabled else fill
    shadow_top = min(height - 1, 3 + offset)
    draw.rounded_rectangle(
        (6, shadow_top * scale, image_width - 7, image_height - scale),
        radius=soft_pill_radius(height) * scale,
        fill=shadow,
    )
    face_bottom = min(height - 3 + offset, height - 1)
    draw.rounded_rectangle(
        (6, offset * scale, image_width - 7, face_bottom * scale),
        radius=soft_pill_radius(height) * scale,
        fill=face,
        outline=BUTTON_BORDER,
        width=2 * scale,
    )
    if focused and not disabled:
        draw.rounded_rectangle(
            (3, max(0, offset - 1) * scale, image_width - 10,
             min(height - 1, height - 2 + offset) * scale),
            radius=soft_pill_radius(height) * scale,
            outline=BUTTON_ACCENT,
            width=2 * scale,
        )
    return ImageTk.PhotoImage(
        image.resize((width, height), Image.Resampling.LANCZOS),
        master=master,
    )


class RoundedChoice(tk.Radiobutton):
    """Native radio behavior with a softly rounded visual face."""

    def __init__(self, parent: tk.Misc, **kwargs: object) -> None:
        self._surface = str(parent.cget("background"))
        self._face = str(kwargs.pop("background", self._surface))
        self._accent = str(kwargs.pop("selectcolor", self._face))
        self._edge = str(kwargs.pop("highlightbackground", self._face))
        self._hover_fill = BUTTON_HOVER
        self._shadow = BUTTON_SHADOW
        self._hovered = False
        self._pressed = False
        self._focused = False
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
        self._render()

    def _set_pressed(self, pressed: bool) -> None:
        self._pressed = pressed
        self._render()

    def _set_focus(self, focused: bool) -> None:
        self._focused = focused
        self._render()

    def _render(self) -> None:
        width, height = self._size
        normal_fill = self._hover_fill if self._hovered else self._face
        selected_fill = self._accent
        images = [
            render_soft_pill(
                self,
                self._surface,
                width,
                height,
                normal_fill,
                pressed=self._pressed,
                focused=self._focused,
            ),
            render_soft_pill(
                self,
                self._surface,
                width,
                height,
                selected_fill,
                pressed=self._pressed,
                focused=self._focused,
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
        self._draw()

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
        fill = BUTTON_HOVER if self._hovered and self._fill != self._accent else self._fill
        self._pill_image = render_soft_pill(
            self,
            str(self.cget("background")),
            width,
            height,
            fill,
            pressed=self._pressed,
            focused=self._focused,
            disabled=self._state == "disabled",
        )
        self.create_image(0, 0, anchor="nw", image=self._pill_image)
        self.create_text(
            width // 2,
            height // 2 + (1 if self._pressed else 0),
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
        scale = 4
        surface = self._raster_cache.get(key)
        if surface is None:
            surface = Image.new("RGB", (width * scale, height * scale), self.cget("background"))
            draw = ImageDraw.Draw(surface)
            draw.rounded_rectangle(
                (scale, scale, max(scale + 1, (width - 1) * scale),
                 max(scale + 1, (height - 1) * scale)),
                radius=min(self._radius, max(1, min(width, height) // 2)) * scale,
                fill=self._fill,
                outline=BUTTON_ACCENT if self._focused else self._border,
                width=2 * scale,
            )
            if self._focused:
                draw.rounded_rectangle(
                    (3 * scale, 3 * scale,
                     max(4 * scale, (width - 3) * scale),
                     max(4 * scale, (height - 3) * scale)),
                    radius=max(1, min(self._radius - 2, max(1, min(width, height) // 2 - 2))) * scale,
                    outline=BUTTON_INK,
                    width=scale,
                )
            surface = surface.resize((width, height), Image.Resampling.LANCZOS)
            if len(self._raster_cache) >= self._raster_cache_limit:
                self._raster_cache.pop(next(iter(self._raster_cache)))
            self._raster_cache[key] = surface
        self._shelf_image = ImageTk.PhotoImage(
            surface,
            master=self,
        )
        self.create_image(0, 0, anchor="nw", image=self._shelf_image, tags="shelf")
        self.tag_lower("shelf")
