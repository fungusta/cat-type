"""Client-drawn Windows chrome, retaining the OS window manager contract.

Other window systems keep their native decoration: Tk has no portable API for
client decorations which preserves taskbar, resizing and compositor movement.
"""
from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from PIL import Image, ImageTk
from ui_surfaces import RoundedAction, BUTTON_ACCENT, BUTTON_INK, blend


TITLEBAR_BACKGROUND = '#FFF9F3'
WINDOW_EDGE = '#E2D9D0'


class TitleBarAction(RoundedAction):
    """A compact icon action with the existing keyboard and naming contract."""

    def __init__(self, parent, *, label, command, scale):
        self._button_width = round(36 * scale)
        self._button_height = round(30 * scale)
        self._scale = scale
        super().__init__(parent, text=label, command=command, takefocus=True)
        self._width, self._height = self._button_width, self._button_height
        tk.Canvas.configure(self, width=self._width, height=self._height)
        self.accessible_name = label
        self._draw()

    def set_label(self, label):
        self._text = label
        self.accessible_name = label
        self._draw()

    def _draw(self):
        self.delete('all')
        width, height = self._button_width, self._button_height
        scale = self._scale
        hover = self._hover.value
        if hover or self._focused or self._pressed:
            inset = max(1, round(scale))
            amount = 1.0 if self._focused or self._pressed else hover
            self.create_round_rect(inset, inset, width - inset, height - inset,
                radius=round(7 * scale), fill=blend(TITLEBAR_BACKGROUND, BUTTON_ACCENT, amount),
                outline=BUTTON_INK if self._focused else '',
                width=max(1, round(scale)))
        x, y = width / 2, height / 2
        d = 4.5 * scale
        stroke = max(1, round(1.25 * scale))
        opts = dict(fill=BUTTON_INK, width=stroke, tags='icon')
        if self._text == 'Minimize':
            self.create_line(x - d, y, x + d, y, **opts)
        elif self._text == 'Maximize':
            self.create_line(x - d, y - d, x + d, y - d, x + d, y + d,
                             x - d, y + d, x - d, y - d, **opts)
        elif self._text == 'Restore':
            self.create_line(x - d + 3 * scale, y - d + 2 * scale,
                             x - d + 3 * scale, y - d - scale,
                             x + d + scale, y - d - scale,
                             x + d + scale, y + d - 3 * scale,
                             x + d - 2 * scale, y + d - 3 * scale, **opts)
            self.create_line(x - d, y - d + 2 * scale, x + d - 2 * scale, y - d + 2 * scale,
                             x + d - 2 * scale, y + d, x - d, y + d,
                             x - d, y - d + 2 * scale, **opts)
        else:
            self.create_line(x - d, y - d, x + d, y + d, **opts)
            self.create_line(x + d, y - d, x - d, y + d, **opts)


