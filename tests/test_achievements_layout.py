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

    def test_high_scaling_album_copy_and_pager_fit_at_compact_and_wide_widths(self):
        original_scaling = self.root.tk.call("tk", "scaling")
        self.root.tk.call("tk", "scaling", 2.5)
        self.addCleanup(lambda: self.root.tk.call("tk", "scaling", original_scaling))
        window = self.window()
        view = window.achievements
        for width in (920, 620, 600, 920):
            with self.subTest(width=width):
                window.window.geometry(f"{width}x700")
                view.show_page(0)
                view.mark_new((ACCESSORY_BY_ID["ribbon-clip"],))
                window.window.update()
                badge = view.new_badges["ribbon-clip"]
                title = next(child for child in badge.master.winfo_children()
                             if isinstance(child, tk.Label))
                title.configure(text="A very long achievement title that wraps beside its new badge")
                window.window.update()
                self.assertTrue(badge.winfo_ismapped())
                if int(badge.grid_info()["row"]) == 0:
                    self.assertLessEqual(title.winfo_rootx() + title.winfo_width(), badge.winfo_rootx())
                else:
                    self.assertLessEqual(title.winfo_rooty() + title.winfo_height(), badge.winfo_rooty())
                self.assert_inside(view.summary_label, view.album_heading)
                self.assert_inside(view.album_title, view.album_heading)
                for card in view.cards.values():
                    pending = list(card.winfo_children())
                    while pending:
                        child = pending.pop()
                        pending.extend(child.winfo_children())
                        if not child.winfo_ismapped():
                            continue
                        self.assert_inside(child, card)
                        if isinstance(child, tk.Label) and child.cget("text"):
                            self.assertLessEqual(child.winfo_reqwidth(), child.winfo_width(),
                                                 str(child.cget("text")))
                pager = view.pagination_controls
                for child in (pager.previous_button, pager.page_label, pager.next_button):
                    self.assert_inside(child, pager)
                self.assert_inside(pager, view.album_shelf)
                self.assertGreaterEqual(view.album_shelf.winfo_height(),
                                        view.album_shelf.content.winfo_reqheight() + 20)
                bounds = window.scroll_canvas.bbox("all")
                shelf_bottom = (view.album_shelf.winfo_rooty() - window.scroll_canvas.winfo_rooty()
                                + window.scroll_canvas.canvasy(0) + view.album_shelf.winfo_height())
                self.assertLessEqual(shelf_bottom, bounds[3])

    def test_stable_width_changes_page_size_without_invalidating_scrollbar_latch(self):
        window = self.window()
        view = window.achievements
        with patch.object(view, "_responsive_width", return_value=519) as stable_width, \
             patch.object(view.cards_area, "winfo_width", return_value=535), \
             patch.object(view, "_on_content_change") as changed:
            view._page_size = 4
            view._layout_cards()
            stable_width.assert_called_with(535)
            self.assertEqual(view._page_size, 2)
            self.assertEqual(len(view.cards), 2)
            changed.assert_not_called()
            view.show_page(1)
            changed.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
