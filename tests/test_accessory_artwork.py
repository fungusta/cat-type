import unittest
import inspect
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import ImageChops

from cat_settings import CAT_VARIANTS
from cat_accessories import ACCESSORIES
import cat_artwork as art


ASSETS = Path(__file__).resolve().parents[1] / "assets"


class AccessoryArtworkTests(unittest.TestCase):
    def test_capes_follow_the_crop_line_and_show_a_front_neck_fastening(self):
        for cape in ('adventure-cape', 'royal-cape'):
            with self.subTest(cape=cape):
                with art.load_frame(ASSETS, 'white', 'idle', 120) as plain, art.load_frame(
                    ASSETS, 'white', 'idle', 120, back=cape
                ) as dressed:
                    # A short cape must not create a second lower silhouette
                    # beneath the cat's existing cropped body.
                    plain_alpha = plain.getchannel('A').crop((0, 104, 120, 120)).point(
                        lambda alpha: 255 if alpha > 0 else 0
                    )
                    cape_alpha = dressed.getchannel('A').crop((0, 104, 120, 120)).point(
                        lambda alpha: 255 if alpha >= 128 else 0
                    )
                    self.assertIsNone(ImageChops.subtract(cape_alpha, plain_alpha).getbbox())

                    # The fastening is foreground neckwear, so it remains
                    # visible over the body while staying below the mouth.
                    self.assertNotEqual(
                        plain.crop((36, 76, 84, 96)).tobytes(),
                        dressed.crop((36, 76, 84, 96)).tobytes(),
                    )

    def test_collar_wraps_to_each_body_edge_without_widening_the_silhouette(self):
        for variant in CAT_VARIANTS:
            for pose in art.POSE_NAMES:
                for size in (72, 120, 210):
                    with self.subTest(variant=variant, pose=pose, size=size):
                        with art.load_frame(ASSETS, variant, pose, size) as plain, art.load_frame(
                            ASSETS, variant, pose, size, neck='bell-collar'
                        ) as dressed:
                            # The collar must stay inside the cat's existing outer
                            # contour; only its bell may hang below the body.
                            region = (0, round(68 * size / 120), size, round(94 * size / 120))
                            # Compositing can strengthen existing antialiased
                            # edge pixels; it must not create new opaque corners.
                            plain_shape = plain.getchannel('A').crop(region).point(lambda alpha: 255 if alpha > 0 else 0)
                            dressed_shape = dressed.getchannel('A').crop(region).point(lambda alpha: 255 if alpha >= 128 else 0)
                            self.assertIsNone(ImageChops.subtract(dressed_shape, plain_shape).getbbox())

                            # At neck height, the teal band reaches both sides,
                            # rather than ending in the middle of the chest.
                            y = round(77 * size / 120)
                            opaque = [x for x in range(size) if plain.getpixel((x, y))[3] >= 128]
                            inset = max(1, round(3 * size / 120))
                            for x in (opaque[0] + inset, opaque[-1] - inset):
                                red, green = dressed.getpixel((x, y))[:2]
                                self.assertGreater(green, red + 20)

    def test_new_slots_change_pixels_and_cache_independently(self):
        self.assertIn('neck', inspect.signature(art.load_frame).parameters)
        source = art.frame_source_path(ASSETS, 'white', 'idle')
        plain = art.vector_png(source, 'idle', 120)
        choices = ({'neck': 'bow-tie'}, {'back': 'angel-wings'}, {'ears': 'sunflower-clip'})
        images = [art.vector_png(source, 'idle', 120, **choice) for choice in choices]
        self.assertEqual(len(set([plain, *images])), 4)
        for choice, result in zip(choices, images):
            self.assertIs(result, art.vector_png(source, 'idle', 120, **choice))

    def test_back_neck_and_ears_render_in_their_intended_layers(self):
        self.assertIn('neck', inspect.signature(art.posed_svg).parameters)
        source = art.frame_source_path(ASSETS, 'white', 'idle')
        root = ET.fromstring(art.posed_svg(source, 'idle', back='angel-wings',
                                         neck='bow-tie', ears='sunflower-clip', hat='beanie'))
        ids = [node.get('id') for node in root.iter()]
        self.assertLess(ids.index('accessory-back'), ids.index('body'))
        self.assertLess(ids.index('body'), ids.index('accessory-neck'))
        self.assertLess(ids.index('accessory-neck'), ids.index('paw-left'))
        self.assertLess(ids.index('accessory-hat'), ids.index('accessory-ears'))

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
        for accessory_id in (item.id for item in ACCESSORIES):
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

        outfits = ({item.slot: item.id} for item in ACCESSORIES)
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

    def test_new_items_render_across_cats_poses_and_sizes_without_covering_face(self):
        for item in ACCESSORIES:
            if item.slot in {'hat', 'glasses'}:
                continue
            for variant in CAT_VARIANTS:
                for pose in art.POSE_NAMES:
                    for size in (72, 120, 210):
                        with self.subTest(item=item.id, cat=variant, pose=pose, size=size):
                            with art.load_frame(ASSETS, variant, pose, size) as plain, art.load_frame(
                                ASSETS, variant, pose, size, **{item.slot: item.id}
                            ) as dressed:
                                self.assertNotEqual(plain.tobytes(), dressed.tobytes())
                                face = tuple(round(value * size / 120) for value in (36, 50, 84, 76))
                                self.assertEqual(plain.crop(face).tobytes(), dressed.crop(face).tobytes())

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
