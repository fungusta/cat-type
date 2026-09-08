import tkinter as tk
import unittest
from pathlib import Path

from PIL import ImageTk

from cat_settings import AppSettings
from settings_window import SettingsWindow
from usage_metrics import UsageMetrics
from cat_accessories import ACCESSORY_BY_ID
from wardrobe_view import WardrobeView
import inspect


ASSETS = Path(__file__).resolve().parents[1] / 'assets'


class WardrobeTests(unittest.TestCase):
    def test_secrets_and_their_items_are_absent_from_both_tabs_and_totals(self):
        self.assertIn('slots', inspect.signature(WardrobeView).parameters)
        window = self.window()
        hidden = {'angel-wings', 'moon-pendant', 'sunflower-clip', 'cozy-scarf', 'beta-bandana'}
        self.assertFalse(hidden & window.wardrobe.buttons.keys())
        self.assertFalse(hidden & window.achievements.cards.keys())
        self.assertIn('0 of 10', window.achievements.summary.get())
        self.assertNotIn('ears', window.wardrobe.none_buttons)
        self.assertIn('bow-tie', window.wardrobe.buttons)

    def test_live_secret_reveal_keeps_pending_choices_and_supports_all_slots(self):
        self.assertIn('slots', inspect.signature(WardrobeView).parameters)
        window = self.window({'crown', 'round-glasses'})
        window.wardrobe.buttons['crown'].invoke()
        window.wardrobe.buttons['round-glasses'].invoke()
        new_ids = {'beta-bandana', 'angel-wings', 'sunflower-clip'}
        window.update_achievements({'crown', 'round-glasses'} | new_ids,
                                   tuple(ACCESSORY_BY_ID[item] for item in sorted(new_ids)))
        window.window.update()
        self.assertEqual((window.hat.get(), window.glasses.get()), ('crown', 'round-glasses'))
        self.assertIn('5 of 13', window.achievements.summary.get())
        for item_id in new_ids:
            self.assertIn(item_id, window.achievements.cards)
            window.wardrobe.buttons[item_id].invoke()
        plain = ImageTk.getimage(window._preview_frames['white']['idle']).tobytes()
        window.page_buttons['Achievements'].invoke()
        window.page_buttons['Wardrobe'].invoke()
        window.window.update()
        self.assertEqual(ImageTk.getimage(window._preview_frames['white']['idle']).tobytes(), plain)
        window._save()
        self.assertEqual(self.saved[0].outfit(), {'hat': 'crown', 'glasses': 'round-glasses',
                                               'neck': 'beta-bandana', 'back': 'angel-wings', 'ears': 'sunflower-clip'})

    def test_new_slots_none_and_cancel_preserve_saved_outfit(self):
        self.assertIn('slots', inspect.signature(WardrobeView).parameters)
        window = self.window({'beta-bandana', 'angel-wings', 'sunflower-clip'},
                             neck='beta-bandana', back='angel-wings', ears='sunflower-clip')
        window.wardrobe.none_buttons['neck'].invoke()
        self.assertEqual((window.neck.get(), window.back.get(), window.ears.get()), ('none', 'angel-wings', 'sunflower-clip'))
        window.close()
        self.assertEqual(self.saved, [])

    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.saved = []

    def window(self, unlocked=(), **settings):
        self.assertIn('unlocked_accessories', SettingsWindow.__init__.__annotations__, 'Settings must accept unlocked rewards')
        window = SettingsWindow(
            self.root, AppSettings(cat_style='white', **settings), self.saved.append,
            str(ASSETS / 'cat-type.png'), unlocked_accessories=set(unlocked),
            usage_metrics=UsageMetrics(total_keystrokes=640),
        )
        self.addCleanup(window.close)
        window.page_buttons['Wardrobe'].invoke()
        window.window.update()
        return window

    def test_locked_items_link_to_separate_achievement_and_cannot_be_equipped(self):
        window = self.window()
        self.assertIn('Achievements', window.page_buttons)
        wardrobe = window.wardrobe
        self.assertEqual(wardrobe.buttons['round-glasses'].cget('state'), 'disabled')
        self.assertEqual(wardrobe.status_text['round-glasses'].get(), 'Locked')
        wardrobe.buttons['round-glasses'].invoke()
        self.assertEqual(window.glasses.get(), 'none')
        self.assertTrue(wardrobe.winfo_ismapped())
        wardrobe.achievement_links['round-glasses'].invoke()
        window.window.update()
        self.assertEqual(window.active_page.get(), 'Achievements')
        self.assertFalse(wardrobe.winfo_ismapped())
        self.assertTrue(window.achievements.winfo_ismapped())
        self.assertIn('640 / 1,000', window.achievements.progress_text['round-glasses'].get())

    def test_achievement_link_reveals_reward_below_fold(self):
        window = self.window()
        self.assertIn('Achievements', window.page_buttons)
        window.window.minsize(1, 1)
        window.window.geometry('620x500')
        window.window.update()
        window.wardrobe.achievement_links['crown'].invoke()
        window.window.update()
        card = window.achievements.cards['crown']
        top = card.winfo_rooty() - window.scroll_canvas.winfo_rooty()
        self.assertGreaterEqual(top, 0)
        self.assertLess(top + card.winfo_height(), window.scroll_canvas.winfo_height())
        self.assertEqual(window.window.focus_get(), card)

    def test_shared_outfit_updates_real_preview_and_is_saved(self):
        window = self.window({'round-glasses', 'crown'})
        plain = ImageTk.getimage(window._preview_frames['white']['idle']).tobytes()
        window.wardrobe.buttons['round-glasses'].invoke()
        window.wardrobe.buttons['crown'].invoke()
        self.assertIn('Achievements', window.page_buttons)
        window.page_buttons['Achievements'].invoke()
        window.page_buttons['Wardrobe'].invoke()
        window.window.update_idletasks()
        dressed = ImageTk.getimage(window._preview_frames['white']['idle']).tobytes()
        self.assertNotEqual(plain, dressed)
        self.assertEqual((window.hat.get(), window.glasses.get()), ('crown', 'round-glasses'))
        window._save()
        self.assertEqual((self.saved[0].hat, self.saved[0].glasses), ('crown', 'round-glasses'))

    def test_none_removes_one_slot_and_cancel_discards_changes(self):
        window = self.window({'round-glasses', 'crown'}, hat='crown', glasses='round-glasses')
        window.wardrobe.none_buttons['hat'].invoke()
        self.assertEqual((window.hat.get(), window.glasses.get()), ('none', 'round-glasses'))
        self.assertIn('Achievements', window.page_buttons)
        window.page_buttons['Achievements'].invoke()
        window.window.update_idletasks()
        window.close()
        self.assertEqual(self.saved, [])

    def test_live_unlock_enables_reward_without_equipping_or_reopening(self):
        window = self.window()
        self.assertIn('Achievements', window.page_buttons)
        window.page_buttons['Achievements'].invoke()
        from cat_accessories import ACCESSORY_BY_ID
        window.update_usage_metrics(UsageMetrics(total_keystrokes=900))
        self.assertIn('900 / 1,000', window.achievements.progress_text['round-glasses'].get())
        window.update_usage_metrics(UsageMetrics(total_keystrokes=1000))
        window.update_achievements({'round-glasses'}, (ACCESSORY_BY_ID['round-glasses'],))
        self.assertEqual(window.achievements.progress_text['round-glasses'].get(), 'Unlocked')
        self.assertEqual(window.wardrobe.buttons['round-glasses'].cget('state'), 'normal')
        self.assertEqual(window.wardrobe.status_text['round-glasses'].get(), 'Unlocked')
        self.assertEqual(window.glasses.get(), 'none')
        self.assertIn('Round glasses', window.wardrobe.notice.get())
        window.page_buttons['Wardrobe'].invoke()
        window.wardrobe.buttons['round-glasses'].invoke()
        self.assertEqual(window.glasses.get(), 'round-glasses')
        window.window.update_idletasks()

    def test_locked_saved_or_programmatic_selection_is_not_saved(self):
        window = self.window(hat='crown')
        self.assertEqual(window.hat.get(), 'none')
        window.glasses.set('sunglasses')
        window._save()
        self.assertEqual(self.saved[0].glasses, 'none')

    def test_wardrobe_fits_narrow_width_and_switches_pages(self):
        window = self.window()
        window.window.minsize(1, 1)
        window.window.geometry('620x500')
        window.window.update()
        self.assertLessEqual(window.wardrobe.winfo_reqwidth(), window.scroll_canvas.winfo_width())
        self.assertIn('Achievements', window.page_buttons)
        for page in ('Metrics', 'Settings', 'Achievements', 'Wardrobe'):
            window.page_buttons[page].invoke()
            window.window.update()
            self.assertEqual(bool(window.wardrobe.winfo_ismapped()), page == 'Wardrobe')
            self.assertEqual(bool(window.achievements.winfo_ismapped()), page == 'Achievements')
            self.assertLessEqual(window.achievements.winfo_reqwidth(), window.scroll_canvas.winfo_width() - 52)
            last_tab = window.page_buttons['Achievements']
            self.assertLessEqual(last_tab.winfo_rootx() + last_tab.winfo_width(),
                                 window.scroll_canvas.winfo_rootx() + window.scroll_canvas.winfo_width())


if __name__ == '__main__':
    unittest.main()
