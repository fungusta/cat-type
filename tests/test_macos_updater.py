"""Tests for staging, verifying, and handing off macOS bundle updates."""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from auto_update import RELEASES_URL
from macos_updater import (
    CODE_REQUIREMENT,
    HELPER_NAME,
    LOCK_SUFFIX,
    STAGING_PREFIX,
    MacBundleInstaller,
    PreparedMacUpdate,
)


def make_bundle(
    path: Path,
    *,
    marker: str,
    version: str = "1.1.0",
    bundle_id: str = "com.fungusta.cat-type",
) -> Path:
    contents = path / "Contents"
    (contents / "MacOS").mkdir(parents=True)
    executable = contents / "MacOS" / "Cat Type"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)
    with (contents / "Info.plist").open("wb") as info:
        plistlib.dump(
            {
                "CFBundleIdentifier": bundle_id,
                "CFBundleShortVersionString": version,
            },
            info,
        )
    (contents / "marker.txt").write_text(marker, encoding="utf-8")
    return path


def marker(bundle: Path) -> str:
    return (bundle / "Contents" / "marker.txt").read_text(encoding="utf-8")


class FakeRunner:
    """Answer the macOS tools the installer calls, recording every argv."""

    def __init__(self, fixture: Path | None) -> None:
        self.fixture = fixture
        self.calls: list[list[str]] = []
        self.failures: dict[str, int] = {}
        self.volume_extras: dict[str, str] = {}
        self.app_as_symlink = False

    def fail(self, key: str, returncode: int = 1) -> None:
        self.failures[key] = returncode

    def __call__(self, argv: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(argv))
        key = self._key(argv)
        returncode = self.failures.get(key, 0)
        if returncode == 0 and key == "attach":
            mount = Path(argv[argv.index("-mountpoint") + 1])
            mount.mkdir(parents=True, exist_ok=True)
            if self.fixture is not None:
                if self.app_as_symlink:
                    (mount / "Cat Type.app").symlink_to(self.fixture)
                else:
                    shutil.copytree(
                        self.fixture, mount / "Cat Type.app", symlinks=True
                    )
            (mount / "Applications").symlink_to("/Applications")
        if returncode == 0 and key == "ditto":
            shutil.copytree(argv[1], argv[2], symlinks=True)
        if key == "detach":
            mount = Path(argv[2])
            for child in list(mount.iterdir()) if mount.exists() else []:
                if child.is_symlink():
                    child.unlink()
                else:
                    shutil.rmtree(child)
        return subprocess.CompletedProcess(argv, returncode, "", "failed" if returncode else "")

    @staticmethod
    def _key(argv: list[str]) -> str:
        tool = Path(argv[0]).name
        if tool == "hdiutil":
            return argv[1]
        if tool == "codesign":
            return "requirement" if "-R" in argv else "codesign"
        return tool

    def commands(self, key: str) -> list[list[str]]:
        return [argv for argv in self.calls if self._key(argv) == key]


class MacInstallerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.parent = self.root / "zoë apps"
        self.parent.mkdir()
        self.installed = make_bundle(
            self.parent / "Cat Type 2.app", marker="old", version="1.0.60"
        )
        self.executable = self.installed / "Contents" / "MacOS" / "Cat Type"
        self.helper = self.installed / "Contents" / "Frameworks" / HELPER_NAME
        self.helper.parent.mkdir()
        self.helper.write_text("#!/bin/sh\n", encoding="utf-8")
        self.helper.chmod(0o755)
        self.fixture = make_bundle(self.root / "fixture" / "Cat Type.app", marker="new")
        self.dmg = self.root / "Cat-Type-macOS-arm64.dmg"
        self.dmg.write_bytes(b"dmg")
        self.runner = FakeRunner(self.fixture)

    def installer(self, **overrides: object) -> MacBundleInstaller:
        options: dict[str, object] = {
            "executable": self.executable,
            "frozen": True,
            "run": self.runner,
            "helper": self.helper,
            "current_version": "1.0.60",
        }
        options.update(overrides)
        return MacBundleInstaller(**options)  # type: ignore[arg-type]

    def staging_dirs(self) -> list[Path]:
        return sorted(self.parent.glob(f"{STAGING_PREFIX}*"))


