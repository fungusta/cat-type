"""Stage, verify, and hand off in-place updates of the macOS Cat Type bundle.

Modelled on Sparkle 2: the verified new bundle is staged beside the installed
one, then a helper copied out of the bundle swaps the two after Cat Type quits
and relaunches the app.
"""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from app_version import APP_VERSION
from auto_update import (
    RELEASES_URL,
    InstallerAvailability,
    UpdateError,
    is_newer_version,
)

if TYPE_CHECKING:
    from auto_update import AvailableUpdate


MACOS_DMG_NAMES = frozenset(
    {
        "Cat-Type-macOS-x64.dmg",
        "Cat-Type-macOS-arm64.dmg",
    }
)
BUNDLE_ID = "com.fungusta.cat-type"
TEAM_ID = "9B98U2J5Q2"
CODE_REQUIREMENT = (
    f'anchor apple generic and identifier "{BUNDLE_ID}" and '
    f'certificate leaf[subject.OU] = "{TEAM_ID}"'
)
HELPER_NAME = "cat-type-update-helper"
HELPER_DIR_PREFIX = "cat-type-update-helper-"
STAGING_PREFIX = ".cat-type-update-"
LOCK_SUFFIX = ".update-lock"
HELPER_PID_FILE = "helper.pid"
HELPER_WAIT_SECONDS = 300
DMG_APP_NAME = "Cat Type.app"

HDIUTIL = "/usr/bin/hdiutil"
DITTO = "/usr/bin/ditto"
CODESIGN = "/usr/bin/codesign"
SPCTL = "/usr/sbin/spctl"
XATTR = "/usr/bin/xattr"
OPEN = "/usr/bin/open"
GKTOOL = "/usr/bin/gktool"

READY_STATUS = "Automatic macOS updates are ready."
SOURCE_STATUS = (
    "Source checkouts cannot update themselves. "
    f"Download a packaged release: {RELEASES_URL}"
)
NO_BUNDLE_STATUS = (
    "Automatic macOS installation is unavailable for this build. "
    f"Download the latest release: {RELEASES_URL}"
)
MOVE_TO_APPLICATIONS_STATUS = (
    "Move Cat Type to Applications to enable automatic updates. "
    f"Download the latest release: {RELEASES_URL}"
)
PROTECTED_STATUS = (
    "Cat Type can't update itself in this location. "
    f"Download the latest release: {RELEASES_URL}"
)
NO_HELPER_STATUS = (
    "Automatic macOS installation is unavailable in this build. "
    f"Download the latest release: {RELEASES_URL}"
)

CommandRunner = Callable[[list[str]], "subprocess.CompletedProcess[str]"]


def _default_run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _default_helper() -> Path:
    bundled = getattr(sys, "_MEIPASS", None)
    base = Path(bundled) if bundled else Path(sys.executable).parent
    return base / HELPER_NAME


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.exists():
        shutil.rmtree(path, ignore_errors=True)


@dataclass(frozen=True)
class PreparedMacUpdate:
    installed: Path
    staged: Path
    staging_dir: Path


