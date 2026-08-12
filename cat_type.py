from __future__ import annotations

import argparse
import ctypes
import os
import platform as runtime_platform
import queue
import sys
import tempfile
import threading
import time
import tkinter as tk
from collections import deque
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from tkinter import messagebox
from typing import Callable, Literal
from ctypes import wintypes

from PIL import Image, ImageTk

from auto_update import (
    AvailableUpdate,
    InstallerAvailability,
    UpdateEvent,
    UpdateService,
    UpdateStateStore,
)
from cat_settings import AppSettings, SettingsStore, set_launch_at_startup
from platform_assets import icon_filename
from settings_window import SettingsWindow


IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")


APP_DIR = Path(
    getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
)
FRAME_ROOT = APP_DIR / "assets" / "tabby-frames"
APP_ICON = APP_DIR / "assets" / icon_filename(sys.platform)
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
LLKHF_EXTENDED = 0x01

PawAction = Literal["left", "right", "both", "alternate"]

LEFT_WINDOWS_KEYS = frozenset(
    {
        0x1B,
        0x09,
        0x14,
        0x5B,
        0xA0,
        0xA2,
        0xA4,
        0xC0,
        *map(ord, "12345QWERTASDFGZXCVB"),
    }
)
RIGHT_WINDOWS_KEYS = frozenset(
    {
        0x08,
        0x0D,
        0x5C,
        0x5D,
        0x90,
        0xA1,
        0xA3,
        0xA5,
        0xBA,
        0xBB,
        0xBD,
        0xBF,
        0xDB,
        0xDC,
        0xDD,
        0xDE,
        0xE2,
        *range(0x21, 0x2F),
        *range(0x60, 0x70),
        *map(ord, "67890YUIOPHJKLNM"),
    }
)
LEFT_PORTABLE_CHARACTERS = frozenset("`~12345!@#$%qwertasdfgzxcvb")
RIGHT_PORTABLE_CHARACTERS = frozenset(
    "67890-=_+^&*()yuiop[]{}\\|hjkl:;'\"nm,./<>?"
)
MACOS_KEYPAD_VKS = frozenset(
    {
        0x41,
        0x43,
        0x45,
        0x47,
        0x4B,
        0x4C,
        0x4E,
        0x51,
        *range(0x52, 0x5A),
        0x5B,
        0x5C,
    }
)
LEFT_PORTABLE_KEYS = frozenset(
    {
        "esc",
        "tab",
        "caps_lock",
        "shift",
        "shift_l",
        "ctrl",
        "ctrl_l",
        "alt",
        "alt_l",
        "cmd",
        "cmd_l",
    }
)
RIGHT_PORTABLE_KEYS = frozenset(
    {
        "backspace",
        "enter",
        "shift_r",
        "ctrl_r",
        "alt_r",
        "alt_gr",
        "cmd_r",
        "insert",
        "delete",
        "home",
        "end",
        "page_up",
        "page_down",
        "left",
        "right",
        "up",
        "down",
        "num_lock",
    }
)

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


if IS_WINDOWS:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
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
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowRect.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.RECT),
    ]
    user32.GetWindowRect.restype = wintypes.BOOL
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
else:
    user32 = None
    kernel32 = None
    HOOKPROC = Callable[..., int]

_instance_mutex: int | None = None
_instance_lock: object | None = None


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
    fallback_allowed: bool = False


def set_per_monitor_dpi_awareness() -> None:
    """Keep caret and overlay coordinates in the same physical pixel space."""
    if not IS_WINDOWS:
        return
    assert user32 is not None
    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        try:
            user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def acquire_single_instance() -> bool:
    global _instance_lock, _instance_mutex
    if IS_WINDOWS:
        assert kernel32 is not None
        _instance_mutex = kernel32.CreateMutexW(
            None,
            False,
            "Local\\CatTypeDesktopApp",
        )
        return bool(_instance_mutex) and ctypes.get_last_error() != 183

    import fcntl

    lock_path = Path(tempfile.gettempdir()) / f"cat-type-{os.getuid()}.lock"
    _instance_lock = lock_path.open("w")
    try:
        fcntl.flock(_instance_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        _instance_lock.close()
        _instance_lock = None
        return False
    return True


def work_area_for(rect: ScreenRect) -> ScreenRect:
    if not IS_WINDOWS:
        root = tk._default_root
        if root is not None:
            left = root.winfo_vrootx()
            top = root.winfo_vrooty()
            return ScreenRect(
                left,
                top,
                left + root.winfo_vrootwidth(),
                top + root.winfo_vrootheight(),
            )
        return ScreenRect(0, 0, 1920, 1080)

    assert user32 is not None
    point = wintypes.POINT(rect.left, rect.top)
    monitor = user32.MonitorFromPoint(point, MONITOR_DEFAULTTONEAREST)
    info = MONITORINFO(cbSize=ctypes.sizeof(MONITORINFO))
    if monitor and user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        work = info.rcWork
        return ScreenRect(work.left, work.top, work.right, work.bottom)
    return ScreenRect(0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))


