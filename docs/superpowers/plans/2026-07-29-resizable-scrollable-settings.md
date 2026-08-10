# Resizable and Scrollable Settings Window Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the settings window vertically resizable and scrollable while keeping its action footer visible.

**Architecture:** Keep the existing settings controls and two-column layout, but embed the header and cards in a frame hosted by a vertically scrollable Tk canvas. Keep the footer as a sibling below the canvas, centralize screen-size clamping and wheel-delta normalization in small deterministic helpers, and bind wheel handling only to the settings toplevel.

**Tech Stack:** Python 3, Tkinter/ttk, Pillow, `unittest`, `unittest.mock`

## Global Constraints

- The settings window must be resizable in both dimensions.
- The minimum window size must be exactly 700 by 480 pixels.
- The preferred initial size remains 920 by 800 pixels and must be clamped to the available screen dimensions.
- The header and settings cards scroll vertically; the footer and its **Not now** and **Save my setup** buttons stay fixed.
- Support a visible vertical scrollbar, Windows/macOS `<MouseWheel>` events, and Linux `<Button-4>`/`<Button-5>` wheel events.
- Wheel events outside the scrollable content must not move the settings canvas.
- Do not add dependencies or refactor unrelated settings behavior.

## File Structure

- Create `tests/test_settings_window.py`: headless regression tests for window-manager configuration, geometry clamping, wheel normalization, and scroll targeting; optional Tk integration coverage when a display is available.
- Modify `settings_window.py`: window size policy, scrollable canvas/content hierarchy, fixed footer, configure handlers, and cross-platform wheel handling.

---

### Task 1: Resizable, Screen-Bounded Window

**Files:**
- Create: `tests/test_settings_window.py`
- Modify: `settings_window.py:131-187`
- Modify: `settings_window.py:701-707`

**Interfaces:**
- Consumes: `SettingsWindow(parent, settings, on_save, icon_path=None)` and `AppSettings`.
- Produces: `SettingsWindow._fit_to_screen(width: int, height: int, screen_width: int, screen_height: int) -> tuple[int, int]`, plus `PREFERRED_WIDTH`, `PREFERRED_HEIGHT`, `MIN_WIDTH`, and `MIN_HEIGHT` class constants.

- [ ] **Step 1: Write failing resize and geometry tests**

Create `tests/test_settings_window.py` with:

```python
from __future__ import annotations

import tkinter as tk
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cat_settings import AppSettings
from settings_window import SettingsWindow


class SettingsWindowSizingTests(unittest.TestCase):
    def test_window_is_resizable_in_both_dimensions(self) -> None:
        window = Mock()
        with ExitStack() as stack:
            stack.enter_context(
                patch("settings_window.tk.Toplevel", return_value=window)
            )
            for variable_type in (
                "BooleanVar",
                "StringVar",
                "IntVar",
                "DoubleVar",
            ):
                stack.enter_context(patch(f"settings_window.tk.{variable_type}"))
            for method_name in (
                "_configure_fonts",
                "_configure_styles",
                "_load_preview_frames",
                "_build",
                "_center",
                "_animate_preview",
            ):
                stack.enter_context(
                    patch.object(SettingsWindow, method_name)
                )

            SettingsWindow(Mock(), AppSettings(), Mock())

        window.geometry.assert_called_once_with("920x800")
        window.minsize.assert_called_once_with(700, 480)
        window.resizable.assert_called_once_with(True, True)

    def test_preferred_size_is_clamped_to_available_screen(self) -> None:
        fit_to_screen = getattr(
            SettingsWindow,
            "_fit_to_screen",
            lambda *_args: None,
        )

        self.assertEqual(
            fit_to_screen(920, 800, 1920, 1080),
            (920, 800),
        )
        self.assertEqual(
            fit_to_screen(920, 800, 1366, 768),
            (920, 688),
        )
        self.assertEqual(
            fit_to_screen(920, 800, 800, 600),
            (760, 520),
        )
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
python -m unittest discover -s tests -p 'test_settings_window.py' -v
```

Expected: two failures. The current window reports `minsize(840, 800)` and
`resizable(True, False)`, and the absent `_fit_to_screen` helper returns the
test fallback value `None`.

- [ ] **Step 3: Add the window sizing policy**

In `SettingsWindow`, add these constants immediately below `BORDER`:

```python
    PREFERRED_WIDTH = 920
    PREFERRED_HEIGHT = 800
    MIN_WIDTH = 700
    MIN_HEIGHT = 480
    SCREEN_HORIZONTAL_MARGIN = 40
    SCREEN_VERTICAL_MARGIN = 80
```

Replace the three window-manager calls in `__init__` with:

