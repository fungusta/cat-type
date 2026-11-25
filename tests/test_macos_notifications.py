import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import cat_type
import macos_notifications
from cat_accessories import ACCESSORY_BY_ID


class UnlockNoticeTextTests(unittest.TestCase):
    def test_one_unlock_names_the_accessory(self):
        title, body = cat_type.unlock_notice_text((ACCESSORY_BY_ID["round-glasses"],))
        self.assertEqual(title, "New accessory unlocked")
        self.assertEqual(body, "Round glasses is ready to try on in your Wardrobe.")

    def test_several_unlocks_read_as_a_list(self):
        earned = tuple(ACCESSORY_BY_ID[key] for key in ("round-glasses", "ribbon-clip", "crown"))
        title, body = cat_type.unlock_notice_text(earned)
        self.assertEqual(title, "New accessories unlocked")
        self.assertTrue(body.startswith("Round glasses, Ribbon clip and Crown are ready"))
        # The system shows the app's own name and icon beside the notice.
        self.assertNotIn("Cat Type", title + body)


class NativeCenterTests(unittest.TestCase):
    def test_off_macos_there_is_no_native_center(self):
        with patch.object(macos_notifications, "_center", None), \
                patch.object(macos_notifications.sys, "platform", "win32"):
            self.assertFalse(macos_notifications.post_notice("Title", "Body", "id"))

    def test_without_an_app_bundle_the_tray_is_used(self):
        # Tests run from a bare interpreter, which has no bundle identity.
        with patch.object(macos_notifications, "_center", None):
            self.assertFalse(macos_notifications.post_notice("Title", "Body", "id"))


class NotifyAccessoriesTests(unittest.TestCase):
    def notify(self, native_result: bool, platform: str = "darwin"):
        posted, tray, pictures = [], [], []
        self.pictures = pictures
        done = threading.Event()

        class Tray:
            HAS_NOTIFICATION = True

            def notify(self, message, title):
                tray.append((title, message))

        def post(title, body, identifier, fallback, picture=None):
            posted.append((title, body, identifier))
            pictures.append(picture)
            if native_result == "refused":
                fallback()
            return bool(native_result)

        app = cat_type.CatTypeApp.__new__(cat_type.CatTypeApp)
        app._tray_icon = Tray()
        real_thread = threading.Thread

        def run_now(target, **kwargs):
            def wrapped():
                target()
                done.set()
            return real_thread(target=wrapped, **kwargs)

        with patch.object(cat_type, "post_notice", post), \
                patch.object(cat_type.sys, "platform", platform), \
                patch.object(cat_type.threading, "Thread", run_now):
            app._notify_accessories((ACCESSORY_BY_ID["round-glasses"],))
            self.assertTrue(done.wait(2))
        return posted, tray

    def test_macos_posts_a_native_notice_with_the_app_icon(self):
        posted, tray = self.notify(native_result=True)
        self.assertEqual(posted, [("New accessory unlocked",
                                   "Round glasses is ready to try on in your Wardrobe.",
                                   "unlock-round-glasses")])
        self.assertEqual(tray, [])

    def test_tray_notice_stands_in_when_macos_refuses_the_app(self):
        posted, tray = self.notify(native_result="refused")
        self.assertEqual(len(posted), 1)
        self.assertEqual(len(tray), 1)
        # The unused picture is cleaned up.
        self.assertFalse(Path(self.pictures[0]).exists())

    def test_macos_notice_carries_a_picture_of_the_cat_in_its_new_item(self):
        self.notify(native_result=True)
        picture = Path(self.pictures[0])
        self.addCleanup(picture.unlink, missing_ok=True)
        with Image.open(picture) as image:
            self.assertEqual(image.width, image.height)
            self.assertGreaterEqual(image.width, 200)
            self.assertEqual(image.mode, "RGBA")

    def test_tray_notice_is_the_fallback(self):
        posted, tray = self.notify(native_result=False)
        self.assertEqual(len(posted), 1)
        self.assertEqual(tray, [("New accessory unlocked",
                                 "Round glasses is ready to try on in your Wardrobe.")])

    def test_other_platforms_use_the_tray(self):
        posted, tray = self.notify(native_result=True, platform="win32")
        self.assertEqual(posted, [])
        self.assertEqual(len(tray), 1)


if __name__ == "__main__":
    unittest.main()