def active_work_area() -> ScreenRect:
    """Return the work area containing the currently focused application."""
    if IS_WINDOWS:
        assert user32 is not None
        hwnd = user32.GetForegroundWindow()
        rect = wintypes.RECT()
        if hwnd and user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return work_area_for(
                ScreenRect(rect.left, rect.top, rect.right, rect.bottom)
            )
    return work_area_for(ScreenRect(0, 0, 1, 1))


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


def choose_fallback_position(
    overlay_width: int,
    overlay_height: int,
    work_area: ScreenRect,
    gap: int = 6,
    placement: str = "above-right",
) -> tuple[int, int]:
    """Place the overlay in the preferred corner when no caret is available."""
    prefer_left = placement.endswith("left")
    prefer_below = placement.startswith("below")
    x = (
        work_area.left + gap
        if prefer_left
        else work_area.right - overlay_width - gap
    )
    y = (
        work_area.bottom - overlay_height - gap
        if prefer_below
        else work_area.top + gap
    )
    return x, y


def make_window_non_interactive(hwnd: int) -> None:
    """Keep the overlay topmost without taking focus or pointer input."""
    if not IS_WINDOWS:
        return
    assert user32 is not None
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


@dataclass(frozen=True)
class AppEvent:
    kind: str
    happened_at: float
    paw: PawAction | None = None


class _PortableKeypadKey:
    __slots__ = ()
    _cat_type_keypad = True


_XORG_KEYPAD_KEY = _PortableKeypadKey()


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
    if getattr(key, "_cat_type_keypad", False):
        return "right"
    if IS_MACOS and getattr(key, "vk", None) in MACOS_KEYPAD_VKS:
        return "right"

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

    def show_startup(self, now: float) -> None:
        self.last_key_at = now
        self._tap_count = 0
        self._paw = "left"
        self._recent.clear()

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
        if now - self.last_key_at > 0.16:
            return "idle"
        if (
            self._paw == "both"
            or len(self._recent) >= 5
            and self._recent[-1] - self._recent[-5] < 0.34
        ):
            return "excited"
        return "tap-left" if self._paw == "left" else "tap-right"


