from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from platform_updater import (
    LINUX_HELPER_SOURCE,
    LinuxPortableInstaller,
    PreparedLinuxUpdate,
)


def _script(path: Path, body: str) -> None:
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(0o755)


@unittest.skipUnless(
    sys.platform.startswith("linux"),
    "Linux helper integration requires Linux process and filesystem semantics",
)
class LinuxHelperContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.current = self.directory / "Cat Type $current;safe"
        self.staged = self.directory / ".Cat Type $current;safe.123.new"
        self.backup = self.directory / "Cat Type $current;safe.previous"
        _script(self.current, "exit 0\n")
        _script(self.staged, "exit 0\n")

    def prepared(self) -> PreparedLinuxUpdate:
        return PreparedLinuxUpdate(
            self.current.resolve(),
            self.staged.resolve(),
            self.backup.resolve(),
        )

    def test_start_uses_constant_shell_source_positional_args_and_detached_streams(
        self,
    ) -> None:
        popen = Mock(return_value=object())
        installer = LinuxPortableInstaller(
            executable=self.current,
            frozen=True,
            popen=popen,
            helper_health_seconds=0.2,
        )

        installer.start(self.prepared(), pid=os.getpid())

        command = popen.call_args.args[0]
        self.assertEqual(command[:3], ["/bin/sh", "-c", LINUX_HELPER_SOURCE])
        self.assertEqual(command[3], "cat-type-linux-updater")
        self.assertEqual(command[4], str(os.getpid()))
        self.assertEqual(
            command[6:9],
            [
                str(self.current.resolve()),
                str(self.staged.resolve()),
                str(self.backup.resolve()),
            ],
        )
        self.assertNotIn(str(self.current), LINUX_HELPER_SOURCE)
        self.assertNotIn(str(self.staged), LINUX_HELPER_SOURCE)
        self.assertEqual(command[9], "0.2")
        self.assertEqual(
            popen.call_args.kwargs,
            {
                "start_new_session": True,
                "stdin": subprocess.DEVNULL,
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
                "close_fds": True,
            },
        )

    def test_start_rejects_bad_pid_prepared_paths_and_existing_backup_before_popen(
        self,
    ) -> None:
        popen = Mock()
        installer = LinuxPortableInstaller(
            executable=self.current,
            frozen=True,
            popen=popen,
            helper_health_seconds=0.2,
        )
        invalid = (
            (self.prepared(), 0),
            (PreparedLinuxUpdate(self.current, self.current, self.backup), 1),
            (
                PreparedLinuxUpdate(
                    self.current,
                    self.staged,
                    self.directory / "wrong.previous",
                ),
                1,
            ),
        )
        for prepared, pid in invalid:
            with self.subTest(prepared=prepared, pid=pid):
                with self.assertRaises((TypeError, ValueError, RuntimeError)):
                    installer.start(prepared, pid=pid)
        self.backup.write_bytes(b"occupied")
        with self.assertRaisesRegex(RuntimeError, "backup"):
            installer.start(self.prepared(), pid=1)
        popen.assert_not_called()

    def test_popen_failure_propagates_without_changing_files(self) -> None:
        lock = Path(f"{self.backup}.lock")
        lock_seen_by_popen: list[bool] = []

        def fail_popen(*_args, **_kwargs):
            lock_seen_by_popen.append(lock.is_dir())
            raise OSError("cannot start helper")

        installer = LinuxPortableInstaller(
            executable=self.current,
            frozen=True,
            popen=fail_popen,
            helper_health_seconds=0.2,
        )
        old = self.current.read_bytes()
        new = self.staged.read_bytes()

        with self.assertRaisesRegex(OSError, "cannot start helper"):
            installer.start(self.prepared(), pid=os.getpid())

        self.assertEqual(self.current.read_bytes(), old)
        self.assertEqual(self.staged.read_bytes(), new)
        self.assertFalse(self.backup.exists())
        self.assertEqual(lock_seen_by_popen, [True])
        self.assertFalse(lock.exists())

    def test_existing_exact_update_lock_rejects_before_popen(self) -> None:
        popen = Mock()
        installer = LinuxPortableInstaller(
            executable=self.current,
            frozen=True,
            popen=popen,
            helper_health_seconds=0.2,
        )
        lock = Path(f"{self.backup}.lock")
        lock.mkdir()
        old = self.current.read_bytes()
        new = self.staged.read_bytes()

        with self.assertRaisesRegex(RuntimeError, "already in progress"):
            installer.start(self.prepared(), pid=os.getpid())

        popen.assert_not_called()
        self.assertEqual(self.current.read_bytes(), old)
        self.assertEqual(self.staged.read_bytes(), new)
        self.assertFalse(self.backup.exists())
        self.assertTrue(lock.is_dir())

    def test_omitted_pid_is_resolved_when_start_is_called(self) -> None:
        popen = Mock(return_value=object())
        installer = LinuxPortableInstaller(
            executable=self.current,
            frozen=True,
            popen=popen,
            helper_health_seconds=0.2,
        )
        live_pid = os.getpid()

        with patch("platform_updater.os.getpid", return_value=live_pid) as getpid:
            installer.start(self.prepared())

        getpid.assert_called_once_with()
        self.assertEqual(popen.call_args.args[0][4], str(live_pid))

    def test_helper_rejects_a_zombie_replacement_before_removing_backup(
        self,
    ) -> None:
        self.assertIn('"/proc/$new_pid/stat"', LINUX_HELPER_SOURCE)
        self.assertIn('[ "$new_state" = "Z" ]', LINUX_HELPER_SOURCE)
        self.assertLess(
            LINUX_HELPER_SOURCE.index('[ "$new_state" = "Z" ]'),
            LINUX_HELPER_SOURCE.index('rm -f -- "$backup"'),
        )

    def test_post_move_invariant_failure_restores_canonical_old_path(self) -> None:
        branch = LINUX_HELPER_SOURCE.split(
            'if path_exists "$staged" || ! path_exists "$current"; then',
            1,
        )[1].split("fi", 1)[0]

        self.assertIn("restore_old", branch)
        self.assertNotIn('"$backup" </dev/null', branch)

    def test_start_rejects_staging_file_without_executable_bits(self) -> None:
        popen = Mock()
        self.staged.chmod(0o600)
        installer = LinuxPortableInstaller(
            executable=self.current,
            frozen=True,
            popen=popen,
            helper_health_seconds=0.2,
        )

        with self.assertRaisesRegex(RuntimeError, "staging"):
            installer.start(self.prepared(), pid=os.getpid())

        popen.assert_not_called()


