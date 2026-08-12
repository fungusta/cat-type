# Windows and Linux Automatic Updates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add confirmation-based, checksum-verified automatic updates for packaged Windows and writable Linux portable installations.

**Architecture:** `auto_update.py` owns release discovery, scheduling, bounded downloads, and checksum verification. `platform_updater.py` owns the Windows shutdown/installer adapter and Linux atomic replacement helper. `CatTypeApp` coordinates background work through a separate update-event queue, while `SettingsWindow` remains a presentation-only boundary.

**Tech Stack:** Python 3.12 standard library, Tkinter, ctypes Win32 events, Inno Setup Pascal Script, GitHub Releases REST API, unittest, PyInstaller.

## Global Constraints

- Windows and Linux check the latest stable GitHub release at most once every 24 hours; macOS remains manual.
- No download or installation begins before explicit user confirmation.
- Only exact release asset names are accepted, and the asset must match its exact `SHA256SUMS.txt` entry.
- Network and filesystem work never runs on the Tk thread, and Tk objects are touched only on the Tk thread.
- Update state persists only the last successful check timestamp; no keyboard identity or keystroke count is persisted or transmitted.
- Source checkouts and protected Linux locations never self-modify.
- Windows first requests graceful shutdown and uses force-close only after the user has consented.
- Linux replaces only a frozen executable in a writable directory and rolls back when replacement or immediate relaunch fails.
- No new runtime dependency, macOS updater, package format, or silent-without-consent mode is added.

---

### Task 1: Runtime Version and Release Contract

**Files:**
- Create: `app_version.py`
- Create: `tests/test_release_version_check.py`
- Modify: `scripts/check_release_version.py`
- Modify: `CatType.spec`
- Modify: `packaging/CatType.iss`
- Modify: `packaging/version_info.txt`

**Interfaces:**
- Produces: `APP_VERSION: str = "1.0.5"`.
- Produces: `metadata_mismatches(expected: str, project_root: Path = PROJECT_ROOT) -> list[str]`.
- Preserves: `python scripts/check_release_version.py vMAJOR.MINOR.PATCH` as the release-workflow command.

- [ ] **Step 1: Write failing synchronization tests**

Add tests that copy the six version-bearing files to a temporary project,
assert `metadata_mismatches("1.0.5", root) == []`, then change
`APP_VERSION` to `1.0.4` and assert `app_version.py` is reported. Also assert
malformed versions are rejected by `main()` through a subprocess invocation.

```python
class ReleaseVersionCheckTests(unittest.TestCase):
    def test_current_version_matches_every_platform_marker(self) -> None:
        self.assertEqual(metadata_mismatches("1.0.5", PROJECT_ROOT), [])

    def test_runtime_version_drift_is_reported(self) -> None:
        root = self.copy_version_files()
        (root / "app_version.py").write_text('APP_VERSION = "1.0.4"\n')
        self.assertIn("app_version.py", metadata_mismatches("1.0.5", root))
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
python -m unittest tests.test_release_version_check -v
```

Expected: import failure because `app_version.py` and
`metadata_mismatches` do not exist.

- [ ] **Step 3: Add the single runtime version and complete metadata checks**

Create:

```python
"""Cat Type's runtime release version."""

APP_VERSION = "1.0.5"
```

Refactor the checker to validate exact markers in `app_version.py`,
`CatType.spec`, `packaging/CatType.iss`, and both numeric and string values in
`packaging/version_info.txt`. Keep CLI error text listing mismatched relative
paths. Do not change the current package version.

- [ ] **Step 4: Verify GREEN and existing release invocation**

Run:

```bash
python -m unittest tests.test_release_version_check -v
python scripts/check_release_version.py v1.0.5
```

Expected: all tests pass and the checker exits 0 without output.

- [ ] **Step 5: Commit**

```bash
git add app_version.py scripts/check_release_version.py \
  tests/test_release_version_check.py
git commit -m "build: synchronize the runtime release version"
```

---

### Task 2: Stable Release Discovery, Scheduling, and Verification

**Files:**
- Create: `auto_update.py`
- Create: `tests/test_auto_update.py`

**Interfaces:**
- Produces immutable `ReleaseAsset(name: str, url: str, size: int)`.
- Produces immutable `AvailableUpdate(version: str, tag_name: str, html_url: str, package: ReleaseAsset, checksums: ReleaseAsset)`.
- Produces `UpdateStateStore(path: Path | None = None)` with `is_due(now: datetime) -> bool` and `record_success(now: datetime) -> None`.
- Produces `UpdateService(current_version: str = APP_VERSION, opener=urlopen, cache_dir: Path | None = None)` with `check(platform: str, machine: str) -> AvailableUpdate | None` and `download_verified(update: AvailableUpdate, progress: Callable[[int, int], None] | None = None) -> Path`.

