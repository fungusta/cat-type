import json
import tempfile
import unittest
from pathlib import Path

from cat_settings import AppSettings, SettingsStore


class AppSettingsTests(unittest.TestCase):
    def test_normalizes_invalid_and_out_of_range_values(self) -> None:
        settings = AppSettings(
            cat_style="blue",
            size_percent=999,
            hold_seconds=0.1,
            fade_seconds=20,
            placement="middle",
        ).normalized()

        self.assertEqual(settings.cat_style, "alternate")
        self.assertEqual(settings.size_percent, 175)
        self.assertEqual(settings.hold_seconds, 0.5)
        self.assertEqual(settings.fade_seconds, 0.5)
        self.assertEqual(settings.placement, "above-right")

    def test_store_round_trips_settings_and_ignores_unknown_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 99,
                        "enabled": False,
                        "cat_style": "ginger",
                        "future_option": "safe to ignore",
                    }
                ),
                encoding="utf-8",
            )

            settings = SettingsStore(path).load()
            self.assertFalse(settings.enabled)
            self.assertEqual(settings.cat_style, "ginger")

            settings.size_percent = 125
            saved = SettingsStore(path).save(settings)
            self.assertEqual(saved.size_percent, 125)
            self.assertEqual(SettingsStore(path).load(), saved)

    def test_bad_file_falls_back_to_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text("{bad json", encoding="utf-8")
            self.assertEqual(SettingsStore(path).load(), AppSettings())


if __name__ == "__main__":
    unittest.main()