class KeyboardMonitor:
    """Signals activity only. It never turns virtual-key codes into text."""

    def __init__(self, event_queue: queue.SimpleQueue[AppEvent]) -> None:
        self.event_queue = event_queue
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._hook = None
        self._callback = None
        self._listener = None
        self._ctrl_down = False
        self._alt_down = False

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run, name="keyboard-activity", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        if IS_WINDOWS and self._thread_id:
            assert user32 is not None
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._listener is not None:
            self._listener.stop()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

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

    @staticmethod
    def _portable_listener_type(listener_type: type) -> type:
        backend_module = sys.modules.get(listener_type.__module__)
        keypad_keys = getattr(backend_module, "KEYPAD_KEYS", None)
        if (
            not IS_LINUX
            or listener_type.__module__ != "pynput.keyboard._xorg"
            or not isinstance(keypad_keys, dict)
            or not callable(getattr(listener_type, "_keycode_to_keysym", None))
        ):
            return listener_type

        try:
            keypad_keysyms = frozenset(keypad_keys.values())
        except (AttributeError, TypeError):
            return listener_type
        if not keypad_keysyms or not all(
            isinstance(keysym, int) for keysym in keypad_keysyms
        ):
            return listener_type

        class XorgKeypadListener(listener_type):
            def _event_to_key(self, display: object, event: object) -> object:
                try:
                    keysyms = (
                        self._keycode_to_keysym(display, event.detail, index)
                        for index in range(4)
                    )
                    is_keypad = any(
                        keysym in keypad_keysyms for keysym in keysyms
                    )
                except Exception:
                    # pynput exposes no public Xorg hook before translating
                    # keypad keysyms. If its private internals change, retain
                    # the normal event rather than failing input monitoring.
                    is_keypad = False

                return (
                    _XORG_KEYPAD_KEY
                    if is_keypad
                    else super()._event_to_key(display, event)
                )

        return XorgKeypadListener

    def _run(self) -> None:
        if not IS_WINDOWS:
            self._run_portable()
            return

        assert kernel32 is not None and user32 is not None
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
            self.event_queue.put(AppEvent("hook-error", time.monotonic()))
            return

        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))

        user32.UnhookWindowsHookEx(self._hook)
        self._hook = None

    def _run_portable(self) -> None:
        try:
            from pynput import keyboard

            ctrl_keys = {keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r}
            alt_keys = {
                keyboard.Key.alt,
                keyboard.Key.alt_l,
                keyboard.Key.alt_r,
                keyboard.Key.alt_gr,
            }

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

            def on_release(key: object, *_injected: object) -> None:
                if key in ctrl_keys:
                    self._ctrl_down = False
                elif key in alt_keys:
                    self._alt_down = False

            listener_type = self._portable_listener_type(keyboard.Listener)
            self._listener = listener_type(
                on_press=on_press,
                on_release=on_release,
            )
            self._listener.run()
        except Exception as exc:
            if os.environ.get("CAT_TYPE_DEBUG"):
                print(f"Keyboard listener unavailable: {exc}", file=sys.stderr)
            self.event_queue.put(AppEvent("hook-error", time.monotonic()))


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
        if not IS_WINDOWS:
            # Accessibility APIs differ considerably between desktop
            # environments. Until a provider returns a usable caret rectangle,
            # anchor the companion at the pointer so typing feedback remains
            # available everywhere.
            try:
                from pynput.mouse import Controller

                left, top = Controller().position
                return CaretSnapshot(
                    now,
                    ScreenRect(round(left), round(top), round(left) + 2, round(top) + 20),
                    False,
                    "pointer-fallback",
                )
            except Exception as exc:
                if self.debug:
                    print(f"Pointer lookup failed: {exc}", file=sys.stderr)
                return CaretSnapshot(now, None)

        uia_rect, is_password, fallback_allowed = self._locate_with_uia()
        if is_password:
            return CaretSnapshot(now, None, True, "uia-password")
        if uia_rect:
            return CaretSnapshot(now, uia_rect, False, "uia")

        win32_rect = self._locate_with_win32()
        if win32_rect:
            return CaretSnapshot(now, win32_rect, False, "win32")
        if fallback_allowed:
            return CaretSnapshot(
                now,
                None,
                False,
                "uia-fallback",
                fallback_allowed=True,
            )
        return CaretSnapshot(now, None)

    def _locate_with_win32(self) -> ScreenRect | None:
        assert user32 is not None
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

    def _locate_with_uia(self) -> tuple[ScreenRect | None, bool, bool]:
        if self._automation is None or self._uia is None:
            return None, False, False

        try:
            element = self._automation.GetFocusedElement()
            if not element:
                return None, False, False
            if bool(element.CurrentIsPassword):
                return None, True, False

            has_text_pattern = False
            unknown = element.GetCurrentPattern(self._uia.UIA_TextPattern2Id)
            if unknown:
                has_text_pattern = True
                pattern = unknown.QueryInterface(
                    self._uia.IUIAutomationTextPattern2
                )
                is_active, text_range = pattern.GetCaretRange()
                if is_active and text_range:
                    rect = self._rect_from_uia_range(text_range)
                    if rect:
                        return rect, False, True

            # Older providers often expose TextPattern but not TextPattern2.
            unknown = element.GetCurrentPattern(self._uia.UIA_TextPatternId)
            if unknown:
                has_text_pattern = True
                pattern = unknown.QueryInterface(
                    self._uia.IUIAutomationTextPattern
                )
                ranges = pattern.GetSelection()
                if ranges and ranges.Length:
                    rect = self._rect_from_uia_range(ranges.GetElement(0))
                    if rect:
                        return rect, False, True
        except Exception as exc:
            if self.debug:
                print(f"UI Automation lookup failed: {exc}", file=sys.stderr)
            return None, False, False
        return None, False, has_text_pattern

    @staticmethod
    def _rect_from_uia_range(text_range: object) -> ScreenRect | None:
        values = text_range.GetBoundingRectangles()
        coords = tuple(values) if values is not None else ()
        used_character_probe = False
        use_trailing_edge = False

        def has_usable_rectangle(rectangles: tuple) -> bool:
            if len(rectangles) < 4:
                return False
            _, _, width, height = rectangles[-4:]
            return width >= 0 and height > 0

        # UI Automation permits a provider to return no rectangles for a
        # degenerate (zero-length) caret range. Terminals commonly do this.
        # Temporarily include the next character to obtain the caret cell's
        # geometry. If the next character is absent or invisible, include the
        # previous character and use its trailing edge instead.
        if not has_usable_rectangle(coords):
            probe = text_range.Clone()
            moved = probe.MoveEndpointByUnit(
                TEXT_PATTERN_RANGE_ENDPOINT_END,
                TEXT_UNIT_CHARACTER,
                1,
            )
            if moved:
                values = probe.GetBoundingRectangles()
                coords = tuple(values) if values is not None else ()
                used_character_probe = True

            if not has_usable_rectangle(coords):
                probe = text_range.Clone()
                moved = probe.MoveEndpointByUnit(
                    TEXT_PATTERN_RANGE_ENDPOINT_START,
                    TEXT_UNIT_CHARACTER,
                    -1,
                )
                if moved:
                    values = probe.GetBoundingRectangles()
                    coords = tuple(values) if values is not None else ()
                    used_character_probe = True
                    use_trailing_edge = has_usable_rectangle(coords)

        if not has_usable_rectangle(coords):
            return None

        # Use the final rectangle for a collapsed selection/caret at line end.
        left, top, width, height = coords[-4:]
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
        comtypes_module = None
        if IS_WINDOWS:
            import comtypes

            comtypes_module = comtypes
            comtypes_module.CoInitialize()
        try:
            if IS_WINDOWS:
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
            if comtypes_module is not None:
                comtypes_module.CoUninitialize()

    def _poll_interval(self) -> float:
        with self._activity_lock:
            active = time.monotonic() < self._active_until
        return 0.025 if active else 0.25


