# Keyboard-Aware Paws and Keystroke Counter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Cat Type select paws from keyboard position, use both paws for spacebar, preserve the rapid-typing pose, and show a live session keystroke total only in Settings.

**Architecture:** Classify each native key inside `KeyboardMonitor` into a privacy-safe `PawAction`, then queue an `AppEvent` containing only that action and a monotonic timestamp. `AnimationState` owns pose selection, `CatTypeApp` owns the non-persistent session count, and `SettingsWindow` exposes a narrow method for displaying the count without changing the overlay.

**Tech Stack:** Python 3.12, `ctypes` Windows low-level keyboard hook, `pynput` portable listener, Tkinter, and `unittest`.

## Global Constraints

- The counter appears only in the Settings window; do not add widgets, text, or geometry to the cat overlay.
- The counter starts at zero on launch, counts enabled keydown/repeat activity, and is never persisted.
- Spacebar always selects the existing `excited` both-paws sprite.
- Five keystrokes within 340 ms retain the approved existing `excited` override.
- Raw keys, characters, scan codes, and virtual-key codes must not leave `KeyboardMonitor`, be logged, or be persisted.
- Ctrl+Alt+Q must still quit without queuing the `Q` as typing activity.
- Unknown platform keys fall back to alternating paws.
- Do not add dependencies or sprite assets.

---

### Task 1: Privacy-Safe Keyboard Classification

**Files:**
- Modify: `cat_type.py:1-70`
- Modify: `tests/test_behavior.py:1-20`
- Modify: `tests/test_behavior.py:163-192`

**Interfaces:**
- Produces: `PawAction = Literal["left", "right", "both", "alternate"]`
- Produces: `AppEvent(kind: str, happened_at: float, paw: PawAction | None = None)`
- Produces: `classify_windows_key(vk_code: int, scan_code: int = 0, flags: int = 0) -> PawAction`
- Produces: `classify_portable_key(key: object) -> PawAction`
- Consumes: only native metadata already delivered by the existing listeners.

- [ ] **Step 1: Write failing classifier and event-privacy tests**

Add these imports and tests to `tests/test_behavior.py`:

```python
from dataclasses import fields

from cat_type import (
    AppEvent,
    AnimationState,
    CaretLocator,
    ScreenRect,
    classify_portable_key,
    classify_windows_key,
    choose_fallback_position,
    choose_overlay_position,
)


class FakePortableKey:
    def __init__(self, char: str | None = None, name: str | None = None) -> None:
        self.char = char
        self.name = name


class KeyboardClassificationTests(unittest.TestCase):
    def test_windows_keys_follow_the_physical_keyboard_split(self) -> None:
        cases = (
            ((0x51, 0, 0), "left"),       # Q
            ((0x54, 0, 0), "left"),       # T
            ((0x59, 0, 0), "right"),      # Y
            ((0x4D, 0, 0), "right"),      # M
            ((0x20, 0, 0), "both"),       # Space
            ((0x70, 0, 0), "left"),       # F1
            ((0x76, 0, 0), "right"),      # F7
            ((0x10, 0x2A, 0), "left"),    # Generic left Shift
            ((0x10, 0x36, 0), "right"),   # Generic right Shift
            ((0x11, 0, 0), "left"),       # Generic left Ctrl
            ((0x11, 0, 1), "right"),      # Extended right Ctrl
            ((0x25, 0, 0), "right"),      # Left-arrow key cluster
            ((0x60, 0, 0), "right"),      # Numpad 0
            ((0xAD, 0, 0), "alternate"),  # Media mute
        )

        for arguments, expected in cases:
            with self.subTest(arguments=arguments):
                self.assertEqual(classify_windows_key(*arguments), expected)

    def test_portable_keys_follow_the_physical_keyboard_split(self) -> None:
        cases = (
            (FakePortableKey(char="q"), "left"),
            (FakePortableKey(char="!"), "left"),
            (FakePortableKey(char="y"), "right"),
            (FakePortableKey(char="^"), "right"),
            (FakePortableKey(char=" "), "both"),
            (FakePortableKey(name="space"), "both"),
            (FakePortableKey(name="shift_l"), "left"),
            (FakePortableKey(name="shift_r"), "right"),
            (FakePortableKey(name="f6"), "left"),
            (FakePortableKey(name="f7"), "right"),
            (FakePortableKey(name="left"), "right"),
            (FakePortableKey(name="media_volume_up"), "alternate"),
        )

        for key, expected in cases:
            with self.subTest(key=vars(key)):
                self.assertEqual(classify_portable_key(key), expected)

    def test_app_event_carries_a_paw_action_but_no_key_identity(self) -> None:
        event = AppEvent("key", 12.5, "left")

        self.assertEqual(event.paw, "left")
        self.assertEqual(
            {field.name for field in fields(event)},
            {"kind", "happened_at", "paw"},
        )
```

