import importlib
import importlib.util
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import ImageChops

from cat_settings import CAT_VARIANTS


ASSETS = Path(__file__).resolve().parents[1] / "assets"


class CatArtworkTests(unittest.TestCase):
    def artwork(self):
        self.assertIsNotNone(
            importlib.util.find_spec("cat_artwork"),
            "The vector artwork renderer must exist",
        )
        return importlib.import_module("cat_artwork")

    def test_vector_frames_render_at_requested_size_with_clear_corners(self):
        for family in CAT_VARIANTS:
            variant = family
            with self.subTest(variant=variant):
                art = self.artwork()
                for size in (72, 120, 148, 210):
                    for pose in ("idle", "tap-left", "tap-right", "excited"):
                        with self.subTest(size=size, pose=pose):
                            frame = art.load_frame(ASSETS, variant, pose, size)
                            self.assertEqual(frame.size, (size, size))
                            self.assertEqual(frame.mode, "RGBA")
                            for corner in ((0, 0), (size - 1, 0), (0, size - 1), (size - 1, size - 1)):
                                self.assertEqual(frame.getpixel(corner)[3], 0)
                            self.assertGreater(frame.getpixel((size // 2, size // 3))[3], 240)

    def test_each_tap_moves_only_its_own_paw_and_keeps_head_aligned(self):
        for family in CAT_VARIANTS:
            variant = family
            with self.subTest(variant=variant):
                art = self.artwork()
                idle, left, right = [
                    art.load_frame(ASSETS, variant, pose, 120)
                    for pose in ("idle", "tap-left", "tap-right")
                ]
                # Comparing RGBA bytes catches RGB changes even where alpha is identical.
                left_change = ImageChops.difference(idle, left).convert("RGB").getbbox()
                right_change = ImageChops.difference(idle, right).convert("RGB").getbbox()
                self.assertIsNotNone(left_change)
                self.assertIsNotNone(right_change)
                self.assertLess(left_change[2], 46)
                self.assertGreater(left_change[1], 70)
                self.assertGreater(right_change[0], 74)
                self.assertGreater(right_change[1], 70)
                self.assertEqual(idle.crop((0, 0, 120, 70)).tobytes(), left.crop((0, 0, 120, 70)).tobytes())

    def test_excited_pose_taps_both_paws_and_opens_the_mouth(self):
        for family in CAT_VARIANTS:
            variant = family
            with self.subTest(variant=variant):
                art = self.artwork()
                idle, left, right, excited = [
                    art.load_frame(ASSETS, variant, pose, 120)
                    for pose in ("idle", "tap-left", "tap-right", "excited")
                ]
                self.assertEqual(excited.crop((8, 73, 44, 105)).tobytes(), left.crop((8, 73, 44, 105)).tobytes())
                self.assertEqual(excited.crop((76, 73, 112, 105)).tobytes(), right.crop((76, 73, 112, 105)).tobytes())
                self.assertNotEqual(idle.crop((49, 62, 71, 76)).tobytes(), excited.crop((49, 62, 71, 76)).tobytes())

    def test_toe_beans_are_visible_only_on_raised_paws(self):
        art = self.artwork()
        for family in CAT_VARIANTS:
            variant = family
            source = art.frame_source_path(ASSETS, variant, "idle")
            for pose, expected in (
                ("idle", (True, True)), ("tap-left", (False, True)),
                ("tap-right", (True, False)), ("excited", (False, False)),
            ):
                with self.subTest(variant=variant, pose=pose):
                    root = ET.fromstring(art.posed_svg(source, pose))
                    parts = {e.get("id"): e for e in root.iter()}
                    frame = art.load_frame(ASSETS, variant, pose, 240)
                    for side, visible, bounds in zip(
                        ("left", "right"), expected,
                        ((16, 146, 88, 210), (152, 146, 224, 210)),
                    ):
                        pad = parts[f"pads-{side}"]
                        self.assertEqual(pad.get("display"), "inline" if visible else "none")
                        color = pad.get("fill").lstrip("#")
                        rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
                        pixels = list(frame.crop(bounds).get_flattened_data())
                        self.assertEqual((*rgb, 255) in pixels, visible)

    def test_artwork_is_editable_vector_groups_without_embedded_images(self):
        for family in CAT_VARIANTS:
            variant = family
            with self.subTest(variant=variant):
                art = self.artwork()
                source = art.frame_source_path(ASSETS, variant, "idle")
                root = ET.fromstring(art.posed_svg(source, "idle"))
                self.assertEqual(root.get("viewBox"), "0 0 120 120")
                ids = {element.get("id") for element in root.iter()}
                self.assertTrue({"body", "head", "ears", "eyes", "mouth", "paw-left", "paw-right"} <= ids)
                self.assertFalse(any(element.tag.endswith("}image") for element in root.iter()))
                self.assertFalse(any("href" in key for element in root.iter() for key in element.attrib))

    def test_windows_output_has_no_partial_alpha_but_preview_keeps_it(self):
        for family in CAT_VARIANTS:
            variant = family
            with self.subTest(variant=variant):
                art = self.artwork()
                preview = art.load_frame(ASSETS, variant, "idle", 148)
                overlay = art.load_frame(ASSETS, variant, "idle", 148, color_key_safe=True)
                self.assertTrue(set(overlay.getchannel("A").get_flattened_data()) <= {0, 255})
                self.assertTrue(any(0 < alpha < 255 for alpha in preview.getchannel("A").get_flattened_data()))

    def test_every_canonical_cat_uses_an_editable_svg_source(self):
        art = self.artwork()
        for variant in CAT_VARIANTS:
            with self.subTest(variant=variant):
                source = art.frame_source_path(ASSETS, variant, "idle")
                self.assertEqual(source, ASSETS / "vector-cats" / f"{variant}.svg")
                self.assertTrue(source.is_file())
        with self.assertRaises(ValueError):
            art.load_frame(ASSETS, "missing", "idle", 120)

    def test_invalid_pose_and_size_are_rejected(self):
        art = self.artwork()
        source = art.frame_source_path(ASSETS, "white", "idle")
        with self.assertRaises(ValueError):
            art.posed_svg(source, "missing")
        with self.assertRaises(ValueError):
            art.vector_png(source, "idle", 0)


if __name__ == "__main__":
    unittest.main()