@unittest.skipUnless(
    sys.platform.startswith("linux"),
    "Linux helper integration requires Linux process and filesystem semantics",
)
class LinuxHelperIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name) / "folder with spaces $x;literal"
        self.directory.mkdir()
        self.current = self.directory / "Cat Type executable"
        self.staged = self.directory / ".Cat Type executable.random.new"
        self.backup = self.directory / "Cat Type executable.previous"
        self.log = self.directory / "launch log"
        self.installer = LinuxPortableInstaller(
            executable=self.current,
            frozen=True,
            helper_health_seconds=0.2,
        )

    def prepared(self) -> PreparedLinuxUpdate:
        return PreparedLinuxUpdate(
            self.current.resolve(),
            self.staged.resolve(),
            self.backup.resolve(),
        )

    def wait_for(self, predicate, timeout: float = 4.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.02)
        self.fail("timed out waiting for Linux helper")

    def sleeper(self) -> subprocess.Popen[bytes]:
        process = subprocess.Popen(
            ["/bin/sh", "-c", "while :; do sleep 1; done"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.addCleanup(process.kill)
        return process

    def test_waits_then_replaces_relaunches_and_removes_backup_after_health_window(
        self,
    ) -> None:
        _script(self.current, f"printf 'old\\n' >> {self._quoted_log()}\n")
        _script(
            self.staged,
            f"printf 'new\\n' >> {self._quoted_log()}\nwhile :; do sleep 1; done\n",
        )
        old_bytes = self.current.read_bytes()
        new_bytes = self.staged.read_bytes()
        process = self.sleeper()

        self.installer.start(self.prepared(), pid=process.pid)
        time.sleep(0.1)
        self.assertEqual(self.current.read_bytes(), old_bytes)
        process.terminate()
        process.wait(timeout=2)

        self.wait_for(lambda: self.log.exists() and "new" in self.log.read_text())
        self.wait_for(lambda: not self.backup.exists())
        self.assertEqual(self.installer._helper_process.wait(timeout=2), 0)
        self.assertEqual(self.current.read_bytes(), new_bytes)
        self.assertFalse(self.staged.exists())
        self.assertFalse(Path(f"{self.backup}.lock").exists())
        self.assertNotIn("old", self.log.read_text())

    def test_new_early_exit_rolls_back_and_relaunches_old(self) -> None:
        _script(self.current, f"printf 'old\\n' >> {self._quoted_log()}\n")
        old_bytes = self.current.read_bytes()
        _script(self.staged, f"printf 'new\\n' >> {self._quoted_log()}\nexit 7\n")
        process = self.sleeper()

        self.installer.start(self.prepared(), pid=process.pid)
        process.terminate()
        process.wait(timeout=2)

        self.wait_for(
            lambda: self.log.exists()
            and self.log.read_text().splitlines() == ["new", "old"]
        )
        self.wait_for(lambda: not self.backup.exists())
        self.assertEqual(self.installer._helper_process.wait(timeout=2), 1)
        self.assertEqual(self.current.read_bytes(), old_bytes)

    def test_missing_staged_at_rename_time_restores_and_relaunches_old(self) -> None:
        _script(self.current, f"printf 'old\\n' >> {self._quoted_log()}\n")
        old_bytes = self.current.read_bytes()
        _script(self.staged, "exit 0\n")
        process = self.sleeper()

        self.installer.start(self.prepared(), pid=process.pid)
        self.staged.unlink()
        process.terminate()
        process.wait(timeout=2)

        self.wait_for(lambda: self.log.exists() and self.log.read_text() == "old\n")
        self.assertEqual(self.installer._helper_process.wait(timeout=2), 1)
        self.assertEqual(self.current.read_bytes(), old_bytes)
        self.assertFalse(self.backup.exists())

    def test_current_rename_failure_relaunches_unchanged_old_executable(self) -> None:
        _script(self.current, f"printf 'old\\n' >> {self._quoted_log()}\n")
        old_bytes = self.current.read_bytes()
        _script(self.staged, "exit 0\n")
        process = self.sleeper()

        self.installer.start(self.prepared(), pid=process.pid)
        self.backup.mkdir()
        process.terminate()
        process.wait(timeout=2)

        self.wait_for(lambda: self.log.exists() and self.log.read_text() == "old\n")
        self.assertEqual(self.installer._helper_process.wait(timeout=2), 1)
        self.assertEqual(self.current.read_bytes(), old_bytes)
        self.assertTrue(self.staged.exists())

    def test_backup_appearing_after_start_is_not_overwritten(self) -> None:
        _script(self.current, f"printf 'old\\n' >> {self._quoted_log()}\n")
        old_bytes = self.current.read_bytes()
        _script(self.staged, "exit 0\n")
        process = self.sleeper()

        self.installer.start(self.prepared(), pid=process.pid)
        self.backup.write_bytes(b"concurrent backup")
        process.terminate()
        process.wait(timeout=2)

        self.wait_for(lambda: self.log.exists() and self.log.read_text() == "old\n")
        self.assertEqual(self.installer._helper_process.wait(timeout=2), 1)
        self.assertEqual(self.current.read_bytes(), old_bytes)
        self.assertEqual(self.backup.read_bytes(), b"concurrent backup")
        self.assertTrue(self.staged.exists())

    def _quoted_log(self) -> str:
        return "'" + str(self.log).replace("'", "'\\''") + "'"


if __name__ == "__main__":
    unittest.main()
