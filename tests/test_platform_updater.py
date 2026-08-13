from __future__ import annotations

import ctypes
import io
import inspect
import os
import queue
import stat
import sys
import tarfile
import tempfile
import threading
import unittest
from dataclasses import FrozenInstanceError
from ctypes import wintypes
from pathlib import Path
from unittest.mock import Mock, patch

import cat_type
import platform_updater
from cat_type import CatTypeApp
from platform_updater import (
    LinuxControllerInstaller,
    LinuxPortableInstaller,
    PreparedLinuxUpdate,
    WindowsControllerInstaller,
    WindowsShutdownSignal,
)


class FakeFunction:
    def __init__(self, implementation):
        self.implementation = implementation
        self.argtypes = None
        self.restype = None

    def __call__(self, *args):
        return self.implementation(*args)


class FakeKernel32:
    def __init__(self, *, create_handle: int = 73) -> None:
        self.create_handle = create_handle
        self.signaled = False
        self.create_calls: list[tuple[object, ...]] = []
        self.wait_calls: list[tuple[object, ...]] = []
        self.close_calls: list[tuple[object, ...]] = []
        self.CreateEventW = FakeFunction(self._create_event)
        self.WaitForSingleObject = FakeFunction(self._wait_for_single_object)
        self.CloseHandle = FakeFunction(self._close_handle)

    def _create_event(self, *args):
        self.create_calls.append(args)
        return self.create_handle

    def _wait_for_single_object(self, *args):
        self.wait_calls.append(args)
        if self.signaled:
            self.signaled = False
            return 0
        return 258

    def _close_handle(self, *args):
        self.close_calls.append(args)
        return 1


class WindowsShutdownSignalTests(unittest.TestCase):
    def test_creates_exact_auto_reset_initially_nonsignaled_event(self) -> None:
        kernel32 = FakeKernel32()

        signal = WindowsShutdownSignal(kernel32=kernel32)

        self.addCleanup(signal.close)
        self.assertEqual(
            kernel32.create_calls,
            [(None, False, False, "Local\\CatTypeShutdown")],
        )
        self.assertEqual(
            kernel32.CreateEventW.argtypes,
            [
                ctypes.c_void_p,
                wintypes.BOOL,
                wintypes.BOOL,
                wintypes.LPCWSTR,
            ],
        )
        self.assertIs(kernel32.CreateEventW.restype, wintypes.HANDLE)
        self.assertEqual(
            kernel32.WaitForSingleObject.argtypes,
            [wintypes.HANDLE, wintypes.DWORD],
        )
        self.assertIs(kernel32.WaitForSingleObject.restype, wintypes.DWORD)
        self.assertEqual(
            kernel32.CloseHandle.argtypes,
            [wintypes.HANDLE],
        )
        self.assertIs(kernel32.CloseHandle.restype, wintypes.BOOL)
        self.assertTrue(signal.available)

    def test_nonblocking_poll_consumes_one_request(self) -> None:
        kernel32 = FakeKernel32()
        signal = WindowsShutdownSignal(kernel32=kernel32)
        self.addCleanup(signal.close)
        kernel32.signaled = True

        self.assertTrue(signal.requested())
        self.assertFalse(signal.requested())

        self.assertEqual(kernel32.wait_calls, [(73, 0), (73, 0)])

    def test_close_is_idempotent(self) -> None:
        kernel32 = FakeKernel32()
        signal = WindowsShutdownSignal(kernel32=kernel32)

        signal.close()
        signal.close()

        self.assertEqual(kernel32.close_calls, [(73,)])
        self.assertFalse(signal.available)

    def test_creation_failure_is_safe_and_never_polls_or_closes(self) -> None:
        kernel32 = FakeKernel32(create_handle=0)

        signal = WindowsShutdownSignal(kernel32=kernel32)

        self.assertFalse(signal.available)
        self.assertFalse(signal.requested())
        signal.close()
        self.assertEqual(kernel32.wait_calls, [])
        self.assertEqual(kernel32.close_calls, [])

    def test_without_an_injected_kernel_is_a_noop_outside_windows(self) -> None:
        with patch.object(platform_updater.sys, "platform", "linux"):
            signal = WindowsShutdownSignal()

        self.assertFalse(signal.available)
        self.assertFalse(signal.requested())
        signal.close()


