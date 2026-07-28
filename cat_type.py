from __future__ import annotations

import argparse
import ctypes
import queue
import sys
import threading
import time
import tkinter as tk
from collections import deque
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable
from ctypes import wintypes

import pystray
from PIL import Image, ImageTk

from cat_settings import AppSettings, SettingsStore, set_launch_at_startup
from settings_window import SettingsWindow


if sys.platform != "win32":
    raise SystemExit("This prototype currently supports Windows only.")


APP_DIR = Path(
    getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
)
FRAME_ROOT = APP_DIR / "assets" / "tabby-frames"
APP_ICON = APP_DIR / "assets" / "cat-type.ico"
CAT_VARIANTS = ("gray", "ginger")
FRAME_DIR = FRAME_ROOT / CAT_VARIANTS[0]
FRAME_NAMES = ("idle", "tap-left", "tap-right", "excited")

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012
WH_KEYBOARD_LL = 13
HC_ACTION = 0

VK_CONTROL = 0x11
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_MENU = 0x12
VK_LMENU = 0xA4
VK_RMENU = 0xA5
VK_Q = 0x51

WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
GWL_EXSTYLE = -20

HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
MONITOR_DEFAULTTONEAREST = 0x00000002
TEXT_PATTERN_RANGE_ENDPOINT_START = 0
TEXT_PATTERN_RANGE_ENDPOINT_END = 1
TEXT_UNIT_CHARACTER = 0

LRESULT = ctypes.c_ssize_t
ULONG_PTR = wintypes.WPARAM

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


HOOKPROC = ctypes.WINFUNCTYPE(
    LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
)

