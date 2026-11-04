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


class RewardMarkTests(unittest.TestCase):
    def test_progress_bar_fills_its_share_and_keeps_a_rounded_sliver(self):
        from ui_surfaces import BUTTON_ACCENT, PROGRESS_TRACK
        from PIL import ImageColor

        accent = ImageColor.getrgb(BUTTON_ACCENT)
        track = ImageColor.getrgb(PROGRESS_TRACK)
        half = ui_surfaces.progress_bar_image("#FFFFFF", 100, 8, 0.5)
        self.assertEqual(half.size, (100, 8))
        self.assertEqual(half.getpixel((25, 4)), accent)
        self.assertEqual(half.getpixel((75, 4)), track)
        empty = ui_surfaces.progress_bar_image("#FFFFFF", 100, 8, 0)
        self.assertEqual(empty.getpixel((4, 4)), track)
        # A tiny share still draws a full-height cap rather than a dot.
        sliver = ui_surfaces.progress_bar_image("#FFFFFF", 100, 8, 0.001)
        self.assertEqual(sliver.getpixel((4, 4)), accent)
        self.assertIs(half, ui_surfaces.progress_bar_image("#FFFFFF", 100, 8, 0.5))

    def test_status_marks_differ_and_blend_into_their_surface(self):
        check = ui_surfaces.status_mark_image("#FFF1B8", 20, "check")
        lock = ui_surfaces.status_mark_image("#FFF1B8", 20, "lock")
        self.assertEqual(check.size, (20, 20))
        self.assertNotEqual(check.tobytes(), lock.tobytes())
        self.assertEqual(check.getpixel((0, 0)), (255, 241, 184))

    def test_faded_art_is_grey_and_keeps_transparency(self):
        from PIL import Image

        art = Image.new("RGBA", (4, 4), (255, 0, 0, 0))
        art.putpixel((1, 1), (220, 40, 40, 255))
        faded = ui_surfaces.faded_art(art)
        red, green, blue, alpha = faded.getpixel((1, 1))
        self.assertEqual(red, green)
        self.assertEqual(green, blue)
        self.assertEqual(alpha, 255)
        self.assertEqual(faded.getpixel((0, 0))[3], 0)

    def test_navigation_icons_are_distinct_and_transparent(self):
        icons = {kind: ui_surfaces.nav_icon_image(kind, 20)
                 for kind in ("settings", "metrics", "wardrobe", "achievements")}
        self.assertEqual(len({image.tobytes() for image in icons.values()}), 4)
        for image in icons.values():
            self.assertEqual(image.size, (20, 20))
            self.assertEqual(image.getpixel((0, 19))[3], 0)

    def test_icon_choice_keeps_its_plain_label_and_variable(self):
        root = tk.Tk()
        self.addCleanup(root.destroy)
        rail = tk.Frame(root, background="#FFFFFF")
        selected = tk.StringVar(master=root, value="Metrics")
        label = tk.StringVar(master=root, value="Metrics")
        plain = ui_surfaces.RoundedChoice(rail, text="Metrics", variable=selected, value="Metrics")
        icon = ui_surfaces.RoundedChoice(rail, textvariable=label, variable=selected,
                                         value="Metrics", icon="metrics")
        self.assertEqual(icon.cget("text"), "Metrics")
        self.assertEqual(icon["text"], "Metrics")
        self.assertEqual(icon.cget("textvariable"), str(label))
        self.assertGreater(icon._size[0], plain._size[0])
        # The visible label follows the caller's variable.
        label.set("Metrics · New")
        self.assertEqual(icon.cget("text"), "Metrics · New")
        self.assertTrue(str(super(ui_surfaces.RoundedChoice, icon).cget("text")).endswith("Metrics · New"))

    def test_choices_wrap_into_rows_without_sharing_column_widths(self):
        root = tk.Tk()
        self.addCleanup(root.destroy)
        bar = tk.Frame(root, background="#FFFFFF")
        bar.pack(fill="x")
        variable = tk.StringVar(master=root)
        labels = ("All", "A much longer choice", "Mid", "Short")
        buttons = [ui_surfaces.RoundedChoice(bar, text=label, variable=variable, value=label,
                                             indicatoron=False) for label in labels]
        width = buttons[0]._size[0] + buttons[1]._size[0] + 6
        ui_surfaces.flow_choices(bar, buttons, width)
        root.update()
        rows = {}
        for button in buttons:
            rows.setdefault(button.winfo_y(), []).append(button)
            self.assertLessEqual(button.winfo_x() + button.winfo_reqwidth(), width + 1)
        self.assertGreater(len(rows), 1)
        # Each wrapped row starts flush left, whatever the row above holds.
        self.assertTrue(all(min(button.winfo_x() for button in row) == 0 for row in rows.values()))
        self.assertGreaterEqual(bar.winfo_reqheight(), max(rows) + buttons[0].winfo_reqheight())


if __name__ == "__main__":
    unittest.main()
