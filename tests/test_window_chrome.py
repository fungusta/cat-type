import sys
import tkinter as tk
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from window_chrome import ThemedTitleBar, NativeWindowChrome


class TitleBarTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.geometry('460x220+40+40')
        self.calls = []
        self.bar = ThemedTitleBar(self.root, on_minimize=lambda: self.calls.append('min'),
            on_toggle_maximize=lambda: self.calls.append('max'), on_close=lambda: self.calls.append('close'))
        self.bar.pack(fill='x')
        self.root.update()

    def tearDown(self):
        self.root.destroy()

    def test_labels_callbacks_and_focus(self):
        self.assertEqual(self.bar.title.cget('text'), 'Cat Type Settings')
        for control, label in zip(self.bar.controls, ('Minimize', 'Maximize', 'Close')):
            self.assertEqual(control.cget('text'), label)
            self.assertEqual(str(control.cget('takefocus')), '1')
            control.invoke()
        self.assertEqual(self.calls, ['min', 'max', 'close'])
        self.bar.set_maximized(True)
        self.assertEqual(self.bar.controls[1].cget('text'), 'Restore')
        self.bar.set_title('Another title')
        self.assertEqual(self.bar.title.cget('text'), 'Another title')

    def test_compact_icon_controls_blend_with_title_bar(self):
        self.assertEqual(self.bar.cget('background').lower(), '#fff9f3')
        scale = max(1.0, float(self.root.tk.call('tk', 'scaling')) / (96 / 72))
        for control in self.bar.controls:
            self.assertLess(control.winfo_width(), 48 * scale)
            self.assertFalse(any(control.type(item) == 'text' for item in control.find_all()))
            self.assertEqual(control.cget('accessible_name'), control.cget('text'))

    def test_icon_control_hover_focus_and_restore(self):
        control = self.bar.controls[1]
        control.event_generate('<Enter>')
        self.root.update()
        self.assertIn('#f2d66b', [control.itemcget(item, 'fill').lower()
                                 for item in control.find_all() if control.type(item) != 'image'])
        control.event_generate('<Leave>')
        control.event_generate('<FocusIn>')
        self.root.update()
        self.assertIn('#f2d66b', [control.itemcget(item, 'fill').lower()
                                 for item in control.find_all() if control.type(item) != 'image'])
        normal_icon = [control.coords(item) for item in control.find_withtag('icon')]
        self.bar.set_maximized(True)
        self.assertEqual(control.cget('accessible_name'), 'Restore')
        self.assertNotEqual(normal_icon, [control.coords(item) for item in control.find_withtag('icon')])

    def test_icon_controls_activate_from_keyboard(self):
        self.root.focus_force()
        for control, key in zip(self.bar.controls, ('space', 'Return', 'space')):
            control.focus_force()
            self.root.update()
            control.event_generate(f'<KeyPress-{key}>')
            self.root.update()
        self.assertEqual(self.calls, ['min', 'max', 'close'])

    def test_drag_delta(self):
        window = Mock()
        window.winfo_x.return_value = 80
        window.winfo_y.return_value = 100
        with patch.object(self.bar, "winfo_toplevel", return_value=window):
            self.bar.drag_start(SimpleNamespace(x_root=150, y_root=120))
            self.bar.drag_move(SimpleNamespace(x_root=190, y_root=110))
            window.geometry.assert_called_once_with("+120+90")
            self.bar.drag_end()
            self.bar.drag_move(SimpleNamespace(x_root=200, y_root=140))
            window.geometry.assert_called_once()

    def test_narrow_controls_remain_visible(self):
        self.root.geometry('340x220')
        self.root.update()
        for control in self.bar.controls:
            self.assertTrue(control.winfo_viewable())
            self.assertLessEqual(control.winfo_rootx() + control.winfo_width(), self.root.winfo_rootx() + self.root.winfo_width())

    def test_high_scaling_narrow_controls_remain_visible(self):
        original = float(self.root.tk.call('tk', 'scaling'))
        self.root.tk.call('tk', 'scaling', 2.5)
        self.bar.destroy()
        self.bar = ThemedTitleBar(self.root, on_minimize=lambda: None,
            on_toggle_maximize=lambda: None, on_close=lambda: None)
        self.bar.pack(fill='x')
        self.root.geometry('600x260')
        self.root.update()
        for control in self.bar.controls:
            self.assertTrue(control.winfo_viewable())
            self.assertGreaterEqual(control.winfo_rootx(), self.root.winfo_rootx())
            self.assertLessEqual(control.winfo_rootx() + control.winfo_width(),
                                 self.root.winfo_rootx() + self.root.winfo_width())
        self.root.tk.call('tk', 'scaling', original)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows native frame')
    def test_native_frame_resize_minimize_restore_and_close(self):
        chrome = NativeWindowChrome(self.root)
        self.assertTrue(chrome.install())
        self.root.update()
        self.assertTrue(self.root.overrideredirect())
        import ctypes
        from ctypes import wintypes
        user = chrome.user
        self.assertTrue(user.GetWindowLongW(chrome.hwnd, -20) & 0x40000)
        self.assertFalse(user.GetWindowLongW(chrome.hwnd, -20) & 0x80)  # not a tool window
        style = user.GetWindowLongW(chrome.hwnd, -16)
        self.assertEqual(style & 0x70000, 0x70000)  # resize, minimize, maximize boxes
        rect = wintypes.RECT()
        user.GetWindowRect(chrome.hwnd, ctypes.byref(rect))
        point = ((rect.top + 1) << 16) | ((rect.left + 1) & 0xffff)
        self.assertEqual(user.SendMessageW(chrome.hwnd, 0x84, 0, point), 13)  # HTTOPLEFT
        chrome.minimize()
        self.root.update()
        self.assertTrue(user.IsIconic(chrome.hwnd))
        user.ShowWindow(chrome.hwnd, 9)
        self.root.update()
        self.assertFalse(user.IsIconic(chrome.hwnd))
        chrome.toggle_maximize()
        self.root.update()
        self.assertTrue(user.IsZoomed(chrome.hwnd))
        chrome.toggle_maximize()
        self.root.update()
        self.assertFalse(user.IsZoomed(chrome.hwnd))
        closed = []
        self.root.protocol('WM_DELETE_WINDOW', lambda: closed.append(True))
        user.SendMessageW(chrome.hwnd, 0x112, 0xF060, 0)  # SC_CLOSE, same path as Alt+F4
        self.root.update()
        self.assertEqual(closed, [True])