- [ ] **Step 2: Run the tests and verify the missing interfaces fail**

Run:

```bash
python -m unittest tests.test_behavior.KeyboardClassificationTests -v
```

Expected: `ImportError` because `AppEvent`, `classify_windows_key`, and `classify_portable_key` do not exist yet.

- [ ] **Step 3: Add the event type and pure classifiers**

In `cat_type.py`, import `Literal`, define `PawAction` and `AppEvent`, and add the classifier constants and functions before `AnimationState`:

```python
from typing import Callable, Literal


PawAction = Literal["left", "right", "both", "alternate"]
LLKHF_EXTENDED = 0x01


@dataclass(frozen=True)
class AppEvent:
    kind: str
    happened_at: float
    paw: PawAction | None = None


LEFT_WINDOWS_KEYS = frozenset(
    {
        0x1B, 0x09, 0x14, 0x5B, 0xA0, 0xA2, 0xA4, 0xC0,
        *map(ord, "12345QWERTASDFGZXCVB"),
    }
)
RIGHT_WINDOWS_KEYS = frozenset(
    {
        0x08, 0x0D, 0x5C, 0x5D, 0x90, 0xA1, 0xA3, 0xA5,
        0xBA, 0xBB, 0xBD, 0xBF, 0xDB, 0xDC, 0xDD, 0xDE, 0xE2,
        *range(0x21, 0x2F),
        *range(0x60, 0x70),
        *map(ord, "67890YUIOPHJKLNM"),
    }
)
LEFT_PORTABLE_CHARACTERS = frozenset("`~12345!@#$%qwertasdfgzxcvb")
RIGHT_PORTABLE_CHARACTERS = frozenset(
    "67890-=_+^&*()yuiop[]{}\\|hjkl;'\"nm,./<>?"
)
LEFT_PORTABLE_KEYS = frozenset(
    {"esc", "tab", "caps_lock", "shift", "shift_l", "ctrl", "ctrl_l", "alt", "alt_l", "cmd", "cmd_l"}
)
RIGHT_PORTABLE_KEYS = frozenset(
    {
        "backspace", "enter", "shift_r", "ctrl_r", "alt_r", "cmd_r",
        "insert", "delete", "home", "end", "page_up", "page_down",
        "left", "right", "up", "down", "num_lock",
    }
)


def classify_windows_key(
    vk_code: int,
    scan_code: int = 0,
    flags: int = 0,
) -> PawAction:
    if vk_code == 0x20:
        return "both"
    if vk_code == 0x10:
        return "right" if scan_code == 0x36 else "left"
    if vk_code in (VK_CONTROL, VK_MENU):
        return "right" if flags & LLKHF_EXTENDED else "left"
    if 0x70 <= vk_code <= 0x75:
        return "left"
    if 0x76 <= vk_code <= 0x7B:
        return "right"
    if vk_code in LEFT_WINDOWS_KEYS:
        return "left"
    if vk_code in RIGHT_WINDOWS_KEYS:
        return "right"
    return "alternate"