```python
        self.window.geometry(
            f"{self.PREFERRED_WIDTH}x{self.PREFERRED_HEIGHT}"
        )
        self.window.minsize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self.window.resizable(True, True)
```

Add the sizing helper immediately before `_center`:

```python
    @classmethod
    def _fit_to_screen(
        cls,
        width: int,
        height: int,
        screen_width: int,
        screen_height: int,
    ) -> tuple[int, int]:
        available_width = max(
            cls.MIN_WIDTH,
            screen_width - cls.SCREEN_HORIZONTAL_MARGIN,
        )
        available_height = max(
            cls.MIN_HEIGHT,
            screen_height - cls.SCREEN_VERTICAL_MARGIN,
        )
        return min(width, available_width), min(height, available_height)
```

Replace `_center` with:

```python
    def _center(self) -> None:
        self.window.update_idletasks()
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        width, height = self._fit_to_screen(
            self.window.winfo_width(),
            self.window.winfo_height(),
            screen_width,
            screen_height,
        )
        x = max(4, (screen_width - width) // 2)
        y = max(4, (screen_height - height - 32) // 2)
        self.window.geometry(f"{width}x{height}+{x}+{y}")
```

- [ ] **Step 4: Run focused and existing settings tests and verify GREEN**

Run:

```bash
python -m unittest discover -s tests -p 'test_settings_window.py' -v
python -m unittest discover -s tests -p 'test_settings.py' -v
```

Expected: both settings-window sizing tests pass, followed by all three
settings persistence tests passing.

- [ ] **Step 5: Commit the sizing change**

```bash
git add settings_window.py tests/test_settings_window.py
git commit -m "Make settings window vertically resizable"
```

---

### Task 2: Scrollable Content with a Fixed Footer

**Files:**
- Modify: `tests/test_settings_window.py`
- Modify: `settings_window.py:324-345`
- Modify: `settings_window.py:546-588`
- Modify: `settings_window.py:671-686`

**Interfaces:**
- Consumes: `SettingsWindow.MIN_WIDTH`, `SettingsWindow.MIN_HEIGHT`, and the existing `_build_header`, card-building, save, and close methods.
- Produces: `scroll_canvas: tk.Canvas`, `scroll_content: tk.Frame`, `footer: tk.Frame`, `_wheel_scroll_units(event: tk.Event[tk.Misc]) -> int`, `_on_mouse_wheel(event: tk.Event[tk.Misc]) -> str | None`, `_on_content_configure(event: tk.Event[tk.Misc]) -> None`, and `_on_canvas_configure(event: tk.Event[tk.Misc]) -> None`.

- [ ] **Step 1: Add failing wheel and layout tests**

Append to `tests/test_settings_window.py`:

