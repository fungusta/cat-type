import importlib
import importlib.util
import unittest


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


if __name__ == "__main__":
    unittest.main()
