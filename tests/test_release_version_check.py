import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from app_version import APP_VERSION
from scripts.check_release_version import PROJECT_ROOT, metadata_mismatches


class ReleaseVersionCheckTests(unittest.TestCase):
    def copy_version_files(self) -> Path:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        root = Path(temporary_directory.name)
        for relative_path in (
            "app_version.py",
            "CatType.spec",
            "packaging/CatType.iss",
            "packaging/version_info.txt",
        ):
            destination = root / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(PROJECT_ROOT / relative_path, destination)
        return root

    def test_current_version_matches_every_platform_marker(self) -> None:
        self.assertEqual(APP_VERSION, "1.0.11")
        self.assertEqual(metadata_mismatches("1.0.11", PROJECT_ROOT), [])
        self.assertNotEqual(metadata_mismatches("1.0.10", PROJECT_ROOT), [])

    def test_runtime_version_drift_is_reported(self) -> None:
        root = self.copy_version_files()
        self.assertEqual(metadata_mismatches("1.0.11", root), [])

        (root / "app_version.py").write_text('APP_VERSION = "1.0.4"\n')

        self.assertIn("app_version.py", metadata_mismatches("1.0.11", root))

    def test_malformed_version_is_rejected_by_release_command(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "check_release_version.py"),
                "v1.0",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid release version: 1.0", result.stderr)


if __name__ == "__main__":
    unittest.main()
