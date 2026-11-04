import sys
import tkinter as tk
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from ui_surfaces import MOTION_FAST_MS
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
        # Hover eases in; let the short animation settle before inspecting.
        self.root.after(MOTION_FAST_MS + 40)
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
        # Tk children cover the client area, so the border is found from Tk
        # events: over a child at each edge, never in the middle.
        self.root.geometry('460x220+40+40')
        self.root.update()
        left, top = self.root.winfo_rootx(), self.root.winfo_rooty()
        right, bottom = left + self.root.winfo_width(), top + self.root.winfo_height()
        middle_x, middle_y = (left + right) // 2, (top + bottom) // 2
        for (x, y), hit in (((left + 1, middle_y), 10), ((right - 2, middle_y), 11),
                            ((middle_x, top + 1), 12), ((middle_x, bottom - 2), 15),
                            ((left + 1, top + 1), 13), ((right - 2, top + 1), 14),
                            ((left + 1, bottom - 2), 16), ((right - 2, bottom - 2), 17),
                            ((right - 2, bottom - 15), 17), ((middle_x, middle_y), None)):
            with self.subTest(x=x - left, y=y - top):
                self.assertEqual(chrome.resize_edge(x, y), hit)
        with patch.object(chrome, 'is_maximized', return_value=True):
            self.assertIsNone(chrome.resize_edge(left + 1, middle_y))
        with patch.object(user, 'PostMessageW') as post, patch.object(user, 'SendMessageW') as send:
            event = SimpleNamespace(x_root=right - 2, y_root=middle_y)
            chrome.begin_resize(11, event)
            chrome.begin_drag(SimpleNamespace(x_root=middle_x, y_root=top + 10))
        # Posted so the modal loop starts from Tk's pump, never inside a callback.
        send.assert_not_called()
        self.assertEqual([call.args[1:3] for call in post.call_args_list], [(0xA1, 11), (0xA1, 2)])
        closed = []
        self.root.protocol('WM_DELETE_WINDOW', lambda: closed.append(True))
        user.SendMessageW(chrome.hwnd, 0x112, 0xF060, 0)  # SC_CLOSE, same path as Alt+F4
        self.root.update()
        self.assertEqual(closed, [True])
