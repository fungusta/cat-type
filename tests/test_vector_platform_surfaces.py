"""Exercise platform image boundaries with real vectors and small OS adapters.

These tests verify the data passed to native APIs; window-manager behavior is
covered separately by tests that run on the corresponding platform.
"""

import sys
import tkinter as tk
import unittest
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image, ImageTk

import cat_type
from cat_settings import CAT_VARIANTS, AppSettings


class VectorPlatformSurfaceTests(unittest.TestCase):
    def soft_edge_pixels(self, variant, **outfit):
        preview = cat_type.load_frame(cat_type.APP_DIR / "assets", variant, "idle", 120, **outfit)
        # Ear silhouettes vary; sample their rendered edges instead of a fixed point.
        pixels = [
            (index % preview.width, index // preview.width)
            for index, alpha in enumerate(preview.getchannel("A").get_flattened_data())
            if 0 < alpha < 128
        ]
        self.assertTrue(pixels, "The vector preview must contain soft edge pixels")
        return pixels

    def test_macos_native_image_receives_vector_pixels_at_backing_resolution(self):
        class NativeImage:
            @classmethod
            def alloc(cls):
                return cls()

            def initWithData_(self, data):
                with Image.open(BytesIO(data)) as source:
                    self.pixels = source.convert("RGBA")
                return self

        class NativeImageView:
            width = 120

            def bounds(self):
                return SimpleNamespace(size=SimpleNamespace(width=self.width))

            def setImage_(self, image):
                self.image = image

        surface = cat_type._MacOSNativeOverlaySurface("test")
        surface._window = SimpleNamespace(backingScaleFactor=lambda: 2)
        surface._tk_content_view = object()
        surface._image_view = view = NativeImageView()
        modules = {
            "AppKit": SimpleNamespace(NSImage=NativeImage),
            "Foundation": SimpleNamespace(NSData=SimpleNamespace(
                dataWithBytes_length_=lambda data, length: data[:length],
            )),
        }
        with patch.dict(sys.modules, modules):
            for variant in CAT_VARIANTS:
                with self.subTest(variant=variant):
                    view.width = 120
                    surface.set_frame(variant, "tap-left")
                    first_image = view.image
                    self.assertEqual(first_image.pixels.size, (240, 240))
                    self.assertEqual(first_image.pixels.getpixel((0, 0))[3], 0)
                    self.assertEqual(first_image.pixels.getpixel((120, 80))[3], 255)
                    surface.set_frame(variant, "tap-left")
                    self.assertIs(view.image, first_image)
                    view.width = 210
                    surface.set_frame(variant, "tap-left")
                    self.assertEqual(view.image.pixels.size, (420, 420))
                    self.assertIsNot(view.image, first_image)
                    surface.set_outfit("crown", "round-glasses")
                    surface.set_frame(variant, "tap-left")
                    dressed = cat_type.load_frame(
                        cat_type.ASSETS_ROOT, variant, "tap-left", 420,
                        hat="crown", glasses="round-glasses",
                    )
                    self.assertEqual(view.image.pixels.tobytes(), dressed.tobytes())
                    surface.set_outfit("none", "none")
                    surface.set_frame(variant, "tap-left")
                    self.assertNotEqual(view.image.pixels.tobytes(), dressed.tobytes())

    def test_linux_shape_uses_vector_alpha_at_overlay_size_and_empty_input_region(self):
        rectangles_by_kind = {}

        class ShapeWindow:
            def shape_rectangles(self, operation, kind, order, x, y, rectangles):
                rectangles_by_kind[kind] = rectangles

        native_display = SimpleNamespace(
            create_resource_object=lambda kind, identifier: ShapeWindow(),
            sync=lambda: None,
        )
        app = SimpleNamespace(
            settings=AppSettings(),
            _x_display=native_display,
            root=SimpleNamespace(winfo_id=lambda: 123),
            frame_width=210,
            debug=True,
        )
        modules = {
            "Xlib": SimpleNamespace(X=SimpleNamespace(YXBanded=3), display=object()),
            "Xlib.ext": SimpleNamespace(shape=SimpleNamespace(
                SO=SimpleNamespace(Set=0), SK=SimpleNamespace(Bounding=0, Input=2),
            )),
        }
        with patch.dict(sys.modules, modules), patch.object(cat_type, "IS_LINUX", True):
            cat_type.CatTypeApp._shape_linux_overlay(app, "white", "excited")
        self.assertEqual(rectangles_by_kind[2], [])
        bounds = rectangles_by_kind[0]
        self.assertGreater(len(bounds), 100)
        self.assertTrue(all(0 <= x < 210 and 0 <= y < 210 and x + width <= 210
                            for x, y, width, height in bounds))
        self.assertFalse(any(x == 0 and y == 0 for x, y, width, height in bounds))
        self.assertTrue(any(y == 70 and x <= 105 < x + width
                            for x, y, width, height in bounds))

    def test_linux_shape_matches_binary_display_alpha_and_excludes_soft_edge(self):
        rectangles_by_kind = {}

        class ShapeWindow:
            def shape_rectangles(self, operation, kind, order, x, y, rectangles):
                rectangles_by_kind[kind] = rectangles

        native_display = SimpleNamespace(
            create_resource_object=lambda kind, identifier: ShapeWindow(),
            sync=lambda: None,
        )
        app = SimpleNamespace(
            settings=AppSettings(hat="crown", glasses="round-glasses"),
            _x_display=native_display,
            root=SimpleNamespace(winfo_id=lambda: 123),
            frame_width=120,
            debug=True,
        )
        modules = {
            "Xlib": SimpleNamespace(X=SimpleNamespace(YXBanded=3), display=object()),
            "Xlib.ext": SimpleNamespace(shape=SimpleNamespace(
                SO=SimpleNamespace(Set=0), SK=SimpleNamespace(Bounding=0, Input=2),
            )),
        }
        for variant in CAT_VARIANTS:
            with self.subTest(variant=variant):
                with patch.dict(sys.modules, modules), patch.object(cat_type, "IS_LINUX", True):
                    cat_type.CatTypeApp._shape_linux_overlay(app, variant, "idle")

                mask = Image.new("1", (120, 120))
                mask_pixels = mask.load()
                for x, y, width, height in rectangles_by_kind[0]:
                    for row in range(y, y + height):
                        for column in range(x, x + width):
                            mask_pixels[column, row] = 1
                displayed = cat_type.load_frame(
                    cat_type.APP_DIR / "assets",
                    variant,
                    "idle",
                    120,
                    color_key_safe=True,
                    hat=app.settings.hat,
                    glasses=app.settings.glasses,
                )
                expected = displayed.getchannel("A").point(lambda alpha: 1 if alpha else 0, "1")
                self.assertEqual(mask.tobytes(), expected.tobytes())
                self.assertTrue(all(mask.getpixel(point) == 0
                                    for point in self.soft_edge_pixels(
                                        variant, hat=app.settings.hat, glasses=app.settings.glasses)))

    def test_linux_tk_vector_frames_use_binary_alpha(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk display unavailable: {error}")
        root.withdraw()
        try:
            app = cat_type.CatTypeApp.__new__(cat_type.CatTypeApp)
            app.root = root
            app.settings = AppSettings(hat="beanie", glasses="star-glasses")
            with (
                patch.object(cat_type, "IS_WINDOWS", False),
                patch.object(cat_type, "IS_LINUX", True),
            ):
                frames = app._load_frames(100)
            for variant in CAT_VARIANTS:
                with self.subTest(variant=variant):
                    displayed = ImageTk.getimage(frames[variant]["idle"]).convert("RGBA")
                    self.assertLessEqual(
                        set(displayed.getchannel("A").get_flattened_data()),
                        {0, 255},
                    )
                    self.assertTrue(all(displayed.getpixel(point)[3] == 0
                                        for point in self.soft_edge_pixels(
                                            variant, hat=app.settings.hat, glasses=app.settings.glasses)))

        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
