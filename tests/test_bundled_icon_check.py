import importlib
import importlib.util
import tempfile
import unittest
from pathlib import Path


class BundledIconCheckTests(unittest.TestCase):
    def _module(self):
        spec = importlib.util.find_spec("scripts.check_bundled_icon")
        self.assertIsNotNone(spec, "bundled icon checker must exist")
        return importlib.import_module("scripts.check_bundled_icon")

    def test_accepts_expected_platform_icon(self) -> None:
        checker = self._module()
        entry = checker.validate_bundled_icon(
            {"assets/cat-type.icns"},
            "darwin",
        )
        self.assertEqual(entry, "assets/cat-type.icns")

    def test_accepts_windows_archive_path_separator(self) -> None:
        checker = self._module()
        try:
            entry = checker.validate_bundled_icon(
                {r"assets\cat-type.ico"},
                "win32",
            )
        except ValueError as exc:
            self.fail(str(exc))
        self.assertEqual(entry, "assets/cat-type.ico")

    def test_rejects_another_platforms_icon(self) -> None:
        checker = self._module()
        with self.assertRaisesRegex(
            ValueError,
            "assets/cat-type.png",
        ):
            checker.validate_bundled_icon(
                {"assets/cat-type.ico"},
                "linux",
            )

    def test_reads_resources_from_a_macos_one_directory_bundle(self) -> None:
        checker = self._module()
        with tempfile.TemporaryDirectory() as directory:
            contents = Path(directory) / "Cat Type.app" / "Contents"
            executable = contents / "MacOS" / "Cat Type"
            icon = contents / "Resources" / "assets" / "cat-type.icns"
            executable.parent.mkdir(parents=True)
            executable.touch()
            icon.parent.mkdir(parents=True)
            icon.touch()

            entries = checker.external_bundle_entries(executable, "darwin")

        self.assertIn("assets/cat-type.icns", entries)


class BundledRuntimeModuleCheckTests(unittest.TestCase):
    def _module(self):
        return importlib.import_module("scripts.check_bundled_icon")

    def test_accepts_expected_linux_runtime_modules(self) -> None:
        checker = self._module()
        modules = checker.validate_bundled_runtime_modules(
            {
                "PIL._tkinter_finder",
                "pynput.keyboard._xorg",
                "pynput.mouse._xorg",
                "pystray._xorg",
            },
            "linux",
        )
        self.assertEqual(
            modules,
            (
                "PIL._tkinter_finder",
                "pynput.keyboard._xorg",
                "pynput.mouse._xorg",
                "pystray._xorg",
            ),
        )

    def test_rejects_missing_linux_input_backends(self) -> None:
        checker = self._module()
        with self.assertRaisesRegex(
            ValueError,
            "pynput.keyboard._xorg, pynput.mouse._xorg",
        ):
            checker.validate_bundled_runtime_modules(
                {"PIL._tkinter_finder", "pystray._xorg"},
                "linux",
            )

    def test_rejects_missing_windows_pynput_backends(self) -> None:
        checker = self._module()
        with self.assertRaisesRegex(ValueError, "pynput.keyboard._win32"):
            checker.validate_bundled_runtime_modules(
                {"PIL._tkinter_finder", "pynput.mouse._win32"},
                "win32",
            )

    def test_rejects_missing_pillow_tk_bridge(self) -> None:
        checker = self._module()
        with self.assertRaisesRegex(ValueError, "PIL._tkinter_finder"):
            checker.validate_bundled_runtime_modules(
                {
                    "pynput.keyboard._xorg",
                    "pynput.mouse._xorg",
                    "pystray._xorg",
                },
                "linux",
            )


if __name__ == "__main__":
    unittest.main()
