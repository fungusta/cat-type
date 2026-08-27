# Deterministic Settings Height Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Derive the Settings canvas viewport height from the evaluated top-level geometry, prove the fix on native Windows without a release tag, and publish the verified result as v1.0.24.

**Architecture:** `_center` will calculate a deterministic viewport height from the accepted top-level height, footer requested height, and named footer packing. It will supply that value to both scrollbar synchronization and fitted-height calculation while normal configure events continue using live canvas geometry.

**Tech Stack:** Python 3.12, Tkinter, `unittest`, PyInstaller, GitHub Actions, GitHub CLI

## Global Constraints

- Keep `_center` as the sole owner of initial top-level geometry.
- Keep footer appearance unchanged with external vertical padding exactly `(12, 14)` pixels.
- Do not call the full Tk event loop from production sizing code.
- Use one deterministic viewport height for both scrollbar visibility and `_content_fitted_height` in each sizing pass.
- Preserve deterministic viewport width, two layout-settling passes, four content-height passes, screen caps, minimum-size clamping, centering, and manual resizing.
- Preserve preferred size, responsive breakpoint, card layout, scrollbar policy, maximization, saved geometry, and page-switch behavior.
- Remove all `[DEBUG-winh]` instrumentation from the release candidate.
- Prove the focused test on native Windows from a feature branch before creating v1.0.24.
- Preserve public tags v1.0.19 through v1.0.23; never move, delete, or reuse them.

---

### Task 1: Derive and Apply Deterministic Viewport Height

**Files:**
- Modify: `settings_window.py:270-280,1388-1420,1558-1580,1670-1760`
- Modify: `tests/test_settings_window.py:60-155,275-320`

**Interfaces:**
- Consumes: accepted top-level `measured_height: int`, `footer.winfo_reqheight()`, and `FOOTER_VERTICAL_PADDING: tuple[int, int]`
- Produces: `_content_viewport_height(window_height: int, footer_height: int) -> int`
- Produces: `_settle_content_layout(window_width: int, viewport_height: int) -> None`
- Extends: `_sync_scrollbar_visibility(viewport_height: int | None = None) -> None`

- [ ] **Step 1: Add failing tests for the native Windows height seam**

Add this pure sizing test to `SettingsWindowSizingTests`:

```python
def test_content_viewport_height_excludes_footer_and_padding(self) -> None:
    viewport_height = getattr(
        SettingsWindow,
        "_content_viewport_height",
        lambda *_args: None,
    )

    self.assertEqual(viewport_height(300, 35), 239)
    self.assertEqual(viewport_height(514, 35), 453)
    self.assertEqual(viewport_height(363, 35), 302)
    self.assertEqual(viewport_height(20, 35), 1)
```

Update `test_center_reduces_minimum_when_screen_is_too_small` with:

```python
settings_window.footer = Mock()
settings_window.footer.winfo_reqheight.return_value = 35
settings_window._settle_content_layout.assert_called_once_with(600, 339)
```

Update `test_content_layout_settles_canvas_width_before_measurement` to call:

```python
settings_window._settle_content_layout(855, 453)
```

Make its scrollbar event record the supplied viewport:

```python
settings_window._sync_scrollbar_visibility = Mock(
    side_effect=lambda viewport_height: events.append(
        ("scrollbar", viewport_height)
    )
)
```

Expect `("scrollbar", 453)` in both ordered settle passes.

Add this regression to `SettingsWindowScrollingTests`:

```python
def test_scrollbar_uses_deterministic_viewport_during_opening(self) -> None:
    settings_window = SettingsWindow.__new__(SettingsWindow)
    canvas = Mock()
    canvas.bbox.return_value = (0, 0, 700, 453)
    canvas.winfo_height.return_value = 239
    scrollbar = Mock()
    scrollbar.winfo_manager.return_value = "pack"
    settings_window.scroll_canvas = canvas
    settings_window.scrollbar = scrollbar

    try:
        settings_window._sync_scrollbar_visibility(453)
    except TypeError as error:
        self.fail(
            "_sync_scrollbar_visibility must accept viewport height: "
            f"{error}"
        )

    scrollbar.pack_forget.assert_called_once_with()
    canvas.yview_moveto.assert_called_once_with(0)
```

- [ ] **Step 2: Run the pure viewport test and verify RED**

Run:

```bash
docker exec -w /workspace/.worktrees/deterministic-settings-width \
  cat-type-sizing-debug xvfb-run -a \
  /tmp/cat-type-release-venv/bin/python -m unittest \
  tests.test_settings_window.SettingsWindowSizingTests.test_content_viewport_height_excludes_footer_and_padding \
  -v
```

Expected: FAIL because the missing helper returns `None` instead of `239`.

- [ ] **Step 3: Implement the minimal deterministic viewport contract**

Add the named footer packing beside the sizing constants:

```python
FOOTER_VERTICAL_PADDING: tuple[int, int] = (12, 14)
```

Use it without changing appearance:

```python
footer.pack(
    side="bottom",
    fill="x",
    padx=28,
    pady=self.FOOTER_VERTICAL_PADDING,
)
```

Add the pure helper before `_content_fitted_height`:

```python
@classmethod
def _content_viewport_height(
    cls,
    window_height: int,
    footer_height: int,
) -> int:
    return max(
        1,
        window_height
        - footer_height
        - sum(cls.FOOTER_VERTICAL_PADDING),
    )
```

Extend scrollbar synchronization while preserving event-handler behavior:

```python
def _sync_scrollbar_visibility(
    self,
    viewport_height: int | None = None,
) -> None:
    bounds = self.scroll_canvas.bbox("all")
    available_height = (
        self.scroll_canvas.winfo_height()
        if viewport_height is None
        else viewport_height
    )
    overflows = bool(
        bounds
        and bounds[3] - bounds[1] > available_height
    )
```

Change the layout helper signature and sync call:

```python
def _settle_content_layout(
    self,
    window_width: int,
    viewport_height: int,
) -> None:
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
        self._sync_scrollbar_visibility(viewport_height)
        self.window.update_idletasks()
```

In every `_center` pass, read the accepted top-level height before settling,
derive the viewport, and use it consistently:

```python
self.window.geometry(f"{width}x{height}")
self.window.update_idletasks()
measured_height = self.window.winfo_height()
viewport_height = self._content_viewport_height(
    measured_height,
    self.footer.winfo_reqheight(),
)
self._settle_content_layout(width, viewport_height)
# measure content bounds
fitted_height = self._content_fitted_height(
    opening_height,
    measured_height,
    content_height,
    viewport_height,
    available_height,
)
```

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```bash
docker exec -w /workspace/.worktrees/deterministic-settings-width \
  cat-type-sizing-debug sh -lc '
python_bin=/tmp/cat-type-release-venv/bin/python
xvfb-run -a "$python_bin" -m unittest \
  tests.test_settings_window.SettingsWindowSizingTests.test_content_viewport_height_excludes_footer_and_padding \
  tests.test_settings_window.SettingsWindowSizingTests.test_center_reduces_minimum_when_screen_is_too_small \
  tests.test_settings_window.SettingsWindowSizingTests.test_content_layout_settles_canvas_width_before_measurement \
  tests.test_settings_window.SettingsWindowScrollingTests.test_scrollbar_uses_deterministic_viewport_during_opening \
  tests.test_settings_window.SettingsWindowScrollingTests.test_scrollbar_is_hidden_when_content_fits \
  tests.test_settings_window.SettingsWindowTkLayoutTests.test_opening_measures_after_reducing_minimum_for_small_screen \
  tests.test_settings_window.SettingsWindowTkLayoutTests.test_opening_remeasures_after_scrollbar_changes_layout_mode \
  -v
'
```

Expected: 7 tests pass.

- [ ] **Step 5: Verify diagnostics are absent and commit**

Run:

```bash
rg -n "DEBUG-winh" . --glob '!docs/**'
git diff --check
```

Expected: both commands produce no output.

Commit:

```bash
git add settings_window.py tests/test_settings_window.py
git commit -m "fix: derive settings viewport height"
```

### Task 2: Prove the Fix on Native Windows Without a Release Tag

**Files:**
- Verify: all tracked project files
- Publish temporary branch: `fix/deterministic-settings-height`

**Interfaces:**
- Consumes: reviewed Task 1 commit and existing `.github/workflows/build.yml`
- Produces: a successful native Windows `Run automated tests` step for the focused regression before v1.0.24 exists

- [ ] **Step 1: Run the exact Linux release suite on the feature branch**

Run:

```bash
docker exec -w /workspace/.worktrees/deterministic-settings-width \
  cat-type-sizing-debug sh -lc '
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

Expected: 256 tests pass with 4 expected skips.

- [ ] **Step 2: Complete task-scoped review**

Review the Task 1 commit for deterministic height math, consistent viewport
use, unchanged footer appearance, event-handler fallback, regression fidelity,
and absence of diagnostics. Resolve every Critical or Important finding and
rerun Step 1 after any fix.

- [ ] **Step 3: Push only the feature branch and dispatch the existing build workflow**

Run:

```bash
git push -u origin fix/deterministic-settings-height
gh workflow run build.yml --ref fix/deterministic-settings-height
```

Do not touch `main` or create a tag.

- [ ] **Step 4: Gate on the native Windows test step**

Poll the dispatched run until the Windows job's `Run automated tests` step
completes. Verify its logs include:

```text
test_opening_remeasures_after_scrollbar_changes_layout_mode ... ok
```

After that Windows test step succeeds, cancel the remaining diagnostic build
matrix to avoid unnecessary packaging work. Record the run and job URLs. If
the step fails, stop and diagnose; do not prepare v1.0.24.

### Task 3: Prepare, Publish, and Verify v1.0.24

**Files:**
- Modify: `app_version.py`
- Modify: `CatType.spec`
- Modify: `packaging/CatType.iss`
- Modify: `packaging/version_info.txt`
- Modify: `tests/test_release_version_check.py`
- Modify: `README.md`
- Publish: `refs/tags/v1.0.24`

**Interfaces:**
- Consumes: successful native Windows branch proof and reviewed feature head
- Produces: published GitHub Release v1.0.24 with five platform packages and `SHA256SUMS.txt`

- [ ] **Step 1: Update all live release markers to 1.0.24**

Apply these exact marker values:

```python
# app_version.py
APP_VERSION: str = "1.0.24"

