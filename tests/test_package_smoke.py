import importlib
import importlib.util
import sys
import unittest


class PackageSmokeTests(unittest.TestCase):
    def _module(self):
        spec = importlib.util.find_spec("scripts.smoke_linux_package")
        self.assertIsNotNone(spec, "Linux package smoke tester must exist")
        return importlib.import_module("scripts.smoke_linux_package")

    def test_accepts_process_that_remains_alive(self) -> None:
        smoke = self._module()
        output = smoke.run_startup_smoke(
            [sys.executable, "-c", "import time; time.sleep(1)"],
            duration=0.05,
        )
        self.assertEqual(output, "")

    def test_rejects_process_that_exits_early(self) -> None:
        smoke = self._module()
        with self.assertRaisesRegex(RuntimeError, "exited with status 7"):
            smoke.run_startup_smoke(
                [sys.executable, "-c", "raise SystemExit(7)"],
                duration=2.0,
            )

    def test_rejects_runtime_failure_diagnostics(self) -> None:
        smoke = self._module()
        for diagnostic in (
            "Could not install the keyboard activity listener",
            "Keyboard listener unavailable:",
            "ModuleNotFoundError:",
            "ImportError:",
            "Update startup failed:",
            "Exception in Tkinter callback",
        ):
            with self.subTest(diagnostic=diagnostic):
                with self.assertRaisesRegex(RuntimeError, diagnostic):
                    smoke.ensure_clean_startup_output(diagnostic)

    def test_allows_missing_tray_host_diagnostics(self) -> None:
        smoke = self._module()
        smoke.ensure_clean_startup_output(
            "Failed to dock icon\npystray._xorg.AssertionError"
        )



class MacUpdateSmokeTests(unittest.TestCase):
    def _module(self):
        spec = importlib.util.find_spec("scripts.smoke_macos_update")
        self.assertIsNotNone(spec, "macOS update smoke tester must exist")
        return importlib.import_module("scripts.smoke_macos_update")

    def test_smoke_macos_update_parses_app_and_optional_dmg(self) -> None:
        smoke = self._module()

        without = smoke.parse_args(["--app", "dist/Cat Type.app"])
        with_dmg = smoke.parse_args(
            ["--app", "dist/Cat Type.app", "--dmg", "dist/Cat-Type-macOS-arm64.dmg"]
        )

        self.assertEqual(str(without.app), "dist/Cat Type.app")
        self.assertIsNone(without.dmg)
        self.assertEqual(str(with_dmg.dmg), "dist/Cat-Type-macOS-arm64.dmg")

    @unittest.skipUnless(sys.platform == "darwin", "requires macOS")
    def test_swap_smoke_passes_against_a_bundle_with_the_helper(self) -> None:
        import plistlib
        import tempfile
        from pathlib import Path

        from scripts.build_macos_update_helper import build_update_helper

        smoke = self._module()
        with tempfile.TemporaryDirectory() as raw:
            app = Path(raw) / "Cat Type.app"
            (app / "Contents" / "MacOS").mkdir(parents=True)
            with (app / "Contents" / "Info.plist").open("wb") as info:
                plistlib.dump({"CFBundleIdentifier": "com.fungusta.cat-type"}, info)
            build_update_helper(
                app / "Contents" / "Frameworks" / "cat-type-update-helper"
            )

            smoke.run_swap_smoke(app)


if __name__ == "__main__":
    unittest.main()
