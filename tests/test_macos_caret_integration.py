import json
import subprocess
import sys
import unittest


IS_MACOS = sys.platform == "darwin"


@unittest.skipUnless(IS_MACOS, "requires macOS Accessibility")
class MacOSCaretIntegrationTests(unittest.TestCase):
    def test_focused_text_field_returns_caret_sized_screen_rectangle(
        self,
    ) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "tests.macos_caret_probe"],
            capture_output=True,
            text=True,
            timeout=10.0,
        )
        self.assertEqual(
            completed.returncode,
            0,
            completed.stderr or completed.stdout,
        )
        result = json.loads(completed.stdout)
        if result["status"] == "skipped":
            self.skipTest(result["reason"])

        self.assertEqual(result["source"], "macos-accessibility")
        self.assertLessEqual(result["width"], 2)
        self.assertGreaterEqual(result["height"], 10)


if __name__ == "__main__":
    unittest.main()
