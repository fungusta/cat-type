import tkinter as tk
import unittest
from unittest.mock import patch
from pathlib import Path

from PIL import ImageTk

from cat_settings import AppSettings
from settings_window import SettingsWindow
from usage_metrics import UsageMetrics
from cat_accessories import ACCESSORY_BY_ID, ACCESSORY_SLOTS, visible_accessories
from wardrobe_view import AccessoryTile, WardrobeView, TRY_ON_RESTORE_MS
from achievements_view import RewardEntry
from ui_surfaces import RoundedPanel, RoundedChoice
import inspect


ASSETS = Path(__file__).resolve().parents[1] / 'assets'
HIDDEN = {'angel-wings', 'moon-pendant', 'sunflower-clip', 'cozy-scarf',
          'beta-bandana', 'shooting-star-clip', 'sunrise-scarf', 'butterfly-wings'}


def drawn_text(canvas: tk.Canvas) -> list[str]:
    return [canvas.itemcget(item, 'text') for item in canvas.find_all() if canvas.type(item) == 'text']


class WardrobeTests(unittest.TestCase):
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

    def assert_drawing_inside(self, canvas: tk.Canvas) -> None:
        """Every text and badge on a drawn card stays within its canvas."""
        width, height = canvas.winfo_width(), canvas.winfo_height()
        for item in canvas.find_all():
            x1, y1, x2, y2 = canvas.bbox(item)
            with self.subTest(canvas=str(canvas), item=canvas.itemcget(item, 'text')
                              if canvas.type(item) == 'text' else canvas.type(item)):
                self.assertGreaterEqual(x1, -1)
                self.assertGreaterEqual(y1, -1)
                self.assertLessEqual(x2, width + 1)
                self.assertLessEqual(y2, height + 1)

    # Locker ----------------------------------------------------------------

    def test_every_visible_accessory_has_one_canvas_tile_grouped_by_slot(self):
        window = self.window({'crown'})
        view = window.wardrobe
        self.assertEqual(set(view.tiles), {item.id for item in visible_accessories({'crown'})})
        self.assertEqual(set(view.none_tiles), set(ACCESSORY_SLOTS))
        for item_id, tile in view.tiles.items():
            self.assertIsInstance(tile, AccessoryTile)
            # One native window per tile keeps the whole tray cheap to build.
            self.assertEqual(tile.winfo_children(), [])
            self.assertIs(tile.master, view._section_grids[ACCESSORY_BY_ID[item_id].slot])
            self.assertTrue(tile.winfo_ismapped())
        self.assertIsInstance(view.tray_shelf, RoundedPanel)
        self.assertEqual(view.tray_shelf._radius, 18)
        self.assertTrue(all(isinstance(button, RoundedChoice) for button in view.filter_buttons.values()))

    def test_filter_shows_one_slot_and_focus_returns_to_all(self):
        window = self.window()
        view = window.wardrobe
        with patch.object(view, '_on_content_change') as changed:
            view.filter_buttons['hat'].invoke()
            changed.assert_called_once_with()
        window.window.update()
        self.assertEqual([slot for slot, section in view.sections.items() if section.winfo_ismapped()], ['hat'])
        self.assertFalse(view.tiles['round-glasses'].winfo_ismapped())
        tile = view.focus_item('round-glasses')
        window.window.update()
        self.assertEqual(view.filter.get(), 'all')
        self.assertTrue(tile.winfo_ismapped())
        self.assertIs(window.window.focus_get(), tile)

    def test_resizing_changes_columns_without_invalidating_scrollbar_latch(self):
        window = self.window()
        view = window.wardrobe
        window.window.minsize(1, 1)
        with patch.object(view, '_on_content_change') as changed:
            for geometry in ('920x800', '620x700', '920x800'):
                window.window.geometry(geometry)
                window.window.update()
            changed.assert_not_called()

        def columns():
            return {int(tile.grid_info()['column']) for tile in view.tiles.values()}

        window.window.geometry('920x800')
        window.window.update()
        wide = columns()
        window.window.geometry('620x700')
        window.window.update()
        self.assertGreater(len(wide), len(columns()))

    def test_scrollbar_gutter_does_not_change_column_count(self):
        window = self.window()
        view = window.wardrobe
        gutter = window.scrollbar.winfo_reqwidth()
        minimum = view._tile_minimum() + 10
        width = minimum * 3 + gutter - 1
        counts = set()
        for visible in (False, True, False):
            with patch.object(window.scrollbar, 'winfo_manager', return_value='pack' if visible else ''), \
                 patch.object(view.choices_area, 'winfo_width',
                              return_value=width - (gutter if visible else 0)):
                view._layout_key = None
                view._layout_tiles()
                counts.add(max(int(tile.grid_info()['column']) for tile in view.tiles.values()) + 1)
        self.assertEqual(len(counts), 1)

    def test_height_only_configure_does_not_regrid_tiles(self):
        window = self.window()
        view = window.wardrobe
        tile = view.tiles['crown']
        with patch.object(tile, 'grid', wraps=tile.grid) as regrid:
            for _ in range(5):
                view.choices_area.event_generate(
                    '<Configure>', width=view.choices_area.winfo_width(),
                    height=view.choices_area.winfo_height() + 1)
            regrid.assert_not_called()
        idle_ran = []
        window.window.after_idle(lambda: idle_ran.append(True))
        window.window.update_idletasks()
        self.assertEqual(idle_ran, [True])

    def test_tiles_show_equipped_unlocked_and_locked_progress(self):
        window = self.window({'round-glasses', 'crown'}, glasses='round-glasses')
        view = window.wardrobe
        window.window.update()
        self.assertEqual(view.tiles['round-glasses'].status, 'Equipped')
        # The fill and check mark say "worn"; earned tiles carry a blurb instead.
        self.assertEqual(drawn_text(view.tiles['round-glasses']),
                         ['Round glasses', 'For reading the fine print.'])
        self.assertEqual(view.tiles['crown'].status, 'Unlocked')
        self.assertEqual(drawn_text(view.tiles['crown']), ['Crown', 'Rules the keyboard kindly.'])
        self.assertNotIn(view.tiles['bow-tie'].blurb, drawn_text(view.tiles['bow-tie']))
        locked = view.tiles['ribbon-clip']
        self.assertEqual(locked.status, 'Locked')
        self.assertEqual(locked.progress, (250, 250))
        self.assertEqual(view.tiles['bow-tie'].progress, (640, 5000))
        self.assertIn('640 / 5,000', drawn_text(view.tiles['bow-tie']))
        self.assertIsNotNone(view.tiles['bow-tie']._faded)
        self.assertEqual(view.none_tiles['glasses'].status, 'Unlocked')
        self.assertEqual(view.none_tiles['hat'].status, 'Equipped')
        self.assertEqual(view.tray_count.get(), '2 of 22 unlocked')
        self.assertEqual(view.tiles['crown'].cget('accessible_name'), 'Crown, Unlocked')
        self.assertEqual(view.tiles['crown'].cget('accessible_role'), 'button')

    def test_locked_meters_follow_live_metrics_while_wardrobe_is_open(self):
        window = self.window()
        window.update_usage_metrics(UsageMetrics(total_keystrokes=4000))
        self.assertEqual(window.wardrobe.tiles['bow-tie'].progress, (4000, 5000))

    def test_high_scaling_tiles_and_headings_keep_all_copy_inside(self):
        original_scaling = self.root.tk.call('tk', 'scaling')
        self.root.tk.call('tk', 'scaling', 2.5)
        self.addCleanup(lambda: self.root.tk.call('tk', 'scaling', original_scaling))
        window = self.window({'round-glasses'}, glasses='round-glasses')
        window.window.minsize(1, 1)
        view = window.wardrobe
        view.update_unlocks({'round-glasses', 'angel-wings'}, (ACCESSORY_BY_ID['angel-wings'],))
        for geometry in ('600x700', '620x700', '920x800'):
            window.window.geometry(geometry)
            window.window.update()
            for tile in (*view.tiles.values(), *view.none_tiles.values()):
                self.assert_drawing_inside(tile)
                self.assertGreaterEqual(tile.winfo_height(), tile.required_height(tile.winfo_width()))
            shelf = view.tray_shelf
            for tile in view.tiles.values():
                self.assertLessEqual(tile.winfo_rootx() + tile.winfo_width(), shelf.winfo_rootx() + shelf.winfo_width())
            self.assertGreaterEqual(shelf.winfo_height(), shelf.content.winfo_reqheight() + 20)
            for button in view.filter_buttons.values():
                self.assertTrue(button.winfo_ismapped())
                self.assertLessEqual(button.winfo_rootx() + button.winfo_width(),
                                     view.filter_bar.winfo_rootx() + view.filter_bar.winfo_width())
            for child in view.tray_heading.winfo_children():
                self.assertLessEqual(child.winfo_reqwidth(), child.winfo_width() + 1)

    def test_new_badge_is_drawn_until_the_reward_is_worn(self):
        window = self.window()
        view = window.wardrobe
        self.assertFalse(any(tile.is_new for tile in view.tiles.values()))
        self.assertFalse(view.notice_label.winfo_manager())
        view.update_unlocks({'round-glasses'}, (ACCESSORY_BY_ID['round-glasses'],))
        window.window.update()
        tile = view.tiles['round-glasses']
        self.assertTrue(tile.is_new)
        self.assertIn('NEW', drawn_text(tile))
        self.assertIn('Round glasses', view.notice.get())
        self.assertTrue(view.notice_label.winfo_ismapped())
        tile.invoke()
        window.window.update()
        self.assertFalse(tile.is_new)
        self.assertNotIn('NEW', drawn_text(tile))
        self.assertEqual(window.glasses.get(), 'round-glasses')

    def test_mix_it_up_chooses_only_unlocked_and_clears_new_badges(self):
        window = self.window({'crown', 'round-glasses'})
        view = window.wardrobe
        view.update_unlocks({'crown', 'round-glasses', 'angel-wings'}, (ACCESSORY_BY_ID['angel-wings'],))
        view.mix_it_up()
        self.assertIn(window.hat.get(), {'none', 'crown'})
        self.assertIn(window.glasses.get(), {'none', 'round-glasses'})
        self.assertEqual(window.neck.get(), 'none')
        self.assertEqual(window.back.get(), 'angel-wings')
        self.assertNotIn('angel-wings', view._new_ids)
        self.assertEqual(view.tiles['angel-wings'].status, 'Equipped')

    def test_hiding_secrets_again_removes_their_tiles_and_focus_still_works(self):
        window = self.window({'angel-wings', 'beta-bandana'})
        view = window.wardrobe
        self.assertIn('angel-wings', view.tiles)
        old = view.tiles['angel-wings']
        view.update_unlocks(set())
        self.assertNotIn('angel-wings', view.tiles)
        self.assertFalse(old.winfo_exists())
        tile = view.focus_item('round-glasses')
        window.window.update()
        self.assertIs(window.window.focus_get(), tile)

    def test_secrets_and_their_items_are_absent_from_both_tabs_and_totals(self):
        self.assertIn('slots', inspect.signature(WardrobeView).parameters)
        window = self.window()
        window.page_buttons['Achievements'].invoke()
        window.page_buttons['Wardrobe'].invoke()
        window.window.update()
        self.assertFalse(HIDDEN & window.wardrobe.tiles.keys())
        self.assertFalse(HIDDEN & window.achievements.cards.keys())
        self.assertIn('0 of 22', window.achievements.summary.get())
        self.assertNotIn('discoveries', [key for key, section in window.achievements.sections.items()
                                         if section.winfo_manager()])
        self.assertIn('ears', window.wardrobe.none_tiles)
        self.assertEqual(window.wardrobe.tiles['ribbon-clip'].status, 'Locked')

    def test_wardrobe_and_achievements_omit_repeated_purpose_copy(self):
        window = self.window()
        window.page_buttons['Achievements'].invoke()
        window.window.update()

        def texts(widget):
            values = []
            for child in widget.winfo_children():
                if isinstance(child, tk.Label):
                    values.append(str(child.cget('text')))
                elif isinstance(child, tk.Canvas):
                    values.extend(drawn_text(child))
                values.extend(texts(child))
            return values

        self.assertNotIn('One outfit for all cats.\nChanges save automatically.', texts(window.wardrobe))
        self.assertNotIn('Equip unlocked rewards in Wardrobe.', texts(window.achievements))
        self.assertNotIn('Favorite spot', texts(window.wardrobe))

    # Try-on ----------------------------------------------------------------

    def test_hovering_a_tile_tries_it_on_the_stage_without_saving(self):
        window = self.window()
        view = window.wardrobe
        window.window.update()
        stage = window.rail_preview
        saved_image = stage.itemcget(window._rail_preview_image, 'image')
        tile = view.tiles['crown']
        tile.event_generate('<Enter>')
        window.window.update()
        self.assertIsNotNone(window._try_on_frame)
        self.assertEqual(stage.itemcget(window._rail_preview_image, 'image'), str(window._try_on_frame))
        self.assertEqual(window.rail_brand_subtitle.cget('text'), 'Trying on Crown')
        # The preview holds while the saved outfit's loop keeps ticking.
        window._display_preview()
        self.assertEqual(stage.itemcget(window._rail_preview_image, 'image'), str(window._try_on_frame))
        self.assertEqual(window.hat.get(), 'none')
        self.assertEqual(self.saved, [])

        # Moving straight to the neighbour keeps the preview up between tiles.
        tile.event_generate('<Leave>')
        view.tiles['party-hat'].event_generate('<Enter>')
        window.window.update()
        self.assertEqual(window.rail_brand_subtitle.cget('text'), 'Trying on Party hat')
        view.tiles['party-hat'].event_generate('<Leave>')
        window.window.after(TRY_ON_RESTORE_MS * 3)
        window.window.update()
        self.assertIsNone(window._try_on_frame)
        self.assertEqual(window.rail_brand_subtitle.cget('text'), 'companion studio')
        self.assertNotEqual(stage.itemcget(window._rail_preview_image, 'image'), '')
        self.assertTrue(saved_image)

    def test_try_on_clears_when_leaving_the_page_or_equipping(self):
        window = self.window({'crown'})
        view = window.wardrobe
        view.tiles['crown'].event_generate('<Enter>')
        window.window.update()
        view.tiles['crown'].invoke()
        self.assertIsNone(window._try_on_frame)
        self.assertEqual(window.hat.get(), 'crown')
        view.tiles['party-hat'].event_generate('<Enter>')
        window.window.update()
        self.assertIsNotNone(window._try_on_frame)
        window.page_buttons['Metrics'].invoke()
        self.assertIsNone(window._try_on_frame)
        self.assertEqual(window.rail_brand_subtitle.cget('text'), 'companion studio')

    def test_failed_try_on_render_keeps_the_saved_outfit(self):
        import settings_window
        window = self.window()
        with patch.object(settings_window, 'load_frame', side_effect=tk.TclError('renderer unavailable')):
            window.wardrobe.tiles['crown'].event_generate('<Enter>')
            window.window.update()
        self.assertIsNone(window._try_on_frame)
        self.assertEqual(window.rail_brand_subtitle.cget('text'), 'companion studio')

    # Choosing --------------------------------------------------------------

    def test_locked_tiles_open_their_achievement_and_cannot_be_equipped(self):
        window = self.window()
        wardrobe = window.wardrobe
        wardrobe.focus_item('round-glasses').invoke()
        window.window.update()
        self.assertEqual(window.glasses.get(), 'none')
        self.assertEqual(window.active_page.get(), 'Achievements')
        self.assertFalse(wardrobe.winfo_ismapped())
        self.assertTrue(window.achievements.winfo_ismapped())
        self.assertIn('640 / 1,000', window.achievements.progress_text['round-glasses'].get())
        self.assertIs(window.window.focus_get(), window.achievements.cards['round-glasses'])

    def test_achievement_link_reveals_reward_below_fold(self):
        window = self.window()
        window.window.minsize(1, 1)
        window.window.geometry('620x500')
        window.window.update()
        window.wardrobe.focus_item('crown').invoke()
        window.window.update()
        card = window.achievements.cards['crown']
        top = card.winfo_rooty() - window.scroll_canvas.winfo_rooty()
        self.assertGreaterEqual(top, 0)
        self.assertLess(top + card.winfo_height(), window.scroll_canvas.winfo_height())
        self.assertEqual(window.window.focus_get(), card)

    def test_live_secret_reveal_keeps_choices_and_autosaves_all_slots(self):
        window = self.window({'crown', 'round-glasses'})
        window.page_buttons['Achievements'].invoke()
        window.page_buttons['Wardrobe'].invoke()
        window.window.update()
        window.wardrobe.focus_item('crown').invoke()
        window.wardrobe.focus_item('round-glasses').invoke()
        new_ids = {'beta-bandana', 'angel-wings', 'sunflower-clip'}
        window.update_achievements({'crown', 'round-glasses'} | new_ids,
                                   tuple(ACCESSORY_BY_ID[item] for item in sorted(new_ids)))
        window.window.update()
        self.assertEqual((window.hat.get(), window.glasses.get()), ('crown', 'round-glasses'))
        self.assertIn('5 of 25', window.achievements.summary.get())
        for item_id in new_ids:
            self.assertIn(item_id, window.achievements._visible_ids)
            window.wardrobe.focus_item(item_id).invoke()
        plain = ImageTk.getimage(window._preview_frames['white']['idle']).tobytes()
        window.page_buttons['Achievements'].invoke()
        window.page_buttons['Wardrobe'].invoke()
        window.window.update()
        self.assertEqual(ImageTk.getimage(window._preview_frames['white']['idle']).tobytes(), plain)
        self.assertEqual(self.saved[-1].outfit(), {'hat': 'crown', 'glasses': 'round-glasses',
                                               'neck': 'beta-bandana', 'back': 'angel-wings', 'ears': 'sunflower-clip'})

    def test_none_tile_removes_one_slot_and_close_keeps_other_slots(self):
        window = self.window({'beta-bandana', 'angel-wings', 'sunflower-clip'},
                             neck='beta-bandana', back='angel-wings', ears='sunflower-clip')
        window.wardrobe.none_tiles['neck'].invoke()
        self.assertEqual((window.neck.get(), window.back.get(), window.ears.get()),
                         ('none', 'angel-wings', 'sunflower-clip'))
        self.assertEqual(window.wardrobe.none_tiles['neck'].status, 'Equipped')
        window.close()
        self.assertEqual((self.saved[-1].neck, self.saved[-1].back, self.saved[-1].ears),
                         ('none', 'angel-wings', 'sunflower-clip'))

    def test_shared_outfit_updates_real_preview_and_is_saved(self):
        window = self.window({'round-glasses', 'crown'})
        plain = ImageTk.getimage(window._preview_frames['white']['idle']).tobytes()
        window.wardrobe.focus_item('round-glasses').invoke()
        window.wardrobe.focus_item('crown').invoke()
        window.page_buttons['Achievements'].invoke()
        window.page_buttons['Wardrobe'].invoke()
        window.window.update_idletasks()
        dressed = ImageTk.getimage(window._preview_frames['white']['idle']).tobytes()
        self.assertNotEqual(plain, dressed)
        self.assertEqual((window.hat.get(), window.glasses.get()), ('crown', 'round-glasses'))
        self.assertEqual((self.saved[-1].hat, self.saved[-1].glasses), ('crown', 'round-glasses'))

    def test_live_unlock_enables_reward_without_equipping_or_reopening(self):
        window = self.window()
        window.page_buttons['Achievements'].invoke()
        window.update_usage_metrics(UsageMetrics(total_keystrokes=900))
        self.assertIn('900 / 1,000', window.achievements.progress_text['round-glasses'].get())
        window.update_usage_metrics(UsageMetrics(total_keystrokes=1000))
        window.update_achievements({'round-glasses'}, (ACCESSORY_BY_ID['round-glasses'],))
        self.assertEqual(window.achievements.progress_text['round-glasses'].get(), 'Unlocked')
        self.assertEqual(window.wardrobe.tiles['round-glasses'].status, 'Unlocked')
        self.assertEqual(window.glasses.get(), 'none')
        self.assertIn('Round glasses', window.wardrobe.notice.get())
        window.page_buttons['Wardrobe'].invoke()
        window.wardrobe.focus_item('round-glasses').invoke()
        self.assertEqual(window.glasses.get(), 'round-glasses')

    def test_locked_saved_or_programmatic_selection_is_not_saved(self):
        window = self.window(hat='crown')
        self.assertEqual(window.hat.get(), 'none')
        window.glasses.set('sunglasses')
        self.assertEqual(self.saved, [])

    def test_wardrobe_fits_narrow_width_and_switches_pages(self):
        window = self.window()
        window.page_buttons['Achievements'].invoke()
        window.page_buttons['Wardrobe'].invoke()
        window.window.update()
        window.window.minsize(1, 1)
        window.window.geometry('620x500')
        window.window.update()
        # The pinned rail sits beside the scroll canvas; measure the area the
        # rail and page share, as when the rail scrolled with the page.
        rail = window.page_switcher
        shared_width = window.scroll_canvas.winfo_width() + (
            window.scroll_canvas.winfo_rootx() - rail.winfo_rootx())
        self.assertLessEqual(window.wardrobe.winfo_reqwidth(), shared_width)
        for page in ('Metrics', 'Settings', 'Achievements', 'Wardrobe'):
            window.page_buttons[page].invoke()
            window.window.update()
            self.assertEqual(bool(window.wardrobe.winfo_ismapped()), page == 'Wardrobe')
            self.assertEqual(bool(window.achievements.winfo_ismapped()), page == 'Achievements')
            self.assertLessEqual(window.achievements.winfo_reqwidth(), shared_width - 52)
            last_tab = window.page_buttons['Achievements']
            self.assertLessEqual(last_tab.winfo_rootx() + last_tab.winfo_width(),
                                 window.scroll_canvas.winfo_rootx() + window.scroll_canvas.winfo_width())


class RewardAlbumTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.root.withdraw()
        self.addCleanup(self.root.destroy)

    def album(self, unlocked=(), keystrokes=640, geometry=None):
        window = SettingsWindow(
            self.root, AppSettings(cat_style='white'), lambda _settings: None,
            str(ASSETS / 'cat-type.png'), unlocked_accessories=set(unlocked),
            usage_metrics=UsageMetrics(total_keystrokes=keystrokes),
        )
        self.addCleanup(window.close)
        window.window.minsize(1, 1)
        if geometry:
            window.window.geometry(geometry)
        window.page_buttons['Achievements'].invoke()
        window.window.update()
        return window

    def test_every_visible_reward_is_one_focusable_card_in_its_section(self):
        window = self.album({'ribbon-clip', 'daisy-clip', 'angel-wings'})
        view = window.achievements
        self.assertIsInstance(view.album_shelf, RoundedPanel)
        self.assertEqual(view.album_shelf._radius, 18)
        self.assertEqual(set(view.cards), {item.id for item in view._visible_items})
        for item_id, card in view.cards.items():
            self.assertIsInstance(card, RewardEntry)
            self.assertEqual(card.winfo_children(), [])
            self.assertTrue(bool(int(card.cget('takefocus'))))
            self.assertEqual(int(card.cget('highlightthickness')), 2)
        self.assertIs(view.cards['ribbon-clip'].master, view._section_grids['milestones'])
        self.assertIs(view.cards['daisy-clip'].master, view._section_grids['days'])
        self.assertIs(view.cards['angel-wings'].master, view._section_grids['discoveries'])
        self.assertTrue(view.sections['discoveries'].winfo_ismapped())
        self.assertEqual(view._section_counts['days'].get(), '1 of 7')

    def test_cards_draw_a_meter_status_mark_and_percent(self):
        window = self.album({'ribbon-clip'})
        view = window.achievements
        locked = view.cards['bow-tie']
        self.assertEqual(locked.status, 'Locked')
        self.assertEqual(locked.progress, (640, 5000))
        self.assertIn('640 / 5,000', drawn_text(locked))
        self.assertIn('13%', drawn_text(locked))
        self.assertIsNotNone(locked._faded)
        earned = view.cards['ribbon-clip']
        self.assertEqual(earned.status, 'Unlocked')
        self.assertIn('Unlocked', drawn_text(earned))
        self.assertIsNone(earned._faded)
        self.assertIn('Bow tie', locked.cget('accessible_name'))
        self.assertIn('640 of 5,000', locked.cget('accessible_name'))

    def test_up_next_spotlights_the_locked_reward_nearest_completion(self):
        window = self.album({'ribbon-clip'}, keystrokes=900)
        view = window.achievements
        self.assertEqual(view.up_next_id, 'round-glasses')
        self.assertTrue(view.up_next.winfo_ismapped())
        self.assertIn('900 / 1,000', drawn_text(view.up_next_card))
        view.update_progress(UsageMetrics(total_keystrokes=1000), {'ribbon-clip', 'round-glasses'})
        window.window.update()
        self.assertEqual(view.up_next_id, 'bell-collar')
        everything = {item.id for item in visible_accessories(set())} | {'beta-bandana'}
        view.update_progress(UsageMetrics(total_keystrokes=1000), everything)
        window.window.update()
        self.assertIsNone(view.up_next_id)
        self.assertFalse(view.up_next.winfo_manager())

    def test_completion_meter_and_summary_count_visible_rewards(self):
        window = self.album({'ribbon-clip', 'round-glasses'})
        view = window.achievements
        self.assertEqual(view.summary.get(), '2 of 22 achievements unlocked')
        self.assertTrue(view.completion.winfo_ismapped())
        self.assertIsNotNone(view._completion_image)

    def test_filters_show_progress_or_unlocked_rewards_with_an_empty_state(self):
        window = self.album({'ribbon-clip'})
        view = window.achievements
        with patch.object(view, '_on_content_change') as changed:
            view.filter_buttons['unlocked'].invoke()
            changed.assert_called_once_with()
        window.window.update()
        self.assertEqual([item_id for item_id, card in view.cards.items() if card.winfo_ismapped()],
                         ['ribbon-clip'])
        view.filter_buttons['progress'].invoke()
        window.window.update()
        shown = {item_id for item_id, card in view.cards.items() if card.winfo_ismapped()}
        self.assertEqual(shown, set(view.cards) - {'ribbon-clip'})
        view.update_progress(view._metrics, set())
        view.filter_buttons['unlocked'].invoke()
        window.window.update()
        self.assertTrue(view.empty_label.winfo_ismapped())
        self.assertIn('250 keystrokes', view.empty_label.cget('text'))

    def test_album_reflows_between_one_and_two_columns(self):
        window = self.album(geometry='920x800')
        view = window.achievements
        wide = {int(card.grid_info()['column']) for card in view.cards.values()}
        self.assertEqual(wide, {0, 1})
        window.window.geometry('620x500')
        window.window.update()
        self.assertEqual({int(card.grid_info()['column']) for card in view.cards.values()}, {0})

    def test_new_flags_progress_and_focus_survive_filters(self):
        window = self.album()
        view = window.achievements
        self.assertFalse(any(card.is_new for card in view.cards.values()))
        view.mark_new((ACCESSORY_BY_ID['crown'],))
        window.window.update()
        self.assertIn('NEW', drawn_text(view.cards['crown']))
        view.update_progress(UsageMetrics(total_keystrokes=900), set())
        self.assertIn('900 / 1,000', view.progress_text['round-glasses'].get())
        view.filter_buttons['unlocked'].invoke()
        card = view.focus_reward('crown')
        window.window.update()
        self.assertEqual(view.filter.get(), 'all')
        self.assertIs(window.window.focus_get(), card)
        self.assertTrue(card._focused)
        self.assertEqual(card.cget('highlightbackground'), view.palette['accent_dark'])
        self.assertNotIn('crown', view._new_ids)
        self.assertNotIn('NEW', drawn_text(card))
        with self.assertRaises(KeyError):
            view.focus_reward('missing')


if __name__ == '__main__':
    unittest.main()