def classify_portable_key(key: object) -> PawAction:
    char = getattr(key, "char", None)
    if char == " ":
        return "both"
    if isinstance(char, str):
        if char.lower() in LEFT_PORTABLE_CHARACTERS:
            return "left"
        if char.lower() in RIGHT_PORTABLE_CHARACTERS:
            return "right"

    name = getattr(key, "name", None)
    if name == "space":
        return "both"
    if name in LEFT_PORTABLE_KEYS:
        return "left"
    if name in RIGHT_PORTABLE_KEYS or (
        isinstance(name, str) and name.startswith("num_")
    ):
        return "right"
    if isinstance(name, str) and name.startswith("f"):
        try:
            number = int(name[1:])
        except ValueError:
            return "alternate"
        if 1 <= number <= 6:
            return "left"
        if 7 <= number <= 12:
            return "right"
        return "alternate"
    return "alternate"
```

Keep the constants close to the current virtual-key constants. Format the long sets to the repository's 88-character line style without changing their contents.

- [ ] **Step 4: Run the classifier tests and full behavior module**

Run:

```bash
python -m unittest tests.test_behavior.KeyboardClassificationTests tests.test_behavior.AnimationStateTests -v
```

Expected: all classifier tests and the unchanged animation tests pass.

- [ ] **Step 5: Commit the classification boundary**

```bash
git add cat_type.py tests/test_behavior.py
git commit -m "feat: classify keyboard input by paw side"
```

---

### Task 2: Paw-Directed Animation State

**Files:**
- Modify: `cat_type.py:379-415`
- Modify: `tests/test_behavior.py` in `AnimationStateTests`

**Interfaces:**
- Consumes: `PawAction` from Task 1.
- Produces: `AnimationState.record_key(now: float, paw: PawAction = "alternate") -> None`.
- Preserves: `frame_name`, `is_visible`, and `opacity` public behavior and timing.

- [ ] **Step 1: Add failing tests for explicit paws, spacebar, fallback, and settling**

Replace and extend `AnimationStateTests` with the following focused behavior tests while retaining the existing opacity assertions:

```python
class AnimationStateTests(unittest.TestCase):
    def test_explicit_keyboard_sides_choose_matching_paws(self) -> None:
        animation = AnimationState(hide_after=0.9)

        animation.record_key(10.0, "left")
        self.assertEqual(animation.frame_name(10.01), "tap-left")
        animation.record_key(10.2, "right")
        self.assertEqual(animation.frame_name(10.21), "tap-right")

    def test_spacebar_uses_both_paws_then_settles(self) -> None:
        animation = AnimationState()

        animation.record_key(1.0, "both")

        self.assertEqual(animation.frame_name(1.01), "excited")
        self.assertEqual(animation.frame_name(1.17), "idle")

    def test_unknown_keys_keep_the_alternating_fallback(self) -> None:
        animation = AnimationState()

        animation.record_key(2.0, "alternate")
        self.assertEqual(animation.frame_name(2.01), "tap-left")
        animation.record_key(2.2, "alternate")
        self.assertEqual(animation.frame_name(2.21), "tap-right")

    def test_fast_typing_overrides_latest_side_with_both_paws(self) -> None:
        animation = AnimationState()
        for index, timestamp in enumerate((1.0, 1.05, 1.1, 1.15, 1.2)):
            paw = "left" if index % 2 == 0 else "right"
            animation.record_key(timestamp, paw)

        self.assertEqual(animation.frame_name(1.21), "excited")
        self.assertEqual(animation.frame_name(1.37), "idle")

    def test_settles_and_hides_on_the_existing_timing(self) -> None:
        animation = AnimationState(hide_after=0.9)
        animation.record_key(10.0, "left")

        self.assertEqual(animation.frame_name(10.17), "idle")
        self.assertTrue(animation.is_visible(10.8))
        self.assertFalse(animation.is_visible(11.2))

    def test_fades_during_the_end_of_the_visible_period(self) -> None:
        animation = AnimationState(hide_after=1.5, fade_seconds=0.3)
        animation.record_key(10.0, "left")

        self.assertEqual(animation.opacity(11.19), 1.0)
        self.assertAlmostEqual(animation.opacity(11.35), 0.5)
        self.assertEqual(animation.opacity(11.5), 0.0)

        animation.record_key(11.6, "right")
        self.assertEqual(animation.opacity(11.6), 1.0)
