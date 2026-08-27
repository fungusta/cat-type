# Content-Aware Settings Window Sizing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow the initial Settings window by its measured vertical overflow when the display has room, eliminating unnecessary opening scrollbars without breaking small-screen behavior.

**Architecture:** Keep `_center()` as the single owner of initial geometry. Add a pure height helper for the sizing rule, apply the screen-clamped width before measuring the final responsive layout, then add only positive scroll overflow to the preferred height and cap it to the usable display.

**Tech Stack:** Python 3.12, Tkinter, Pillow, `unittest`, Xvfb.

## Global Constraints

- The preferred width remains exactly 920 pixels and the base preferred height remains exactly 800 pixels.
- The opening height grows only by measured vertical overflow and never exceeds the existing usable-screen or window-manager limit.
- Content that already fits remains at the base opening height.
- Content that cannot fit remains scrollable with the fixed footer reachable.
- Manual resizing, page switching, saved settings, Metrics, responsive breakpoints, scroll input, and scrollbar visibility rules do not change.
- The window does not maximize, remember prior geometry, or resize after page switches.

---

### Task 1: Make initial height content-aware

**Files:**
- Modify: `settings_window.py:1665-1705`
- Test: `tests/test_settings_window.py:17-85`
- Test: `tests/test_settings_window.py:243-920`

**Interfaces:**
- Produces: `SettingsWindow._content_fitted_height(opening_height: int, content_height: int, viewport_height: int, available_height: int) -> int`.
- Consumes: the existing `scroll_canvas.bbox("all")`, `scroll_canvas.winfo_height()`, screen margins, window-manager maximum size, and responsive configure handlers.

- [ ] **Step 1: Write failing pure sizing tests**

Add these cases to `SettingsWindowSizingTests`:

```python
def test_content_fitted_height_adds_only_overflow_within_screen(self) -> None:
    fitted_height = getattr(
        SettingsWindow,
        "_content_fitted_height",
        lambda *_args: None,
    )

    self.assertEqual(fitted_height(800, 775, 724, 1120), 851)
    self.assertEqual(fitted_height(800, 677, 736, 1120), 800)
    self.assertEqual(fitted_height(800, 1228, 736, 1120), 1120)
```

- [ ] **Step 2: Write failing real-Tk opening tests**

Add two tests to `SettingsWindowTkLayoutTests`. The first constructs a wide window with a deliberately short base opening and verifies that available headroom removes its scrollbar:

First add `call` to the existing mock import:

```python
from unittest.mock import Mock, call, patch
```

```python
def test_opening_height_grows_to_remove_avoidable_scrolling(self) -> None:
    with patch.object(SettingsWindow, "PREFERRED_HEIGHT", 600):
        fitted_window = SettingsWindow(
            self.root,
            AppSettings(),
            Mock(),
        )
    self.addCleanup(fitted_window.close)
    fitted_window.window.update()

    bounds = fitted_window.scroll_canvas.bbox("all")
    self.assertIsNotNone(bounds)
    assert bounds is not None
    self.assertGreater(fitted_window.window.winfo_height(), 600)
    self.assertLessEqual(
        bounds[3] - bounds[1],
        fitted_window.scroll_canvas.winfo_height(),
    )
    self.assertFalse(fitted_window.scrollbar.winfo_ismapped())
```

The second constructs a narrow, stacked layout whose content cannot fit and verifies that the opening uses the safe available height while retaining scrolling:

```python
def test_narrow_opening_uses_available_height_and_keeps_needed_scroll(self) -> None:
    with (
        patch.object(SettingsWindow, "PREFERRED_WIDTH", 760),
        patch.object(SettingsWindow, "PREFERRED_HEIGHT", 600),
    ):
        fitted_window = SettingsWindow(
            self.root,
            AppSettings(),
            Mock(),
        )
    self.addCleanup(fitted_window.close)
    fitted_window.window.update()

    available_height = (
        fitted_window.window.winfo_screenheight()
        - fitted_window.SCREEN_VERTICAL_MARGIN
    )
    maximum_height = fitted_window.window.maxsize()[1]
    if maximum_height > 0:
        available_height = min(available_height, maximum_height)

    self.assertEqual(fitted_window._layout_mode, "narrow")
    self.assertEqual(fitted_window.window.winfo_height(), available_height)
    self.assertTrue(fitted_window.scrollbar.winfo_ismapped())
```

Update `test_center_reduces_minimum_when_screen_is_too_small` so its partial test instance supplies a mocked `scroll_canvas` and verifies both the width-first and final centered geometry calls:

```python
scroll_canvas = Mock()
scroll_canvas.bbox.return_value = None
settings_window.scroll_canvas = scroll_canvas

settings_window._center()

window.minsize.assert_called_once_with(600, 400)
self.assertEqual(
    window.geometry.call_args_list,
    [call("600x400"), call("600x400+20+24")],
)
```

- [ ] **Step 3: Run the focused tests and confirm the red state**

