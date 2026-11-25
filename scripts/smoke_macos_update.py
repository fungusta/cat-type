"""Smoke-test macOS self-update against a freshly built Cat Type.app.

Without ``--dmg`` (unsigned PR builds) only the bundled swap helper is
exercised. With ``--dmg`` (notarized release builds) the real ``prepare`` step
also mounts the disk image and validates the signature, Gatekeeper
assessment, and version before the helper swaps a copy of the app.
"""

from __future__ import annotations

import argparse
import plistlib
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from app_version import APP_VERSION
from macos_updater import (
    CODESIGN,
    HELPER_DIR_PREFIX,
    HELPER_NAME,
    LOCK_SUFFIX,
    STAGING_PREFIX,
    MacBundleInstaller,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--dmg", type=Path, default=None)
    return parser.parse_args(argv)


def _bundled_helper(app: Path) -> Path:
    helper = app / "Contents" / "Frameworks" / HELPER_NAME
    if not helper.is_file():
        raise RuntimeError(f"update helper missing from {app}")
    return helper


def _short_lived_pid() -> int:
    process = subprocess.Popen(["/bin/sleep", "0.5"])
    threading.Thread(target=process.wait, daemon=True).start()
    return process.pid


def _run_helper(
    helper: Path,
    installed: Path,
    staged: Path,
    staging_dir: Path,
    work: Path,
) -> list[str]:
    """Run the helper exactly as ``MacBundleInstaller.start`` lays it out."""
    lock = Path(f"{installed}{LOCK_SUFFIX}")
    lock.mkdir()
    helper_dir = Path(tempfile.mkdtemp(prefix=HELPER_DIR_PREFIX, dir=work))
    helper_copy = helper_dir / HELPER_NAME
    shutil.copy2(helper, helper_copy)
    recorder_log = work / "open-calls.txt"
    recorder = work / "fake-open"
    recorder.write_text(
        f"#!/bin/sh\nprintf '%s\\n' \"$@\" >> '{recorder_log}'\n", encoding="utf-8"
    )
    recorder.chmod(0o755)
    result = subprocess.run(
        [
            str(helper_copy),
            str(_short_lived_pid()),
            str(installed),
            str(staged),
            str(staging_dir),
            str(lock),
            str(helper_dir),
            str(recorder),
            "-",
            "swap",
            "30",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"update helper exited with {result.returncode}: {result.stderr.strip()}"
        )
    for leftover in (staging_dir, lock, helper_dir):
        if leftover.exists():
            raise RuntimeError(f"update helper left {leftover} behind")
    if not recorder_log.exists():
        raise RuntimeError("update helper did not relaunch the app")
    return recorder_log.read_text(encoding="utf-8").splitlines()


def _copy_bundle(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["/usr/bin/ditto", str(source), str(destination)], check=True)


def run_swap_smoke(app: Path) -> None:
    app = app.resolve(strict=True)
    helper = _bundled_helper(app)
    with tempfile.TemporaryDirectory(prefix="cat-type-mac-update-") as raw:
        work = Path(raw).resolve()
        installed = work / "Old Apps" / "Cat Type.app"
        _copy_bundle(app, installed)
        staging_dir = Path(tempfile.mkdtemp(prefix=STAGING_PREFIX, dir=installed.parent))
        staged = staging_dir / installed.name
        _copy_bundle(app, staged)
        marker = staged / "Contents" / "cat-type-smoke-marker"
        marker.write_text("new", encoding="utf-8")

        calls = _run_helper(helper, installed, staged, staging_dir, work)

        if not (installed / "Contents" / "cat-type-smoke-marker").exists():
            raise RuntimeError("the new bundle was not swapped into place")
        if calls != [str(installed)]:
            raise RuntimeError(f"unexpected relaunch calls: {calls}")


def run_dmg_smoke(app: Path, dmg: Path) -> None:
    app = app.resolve(strict=True)
    dmg = dmg.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="cat-type-mac-update-") as raw:
        work = Path(raw).resolve()
        installed = work / "Old Apps" / "Cat Type.app"
        _copy_bundle(app, installed)
        installer = MacBundleInstaller(
            executable=installed / "Contents" / "MacOS" / "Cat Type",
            frozen=True,
            helper=_bundled_helper(installed),
            current_version="0.0.0",
            log_path=work / "update-helper.log",
        )
        availability = installer.availability()
        if not availability.can_install:
            raise RuntimeError(availability.status)

        prepared = installer.prepare(dmg, APP_VERSION)
        calls = _run_helper(
            _bundled_helper(installed),
            prepared.installed,
            prepared.staged,
            prepared.staging_dir,
            work,
        )

        subprocess.run(
            [CODESIGN, "--verify", "--deep", "--strict", str(prepared.installed)],
            check=True,
        )
        with (prepared.installed / "Contents" / "Info.plist").open("rb") as info:
            version = plistlib.load(info).get("CFBundleShortVersionString")
        if version != APP_VERSION:
            raise RuntimeError(f"installed version is {version!r}, not {APP_VERSION}")
        if calls != [str(prepared.installed)]:
            raise RuntimeError(f"unexpected relaunch calls: {calls}")


def main(argv: list[str] | None = None) -> None:
    arguments = parse_args(argv)
    if arguments.dmg is None:
        run_swap_smoke(arguments.app)
    else:
        run_dmg_smoke(arguments.app, arguments.dmg)
    print("macOS update smoke passed")


if __name__ == "__main__":
    main()
