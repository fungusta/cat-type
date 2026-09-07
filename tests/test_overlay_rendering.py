import ctypes
import sys
import time
import tkinter as tk
import unittest

from PIL import Image, ImageTk
from cat_settings import AppSettings
from cat_artwork import load_frame

if sys.platform == "win32":
    import win32gui
    import win32ui
else:
    win32gui = None
    win32ui = None

from cat_type import (
    CAT_VARIANTS,
    CaretSnapshot,
    CatTypeApp,
    ASSETS_ROOT,
    ScreenRect,
    make_window_non_interactive,
)


@unittest.skipUnless(
    sys.platform == "win32",
    "Windows-only rendering integration",
)
class OverlayRenderingTests(unittest.TestCase):
    def test_vector_cat_renders_all_input_poses_and_returns_to_idle(self) -> None:
        for variant in CAT_VARIANTS:
            with self.subTest(variant=variant):
                app = CatTypeApp(settings=AppSettings(cat_style=variant))
                try:
                    now = time.monotonic()
                    captures = {}
                    for index, (paw, expected) in enumerate(
                        (("left", "tap-left"), ("right", "tap-right"), ("both", "excited"))
                    ):
                        at = now + index
                        app.animation.record_key(at, paw)
                        snapshot = CaretSnapshot(at, ScreenRect(400, 300, 402, 320), "vector-test")
                        app._show(snapshot, at)
                        app.root.update()
                        self.assertEqual(app._last_rendered_frame, (variant, expected))
                        capture = self._capture_window(app.root.winfo_id(), 120, 120)
                        coat = load_frame(ASSETS_ROOT, variant, expected, 120).getpixel((60, 50))[:3]
                        self.assertGreater(sum(pixel == coat for pixel in capture.get_flattened_data()), 1000)
                        self._assert_no_green_fringe(capture)
                        captures[expected] = capture.tobytes()
                    self.assertEqual(len(set(captures.values())), 3)
                    app._show(snapshot, at + 0.2)
                    self.assertEqual(app._last_rendered_frame, (variant, "idle"))
                    app._show(snapshot, at + 1.325)
                    self.assertAlmostEqual(float(app.root.wm_attributes("-alpha")), 0.5, places=1)
                finally:
                    app.root.destroy()

    def test_vector_cat_renders_at_every_supported_size_and_is_clickthrough(self) -> None:
        for percent in (60, 100, 175):
            with self.subTest(percent=percent):
                app = CatTypeApp(settings=AppSettings(cat_style="white", size_percent=percent))
                try:
                    now = time.monotonic()
                    app.animation.record_key(now)
                    app._show(CaretSnapshot(now, ScreenRect(400, 300, 402, 320), "vector-size"), now)
                    app.root.update()
                    size = round(120 * percent / 100)
                    self.assertEqual((app.frame_width, app.frame_height), (size, size))
                    self.assertEqual(app.label.cget("image"), str(app.frames["white"]["tap-left"]))
                    hwnd = app.root.winfo_id()
                    style = win32gui.GetWindowLong(hwnd, -20)
                    self.assertTrue(style & 0x20, "SVG overlay must let mouse input pass through")
                    self._assert_no_green_fringe(self._capture_window(app.root.winfo_id(), size, size))
                finally:
                    app.root.destroy()

    def test_keystroke_counter_is_not_rendered_in_the_cat_overlay(self) -> None:
        app = CatTypeApp(hold_seconds=10.0)
        try:
            app.root.update_idletasks()

            self.assertEqual(app.root.winfo_children(), [app.label])
            self.assertEqual(app.label.winfo_reqwidth(), app.frame_width)
            self.assertEqual(app.label.winfo_reqheight(), app.frame_height)
        finally:
            app.root.destroy()

    def test_new_appearances_alternate_tabby_variants(self) -> None:
        app = CatTypeApp(hold_seconds=1.5)
        try:
            now = time.monotonic()
            app.animation.record_key(now)
            app._show(
                CaretSnapshot(
                    captured_at=now,
                    rect=ScreenRect(500, 300, 502, 320),
                    source="test",
                ),
                now,
            )
            self.assertEqual(app._active_variant, "gray")
            self.assertEqual((app.frame_width, app.frame_height), (120, 120))

            app._hide()
            app.animation.record_key(now + 2.0)
            app._show(
                CaretSnapshot(
                    captured_at=now + 2.0,
                    rect=ScreenRect(300, 200, 302, 220),
                    source="test",
                ),
                now + 2.0,
            )
            self.assertEqual(app._active_variant, "ginger")
            app.root.update()
            captured = self._capture_window(
                app.root.winfo_id(), app.frame_width, app.frame_height
            )
            ginger_pixels = sum(
                1
                for red, green, blue in captured.get_flattened_data()
                if red > 220 and 80 < green < 210 and blue < 100
            )
            self.assertGreater(ginger_pixels, 1_000)
            self._assert_no_green_fringe(captured)
        finally:
            app.root.destroy()

    def test_overlay_stays_at_spawn_position_when_caret_moves(self) -> None:
        app = CatTypeApp(hold_seconds=10.0)
        try:
            now = time.monotonic()
            app.animation.record_key(now)
            app._show(
                CaretSnapshot(
                    captured_at=now,
                    rect=ScreenRect(500, 300, 502, 320),
                    source="test",
                ),
                now,
            )
            app.root.update()
            spawned_at = (app.root.winfo_x(), app.root.winfo_y())

            app._show(
                CaretSnapshot(
                    captured_at=now + 0.1,
                    rect=ScreenRect(100, 320, 102, 340),
                    source="test",
                ),
                now + 0.1,
            )
            app.root.update()

            self.assertEqual(
                (app.root.winfo_x(), app.root.winfo_y()),
                spawned_at,
            )
        finally:
            app.root.destroy()

    def test_show_path_applies_fade_opacity_to_the_window(self) -> None:
        app = CatTypeApp(hold_seconds=1.5, fade_seconds=0.3)
        try:
            now = time.monotonic()
            app.animation.record_key(now - 1.35)
            app._show(
                CaretSnapshot(
                    captured_at=now,
                    rect=ScreenRect(400, 300, 402, 320),
                    source="test",
                ),
                now,
            )
            app.root.update()
            self.assertAlmostEqual(
                float(app.root.wm_attributes("-alpha")),
                0.5,
                places=1,
            )
            captured = self._capture_window(
                app.root.winfo_id(), app.frame_width, app.frame_height
            )
            self._assert_no_green_fringe(captured)
        finally:
            app.root.destroy()

    def test_real_app_show_path_renders_cat_pixels(self) -> None:
        app = CatTypeApp(hold_seconds=10.0)
        try:
            now = time.monotonic()
            app.animation.record_key(now)
            app._show(
                CaretSnapshot(
                    captured_at=now,
                    rect=ScreenRect(400, 300, 402, 320),
                    source="test",
                ),
                now,
            )
            app.root.update()
            captured = self._capture_window(
                app.root.winfo_id(), app.frame_width, app.frame_height
            )
            self._assert_cat_pixels(captured)
            self._assert_no_green_fringe(captured)
        finally:
            app.root.destroy()

    def test_clickthrough_overlay_keeps_rendered_cat_pixels(self) -> None:
        root = tk.Tk()
        try:
            transparent = "#00ff01"
            root.title("Cat Type Rendering Test")
            root.withdraw()
            root.overrideredirect(True)
            root.configure(background=transparent)
            root.wm_attributes("-topmost", True)
            root.wm_attributes("-transparentcolor", transparent)

            image = ImageTk.PhotoImage(
                load_frame(ASSETS_ROOT, "gray", "idle", 120, color_key_safe=True),
                master=root,
            )
            label = tk.Label(
                root,
                image=image,
                background=transparent,
                borderwidth=0,
                highlightthickness=0,
            )
            label.pack()
            root.update_idletasks()

            # Match the real lifecycle: configure while withdrawn, then map
            # the click-through overlay beside a caret.
            make_window_non_interactive(root.winfo_id())
            root.geometry(f"{image.width()}x{image.height()}+20+20")
            root.deiconify()
            root.lift()
            make_window_non_interactive(root.winfo_id())
            root.update()
            time.sleep(0.05)

            captured = self._capture_window(
                root.winfo_id(), image.width(), image.height()
            )
            self._assert_cat_pixels(captured)
            self._assert_no_green_fringe(captured)
        finally:
            root.destroy()

    def _assert_cat_pixels(self, captured: Image.Image) -> None:
        light_cat_pixels = sum(
            1
            for red, green, blue in captured.get_flattened_data()
            if red > 220 and green > 220 and blue > 220
        )
        self.assertGreater(
            light_cat_pixels,
            1_000,
            "The click-through window is visible but its cat surface is blank",
        )

    def _assert_no_green_fringe(self, captured: Image.Image) -> None:
        green_fringe_pixels = sum(
            1
            for red, green, blue in captured.get_flattened_data()
            if green > red * 1.15
            and green > blue * 1.15
            and not (red < 5 and green > 245 and blue < 5)
        )
        self.assertEqual(
            green_fringe_pixels,
            0,
            "The rendered window still contains blended green edge pixels",
        )

    @staticmethod
    def _capture_window(hwnd: int, width: int, height: int) -> Image.Image:
        assert win32gui is not None
        assert win32ui is not None
        window_dc = win32gui.GetWindowDC(hwnd)
        source_dc = win32ui.CreateDCFromHandle(window_dc)
        memory_dc = source_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(source_dc, width, height)
        memory_dc.SelectObject(bitmap)
        try:
            ctypes.windll.user32.PrintWindow(
                hwnd, memory_dc.GetSafeHdc(), 0x00000002
            )
            info = bitmap.GetInfo()
            bits = bitmap.GetBitmapBits(True)
            return Image.frombuffer(
                "RGB",
                (info["bmWidth"], info["bmHeight"]),
                bits,
                "raw",
                "BGRX",
                0,
                1,
            )
        finally:
            win32gui.DeleteObject(bitmap.GetHandle())
            memory_dc.DeleteDC()
            source_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, window_dc)


class CatSurfaceArtworkTests(unittest.TestCase):
    def test_gray_tabby_has_dark_purple_pads_not_purple_paw_fur(self) -> None:
        frame = load_frame(ASSETS_ROOT, "gray", "idle", 120)
        purple_pixels = sum(
            1 for red, green, blue, alpha in frame.get_flattened_data()
            if alpha and blue > red and green < red and red > 20
        )
        self.assertGreater(purple_pixels, 20)
        self.assertLess(purple_pixels, 300)

    def test_all_rendered_poses_have_no_green_chroma_key_fringe(self) -> None:
        for variant in CAT_VARIANTS:
            for pose in ("idle", "tap-left", "tap-right", "excited"):
                with self.subTest(variant=variant, pose=pose):
                    frame = load_frame(ASSETS_ROOT, variant, pose, 120, color_key_safe=True)
                    fringe = sum(
                        1 for red, green, blue, alpha in frame.get_flattened_data()
                        if alpha >= 16 and green > red * 1.15 and green > blue * 1.15
                    )
                    self.assertEqual(fringe, 0)


if __name__ == "__main__":
    unittest.main()
