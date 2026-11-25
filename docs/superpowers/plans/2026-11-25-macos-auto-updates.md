# macOS Automatic Updates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Packaged Mac builds install updates themselves after one click, Sparkle-style, and all platforms re-check every 24 hours while running.

**Architecture:** A new `macos_updater.py` stages and verifies the new `Cat Type.app` beside the installed one, then hands off to a small C helper (copied out of the bundle) that waits for Cat Type to quit, swaps the bundles with `renamex_np(RENAME_SWAP)`, and relaunches through `/usr/bin/open`. The controller in `cat_type.py` gains an hourly re-check timer, a skipped-version rule, and on macOS a non-modal three-button prompt (`update_prompt.py`) that becomes the progress/error window.

**Tech Stack:** Python 3 stdlib, Tk, PyInstaller one-folder `.app`, C (clang from Xcode command-line tools), `hdiutil`, `ditto`, `codesign`, `spctl`, `xattr`, unittest.

**Spec:** `docs/superpowers/specs/2026-11-25-macos-auto-updates-design.md`

## Global Constraints

- Minimum macOS 12.0 (`LSMinimumSystemVersion`); compile the helper with `-mmacosx-version-min=12.0`.
- No new Python runtime dependencies. Shell out only to `/usr/bin/hdiutil`, `/usr/bin/ditto`, `/usr/bin/codesign`, `/usr/sbin/spctl`, `/usr/bin/xattr`, `/usr/bin/open`, `/usr/bin/gktool` (absolute paths, argv lists, never a shell string).
- Accepted bundle: bundle ID `com.fungusta.cat-type`, team `9B98U2J5Q2`, code requirement exactly `anchor apple generic and identifier "com.fungusta.cat-type" and certificate leaf[subject.OU] = "9B98U2J5Q2"`.
- Accepted packages: `Cat-Type-macOS-x64.dmg`, `Cat-Type-macOS-arm64.dmg`.
- The new bundle's `CFBundleShortVersionString` must equal the update's version and be newer than the running `APP_VERSION`.
- Helper waits at most 300 seconds for Cat Type to exit.
- Prompt copy: title "A new version of Cat Type is available"; body "Cat Type {new} is available — you have {current}."; buttons "Install Update" (default), "Remind Me Later", "Skip This Version"; failure buttons "Download Manually" and "Close"; "Cancel" only while downloading.
- An automatic-check prompt must never take keyboard focus or activate Cat Type until clicked.
- Windows and Linux keep their existing yes/no `messagebox` prompt.
- Every new test module is added to `TEST_MODULES` in `scripts/run_ci_tests.py`.
- Run tests with `python -m unittest <module> -v` from the repo root.

## Review Focus

1. **Renamed or relocated app** (`~/Applications/Cat Type 2.app`): the installed path comes from the running bundle, and the staged copy takes that bundle's name. Test in Task 3.
2. **Non-ASCII or spaced parent folder** (`/Users/zoë/Apps/`): paths travel as argv, never through a shell. Test in Task 2 and Task 3.
3. **Manual check while an automatic prompt is open:** no second prompt; the open one comes to the front. Test in Task 6.
4. **Failure after staging** (signature rejection, Wi-Fi drop): the staging folder is removed and the installed app untouched. Test in Task 3.
5. **User quits Cat Type from the tray while the prompt or download is open:** the prompt closes, no helper launches, and no staging folder is left behind. Test in Task 6.

---

### Task 1: Version comparison and skipped-version state

**Files:**
- Modify: `auto_update.py` (add `is_newer_version`, `UpdateCancelled`; extend `UpdateStateStore`; add `manual` to `UpdateEvent`)
- Modify: `cat_type.py:1480-1486` (`ControllerUpdateState` protocol)
- Test: `tests/test_auto_update.py`