class _DaemonUpdateRunner:
    """Serialize update jobs on one lazily started daemon thread."""

    def __init__(self) -> None:
        self._jobs: queue.SimpleQueue[
            tuple[Callable[[], None], str]
        ] = queue.SimpleQueue()
        self._start_lock = threading.Lock()
        self._worker: threading.Thread | None = None

    def __call__(
        self,
        target: Callable[[], None],
        name: str,
    ) -> threading.Thread:
        self._jobs.put((target, name))
        with self._start_lock:
            if self._worker is None:
                self._worker = threading.Thread(
                    target=self._run,
                    name="cat-type-updates",
                    daemon=True,
                )
                self._worker.start()
        return self._worker

    def _run(self) -> None:
        while True:
            target, name = self._jobs.get()
            assert self._worker is not None
            self._worker.name = name
            target()


class _UnavailableUpdateInstaller:
    """Narrow placeholder replaced by platform installers in later tasks."""

    RELEASES_URL = "https://github.com/fungusta/cat-type/releases/latest"

    def __init__(self, platform_name: str, frozen: bool | None) -> None:
        is_frozen = (
            bool(getattr(sys, "frozen", False)) if frozen is None else frozen
        )
        if platform_name == "darwin":
            status = (
                "macOS updates are manual. Download the latest DMG: "
                f"{self.RELEASES_URL}"
            )
        elif not is_frozen:
            status = (
                "Source checkouts cannot update themselves. "
                "Download a packaged Windows or Linux release: "
                f"{self.RELEASES_URL}"
            )
        else:
            status = (
                "Automatic installation is unavailable in this build. "
                f"Download the latest release: {self.RELEASES_URL}"
            )
        self._availability = InstallerAvailability(False, status)

    def availability(self) -> InstallerAvailability:
        return self._availability

    def prepare(self, package: Path, update: AvailableUpdate) -> object:
        del package, update
        raise RuntimeError("automatic installation is unavailable")

    def start(self, prepared: object) -> None:
        del prepared
        raise RuntimeError("automatic installation is unavailable")