- [ ] **Step 1: Write failing pure-contract tests**

Cover strict three-part numeric parsing/comparison; exact Windows x64 and
Linux x64/arm64 asset selection; macOS, unsupported Windows architectures,
draft/prerelease/malformed releases; missing or duplicate package/checksum
assets; 24-hour due behavior; corrupt state; and atomic state writes.

```python
def test_selects_linux_arm64_release_assets(self) -> None:
    update = service_from_payload(release_payload()).check("linux", "aarch64")
    self.assertEqual(update.package.name, "Cat-Type-Linux-arm64.tar.gz")
    self.assertEqual(update.checksums.name, "SHA256SUMS.txt")

def test_check_is_due_only_after_twenty_four_hours(self) -> None:
    store.record_success(datetime(2026, 8, 12, tzinfo=timezone.utc))
    self.assertFalse(store.is_due(datetime(2026, 8, 12, 23, 59, tzinfo=timezone.utc)))
    self.assertTrue(store.is_due(datetime(2026, 8, 13, tzinfo=timezone.utc)))
```

- [ ] **Step 2: Verify pure-contract RED**

Run:

```bash
python -m unittest tests.test_auto_update.ReleaseDiscoveryTests \
  tests.test_auto_update.UpdateStateStoreTests -v
```

Expected: import failure because `auto_update` does not exist.

- [ ] **Step 3: Implement strict discovery and persistent scheduling**

Use `urllib.request.Request` with `Accept: application/vnd.github+json`, a
fixed GitHub API version, `User-Agent: Cat-Type/<APP_VERSION>`, and a 10-second
timeout. Limit JSON and checksum responses to 1 MiB. Store UTC timestamps as
ISO-8601 JSON in `update-state.json` beside the default settings path. Record
only successful checks, including an up-to-date result.

- [ ] **Step 4: Write failing bounded-download and checksum tests**

Use fake streamed HTTP responses to cover redirects handled by the opener,
declared and actual oversize content, interrupted downloads, progress values,
exact checksum filename matching, malformed/duplicate checksum entries,
digest mismatch, temporary cleanup, and successful atomic cache placement.

```python
def test_checksum_mismatch_removes_partial_package(self) -> None:
    with self.assertRaisesRegex(UpdateError, "checksum"):
        service.download_verified(update)
    self.assertEqual(list(cache.iterdir()), [])
```

- [ ] **Step 5: Verify download RED, then implement minimal download path**

Run the new download test class before and after implementation. Download
`SHA256SUMS.txt` first, find exactly one two-space-separated digest entry for
the selected basename, stream the package through `hashlib.sha256`, call the
progress callback, and atomically rename the verified `.part` file.

- [ ] **Step 6: Run Task 2 GREEN suite and commit**

```bash
python -m unittest tests.test_auto_update -v
git add auto_update.py tests/test_auto_update.py
git commit -m "feat: discover and verify stable updates"
```

Expected: all Task 2 tests pass with no network access.

---

### Task 3: Settings UI and Tk-Safe Update Orchestration

**Files:**
- Modify: `settings_window.py`
- Modify: `cat_type.py`
- Modify: `tests/test_settings_window.py`
- Create: `tests/test_update_controller.py`

**Interfaces:**
- `SettingsWindow(..., on_check_for_updates: Callable[[], None] | None = None, update_status: str = "")`.
- `SettingsWindow.set_update_status(text: str, checking: bool = False) -> None` updates only update widgets.
- `CatTypeApp` owns `update_events: queue.SimpleQueue[UpdateEvent]`, one worker, `check_for_updates(manual: bool = False)`, and confirmation/install handlers.

- [ ] **Step 1: Write failing Settings layout and callback tests**

Add a visible **Updates** card containing the current `APP_VERSION`, status
text, and **Check for updates** button. Verify the callback fires once, the
button disables while checking, status can update live, and the existing
footer remains outside scrollable content.

- [ ] **Step 2: Verify Settings RED**

Run:

```bash
python -m unittest tests.test_settings_window.SettingsWindowTkLayoutTests -v
```

Expected: failures for missing update widgets and method.

- [ ] **Step 3: Add presentation-only update controls**

Build the new card in the right column below Timing. Keep network and install
imports out of `settings_window.py`. Store the callback, use a `StringVar`,
and expose `set_update_status` to toggle the button state.

