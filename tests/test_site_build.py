import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cat_accessories import ACCESSORIES, ACCESSORY_BLURBS, Accessory


HIDDEN_IDS = {item.id for item in ACCESSORIES if item.hidden}
TEXT_SUFFIXES = {".html", ".css", ".js", ".json", ".svg"}


class SiteBuildTests(unittest.TestCase):
    def module(self):
        from scripts import build_site
        return build_site

    def build(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return self.module().build_site(Path(directory.name) / "site")

    def test_starter_items_follow_the_rule(self):
        ids = {item.id for item in self.module().starter_items()}
        self.assertEqual(ids, {
            "ribbon-clip", "round-glasses", "bell-collar", "bow-tie",
            "beanie", "daisy-clip", "sunglasses",
        })

    def test_starter_rule_never_admits_hidden_items(self):
        module = self.module()
        secret = Accessory("cheap-secret", "Cheap secret", "hat", "Shh", "keystrokes", 10, hidden=True)
        with patch.object(module, "ACCESSORIES", ACCESSORIES + (secret,)):
            ids = {item.id for item in module.starter_items()}
        self.assertNotIn("cheap-secret", ids)

    def test_pretend_week_matches_spec(self):
        module = self.module()
        self.assertEqual(len(module.PRETEND_WEEK), 7)
        self.assertEqual(sum(module.PRETEND_WEEK), 10_500)
        catalog = module.catalog()
        self.assertEqual(catalog["today"], 1440)
        self.assertEqual(catalog["last7"], 10_500)
        self.assertEqual(catalog["allTime"], 10_500)
        self.assertEqual(catalog["week"], list(module.PRETEND_WEEK))

    def test_showcase_progress_agrees_with_thresholds(self):
        showcase = {item["id"]: item for item in self.module().catalog()["showcase"]}
        self.assertEqual(list(showcase), ["beanie", "party-hat", "crown", "dragon-wings"])
        self.assertEqual(showcase["beanie"]["progress"], 100)
        self.assertIs(showcase["beanie"]["equipped"], True)
        self.assertEqual(showcase["party-hat"]["progress"], 21)
        self.assertEqual(showcase["crown"]["progress"], 10)
        self.assertEqual(showcase["dragon-wings"]["progress"], 2)
        for item_id in ("party-hat", "crown", "dragon-wings"):
            self.assertIs(showcase[item_id]["equipped"], False)
        for item_id, item in showcase.items():
            self.assertEqual(item["blurb"], ACCESSORY_BLURBS[item_id])

    def test_build_publishes_no_hidden_or_linux_content(self):
        out = self.build()
        stems = {path.stem for path in (out / "assets" / "accessories").glob("*.svg")}
        self.assertFalse(stems & HIDDEN_IDS)
        for path in out.rglob("*"):
            if path.suffix in TEXT_SUFFIXES:
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("Linux", text, path)
                for hidden in HIDDEN_IDS:
                    self.assertNotIn(hidden, text, path)
        json.loads((out / "catalog.json").read_text(encoding="utf-8"))

    def test_build_copies_all_six_cats_and_excludes_site_tests(self):
        out = self.build()
        self.assertEqual(len(list((out / "assets" / "cats").glob("*.svg"))), 6)
        self.assertFalse((out / "tests").exists())


if __name__ == "__main__":
    unittest.main()