user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    HOOKPROC,
    wintypes.HINSTANCE,
    wintypes.DWORD,
]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.argtypes = [
    wintypes.HHOOK,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.GetGUIThreadInfo.argtypes = [
    wintypes.DWORD,
    ctypes.POINTER(GUITHREADINFO),
]
user32.GetGUIThreadInfo.restype = wintypes.BOOL
user32.ClientToScreen.argtypes = [
    wintypes.HWND,
    ctypes.POINTER(wintypes.POINT),
]
user32.ClientToScreen.restype = wintypes.BOOL
user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
user32.MonitorFromPoint.restype = wintypes.HMONITOR
user32.GetMonitorInfoW.argtypes = [
    wintypes.HMONITOR,
    ctypes.POINTER(MONITORINFO),
]
user32.GetMonitorInfoW.restype = wintypes.BOOL
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long
user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
user32.SetWindowLongW.restype = ctypes.c_long
user32.SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
user32.SetWindowPos.restype = wintypes.BOOL
user32.PostThreadMessageW.argtypes = [
    wintypes.DWORD,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.PostThreadMessageW.restype = wintypes.BOOL
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.CreateMutexW.argtypes = [
    ctypes.c_void_p,
    wintypes.BOOL,
    wintypes.LPCWSTR,
]
kernel32.CreateMutexW.restype = wintypes.HANDLE

_instance_mutex: int | None = None


@dataclass(frozen=True)
class ScreenRect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return max(1, self.right - self.left)

    @property
    def height(self) -> int:
        return max(1, self.bottom - self.top)


@dataclass(frozen=True)
class CaretSnapshot:
    captured_at: float
    rect: ScreenRect | None
    is_password: bool = False
    source: str = "none"


def set_per_monitor_dpi_awareness() -> None:
    """Keep caret and overlay coordinates in the same physical pixel space."""
    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        try:
            user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def acquire_single_instance() -> bool:
    global _instance_mutex
    _instance_mutex = kernel32.CreateMutexW(
        None,
        False,
        "Local\\CatTypeDesktopApp",
    )
    return bool(_instance_mutex) and ctypes.get_last_error() != 183


def work_area_for(rect: ScreenRect) -> ScreenRect:
    point = wintypes.POINT(rect.left, rect.top)
    monitor = user32.MonitorFromPoint(point, MONITOR_DEFAULTTONEAREST)
    info = MONITORINFO(cbSize=ctypes.sizeof(MONITORINFO))
    if monitor and user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        work = info.rcWork
        return ScreenRect(work.left, work.top, work.right, work.bottom)
    return ScreenRect(0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))


def choose_overlay_position(
    caret: ScreenRect,
    overlay_width: int,
    overlay_height: int,
    work_area: ScreenRect,
    gap: int = 6,
    placement: str = "above-right",
) -> tuple[int, int]:
    """Use the preferred caret corner, then flip to remain on-screen."""
    prefer_left = placement.endswith("left")
    prefer_below = placement.startswith("below")

    x = (
        caret.left - overlay_width - gap
        if prefer_left
        else caret.right + gap
    )
    y = (
        caret.bottom + gap
        if prefer_below
        else caret.top - overlay_height - gap
    )

    if x < work_area.left or x + overlay_width > work_area.right:
        x = (
            caret.right + gap
            if prefer_left
            else caret.left - overlay_width - gap
        )
    if y < work_area.top or y + overlay_height > work_area.bottom:
        y = (
            caret.top - overlay_height - gap
            if prefer_below
            else caret.bottom + gap
        )

    x = max(work_area.left, min(x, work_area.right - overlay_width))
    y = max(work_area.top, min(y, work_area.bottom - overlay_height))
    return x, y


def make_window_non_interactive(hwnd: int) -> None:
    """Keep the overlay topmost without taking focus or pointer input."""
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    style |= (
        WS_EX_TRANSPARENT
        | WS_EX_TOOLWINDOW
        | WS_EX_NOACTIVATE
    )
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
    user32.SetWindowPos(
        hwnd,
        HWND_TOPMOST,
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
    )


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
        self._recent: deque[float] = deque(maxlen=6)

    def record_key(self, now: float) -> None:
        self.last_key_at = now
        self._tap_count += 1
        self._recent.append(now)

    def is_visible(self, now: float) -> bool:
        return self.last_key_at > 0 and now - self.last_key_at < self.hide_after

    def opacity(self, now: float) -> float:
        if not self.is_visible(now):
            return 0.0
        if self.fade_seconds == 0:
            return 1.0

        elapsed = now - self.last_key_at
        fade_starts_at = self.hide_after - self.fade_seconds
        if elapsed <= fade_starts_at:
            return 1.0
        return max(0.0, (self.hide_after - elapsed) / self.fade_seconds)

    def frame_name(self, now: float) -> str:
        if len(self._recent) >= 5 and self._recent[-1] - self._recent[-5] < 0.34:
            return "excited"
        if now - self.last_key_at > 0.16:
            return "idle"
        return "tap-left" if self._tap_count % 2 else "tap-right"


class KeyboardMonitor:
    """Signals activity only. It never turns virtual-key codes into text."""

    def __init__(self, event_queue: queue.SimpleQueue[tuple[str, float]]) -> None:
        self.event_queue = event_queue
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._hook = None
        self._callback = None
        self._ctrl_down = False
        self._alt_down = False

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run, name="keyboard-activity", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _run(self) -> None:
        self._thread_id = kernel32.GetCurrentThreadId()

        @HOOKPROC
        def callback(
            code: int, message: wintypes.WPARAM, data_ptr: wintypes.LPARAM
        ) -> int:
            if code == HC_ACTION:
                data = ctypes.cast(
                    data_ptr, ctypes.POINTER(KBDLLHOOKSTRUCT)
                ).contents
                vk = data.vkCode

                if message in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    if vk in (VK_CONTROL, VK_LCONTROL, VK_RCONTROL):
                        self._ctrl_down = True
                    elif vk in (VK_MENU, VK_LMENU, VK_RMENU):
                        self._alt_down = True
                    elif vk == VK_Q and self._ctrl_down and self._alt_down:
                        self.event_queue.put(("quit", time.monotonic()))
                    else:
                        self.event_queue.put(("key", time.monotonic()))
                elif message in (WM_KEYUP, WM_SYSKEYUP):
                    if vk in (VK_CONTROL, VK_LCONTROL, VK_RCONTROL):
                        self._ctrl_down = False
                    elif vk in (VK_MENU, VK_LMENU, VK_RMENU):
                        self._alt_down = False

            return user32.CallNextHookEx(None, code, message, data_ptr)

        self._callback = callback
        module = kernel32.GetModuleHandleW(None)
        self._hook = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL, callback, module, 0
        )
        if not self._hook:
            self.event_queue.put(("hook-error", time.monotonic()))
            return

        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))

        user32.UnhookWindowsHookEx(self._hook)
        self._hook = None


