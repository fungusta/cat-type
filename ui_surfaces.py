"""Rounded native surfaces shared by the settings destinations."""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from PIL import Image, ImageDraw, ImageTk


BUTTON_SHADOW = "#E7DED6"
BUTTON_BORDER = "#D8CEC5"
BUTTON_HOVER = "#FFF1B8"
BUTTON_ACCENT = "#F2D66B"
BUTTON_INK = "#302A33"
BUTTON_MUTED = "#655C66"


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
        radius=max(1, (height - 3) * 2 * scale),
        fill=shadow,
    )
    face_bottom = min(height - 3 + offset, height - 1)
    draw.rounded_rectangle(
        (6, offset * scale, image_width - 7, face_bottom * scale),
        radius=max(1, (height - 5) * 2 * scale),
        fill=face,
        outline=BUTTON_BORDER,
        width=2 * scale,
    )
    if focused and not disabled:
        draw.rounded_rectangle(
            (3, max(0, offset - 1) * scale, image_width - 10,
             min(height - 1, height - 2 + offset) * scale),
            radius=max(1, (height - 3) * 2 * scale),
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
        padx = int(kwargs.pop("padx", 10))
        pady = int(kwargs.pop("pady", 8))
        self._size = (
            max(60, face.measure(text) + (padx * 2) + 8),
            face.metrics("linespace") + (pady * 2) + 6,
        )
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
    """A keyboard-usable soft pill with a subtle, shared lift."""

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
        return super().cget(key)

class RoundedPanel(tk.Canvas):
    """A soft shelf surface that keeps native child widgets intact."""

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
        self.content = tk.Frame(self, background=fill)
        self._content_id = self.create_window(
            padding,
            padding,
            anchor="nw",
            window=self.content,
        )
        self.content.bind("<Configure>", self._sync_size, add="+")
        self.bind("<Configure>", self._draw, add="+")
        self.after_idle(self._sync_size)

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
        self.itemconfigure(self._content_id, width=width, height=height)
        if current_width <= 1:
            self.configure(width=width + self._padding * 2)
        self.configure(height=height + self._padding * 2)
        if current_width > 1:
            self._draw()

    def _draw(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        self.itemconfigure(self._content_id, width=max(1, width - self._padding * 2))
        self.delete("shelf")
        scale = 4
        surface = Image.new("RGB", (width * scale, height * scale), self.cget("background"))
        draw = ImageDraw.Draw(surface)
        draw.rounded_rectangle(
            (scale, scale, max(scale + 1, (width - 1) * scale),
             max(scale + 1, (height - 1) * scale)),
            radius=min(self._radius, max(1, min(width, height) // 2)) * scale,
            fill=self._fill,
            outline=self._border,
            width=2 * scale,
        )
        self._shelf_image = ImageTk.PhotoImage(
            surface.resize((width, height), Image.Resampling.LANCZOS),
            master=self,
        )
        self.create_image(0, 0, anchor="nw", image=self._shelf_image, tags="shelf")
        self.tag_lower("shelf")

