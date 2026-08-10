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
                duration=0.2,
            )

    def test_rejects_runtime_failure_diagnostics(self) -> None:
        smoke = self._module()
        for diagnostic in (
            "Could not install the keyboard activity listener",
            "Keyboard listener unavailable:",
            "ModuleNotFoundError:",
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


if __name__ == "__main__":
    unittest.main()
