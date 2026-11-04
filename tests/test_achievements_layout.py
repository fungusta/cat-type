import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from cat_accessories import ACCESSORY_BY_ID
from cat_settings import AppSettings
from settings_window import SettingsWindow
from usage_metrics import UsageMetrics


ASSETS = Path(__file__).resolve().parents[1] / "assets"


class AchievementLayoutTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.root.withdraw()
        self.addCleanup(self.root.destroy)

    def window(self):
        window = SettingsWindow(
            self.root, AppSettings(cat_style="white"), lambda _settings: None,
            str(ASSETS / "cat-type.png"), usage_metrics=UsageMetrics(total_keystrokes=640),
        )
        self.addCleanup(window.close)
        window.window.minsize(1, 1)
        window.page_buttons["Achievements"].invoke()
        window.window.update()
        return window

    def assert_inside(self, child, container):
        self.assertGreaterEqual(child.winfo_rootx(), container.winfo_rootx(), str(child))
        self.assertLessEqual(child.winfo_rootx() + child.winfo_width(),
                             container.winfo_rootx() + container.winfo_width(), str(child))
        self.assertGreaterEqual(child.winfo_rooty(), container.winfo_rooty(), str(child))
        self.assertLessEqual(child.winfo_rooty() + child.winfo_height(),
                             container.winfo_rooty() + container.winfo_height(), str(child))

    def assert_drawing_inside(self, canvas):
        width, height = canvas.winfo_width(), canvas.winfo_height()
        for item in canvas.find_all():
            x1, y1, x2, y2 = canvas.bbox(item)
            label = canvas.itemcget(item, "text") if canvas.type(item) == "text" else canvas.type(item)
            self.assertGreaterEqual(x1, -1, label)
            self.assertGreaterEqual(y1, -1, label)
            self.assertLessEqual(x2, width + 1, label)
            self.assertLessEqual(y2, height + 1, label)

    def test_high_scaling_album_copy_fits_at_compact_and_wide_widths(self):
        original_scaling = self.root.tk.call("tk", "scaling")
        self.root.tk.call("tk", "scaling", 2.5)
        self.addCleanup(lambda: self.root.tk.call("tk", "scaling", original_scaling))
        window = self.window()
        view = window.achievements
        view.mark_new((ACCESSORY_BY_ID["ribbon-clip"],))
        for width in (920, 620, 600, 920):
            with self.subTest(width=width):
                window.window.geometry(f"{width}x700")
                window.window.update()
                self.assert_inside(view.summary_label, view.album_heading)
                self.assert_inside(view.album_title, view.album_heading)
                for card in (*view.cards.values(), view.up_next_card):
                    self.assert_drawing_inside(card)
                    self.assert_inside(card, view.album_shelf)
                for button in view.filter_buttons.values():
                    self.assert_inside(button, view.album_shelf)
                self.assertGreaterEqual(view.album_shelf.winfo_height(),
                                        view.album_shelf.content.winfo_reqheight() + 20)
                bounds = window.scroll_canvas.bbox("all")
                shelf_bottom = (view.album_shelf.winfo_rooty() - window.scroll_canvas.winfo_rooty()
                                + window.scroll_canvas.canvasy(0) + view.album_shelf.winfo_height())
                self.assertLessEqual(shelf_bottom, bounds[3])

    def test_long_title_wraps_clear_of_the_new_badge(self):
        window = self.window()
        window.window.geometry("620x700")
        view = window.achievements
        card = view.cards["ribbon-clip"]
        plain = card.required_height(card.winfo_width())
        view.mark_new((ACCESSORY_BY_ID["ribbon-clip"],))
        window.window.update()
        title = next(item for item in card.find_all()
                     if card.type(item) == "text" and card.itemcget(item, "text") == "A Little Flair")
        new = next(item for item in card.find_all()
                   if card.type(item) == "text" and card.itemcget(item, "text") == "NEW")
        self.assertLessEqual(card.bbox(title)[2], card.bbox(new)[0])
        self.assertGreaterEqual(card.required_height(card.winfo_width()), plain)
        self.assert_drawing_inside(card)

    def test_cramped_cards_stack_the_copy_under_the_thumbnail(self):
        window = self.window()
        card = window.achievements.cards["ribbon-clip"]
        self.assertFalse(card._stacked(600))
        self.assertTrue(card._stacked(card._thumbnail + 60))
        self.assertEqual(card._copy_width(card._thumbnail + 60), card._thumbnail + 60 - 4 - card.PAD * 2)
        self.assertGreater(card.required_height(card._thumbnail + 60), card.required_height(600))

    def test_stable_width_sets_columns_without_invalidating_scrollbar_latch(self):
        window = self.window()
        view = window.achievements
        with patch.object(view, "_responsive_width", return_value=519) as stable_width, \
             patch.object(view.cards_area, "winfo_width", return_value=535), \
             patch.object(view, "_on_content_change") as changed:
            view._layout_key = None
            view._layout_cards()
            stable_width.assert_called_with(535)
            self.assertEqual({int(card.grid_info()["column"]) for card in view.cards.values()}, {0})
            changed.assert_not_called()


if __name__ == "__main__":
    unittest.main()