class MacBundleInstaller:
    """Stage and hand off atomic updates of a writable macOS app bundle."""

    def __init__(
        self,
        *,
        executable: str | os.PathLike[str] | None = None,
        frozen: bool | None = None,
        run: CommandRunner | None = None,
        helper: str | os.PathLike[str] | None = None,
        current_version: str = APP_VERSION,
        popen: Callable[..., object] | None = None,
        log_path: str | os.PathLike[str] | None = None,
    ) -> None:
        self._executable = Path(sys.executable if executable is None else executable)
        self._frozen = (
            bool(getattr(sys, "frozen", False)) if frozen is None else frozen
        )
        self._run = _default_run if run is None else run
        self._helper = _default_helper() if helper is None else Path(helper)
        self._current_version = current_version
        self._popen = subprocess.Popen if popen is None else popen
        self._log_path = (
            Path.home() / "Library" / "Logs" / "Cat Type" / "update-helper.log"
            if log_path is None
            else Path(log_path)
        )

    def bundle_path(self) -> Path:
        """Return the ``.app`` bundle that contains the running executable."""
        try:
            executable = self._executable.resolve(strict=True)
        except OSError as error:
            raise RuntimeError(NO_BUNDLE_STATUS) from error
        macos_dir = executable.parent
        contents = macos_dir.parent
        bundle = contents.parent
        if (
            macos_dir.name != "MacOS"
            or contents.name != "Contents"
            or bundle.suffix != ".app"
            or not bundle.is_dir()
        ):
            raise RuntimeError(NO_BUNDLE_STATUS)
        return bundle

    def _require_capability(self) -> Path:
        if not self._frozen:
            raise RuntimeError(SOURCE_STATUS)
        bundle = self.bundle_path()
        parent = bundle.parent
        if "/AppTranslocation/" in f"{bundle}/":
            raise RuntimeError(MOVE_TO_APPLICATIONS_STATUS)
        try:
            read_only = bool(os.statvfs(parent).f_flag & os.ST_RDONLY)
        except OSError as error:
            raise RuntimeError(PROTECTED_STATUS) from error
        if read_only:
            raise RuntimeError(MOVE_TO_APPLICATIONS_STATUS)
        if not self._parent_is_writable(parent) or not os.access(bundle, os.W_OK):
            raise RuntimeError(PROTECTED_STATUS)
        if not self._helper.is_file() or not os.access(self._helper, os.X_OK):
            raise RuntimeError(NO_HELPER_STATUS)
        return bundle

    @staticmethod
    def _parent_is_writable(parent: Path) -> bool:
        first: Path | None = None
        second: Path | None = None
        try:
            descriptor, name = tempfile.mkstemp(
                prefix=".cat-type-update-probe.", dir=parent
            )
            first = Path(name)
            os.close(descriptor)
            descriptor, name = tempfile.mkstemp(
                prefix=".cat-type-update-probe.", dir=parent
            )
            second = Path(name)
            os.close(descriptor)
            os.replace(first, second)
            first = None
            return True
        except OSError:
            return False
        finally:
            for probe in (first, second):
                if probe is not None:
                    try:
                        probe.unlink(missing_ok=True)
                    except OSError:
                        pass

    def availability(self) -> InstallerAvailability:
        try:
            self._require_capability()
        except RuntimeError as error:
            return InstallerAvailability(False, str(error))
        return InstallerAvailability(True, READY_STATUS)

    @staticmethod
    def _lock_path(installed: Path) -> Path:
        return Path(f"{installed}{LOCK_SUFFIX}")

    def _clear_leftovers(self, installed: Path) -> None:
        lock = self._lock_path(installed)
        if os.path.lexists(lock):
            pid: int | None = None
            try:
                raw = (lock / HELPER_PID_FILE).read_text(encoding="ascii").strip()
                pid = int(raw)
            except (OSError, ValueError):
                pid = None
            if pid is not None and pid > 0 and _process_alive(pid):
                raise RuntimeError("An update is already in progress.")
            _remove_path(lock)
        for leftover in installed.parent.glob(f"{STAGING_PREFIX}*"):
            if leftover.is_dir() and not leftover.is_symlink():
                shutil.rmtree(leftover, ignore_errors=True)

    def _check(self, argv: list[str], message: str) -> None:
        try:
            result = self._run(argv)
        except (OSError, subprocess.SubprocessError) as error:
            raise RuntimeError(message) from error
        if result.returncode != 0:
            raise RuntimeError(message)

    def prepare(self, dmg: Path, version: str) -> PreparedMacUpdate:
        if not isinstance(version, str) or not version:
            raise ValueError("macOS update version must be nonempty")
        installed = self._require_capability()
        self._clear_leftovers(installed)
        staging_dir = Path(
            tempfile.mkdtemp(prefix=STAGING_PREFIX, dir=installed.parent)
        )
        try:
            staged = staging_dir / installed.name
            self._copy_from_disk_image(Path(dmg), staged)
            self._validate(staged, version)
            self._release_from_quarantine(staged)
            self._match_ownership(installed, staged)
            return PreparedMacUpdate(installed, staged, staging_dir)
        except BaseException as error:
            shutil.rmtree(staging_dir, ignore_errors=True)
            if isinstance(error, Exception) and not isinstance(error, RuntimeError):
                raise RuntimeError("The update could not be prepared.") from error
            raise

    def _copy_from_disk_image(self, dmg: Path, staged: Path) -> None:
        mount = Path(tempfile.mkdtemp(prefix="cat-type-update-mount-"))
        try:
            self._check(
                [
                    HDIUTIL,
                    "attach",
                    "-readonly",
                    "-nobrowse",
                    "-noautoopen",
                    "-mountpoint",
                    str(mount),
                    str(dmg),
                ],
                "The update disk image could not be opened.",
            )
            try:
                source = mount / DMG_APP_NAME
                if source.is_symlink() or not source.is_dir():
                    raise RuntimeError(
                        "The update disk image does not contain Cat Type."
                    )
                self._check(
                    [DITTO, str(source), str(staged)],
                    "The update could not be copied from its disk image.",
                )
            finally:
                try:
                    self._run([HDIUTIL, "detach", str(mount), "-force"])
                except (OSError, subprocess.SubprocessError):
                    pass
        finally:
            try:
                mount.rmdir()
            except OSError:
                pass

    def _validate(self, staged: Path, version: str) -> None:
        self._check(
            [CODESIGN, "--verify", "--deep", "--strict", str(staged)],
            "The update's code signature is not valid.",
        )
        self._check(
            [CODESIGN, "--verify", "--strict", "-R", f"={CODE_REQUIREMENT}", str(staged)],
            "The update was not signed by Cat Type's developer.",
        )
        self._check(
            [SPCTL, "--assess", "--type", "execute", str(staged)],
            "macOS Gatekeeper rejected the update.",
        )
        try:
            with (staged / "Contents" / "Info.plist").open("rb") as info_file:
                info = plistlib.load(info_file)
        except (OSError, plistlib.InvalidFileException, ValueError) as error:
            raise RuntimeError("The update's app information is unreadable.") from error
        if not isinstance(info, dict) or info.get("CFBundleIdentifier") != BUNDLE_ID:
            raise RuntimeError("The update is not Cat Type.")
        bundle_version = info.get("CFBundleShortVersionString")
        if bundle_version != version:
            raise RuntimeError("The update's version does not match the release.")
        try:
            newer = is_newer_version(version, self._current_version)
        except UpdateError as error:
            raise RuntimeError("The update's version is invalid.") from error
        if not newer:
            raise RuntimeError("The update is not newer than this version.")

    def _release_from_quarantine(self, staged: Path) -> None:
        try:
            self._run([XATTR, "-dr", "com.apple.quarantine", str(staged)])
        except (OSError, subprocess.SubprocessError):
            pass

    @staticmethod
    def _match_ownership(installed: Path, staged: Path) -> None:
        try:
            owner = installed.stat()
        except OSError:
            return
        for root, directories, files in os.walk(staged):
            for name in (root, *(Path(root) / entry for entry in (*directories, *files))):
                try:
                    os.lchown(name, owner.st_uid, owner.st_gid)
                except OSError:
                    pass

    def discard(self, prepared: PreparedMacUpdate) -> None:
        """Delete an abandoned staged update; never touches anything else."""
        if not isinstance(prepared, PreparedMacUpdate):
            return
        staging_dir = prepared.staging_dir
        if (
            staging_dir.name.startswith(STAGING_PREFIX)
            and staging_dir.parent == prepared.installed.parent
            and staging_dir != prepared.installed
            and staging_dir.is_dir()
            and not staging_dir.is_symlink()
        ):
            shutil.rmtree(staging_dir, ignore_errors=True)

    def start(self, prepared: PreparedMacUpdate, pid: int | None = None) -> None:
        """Copy the helper out of the bundle and launch it to finish the swap.

        Any failure deletes the staged update, so nothing is left beside the
        installed app.
        """
        if not isinstance(prepared, PreparedMacUpdate):
            raise TypeError("prepared macOS update has the wrong type")
        try:
            self._start(prepared, pid)
        except BaseException:
            self.discard(prepared)
            raise

    def _start(self, prepared: PreparedMacUpdate, pid: int | None) -> None:
        if pid is None:
            pid = os.getpid()
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            raise ValueError("macOS updater PID must be a positive integer")
        installed = self._require_capability()
        if (
            prepared.installed != installed
            or prepared.staging_dir.parent != installed.parent
            or not prepared.staging_dir.name.startswith(STAGING_PREFIX)
            or prepared.staged != prepared.staging_dir / installed.name
            or not prepared.staged.is_dir()
        ):
            raise RuntimeError("The prepared update no longer matches this app.")
        lock = self._lock_path(installed)
        try:
            lock.mkdir(mode=0o700)
        except FileExistsError as error:
            raise RuntimeError("An update is already in progress.") from error
        except OSError as error:
            raise RuntimeError("The update lock could not be created.") from error

        helper_dir: Path | None = None
        try:
            helper_dir = Path(tempfile.mkdtemp(prefix=HELPER_DIR_PREFIX))
            helper_copy = helper_dir / HELPER_NAME
            shutil.copy2(self._helper, helper_copy)
            helper_copy.chmod(0o755)
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with self._log_path.open("ab") as log:
                process = self._popen(
                    [
                        str(helper_copy),
                        str(pid),
                        str(installed),
                        str(prepared.staged),
                        str(prepared.staging_dir),
                        str(lock),
                        str(helper_dir),
                        OPEN,
                        GKTOOL,
                        "swap",
                        str(HELPER_WAIT_SECONDS),
                    ],
                    start_new_session=True,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=log,
                    close_fds=True,
                )
        except BaseException:
            _remove_path(lock)
            if helper_dir is not None:
                shutil.rmtree(helper_dir, ignore_errors=True)
            raise
        try:
            (lock / HELPER_PID_FILE).write_text(
                f"{getattr(process, 'pid', '')}\n", encoding="ascii"
            )
        except OSError:
            pass


class MacControllerInstaller:
    """Normalize macOS bundle installation to the controller protocol."""

    def __init__(self, installer: MacBundleInstaller | None = None) -> None:
        self._installer = installer or MacBundleInstaller()

    def availability(self) -> InstallerAvailability:
        return self._installer.availability()

    def prepare(self, package: Path, update: AvailableUpdate) -> PreparedMacUpdate:
        if (
            update.package.name not in MACOS_DMG_NAMES
            or Path(package).name != update.package.name
        ):
            raise ValueError("verified macOS disk image does not match the selected asset")
        return self._installer.prepare(Path(package), update.version)

    def start(self, prepared: object) -> None:
        if not isinstance(prepared, PreparedMacUpdate):
            raise TypeError("prepared macOS update has the wrong type")
        self._installer.start(prepared)

    def discard(self, prepared: object) -> None:
        if isinstance(prepared, PreparedMacUpdate):
            self._installer.discard(prepared)