class CatTypeApp:
    TRANSPARENT_COLOR = "#00ff01"

    def __init__(
        self,
        debug: bool = False,
        hold_seconds: float = 1.5,
        fade_seconds: float = 0.35,
        settings: AppSettings | None = None,
        settings_store: SettingsStore | None = None,
        update_service: object | None = None,
        update_state: object | None = None,
        update_installer: object | None = None,
        thread_runner: Callable[[Callable[[], None], str], object] | None = None,
        confirm_update: Callable[[AvailableUpdate], bool] | None = None,
        platform_name: str = sys.platform,
        machine: str | None = None,
        frozen: bool | None = None,
        now: Callable[[], datetime] | None = None,
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
        self.events: queue.SimpleQueue[AppEvent] = queue.SimpleQueue()
        self.keystroke_count = 0
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
        self._x_display = None
        self._shutting_down = False
        self._update_status = "Ready to check for updates."
        self._initialize_update_controller(
            update_service=(
                UpdateService() if update_service is None else update_service
            ),
            update_state=(
                UpdateStateStore() if update_state is None else update_state
            ),
            update_installer=(
                _UnavailableUpdateInstaller(platform_name, frozen)
                if update_installer is None
                else update_installer
            ),
            thread_runner=(
                _DaemonUpdateRunner() if thread_runner is None else thread_runner
            ),
            confirm_update=(
                self._confirm_available_update
                if confirm_update is None
                else confirm_update
            ),
            platform_name=platform_name,
            machine=machine or runtime_platform.machine(),
            frozen=bool(getattr(sys, "frozen", False)) if frozen is None else frozen,
            now=now or (lambda: datetime.now(timezone.utc)),
        )

        self.root = tk.Tk()
        self.root.title("Cat Type")
        if APP_ICON.exists():
            try:
                self.root.iconbitmap(default=str(APP_ICON))
            except tk.TclError:
                pass
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        self._window_background = (
            "systemTransparent" if IS_MACOS else self.TRANSPARENT_COLOR
        )
        self.root.configure(background=self._window_background)
        if IS_WINDOWS:
            self.root.wm_attributes("-transparentcolor", self.TRANSPARENT_COLOR)
        elif IS_MACOS:
            self.root.wm_attributes("-transparent", True)
        else:
            try:
                self.root.wm_attributes("-type", "splash")
            except tk.TclError:
                pass

        self.frames = self._load_frames(self.settings.size_percent)
        self.frame_width = self.frames[CAT_VARIANTS[0]]["idle"].width()
        self.frame_height = self.frames[CAT_VARIANTS[0]]["idle"].height()
        self.label = tk.Label(
            self.root,
            image=self.frames[CAT_VARIANTS[0]]["idle"],
            borderwidth=0,
            highlightthickness=0,
            background=self._window_background,
        )
        self.label.pack()
        self.root.update_idletasks()
        self._make_overlay_non_interactive()
        self.root.withdraw()
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)

    def _initialize_update_controller(
        self,
        *,
        update_service: object,
        update_state: object,
        update_installer: object,
        thread_runner: Callable[[Callable[[], None], str], object],
        confirm_update: Callable[[AvailableUpdate], bool],
        platform_name: str,
        machine: str,
        frozen: bool,
        now: Callable[[], datetime],
    ) -> None:
        self.update_events: queue.SimpleQueue[UpdateEvent] = queue.SimpleQueue()
        self._update_service = update_service
        self._update_state = update_state
        self._update_installer = update_installer
        self._update_thread_runner = thread_runner
        self._confirm_update = confirm_update
        self._platform_name = platform_name
        self._machine = machine
        self._frozen = frozen
        self._update_now = now
        self._update_worker: object | None = None
        self._update_worker_active = False

    def check_for_updates(self, manual: bool = False) -> None:
        if self._shutting_down or self._update_worker_active:
            return
        if not manual:
            if not (
                self._platform_name == "win32"
                or self._platform_name.startswith("linux")
            ):
                return

        self._set_update_status("Checking for updates…", checking=True)
        self._update_worker_active = True

        def check_worker() -> None:
            try:
                if not manual and not self._update_state.is_due(
                    self._update_now()
                ):
                    self.update_events.put(UpdateEvent("not-due"))
                    return
                availability = self._update_installer.availability()
                if not availability.can_install:
                    self.update_events.put(
                        UpdateEvent("unavailable", message=availability.status)
                    )
                    return
                update = self._update_service.check(
                    self._platform_name,
                    self._machine,
                )
                checked_at = self._update_now()
                self._update_state.record_success(checked_at)
                self.update_events.put(UpdateEvent("check-result", update=update))
            except Exception as error:
                self.update_events.put(UpdateEvent("error", message=str(error)))

        self._update_worker = self._update_thread_runner(
            check_worker,
            "update-check",
        )

    def _confirm_available_update(self, update: AvailableUpdate) -> bool:
        return messagebox.askyesno(
            "Cat Type update",
            f"Cat Type {update.version} is available. Download and install it now?",
            parent=self.root,
        )

    def _set_update_status(self, text: str, checking: bool = False) -> None:
        self._update_status = text
        if (
            self._settings_window is not None
            and self._settings_window.window.winfo_exists()
        ):
            self._settings_window.set_update_status(text, checking=checking)

    def _drain_update_events(self) -> None:
        while True:
            try:
                event = self.update_events.get_nowait()
            except queue.Empty:
                return
            self._handle_update_event(event)

    def _handle_update_event(self, event: UpdateEvent) -> None:
        if event.kind == "progress":
            percent = round(event.received * 100 / event.total) if event.total else 0
            self._set_update_status(f"Downloading update… {percent}%", checking=True)
            return
        if event.kind == "stage":
            self._set_update_status(event.message, checking=True)
            return

        self._update_worker_active = False
        self._update_worker = None
        if self._shutting_down:
            return
        if event.kind == "not-due":
            self._set_update_status("Ready to check for updates.")
            return
        if event.kind == "unavailable":
            self._set_update_status(event.message)
            return
        if event.kind == "error":
            detail = event.message or "Unknown update error"
            self._set_update_status(f"Update failed: {detail}")
            return
        if event.kind == "install-started":
            self._set_update_status(event.message)
            return
        if event.kind != "check-result":
            return
        if event.update is None:
            self._set_update_status("Cat Type is up to date.")
            return

        update = event.update
        self._set_update_status(f"Cat Type {update.version} is available.")
        if not self._confirm_update(update):
            self._set_update_status("Update cancelled.")
            return
        self._start_update_install(update)

    def _start_update_install(self, update: AvailableUpdate) -> None:
        if self._shutting_down or self._update_worker_active:
            return
        self._update_worker_active = True
        self._set_update_status("Downloading update… 0%", checking=True)

        def progress(received: int, total: int) -> None:
            self.update_events.put(
                UpdateEvent("progress", received=received, total=total)
            )

        def install_worker() -> None:
            try:
                package = self._update_service.download_verified(
                    update,
                    progress=progress,
                )
                if self._shutting_down:
                    return
                self.update_events.put(
                    UpdateEvent(
                        "stage",
                        message=f"Verifying Cat Type {update.version}…",
                    )
                )
                prepared = self._update_installer.prepare(package, update)
                if self._shutting_down:
                    return
                self.update_events.put(
                    UpdateEvent(
                        "stage",
                        message=f"Installing Cat Type {update.version}…",
                    )
                )
                self._update_installer.start(prepared)
                if not self._shutting_down:
                    self.update_events.put(
                        UpdateEvent(
                            "install-started",
                            message=f"Installing Cat Type {update.version}…",
                        )
                    )
            except Exception as error:
                self.update_events.put(UpdateEvent("error", message=str(error)))

        self._update_worker = self._update_thread_runner(
            install_worker,
            "update-install",
        )

    def run(self) -> None:
        self._start_tray()
        self.keyboard.start()
        self.tracker.start()
        # Give immediate visual confirmation when the app starts while a text
        # field is already focused.
        started_at = time.monotonic()
        self.animation.show_startup(started_at)
        self.tracker.notify_activity(started_at)
        self.root.after(16, self._tick)
        platform_name = getattr(self, "_platform_name", sys.platform)
        if platform_name == "win32" or platform_name.startswith(
            "linux"
        ):
            self.root.after(2000, self.check_for_updates)
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

        self._drain_update_events()

        should_quit = False
        while True:
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

        if should_quit:
            self.shutdown()
            return
        if self._hook_failed:
            self._hook_failed = False
            print(
                "Could not install the keyboard activity listener. "
                "Check the operating system's input-monitoring permissions.",
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
            and (snapshot.rect is not None or snapshot.fallback_allowed)
            and not snapshot.is_password
        ):
            self._show(snapshot, now)
        else:
            reset_anchor = (
                not self.animation.is_visible(now) or snapshot.is_password
            )
            self._hide(reset_anchor=reset_anchor)

        self.root.after(16, self._tick)

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

    def _show(self, snapshot: CaretSnapshot, now: float) -> None:
        assert snapshot.rect is not None or snapshot.fallback_allowed
        self.root.wm_attributes("-alpha", self.animation.opacity(now))
        frame_name = self.animation.frame_name(now)

        if self._anchor_position is None:
            if snapshot.rect is not None:
                area = work_area_for(snapshot.rect)
                self._anchor_position = choose_overlay_position(
                    snapshot.rect,
                    self.frame_width,
                    self.frame_height,
                    area,
                    placement=self.settings.placement,
                )
            else:
                self._anchor_position = choose_fallback_position(
                    self.frame_width,
                    self.frame_height,
                    active_work_area(),
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
            self._shape_linux_overlay(self._active_variant, frame_name)
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
        if IS_LINUX:
            self._shape_linux_overlay(self._active_variant, "idle")

    def _shape_linux_overlay(self, variant: str, frame_name: str) -> None:
        """Use X Shape for a transparent, click-through overlay on X11."""
        if not IS_LINUX:
            return
        try:
            from Xlib import X, display
            from Xlib.ext import shape

            if self._x_display is None:
                self._x_display = display.Display()
            window = self._x_display.create_resource_object(
                "window",
                self.root.winfo_id(),
            )
            with Image.open(
                FRAME_ROOT / variant / f"{frame_name}.png"
            ) as source:
                alpha = source.convert("RGBA").getchannel("A")
                if self.settings.size_percent != 100:
                    alpha = alpha.resize(
                        (self.frame_width, self.frame_height),
                        Image.Resampling.NEAREST,
                    )
                rectangles = []
                pixels = alpha.load()
                for y in range(alpha.height):
                    start = None
                    for x in range(alpha.width + 1):
                        opaque = x < alpha.width and pixels[x, y] > 0
                        if opaque and start is None:
                            start = x
                        elif not opaque and start is not None:
                            rectangles.append((start, y, x - start, 1))
                            start = None

            window.shape_rectangles(
                shape.SO.Set,
                shape.SK.Bounding,
                X.YXBanded,
                0,
                0,
                rectangles,
            )
            window.shape_rectangles(
                shape.SO.Set,
                shape.SK.Input,
                X.YXBanded,
                0,
                0,
                [],
            )
            self._x_display.sync()
        except Exception as exc:
            if self.debug:
                print(f"X11 window shaping unavailable: {exc}", file=sys.stderr)

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
        import pystray

        with Image.open(APP_ICON) as source:
            tray_image = source.convert("RGBA").copy()
        menu = pystray.Menu(
            pystray.MenuItem(
                "Settings…",
                lambda _icon, _item: self.events.put(
                    AppEvent("settings", time.monotonic())
                ),
                default=True,
            ),
            pystray.MenuItem(
                "Enabled",
                lambda _icon, _item: self.events.put(
                    AppEvent("toggle", time.monotonic())
                ),
                checked=lambda _item: self.settings.enabled,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Quit Cat Type",
                lambda _icon, _item: self.events.put(
                    AppEvent("quit", time.monotonic())
                ),
            ),
        )
        self._tray_icon = pystray.Icon(
            "cat-type",
            tray_image,
            "Cat Type",
            menu,
        )
        if IS_MACOS:
            self._tray_icon.run_detached()
            return
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
            keystroke_count=self.keystroke_count,
            on_check_for_updates=lambda: self.check_for_updates(manual=True),
            update_status=getattr(
                self,
                "_update_status",
                "Ready to check for updates.",
            ),
        )
        if getattr(self, "_update_worker_active", False):
            self._settings_window.set_update_status(
                self._update_status,
                checking=True,
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
        message = (
            "Cat Type is already running. Use its cat icon in the system tray "
            "to open Settings or quit."
        )
        if IS_WINDOWS:
            assert user32 is not None
            user32.MessageBoxW(None, message, "Cat Type", 0x00000040)
        else:
            from tkinter import messagebox

            duplicate_root = tk.Tk()
            duplicate_root.withdraw()
            messagebox.showinfo("Cat Type", message, parent=duplicate_root)
            duplicate_root.destroy()
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
