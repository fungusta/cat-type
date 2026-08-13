"""Exercise Linux replacement using a copied frozen executable as the old app."""

from __future__ import annotations

import argparse
import io
import os
import shlex
import shutil
import signal
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path

from platform_updater import LinuxPortableInstaller


def run_frozen_update_smoke(executable: Path, timeout: float = 8.0) -> None:
    executable = executable.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="cat-type-frozen-update-") as raw:
        directory = Path(raw)
        current = directory / "Cat Type"
        archive = directory / "Cat-Type-Linux-x64.tar.gz"
        launch_log = directory / "replacement.pid"
        shutil.copy2(executable, current)
        replacement = (
            "#!/bin/sh\n"
            f"printf '%s\\n' \"$$\" > {shlex.quote(str(launch_log))}\n"
            "while :; do sleep 1; done\n"
        ).encode("utf-8")
        member = tarfile.TarInfo("Cat Type")
        member.size = len(replacement)
        member.mode = 0o755
        with tarfile.open(archive, "w:gz") as package:
            package.addfile(member, io.BytesIO(replacement))

        installer = LinuxPortableInstaller(
            executable=current,
            frozen=True,
            helper_health_seconds=0.2,
        )
        prepared = installer.prepare(archive, "999.0.0")
        old_process = subprocess.Popen(
            ["/bin/sh", "-c", "while :; do sleep 1; done"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        replacement_pid: int | None = None
        try:
            installer.start(prepared, pid=old_process.pid)
            old_process.terminate()
            old_process.wait(timeout=2.0)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if launch_log.exists() and not prepared.backup.exists():
                    replacement_pid = int(launch_log.read_text().strip())
                    break
                time.sleep(0.02)
            else:
                raise RuntimeError("frozen Linux replacement did not complete")
            helper_status = installer._helper_process.wait(timeout=2.0)
            if helper_status != 0:
                raise RuntimeError(
                    f"Linux replacement helper exited with status {helper_status}"
                )
            if current.read_bytes() != replacement:
                raise RuntimeError("Linux replacement bytes do not match staging")
            if prepared.staged.exists() or prepared.backup.exists():
                raise RuntimeError("Linux staging or backup remained after success")
        finally:
            if old_process.poll() is None:
                old_process.kill()
                old_process.wait()
            if replacement_pid is not None:
                try:
                    os.kill(replacement_pid, signal.SIGKILL)
                except OSError:
                    pass

    with tempfile.TemporaryDirectory(prefix="cat-type-protected-update-") as raw:
        directory = Path(raw)
        current = directory / "Cat Type"
        shutil.copy2(executable, current)
        directory.chmod(0o555)
        try:
            availability = LinuxPortableInstaller(
                executable=current,
                frozen=True,
            ).availability()
            if availability.can_install or "protected" not in availability.status.lower():
                raise RuntimeError(
                    f"unexpected protected-directory status: {availability.status}"
                )
        finally:
            directory.chmod(0o755)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Smoke test a frozen Linux Cat Type replacement."
    )
    parser.add_argument("executable", type=Path)
    parser.add_argument("--timeout", type=float, default=8.0)
    args = parser.parse_args()
    try:
        run_frozen_update_smoke(args.executable, args.timeout)
    except (OSError, RuntimeError, ValueError) as error:
        raise SystemExit(str(error)) from error
    print("Frozen Linux update smoke passed.")


if __name__ == "__main__":
    main()