- [ ] **Step 4: Write failing orchestration tests**

With fake service/state/platform installer and no real threads, prove:

- startup schedules a due check but not a fresh one;
- manual checks always run and concurrent checks collapse;
- worker results reach the Tk thread through `update_events`;
- up-to-date and errors update Settings without prompting;
- an available update prompts before download;
- declining performs no download;
- accepting starts verified download and install stages;
- macOS/source/protected-Linux statuses do not self-install; and
- shutdown during a worker prevents installation.

- [ ] **Step 5: Verify orchestration RED, then implement it**

Use typed immutable update events defined in `auto_update.py`. Start daemon
workers, never call Tk from them, and drain the update queue inside `_tick`.
Use `tkinter.messagebox.askyesno` only on the Tk thread. Schedule the startup
check two seconds after `run()` begins.

- [ ] **Step 6: Run Task 3 GREEN suites and commit**

```bash
python -m unittest tests.test_settings_window tests.test_update_controller -v
git add settings_window.py cat_type.py tests/test_settings_window.py \
  tests/test_update_controller.py
git commit -m "feat: add update checks to settings"
```

---

### Task 4: Windows Graceful Shutdown and Installer Auto-Update

**Files:**
- Create: `platform_updater.py`
- Modify: `cat_type.py`
- Modify: `packaging/CatType.iss`
- Create: `tests/test_platform_updater.py`
- Create: `tests/test_windows_installer_contract.py`

**Interfaces:**
- Produces `WindowsShutdownSignal(kernel32=None)` with `requested() -> bool` and `close() -> None`.
- Produces `WindowsInstaller.start(package: Path) -> None`.
- Consumes a verified `Cat-Type-Windows-x64.exe` package from Task 2.

- [ ] **Step 1: Write failing shutdown-signal tests**

Use a fake kernel32 to assert creation of auto-reset event
`Local\\CatTypeShutdown`, nonblocking polling, one consumed request, safe close,
and a no-op implementation outside Windows. Add a `CatTypeApp._tick` test that
routes a request through normal `shutdown()`.

- [ ] **Step 2: Verify signal RED, then implement the Win32 wrapper**

Define explicit ctypes signatures for `CreateEventW`, `WaitForSingleObject`,
and `CloseHandle`. Treat event creation failure as updater unavailability, not
application startup failure. Close the handle during normal shutdown.

- [ ] **Step 3: Write failing installer-contract tests**

Parse `packaging/CatType.iss` as text and require:

- `CloseApplications=force` and `RestartApplications=no`;
- a `PrepareToInstall` function that opens and sets the exact shutdown event;
- graceful wait before Restart Manager file checks;
- an `/AUTOUPDATE=1`-gated silent relaunch entry; and
- preservation of the interactive post-install launch entry.

Test `WindowsInstaller.start` passes `/VERYSILENT`, `/SUPPRESSMSGBOXES`,
`/CLOSEAPPLICATIONS`, `/FORCECLOSEAPPLICATIONS`, `/NORESTART`, and
`/AUTOUPDATE=1`, then returns only after `Popen` succeeds so the app may shut
down.

- [ ] **Step 4: Verify installer RED, then implement minimal contracts**

Use Inno Pascal external declarations for `OpenEventW`, `SetEvent`, and
`CloseHandle`. `PrepareToInstall` signals the event when present and sleeps in
short intervals for at most five seconds; older versions fall through to
Restart Manager. Interactive force-close consent remains Inno's Preparing to
Install prompt; silent force-close is allowed only after in-app consent.

- [ ] **Step 5: Run Task 4 GREEN suites and commit**

```bash
python -m unittest tests.test_platform_updater \
  tests.test_windows_installer_contract tests.test_update_controller -v
git add platform_updater.py cat_type.py packaging/CatType.iss \
  tests/test_platform_updater.py tests/test_windows_installer_contract.py \
  tests/test_update_controller.py
git commit -m "feat: install Windows updates after graceful shutdown"
```

---

### Task 5: Linux Atomic Portable Replacement and Rollback

**Files:**
- Modify: `platform_updater.py`
- Modify: `cat_type.py`
- Modify: `tests/test_platform_updater.py`
- Create: `tests/test_linux_update_integration.py`

**Interfaces:**
- Produces immutable `PreparedLinuxUpdate(current: Path, staged: Path, backup: Path)`.
- Produces `LinuxPortableInstaller.prepare(archive: Path, version: str) -> PreparedLinuxUpdate`.
- Produces `LinuxPortableInstaller.start(prepared: PreparedLinuxUpdate, pid: int = os.getpid()) -> None`.

