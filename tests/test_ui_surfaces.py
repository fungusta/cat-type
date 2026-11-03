import tkinter as tk
import unittest
from unittest.mock import patch

import ui_surfaces
from ui_surfaces import MOTION_FAST_MS, RoundedAction, Tween, render_soft_pill


class SoftPillTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.configure(background="#FFF9F3")
        self.addCleanup(self.root.destroy)

    def test_renders_widths_narrower_than_the_pill_margins(self):
        # Tk reports 1px widths during the first layout passes; the shared
        # renderer must not hand Pillow an inverted rectangle.
        for width in range(1, 20):
            for state in ({}, {"pressed": True}, {"focused": True}, {"disabled": True}):
                with self.subTest(width=width, state=state):
                    image = render_soft_pill(self.root, "#FFF9F3", width, 34, "#FFFFFF", **state)
                    self.assertEqual((image.width(), image.height()), (width, 34))

    def test_action_survives_a_one_pixel_layout_pass(self):
        action = RoundedAction(self.root, text="Progress →", command=lambda: None)
        action.pack()
        action.fit_width(1)
        self.root.update()
        self.assertGreaterEqual(action.winfo_reqwidth(), 1)


class ShelfFaceTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.addCleanup(self.root.destroy)

    def test_corner_slicing_matches_a_full_supersampled_face(self):
        from PIL import ImageChops
        panel = ui_surfaces.RoundedPanel(self.root, background="#FFF9F2",
                                         fill="#FFFFFF", border="#E8E1DA", radius=20)
        for focused in (False, True):
            panel._focused = focused
            for width, height in ((661, 704), (185, 437), (40, 30)):
                box = (2, 1, width - 2, height - 4)
                radius = min(20, max(1, min(box[2] - box[0], box[3] - box[1]) // 2))
                with self.subTest(focused=focused, size=(width, height)):
                    sliced = panel._render_face(width, height, box, radius)
                    full = panel._paint_face(width, height, box, radius)
                    self.assertIsNone(ImageChops.difference(sliced, full).getbbox())

    def test_tall_shelves_supersample_only_the_corners(self):
        panel = ui_surfaces.RoundedPanel(self.root, background="#FFF9F2",
                                         fill="#FFFFFF", border="#E8E1DA", radius=20)
        sizes = []
        original = panel._paint_face
        def record(width, height, box, radius):
            sizes.append((width, height))
            return original(width, height, box, radius)
        with patch.object(panel, "_paint_face", side_effect=record):
            panel._render_face(661, 2000, (2, 1, 659, 1996), 20)
        self.assertEqual(len(sizes), 1)
        self.assertLess(sizes[0][0] * sizes[0][1], 100 * 100)


class TweenTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.geometry("120x60+40+40")
        self.addCleanup(self.root.destroy)
        self.frames = []
        self.root.update()

    def test_mapped_widgets_ease_toward_the_target(self):
        with patch.object(ui_surfaces, "prefers_reduced_motion", return_value=False):
            tween = Tween(self.root, self.frames.append)
            tween.to(1.0)
            self.assertLess(tween.value, 1.0)
            self.root.after(MOTION_FAST_MS + 40)
            self.root.update()
        self.assertEqual(tween.value, 1.0)
        self.assertEqual(self.frames[-1], 1.0)

    def test_reduced_motion_jumps_straight_to_the_target(self):
        with patch.object(ui_surfaces, "prefers_reduced_motion", return_value=True):
            tween = Tween(self.root, self.frames.append)
            tween.to(1.0)
        self.assertEqual(self.frames, [1.0])

    def test_hover_on_a_disabled_action_stays_at_rest(self):
        action = RoundedAction(self.root, text="Next page", command=lambda: None,
                               state="disabled")
        action.pack()
        self.root.update()
        action.event_generate("<Enter>")
        self.root.after(MOTION_FAST_MS + 40)
        self.root.update()
        self.assertEqual(action._hover.value, 0.0)


if __name__ == "__main__":
    unittest.main()
