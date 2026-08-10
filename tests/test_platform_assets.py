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


class PlatformBackendTests(unittest.TestCase):
    def test_selects_native_input_and_tray_backends(self) -> None:
        platform_assets = importlib.import_module("platform_assets")
        self.assertTrue(
            hasattr(platform_assets, "backend_modules"),
            "platform_assets.backend_modules must exist",
        )

        expected = {
            "darwin": (
                "pynput.keyboard._darwin",
                "pynput.mouse._darwin",
                "pystray._darwin",
            ),
            "linux": (
                "pynput.keyboard._xorg",
                "pynput.mouse._xorg",
                "pystray._xorg",
            ),
        }
        for platform, modules in expected.items():
            with self.subTest(platform=platform):
                self.assertEqual(
                    platform_assets.backend_modules(platform),
                    modules,
                )

    def test_runtime_modules_include_pillow_tk_bridge(self) -> None:
        platform_assets = importlib.import_module("platform_assets")
        self.assertTrue(
            hasattr(platform_assets, "runtime_modules"),
            "platform_assets.runtime_modules must exist",
        )
        self.assertEqual(
            platform_assets.runtime_modules("linux"),
            (
                "PIL._tkinter_finder",
                "pynput.keyboard._xorg",
                "pynput.mouse._xorg",
                "pystray._xorg",
            ),
        )
        self.assertEqual(
            platform_assets.runtime_modules("win32"),
            ("PIL._tkinter_finder",),
        )


if __name__ == "__main__":
    unittest.main()
