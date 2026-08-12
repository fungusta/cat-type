"""Platform-specific update handoff contracts for Cat Type."""

from __future__ import annotations

import ctypes
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from auto_update import InstallerAvailability

if TYPE_CHECKING:
    from auto_update import AvailableUpdate


WINDOWS_INSTALLER_NAME = "Cat-Type-Windows-x64.exe"
WINDOWS_SHUTDOWN_EVENT = "Local\\CatTypeShutdown"

WAIT_OBJECT_0 = 0


def _validated_windows_installer(package: Path) -> Path:
    if package.name != WINDOWS_INSTALLER_NAME:
        raise ValueError(
            f"expected verified installer {WINDOWS_INSTALLER_NAME!r}"
        )
    return package


class WindowsShutdownSignal:
    """Own and nonblockingly consume the installer shutdown event."""

    def __init__(self, kernel32: object | None = None) -> None:
        self._kernel32: object | None = None
        self._handle: object | None = None
        if kernel32 is None:
            if sys.platform != "win32":
                return
            try:
                kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            except Exception:
                return
        try:
            create_event = kernel32.CreateEventW  # type: ignore[attr-defined]
            wait_for_single_object = (  # type: ignore[attr-defined]
                kernel32.WaitForSingleObject
            )
            close_handle = kernel32.CloseHandle  # type: ignore[attr-defined]
            create_event.argtypes = [
                ctypes.c_void_p,
                wintypes.BOOL,
                wintypes.BOOL,
                wintypes.LPCWSTR,
            ]
            create_event.restype = wintypes.HANDLE
            wait_for_single_object.argtypes = [
                wintypes.HANDLE,
                wintypes.DWORD,
            ]
            wait_for_single_object.restype = wintypes.DWORD
            close_handle.argtypes = [wintypes.HANDLE]
            close_handle.restype = wintypes.BOOL
            handle = create_event(
                None,
                False,
                False,
                WINDOWS_SHUTDOWN_EVENT,
            )
        except Exception:
            return
        if handle:
            self._kernel32 = kernel32
            self._handle = handle

    @property
    def available(self) -> bool:
        return self._handle is not None

    def requested(self) -> bool:
        kernel32 = self._kernel32
        handle = self._handle
        if kernel32 is None or handle is None:
            return False
        try:
            result = kernel32.WaitForSingleObject(  # type: ignore[attr-defined]
                handle,
                0,
            )
        except Exception:
            return False
        return result == WAIT_OBJECT_0

    def close(self) -> None:
        kernel32 = self._kernel32
        handle = self._handle
        self._kernel32 = None
        self._handle = None
        if kernel32 is None or handle is None:
            return
        try:
            kernel32.CloseHandle(handle)  # type: ignore[attr-defined]
        except Exception:
            pass


class WindowsInstaller:
    """Launch a verified Inno installer for a consented auto-update."""

    FLAGS = (
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/CLOSEAPPLICATIONS",
        "/FORCECLOSEAPPLICATIONS",
        "/NORESTART",
        "/AUTOUPDATE=1",
    )

    def __init__(
        self,
        popen: Callable[..., object] | None = None,
    ) -> None:
        self._popen = subprocess.Popen if popen is None else popen

    def start(self, package: Path) -> None:
        package = _validated_windows_installer(package)
        self._popen([str(package), *self.FLAGS], shell=False)


class WindowsControllerInstaller:
    """Normalize the Windows installer to CatTypeApp's controller protocol."""

    def __init__(self, installer: WindowsInstaller | None = None) -> None:
        self._installer = installer or WindowsInstaller()

    def availability(self) -> InstallerAvailability:
        return InstallerAvailability(
            True,
            "Automatic Windows updates are ready.",
        )

    def prepare(self, package: Path, update: AvailableUpdate) -> Path:
        if update.package.name != WINDOWS_INSTALLER_NAME:
            raise ValueError(
                f"expected release asset {WINDOWS_INSTALLER_NAME!r}"
            )
        return _validated_windows_installer(package)

    def start(self, prepared: object) -> None:
        if not isinstance(prepared, Path):
            raise TypeError("prepared Windows update must be a Path")
        self._installer.start(prepared)