```

- [ ] **Step 2: Run the tests and verify explicit paw arguments fail**

Run:

```bash
python -m unittest tests.test_behavior.AnimationStateTests -v
```

Expected: failures report that `AnimationState.record_key()` does not accept a paw argument.

- [ ] **Step 3: Store the resolved paw and render it after the idle check**

Change `AnimationState` to this behavior:

```python
class AnimationState:
    def __init__(
        self,
        hide_after: float = 0.9,
        fade_seconds: float = 0.35,
    ) -> None:
        self.hide_after = hide_after
        self.fade_seconds = min(max(0.0, fade_seconds), hide_after)
        self.last_key_at = 0.0
        self._tap_count = 0
        self._paw: PawAction = "left"
        self._recent: deque[float] = deque(maxlen=6)

    def record_key(
        self,
        now: float,
        paw: PawAction = "alternate",
    ) -> None:
        self.last_key_at = now
        self._tap_count += 1
        self._paw = (
            "left" if self._tap_count % 2 else "right"
        ) if paw == "alternate" else paw
        self._recent.append(now)

    def frame_name(self, now: float) -> str:
        if now - self.last_key_at > 0.16:
            return "idle"
        if (
            self._paw == "both"
            or len(self._recent) >= 5
            and self._recent[-1] - self._recent[-5] < 0.34
        ):
            return "excited"
        return "tap-left" if self._paw == "left" else "tap-right"
```

Leave `is_visible` and `opacity` unchanged.

- [ ] **Step 4: Run behavior tests and verify green**

Run:

```bash
python -m unittest tests.test_behavior.AnimationStateTests -v
```

Expected: all animation tests pass, including the rapid-pose return to idle.

- [ ] **Step 5: Commit paw-directed animation**

```bash
git add cat_type.py tests/test_behavior.py
git commit -m "feat: animate the paw matching each key"
```

---

### Task 3: Settings-Only Session Counter UI

**Files:**
- Modify: `settings_window.py:148-195`
- Modify: `settings_window.py:487-520`
- Modify: `settings_window.py:819-858`
- Modify: `tests/test_settings_window.py:173-241`

**Interfaces:**
- Produces: optional `SettingsWindow(..., keystroke_count: int = 0)` constructor parameter after `icon_path`.
- Produces: `SettingsWindow.update_keystroke_count(count: int) -> None`.
- Produces: `SettingsWindow.keystroke_count_text: tk.StringVar` and settings-card labels.
- Does not modify: `AppSettings`, `SettingsStore`, or any overlay widget.

- [ ] **Step 1: Add a failing Tk settings-counter test**

Pass a nonzero initial count from `SettingsWindowTkLayoutTests.setUp`, then add this test:

```python
        self.settings_window = SettingsWindow(
            self.root,
            AppSettings(),
            lambda _settings: None,
            keystroke_count=1_234,
        )

    def test_session_keystroke_counter_is_visible_and_updates_live(self) -> None:
        self.assertEqual(
            self.settings_window.keystroke_count_title.cget("text"),
            "Keystrokes this session",
        )
        self.assertEqual(
            self.settings_window.keystroke_count_text.get(),
            "1,234",
        )

        self.settings_window.update_keystroke_count(5_678)

        self.assertEqual(
            self.settings_window.keystroke_count_text.get(),
            "5,678",
        )