**Interfaces:**
- Produces: `is_newer_version(candidate: str, current: str) -> bool` (raises `UpdateError` on malformed input, reusing `_parse_version`).
- Produces: `class UpdateCancelled(Exception)`. Not an `UpdateError` subclass.
- Produces: `UpdateStateStore.skipped_version() -> str | None` and `UpdateStateStore.skip_version(version: str) -> None`. Both keys live in the same `update-state.json`; `record_success` and `skip_version` each preserve the other's key.
- Produces: `UpdateEvent.manual: bool = False`.
- Produces: `ControllerUpdateState` protocol gains `skipped_version` and `skip_version`.

- [ ] **Step 1: Write failing tests** in `UpdateStateStoreTests`:
  - `test_skip_version_round_trips_and_survives_record_success`: `skip_version("1.1.0")`, then `record_success(NOW)`; assert `skipped_version() == "1.1.0"` and `is_due(NOW) is False`.
  - `test_record_success_then_skip_keeps_last_check`: reverse order; same assertions.
  - `test_skipped_version_is_none_for_missing_corrupt_or_non_string_state`.

  And a new `VersionComparisonTests`:
  - `test_is_newer_version`: `("1.0.61","1.0.60")` → True; `("1.0.60","1.0.60")` → False; `("1.0.9","1.0.10")` → False; `"1.0"` raises `UpdateError`.
- [ ] **Step 2: Run** `python -m unittest tests.test_auto_update -v`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement** the Interfaces above. `skip_version` writes atomically the same way `record_success` does; extract a shared `_write_state(payload: dict) -> None` and `_read_state() -> dict`.
- [ ] **Step 4: Run** `python -m unittest tests.test_auto_update tests.test_update_controller -v`. Expected: PASS, with existing tests unchanged.
- [ ] **Step 5: Commit** `feat: track skipped update versions`

---

### Task 2: C update helper and bundling

**Files:**
- Create: `packaging/macos_update_helper.c`
- Create: `scripts/build_macos_update_helper.py`
- Modify: `CatType.spec` (on macOS, build the helper and add it to `a.binaries`)
- Test: `tests/test_macos_update_helper.py` (skip unless `sys.platform == "darwin"` and `xcrun --find clang` succeeds)

**Interfaces:**
- Produces: `build_update_helper(output: Path) -> Path` in `scripts/build_macos_update_helper.py`. It runs `xcrun clang -O2 -Wall -Wextra -Werror -mmacosx-version-min=12.0 -o <output> packaging/macos_update_helper.c` and returns `output`.
- Produces: helper executable name `cat-type-update-helper`, available at runtime as `Path(sys._MEIPASS) / "cat-type-update-helper"`.
- Produces: helper argv (positional, exact order): `pid installed staged staging_dir lock_dir helper_dir open_tool gktool swap_mode wait_seconds`.
  - `gktool` is a path or `-` to skip.
  - `swap_mode` is `swap` or `move`; production always passes `swap`, and tests use `move` to exercise the fallback.
  - `wait_seconds` is an integer from 1 to 300.
- Produces: exit code 0 on success. Non-zero exit codes, each with one line on stderr:
  - 2: bad arguments
  - 3: wait timeout
  - 4: swap failed, old app restored and relaunched
  - 5: swap failed, restore also failed

Helper behaviour, in order:
1. At start, record the target PID's start time (`proc_pidinfo` `PROC_PIDTBSDINFO`). If the PID is already gone, treat it as exited.
2. Poll every 50 ms until the PID is gone or its start time differs. After `wait_seconds`, remove `staging_dir`, `lock_dir`, and `helper_dir`, then exit 3.
3. `swap` mode: `renamex_np(staged, installed, RENAME_SWAP)`. `move` mode, or if the swap fails:
   - rename `installed` → `<staging_dir>/old.app`, then `staged` → `installed`;
   - if the second rename fails, rename `old.app` back.
4. On success: `utimes(installed, NULL)`. If `gktool` is not `-` and the macOS version is 14.4 or later, run `gktool scan <installed>` and ignore its result.
5. Remove `staging_dir` recursively (`nftw`, no symlink following), then `lock_dir`, then `helper_dir`.
6. `posix_spawn` `open_tool <installed>` (on restore, the restored old app), then exit.

