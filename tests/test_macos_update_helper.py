"""Exercise the compiled macOS update swap helper against throwaway bundles."""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path


def _clang_available() -> bool:
    if sys.platform != "darwin":
        return False
    try:
        return (
            subprocess.run(
                ["xcrun", "--find", "clang"],
                capture_output=True,
                check=False,
            ).returncode
            == 0
        )
    except OSError:
        return False


def make_bundle(path: Path, marker: str) -> Path:
    contents = path / "Contents"
    (contents / "MacOS").mkdir(parents=True)
    with (contents / "Info.plist").open("wb") as info:
        plistlib.dump({"CFBundleIdentifier": "com.fungusta.cat-type"}, info)
    (contents / "marker.txt").write_text(marker, encoding="utf-8")
    return path


def read_marker(bundle: Path) -> str:
    return (bundle / "Contents" / "marker.txt").read_text(encoding="utf-8")


@unittest.skipUnless(_clang_available(), "requires macOS with clang")
class MacUpdateHelperTests(unittest.TestCase):
    helper: Path

    @classmethod
    def setUpClass(cls) -> None:
        from scripts.build_macos_update_helper import build_update_helper

        cls._build_dir = tempfile.TemporaryDirectory()
        cls.helper = build_update_helper(
            Path(cls._build_dir.name) / "cat-type-update-helper"
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._build_dir.cleanup()

    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.parent = self.root / "Apps"
        self.parent.mkdir()
        self.recorder_log = self.root / "open-calls.txt"
        self.open_tool = self.root / "fake-open"
        self.open_tool.write_text(
            "#!/bin/sh\n"
            f"printf '%s\\n' \"$@\" >> '{self.recorder_log}'\n",
            encoding="utf-8",
        )
        self.open_tool.chmod(0o755)

    def layout(self, parent: Path | None = None, name: str = "Cat Type.app"):
        parent = parent or self.parent
        installed = make_bundle(parent / name, "old")
        staging_dir = Path(tempfile.mkdtemp(prefix=".cat-type-update-", dir=parent))
        staged = make_bundle(staging_dir / name, "new")
        lock_dir = Path(f"{installed}.update-lock")
        lock_dir.mkdir()
        (lock_dir / "helper.pid").write_text("1\n", encoding="utf-8")
        helper_dir = Path(
            tempfile.mkdtemp(prefix="cat-type-update-helper-", dir=self.root)
        )
        helper = helper_dir / "cat-type-update-helper"
        shutil.copy2(self.helper, helper)
        return installed, staged, staging_dir, lock_dir, helper_dir, helper

    def exited_pid(self) -> int:
        process = subprocess.Popen(["/usr/bin/true"])
        process.wait()
        return process.pid

    def short_lived_pid(self, seconds: float) -> int:
        process = subprocess.Popen(["/bin/sleep", str(seconds)])
        threading.Thread(target=process.wait, daemon=True).start()
        return process.pid

    def run_helper(
        self,
        pid: int,
        installed: Path,
        staged: Path,
        staging_dir: Path,
        lock_dir: Path,
        helper_dir: Path,
        helper: Path,
        *,
        swap_mode: str = "swap",
        wait_seconds: int = 300,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(helper),
                str(pid),
                str(installed),
                str(staged),
                str(staging_dir),
                str(lock_dir),
                str(helper_dir),
                str(self.open_tool),
                "-",
                swap_mode,
                str(wait_seconds),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def open_calls(self) -> list[str]:
        if not self.recorder_log.exists():
            return []
        return self.recorder_log.read_text(encoding="utf-8").splitlines()

    def assert_cleaned(self, staging_dir: Path, lock_dir: Path, helper_dir: Path):
        self.assertFalse(staging_dir.exists())
        self.assertFalse(lock_dir.exists())
        self.assertFalse(helper_dir.exists())

    def test_swap_replaces_bundle_removes_staging_lock_helper_dir_and_relaunches(
        self,
    ) -> None:
        installed, staged, staging, lock, helper_dir, helper = self.layout()
        pid = self.short_lived_pid(0.3)

        result = self.run_helper(pid, installed, staged, staging, lock, helper_dir, helper)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("falling back", result.stderr)
        self.assertEqual(read_marker(installed), "new")
        self.assert_cleaned(staging, lock, helper_dir)
        self.assertEqual(self.open_calls(), [str(installed)])

    def test_move_mode_replaces_bundle_the_same_way(self) -> None:
        installed, staged, staging, lock, helper_dir, helper = self.layout()

        result = self.run_helper(
            self.exited_pid(),
            installed,
            staged,
            staging,
            lock,
            helper_dir,
            helper,
            swap_mode="move",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(read_marker(installed), "new")
        self.assert_cleaned(staging, lock, helper_dir)
        self.assertEqual(self.open_calls(), [str(installed)])

    def test_restores_old_bundle_when_new_cannot_move_in(self) -> None:
        installed, staged, staging, lock, helper_dir, helper = self.layout()
        shutil.rmtree(staged)

        result = self.run_helper(
            self.exited_pid(), installed, staged, staging, lock, helper_dir, helper
        )

        self.assertEqual(result.returncode, 4, result.stderr)
        self.assertEqual(read_marker(installed), "old")
        self.assert_cleaned(staging, lock, helper_dir)
        self.assertEqual(self.open_calls(), [str(installed)])

    def test_times_out_without_touching_installed_bundle(self) -> None:
        installed, staged, staging, lock, helper_dir, helper = self.layout()
        sleeper = subprocess.Popen(["/bin/sleep", "30"])
        self.addCleanup(sleeper.wait)
        self.addCleanup(sleeper.kill)

        started = time.monotonic()
        result = self.run_helper(
            sleeper.pid,
            installed,
            staged,
            staging,
            lock,
            helper_dir,
            helper,
            wait_seconds=1,
        )

        self.assertLess(time.monotonic() - started, 10)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(read_marker(installed), "old")
        self.assert_cleaned(staging, lock, helper_dir)
        self.assertEqual(self.open_calls(), [])

    def test_reused_pid_with_new_start_time_counts_as_exited(self) -> None:
        installed, staged, staging, lock, helper_dir, helper = self.layout()

        started = time.monotonic()
        result = self.run_helper(
            self.exited_pid(), installed, staged, staging, lock, helper_dir, helper
        )

        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(read_marker(installed), "new")

    def test_handles_spaces_and_non_ascii_paths(self) -> None:
        parent = self.root / "zoë apps"
        parent.mkdir()
        installed, staged, staging, lock, helper_dir, helper = self.layout(parent)

        result = self.run_helper(
            self.exited_pid(), installed, staged, staging, lock, helper_dir, helper
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(read_marker(installed), "new")
        self.assertEqual(self.open_calls(), [str(installed)])

    def test_rejects_wrong_argument_count_with_exit_2(self) -> None:
        result = subprocess.run(
            [str(self.helper), "1", "2"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("usage", result.stderr)

    def test_rejects_paths_outside_the_expected_layout_with_exit_2(self) -> None:
        installed, staged, staging, lock, helper_dir, helper = self.layout()
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()

        result = self.run_helper(
            self.exited_pid(), installed, staged, elsewhere, lock, helper_dir, helper
        )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(read_marker(installed), "old")
        self.assertTrue(elsewhere.exists())
        self.assertTrue(staging.exists())


if __name__ == "__main__":
    unittest.main()