class CaretLocator:
    def __init__(self, debug: bool = False) -> None:
        self.debug = debug
        self._automation = None
        self._uia = None

    def initialize_uia(self) -> None:
        try:
            import comtypes.client

            comtypes.client.GetModule("UIAutomationCore.dll")
            from comtypes.gen import UIAutomationClient

            self._uia = UIAutomationClient
            self._automation = comtypes.client.CreateObject(
                UIAutomationClient.CUIAutomation8,
                interface=UIAutomationClient.IUIAutomation,
            )
        except Exception as exc:
            if self.debug:
                print(f"UI Automation unavailable: {exc}", file=sys.stderr)
            self._uia = None
            self._automation = None

    def locate(self) -> CaretSnapshot:
        now = time.monotonic()
        uia_rect, is_password = self._locate_with_uia()
        if is_password:
            return CaretSnapshot(now, None, True, "uia-password")
        if uia_rect:
            return CaretSnapshot(now, uia_rect, False, "uia")

        win32_rect = self._locate_with_win32()
        if win32_rect:
            return CaretSnapshot(now, win32_rect, False, "win32")
        return CaretSnapshot(now, None)

    def _locate_with_win32(self) -> ScreenRect | None:
        info = GUITHREADINFO(cbSize=ctypes.sizeof(GUITHREADINFO))
        if not user32.GetGUIThreadInfo(0, ctypes.byref(info)) or not info.hwndCaret:
            return None

        top_left = wintypes.POINT(info.rcCaret.left, info.rcCaret.top)
        bottom_right = wintypes.POINT(info.rcCaret.right, info.rcCaret.bottom)
        if not user32.ClientToScreen(info.hwndCaret, ctypes.byref(top_left)):
            return None
        if not user32.ClientToScreen(info.hwndCaret, ctypes.byref(bottom_right)):
            return None

        bottom = bottom_right.y
        right = bottom_right.x
        if bottom <= top_left.y:
            bottom = top_left.y + 18
        if right <= top_left.x:
            right = top_left.x + 2
        return ScreenRect(top_left.x, top_left.y, right, bottom)

    def _locate_with_uia(self) -> tuple[ScreenRect | None, bool]:
        if self._automation is None or self._uia is None:
            return None, False

        try:
            element = self._automation.GetFocusedElement()
            if not element:
                return None, False
            if bool(element.CurrentIsPassword):
                return None, True

            unknown = element.GetCurrentPattern(self._uia.UIA_TextPattern2Id)
            if unknown:
                pattern = unknown.QueryInterface(
                    self._uia.IUIAutomationTextPattern2
                )
                is_active, text_range = pattern.GetCaretRange()
                if is_active and text_range:
                    rect = self._rect_from_uia_range(text_range)
                    if rect:
                        return rect, False

            # Older providers often expose TextPattern but not TextPattern2.
            unknown = element.GetCurrentPattern(self._uia.UIA_TextPatternId)
            if unknown:
                pattern = unknown.QueryInterface(
                    self._uia.IUIAutomationTextPattern
                )
                ranges = pattern.GetSelection()
                if ranges and ranges.Length:
                    rect = self._rect_from_uia_range(ranges.GetElement(0))
                    if rect:
                        return rect, False
        except Exception as exc:
            if self.debug:
                print(f"UI Automation lookup failed: {exc}", file=sys.stderr)
        return None, False

    @staticmethod
    def _rect_from_uia_range(text_range: object) -> ScreenRect | None:
        values = text_range.GetBoundingRectangles()
        coords = tuple(values) if values is not None else ()
        used_character_probe = False
        use_trailing_edge = False

        # UI Automation permits a provider to return no rectangles for a
        # degenerate (zero-length) caret range. Terminals commonly do this.
        # Temporarily include the next character to obtain the caret cell's
        # geometry. At the end of a document, include the previous character
        # and use its trailing edge instead.
        if len(coords) < 4:
            probe = text_range.Clone()
            moved = probe.MoveEndpointByUnit(
                TEXT_PATTERN_RANGE_ENDPOINT_END,
                TEXT_UNIT_CHARACTER,
                1,
            )
            if not moved:
                probe = text_range.Clone()
                moved = probe.MoveEndpointByUnit(
                    TEXT_PATTERN_RANGE_ENDPOINT_START,
                    TEXT_UNIT_CHARACTER,
                    -1,
                )
                use_trailing_edge = bool(moved)
            if moved:
                values = probe.GetBoundingRectangles()
                coords = tuple(values) if values is not None else ()
                used_character_probe = True

        if len(coords) < 4:
            return None

        # Use the final rectangle for a collapsed selection/caret at line end.
        left, top, width, height = coords[-4:]
        if width < 0 or height <= 0:
            return None
        if use_trailing_edge:
            left += width
        right = left + (2.0 if used_character_probe else max(width, 2.0))
        return ScreenRect(
            round(left), round(top), round(right), round(top + height)
        )