class MacCapabilityTests(MacInstallerTestCase):
    def test_bundle_path_is_enclosing_app_even_when_renamed(self) -> None:
        self.assertEqual(self.installer().bundle_path(), self.installed.resolve())

    def test_availability_ready(self) -> None:
        availability = self.installer().availability()

        self.assertTrue(availability.can_install)
        self.assertEqual(availability.status, "Automatic macOS updates are ready.")

    def test_availability_reports_each_fallback_in_order(self) -> None:
        loose = self.root / "loose" / "Cat Type"
        loose.parent.mkdir()
        loose.write_text("", encoding="utf-8")
        translocated = make_bundle(
            self.root / "AppTranslocation" / "ABC" / "d" / "Cat Type.app",
            marker="old",
        )

        class ReadOnly:
            f_flag = os.ST_RDONLY

        cases = [
            ("source", {"frozen": False}, None, "Source checkouts cannot update"),
            ("no bundle", {"executable": loose}, None, "unavailable for this build"),
            (
                "translocated",
                {
                    "executable": translocated / "Contents" / "MacOS" / "Cat Type",
                },
                None,
                "Move Cat Type to Applications",
            ),
            ("read-only", {}, "read-only", "Move Cat Type to Applications"),
            ("not writable", {}, "not-writable", "can't update itself in this location"),
            (
                "helper missing",
                {"helper": self.root / "missing-helper"},
                None,
                "unavailable in this build",
            ),
        ]
        for name, overrides, condition, expected in cases:
            with self.subTest(name=name):
                installer = self.installer(**overrides)
                if condition == "read-only":
                    with patch("macos_updater.os.statvfs", return_value=ReadOnly()):
                        availability = installer.availability()
                elif condition == "not-writable":
                    with patch(
                        "macos_updater.tempfile.mkstemp",
                        side_effect=PermissionError("denied"),
                    ):
                        availability = installer.availability()
                else:
                    availability = installer.availability()
                self.assertFalse(availability.can_install)
                self.assertIn(expected, availability.status)
                self.assertIn(RELEASES_URL, availability.status)

    def test_capability_probe_leaves_no_files_behind(self) -> None:
        before = set(self.parent.iterdir())

        self.installer().availability()

        self.assertEqual(set(self.parent.iterdir()), before)