class ThemedTitleBar(tk.Frame):
    def __init__(self, parent, *, on_minimize, on_toggle_maximize, on_close):
        super().__init__(parent, background=TITLEBAR_BACKGROUND)
        self._drag_origin = None
        self._maximized = False
        scale = max(1.0, float(self.tk.call('tk', 'scaling')) / (96 / 72))
        # Pack controls first: the title yields space before any action does.
        actions = tk.Frame(self, background=TITLEBAR_BACKGROUND)
        actions.pack(side='right', padx=round(8 * scale), pady=round(6 * scale))
        self.controls = []
        for label, callback in zip(('Minimize', 'Maximize', 'Close'),
                                   (on_minimize, on_toggle_maximize, on_close)):
            control = TitleBarAction(actions, label=label, command=callback, scale=scale)
            control.pack(side='left', padx=round(scale))
            self.controls.append(control)
        families = set(tkfont.families(self))
        family = next((name for name in ('Segoe UI Variable Text Semibold', 'Segoe UI Semibold')
                       if name in families), None)
        self.title = tk.Label(self, text='Cat Type Settings', anchor='w',
                              background=TITLEBAR_BACKGROUND, foreground=BUTTON_INK,
                              font=(family, 9) if family else ('TkDefaultFont', 9, 'bold'))
        try:
            with Image.open(Path(__file__).resolve().parent / 'assets' / 'cat-type.png') as mark:
                mark_size = round(22 * scale)
                self._mark = ImageTk.PhotoImage(mark.convert('RGBA').resize((mark_size, mark_size), Image.Resampling.LANCZOS), master=self)
            self.title.configure(image=self._mark, compound='left', padx=round(6 * scale))
        except OSError:
            pass  # Keep title and window commands usable in asset-light installs.
        self.title.pack(side='left', fill='both', expand=True, padx=round(8 * scale))
        for region in (self, self.title):
            region.bind('<ButtonPress-1>', self.drag_start)
            region.bind('<B1-Motion>', self.drag_move)
            region.bind('<ButtonRelease-1>', self.drag_end)
            region.bind('<Double-Button-1>', lambda e: on_toggle_maximize())

    def set_title(self, title):
        self.title.configure(text=title)

    def set_maximized(self, value):
        if self._maximized == bool(value):
            return
        self._maximized = bool(value)
        label = 'Restore' if value else 'Maximize'
        self.controls[1].set_label(label)

    def drag_start(self, event):
        window = self.winfo_toplevel()
        self._drag_origin = (event.x_root, event.y_root, window.winfo_x(), window.winfo_y())

    def drag_move(self, event):
        if self._drag_origin is not None:
            x, y, left, top = self._drag_origin
            self.winfo_toplevel().geometry(f'{left + event.x_root - x:+d}{top + event.y_root - y:+d}')

    def drag_end(self, _event=None):
        self._drag_origin = None