class CaretTracker:
    def __init__(self, debug: bool = False) -> None:
        self._locator = CaretLocator(debug=debug)
        self._snapshot = CaretSnapshot(0.0, None)
        self._snapshot_lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._active_until = 0.0
        self._activity_lock = threading.Lock()
        self._thread = threading.Thread(
            target=self._run, name="caret-tracker", daemon=True
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def notify_activity(self, now: float) -> None:
        with self._activity_lock:
            self._active_until = max(self._active_until, now + 1.0)
        self._wake.set()

    def snapshot(self) -> CaretSnapshot:
        with self._snapshot_lock:
            return self._snapshot

    def _run(self) -> None:
        import comtypes

        comtypes.CoInitialize()
        try:
            self._locator.initialize_uia()
            while not self._stop.is_set():
                self._wake.wait(timeout=self._poll_interval())
                self._wake.clear()
                if self._stop.is_set():
                    break
                snapshot = self._locator.locate()
                with self._snapshot_lock:
                    self._snapshot = snapshot
        finally:
            comtypes.CoUninitialize()

    def _poll_interval(self) -> float:
        with self._activity_lock:
            active = time.monotonic() < self._active_until
        return 0.025 if active else 0.25


class CatTypeApp:
    TRANSPARENT_COLOR = "#00ff01"

    def __init__(
        self,
        debug: bool = False,
        hold_seconds: float = 1.5,
        fade_seconds: float = 0.35,
        settings: AppSettings | None = None,
        settings_store: SettingsStore | None = None,
    ) -> None:
        self.debug = debug
        self.settings_store = settings_store or SettingsStore()
        self._first_run = not self.settings_store.path.exists()
        self.settings = (
            settings
            or AppSettings(
                hold_seconds=hold_seconds,
                fade_seconds=fade_seconds,
            )
        ).normalized()
        self.events: queue.SimpleQueue[tuple[str, float]] = queue.SimpleQueue()
        self.animation = AnimationState(
            hide_after=self.settings.hold_seconds,
            fade_seconds=self.settings.fade_seconds,
        )
        self.keyboard = KeyboardMonitor(self.events)
        self.tracker = CaretTracker(debug=debug)
        self._last_rendered_frame: tuple[str, str] | None = None
        self._last_key_at = 0.0
        self._hook_failed = False
        self._last_debug_at = 0.0
        self._last_debug_source = ""
        self._overlay_visible = False
        self._anchor_position: tuple[int, int] | None = None
        self._active_variant = CAT_VARIANTS[0]
        self._next_variant_index = 0
        self._settings_window: SettingsWindow | None = None
        self._tray_icon: pystray.Icon | None = None
        self._tray_thread: threading.Thread | None = None
        self._shutting_down = False

        self.root = tk.Tk()
        self.root.title("Cat Type")
        if APP_ICON.exists():
            try:
                self.root.iconbitmap(default=str(APP_ICON))
            except tk.TclError:
                pass
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.configure(background=self.TRANSPARENT_COLOR)
        self.root.wm_attributes("-topmost", True)
        self.root.wm_attributes("-transparentcolor", self.TRANSPARENT_COLOR)

        self.frames = self._load_frames(self.settings.size_percent)
        self.frame_width = self.frames[CAT_VARIANTS[0]]["idle"].width()
        self.frame_height = self.frames[CAT_VARIANTS[0]]["idle"].height()
        self.label = tk.Label(
            self.root,
            image=self.frames[CAT_VARIANTS[0]]["idle"],
            borderwidth=0,
            highlightthickness=0,
            background=self.TRANSPARENT_COLOR,
        )
        self.label.pack()
        self.root.update_idletasks()
        self._make_overlay_non_interactive()
        self.root.withdraw()
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)

    def run(self) -> None:
        self._start_tray()
        self.keyboard.start()
        self.tracker.start()
        # Give immediate visual confirmation when the app starts while a text
        # field is already focused.
        started_at = time.monotonic()
        self.animation.record_key(started_at)
        self.tracker.notify_activity(started_at)
        self.root.after(16, self._tick)
        if self._first_run:
            self.root.after(400, self.open_settings)
        self.root.mainloop()

    def shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        self._hide()
        if self._tray_icon is not None:
            self._tray_icon.stop()
        self.keyboard.stop()
        self.tracker.stop()
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def _tick(self) -> None:
        if not self.root.winfo_exists():
            return

        should_quit = False
        while True:
            try:
                kind, happened_at = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "quit":
                should_quit = True
            elif kind == "settings":
                self.open_settings()
            elif kind == "toggle":
                self._set_enabled(not self.settings.enabled)
            elif kind == "hook-error":
                self._hook_failed = True
            elif kind == "key":
                if not self.settings.enabled:
                    continue
                if not self.animation.is_visible(happened_at):
                    self._anchor_position = None
                self._last_key_at = happened_at
                self.animation.record_key(happened_at)
                self.tracker.notify_activity(happened_at)

        if should_quit:
            self.shutdown()
            return
        if self._hook_failed:
            self._hook_failed = False
            print(
                "Could not install the Windows keyboard activity hook.",
                file=sys.stderr,
            )
            self.shutdown()
            return

        now = time.monotonic()
        snapshot = self.tracker.snapshot()
        snapshot_is_current = snapshot.captured_at >= self._last_key_at - 0.05

        if (
            self.settings.enabled
            and
            self.animation.is_visible(now)
            and snapshot_is_current
            and snapshot.rect is not None
            and not snapshot.is_password
        ):
            self._show(snapshot, now)
        else:
            reset_anchor = (
                not self.animation.is_visible(now) or snapshot.is_password
            )
            self._hide(reset_anchor=reset_anchor)

        self.root.after(16, self._tick)

    def _show(self, snapshot: CaretSnapshot, now: float) -> None:
        assert snapshot.rect is not None
        self.root.wm_attributes("-alpha", self.animation.opacity(now))
        frame_name = self.animation.frame_name(now)

        if self._anchor_position is None:
            area = work_area_for(snapshot.rect)
            self._anchor_position = choose_overlay_position(
                snapshot.rect,
                self.frame_width,
                self.frame_height,
                area,
                placement=self.settings.placement,
            )
            if self.settings.cat_style == "alternate":
                self._active_variant = CAT_VARIANTS[self._next_variant_index]
                self._next_variant_index = (
                    self._next_variant_index + 1
                ) % len(CAT_VARIANTS)
            else:
                self._active_variant = self.settings.cat_style

        rendered_frame = (self._active_variant, frame_name)
        if rendered_frame != self._last_rendered_frame:
            self.label.configure(
                image=self.frames[self._active_variant][frame_name]
            )
            self._last_rendered_frame = rendered_frame

        x, y = self._anchor_position
        self.root.geometry(f"{self.frame_width}x{self.frame_height}+{x}+{y}")
        if not self._overlay_visible:
            self.root.deiconify()
            self.root.lift()
            self._make_overlay_non_interactive()
            self.root.update_idletasks()
            self._overlay_visible = True

        if self.debug and (
            snapshot.source != self._last_debug_source
            or now - self._last_debug_at > 0.5
        ):
            print(
                f"caret={snapshot.source} "
                f"({snapshot.rect.left},{snapshot.rect.top}) "
                f"cat=({x},{y}) frame={frame_name}",
                flush=True,
            )
            self._last_debug_at = now
            self._last_debug_source = snapshot.source

    def _hide(self, reset_anchor: bool = True) -> None:
        if self._overlay_visible:
            self.root.withdraw()
            self._overlay_visible = False
        if reset_anchor:
            self._anchor_position = None
        self.root.wm_attributes("-alpha", 1.0)

    def _make_overlay_non_interactive(self) -> None:
        make_window_non_interactive(self.root.winfo_id())

    def _load_frames(
        self,
        size_percent: int,
    ) -> dict[str, dict[str, tk.PhotoImage | ImageTk.PhotoImage]]:
        if size_percent == 100:
            return {
                variant: {
                    name: tk.PhotoImage(
                        file=str(FRAME_ROOT / variant / f"{name}.png")
                    )
                    for name in FRAME_NAMES
                }
                for variant in CAT_VARIANTS
            }

        frames: dict[str, dict[str, ImageTk.PhotoImage]] = {}
        for variant in CAT_VARIANTS:
            frames[variant] = {}
            for name in FRAME_NAMES:
                with Image.open(FRAME_ROOT / variant / f"{name}.png") as source:
                    width = max(1, round(source.width * size_percent / 100))
                    height = max(1, round(source.height * size_percent / 100))
                    resized = source.convert("RGBA").resize(
                        (width, height),
                        Image.Resampling.NEAREST,
                    )
                    frames[variant][name] = ImageTk.PhotoImage(
                        resized,
                        master=self.root,
                    )
        return frames

    def _start_tray(self) -> None:
        with Image.open(APP_ICON) as source:
            tray_image = source.convert("RGBA").copy()
        menu = pystray.Menu(
            pystray.MenuItem(
                "Settings…",
                lambda _icon, _item: self.events.put(
                    ("settings", time.monotonic())
                ),
                default=True,
            ),
            pystray.MenuItem(
                "Enabled",
                lambda _icon, _item: self.events.put(
                    ("toggle", time.monotonic())
                ),
                checked=lambda _item: self.settings.enabled,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Quit Cat Type",
                lambda _icon, _item: self.events.put(
                    ("quit", time.monotonic())
                ),
            ),
        )
        self._tray_icon = pystray.Icon(
            "cat-type",
            tray_image,
            "Cat Type",
            menu,
        )
        self._tray_thread = threading.Thread(
            target=self._tray_icon.run,
            name="system-tray",
            daemon=True,
        )
        self._tray_thread.start()

    def open_settings(self) -> None:
        if (
            self._settings_window is not None
            and self._settings_window.window.winfo_exists()
        ):
            self._settings_window.show()
            return
        self._settings_window = SettingsWindow(
            self.root,
            self.settings,
            self.apply_settings,
            str(APP_ICON) if APP_ICON.exists() else None,
        )

    def apply_settings(self, settings: AppSettings) -> None:
        previous_size = self.settings.size_percent
        self.settings = self.settings_store.save(settings)
        set_launch_at_startup(self.settings.launch_at_startup)
        self.animation.hide_after = self.settings.hold_seconds
        self.animation.fade_seconds = min(
            self.settings.fade_seconds,
            self.settings.hold_seconds,
        )
        if self.settings.size_percent != previous_size:
            self.frames = self._load_frames(self.settings.size_percent)
            self.frame_width = self.frames[CAT_VARIANTS[0]]["idle"].width()
            self.frame_height = self.frames[CAT_VARIANTS[0]]["idle"].height()
            self.label.configure(
                image=self.frames[self._active_variant]["idle"]
            )
            self._last_rendered_frame = None
        self._anchor_position = None
        if not self.settings.enabled:
            self._hide()
        if self._tray_icon is not None:
            self._tray_icon.update_menu()

    def _set_enabled(self, enabled: bool) -> None:
        updated = AppSettings(
            **{
                **self.settings.__dict__,
                "enabled": enabled,
            }
        )
        self.apply_settings(updated)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Show a tiny animated cat beside the active text caret."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print caret-provider errors to the terminal.",
    )
    parser.add_argument(
        "--hold-seconds",
        type=float,
        default=None,
        help="Temporarily override the saved display duration.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    set_per_monitor_dpi_awareness()
    if not acquire_single_instance():
        user32.MessageBoxW(
            None,
            "Cat Type is already running. Use its cat icon in the system tray "
            "to open Settings or quit.",
            "Cat Type",
            0x00000040,
        )
        return
    missing = [
        str(FRAME_ROOT / variant / f"{name}.png")
        for variant in CAT_VARIANTS
        for name in FRAME_NAMES
        if not (FRAME_ROOT / variant / f"{name}.png").exists()
    ]
    if missing:
        raise SystemExit(f"Missing sprite frames: {', '.join(missing)}")
    settings_store = SettingsStore()
    settings = settings_store.load()
    if args.hold_seconds is not None:
        settings = replace(
            settings,
            hold_seconds=max(0.25, args.hold_seconds),
        ).normalized()
    CatTypeApp(
        debug=args.debug,
        settings=settings,
        settings_store=settings_store,
    ).run()


if __name__ == "__main__":
    main()