```

- [ ] **Step 2: Run the focused test and verify the constructor fails**

On Linux with Tk and Xvfb installed, run:

```bash
xvfb-run --auto-servernum python -m unittest tests.test_settings_window.SettingsWindowTkLayoutTests.test_session_keystroke_counter_is_visible_and_updates_live -v
```

On Windows or macOS with a display session, omit `xvfb-run --auto-servernum`.

Expected: failure because `SettingsWindow.__init__` does not accept `keystroke_count`.

- [ ] **Step 3: Add the non-persistent display variable and live updater**

Add `keystroke_count` after the existing optional `icon_path` argument:

```python
    def __init__(
        self,
        parent: tk.Misc,
        settings: AppSettings,
        on_save: Callable[[AppSettings], None],
        icon_path: str | None = None,
        keystroke_count: int = 0,
    ) -> None:
```

Immediately after the existing `self.launch_at_startup` assignment, create
the display-only variable:

```python
        self.keystroke_count_text = tk.StringVar(
            value=f"{keystroke_count:,}"
        )
```

In `_build_companion_card`, insert the counter after the enabled toggle and before the first divider:

```python
        counter = tk.Frame(content, background=self.BLUSH)
        counter.pack(fill="x", pady=(14, 0))
        self.keystroke_count_title = tk.Label(
            counter,
            text="Keystrokes this session",
            background=self.BLUSH,
            foreground=self.MUTED,
            font=self.fonts["small"],
        )
        self.keystroke_count_title.pack(
            side="left",
            padx=(12, 6),
            pady=10,
        )
        tk.Label(
            counter,
            textvariable=self.keystroke_count_text,
            background=self.BLUSH,
            foreground=self.ACCENT_DARK,
            font=self.fonts["section"],
        ).pack(side="right", padx=(6, 12), pady=8)
```

Add the update method near `show`:

```python
    def update_keystroke_count(self, count: int) -> None:
        self.keystroke_count_text.set(f"{count:,}")
```

- [ ] **Step 4: Run the settings tests and verify green**

Run:

```bash
xvfb-run --auto-servernum python -m unittest tests.test_settings_window -v
```

Expected: all settings-window tests pass and the counter formats thousands with commas.

- [ ] **Step 5: Commit the Settings counter**

```bash
git add settings_window.py tests/test_settings_window.py
git commit -m "feat: show session keystrokes in settings"
```

---

### Task 4: Listener Events and Application Session Counting

**Files:**
- Modify: `cat_type.py:418-532`
- Modify: `cat_type.py:784-920`
- Modify: `cat_type.py:1110-1168`
- Modify: `tests/test_behavior.py`
- Modify: `tests/test_overlay_rendering.py` in `OverlayRenderingTests`

**Interfaces:**
- Consumes: `AppEvent`, `PawAction`, both classifiers, directed `AnimationState.record_key`, and `SettingsWindow.update_keystroke_count`.
- Produces: `KeyboardMonitor._emit_key(paw: PawAction, happened_at: float | None = None) -> None`.
- Produces: `CatTypeApp._handle_key_activity(happened_at: float, paw: PawAction) -> None`.
- Produces: `CatTypeApp.keystroke_count: int`, initialized to zero and never saved.

- [ ] **Step 1: Add failing monitor-payload and app-counter tests**

Add the exact standard-library imports used by the tests:

```python
import queue
import unittest
from unittest.mock import Mock, patch
```

Extend the `cat_type` import with `AppEvent`, `CatTypeApp`, and
`KeyboardMonitor`, and add `AppSettings` from `cat_settings`:

```python
from cat_settings import AppSettings
from cat_type import (
    AppEvent,
    AnimationState,
    CaretLocator,
    CatTypeApp,
    KeyboardMonitor,
    ScreenRect,
    classify_portable_key,
    classify_windows_key,
    choose_fallback_position,
    choose_overlay_position,
)
```

Then add:

```python
class KeyboardMonitorEventTests(unittest.TestCase):
    def test_emitted_key_event_contains_only_time_and_paw(self) -> None:
        events: queue.SimpleQueue[AppEvent] = queue.SimpleQueue()
        monitor = KeyboardMonitor(events)

        monitor._emit_key("left", happened_at=12.5)

        self.assertEqual(events.get_nowait(), AppEvent("key", 12.5, "left"))


