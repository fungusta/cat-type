# Deterministic Settings Width Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make content-aware Settings sizing independent of delayed native Windows `Configure` events and publish the verified correction as v1.0.23.

**Architecture:** `_center` will pass its deterministic target top-level width into `_settle_content_layout`. The helper will derive the current canvas viewport from that target width and synchronous scrollbar manager state, settle the responsive layout twice, and only then allow height measurement.

**Tech Stack:** Python 3.12, Tkinter, `unittest`, PyInstaller, GitHub Actions, GitHub CLI

## Global Constraints

- Keep `SettingsWindow._center` as the sole owner of initial top-level geometry.
- Derive canvas width from the chosen window width and the packed scrollbar's requested width; do not depend on a pending native `Configure` event.
- Clamp the derived canvas width to at least one pixel.
- Preserve the existing two layout-settling passes and four content-height passes.
- Do not alter preferred size, responsive breakpoint, card layout, scrollbar policy, maximization, saved geometry, or page-switch behavior.
- Preserve public tags v1.0.19 through v1.0.22; publish the corrected release only as v1.0.23.

---

### Task 1: Derive Responsive Layout From the Target Window Width

**Files:**
- Modify: `tests/test_settings_window.py:80-150`
- Modify: `settings_window.py:1692-1740`

**Interfaces:**
- Consumes: `_center`'s local `width: int`, `scrollbar.winfo_manager()`, and `scrollbar.winfo_reqwidth()`
- Produces: `_settle_content_layout(window_width: int) -> None`

- [ ] **Step 1: Change the unit tests to require the deterministic target width**

Update `test_center_reduces_minimum_when_screen_is_too_small` to verify the
target width crosses the method boundary:

```python
settings_window._settle_content_layout.assert_called_once_with(600)
```

Replace the stale `scroll_canvas.winfo_width` setup in
`test_content_layout_settles_canvas_width_before_measurement` with synchronous
scrollbar state and call the wished-for interface:

```python
settings_window.scrollbar = Mock()
settings_window.scrollbar.winfo_manager.side_effect = ["pack", ""]
settings_window.scrollbar.winfo_reqwidth.return_value = 16

try:
    settings_window._settle_content_layout(855)
except TypeError as error:
    self.fail(
        "_settle_content_layout must accept the target window width: "
        f"{error}"
    )
```

Keep the ordered event assertion, with expected canvas/layout widths of 839 on
the visible-scrollbar pass and 855 after the scrollbar is hidden.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
docker exec -w /workspace cat-type-sizing-debug \
  xvfb-run -a /tmp/cat-type-release-venv/bin/python -m unittest \
  tests.test_settings_window.SettingsWindowSizingTests.test_content_layout_settles_canvas_width_before_measurement \
  -v
```

Expected: FAIL with `_settle_content_layout must accept the target window width`.

- [ ] **Step 3: Implement the deterministic layout width**

Replace the helper's native canvas-width read with:

```python
def _settle_content_layout(self, window_width: int) -> None:
    """Synchronize width-driven layout before measuring its height."""
    for _ in range(self.CONTENT_LAYOUT_SETTLE_PASSES):
        scrollbar_width = (
            self.scrollbar.winfo_reqwidth()
            if self.scrollbar.winfo_manager()
            else 0
        )
        canvas_width = max(1, window_width - scrollbar_width)
        self.scroll_canvas.itemconfigure(
            self._scroll_content_id,
            width=canvas_width,
        )
        self._apply_responsive_layout(canvas_width)
        self.window.update_idletasks()
        self._sync_scrollbar_visibility()
        self.window.update_idletasks()
```

Change `_center` to call:

```python
self._settle_content_layout(width)
```

- [ ] **Step 4: Run focused unit and real-Tk tests and verify GREEN**

Run:

```bash
docker exec -w /workspace cat-type-sizing-debug sh -lc '
python_bin=/tmp/cat-type-release-venv/bin/python
xvfb-run -a "$python_bin" -m unittest \
  tests.test_settings_window.SettingsWindowSizingTests.test_center_reduces_minimum_when_screen_is_too_small \
  tests.test_settings_window.SettingsWindowSizingTests.test_content_layout_settles_canvas_width_before_measurement \
  tests.test_settings_window.SettingsWindowTkLayoutTests.test_opening_measures_after_reducing_minimum_for_small_screen \
  tests.test_settings_window.SettingsWindowTkLayoutTests.test_opening_remeasures_after_scrollbar_changes_layout_mode \
  -v
