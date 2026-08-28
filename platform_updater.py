"""Platform-specific update handoff contracts for Cat Type."""

from __future__ import annotations

import ctypes
import os
import stat
import subprocess
import sys
import tarfile
import tempfile
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from auto_update import InstallerAvailability

if TYPE_CHECKING:
    from auto_update import AvailableUpdate


WINDOWS_INSTALLER_NAME = "Cat-Type-Windows-x64.exe"
WINDOWS_SHUTDOWN_EVENT = "Local\\CatTypeShutdown"
LINUX_ARCHIVE_NAMES = frozenset(
    {
        "Cat-Type-Linux-x64.tar.gz",
        "Cat-Type-Linux-arm64.tar.gz",
    }
)
LINUX_ARCHIVE_MEMBER = "Cat Type"
MAX_LINUX_EXECUTABLE_BYTES = 256 * 1024 * 1024

LINUX_HELPER_SOURCE = r'''pid=$1
identity=$2
current=$3
staged=$4
backup=$5
health=$6
lock="${backup}.lock"

if [ ! -d "$lock" ]; then
    exit 1
fi
cleanup_lock() {
    rmdir -- "$lock" 2>/dev/null || :
}
trap cleanup_lock EXIT HUP INT TERM

attempts=0
while kill -0 "$pid" 2>/dev/null; do
    live_identity=$(sed 's/^[^)]*) //' "/proc/$pid/stat" 2>/dev/null | awk '{print $20}')
    if [ -z "$live_identity" ] || [ "$live_identity" != "$identity" ]; then
        break
    fi
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 6000 ]; then
        exit 1
    fi
    sleep 0.05
done

launch_old() {
    "$current" </dev/null >/dev/null 2>&1 &
}
path_exists() {
    [ -e "$1" ] || [ -L "$1" ]
}
restore_old() {
    if path_exists "$current" && ! rm -f -- "$current"; then
        "$backup" </dev/null >/dev/null 2>&1 &
        return
    fi
    if mv -T -n -- "$backup" "$current" && ! path_exists "$backup"; then
        launch_old
    else
        "$backup" </dev/null >/dev/null 2>&1 &
    fi
}

if path_exists "$backup"; then
    launch_old
    exit 1
fi
if ! mv -T -n -- "$current" "$backup" || path_exists "$current"; then
    launch_old
    exit 1
fi
if ! mv -T -n -- "$staged" "$current"; then
    restore_old
    exit 1
fi
if path_exists "$staged" || ! path_exists "$current"; then
    restore_old
    exit 1
fi

"$current" </dev/null >/dev/null 2>&1 &
new_pid=$!
sleep "$health"
new_state=$(sed 's/^[^)]*) //' "/proc/$new_pid/stat" 2>/dev/null | awk '{print $1}')
if ! kill -0 "$new_pid" 2>/dev/null || \
        [ -z "$new_state" ] || [ "$new_state" = "Z" ]; then
    wait "$new_pid" 2>/dev/null || :
    restore_old
    exit 1
fi
rm -f -- "$backup" || exit 1
exit 0
'''

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
        environment = os.environ.copy()
        environment["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
        self._popen(
            [str(package), *self.FLAGS],
            shell=False,
            env=environment,
        )


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


@dataclass(frozen=True)
class PreparedLinuxUpdate:
    """Explicit paths handed to the detached Linux replacement helper."""

    current: Path
    staged: Path
    backup: Path


def _remove_if_present(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def _fsync_directory(directory: Path) -> None:
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        try:
            os.fsync(descriptor)
        except OSError:
            pass
    finally:
        os.close(descriptor)


class LinuxPortableInstaller:
    """Stage and launch atomic updates for a writable Linux portable build."""

    def __init__(
        self,
        *,
        executable: str | os.PathLike[str] | None = None,
        frozen: bool | None = None,
        popen: Callable[..., object] | None = None,
        helper_health_seconds: float = 5,
    ) -> None:
        self._executable = Path(sys.executable if executable is None else executable)
        self._frozen = (
            bool(getattr(sys, "frozen", False)) if frozen is None else frozen
        )
        self._popen = subprocess.Popen if popen is None else popen
        if (
            isinstance(helper_health_seconds, bool)
            or not isinstance(helper_health_seconds, (int, float))
            or helper_health_seconds <= 0
            or helper_health_seconds > 5
        ):
            raise ValueError("Linux helper health window must be in (0, 5]")
        self._helper_health_seconds = helper_health_seconds

    def _current_executable(self) -> Path:
        if not self._frozen:
            raise RuntimeError(
                "Source checkouts cannot update themselves; download a packaged "
                "Linux release instead."
            )
        try:
            current = self._executable.resolve(strict=True)
            metadata = current.stat()
        except OSError as error:
            raise RuntimeError("The Cat Type executable is unavailable.") from error
        if not stat.S_ISREG(metadata.st_mode):
            raise RuntimeError("The Cat Type executable is not a regular file.")
        mode = stat.S_IMODE(metadata.st_mode)
        if mode & 0o111 == 0:
            raise RuntimeError("The Cat Type executable is not executable.")
        return current

    @staticmethod
    def _probe_parent(parent: Path) -> None:
        first: Path | None = None
        second: Path | None = None
        try:
            first_descriptor, first_name = tempfile.mkstemp(
                prefix=".cat-type-update-probe.",
                dir=parent,
            )
            first = Path(first_name)
            os.close(first_descriptor)
            second_descriptor, second_name = tempfile.mkstemp(
                prefix=".cat-type-update-probe.",
                dir=parent,
            )
            second = Path(second_name)
            os.close(second_descriptor)
            os.replace(first, second)
            first = None
        except OSError as error:
            raise RuntimeError(
                "This Linux installation location is protected. Move Cat Type "
                "to a writable folder or install the update manually."
            ) from error
        finally:
            if first is not None:
                _remove_if_present(first)
            if second is not None:
                _remove_if_present(second)

    def _require_capability(self) -> Path:
        current = self._current_executable()
        self._probe_parent(current.parent)
        return current

    def availability(self) -> InstallerAvailability:
        try:
            self._require_capability()
        except RuntimeError as error:
            return InstallerAvailability(False, str(error))
        return InstallerAvailability(
            True,
            "Automatic Linux portable updates are ready.",
        )

    def prepare(self, archive: Path, version: str) -> PreparedLinuxUpdate:
        if not isinstance(version, str) or not version:
            raise ValueError("Linux update version must be nonempty")
        current = self._require_capability()
        parent = current.parent.resolve(strict=True)
        backup = current.with_name(current.name + ".previous")
        if backup.parent.resolve(strict=True) != parent:
            raise RuntimeError("unsafe Linux update backup path")
        if os.path.lexists(backup):
            raise RuntimeError(
                "A previous Linux update backup already exists; remove it only "
                "after confirming the installed copy is healthy."
            )

        staged: Path | None = None
        try:
            with tarfile.open(archive, mode="r:gz") as package:
                members = package.getmembers()
                if len(members) != 1:
                    raise ValueError(
                        "Linux update archive must contain exactly one member"
                    )
                member = members[0]
                if member.name != LINUX_ARCHIVE_MEMBER or not member.isfile():
                    raise ValueError(
                        f"Linux update archive must contain only the regular file "
                        f"{LINUX_ARCHIVE_MEMBER!r}"
                    )
                if not 0 < member.size <= MAX_LINUX_EXECUTABLE_BYTES:
                    raise ValueError("Linux update executable has an invalid size")
                source = package.extractfile(member)
                if source is None:
                    raise ValueError("Linux update executable could not be read")

                descriptor, staged_name = tempfile.mkstemp(
                    prefix=f".{current.name}.",
                    suffix=".new",
                    dir=parent,
                )
                staged = Path(staged_name).resolve(strict=True)
                if staged.parent != parent:
                    raise RuntimeError("unsafe Linux update staging path")
                with os.fdopen(descriptor, "wb") as destination:
                    remaining = member.size
                    while remaining:
                        chunk = source.read(min(1024 * 1024, remaining))
                        if not chunk:
                            raise ValueError("Linux update executable is truncated")
                        if len(chunk) > remaining:
                            raise ValueError(
                                "Linux update executable exceeds its declared size"
                            )
                        destination.write(chunk)
                        remaining -= len(chunk)
                    if source.read(1):
                        raise ValueError(
                            "Linux update executable exceeds its declared size"
                        )
                    destination.flush()
                    os.fsync(destination.fileno())
                    os.fchmod(
                        destination.fileno(),
                        stat.S_IMODE(current.stat().st_mode),
                    )
                    os.fsync(destination.fileno())
            _fsync_directory(parent)
            return PreparedLinuxUpdate(current, staged, backup)
        except BaseException:
            if staged is not None:
                _remove_if_present(staged)
            raise

    def start(
        self,
        prepared: PreparedLinuxUpdate,
        pid: int | None = None,
    ) -> None:
        if not isinstance(prepared, PreparedLinuxUpdate):
            raise TypeError("prepared Linux update has the wrong type")
        if pid is None:
            pid = os.getpid()
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            raise ValueError("Linux updater PID must be a positive integer")
        current = self._current_executable()
        if prepared.current != current:
            raise RuntimeError("prepared Linux current executable changed")
        parent = current.parent.resolve(strict=True)
        try:
            staged = prepared.staged.resolve(strict=True)
        except OSError as error:
            raise RuntimeError("prepared Linux staging file is unavailable") from error
        if (
            staged != prepared.staged
            or staged.parent != parent
            or not staged.is_file()
            or stat.S_IMODE(staged.stat().st_mode) & 0o111 == 0
            or not staged.name.startswith(f".{current.name}.")
            or not staged.name.endswith(".new")
            or staged.stat().st_dev != current.stat().st_dev
        ):
            raise RuntimeError("unsafe prepared Linux staging path")
        backup = prepared.backup
        if (
            backup != current.with_name(current.name + ".previous")
            or backup.parent.resolve(strict=True) != parent
        ):
            raise RuntimeError("unsafe prepared Linux backup path")
        if os.path.lexists(backup):
            raise RuntimeError("Linux update backup already exists")
        lock = Path(f"{backup}.lock")
        try:
            lock.mkdir(mode=0o700)
        except FileExistsError as error:
            raise RuntimeError("A Linux update is already in progress") from error
        except OSError as error:
            raise RuntimeError("The Linux update lock could not be created") from error
        try:
            stat_payload = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
            identity = stat_payload.rsplit(") ", 1)[1].split()[19]
        except (OSError, IndexError) as error:
            try:
                lock.rmdir()
            except OSError:
                pass
            raise RuntimeError(
                "Linux updater process identity is unavailable"
            ) from error

        try:
            self._helper_process = self._popen(
                [
                    "/bin/sh",
                    "-c",
                    LINUX_HELPER_SOURCE,
                    "cat-type-linux-updater",
                    str(pid),
                    identity,
                    str(current),
                    str(staged),
                    str(backup),
                    format(self._helper_health_seconds, ".15g"),
                ],
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
        except BaseException:
            try:
                lock.rmdir()
            except OSError:
                pass
            raise


class LinuxControllerInstaller:
    """Normalize Linux portable installation to the controller protocol."""

    def __init__(self, installer: LinuxPortableInstaller | None = None) -> None:
        self._installer = installer or LinuxPortableInstaller()

    def availability(self) -> InstallerAvailability:
        return self._installer.availability()

    def prepare(
        self,
        package: Path,
        update: AvailableUpdate,
    ) -> PreparedLinuxUpdate:
        if (
            update.package.name not in LINUX_ARCHIVE_NAMES
            or package.name != update.package.name
        ):
            raise ValueError("verified Linux archive does not match the selected asset")
        return self._installer.prepare(package, update.version)

    def start(self, prepared: object) -> None:
        if not isinstance(prepared, PreparedLinuxUpdate):
            raise TypeError("prepared Linux update has the wrong type")
        self._installer.start(prepared)
