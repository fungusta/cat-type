import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

import cat_type
from cat_artwork import BASE_SIZE, POSE_NAMES
from cat_settings import CAT_VARIANTS
from scripts.preview_svg_cat import PreviewWindow, classify_tk_key, export_preview


class PreviewTests(unittest.TestCase):
    def test_preview_launch_bypasses_overlay_instance_and_saved_settings(self):
        with (
            patch.object(sys, "argv", ["cat_type.py", "--preview-cats"]),
            patch("scripts.preview_svg_cat.run_preview") as show,
            patch.object(
                cat_type,
                "acquire_single_instance",
                side_effect=AssertionError("preview must coexist"),
            ),
            patch.object(
                cat_type.SettingsStore,
                "load",
                side_effect=AssertionError("preview must not use settings"),
            ),
        ):
            cat_type.main()
        show.assert_called_once_with()

    def test_export_writes_all_posed_svgs_and_six_row_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            export_dir = Path(directory)
            export_preview(export_dir)

            expected = {
                f"{variant}-{pose}.svg"
                for variant in CAT_VARIANTS
                for pose in POSE_NAMES
            }
            self.assertEqual(
                {path.name for path in export_dir.glob("*.svg")}, expected
            )
            preview = export_dir / "preview.png"
            self.assertTrue(preview.is_file())
            with Image.open(preview) as image:
                self.assertEqual(image.mode, "RGB")
                self.assertGreaterEqual(image.width, 4 * BASE_SIZE)
                self.assertGreaterEqual(image.height, 6 * BASE_SIZE)

    def test_tk_keys_use_portable_keyboard_classification(self):
        cases = (
            ("Return", "\r", "right"),
            ("Control_L", "", "left"),
            ("Control_R", "", "right"),
            ("KP_1", "1", "right"),
            ("KP_Add", "+", "right"),
            ("Escape", "\x1b", "left"),
            ("Prior", "", "right"),
            ("Next", "", "right"),
            ("BackSpace", "\x08", "right"),
            ("Shift_L", "", "left"),
            ("Shift_R", "", "right"),
            ("space", " ", "both"),
            ("q", "Q", "left"),
            ("p", "P", "right"),
        )
        for keysym, char, expected in cases:
            with self.subTest(keysym=keysym):
                event = SimpleNamespace(keysym=keysym, char=char)
                self.assertEqual(classify_tk_key(event), expected)

    def test_manual_poses_override_keyboard_state_and_resize_the_cat(self):
        try:
            preview = PreviewWindow()
        except tk.TclError as error:
            self.skipTest(f"Tk display unavailable: {error}")
        try:
            for _ in range(6):
                preview.on_key(SimpleNamespace(char="q", keysym="q"))
            self.assertEqual(preview.pose_text.get(), "excited")
            for pose in POSE_NAMES:
                preview.show_pose(pose)
                self.assertEqual(preview.pose_text.get(), pose)
                self.assertIsNone(preview._idle_after)
                self.assertEqual(
                    (preview.image.width(), preview.image.height()), (120, 120)
                )
            preview.size_percent.set(175)
            preview.render("tap-right")
            self.assertEqual(
                (preview.image.width(), preview.image.height()), (210, 210)
            )
        finally:
            preview.root.destroy()

    def test_cat_switch_updates_image_without_resetting_pose_or_size(self):
        try:
            preview = PreviewWindow()
        except tk.TclError as error:
            self.skipTest(f"Tk display unavailable: {error}")
        try:
            self.assertEqual(preview.cat.get(), "White")
            preview.size_percent.set(175)
            preview.show_pose("tap-left")
            white_image = preview.root.tk.call(
                str(preview.image), "data", "-format", "ppm"
            )

            preview.cat.set("Ginger tabby")
            preview.root.update()
            ginger_image = preview.root.tk.call(
                str(preview.image), "data", "-format", "ppm"
            )

            self.assertEqual(preview.pose_text.get(), "tap-left")
            self.assertEqual(preview.size_percent.get(), 175)
            self.assertEqual(
                (preview.image.width(), preview.image.height()), (210, 210)
            )
            self.assertNotEqual(ginger_image, white_image)
        finally:
            preview.root.destroy()


if __name__ == "__main__":
    unittest.main()