```python

class SettingsWindowScrollingTests(unittest.TestCase):
    def test_wheel_events_are_normalized_across_platforms(self) -> None:
        wheel_units = getattr(
            SettingsWindow,
            "_wheel_scroll_units",
            lambda _event: None,
        )

        cases = (
            (SimpleNamespace(delta=120, num=None), -1),
            (SimpleNamespace(delta=-120, num=None), 1),
            (SimpleNamespace(delta=240, num=None), -2),
            (SimpleNamespace(delta=1, num=None), -1),
            (SimpleNamespace(delta=0, num=4), -1),
            (SimpleNamespace(delta=0, num=5), 1),
            (SimpleNamespace(delta=0, num=None), 0),
        )
        for event, expected in cases:
            with self.subTest(event=event):
                self.assertEqual(wheel_units(event), expected)

    def test_wheel_scrolls_overflowing_content_under_pointer(self) -> None:
        settings_window = SettingsWindow.__new__(SettingsWindow)
        canvas = Mock()
        canvas.bbox.return_value = (0, 0, 700, 900)
        canvas.winfo_height.return_value = 400
        canvas.master = None
        settings_window.scroll_canvas = canvas
        content = SimpleNamespace(master=canvas)
        child = SimpleNamespace(master=content)
        event = SimpleNamespace(widget=child, delta=-120, num=None)
        handle_wheel = getattr(
            settings_window,
            "_on_mouse_wheel",
            lambda _event: None,
        )

        result = handle_wheel(event)

        canvas.yview_scroll.assert_called_once_with(1, "units")
        self.assertEqual(result, "break")

    def test_wheel_ignores_footer_and_content_that_fits(self) -> None:
        settings_window = SettingsWindow.__new__(SettingsWindow)
        canvas = Mock()
        canvas.bbox.return_value = (0, 0, 700, 300)
        canvas.winfo_height.return_value = 400
        canvas.master = None
        settings_window.scroll_canvas = canvas
        content = SimpleNamespace(master=canvas)
        footer_child = SimpleNamespace(master=None)
        handle_wheel = getattr(
            settings_window,
            "_on_mouse_wheel",
            lambda _event: None,
        )

        result_over_footer = handle_wheel(
            SimpleNamespace(
                widget=footer_child,
                delta=-120,
                num=None,
            )
        )
        result_when_content_fits = handle_wheel(
            SimpleNamespace(
                widget=content,
                delta=-120,
                num=None,
            )
        )

        canvas.yview_scroll.assert_not_called()
        self.assertIsNone(result_over_footer)
        self.assertIsNone(result_when_content_fits)


class SettingsWindowTkLayoutTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk display is unavailable: {error}")
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.settings_window = SettingsWindow(
            self.root,
            AppSettings(),
            lambda _settings: None,
        )
        self.addCleanup(self.settings_window.close)

    def test_footer_is_outside_scrollable_content(self) -> None:
        self.assertTrue(hasattr(self.settings_window, "footer"))
        self.assertTrue(hasattr(self.settings_window, "scroll_host"))
        self.assertTrue(hasattr(self.settings_window, "scroll_content"))
        self.assertTrue(hasattr(self.settings_window, "scroll_canvas"))
        self.settings_window.window.geometry("700x480")
        self.settings_window.window.update_idletasks()

        self.assertIs(
            self.settings_window.footer.master,
            self.settings_window.body,
        )
        self.assertIs(
            self.settings_window.scroll_host.master,
            self.settings_window.body,
        )
        self.assertIs(
            self.settings_window.scroll_content.master,
            self.settings_window.scroll_canvas,
        )
        self.assertIsNot(
            self.settings_window.footer.master,
            self.settings_window.scroll_content,
        )
        content_bounds = self.settings_window.scroll_canvas.bbox("all")
        self.assertIsNotNone(content_bounds)
        assert content_bounds is not None
        self.assertGreater(
            content_bounds[3] - content_bounds[1],
            self.settings_window.scroll_canvas.winfo_height(),
        )
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
python -m unittest discover -s tests -p 'test_settings_window.py' -v
```

Expected: the Task 1 tests pass. The wheel-normalization and overflowing
content assertions fail because their fallbacks return `None` without
scrolling. If Tk has a display, the layout test fails its attribute checks;
otherwise that one test skips. There are no unexpected import or setup errors.

- [ ] **Step 3: Build the scrollable content hierarchy**

Replace `_build` with:

```python
    def _build(self) -> None:
        self.body = tk.Frame(self.window, background=self.BACKGROUND)
        self.body.pack(fill="both", expand=True)

        self.footer = self._build_footer(self.body)

        self.scroll_host = tk.Frame(
            self.body,
            background=self.BACKGROUND,
        )
        self.scroll_host.pack(side="top", fill="both", expand=True)

        self.scrollbar = ttk.Scrollbar(
            self.scroll_host,
            orient="vertical",
        )
        self.scrollbar.pack(side="right", fill="y")

        self.scroll_canvas = tk.Canvas(
            self.scroll_host,
            background=self.BACKGROUND,
            highlightthickness=0,
            yscrollcommand=self.scrollbar.set,
        )
        self.scroll_canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.configure(command=self.scroll_canvas.yview)

        self.scroll_content = tk.Frame(
            self.scroll_canvas,
            background=self.BACKGROUND,
        )
        self._scroll_content_id = self.scroll_canvas.create_window(
            (0, 0),
            window=self.scroll_content,
            anchor="nw",
        )
        self.scroll_content.bind(
            "<Configure>",
            self._on_content_configure,
        )
        self.scroll_canvas.bind(
            "<Configure>",
            self._on_canvas_configure,
        )
        self.window.bind(
            "<MouseWheel>",
            self._on_mouse_wheel,
            add="+",
        )
        self.window.bind(
            "<Button-4>",
            self._on_mouse_wheel,
            add="+",
        )
        self.window.bind(
            "<Button-5>",
            self._on_mouse_wheel,
            add="+",
        )

        self._build_header(self.scroll_content)

        columns = tk.Frame(
            self.scroll_content,
            background=self.BACKGROUND,
        )
        columns.pack(fill="x", padx=26)
        columns.grid_columnconfigure(0, weight=3, uniform="settings")
        columns.grid_columnconfigure(1, weight=2, uniform="settings")

        left = tk.Frame(columns, background=self.BACKGROUND)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right = tk.Frame(columns, background=self.BACKGROUND)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        self._build_companion_card(left)
        self._build_appearance_card(left)
        self._build_size_card(right)
        self._build_timing_card(right)
```