- [ ] **Step 1: Write failing tests.** Each builds the helper once into a temp dir (`setUpClass`). Fake bundles are folders with `Contents/Info.plist` and a marker file. `open_tool` is a recording shell script that appends its argv to a file. Tests:
  - `test_swap_replaces_bundle_removes_staging_lock_helper_dir_and_relaunches`: target PID is a `sleep 0.3` child. Assert the marker is new, the old bundle is gone, and the recorder got `[installed]`.
  - `test_move_mode_replaces_bundle_the_same_way`
  - `test_restores_old_bundle_when_new_cannot_move_in`: make `staged` a missing path. Assert exit 4, the old marker is in place, and the recorder got `[installed]`.
  - `test_times_out_without_touching_installed_bundle`: target is a live `sleep 30` with `wait_seconds=1`. Assert exit 3, installed unchanged, staging removed.
  - `test_reused_pid_with_new_start_time_counts_as_exited`: pass a PID that has already exited. Assert it completes promptly.
  - `test_handles_spaces_and_non_ascii_paths`: parent `"zoë apps"`, bundle `"Cat Type.app"`.
  - `test_rejects_wrong_argument_count_with_exit_2`
- [ ] **Step 2: Run** `python -m unittest tests.test_macos_update_helper -v`. Expected: FAIL, because the source file is missing.
- [ ] **Step 3: Implement** `packaging/macos_update_helper.c` and `scripts/build_macos_update_helper.py`. In `CatType.spec`, when `is_macos`, call `build_update_helper(Path("build/cat-type-update-helper"))` before `Analysis` and append `("build/cat-type-update-helper", ".")` to its `binaries`.
- [ ] **Step 4: Run** the helper tests (expect PASS), then `python -m PyInstaller --noconfirm --clean CatType.spec` and `test -x "dist/Cat Type.app/Contents/Frameworks/cat-type-update-helper"`. If PyInstaller places it elsewhere, record the actual path in the Task 3 constant.
- [ ] **Step 5:** Add `tests.test_macos_update_helper` to `TEST_MODULES`, then **commit** `feat: add macOS update swap helper`

---

### Task 3: Mac installer capability and prepare

**Files:**
- Create: `macos_updater.py`
- Test: `tests/test_macos_updater.py`

**Interfaces:**
- Consumes: `is_newer_version` (Task 1), helper name (Task 2), `InstallerAvailability`, `AvailableUpdate`.
- Produces constants: `MACOS_DMG_NAMES`, `BUNDLE_ID`, `TEAM_ID`, `CODE_REQUIREMENT`, `HELPER_NAME = "cat-type-update-helper"`, `STAGING_PREFIX = ".cat-type-update-"`, `LOCK_SUFFIX = ".update-lock"`.
- Produces: `@dataclass(frozen=True) class PreparedMacUpdate: installed: Path; staged: Path; staging_dir: Path`.
- Produces: `class MacBundleInstaller` with:
  - `__init__(*, executable=None, frozen=None, run=None, helper=None, current_version=APP_VERSION, popen=None, log_path=None)`. `run(argv: list[str]) -> subprocess.CompletedProcess` defaults to `subprocess.run(argv, capture_output=True, text=True, check=False, timeout=120)`.
  - `bundle_path() -> Path`: the `.app` that contains `executable`, which must be `<X>.app/Contents/MacOS/<name>`.
  - `availability() -> InstallerAvailability`
  - `prepare(dmg: Path, version: str) -> PreparedMacUpdate`