class CatTypeKeyActivityTests(unittest.TestCase):
    @staticmethod
    def make_app(enabled: bool = True) -> CatTypeApp:
        app = CatTypeApp.__new__(CatTypeApp)
        app.settings = AppSettings(enabled=enabled)
        app.animation = Mock()
        app.animation.is_visible.return_value = False
        app.tracker = Mock()
        app._anchor_position = (20, 30)
        app._last_key_at = 0.0
        app.keystroke_count = 0
        app._settings_window = None
        return app

    def test_enabled_key_updates_animation_tracking_and_session_count(self) -> None:
        app = self.make_app()

        app._handle_key_activity(10.0, "left")

        self.assertEqual(app.keystroke_count, 1)
        self.assertIsNone(app._anchor_position)
        self.assertEqual(app._last_key_at, 10.0)
        app.animation.record_key.assert_called_once_with(10.0, "left")
        app.tracker.notify_activity.assert_called_once_with(10.0)

    def test_disabled_key_does_not_increment_or_animate(self) -> None:
        app = self.make_app(enabled=False)

        app._handle_key_activity(10.0, "right")

        self.assertEqual(app.keystroke_count, 0)
        app.animation.record_key.assert_not_called()
        app.tracker.notify_activity.assert_not_called()

    def test_open_settings_counter_updates_live(self) -> None:
        app = self.make_app()
        settings_window = Mock()
        settings_window.window.winfo_exists.return_value = True
        app._settings_window = settings_window

        app._handle_key_activity(10.0, "both")

        settings_window.update_keystroke_count.assert_called_once_with(1)

    def test_repeated_keydowns_count_individually(self) -> None:
        app = self.make_app()

        app._handle_key_activity(10.0, "right")
        app._handle_key_activity(10.1, "right")

        self.assertEqual(app.keystroke_count, 2)

    def test_open_settings_receives_the_current_session_count(self) -> None:
        app = self.make_app()
        app.root = Mock()
        app.keystroke_count = 42

        with (
            patch("cat_type.SettingsWindow") as settings_window,
            patch("cat_type.APP_ICON") as app_icon,
        ):
            app_icon.exists.return_value = False
            app.open_settings()

        settings_window.assert_called_once_with(
            app.root,
            app.settings,
            app.apply_settings,
            None,
            keystroke_count=42,
        )
```

Add this Windows/Tk overlay regression to `tests/test_overlay_rendering.py`:

```python
    def test_keystroke_counter_is_not_rendered_in_the_cat_overlay(self) -> None:
        app = CatTypeApp(hold_seconds=10.0)
        try:
            app.root.update_idletasks()

            self.assertEqual(app.root.winfo_children(), [app.label])
            self.assertEqual(app.label.winfo_reqwidth(), app.frame_width)
            self.assertEqual(app.label.winfo_reqheight(), app.frame_height)
        finally:
            app.root.destroy()
