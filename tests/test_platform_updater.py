from __future__ import annotations

import ctypes
import inspect
import queue
import threading
import unittest
from ctypes import wintypes
from pathlib import Path
from unittest.mock import Mock, patch

import cat_type
import platform_updater
from cat_type import CatTypeApp
from platform_updater import (
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

    def test_source_windows_and_frozen_linux_remain_manual(self) -> None:
        for platform_name, frozen in (("win32", False), ("linux", True)):
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


if __name__ == "__main__":
    unittest.main()