class FakeShutdownSignal:
    def __init__(self, requested: bool = False, available: bool = True) -> None:
        self._requested = requested
        self.available = available
        self.request_calls = 0
        self.close_calls = 0

    def requested(self) -> bool:
        self.request_calls += 1
        requested = self._requested
        self._requested = False
        return requested

    def close(self) -> None:
        self.close_calls += 1


class CatTypeShutdownSignalTests(unittest.TestCase):
    def make_app(self, signal: FakeShutdownSignal) -> CatTypeApp:
        app = CatTypeApp.__new__(CatTypeApp)
        app._shutdown_signal = signal
        app._shutting_down = False
        app._update_lifecycle_lock = threading.RLock()
        app._active_update_operation_id = None
        app._update_worker_active = False
        app._update_worker = None
        app._hide = Mock()
        app._tray_icon = None
        app.keyboard = Mock()
        app.tracker = Mock()
        app.root = Mock()
        app.events = queue.SimpleQueue()
        app._drain_update_events = Mock()
        return app

    def test_tick_routes_shutdown_request_through_normal_shutdown_first(self) -> None:
        signal = FakeShutdownSignal(requested=True)
        app = self.make_app(signal)

        app._tick()

        self.assertTrue(app._shutting_down)
        app._hide.assert_called_once_with()
        app.keyboard.stop.assert_called_once_with()
        app.tracker.stop.assert_called_once_with()
        app.root.destroy.assert_called_once_with()
        app.root.winfo_exists.assert_not_called()
        app._drain_update_events.assert_not_called()
        self.assertEqual(signal.close_calls, 1)

    def test_tick_continues_normally_when_no_request_is_pending(self) -> None:
        signal = FakeShutdownSignal()
        app = self.make_app(signal)
        app.root.winfo_exists.return_value = False

        app._tick()

        self.assertEqual(signal.request_calls, 1)
        self.assertFalse(app._shutting_down)
        self.assertEqual(signal.close_calls, 0)

    def test_normal_shutdown_closes_signal_exactly_once(self) -> None:
        signal = FakeShutdownSignal()
        app = self.make_app(signal)

        app.shutdown()
        app.shutdown()

        self.assertEqual(signal.close_calls, 1)
        app.root.destroy.assert_called_once_with()


class WindowsControllerWiringTests(unittest.TestCase):
    def test_frozen_windows_defaults_to_normalized_windows_adapter(self) -> None:
        installer = cat_type._default_update_installer(
            "win32",
            frozen=True,
            shutdown_available=True,
        )

        self.assertIsInstance(installer, WindowsControllerInstaller)
        self.assertTrue(installer.availability().can_install)

    def test_source_windows_remains_manual(self) -> None:
        for platform_name, frozen in (("win32", False),):
            with self.subTest(platform=platform_name, frozen=frozen):
                installer = cat_type._default_update_installer(
                    platform_name,
                    frozen=frozen,
                    shutdown_available=True,
                )

                self.assertFalse(installer.availability().can_install)

    def test_failed_shutdown_event_makes_default_windows_updater_unavailable(
        self,
    ) -> None:
        installer = cat_type._default_update_installer(
            "win32",
            frozen=True,
            shutdown_available=False,
        )

        availability = installer.availability()
        self.assertFalse(availability.can_install)
        self.assertIn("unavailable", availability.status.lower())

    def test_public_constructor_no_longer_exposes_test_handoff_hook(self) -> None:
        self.assertNotIn(
            "before_update_handoff",
            inspect.signature(CatTypeApp).parameters,
        )


def _write_tar(
    path: Path,
    members: list[tuple[tarfile.TarInfo, bytes]],
) -> None:
    with tarfile.open(path, "w:gz") as archive:
        for member, body in members:
            archive.addfile(member, io.BytesIO(body) if member.isfile() else None)


def _regular_member(
    name: str = "Cat Type",
    body: bytes = b"new",
) -> tuple[tarfile.TarInfo, bytes]:
    member = tarfile.TarInfo(name)
    member.size = len(body)
    member.mode = 0o777
    return member, body