```

- [ ] **Step 2: Run the focused tests and verify the missing handlers fail**

Run:

```bash
python -m unittest tests.test_behavior.KeyboardMonitorEventTests tests.test_behavior.CatTypeKeyActivityTests -v
```

Expected: failures because `_emit_key`, `_handle_key_activity`, and `keystroke_count` do not exist.

- [ ] **Step 3: Emit classified `AppEvent` values from both listeners**

Change the existing `KeyboardMonitor.__init__` queue annotation from
`queue.SimpleQueue[tuple[str, float]]` to `queue.SimpleQueue[AppEvent]`.
Then add the helper after `stop`:

```python
    def _emit_key(
        self,
        paw: PawAction,
        happened_at: float | None = None,
    ) -> None:
        self.event_queue.put(
            AppEvent(
                "key",
                time.monotonic() if happened_at is None else happened_at,
                paw,
            )
        )
```

For a Windows keydown, update modifier state first, keep the quit chord check ahead of normal emission, and otherwise classify without retaining metadata:

```python
                if message in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    if vk in (VK_CONTROL, VK_LCONTROL, VK_RCONTROL):
                        self._ctrl_down = True
                    elif vk in (VK_MENU, VK_LMENU, VK_RMENU):
                        self._alt_down = True

                    if vk == VK_Q and self._ctrl_down and self._alt_down:
                        self.event_queue.put(AppEvent("quit", time.monotonic()))
                    else:
                        self._emit_key(
                            classify_windows_key(
                                vk,
                                data.scanCode,
                                data.flags,
                            )
                        )
```

For portable `on_press`, update modifier state without returning, preserve quit precedence, and emit only the classification:

```python
            def on_press(key: object, *_injected: object) -> None:
                if key in ctrl_keys:
                    self._ctrl_down = True
                elif key in alt_keys:
                    self._alt_down = True

                char = getattr(key, "char", None)
                if (
                    char
                    and char.lower() == "q"
                    and self._ctrl_down
                    and self._alt_down
                ):
                    self.event_queue.put(AppEvent("quit", time.monotonic()))
                else:
                    self._emit_key(classify_portable_key(key))
```

Replace both hook-error tuple emissions with:

```python
            self.event_queue.put(
                AppEvent("hook-error", time.monotonic())
            )
```

Change the three tray callbacks to enqueue these exact values:

```python
AppEvent("settings", time.monotonic())
AppEvent("toggle", time.monotonic())
AppEvent("quit", time.monotonic())
```

This leaves no mixed tuple/dataclass protocol in the queue.

- [ ] **Step 4: Add session ownership and a focused key handler to `CatTypeApp`**

Initialize the queue and total before constructing the keyboard monitor:

```python
        self.events: queue.SimpleQueue[AppEvent] = queue.SimpleQueue()
        self.keystroke_count = 0
```

Add this method near `_tick`:

```python
    def _handle_key_activity(
        self,
        happened_at: float,
        paw: PawAction,
    ) -> None:
        if not self.settings.enabled:
            return
        if not self.animation.is_visible(happened_at):
            self._anchor_position = None
        self._last_key_at = happened_at
        self.keystroke_count += 1
        self.animation.record_key(happened_at, paw)
        self.tracker.notify_activity(happened_at)
        if (
            self._settings_window is not None
            and self._settings_window.window.winfo_exists()
        ):
            self._settings_window.update_keystroke_count(
                self.keystroke_count
            )
```

Update `_tick` to consume `AppEvent` and delegate keys:

```python
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            if event.kind == "quit":
                should_quit = True
            elif event.kind == "settings":
                self.open_settings()
            elif event.kind == "toggle":
                self._set_enabled(not self.settings.enabled)
            elif event.kind == "hook-error":
                self._hook_failed = True
            elif event.kind == "key":
                assert event.paw is not None
                self._handle_key_activity(event.happened_at, event.paw)
```

Keep the startup `animation.record_key(started_at)` call separate from `_handle_key_activity`; this is what guarantees the startup appearance leaves `keystroke_count` at zero.

Pass the current total only to Settings:

```python
        self._settings_window = SettingsWindow(
            self.root,
            self.settings,
            self.apply_settings,
            str(APP_ICON) if APP_ICON.exists() else None,
            keystroke_count=self.keystroke_count,
        )
