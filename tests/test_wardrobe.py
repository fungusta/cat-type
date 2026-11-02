import tkinter as tk
import unittest
from unittest.mock import patch
from pathlib import Path

from PIL import ImageTk

from cat_settings import AppSettings
from settings_window import SettingsWindow
from usage_metrics import UsageMetrics
from cat_accessories import ACCESSORY_BY_ID
from wardrobe_view import WardrobeView
from ui_surfaces import RoundedAction, RoundedPanel, RoundedChoice
import inspect
import _tkinter
from collections import Counter, deque
import time
import traceback


ASSETS = Path(__file__).resolve().parents[1] / 'assets'


class WardrobeTests(unittest.TestCase):
    def test_scrollbar_gutter_does_not_change_card_layout_or_page_size(self):
        from types import SimpleNamespace
        window = self.window()
        view = window.wardrobe
        view.focus_item("round-glasses")
        tile = view.choice_tiles["round-glasses"]
        action = view.buttons["round-glasses"]
        thumbnail = next(child for child in tile.content.winfo_children()
                         if isinstance(child, tk.Label))
        wide_breakpoint = thumbnail.winfo_reqwidth() + action.winfo_reqwidth() + 178
        stacked_breakpoint = thumbnail.winfo_reqwidth() + 18 + max(
            view.new_badges["round-glasses"].winfo_reqwidth(),
            action.winfo_reqwidth() + 4,
            view.achievement_links["round-glasses"].winfo_reqwidth() + 4,
        )
        gutter = window.scrollbar.winfo_reqwidth()
        tile.grid_remove()
        with patch.object(window, "_sync_scrollbar_visibility"):
            for breakpoint, action_row in ((wide_breakpoint, 1), (stacked_breakpoint, 2)):
                for visible in (False, True, False):
                    with self.subTest(breakpoint=breakpoint, scrollbar_visible=visible):
                        if visible:
                            window.scrollbar.pack(side="right", fill="y", before=window.scroll_canvas)
                        else:
                            window.scrollbar.pack_forget()
                        # The same outer width straddles the card breakpoint only
                        # because the scrollbar takes a gutter from the canvas.
                        width = breakpoint + gutter - 1 - (gutter if visible else 0)
                        tile.place(x=0, y=0, width=width + 12)
                        window.window.update()
                        self.assertEqual(int(action.grid_info()["row"]), action_row)

            tile.place_configure(width=wide_breakpoint + gutter + 40 + 12)
            window.window.update()
            self.assertEqual(int(action.grid_info()["row"]), 0)
            for visible in (False, True, False):
                with patch.object(window.scrollbar, "winfo_manager", return_value="pack" if visible else ""):
                    view._resize_choices(SimpleNamespace(width=520 + gutter - 1 - (gutter if visible else 0)))
                    self.assertEqual(view._page_size, 2)
            view._resize_choices(SimpleNamespace(width=520 + gutter + 40))
            self.assertEqual(view._page_size, 4)
            window.window.update_idletasks()

    def _trace_bounded_idle_layout(self, window):
        """Temporary CI diagnostic: retain geometry evidence before a Tk hang."""
        events = deque(maxlen=40)
        counts = Counter()
        images = Counter()
        original_image_init = ImageTk.PhotoImage.__init__

        def trace_image(image_self, image=None, *args, **kwargs):
            images[str(getattr(image, "size", None))] += 1
            original_image_init(image_self, image, *args, **kwargs)

        image_patch = patch.object(ImageTk.PhotoImage, "__init__", trace_image)
        image_patch.start()
        self.addCleanup(image_patch.stop)

        def record(event):
            widget = event.widget
            if not isinstance(widget, tk.Misc):
                return
            try:
                path = str(widget)
                counts[path] += 1
                details = {
                    "widget": path, "actual": (event.width, event.height),
                    "requested": (widget.winfo_reqwidth(), widget.winfo_reqheight()),
                    "parent_width": widget.master.winfo_width() if widget.master else None,
                }
                if isinstance(widget, tk.Label):
                    details["wrap"] = str(widget.cget("wraplength"))
                    details["text"] = str(widget.cget("text"))
                if widget.winfo_manager() == "grid":
                    grid = widget.grid_info()
                    details["grid"] = tuple(grid.get(key) for key in
                                             ("row", "column", "rowspan", "columnspan"))
                events.append(details)
            except tk.TclError:
                pass

        self.root.bind_all("<Configure>", record, add="+")
        self.addCleanup(lambda: self.root.unbind_all("<Configure>"))

        scroll_transitions = deque(maxlen=30)
        sync_calls = Counter()
        original_sync = window._sync_scrollbar_visibility

        def trace_scroll(*args, **kwargs):
            before = bool(window.scrollbar.winfo_manager())
            canvas = window.scroll_canvas
            content = window.scroll_content
            bounds = canvas.bbox("all")
            original_sync(*args, **kwargs)
            after = bool(window.scrollbar.winfo_manager())
            sync_calls[(before, after)] += 1
            if before != after:
                origin = content.winfo_rooty()
                pending = list(content.winfo_children())
                extents = []
                while pending:
                    child = pending.pop()
                    if child.winfo_ismapped():
                        extents.append((child.winfo_rooty() - origin + child.winfo_reqheight(), str(child)))
                        pending.extend(child.winfo_children())
                scroll_transitions.append({
                    "visible": (before, after), "bbox": bounds,
                    "viewport": args[0] if args else canvas.winfo_height(),
                    "canvas": (canvas.winfo_width(), canvas.winfo_height()),
                    "content": (content.winfo_width(), content.winfo_height(), content.winfo_reqheight()),
                    "largest_requested_bottoms": sorted(extents, reverse=True)[:3],
                    "caller": traceback.extract_stack(limit=3)[-2].name,
                })

        sync_patch = patch.object(window, "_sync_scrollbar_visibility", trace_scroll)
        sync_patch.start()
        self.addCleanup(sync_patch.stop)

        def bounded_idle(widget):
            started = time.monotonic()
            iterations = 0
            # Tcl's update idletasks drains this same class of events. Drain
            # one batch at a time so a self-sustaining queue can fail the test.
            while widget.tk.dooneevent(_tkinter.IDLE_EVENTS | _tkinter.DONT_WAIT):
                iterations += 1
                if iterations >= 2000 or time.monotonic() - started > 15:
                    print("WARDROBE GEOMETRY DIAGNOSTIC", flush=True)
                    print("idle batches:", iterations, "configure counts:", counts.most_common(12), flush=True)
                    print("PhotoImage sizes/counts:", images.most_common(12),
                          "live images:", len(widget.tk.call("image", "names")), flush=True)
                    print("SCROLL SYNC COUNTS", sync_calls, flush=True)
                    for transition in scroll_transitions:
                        print("SCROLL TRANSITION", transition, flush=True)
                    for event in events:
                        print(event, flush=True)
                    view = window.wardrobe
                    for item_id, tile in view.choice_tiles.items():
                        print("CARD", item_id, "content", tile.content.winfo_width(),
                              "choose", view.buttons[item_id].grid_info(),
                              "badge", view.new_badges[item_id].winfo_width(),
                              "badge_request", view.new_badges[item_id].winfo_reqwidth(), flush=True)
                    traceback.print_stack(limit=12)
                    self.fail("Tk idle layout did not settle; see WARDROBE GEOMETRY DIAGNOSTIC")

        idle_patch = patch.object(tk.Misc, "update_idletasks", bounded_idle)
        idle_patch.start()
        self.addCleanup(idle_patch.stop)

    def test_height_only_configure_does_not_restart_card_geometry(self):
        original_scaling = self.root.tk.call("tk", "scaling")
        self.root.tk.call("tk", "scaling", 2.5)
        self.addCleanup(lambda: self.root.tk.call("tk", "scaling", original_scaling))
        window = self.window()
        window.window.minsize(1, 1)
        window.window.geometry("620x700")
        self._trace_bounded_idle_layout(window)
        view = window.wardrobe
        view.focus_item("round-glasses")
        window.window.update()
        badge = view.new_badges["round-glasses"]
        status_row = badge.master
        copy = status_row.master
        labels = [child for child in copy.winfo_children() if isinstance(child, tk.Label)]
        status = next(child for child in status_row.winfo_children() if isinstance(child, tk.Label))
        # Wrapping changes height and emits Configure again. Replaying those
        # notifications must not request another geometry calculation.
        with patch.object(labels[0], "configure", wraps=labels[0].configure) as name_configure, \
             patch.object(status, "configure", wraps=status.configure) as status_configure, \
             patch.object(copy, "grid_configure", wraps=copy.grid_configure) as copy_grid:
            for _ in range(5):
                for widget in (copy, status_row, copy.master):
                    widget.event_generate("<Configure>", width=widget.winfo_width(),
                                          height=widget.winfo_height() + 1)
            name_configure.assert_not_called()
            status_configure.assert_not_called()
            copy_grid.assert_not_called()
        idle_ran = []
        window.window.after_idle(lambda: idle_ran.append(True))
        window.window.update_idletasks()
        self.assertEqual(idle_ran, [True])

    def test_pages_mount_only_the_slice_and_preserve_outfit(self):
        from cat_accessories import visible_accessories
        ids = {item.id for item in visible_accessories(set())}
        window = self.window(ids)
        view = window.wardrobe
        self.assertEqual(set(view.buttons), {item.id for item in view._visible_items[:view._page_size]})
        self.assertLessEqual(len(view.buttons), 4)
        view.focus_item("round-glasses").invoke()
        view.show_page(view._page_index + 1)
        self.assertEqual(window.glasses.get(), "round-glasses")
        start = view._page_index * view._page_size
        self.assertEqual(set(view.buttons), {item.id for item in view._visible_items[start:start + view._page_size]})

    def test_high_scaling_new_badge_is_visible_without_status_overlap(self):
        original_scaling = self.root.tk.call("tk", "scaling")
        self.root.tk.call("tk", "scaling", 2.5)
        self.addCleanup(lambda: self.root.tk.call("tk", "scaling", original_scaling))
        window = self.window()
        window.window.minsize(1, 1)
        window.window.geometry("620x700")
        view = window.wardrobe
        view.update_unlocks({"round-glasses"}, (ACCESSORY_BY_ID["round-glasses"],))
        for _ in range(2):
            view.focus_item("round-glasses")
            window.window.update()
            badge = view.new_badges["round-glasses"]
            self.assertTrue(badge.winfo_ismapped())
            self.assertGreaterEqual(badge.winfo_width(), badge.winfo_reqwidth())
            status = next(child for child in badge.master.winfo_children() if isinstance(child, tk.Label))
            self.assertTrue(status.winfo_ismapped())
            self.assertLessEqual(status.winfo_reqwidth(), status.winfo_width())
            self.assertLessEqual(badge.winfo_rootx() + badge.winfo_width(),
                                 badge.master.winfo_rootx() + badge.master.winfo_width())
            self.assertTrue(status.winfo_rooty() + status.winfo_height() <= badge.winfo_rooty()
                            or badge.winfo_rooty() + badge.winfo_height() <= status.winfo_rooty()
                            or status.winfo_rootx() + status.winfo_width() <= badge.winfo_rootx()
                            or badge.winfo_rootx() + badge.winfo_width() <= status.winfo_rootx())
            view.show_page(view._page_index + 1)
        self.assertIn("round-glasses", view._new_ids)
        self.assertEqual(window.glasses.get(), "none")

    def test_new_badge_fits_when_card_only_has_room_for_one_action(self):
        original_scaling = self.root.tk.call("tk", "scaling")
        self.root.tk.call("tk", "scaling", 2.5)
        self.addCleanup(lambda: self.root.tk.call("tk", "scaling", original_scaling))
        window = self.window()
        view = window.wardrobe
        view.update_unlocks({"round-glasses"}, (ACCESSORY_BY_ID["round-glasses"],))
        view.focus_item("round-glasses")
        tile = view.choice_tiles["round-glasses"]
        badge = view.new_badges["round-glasses"]
        action = view.achievement_links["round-glasses"]
        # Allocate enough width for the widest action, independent of platform
        # font metrics and the surrounding settings navigation width.
        tile.grid_remove()
        narrow_width = action.winfo_reqwidth() + 4 + 12
        for width in (narrow_width, 600, narrow_width):
            with self.subTest(width=width):
                tile.place(x=0, y=0, width=width)
                window.window.update()
                self.assertTrue(badge.winfo_ismapped())
                self.assertGreaterEqual(badge.winfo_width(), badge.winfo_reqwidth())
                status = next(child for child in badge.master.winfo_children()
                              if isinstance(child, tk.Label))
                self.assertLessEqual(status.winfo_rooty() + status.winfo_height(), badge.winfo_rooty())
                for widget in (badge, action, view.buttons["round-glasses"]):
                    self.assertGreaterEqual(widget.winfo_width(), widget.winfo_reqwidth())
                    self.assertGreaterEqual(widget.winfo_rootx(), tile.winfo_rootx())
                    self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                                         tile.winfo_rootx() + tile.winfo_width())
                    self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                                         tile.winfo_rooty() + tile.winfo_height())

    def test_high_scaling_narrow_cards_wrap_all_copy_and_keep_actions_inside(self):
        original_scaling = self.root.tk.call("tk", "scaling")
        self.root.tk.call("tk", "scaling", 2.5)
        self.addCleanup(lambda: self.root.tk.call("tk", "scaling", original_scaling))
        window = self.window({"round-glasses"})
        window.window.minsize(1, 1)
        window.window.geometry("620x700")
        view = window.wardrobe
        for item_id in ("round-glasses", "ribbon-clip"):
            view.focus_item(item_id)
            window.window.update()
            tile = view.choice_tiles[item_id]
            pending = list(tile.content.winfo_children())
            while pending:
                child = pending.pop()
                pending.extend(child.winfo_children())
                if not child.winfo_ismapped():
                    continue
                self.assertGreaterEqual(child.winfo_rootx(), tile.winfo_rootx())
                self.assertLessEqual(child.winfo_rootx() + child.winfo_width(),
                                     tile.winfo_rootx() + tile.winfo_width())
                self.assertLessEqual(child.winfo_rooty() + child.winfo_height(),
                                     tile.winfo_rooty() + tile.winfo_height())
                if isinstance(child, tk.Label) and child.cget("text"):
                    self.assertGreater(int(str(child.cget("wraplength"))), 0)
                    self.assertLessEqual(child.winfo_reqwidth(), child.winfo_width())
            pager = view.pagination_controls
            shelf = view.tray_shelf
            self.assertTrue(pager.winfo_ismapped())
            self.assertLessEqual(pager.winfo_rooty() + pager.winfo_height(),
                                 shelf.winfo_rooty() + shelf.winfo_height())
            bounds = window.scroll_canvas.bbox("all")
            self.assertLessEqual(shelf.winfo_rooty() - window.scroll_canvas.winfo_rooty()
                                 + window.scroll_canvas.canvasy(0) + shelf.winfo_height(), bounds[3])

    def test_cards_and_pagination_fit_content_driven_shelf(self):
        window = self.window()
        view = window.wardrobe
        window.window.minsize(1, 1)
        for geometry in ("920x1360", "620x500"):
            window.window.geometry(geometry)
            window.window.update()
            for page in (0, 1):
                view.show_page(page)
                window.window.update()
                shelf = view.tray_shelf
                self.assertGreaterEqual(shelf.winfo_height(), shelf.content.winfo_reqheight() + 20)
                widgets = [view.pagination_controls, *view.choice_tiles.values(),
                           *view.buttons.values(), *view.achievement_links.values()]
                for widget in widgets:
                    self.assertTrue(widget.winfo_ismapped(), (geometry, str(widget)))
                    self.assertGreaterEqual(widget.winfo_rooty(), shelf.winfo_rooty())
                    self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                                         shelf.winfo_rooty() + shelf.winfo_height())
                for tile in view.choice_tiles.values():
                    self.assertGreaterEqual(tile.winfo_height(), tile.content.winfo_reqheight() + 12)
                    pending = list(tile.content.winfo_children())
                    while pending:
                        child = pending.pop()
                        pending.extend(child.winfo_children())
                        if child.winfo_ismapped():
                            self.assertLessEqual(child.winfo_rooty() + child.winfo_height(),
                                                 tile.winfo_rooty() + tile.winfo_height())
                bounds = window.scroll_canvas.bbox("all")
                shelf_bottom = (shelf.winfo_rooty() - window.scroll_canvas.winfo_rooty()
                                + window.scroll_canvas.canvasy(0) + shelf.winfo_height())
                self.assertLessEqual(shelf_bottom, bounds[3])

    def test_mix_it_up_clears_new_badge_for_off_page_equipped_item(self):
        window = self.window()
        view = window.wardrobe
        view.update_unlocks({"angel-wings"}, (ACCESSORY_BY_ID["angel-wings"],))
        view.show_page(0)
        self.assertNotIn("angel-wings", view.buttons)
        view.mix_it_up()
        self.assertEqual(window.back.get(), "angel-wings")
        self.assertNotIn("angel-wings", view._new_ids)
        view.focus_item("angel-wings")
        self.assertEqual(view.buttons["angel-wings"].cget("text"), "Equipped")
        self.assertEqual(view.new_badges["angel-wings"].winfo_manager(), "")

    def test_resize_preserves_first_item_and_off_page_unlock_badge(self):
        from types import SimpleNamespace
        window = self.window()
        view = window.wardrobe
        view.show_page(2)
        first = next(iter(view.buttons))
        view._resize_choices(SimpleNamespace(width=400))
        self.assertEqual(view._page_size, 2)
        self.assertIn(first, view.buttons)
        view.update_unlocks({"angel-wings"}, (ACCESSORY_BY_ID["angel-wings"],))
        view.focus_item("angel-wings")
        self.assertEqual(view.status_text["angel-wings"].get(), "Unlocked")
        self.assertEqual(view.new_badges["angel-wings"].winfo_manager(), "pack")
        view.buttons["angel-wings"].invoke()
        view.show_page(0)
        view.focus_item("angel-wings")
        self.assertEqual(view.new_badges["angel-wings"].winfo_manager(), "")

    def test_shrinking_model_clamps_page_and_focus_navigates(self):
        window = self.window({"angel-wings", "beta-bandana"})
        view = window.wardrobe
        view.show_page(999)
        view.update_unlocks(set())
        self.assertLess(view._page_index * view._page_size, len(view._visible_items))
        action = view.focus_item("round-glasses")
        self.assertEqual(view._page_index, view.page_for_item("round-glasses"))
        self.assertIs(action, view.buttons["round-glasses"])
        self.assertEqual(window.window.focus_get(), action)

    def test_wardrobe_and_achievements_omit_repeated_purpose_copy(self):
        window = self.window()
        window.page_buttons["Achievements"].invoke()
        window.page_buttons["Wardrobe"].invoke()
        window.window.update()

        def label_texts(widget):
            texts = []
            for child in widget.winfo_children():
                if isinstance(child, tk.Label):
                    texts.append(str(child.cget("text")))
                texts.extend(label_texts(child))
            return texts

        wardrobe_texts = label_texts(window.wardrobe)
        window.page_buttons["Achievements"].invoke()
        window.window.update_idletasks()
        achievement_texts = label_texts(window.achievements)

        self.assertNotIn("One outfit for all cats.\nChanges save automatically.", wardrobe_texts)
        self.assertNotIn("Equip unlocked rewards in Wardrobe.", achievement_texts)

    def test_secrets_and_their_items_are_absent_from_both_tabs_and_totals(self):
        self.assertIn('slots', inspect.signature(WardrobeView).parameters)
        window = self.window()
        window.page_buttons["Achievements"].invoke()
        window.page_buttons["Wardrobe"].invoke()
        window.window.update()
        hidden = {'angel-wings', 'moon-pendant', 'sunflower-clip', 'cozy-scarf',
                  'beta-bandana', 'shooting-star-clip', 'sunrise-scarf', 'butterfly-wings'}
        self.assertFalse(hidden & window.wardrobe.buttons.keys())
        self.assertFalse(hidden & window.achievements.cards.keys())
        self.assertIn('0 of 22', window.achievements.summary.get())
        self.assertIn('ears', window.wardrobe.none_buttons)
        self.assertEqual(window.wardrobe.buttons['ribbon-clip'].cget('state'), 'disabled')
        window.wardrobe.focus_item('bow-tie')
        self.assertIn('bow-tie', window.wardrobe.buttons)

    def test_wardrobe_and_achievement_surfaces_use_shared_soft_shelves(self):
        window = self.window()
        window.page_buttons["Achievements"].invoke()
        window.page_buttons["Wardrobe"].invoke()
        window.window.update()

        self.assertIsInstance(window.wardrobe.preview_card, RoundedPanel)
        self.assertEqual(window.wardrobe.preview_card._radius, 18)
        self.assertTrue(window.wardrobe.choice_tiles)
        self.assertTrue(
            all(tile._radius == 16 for tile in window.wardrobe.choice_tiles.values())
        )
        self.assertTrue(
            all(
                isinstance(button, RoundedChoice)
                for button in window.wardrobe.none_buttons.values()
            )
        )
        self.assertTrue(window.achievements.cards)
        self.assertTrue(
            all(
                isinstance(card, RoundedPanel)
                and card._radius == 16
                and bool(int(card.cget("takefocus")))
                for card in window.achievements.cards.values()
            )
        )

    def test_wardrobe_matches_the_prototype_accessory_tray(self):
        window = self.window()

        self.assertFalse(window.wardrobe.preview_card.winfo_ismapped())
        self.assertTrue(window.wardrobe.choice_tiles)
        self.assertTrue(
            all(
                int(tile.grid_info()["column"]) == 0
                for tile in window.wardrobe.choice_tiles.values()
            )
        )

    def test_wardrobe_accessory_actions_use_shared_soft_pills(self):
        window = self.window()

        self.assertTrue(
            all(isinstance(button, RoundedAction)
                for button in window.wardrobe.buttons.values())
        )
        self.assertTrue(
            all(isinstance(link, RoundedAction)
                for link in window.wardrobe.achievement_links.values())
        )

    def test_achievements_group_rewards_in_one_album_shelf(self):
        window = self.window()
        window.page_buttons["Achievements"].invoke()
        window.page_buttons["Wardrobe"].invoke()
        window.window.update()

        self.assertIsInstance(window.achievements.album_shelf, RoundedPanel)
        self.assertEqual(window.achievements.album_shelf._radius, 18)
        self.assertIs(window.achievements.cards_area.master,
                      window.achievements.album_shelf.content)
        self.assertTrue(window.achievements.status_badges)

    def test_mix_it_up_chooses_only_unlocked_accessories(self):
        window = self.window({'crown', 'round-glasses'})
        window.wardrobe.mix_it_up()

        self.assertIn(window.hat.get(), {'none', 'crown'})
        self.assertIn(window.glasses.get(), {'none', 'round-glasses'})
        self.assertEqual(window.neck.get(), 'none')

    def test_wardrobe_does_not_contain_general_settings(self) -> None:
        window = self.window()

        def texts(widget: tk.Misc) -> set[str]:
            values: set[str] = set()
            for child in widget.winfo_children():
                try:
                    value = child.cget("text")
                except tk.TclError:
                    value = ""
                if value:
                    values.add(str(value))
                values.update(texts(child))
            return values

        self.assertNotIn("Favorite spot", texts(window.wardrobe))
        self.assertTrue(window.wardrobe.choice_tiles)

    def test_achievements_cards_are_focusable_rounded_shelves(self) -> None:
        window = self.window()
        window.page_buttons["Achievements"].invoke()
        window.page_buttons["Wardrobe"].invoke()
        window.window.update()
        for card in window.achievements.cards.values():
            self.assertTrue(bool(int(card.cget("takefocus"))))
            self.assertEqual(card._radius, 16)

    def test_empty_new_badges_are_hidden_until_a_reward_is_new(self) -> None:
        window = self.window()
        window.page_buttons["Achievements"].invoke()
        window.page_buttons["Wardrobe"].invoke()
        window.window.update()
        self.assertTrue(
            all(not badge.winfo_ismapped() for badge in window.wardrobe.new_badges.values())
        )
        self.assertTrue(
            all(not badge.winfo_ismapped() for badge in window.achievements.new_badges.values())
        )

    def test_achievements_reward_album_reflows_between_grid_columns(self) -> None:
        window = self.window()
        window.page_buttons["Achievements"].invoke()
        window.page_buttons["Wardrobe"].invoke()
        window.window.update()
        window.page_buttons["Achievements"].invoke()
        window.window.geometry("920x800")
        window.window.update()
        wide_columns = {
            int(card.grid_info()["column"])
            for card in window.achievements.cards.values()
        }
        self.assertIn(1, wide_columns)
        self.assertEqual(len(window.achievements.cards), 4)

        window.window.geometry("620x500")
        window.window.update()
        narrow_columns = {
            int(card.grid_info()["column"])
            for card in window.achievements.cards.values()
        }
        self.assertEqual(narrow_columns, {0})
        self.assertEqual(len(window.achievements.cards), 2)
        for card in window.achievements.cards.values():
            copy = next(child for child in card.content.winfo_children()
                        if isinstance(child, tk.Frame))
            labels = [child for child in copy.winfo_children() if isinstance(child, tk.Label)]
            self.assertTrue(labels)
            for label in labels:
                self.assertEqual(int(label.cget('wraplength')), max(1, copy.winfo_width() - 4))

    def test_long_achievement_heading_reserves_new_badge_space(self):
        window = self.window()
        window.page_buttons["Achievements"].invoke()
        window.page_buttons["Wardrobe"].invoke()
        window.window.update()
        window.page_buttons['Achievements'].invoke()
        window.window.geometry('620x500')
        view = window.achievements
        window.window.update()
        item_id = next(iter(view.cards))
        badge = view.new_badges[item_id]
        heading = badge.master
        title = next(child for child in heading.winfo_children() if isinstance(child, tk.Label))
        title.configure(text='A very long achievement title with many words for compact layouts')
        view.mark_new((ACCESSORY_BY_ID[item_id],))
        window.window.update()
        self.assertEqual(title.winfo_manager(), 'grid')
        self.assertEqual(badge.winfo_manager(), 'grid')
        self.assertTrue(badge.winfo_ismapped())
        self.assertLessEqual(title.winfo_x() + title.winfo_width(), badge.winfo_x())
        self.assertLessEqual(badge.winfo_x() + badge.winfo_width(), heading.winfo_width())
        self.assertEqual(int(title.cget('wraplength')), max(1, title.winfo_width() - 4))

    def test_achievement_pages_preserve_progress_new_flags_and_focus(self):
        window = self.window()
        window.page_buttons["Achievements"].invoke()
        window.page_buttons["Wardrobe"].invoke()
        window.window.update()
        view = window.achievements
        self.assertEqual(len(view._visible_items), 22)
        self.assertLessEqual(len(view.cards), 4)
        view.mark_new((ACCESSORY_BY_ID['crown'],))
        view.show_page(999)
        self.assertEqual(view._page_index, (22 - 1) // view._page_size)
        view.update_progress(UsageMetrics(total_keystrokes=900), set())
        self.assertIn('900 / 1,000', view.progress_text['round-glasses'].get())
        view.show_page(0)
        self.assertIn('crown', view._new_ids)
        view.show_page(view.page_for_item('crown'))
        self.assertTrue(view.new_badges['crown'].winfo_manager())
        window.page_buttons['Achievements'].invoke()
        view.show_page(0 if view.page_for_item('crown') else 1)
        self.assertNotIn('crown', view.cards)
        card = view.focus_reward('crown')
        window.window.update()
        self.assertIs(window.window.focus_get(), card)
        self.assertIs(card, view.cards['crown'])
        self.assertEqual(view._page_index, view.page_for_item('crown'))
        self.assertNotIn('crown', view._new_ids)
        with self.assertRaises(KeyError):
            view.page_for_item('missing')

    def test_achievement_card_focus_draws_a_visible_focus_ring(self) -> None:
        window = self.window()
        window.page_buttons["Achievements"].invoke()
        window.page_buttons["Wardrobe"].invoke()
        window.window.update()
        window.page_buttons["Achievements"].invoke()
        window.window.update()
        card = next(iter(window.achievements.cards.values()))
        before = card._shelf_image
        card.focus_set()
        window.window.update()
        self.assertTrue(card._focused)
        self.assertIsNot(before, card._shelf_image)

    def test_live_secret_reveal_keeps_choices_and_autosaves_all_slots(self):
        self.assertIn('slots', inspect.signature(WardrobeView).parameters)
        window = self.window({'crown', 'round-glasses'})
        window.page_buttons["Achievements"].invoke()
        window.page_buttons["Wardrobe"].invoke()
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

    def test_new_slots_none_and_close_preserve_other_equipped_slots(self):
        self.assertIn('slots', inspect.signature(WardrobeView).parameters)
        window = self.window({'beta-bandana', 'angel-wings', 'sunflower-clip'},
                             neck='beta-bandana', back='angel-wings', ears='sunflower-clip')
        window.wardrobe.focus_item('beta-bandana')
        window.wardrobe.none_buttons['neck'].invoke()
        self.assertEqual((window.neck.get(), window.back.get(), window.ears.get()), ('none', 'angel-wings', 'sunflower-clip'))
        window.close()
        self.assertEqual((self.saved[-1].neck, self.saved[-1].back, self.saved[-1].ears),
                         ('none', 'angel-wings', 'sunflower-clip'))

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
        window.page_buttons["Achievements"].invoke()
        window.page_buttons["Wardrobe"].invoke()
        window.window.update()
        self.assertIn('Achievements', window.page_buttons)
        wardrobe = window.wardrobe
        wardrobe.focus_item('round-glasses')
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
        window.page_buttons["Achievements"].invoke()
        window.page_buttons["Wardrobe"].invoke()
        window.window.update()
        self.assertIn('Achievements', window.page_buttons)
        window.window.minsize(1, 1)
        window.window.geometry('620x500')
        window.window.update()
        window.wardrobe.focus_item('crown')
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
        window.wardrobe.focus_item('round-glasses').invoke()
        window.wardrobe.focus_item('crown').invoke()
        self.assertIn('Achievements', window.page_buttons)
        window.page_buttons['Achievements'].invoke()
        window.page_buttons['Wardrobe'].invoke()
        window.window.update_idletasks()
        dressed = ImageTk.getimage(window._preview_frames['white']['idle']).tobytes()
        self.assertNotEqual(plain, dressed)
        self.assertEqual((window.hat.get(), window.glasses.get()), ('crown', 'round-glasses'))
        self.assertEqual((self.saved[-1].hat, self.saved[-1].glasses), ('crown', 'round-glasses'))
        self.assertTrue(window.window.winfo_exists())

    def test_none_removes_one_slot_and_close_keeps_changes(self):
        window = self.window({'round-glasses', 'crown'}, hat='crown', glasses='round-glasses')
        window.wardrobe.focus_item('crown')
        window.wardrobe.none_buttons['hat'].invoke()
        self.assertEqual((window.hat.get(), window.glasses.get()), ('none', 'round-glasses'))
        self.assertIn('Achievements', window.page_buttons)
        window.page_buttons['Achievements'].invoke()
        window.window.update_idletasks()
        window.close()
        self.assertEqual((self.saved[-1].hat, self.saved[-1].glasses), ('none', 'round-glasses'))

    def test_live_unlock_enables_reward_without_equipping_or_reopening(self):
        window = self.window()
        window.page_buttons["Achievements"].invoke()
        window.page_buttons["Wardrobe"].invoke()
        window.window.update()
        self.assertIn('Achievements', window.page_buttons)
        window.page_buttons['Achievements'].invoke()
        from cat_accessories import ACCESSORY_BY_ID
        window.update_usage_metrics(UsageMetrics(total_keystrokes=900))
        self.assertIn('900 / 1,000', window.achievements.progress_text['round-glasses'].get())
        window.update_usage_metrics(UsageMetrics(total_keystrokes=1000))
        window.update_achievements({'round-glasses'}, (ACCESSORY_BY_ID['round-glasses'],))
        self.assertEqual(window.achievements.progress_text['round-glasses'].get(), 'Unlocked')
        window.wardrobe.focus_item('round-glasses')
        self.assertEqual(window.wardrobe.buttons['round-glasses'].cget('state'), 'normal')
        self.assertEqual(window.wardrobe.status_text['round-glasses'].get(), 'Unlocked')
        self.assertEqual(window.glasses.get(), 'none')
        self.assertIn('Round glasses', window.wardrobe.notice.get())
        window.page_buttons['Wardrobe'].invoke()
        window.wardrobe.focus_item('round-glasses').invoke()
        self.assertEqual(window.glasses.get(), 'round-glasses')
        window.window.update_idletasks()

    def test_locked_saved_or_programmatic_selection_is_not_saved(self):
        window = self.window(hat='crown')
        self.assertEqual(window.hat.get(), 'none')
        window.glasses.set('sunglasses')
        self.assertEqual(self.saved, [])

    def test_wardrobe_fits_narrow_width_and_switches_pages(self):
        window = self.window()
        window.page_buttons["Achievements"].invoke()
        window.page_buttons["Wardrobe"].invoke()
        window.window.update()
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
