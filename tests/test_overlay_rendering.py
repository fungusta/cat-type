import ctypes
import time
import tkinter as tk
import unittest
from unittest.mock import patch

import win32gui
import win32ui
from PIL import Image

from cat_settings import AppSettings
from cat_type import (
    CAT_VARIANTS,
    CaretSnapshot,
    CatTypeApp,
    FRAME_DIR,
    FRAME_ROOT,
    ScreenRect,
    make_window_non_interactive,
)


class OverlayRenderingTests(unittest.TestCase):
    def test_keystroke_counter_is_not_rendered_in_the_cat_overlay(self) -> None:
        app = CatTypeApp(hold_seconds=10.0)
        try:
            app.root.update_idletasks()

            self.assertEqual(app.root.winfo_children(), [app.label])
            self.assertEqual(app.label.winfo_reqwidth(), app.frame_width)
            self.assertEqual(app.label.winfo_reqheight(), app.frame_height)
        finally:
            app.root.destroy()

    def test_missing_caret_uses_preferred_monitor_corner(self) -> None:
        app = CatTypeApp(
            hold_seconds=10.0,
            settings=AppSettings(placement="below-left"),
        )
        try:
            now = time.monotonic()
            app.animation.record_key(now)
            with patch(
                "cat_type.active_work_area",
                return_value=ScreenRect(-1920, 40, 0, 1080),
            ):
                app._show(
                    CaretSnapshot(
                        captured_at=now,
                        rect=None,
                        source="uia-fallback",
                        fallback_allowed=True,
                    ),
                    now,
                )
            app.root.update()

            self.assertEqual(
                (app.root.winfo_x(), app.root.winfo_y()),
                (-1914, 954),
            )
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

            image = tk.PhotoImage(
                file=str(FRAME_DIR / "idle.png")
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


class SpriteAssetTests(unittest.TestCase):
    @staticmethod
    def _frame_paths() -> list:
        return [
            frame_path
            for variant in CAT_VARIANTS
            for frame_path in sorted((FRAME_ROOT / variant).glob("*.png"))
        ]

    def test_runtime_frames_use_binary_alpha_for_windows_color_key(self) -> None:
        for frame_path in self._frame_paths():
            with self.subTest(frame=frame_path.name), Image.open(frame_path) as frame:
                alpha_values = {
                    alpha
                    for _, _, _, alpha in frame.convert(
                        "RGBA"
                    ).get_flattened_data()
                }
                self.assertLessEqual(
                    alpha_values,
                    {0, 255},
                    f"{frame_path.name} has soft alpha that can blend with "
                    "the green Windows color key",
                )

    def test_runtime_frames_are_the_smaller_size(self) -> None:
        for frame_path in self._frame_paths():
            with self.subTest(frame=str(frame_path)), Image.open(frame_path) as frame:
                self.assertEqual(frame.size, (120, 120))

    def test_gray_tabby_has_dark_purple_pads_not_purple_paw_fur(self) -> None:
        with Image.open(FRAME_ROOT / "gray" / "idle.png") as frame:
            dark_gray_purple_pixels = sum(
                1
                for red, green, blue, alpha in frame.convert(
                    "RGBA"
                ).get_flattened_data()
                if alpha
                and blue > red * 1.1
                and green < red
                and red > 20
            )
        self.assertGreater(dark_gray_purple_pixels, 20)
        self.assertLess(
            dark_gray_purple_pixels,
            300,
            "Only the small pads should be purple, not the surrounding paw fur",
        )

    def test_pose_frames_share_the_same_upper_body_center(self) -> None:
        for variant in CAT_VARIANTS:
            centers = []
            for frame_path in sorted((FRAME_ROOT / variant).glob("*.png")):
                alpha = Image.open(frame_path).convert("RGBA").getchannel("A")
                upper_bounds = alpha.crop((0, 0, 120, 72)).getbbox()
                self.assertIsNotNone(upper_bounds)
                assert upper_bounds is not None
                centers.append(
                    (upper_bounds[0] + upper_bounds[2] - 1) / 2
                )

            with self.subTest(variant=variant):
                self.assertLessEqual(
                    max(centers) - min(centers),
                    0.5,
                    f"{variant} pose frames are horizontally misregistered",
                )

    def test_runtime_frames_have_no_green_chroma_key_fringe(self) -> None:
        for frame_path in self._frame_paths():
            with self.subTest(frame=frame_path.name), Image.open(frame_path) as frame:
                green_fringe_pixels = sum(
                    1
                    for red, green, blue, alpha in frame.convert(
                        "RGBA"
                    ).get_flattened_data()
                    if alpha >= 16
                    and green > red * 1.15
                    and green > blue * 1.15
                )
                self.assertEqual(
                    green_fringe_pixels,
                    0,
                    f"{frame_path.name} still contains green matte pixels",
                )


if __name__ == "__main__":
    unittest.main()