class NativeWindowChrome:
    """Subclass the native wrapper on the Tk thread and restore WM capabilities.

    The native style keeps WS_THICKFRAME, caption/system menu and taskbar identity.
    Only nonclient calculation/painting and edge hit-testing are customized.
    comctl32 forwards everything else to Tk, including close and DPI messages.
    """
    def __init__(self, window):
        self.window = window
        self.hwnd = None
        self._callback = None
        self.minimum_size = (1, 1)

    def install(self):
        if sys.platform != 'win32':
            return False
        if self.hwnd:
            return True
        self.window.overrideredirect(True)
        import ctypes as c
        from ctypes import wintypes as w
        self.user = c.WinDLL('user32', use_last_error=True)
        self.comctl = c.WinDLL('comctl32', use_last_error=True)
        pointer = c.c_ssize_t
        self.user.GetParent.argtypes = [w.HWND]
        self.user.GetParent.restype = w.HWND
        self.user.SendMessageW.argtypes = [w.HWND, w.UINT, c.c_size_t, pointer]
        self.user.SendMessageW.restype = pointer
        self.user.PostMessageW.argtypes = [w.HWND, w.UINT, c.c_size_t, pointer]
        self.user.PostMessageW.restype = w.BOOL
        self.user.GetWindowRect.argtypes = [w.HWND, c.POINTER(w.RECT)]
        self.user.IsZoomed.argtypes = self.user.IsIconic.argtypes = [w.HWND]
        self.user.ShowWindow.argtypes = [w.HWND, c.c_int]
        self.user.GetWindowLongW.argtypes = [w.HWND, c.c_int]
        self.user.SetWindowLongW.argtypes = [w.HWND, c.c_int, w.LONG]
        self.user.SetWindowPos.argtypes = [w.HWND, w.HWND, c.c_int, c.c_int, c.c_int, c.c_int, w.UINT]
        self.user.MonitorFromWindow.argtypes = [w.HWND, w.DWORD]
        self.user.MonitorFromWindow.restype = w.HANDLE
        self.user.GetMonitorInfoW.argtypes = [w.HANDLE, c.c_void_p]
        callback_type = c.WINFUNCTYPE(pointer, w.HWND, w.UINT, c.c_size_t, pointer, c.c_size_t, c.c_size_t)
        self.comctl.SetWindowSubclass.argtypes = [w.HWND, callback_type, c.c_size_t, c.c_size_t]
        self.comctl.DefSubclassProc.argtypes = [w.HWND, w.UINT, c.c_size_t, pointer]
        self.comctl.DefSubclassProc.restype = pointer
        self.comctl.RemoveWindowSubclass.argtypes = [w.HWND, callback_type, c.c_size_t]

        class MonitorInfo(c.Structure):
            _fields_ = [('size', w.DWORD), ('monitor', w.RECT), ('work', w.RECT), ('flags', w.DWORD)]

        class MinMaxInfo(c.Structure):
            _fields_ = [(name, w.POINT) for name in ('reserved', 'max_size', 'max_position', 'min_track', 'max_track')]

        def proc(hwnd, message, wp, lp, subclass_id, data):
            if message == 0x83:  # WM_NCCALCSIZE: whole rectangle is client content
                return 0
            if message == 0x84 and self.user.IsZoomed(hwnd):
                return 1
            if message == 0x84:
                rect = w.RECT()
                self.user.GetWindowRect(hwnd, c.byref(rect))
                x, y = c.c_short(lp & 0xffff).value, c.c_short((lp >> 16) & 0xffff).value
                dpi = 96
                if hasattr(self.user, 'GetDpiForWindow'):
                    self.user.GetDpiForWindow.argtypes = [w.HWND]
                    dpi = self.user.GetDpiForWindow(hwnd) or 96
                edge = max(6, round(7 * dpi / 96))
                left, right = x < rect.left + edge, x >= rect.right - edge
                top, bottom = y < rect.top + edge, y >= rect.bottom - edge
                if top: return 13 if left else 14 if right else 12
                if bottom: return 16 if left else 17 if right else 15
                if left: return 10
                if right: return 11
                return 1  # HTCLIENT: Tk title-bar controls retain pointer events
            if message == 0x24:  # WM_GETMINMAXINFO: maximize to monitor work area
                result = self.comctl.DefSubclassProc(hwnd, message, wp, lp)
                info = MonitorInfo(size=c.sizeof(MonitorInfo))
                if self.user.GetMonitorInfoW(self.user.MonitorFromWindow(hwnd, 2), c.byref(info)):
                    limits = c.cast(lp, c.POINTER(MinMaxInfo)).contents
                    limits.max_position.x = info.work.left - info.monitor.left
                    limits.max_position.y = info.work.top - info.monitor.top
                    limits.max_size.x = info.work.right - info.work.left
                    limits.max_size.y = info.work.bottom - info.work.top
                    limits.min_track.x, limits.min_track.y = self.minimum_size
                return result
            if message == 0x82:  # WM_NCDESTROY: remove before Tk disposes the HWND
                self.comctl.RemoveWindowSubclass(hwnd, self._callback, 1)
                self.hwnd = None
            return self.comctl.DefSubclassProc(hwnd, message, wp, lp)

        self._callback = callback_type(proc)
        hwnd = self.user.GetParent(self.window.winfo_id())
        if not hwnd or not self.comctl.SetWindowSubclass(hwnd, self._callback, 1, 0):
            return False
        self.hwnd = hwnd
        # Override-redirect gives Tk an accurate zero-inset geometry model.
        # Restore the native WM capabilities explicitly on its wrapper.
        self.user.SetWindowLongW(hwnd, -16,
            self.user.GetWindowLongW(hwnd, -16) | 0xCF0000)
        self.user.SetWindowLongW(hwnd, -20,
            (self.user.GetWindowLongW(hwnd, -20) | 0x40000) & ~0x80)
        self.user.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x27)
        self._apply_rounded_frame(hwnd)
        return True

    @staticmethod
    def _apply_rounded_frame(hwnd):
        """Ask Windows 11 DWM for rounded corners and a warm hairline edge.

        Earlier Windows versions reject these attributes; the square frame
        remains fully functional there.
        """
        import ctypes as c
        try:
            dwm = c.WinDLL('dwmapi')
        except OSError:
            return
        red, green, blue = (int(WINDOW_EDGE[i:i + 2], 16) for i in (1, 3, 5))
        for attribute, value in ((33, 2),  # DWMWA_WINDOW_CORNER_PREFERENCE: round
                                 (34, red | green << 8 | blue << 16)):  # DWMWA_BORDER_COLOR
            setting = c.c_uint(value)
            dwm.DwmSetWindowAttribute(c.c_void_p(hwnd), attribute,
                                      c.byref(setting), c.sizeof(setting))

    def minimize(self):
        if self.hwnd:
            self.user.ShowWindow(self.hwnd, 6)
        else:
            self.window.iconify()

    def toggle_maximize(self):
        if self.hwnd:
            self.user.ShowWindow(self.hwnd, 9 if self.is_maximized() else 3)
        else:
            self.window.state('normal' if self.window.state() == 'zoomed' else 'zoomed')

    def is_maximized(self):
        return bool(self.hwnd and self.user.IsZoomed(self.hwnd))

    def begin_drag(self, event):
        self._start_native_loop(2, event)  # HTCAPTION: native move/snap loop

    # Tk's own child windows cover the client area right up to its edges, so
    # the wrapper's WM_NCHITTEST never sees the pointer there. The settings
    # window asks resize_edge() from Tk events and starts the native loop.
    RESIZE_EDGE = 7
    RESIZE_CURSORS = {10: 'size_we', 11: 'size_we', 12: 'size_ns', 15: 'size_ns',
                      13: 'size_nw_se', 17: 'size_nw_se', 14: 'size_ne_sw', 16: 'size_ne_sw'}

    def resize_edge(self, x_root, y_root):
        """Return the native hit-test code for a point on the resize border."""
        if not self.hwnd or self.is_maximized():
            return None
        window = self.window
        left, top = window.winfo_rootx(), window.winfo_rooty()
        right, bottom = left + window.winfo_width(), top + window.winfo_height()
        scale = float(window.tk.call('tk', 'scaling')) * 72 / 96
        edge = max(5, round(self.RESIZE_EDGE * scale))
        near_left, near_right = x_root < left + edge, x_root >= right - edge
        near_top, near_bottom = y_root < top + edge, y_root >= bottom - edge
        if not (near_left or near_right or near_top or near_bottom):
            return None
        # A corner also catches the pointer a little way along either side.
        corner = edge * 3
        on_left, on_right = x_root < left + corner, x_root >= right - corner
        on_top, on_bottom = y_root < top + corner, y_root >= bottom - corner
        if (near_top and on_left) or (near_left and on_top):
            return 13  # HTTOPLEFT
        if (near_top and on_right) or (near_right and on_top):
            return 14  # HTTOPRIGHT
        if (near_bottom and on_left) or (near_left and on_bottom):
            return 16  # HTBOTTOMLEFT
        if (near_bottom and on_right) or (near_right and on_bottom):
            return 17  # HTBOTTOMRIGHT
        return 12 if near_top else 15 if near_bottom else 10 if near_left else 11

    def begin_resize(self, hit, event):
        self._start_native_loop(hit, event)

    def _start_native_loop(self, hit, event):
        if not self.hwnd:
            return
        self.user.ReleaseCapture()
        point = ((event.y_root & 0xffff) << 16) | (event.x_root & 0xffff)
        # Posted, not sent: the modal move/size loop must start from Tk's own
        # message pump. Entered from inside a Python callback, any Tk callback
        # the loop dispatches finds no Python thread state and aborts.
        self.user.PostMessageW(self.hwnd, 0xA1, hit, point)  # WM_NCLBUTTONDOWN
