import importlib
import importlib.util
import sys
import unittest


class PlatformIconTests(unittest.TestCase):
    def test_selects_native_icon_filename_for_each_platform(self) -> None:
        spec = importlib.util.find_spec("platform_assets")
        self.assertIsNotNone(spec, "platform_assets module must exist")
        platform_assets = importlib.import_module("platform_assets")

        expected = {
            "win32": "cat-type.ico",
            "darwin": "cat-type.icns",
            "linux": "cat-type.png",
        }
        for platform, filename in expected.items():
            with self.subTest(platform=platform):
                self.assertEqual(
                    platform_assets.icon_filename(platform),
                    filename,
                )

    def test_runtime_requests_current_platform_icon(self) -> None:
        from cat_type import APP_ICON

        expected = {
            "win32": "cat-type.ico",
            "darwin": "cat-type.icns",
        }.get(sys.platform, "cat-type.png")
        self.assertEqual(APP_ICON.name, expected)


if __name__ == "__main__":
    unittest.main()