- [ ] **Step 1: Write failing safe-staging tests**

Create in-memory/temp tar archives and prove only the exact regular-file
member `Cat Type` is accepted. Reject missing, duplicate, symlink, directory,
absolute, traversal, and oversized members. Require frozen execution, a
writable same-filesystem parent, executable-mode preservation, and cleanup on
failure.

- [ ] **Step 2: Verify staging RED, then implement without `extractall`**

Read the selected member with `TarFile.extractfile`, copy it with a bounded
loop to a hidden `.new` file beside `sys.executable`, fsync it, chmod it to the
current executable mode, and return explicit current/staged/backup paths.

- [ ] **Step 3: Write failing helper integration tests**

Run the real constant `/bin/sh` helper against temporary executable scripts.
Cover successful wait/replacement/relaunch/backup cleanup, replacement rename
failure, a new executable that exits during the health window, rollback to the
old executable, path names containing spaces/metacharacters, and detached
standard streams.

- [ ] **Step 4: Verify helper RED, then implement constant shell program**

Pass PID and paths only as positional arguments to constant shell source.
Wait for the old PID, move current to `.previous`, move staged to current,
launch, wait five seconds, roll back and relaunch old on early exit, otherwise
remove the backup. Do not interpolate paths into shell source.

- [ ] **Step 5: Run Task 5 GREEN suites and commit**

```bash
python -m unittest tests.test_platform_updater \
  tests.test_linux_update_integration tests.test_update_controller -v
git add platform_updater.py cat_type.py tests/test_platform_updater.py \
  tests/test_linux_update_integration.py tests/test_update_controller.py
git commit -m "feat: atomically update Linux portable builds"
```

---

### Task 6: Packaging, Documentation, and End-to-End Verification

**Files:**
- Modify: `CatType.spec`
- Modify: `.github/workflows/build.yml`
- Modify: `.github/workflows/release.yml`
- Modify: `README.md`
- Modify: `tests/test_platform_assets.py`
- Modify: `tests/test_package_smoke.py`

**Interfaces:**
- Consumes all updater interfaces and platform assets from Tasks 1–5.
- Produces packaged Windows/Linux builds containing the updater modules.

- [ ] **Step 1: Add failing packaging and workflow tests**

Require both updater modules in PyInstaller analysis/hidden imports when
necessary, require update test modules in build/release workflows, and extend
package smoke diagnostics to reject updater import/startup failures. Preserve
all current native icon/backend assertions.

- [ ] **Step 2: Verify RED, then update packaging/workflows**

Run the focused packaging tests, make only the necessary spec/workflow
changes, and rerun until green.

- [ ] **Step 3: Document supported behavior and limitations**

README must explain confirmation, daily/manual checks, checksum verification,
Windows relaunch, writable Linux portable scope and rollback, protected Linux
fallback, manual macOS updates, GitHub network contact, and the absence of
code signing.

- [ ] **Step 4: Run the complete portable suite**

```bash
python -m unittest \
  tests.test_behavior tests.test_settings tests.test_settings_window \
  tests.test_platform_assets tests.test_bundled_icon_check \
  tests.test_package_smoke tests.test_release_version_check \
  tests.test_auto_update tests.test_update_controller \
  tests.test_platform_updater tests.test_windows_installer_contract \
  tests.test_linux_update_integration -v
```

Expected: all tests pass with no unexpected skips on Linux/X11.

- [ ] **Step 5: Build and verify Linux package**

Build with `CatType.spec`, validate bundled runtime assets, run the existing
startup smoke, and run the Linux update integration against the frozen binary
in a temporary writable directory. Confirm protected-directory detection with
a test-owned unwritable fixture rather than a system path.

- [ ] **Step 6: Build and verify Windows package and installer**

On native Windows, run all portable/applicable tests and overlay tests, build
the PyInstaller executable and Inno installer, validate version/icon/runtime
modules, launch the packaged app, signal `Local\\CatTypeShutdown`, and prove
both PyInstaller processes exit. Install over a running older test copy,
confirm the new executable launches, and preserve the user's real installed
copy outside the test target.

- [ ] **Step 7: Commit final integration**

```bash
git add CatType.spec .github/workflows/build.yml \
  .github/workflows/release.yml README.md tests
git commit -m "docs: explain automatic updates"
git diff --check
```

Expected: clean tracked worktree and no updater artifacts outside ignored
build/cache directories.