# CatType.spec
version="1.0.24",

# tests/test_release_version_check.py
self.assertEqual(APP_VERSION, "1.0.24")
self.assertEqual(metadata_mismatches("1.0.24", PROJECT_ROOT), [])
self.assertNotEqual(metadata_mismatches("1.0.23", PROJECT_ROOT), [])
```

```text
; packaging/CatType.iss
#define MyAppVersion "1.0.24"

; packaging/version_info.txt
filevers=(1, 0, 24, 0)
prodvers=(1, 0, 24, 0)
FileVersion = 1.0.24
ProductVersion = 1.0.24

; README.md release tag example
v1.0.24
```

Use `1.0.24` in both temporary-copy drift checks in
`tests/test_release_version_check.py`. Keep `1.0.23` only as the intentional
negative drift assertion.

- [ ] **Step 2: Run the exact release suite and metadata checks**

Run:

```bash
docker exec -w /workspace/.worktrees/deterministic-settings-width \
  cat-type-sizing-debug sh -lc '
python_bin=/tmp/cat-type-release-venv/bin/python
"$python_bin" scripts/check_release_version.py v1.0.24
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

Then run:

```bash
git diff --check
```

Expected: 256 tests pass with 4 expected skips and both metadata/format checks
exit zero.

- [ ] **Step 3: Commit and complete whole-candidate review**

```bash
git add app_version.py CatType.spec packaging/CatType.iss \
  packaging/version_info.txt tests/test_release_version_check.py README.md
git commit -m "release: prepare Cat Type 1.0.24"
```

Review all commits after `d575bbc`. Resolve every Critical or Important
finding and rerun Step 2 after any change.

- [ ] **Step 4: Fast-forward local main and verify publication preconditions**

From the main checkout, fast-forward `main` to the reviewed feature head. Then
verify clean status, `HEAD...origin/main` is ahead-only, and v1.0.24 is absent
locally and remotely. Preserve v1.0.19 through v1.0.23 unchanged.

```bash
git -C /home/p1370357/Projects/Personal/cat-type merge --ff-only \
  fix/deterministic-settings-height
git -C /home/p1370357/Projects/Personal/cat-type fetch origin main --tags
git -C /home/p1370357/Projects/Personal/cat-type status --short
git -C /home/p1370357/Projects/Personal/cat-type \
  rev-list --left-right --count HEAD...origin/main
git -C /home/p1370357/Projects/Personal/cat-type tag --list v1.0.24
git -C /home/p1370357/Projects/Personal/cat-type \
  ls-remote --tags origin refs/tags/v1.0.24
```

- [ ] **Step 5: Atomically push main and v1.0.24**

```bash
release_sha=$(git rev-parse HEAD)
git tag v1.0.24 "$release_sha"
git push --atomic origin main refs/tags/v1.0.24
```

Verify remote main and the tag both equal `release_sha`.

- [ ] **Step 6: Gate the release workflow on Windows, then all platforms**

Find the v1.0.24 Release workflow. Verify native Windows succeeds first, then
wait for all five builds and `publish` to complete successfully. If any gate
fails, stop; do not create another tag automatically.

- [ ] **Step 7: Verify the published release assets**

Run:

```bash
gh release view v1.0.24 \
  --json tagName,name,isDraft,isPrerelease,publishedAt,assets,url
```

Expected: published, non-draft, non-prerelease, with exactly six non-empty
assets:

```text
Cat-Type-Windows-x64.exe
Cat-Type-macOS-x64.dmg
Cat-Type-macOS-arm64.dmg
Cat-Type-Linux-x64.tar.gz
Cat-Type-Linux-arm64.tar.gz
SHA256SUMS.txt
```

- [ ] **Step 8: Clean owned temporary resources**

After release verification, remove the Docker verifier, remove the worktree,
delete merged local feature branches, prune worktrees, and delete the two
temporary remote feature branches. Report that these release-only resources
were removed and that their implementation commits remain reachable from
`main`/v1.0.24.