class MacPrepareTests(MacInstallerTestCase):
    def test_prepare_stages_beside_installed_bundle_with_installed_name(self) -> None:
        prepared = self.installer().prepare(self.dmg, "1.1.0")

        self.assertIsInstance(prepared, PreparedMacUpdate)
        self.assertEqual(prepared.installed, self.installed.resolve())
        self.assertEqual(prepared.staging_dir.parent, self.installed.resolve().parent)
        self.assertTrue(prepared.staging_dir.name.startswith(STAGING_PREFIX))
        self.assertEqual(prepared.staged, prepared.staging_dir / "Cat Type 2.app")
        self.assertEqual(marker(prepared.staged), "new")
        self.assertEqual(marker(self.installed), "old")

    def test_prepare_runs_exact_validation_commands(self) -> None:
        prepared = self.installer().prepare(self.dmg, "1.1.0")
        staged = str(prepared.staged)

        attach = self.runner.commands("attach")
        self.assertEqual(len(attach), 1)
        self.assertEqual(
            attach[0][:6],
            ["/usr/bin/hdiutil", "attach", "-readonly", "-nobrowse", "-noautoopen", "-mountpoint"],
        )
        self.assertEqual(attach[0][-1], str(self.dmg))
        self.assertIn(
            ["/usr/bin/codesign", "--verify", "--deep", "--strict", staged],
            self.runner.calls,
        )
        self.assertIn(
            ["/usr/bin/codesign", "--verify", "--strict", "-R", f"={CODE_REQUIREMENT}", staged],
            self.runner.calls,
        )
        self.assertEqual(
            CODE_REQUIREMENT,
            'anchor apple generic and identifier "com.fungusta.cat-type" and '
            'certificate leaf[subject.OU] = "9B98U2J5Q2"',
        )
        self.assertIn(
            ["/usr/sbin/spctl", "--assess", "--type", "execute", staged],
            self.runner.calls,
        )
        self.assertIn(
            ["/usr/bin/xattr", "-dr", "com.apple.quarantine", staged],
            self.runner.calls,
        )
        self.assertEqual(len(self.runner.commands("detach")), 1)

    def test_prepare_rejects_and_cleans_staging_for_each_validation_failure(
        self,
    ) -> None:
        cases = {
            "attach fails": ("fail", "attach"),
            "codesign fails": ("fail", "codesign"),
            "requirement fails": ("fail", "requirement"),
            "spctl fails": ("fail", "spctl"),
            "ditto fails": ("fail", "ditto"),
            "wrong bundle id": ("fixture", {"bundle_id": "com.example.other"}),
            "version mismatch": ("fixture", {"version": "1.2.0"}),
            "same version": ("version", "1.0.60"),
            "older version": ("version", "1.0.59"),
            "app missing": ("missing", None),
            "app is a symlink": ("symlink", None),
        }
        for name, (kind, value) in cases.items():
            with self.subTest(name=name):
                self.runner = FakeRunner(self.fixture)
                version = "1.1.0"
                if kind == "fail":
                    self.runner.fail(str(value))
                elif kind == "fixture":
                    fixture = make_bundle(
                        self.root / f"fixture-{name}" / "Cat Type.app",
                        marker="new",
                        **value,  # type: ignore[arg-type]
                    )
                    self.runner = FakeRunner(fixture)
                elif kind == "version":
                    fixture = make_bundle(
                        self.root / f"fixture-{name}" / "Cat Type.app",
                        marker="new",
                        version=str(value),
                    )
                    self.runner = FakeRunner(fixture)
                    version = str(value)
                elif kind == "missing":
                    self.runner = FakeRunner(None)
                elif kind == "symlink":
                    self.runner.app_as_symlink = True

                with self.assertRaises(RuntimeError):
                    self.installer().prepare(self.dmg, version)

                self.assertEqual(self.staging_dirs(), [])
                self.assertEqual(marker(self.installed), "old")
                if kind != "fail" or value != "attach":
                    self.assertEqual(len(self.runner.commands("detach")), 1)

    def test_prepare_always_detaches_after_failure(self) -> None:
        self.runner.fail("spctl")

        with self.assertRaises(RuntimeError):
            self.installer().prepare(self.dmg, "1.1.0")

        detach = self.runner.commands("detach")
        self.assertEqual(len(detach), 1)
        self.assertEqual(detach[0][:2], ["/usr/bin/hdiutil", "detach"])
        self.assertIn("-force", detach[0])

    def test_prepare_removes_stale_staging_when_no_lock(self) -> None:
        stale = self.parent / f"{STAGING_PREFIX}leftover"
        make_bundle(stale / "Cat Type 2.app", marker="stale")

        prepared = self.installer().prepare(self.dmg, "1.1.0")

        self.assertFalse(stale.exists())
        self.assertEqual(self.staging_dirs(), [prepared.staging_dir])

    def test_prepare_clears_lock_whose_helper_is_dead_then_removes_staging(
        self,
    ) -> None:
        lock = Path(f"{self.installed.resolve()}{LOCK_SUFFIX}")
        lock.mkdir()
        dead = subprocess.Popen(["/usr/bin/true"])
        dead.wait()
        (lock / "helper.pid").write_text(f"{dead.pid}\n", encoding="utf-8")
        stale = self.parent / f"{STAGING_PREFIX}leftover"
        stale.mkdir()

        self.installer().prepare(self.dmg, "1.1.0")

        self.assertFalse(lock.exists())
        self.assertFalse(stale.exists())

    def test_prepare_refuses_while_live_helper_holds_lock(self) -> None:
        lock = Path(f"{self.installed.resolve()}{LOCK_SUFFIX}")
        lock.mkdir()
        (lock / "helper.pid").write_text(f"{os.getpid()}\n", encoding="utf-8")
        stale = self.parent / f"{STAGING_PREFIX}in-use"
        stale.mkdir()

        with self.assertRaisesRegex(RuntimeError, "already in progress"):
            self.installer().prepare(self.dmg, "1.1.0")

        self.assertTrue(lock.exists())
        self.assertTrue(stale.exists())
        self.assertEqual(self.runner.calls, [])

    def test_prepare_strips_quarantine_and_ignores_xattr_failure(self) -> None:
        self.runner.fail("xattr")

        prepared = self.installer().prepare(self.dmg, "1.1.0")

        self.assertEqual(marker(prepared.staged), "new")
        self.assertEqual(len(self.runner.commands("xattr")), 1)

    def test_prepare_refuses_when_installation_is_unavailable(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Source checkouts"):
            self.installer(frozen=False).prepare(self.dmg, "1.1.0")

        self.assertEqual(self.runner.calls, [])


if __name__ == "__main__":
    unittest.main()