'
```

Expected: 4 tests pass.

- [ ] **Step 5: Commit the fix**

```bash
git add settings_window.py tests/test_settings_window.py
git commit -m "fix: derive settings layout from target width"
```

### Task 2: Prepare v1.0.23 Metadata

**Files:**
- Modify: `app_version.py`
- Modify: `CatType.spec`
- Modify: `packaging/CatType.iss`
- Modify: `packaging/version_info.txt`
- Modify: `tests/test_release_version_check.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: release tag `v1.0.23`
- Produces: consistent runtime, Windows, macOS, test, and documentation version markers for `1.0.23`

- [ ] **Step 1: Update every live release marker to 1.0.23**

Set `APP_VERSION`, PyInstaller bundle version, Inno Setup version,
`filevers`, `prodvers`, `FileVersion`, `ProductVersion`, README tag example, and
release-version test expectations to `1.0.23`. Keep `1.0.22` only as the
intentional negative drift assertion.

- [ ] **Step 2: Verify metadata and formatting**

Run:

```bash
python scripts/check_release_version.py v1.0.23
git diff --check
```

Expected: both commands exit zero with no output.

- [ ] **Step 3: Commit release preparation**

```bash
git add app_version.py CatType.spec packaging/CatType.iss \
  packaging/version_info.txt tests/test_release_version_check.py README.md
git commit -m "release: prepare Cat Type 1.0.23"
```

### Task 3: Verify, Review, and Publish v1.0.23

**Files:**
- Verify: all tracked project files
- Publish: Git ref `refs/tags/v1.0.23`

**Interfaces:**
- Consumes: clean `main`, consistent v1.0.23 metadata, exact release test command, review approval
- Produces: GitHub Release v1.0.23 with five platform packages and `SHA256SUMS.txt`

- [ ] **Step 1: Run the exact Linux release test command**

Run:

```bash
docker exec -w /workspace cat-type-sizing-debug sh -lc '
python_bin=/tmp/cat-type-release-venv/bin/python
"$python_bin" scripts/check_release_version.py v1.0.23
xvfb-run --auto-servernum "$python_bin" -m unittest \
  tests.test_macos_overlay_focus tests.test_behavior tests.test_settings \
  tests.test_usage_metrics tests.test_settings_window \
  tests.test_platform_assets tests.test_bundled_icon_check \
  tests.test_package_smoke tests.test_release_version_check \
  tests.test_auto_update tests.test_update_controller \
  tests.test_platform_updater tests.test_windows_installer_contract \
  tests.test_linux_update_integration -v
'
```

Expected: 254 tests pass with 4 expected skips before accounting for any new test count.

- [ ] **Step 2: Request focused code review**

Review all commits after `299cef8`, focusing on deterministic viewport math,
scrollbar feedback, test fidelity, and v1.0.23 metadata. Resolve every Critical
or Important finding and rerun Step 1 after any change.

- [ ] **Step 3: Verify remote and tag preconditions**

Run:

```bash
git fetch origin main --tags
git status --short
git rev-list --left-right --count HEAD...origin/main
git tag --list v1.0.23
git ls-remote --tags origin refs/tags/v1.0.23
```

Expected: clean status, local `main` ahead only by the reviewed commits, and no
local or remote v1.0.23 tag.

- [ ] **Step 4: Atomically publish main and the tag**

```bash
release_sha=$(git rev-parse HEAD)
git tag v1.0.23 "$release_sha"
git push --atomic origin main refs/tags/v1.0.23
```

Expected: remote `main` and `refs/tags/v1.0.23` both point to `release_sha`.

- [ ] **Step 5: Gate on native Windows, then the full workflow**

Find the v1.0.23 Release workflow with `gh run list`. Verify the
`build (windows-latest, ...)` job completes successfully before waiting for all
five platform builds and the `publish` job. If Windows fails, stop and diagnose;
do not create another tag automatically.

- [ ] **Step 6: Verify the published release**

Run:

```bash
gh release view v1.0.23 \
  --json tagName,name,isDraft,isPrerelease,publishedAt,assets,url
```

Expected: a published, non-draft, non-prerelease v1.0.23 release containing
exactly these six non-empty assets:

```text
Cat-Type-Windows-x64.exe
Cat-Type-macOS-x64.dmg
Cat-Type-macOS-arm64.dmg
Cat-Type-Linux-x64.tar.gz
Cat-Type-Linux-arm64.tar.gz
SHA256SUMS.txt
```

- [ ] **Step 7: Clean temporary resources and report**

After release verification, remove the owned `cat-type-sizing-debug` container,
remove the merged settings worktree and feature branch, prune worktrees, and
confirm `git status --short` remains clean.
