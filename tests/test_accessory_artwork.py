import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from cat_settings import CAT_VARIANTS


ASSETS = Path(__file__).resolve().parents[1] / "assets"


class AccessoryArtworkTests(unittest.TestCase):
    def test_empty_outfit_preserves_existing_svg_and_pixels(self):
        import cat_artwork as art

        source = art.frame_source_path(ASSETS, "white", "idle")
        expected_svg = art.posed_svg(source, "idle")
        expected_frame = art.load_frame(ASSETS, "white", "idle", 120)

        self.assertEqual(
            art.posed_svg(source, "idle", hat=None, glasses=None), expected_svg
        )
        self.assertEqual(
            art.load_frame(
                ASSETS, "white", "idle", 120, hat=None, glasses=None
            ).tobytes(),
            expected_frame.tobytes(),
        )

    def test_outfit_changes_head_pixels_and_preserves_paws(self):
        import cat_artwork as art

        plain = art.load_frame(ASSETS, "white", "idle", 120)
        dressed = art.load_frame(
            ASSETS,
            "white",
            "idle",
            120,
            hat="crown",
            glasses="round-glasses",
        )

        self.assertNotEqual(plain.tobytes(), dressed.tobytes())
        self.assertEqual(
            plain.crop((0, 74, 120, 120)).tobytes(),
            dressed.crop((0, 74, 120, 120)).tobytes(),
        )

    def test_each_outfit_is_distinct_and_cached_by_accessory(self):
        import cat_artwork as art

        source = art.frame_source_path(ASSETS, "gray", "idle")
        crown = art.vector_png(source, "idle", 120, hat="crown")
        beanie = art.vector_png(source, "idle", 120, hat="beanie")
        glasses = art.vector_png(
            source, "idle", 120, glasses="round-glasses"
        )

        self.assertEqual(
            crown, art.vector_png(source, "idle", 120, hat="crown")
        )
        self.assertEqual(3, len({crown, beanie, glasses}))

    def test_invalid_and_wrong_slot_accessories_are_rejected(self):
        import cat_artwork as art

        source = art.frame_source_path(ASSETS, "white", "idle")
        for kwargs in (
            {"hat": "missing"},
            {"hat": "round-glasses"},
            {"glasses": "crown"},
            {"glasses": []},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                art.vector_png(source, "idle", 120, **kwargs)

    def test_accessory_masters_are_editable_standalone_vectors(self):
        expected = {
            "round-glasses",
            "sunglasses",
            "star-glasses",
            "beanie",
            "party-hat",
            "crown",
        }
        for accessory_id in expected:
            with self.subTest(accessory=accessory_id):
                root = ET.parse(
                    ASSETS / "accessories" / f"{accessory_id}.svg"
                ).getroot()
                self.assertEqual(root.get("viewBox"), "0 0 120 120")
                ids = {element.get("id") for element in root.iter()}
                self.assertIn(accessory_id, ids)
                self.assertFalse(
                    any(element.tag.endswith("}image") for element in root.iter())
                )
                self.assertFalse(
                    any(
                        "href" in key
                        for element in root.iter()
                        for key in element.attrib
                    )
                )

    def test_outfit_renders_for_every_cat_pose_and_supported_size(self):
        import cat_artwork as art

        for variant in CAT_VARIANTS:
            for pose in art.POSE_NAMES:
                for size in (72, 120, 210):
                    with self.subTest(variant=variant, pose=pose, size=size):
                        plain = art.load_frame(ASSETS, variant, pose, size)
                        dressed = art.load_frame(
                            ASSETS,
                            variant,
                            pose,
                            size,
                            hat="party-hat",
                            glasses="star-glasses",
                        )
                        self.assertEqual(dressed.size, (size, size))
                        for corner in (
                            (0, 0),
                            (size - 1, 0),
                            (0, size - 1),
                            (size - 1, size - 1),
                        ):
                            self.assertEqual(dressed.getpixel(corner)[3], 0)
                        paw_top = round(size * 74 / 120)
                        self.assertEqual(
                            plain.crop((0, paw_top, size, size)).tobytes(),
                            dressed.crop((0, paw_top, size, size)).tobytes(),
                        )

    def test_each_accessory_stays_strictly_inside_every_canvas_edge(self):
        import cat_artwork as art

        outfits = (
            {"glasses": "round-glasses"},
            {"glasses": "sunglasses"},
            {"glasses": "star-glasses"},
            {"hat": "beanie"},
            {"hat": "party-hat"},
            {"hat": "crown"},
        )
        for outfit in outfits:
            for size in (72, 120, 210):
                with self.subTest(outfit=outfit, size=size):
                    frame = art.load_frame(
                        ASSETS, "gray", "idle", size, **outfit
                    )
                    left, top, right, bottom = frame.getchannel("A").getbbox()
                    self.assertGreater(left, 0)
                    self.assertGreater(top, 0)
                    self.assertLess(right, size)
                    self.assertLess(bottom, size)

    def test_packaging_includes_accessory_vectors(self):
        spec = (ASSETS.parent / "CatType.spec").read_text(encoding="utf-8")
        self.assertIn('project_root / "assets" / "accessories"', spec)
        self.assertIn('"assets/accessories"', spec)

    def test_hat_composes_above_glasses(self):
        import cat_artwork as art

        source = art.frame_source_path(ASSETS, "white", "idle")
        root = ET.fromstring(
            art.posed_svg(
                source, "idle", hat="crown", glasses="round-glasses"
            )
        )
        self.assertEqual(
            [element.get("id") for element in root][-2:],
            ["accessory-glasses", "accessory-hat"],
        )


if __name__ == "__main__":
    unittest.main()