Run:

```bash
xvfb-run --auto-servernum python -m unittest \
  tests.test_settings_window.SettingsWindowSizingTests \
  tests.test_settings_window.SettingsWindowTkLayoutTests -v
```

Expected: the pure helper test fails because `_content_fitted_height` is absent, and both real-Tk tests fail because the window remains at the patched base height.

- [ ] **Step 4: Add the pure height rule**

Add immediately before `_fit_to_screen` in `settings_window.py`:

```python
@staticmethod
def _content_fitted_height(
    opening_height: int,
    content_height: int,
    viewport_height: int,
    available_height: int,
) -> int:
    overflow = max(0, content_height - viewport_height)
    return min(opening_height + overflow, available_height)
```

- [ ] **Step 5: Measure the final responsive layout in `_center()`**

After applying screen and window-manager caps, replace the current final sizing block with:

```python
width = min(self.window.winfo_width(), available_width)
opening_height = min(self.window.winfo_height(), available_height)

# Apply the final width before measuring vertical overflow so narrow screens
# have already switched to the stacked layout.
self.window.geometry(f"{width}x{opening_height}")
self.window.update_idletasks()

bounds = self.scroll_canvas.bbox("all")
content_height = bounds[3] - bounds[1] if bounds is not None else 0
height = self._content_fitted_height(
    opening_height,
    content_height,
    self.scroll_canvas.winfo_height(),
    available_height,
)
self.window.minsize(
    min(self.MIN_WIDTH, available_width),
    min(self.MIN_HEIGHT, available_height),
)
x = max(4, (screen_width - width) // 2)
y = max(4, (screen_height - height - 32) // 2)
self.window.geometry(f"{width}x{height}+{x}+{y}")
```

- [ ] **Step 6: Run the focused Settings-window tests and confirm green**

Run:

```bash
xvfb-run --auto-servernum python -m unittest tests.test_settings_window -v
```

Expected: all Settings-window tests pass, including the new pure and real-Tk sizing regressions.

- [ ] **Step 7: Commit the sizing fix**

```bash
git add settings_window.py tests/test_settings_window.py
git commit -m "fix: fit settings window to rendered content"
```

### Task 2: Verify the original symptom and full application

**Files:**
- Verify only

**Interfaces:**
- Consumes: the content-aware opening behavior from Task 1.
- Produces: verification evidence for the original scaled 1920-by-1200 reproduction and the full CI-equivalent suite.

- [ ] **Step 1: Re-run the original real-Tk reproduction**

Run the diagnostic harness at 2.5 Tk scaling on a 1920-by-1200 Xvfb screen and assert that the actual opening height equals the content-fitted height. The expected result is a zero exit code with no assertion failure; before the fix it failed with `opened at 800px with scrolling even though 851px fits the screen`.

```bash
xvfb-run --auto-servernum --server-args='-screen 0 1920x1200x24' \
python - <<'PY'
import tkinter as tk

from cat_settings import AppSettings
from settings_window import SettingsWindow

root = tk.Tk()
root.withdraw()
root.tk.call("tk", "scaling", 2.5)
window = SettingsWindow(root, AppSettings(), lambda _settings: None)
window.window.update()
bounds = window.scroll_canvas.bbox("all")
assert bounds is not None
content_height = bounds[3] - bounds[1]
actual_height = window.window.winfo_height()
canvas_height = window.scroll_canvas.winfo_height()
non_scroll_height = actual_height - canvas_height
base_viewport_height = 800 - non_scroll_height
available_height = (
    window.window.winfo_screenheight() - window.SCREEN_VERTICAL_MARGIN
)
maximum_height = window.window.maxsize()[1]
if maximum_height > 0:
    available_height = min(available_height, maximum_height)
expected_height = window._content_fitted_height(
    800,
    content_height,
    base_viewport_height,
    available_height,
)
assert actual_height == expected_height, (
    f"opened at {actual_height}px; expected {expected_height}px"
)
window.close()
root.destroy()
PY
```

- [ ] **Step 2: Run the full CI-equivalent suite**

Run:

```bash
xvfb-run --auto-servernum python -m unittest \
  tests.test_macos_overlay_focus \
  tests.test_behavior \
  tests.test_settings \
  tests.test_usage_metrics \
  tests.test_settings_window \
  tests.test_platform_assets \
  tests.test_bundled_icon_check \
  tests.test_package_smoke \
  tests.test_release_version_check \
  tests.test_auto_update \
  tests.test_update_controller \
  tests.test_platform_updater \
  tests.test_windows_installer_contract \
  tests.test_linux_update_integration -v
```

Expected: all tests pass with only the existing platform-specific skips.

- [ ] **Step 3: Inspect the final diff**

Run:

```bash
git diff --check main...HEAD
git status --short
git log --oneline main..HEAD
```

Expected: no whitespace errors, no uncommitted files, and only the focused sizing commit on the feature branch.