```

- [ ] **Step 5: Run the focused behavior and overlay tests**

Run:

```bash
python -m unittest tests.test_behavior.KeyboardMonitorEventTests tests.test_behavior.CatTypeKeyActivityTests -v
```

Expected: all monitor and session-count tests pass.

On Windows, also run:

```powershell
python -m unittest tests.test_overlay_rendering.OverlayRenderingTests.test_keystroke_counter_is_not_rendered_in_the_cat_overlay -v
```

Expected: the root still contains only the sprite label with unchanged dimensions.

- [ ] **Step 6: Commit listener integration and session counting**

```bash
git add cat_type.py tests/test_behavior.py tests/test_overlay_rendering.py
git commit -m "feat: count classified keyboard activity"
```

---

### Task 5: User-Facing Documentation and Full Verification

**Files:**
- Modify: `README.md:3-5`
- Modify: `README.md:47-58`
- Modify: `README.md:112-120`

**Interfaces:**
- Documents: the QWERTY-side paw behavior, spacebar both-paws pose, settings-only session count, and privacy boundary.
- Verifies: every explicit behavior in the approved design and all existing regression coverage.

- [ ] **Step 1: Update the overview, Settings list, and privacy behavior**

Use this overview copy:

```markdown
Cat Type is a desktop companion for Windows, macOS, and Linux that makes a tiny
animated cat appear while you type. Its paws follow the side of the keyboard
you use, spacebar taps both paws, fast typing makes it excited, and it fades
away after you stop.
```

Add this Settings bullet:

```markdown
- See how many keystrokes Cat Type has reacted to in the current session.
```

Replace the first two privacy bullets with:

```markdown
- The keyboard listener classifies each key as left, right, both, or an
  alternating fallback, then immediately discards the key itself.
- Cat Type retains only the paw action, activity time, and in-memory session
  total. It never reconstructs text, writes keystrokes to disk, or sends input
  over the network.
```

- [ ] **Step 2: Run formatting and targeted static checks**

Run:

```bash
git diff --check
rg -n "alternates paws|writes keystrokes|Keystrokes this session|classifies each key" README.md settings_window.py
```

Expected: `git diff --check` prints nothing; search results show the new Settings label and privacy copy and no stale overview claim.

- [ ] **Step 3: Run the cross-platform CI test selection**

On Linux with Tk and Xvfb installed, run exactly the suite used by the workflows:

```bash
xvfb-run --auto-servernum python -m unittest tests.test_behavior tests.test_settings tests.test_settings_window tests.test_platform_assets tests.test_bundled_icon_check tests.test_package_smoke -v
```

On Windows or macOS with a display session, omit `xvfb-run --auto-servernum`.

Expected: every selected test passes with no errors or warnings.

- [ ] **Step 4: Run the platform-specific overlay regression suite on Windows**

```powershell
python -m unittest tests.test_overlay_rendering -v
```

Expected: all overlay and sprite-rendering tests pass, including the proof that the counter is not in the overlay.

- [ ] **Step 5: Audit each requirement against current evidence**

Confirm all of the following before declaring completion:

```text
Left key -> tap-left unit tests pass.
Right key -> tap-right unit tests pass.
Space -> excited/both unit test passes.
Rapid typing -> excited override and return-to-idle tests pass.
Unknown key -> alternating fallback test passes.
Enabled/repeat counting -> application handler tests pass.
Disabled/startup counting -> handler test plus separate startup path prove no increment.
Settings-only visibility -> Settings Tk test and overlay regression pass.
No persistence -> AppSettings/SettingsStore remain unchanged.
No raw key retention -> AppEvent field test and classifier/listener boundary pass.
Ctrl+Alt+Q -> listener branch still handles quit before key emission.
```

- [ ] **Step 6: Commit documentation**

```bash
git add README.md
git commit -m "docs: explain keyboard-aware paws and counter"
```
