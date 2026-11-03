import tkinter as tk
import unittest

from ui_surfaces import RoundedAction, render_soft_pill


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


if __name__ == "__main__":
    unittest.main()