@unittest.skipUnless(
    sys.platform.startswith("linux"),
    "Linux portable staging requires Linux filesystem semantics",
)
class LinuxPortableStagingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.executable = self.directory / "Cat Type current"
        self.executable.write_bytes(b"old")
        self.executable.chmod(0o751)
        self.installer = LinuxPortableInstaller(
            executable=self.executable,
            frozen=True,
        )

    def make_archive(
        self,
        members: list[tuple[tarfile.TarInfo, bytes]],
        name: str = "Cat-Type-Linux-x64.tar.gz",
    ) -> Path:
        archive = self.directory / name
        _write_tar(archive, members)
        return archive

    def test_prepared_linux_update_is_immutable(self) -> None:
        prepared = PreparedLinuxUpdate(
            self.executable,
            self.directory / ".staged.new",
            self.directory / "Cat Type current.previous",
        )

        with self.assertRaises(FrozenInstanceError):
            prepared.current = Path("changed")  # type: ignore[misc]

    def test_prepare_streams_exact_member_beside_executable_and_preserves_mode(
        self,
    ) -> None:
        archive = self.make_archive([_regular_member(body=b"replacement")])

        prepared = self.installer.prepare(archive, "1.1.0")

        self.addCleanup(prepared.staged.unlink, missing_ok=True)
        self.assertEqual(prepared.current, self.executable.resolve())
        self.assertEqual(prepared.staged.parent, self.executable.parent.resolve())
        self.assertTrue(prepared.staged.name.startswith(".Cat Type current."))
        self.assertTrue(prepared.staged.name.endswith(".new"))
        self.assertEqual(prepared.staged.read_bytes(), b"replacement")
        self.assertEqual(stat.S_IMODE(prepared.staged.stat().st_mode), 0o751)
        self.assertEqual(
            prepared.backup,
            self.directory.resolve() / "Cat Type current.previous",
        )

    def test_prepare_rejects_every_archive_shape_except_one_exact_regular_member(
        self,
    ) -> None:
        link = tarfile.TarInfo("Cat Type")
        link.type = tarfile.SYMTYPE
        link.linkname = "elsewhere"
        hardlink = tarfile.TarInfo("Cat Type")
        hardlink.type = tarfile.LNKTYPE
        hardlink.linkname = "elsewhere"
        directory = tarfile.TarInfo("Cat Type")
        directory.type = tarfile.DIRTYPE
        device = tarfile.TarInfo("Cat Type")
        device.type = tarfile.CHRTYPE
        empty, _body = _regular_member(body=b"")
        cases = {
            "missing": [],
            "duplicate": [_regular_member(), _regular_member()],
            "extra": [_regular_member(), _regular_member("README")],
            "wrong": [_regular_member("cat-type")],
            "absolute": [_regular_member("/Cat Type")],
            "traversal": [_regular_member("../Cat Type")],
            "symlink": [(link, b"")],
            "hardlink": [(hardlink, b"")],
            "directory": [(directory, b"")],
            "device": [(device, b"")],
            "empty": [(empty, b"")],
        }
        for label, members in cases.items():
            with self.subTest(label=label):
                archive = self.make_archive(members, f"{label}.tar.gz")
                with self.assertRaises((ValueError, RuntimeError)):
                    self.installer.prepare(archive, "1.1.0")
                self.assertEqual(
                    list(self.directory.glob(".Cat Type current.*.new")),
                    [],
                )

    def test_prepare_rejects_declared_member_over_256_mib_without_staging(self) -> None:
        archive = self.make_archive([_regular_member()])
        original_open = tarfile.open

        class OversizedArchive:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def getmembers(self):
                member, _ = _regular_member()
                member.size = 256 * 1024 * 1024 + 1
                return [member]

        with patch.object(tarfile, "open", return_value=OversizedArchive()):
            with self.assertRaisesRegex(ValueError, "size"):
                self.installer.prepare(archive, "1.1.0")
        self.assertIsNotNone(original_open)
        self.assertEqual(list(self.directory.glob("*.new")), [])

    def test_prepare_rejects_truncated_and_overread_member_streams(self) -> None:
        archive = self.make_archive([_regular_member()])

        class OverreadingSource(io.BytesIO):
            def read(self, _size=-1):
                return super().read()

        class StreamArchive:
            def __init__(self, source: io.BytesIO) -> None:
                self.source = source

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def getmembers(self):
                member, _ = _regular_member(body=b"abc")
                return [member]

            def extractfile(self, _member):
                return self.source

        cases = (
            (io.BytesIO(b"ab"), "truncated"),
            (OverreadingSource(b"abcd"), "exceeds"),
        )
        for source, message in cases:
            with self.subTest(message=message):
                with patch.object(
                    tarfile,
                    "open",
                    return_value=StreamArchive(source),
                ):
                    with self.assertRaisesRegex(ValueError, message):
                        self.installer.prepare(archive, "1.1.0")
                self.assertEqual(
                    list(self.directory.glob(".Cat Type current.*.new")),
                    [],
                )

    def test_prepare_requires_frozen_regular_executable_with_execute_bits(self) -> None:
        archive = self.make_archive([_regular_member()])
        cases = (
            LinuxPortableInstaller(executable=self.executable, frozen=False),
            LinuxPortableInstaller(executable=self.directory / "missing", frozen=True),
        )
        self.executable.chmod(0o600)
        cases += (LinuxPortableInstaller(executable=self.executable, frozen=True),)
        for installer in cases:
            with self.subTest(installer=installer):
                self.assertFalse(installer.availability().can_install)
                with self.assertRaises(RuntimeError):
                    installer.prepare(archive, "1.1.0")

    def test_capability_probe_uses_real_sibling_replace_and_cleans_probe_files(
        self,
    ) -> None:
        availability = self.installer.availability()

        self.assertTrue(availability.can_install)
        self.assertEqual(list(self.directory.glob(".cat-type-update-probe.*")), [])

    def test_failed_capability_probe_reports_actionable_protected_status(self) -> None:
        with patch.object(tempfile, "mkstemp", side_effect=PermissionError("no")):
            availability = self.installer.availability()

        self.assertFalse(availability.can_install)
        self.assertIn("protected", availability.status.lower())
        self.assertIn("writable folder", availability.status.lower())

    def test_prepare_refuses_existing_backup_and_cleans_staging_after_copy_failure(
        self,
    ) -> None:
        archive = self.make_archive([_regular_member(body=b"replacement")])
        backup = self.executable.with_name(self.executable.name + ".previous")
        backup.write_bytes(b"occupied")
        with self.assertRaisesRegex(RuntimeError, "backup"):
            self.installer.prepare(archive, "1.1.0")
        backup.unlink()

        with patch.object(os, "fsync", side_effect=OSError("disk failure")):
            with self.assertRaisesRegex(OSError, "disk failure"):
                self.installer.prepare(archive, "1.1.0")
        self.assertEqual(list(self.directory.glob(".Cat Type current.*.new")), [])

    def test_cleanup_failure_does_not_mask_primary_staging_error(self) -> None:
        archive = self.make_archive([_regular_member(body=b"replacement")])
        original_unlink = Path.unlink

        def fail_only_staging(path: Path, *args, **kwargs):
            if path.name.endswith(".new"):
                raise PermissionError("cleanup failed")
            return original_unlink(path, *args, **kwargs)

        with (
            patch.object(os, "fsync", side_effect=OSError("primary failure")),
            patch.object(Path, "unlink", fail_only_staging),
        ):
            with self.assertRaisesRegex(OSError, "primary failure"):
                self.installer.prepare(archive, "1.1.0")


class LinuxControllerWiringTests(unittest.TestCase):
    def test_frozen_linux_defaults_to_normalized_linux_adapter(self) -> None:
        with patch.object(platform_updater.sys, "executable", __file__):
            installer = cat_type._default_update_installer(
                "linux",
                frozen=True,
                shutdown_available=False,
            )

        self.assertIsInstance(installer, LinuxControllerInstaller)

    def test_source_linux_and_macos_remain_manual(self) -> None:
        for platform_name, frozen in (("linux", False), ("darwin", True)):
            with self.subTest(platform=platform_name):
                installer = cat_type._default_update_installer(
                    platform_name,
                    frozen=frozen,
                    shutdown_available=False,
                )
                self.assertFalse(installer.availability().can_install)


if __name__ == "__main__":
    unittest.main()