Capability rules, in order, each with its own status text (copy from the spec's Fallbacks table, ending with the release link from `_UnavailableUpdateInstaller.RELEASES_URL`):
1. not frozen
2. no enclosing `.app`
3. `/AppTranslocation/` in the path, or `os.statvfs(parent).f_flag & os.ST_RDONLY`
4. the parent probe fails (same mkstemp/replace probe as `LinuxPortableInstaller._probe_parent`), or `os.access(bundle, os.W_OK)` is false
5. the helper is missing or not executable

Ready status: "Automatic macOS updates are ready."

`prepare` steps:
1. Clear crash leftovers:
   - If the lock `<installed><LOCK_SUFFIX>` exists but `<lock>/helper.pid` is missing, unreadable, or names a dead process (`os.kill(pid, 0)` raises), remove the lock.
   - If no lock remains, delete any `<parent>/<STAGING_PREFIX>*` folders.
   - If a live helper holds the lock, raise "An update is already in progress".
2. Create the staging folder with `tempfile.mkdtemp(prefix=STAGING_PREFIX, dir=parent)`.
3. Mount: `hdiutil attach -readonly -nobrowse -noautoopen -mountpoint <private tmp> <dmg>`. In a `finally`, run `hdiutil detach <mountpoint> -force`.
4. Require `<mount>/Cat Type.app` to be a real directory, not a symlink; ignore other volume entries. Run `ditto <it> <staging>/<installed bundle name>`.
5. Validate:
   - `codesign --verify --deep --strict <staged>`
   - `codesign --verify -R=<CODE_REQUIREMENT> <staged>`
   - `spctl --assess --type execute <staged>`
   - `CFBundleIdentifier == BUNDLE_ID`
   - `CFBundleShortVersionString == version`
   - `is_newer_version(version, current_version)`
6. Run `xattr -dr com.apple.quarantine <staged>` (failure is ignored), then `os.lchown` every entry to the installed bundle's uid/gid (failure is ignored, as Sparkle does).
7. On any exception, remove the staging folder and re-raise as `RuntimeError` with a user-readable message.

- [ ] **Step 1: Write failing tests.**
  - Use a fake `run` that answers `hdiutil attach` by copying a fixture bundle into the mountpoint, and records every argv.
  - Use temp-dir fake installs at `<tmp>/zoë apps/Cat Type 2.app/Contents/MacOS/Cat Type`.
  - Tests:
    - `test_bundle_path_is_enclosing_app_even_when_renamed`
    - `test_availability_reports_each_fallback_in_order`: one subtest per rule. Patch `os.statvfs` for read-only.
    - `test_prepare_stages_beside_installed_bundle_with_installed_name`: the staged path is `<parent>/.cat-type-update-*/Cat Type 2.app`.
    - `test_prepare_runs_exact_validation_commands`: assert the argv list contains the codesign/spctl calls above with `CODE_REQUIREMENT` verbatim.
    - `test_prepare_rejects_and_cleans_staging_for_each_validation_failure`: subtests for codesign fail, requirement fail, spctl fail, wrong bundle ID, version mismatch, same version, older version, `Cat Type.app` missing, and `Cat Type.app` as a symlink. Assert no staging folder remains and the installed marker is unchanged.
    - `test_prepare_always_detaches_after_failure`
    - `test_prepare_removes_stale_staging_when_no_lock`
    - `test_prepare_clears_lock_whose_helper_is_dead_then_removes_staging`
    - `test_prepare_refuses_while_live_helper_holds_lock`
    - `test_prepare_strips_quarantine_and_ignores_xattr_failure`
- [ ] **Step 2: Run** `python -m unittest tests.test_macos_updater -v`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `MacBundleInstaller.bundle_path`, `availability`, `prepare`, and `PreparedMacUpdate`.
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5:** Add `tests.test_macos_updater` to `TEST_MODULES`, then **commit** `feat: stage and verify macOS updates`

---

### Task 4: Mac handoff and controller wiring

**Files:**
- Modify: `macos_updater.py`
- Modify: `cat_type.py:1588-1597` (`_default_update_installer`)
- Test: `tests/test_macos_updater.py`, `tests/test_platform_updater.py:506` (packaged macOS is no longer manual)

**Interfaces:**
- Consumes: `PreparedMacUpdate` and `MacBundleInstaller` (Task 3); helper argv (Task 2).
- Produces: `MacBundleInstaller.start(prepared: PreparedMacUpdate, pid: int | None = None) -> None`.
  1. Re-check that `prepared.installed == bundle_path()`.
  2. `mkdir` the lock `<installed><LOCK_SUFFIX>` with mode 0o700. If it exists, raise "An update is already in progress".
  3. Copy the helper into `tempfile.mkdtemp(prefix="cat-type-update-helper-")` and chmod it 0o755.
  4. `popen` the helper with argv `[copy, pid, installed, staged, staging_dir, lock, helper_dir, "/usr/bin/open", "/usr/bin/gktool", "swap", "300"]`. Use `start_new_session=True`, stdin `DEVNULL`, and stdout/stderr appended to `log_path`. `log_path` defaults to `~/Library/Logs/Cat Type/update-helper.log`, with its parent created.
  5. After `popen` succeeds, write the helper's PID to `<lock>/helper.pid`. If `popen` raises, remove the lock and the helper dir.
- Produces: `class MacControllerInstaller` with `availability()`, `prepare(package: Path, update: AvailableUpdate) -> PreparedMacUpdate` (rejects a package whose name isn't in `MACOS_DMG_NAMES` or doesn't equal `update.package.name`), and `start(prepared: object)` (TypeError on wrong type).
- Produces: `_default_update_installer("darwin", frozen=True, …)` returns `MacControllerInstaller()`.

- [ ] **Step 1: Write failing tests.**
  - `test_start_copies_helper_out_of_bundle_and_passes_exact_argv`: fake `popen` records argv/kwargs. Assert the helper path is outside the bundle and the argv matches the list above exactly.
  - `test_start_refuses_when_lock_exists`
  - `test_start_cleans_lock_and_helper_copy_when_spawn_fails`
  - `test_controller_prepare_rejects_mismatched_package`
  - `test_frozen_macos_defaults_to_mac_adapter`
  - Update `test_source_linux_and_packaged_macos_remain_manual` so only the source checkout stays manual.
- [ ] **Step 2: Run** `python -m unittest tests.test_macos_updater tests.test_platform_updater -v`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement** `start`, `MacControllerInstaller`, and the `_default_update_installer` branch.
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit** `feat: hand macOS updates to the swap helper`

---

### Task 5: Periodic checks, macOS startup check, and skipped versions

**Files:**
- Modify: `cat_type.py` (`run`, `check_for_updates`, `_handle_update_event`, new `_schedule_periodic_update_check`)
- Test: `tests/test_update_controller.py`

**Interfaces:**
- Consumes: `UpdateEvent.manual` and `ControllerUpdateState.skipped_version` (Task 1).
- Produces: `CatTypeApp.UPDATE_RECHECK_INTERVAL_MS = 3_600_000`.
- Produces: `CatTypeApp._schedule_periodic_update_check() -> None`. It calls `self.check_for_updates()` (automatic) and re-arms itself with `self.root.after(UPDATE_RECHECK_INTERVAL_MS, …)` unless shutting down.
- Produces: in `run()`, all three platforms schedule `check_for_updates` at 2000 ms, then `_schedule_periodic_update_check` at `UPDATE_RECHECK_INTERVAL_MS`.
- Produces: in `check_worker`, the `check-result` event carries `manual=manual`.
- Produces: in `_handle_update_event`, a `check-result` with `update.version == skipped_version()` and `not event.manual` finishes the operation silently with status "Cat Type {v} is available (skipped)." and no prompt.

- [ ] **Step 1: Write failing tests.**
  - `test_run_schedules_startup_and_periodic_check_on_each_platform`: subtests for darwin, win32, linux. Use a fake root recording `after` calls; assert delays `2000` and `3_600_000`.
  - `test_periodic_check_rearms_and_stops_after_shutdown`
  - `test_periodic_check_is_noop_while_operation_active`: `check_calls` stays unchanged.
  - `test_periodic_check_respects_not_due`
  - `test_automatic_check_skips_prompt_for_skipped_version`
  - `test_manual_check_prompts_even_for_skipped_version`
  - `test_newer_than_skipped_version_prompts`
- [ ] **Step 2: Run** `python -m unittest tests.test_update_controller -v`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement** the Interfaces above.
- [ ] **Step 4: Run** `python -m unittest tests.test_update_controller tests.test_behavior -v`. Expected: PASS.
- [ ] **Step 5: Commit** `feat: re-check for updates daily while running`

---

### Task 6: Sparkle-style prompt and progress window on macOS

**Files:**
- Create: `update_prompt.py`
- Modify: `cat_type.py` (constructor `update_prompt_factory` parameter, macOS branch in `_handle_update_event`, cancel flag in `_start_update_install`, prompt teardown in `shutdown`)
- Test: `tests/test_update_prompt.py`, `tests/test_update_controller.py`, `tests/test_macos_overlay_focus.py`

**Interfaces:**
- Consumes: `UpdateCancelled` and `skip_version` (Task 1), the "cancelled" event kind.
- Produces: `UpdateChoice = Literal["install", "skip", "later"]` in `update_prompt.py`.
- Produces: `class UpdatePromptView(Protocol)` with `show_progress(text: str, fraction: float | None) -> None`, `show_error(message: str) -> None`, `bring_to_front(take_focus: bool) -> None`, and `close() -> None`.
- Produces: `class MacUpdatePrompt(UpdatePromptView)` with `__init__(root, update: AvailableUpdate, current_version: str, *, take_focus: bool, on_choice: Callable[[UpdateChoice], None], on_cancel: Callable[[], None], on_download_manually: Callable[[], None])`. It is a `tk.Toplevel`, `-topmost`, styled like Settings.
  - When `take_focus` is False, it shows while the app's activation policy stays PROHIBITED (see `_return_to_macos_background_policy`) and binds Return only after a `<Button-1>`. That click switches the policy to ACCESSORY and calls `focus_force`.
  - Escape and the window close button mean "later".
- Produces: `CatTypeApp.__init__(…, update_prompt_factory: Callable[..., UpdatePromptView] | None = None)`. It defaults to `MacUpdatePrompt` when `platform_name == "darwin"`, and is ignored elsewhere.
- Produces macOS controller flow:
  - A `check-result` with an update opens the prompt with `take_focus=event.manual`. The operation stays active (so timers skip).
  - If a prompt is already open, a manual check calls `bring_to_front(True)` instead of opening another.
  - `install` → `_start_update_install`. Stage and progress events route to `show_progress` as well as Settings.
  - `skip` → `skip_version` + finish. `later` → finish.
  - `error` → `show_error`. `install-started` → close, then the existing shutdown.
  - `on_cancel` sets `self._update_cancel = threading.Event()`. The download `progress` callback raises `UpdateCancelled` when it is set and the stage is still downloading. `install_worker` maps `UpdateCancelled` to the "cancelled" event, which closes the prompt with status "Update cancelled."
  - `shutdown()` closes any open prompt and sets the cancel event before the existing teardown.

- [ ] **Step 1: Write failing tests.** Controller tests use a fake prompt factory recording calls:
  - `test_macos_update_opens_prompt_without_focus_for_automatic_check`
  - `test_macos_manual_check_opens_prompt_with_focus`
  - `test_manual_check_with_open_prompt_brings_it_to_front`
  - `test_choice_install_starts_install_and_routes_progress_to_prompt`
  - `test_choice_skip_records_version`
  - `test_choice_later_records_nothing`
  - `test_error_is_shown_in_prompt_and_current_app_keeps_running`
  - `test_cancel_during_download_emits_cancelled_and_closes_prompt`
  - `test_shutdown_with_open_prompt_closes_it_and_never_starts_helper`: the fake installer's `start` is not called.
  - `test_windows_and_linux_still_use_confirm_update`

  Widget tests (`tests/test_update_prompt.py`, need Tk):
  - `test_prompt_copy_and_button_order`: exact strings from Global Constraints.
  - `test_escape_and_close_mean_later`
  - `test_return_ignored_until_clicked_when_not_focused`
  - `test_failure_state_shows_download_manually_and_close`
  - `test_cancel_only_visible_while_downloading`

  macOS focus test: `test_automatic_update_prompt_does_not_activate_cat_type`, modelled on `test_showing_overlay_does_not_activate_cat_type`.
- [ ] **Step 2: Run** `python -m unittest tests.test_update_controller tests.test_update_prompt tests.test_macos_overlay_focus -v`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement** `update_prompt.py` and the controller changes per the Interfaces above.
- [ ] **Step 4: Run** the same command plus `python scripts/run_ci_tests.py`. Expected: PASS.
- [ ] **Step 5:** Add `tests.test_update_prompt` to `TEST_MODULES`, then **commit** `feat: add Sparkle-style macOS update prompt`

---

### Task 7: Release smoke test and documentation

**Files:**
- Create: `scripts/smoke_macos_update.py`
- Modify: `.github/workflows/build.yml` and `.github/workflows/release.yml` (macOS matrix jobs)
- Modify: `README.md:124-138`, `docs/macos-release.md`, `docs/superpowers/specs/2026-08-12-windows-linux-auto-updates-design.md` (mark the macOS-manual lines superseded)
- Test: `tests/test_package_smoke.py` (argument parsing only)

**Interfaces:**
- Consumes: `MacBundleInstaller` (Tasks 3–4), the helper (Task 2).
- Produces: `python -m scripts.smoke_macos_update --app "dist/Cat Type.app" [--dmg dist/Cat-Type-macOS-<arch>.dmg]`.
  - **With `--dmg`** (release workflow, notarized): copy the app to `<tmp>/Old Apps/Cat Type.app` and run `prepare` with `current_version="0.0.0"`. Then run the real helper (copied out, as `start` does) against a `sleep` PID with `open_tool` set to a recorder. Assert the swapped bundle validates with `codesign --verify --deep --strict`, staging is gone, and the recorder fired.
  - **Without `--dmg`** (PR build, unsigned): run the helper swap only, against copies of the built app.
- In `build.yml`, the macOS jobs run the script without `--dmg` after the PyInstaller build. In `release.yml`, they run it with `--dmg` after notarization and stapling.
- Docs: README update section says macOS installs updates itself (prompt, skip, remind) and re-checks daily. `docs/macos-release.md` adds the helper build step and the manual pre-release check from the spec.

- [ ] **Step 1: Write a failing test** `test_smoke_macos_update_parses_app_and_optional_dmg` in `tests/test_package_smoke.py`.
- [ ] **Step 2: Run** `python -m unittest tests.test_package_smoke -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the script and workflow steps, and edit the docs.
- [ ] **Step 4: Run** `python -m PyInstaller --noconfirm --clean CatType.spec && python -m scripts.smoke_macos_update --app "dist/Cat Type.app"`. Expected: exit 0 and "macOS update smoke passed".
- [ ] **Step 5: Commit** `ci: smoke-test macOS self-update; document it`

---

### Task 8: Manual end-to-end check on a real Mac (before first release)

Not automatable: CI cannot grant Input Monitoring or run a notarized release-to-release update.

- [ ] Install the current public release (1.0.60) in `/Applications`, grant Input Monitoring, and type to confirm the cat appears.
- [ ] On a fork of the repo, publish notarized test builds of this branch as `v1.0.61` and `v1.0.62`. Both test builds have `GITHUB_LATEST_RELEASE_URL` pointed at the fork; never ship that change.
- [ ] Install the 1.0.61 test build manually over 1.0.60 (the last manual update) and confirm Input Monitoring is still granted. In 1.0.61, press **Check for updates**, choose **Install Update**, and confirm that Cat Type quits and reopens as 1.0.62 within about 10 seconds. Input Monitoring must still be granted, and settings and achievements intact.
- [ ] Repeat with the app copied to `~/Applications/Cat Type 2.app`.
- [ ] Run from the mounted DMG and confirm the "Move Cat Type to Applications" fallback text.
- [ ] Record the results in `docs/research/2026-11-xx-macos-auto-update-verification.md`.