Replace `_build_footer` so it returns its frame and packs it at the bottom:

```python
    def _build_footer(self, body: tk.Frame) -> tk.Frame:
        footer = tk.Frame(body, background=self.BACKGROUND)
        footer.pack(
            side="bottom",
            fill="x",
            padx=28,
            pady=(12, 14),
        )
        tk.Label(
            footer,
            text="♡  Only keyboard activity is detected — never what you type.",
            background=self.BACKGROUND,
            foreground=self.MUTED,
            font=self.fonts["small"],
        ).pack(side="left", anchor="center")

        buttons = tk.Frame(footer, background=self.BACKGROUND)
        buttons.pack(side="right")
        tk.Button(
            buttons,
            text="Not now",
            command=self.close,
            relief="flat",
            borderwidth=0,
            background="#F1E5DF",
            activebackground="#E8D8D0",
            foreground=self.INK,
            activeforeground=self.INK,
            font=self.fonts["button"],
            padx=18,
            pady=9,
            cursor="hand2",
        ).pack(side="left")
        tk.Button(
            buttons,
            text="Save my setup  ♡",
            command=self._save,
            relief="flat",
            borderwidth=0,
            background=self.ACCENT,
            activebackground=self.ACCENT_DARK,
            foreground="#FFFFFF",
            activeforeground="#FFFFFF",
            font=self.fonts["button"],
            padx=18,
            pady=9,
            cursor="hand2",
        ).pack(side="left", padx=(8, 0))
        return footer
```

- [ ] **Step 4: Add canvas synchronization and wheel handling**

Insert these methods immediately before `_animate_preview`:

```python
    def _on_content_configure(
        self,
        _event: tk.Event[tk.Misc],
    ) -> None:
        bounds = self.scroll_canvas.bbox("all")
        if bounds is not None:
            self.scroll_canvas.configure(scrollregion=bounds)

    def _on_canvas_configure(
        self,
        event: tk.Event[tk.Misc],
    ) -> None:
        self.scroll_canvas.itemconfigure(
            self._scroll_content_id,
            width=event.width,
        )

    @staticmethod
    def _wheel_scroll_units(event: tk.Event[tk.Misc]) -> int:
        delta = int(getattr(event, "delta", 0) or 0)
        if delta:
            magnitude = max(1, abs(delta) // 120)
            return -magnitude if delta > 0 else magnitude
        return {
            4: -1,
            5: 1,
        }.get(getattr(event, "num", None), 0)

    def _event_is_over_scroll_content(
        self,
        widget: tk.Misc | None,
    ) -> bool:
        while widget is not None:
            if widget is self.scroll_canvas:
                return True
            widget = getattr(widget, "master", None)
        return False

    def _on_mouse_wheel(
        self,
        event: tk.Event[tk.Misc],
    ) -> str | None:
        if not self._event_is_over_scroll_content(
            getattr(event, "widget", None)
        ):
            return None
        bounds = self.scroll_canvas.bbox("all")
        if (
            bounds is None
            or bounds[3] - bounds[1] <= self.scroll_canvas.winfo_height()
        ):
            return None
        units = self._wheel_scroll_units(event)
        if not units:
            return None
        self.scroll_canvas.yview_scroll(units, "units")
        return "break"
```

- [ ] **Step 5: Run focused tests and verify GREEN**

Run:

```bash
python -m unittest discover -s tests -p 'test_settings_window.py' -v
```

Expected: all six headless regression tests pass. The Tk layout test passes
when a graphical display is available or reports exactly one skip when it is
not.

- [ ] **Step 6: Run full automated verification**

Run:

```bash
python -m unittest discover -s tests -v
python -m compileall -q cat_settings.py cat_type.py settings_window.py tests
git diff --check
```

Expected: the complete test suite exits with zero failures and zero errors;
the Tk layout test may be skipped only because no display is available.
Compilation and whitespace checks exit with status 0 and no output.

- [ ] **Step 7: Perform a graphical smoke test when a display is available**

Run:

```bash
python cat_type.py
```

Open Settings, resize the window to approximately 700 by 480 pixels, and
verify that:

1. the scrollbar moves through every settings card;
2. mouse-wheel or trackpad input scrolls only while the pointer is over the
   settings content;
3. **Not now** and **Save my setup** remain visible at every scroll position;
4. enlarging the window expands the content without introducing a horizontal
   scrollbar.

Expected: all four checks succeed. Close Cat Type with **Ctrl+Alt+Q**.

- [ ] **Step 8: Commit the scrolling fix**

```bash
git add settings_window.py tests/test_settings_window.py
git commit -m "Add scrolling to the settings window"
```
