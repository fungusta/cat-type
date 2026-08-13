# Pointer Fallback for Missing Carets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Cat Type place the companion beside the mouse pointer whenever an allowed caret lookup produces no usable rectangle, then publish the behavior as v1.0.7.

**Architecture:** `CaretLocator` remains the sole screen-position provider. It will centralize `pynput` pointer lookup, preserve Windows UIA/Win32 precedence and password suppression, and return pointer geometry through the same `CaretSnapshot.rect` path used by caret geometry; the renderer's obsolete active-monitor-corner path will be removed.

**Tech Stack:** Python 3.12, `unittest`, `unittest.mock`, `pynput`, tkinter, GitHub Actions, GitHub CLI.

## Global Constraints

- Password fields detected by Windows UI Automation must remain hidden and must never use the pointer fallback.
- Pointer geometry is a 2-by-20-pixel `ScreenRect` beginning at rounded pointer coordinates.
- A new overlay appearance anchors once; pointer movement must not move it until the next appearance.
- Pointer lookup errors must leave the overlay hidden and print diagnostics only when debug logging is enabled.
- The release version is `1.0.7` and the Git tag is `v1.0.7`.
- Publication requires Windows x64, macOS x64 and arm64, and Linux x64 and arm64 release assets plus `SHA256SUMS.txt`.

---

### Task 1: Caret locator pointer fallback

**Files:**
- Modify: `tests/test_behavior.py`
- Modify: `cat_type.py`

**Interfaces:**
- Consumes: `CaretLocator._locate_with_uia()`, `CaretLocator._locate_with_win32()`, and `pynput.mouse.Controller.position`.
- Produces: `CaretLocator._locate_pointer() -> ScreenRect | None` and `CaretLocator.locate() -> CaretSnapshot` with `source="pointer-fallback"` when caret providers fail.

- [ ] **Step 1: Replace the old corner-fallback test with failing locator tests**

Replace `CaretFallbackTests` with tests that patch `cat_type.IS_WINDOWS` and the three locator providers. Assert all of these exact behaviors:

```python
class CaretFallbackTests(unittest.TestCase):
    def test_windows_uses_pointer_when_caret_providers_fail(self) -> None:
        locator = CaretLocator()
        pointer = ScreenRect(640, 480, 642, 500)

        with (
            patch("cat_type.IS_WINDOWS", True),
            patch.object(
                locator,
                "_locate_with_uia",
                return_value=(None, False),
            ),
            patch.object(locator, "_locate_with_win32", return_value=None),
            patch.object(locator, "_locate_pointer", return_value=pointer),
        ):
            snapshot = locator.locate()

        self.assertEqual(snapshot.rect, pointer)
        self.assertEqual(snapshot.source, "pointer-fallback")

    def test_windows_prefers_detected_caret_over_pointer(self) -> None:
        locator = CaretLocator()
        caret = ScreenRect(100, 200, 102, 220)

        with (
            patch("cat_type.IS_WINDOWS", True),
            patch.object(
                locator,
                "_locate_with_uia",
                return_value=(caret, False),
            ),
            patch.object(locator, "_locate_pointer") as locate_pointer,
        ):
            snapshot = locator.locate()

        self.assertEqual(snapshot.rect, caret)
        self.assertEqual(snapshot.source, "uia")
        locate_pointer.assert_not_called()

    def test_password_field_never_uses_pointer(self) -> None:
        locator = CaretLocator()

        with (
            patch("cat_type.IS_WINDOWS", True),
            patch.object(
                locator,
                "_locate_with_uia",
                return_value=(None, True),
            ),
            patch.object(locator, "_locate_pointer") as locate_pointer,
        ):
            snapshot = locator.locate()

        self.assertTrue(snapshot.is_password)
        self.assertIsNone(snapshot.rect)
        locate_pointer.assert_not_called()

    def test_non_windows_uses_shared_pointer_provider(self) -> None:
        locator = CaretLocator()
        pointer = ScreenRect(320, 240, 322, 260)

        with (
            patch("cat_type.IS_WINDOWS", False),
            patch.object(locator, "_locate_pointer", return_value=pointer),
        ):
            snapshot = locator.locate()

        self.assertEqual(snapshot.rect, pointer)
        self.assertEqual(snapshot.source, "pointer-fallback")

    def test_pointer_coordinates_are_rounded_to_a_caret_sized_rect(self) -> None:
        locator = CaretLocator()
        controller = Mock()
        controller.position = (123.6, 456.2)

        with patch("pynput.mouse.Controller", return_value=controller):
            rect = locator._locate_pointer()

        self.assertEqual(rect, ScreenRect(124, 456, 126, 476))

    def test_pointer_failure_returns_no_position(self) -> None:
        locator = CaretLocator()

        with patch(
            "pynput.mouse.Controller",
            side_effect=RuntimeError("pointer unavailable"),
        ):
            rect = locator._locate_pointer()

        self.assertIsNone(rect)
```

Remove the import and test coverage for `choose_fallback_position`, because the renderer will no longer place missing carets at a monitor corner.

- [ ] **Step 2: Run the targeted tests and verify RED**

Run:

```bash
xvfb-run --auto-servernum python -m unittest \
  tests.test_behavior.CaretFallbackTests \
  tests.test_behavior.OverlayPositionTests -v
```

Expected: failures because `_locate_pointer` does not exist and Windows still returns `uia-fallback` without pointer geometry.

- [ ] **Step 3: Implement the minimal shared pointer provider**

In `cat_type.py`:

1. Remove `fallback_allowed` from `CaretSnapshot`.
2. Remove `choose_fallback_position()`.
3. Change `_locate_with_uia()` to return only `(ScreenRect | None, bool)`; retain its caret and password behavior but remove the now-unused text-pattern availability boolean.
4. Add this method to `CaretLocator`:

```python
def _locate_pointer(self) -> ScreenRect | None:
    try:
        from pynput.mouse import Controller

        left, top = Controller().position
        left = round(left)
        top = round(top)
        return ScreenRect(left, top, left + 2, top + 20)
    except Exception as exc:
        if self.debug:
            print(f"Pointer lookup failed: {exc}", file=sys.stderr)
        return None
```

5. Make non-Windows `locate()` call `_locate_pointer()` and return a `pointer-fallback` snapshot when it succeeds.
6. After Windows UIA and Win32 both fail, call `_locate_pointer()` and return the same `pointer-fallback` snapshot when it succeeds.
7. Preserve the immediate `uia-password` return before Win32 and pointer lookup.
8. In the tick/show path, require `snapshot.rect is not None`; remove `fallback_allowed` checks and the active-monitor-corner rendering branch.

- [ ] **Step 4: Run the targeted tests and verify GREEN**

Run the Step 2 command again.

Expected: all listed tests pass with zero failures.

- [ ] **Step 5: Commit the behavior**

```bash
git add cat_type.py tests/test_behavior.py
git commit -m "feat: fall back to pointer when caret is unavailable"
```

---

### Task 2: User documentation and full local verification

**Files:**
- Modify: `README.md`
- Modify: `tests/test_overlay_rendering.py`

**Interfaces:**
- Consumes: `CaretSnapshot.rect` as the only allowed render-position signal.
- Produces: Documentation of caret-first/pointer-fallback behavior and rendering tests without `fallback_allowed`.

- [ ] **Step 1: Update rendering coverage and documentation**

Delete `OverlayRenderingTests.test_missing_caret_uses_preferred_monitor_corner`; `choose_overlay_position` coverage already verifies placement, monitor work areas, edge flipping, and clamping for all `ScreenRect` sources.

In `README.md`, replace the install-section statement that only initial macOS/Linux builds use the pointer with:

```text
Cat Type uses native accessibility APIs to place the cat beside the text caret
when that geometry is available. If no usable caret can be detected, it falls
back to the current mouse pointer.
```

Replace the final Windows caret-tracking paragraph with:

```text
Some canvas-based editors, terminals, games, elevated applications, or other
controls do not publish a usable caret. In those cases, Cat Type falls back to
the current mouse pointer. Password fields detected through UI Automation stay
hidden and never use the pointer fallback.
```

- [ ] **Step 2: Run the complete Linux test suite**

Run:

```bash
xvfb-run --auto-servernum python -m unittest discover -s tests -v
```

Expected: every test passes with zero failures.

- [ ] **Step 3: Run static and release checks**

Run:

```bash
python -m compileall -q .
git diff --check
python scripts/check_release_version.py v1.0.6
```

Expected: every command exits zero before the version bump.

- [ ] **Step 4: Commit documentation**

```bash
git add README.md tests/test_overlay_rendering.py
git commit -m "docs: explain pointer fallback behavior"
```

---

### Task 3: Prepare and publish v1.0.7

**Files:**
- Modify: `app_version.py`
- Modify: `CatType.spec`
- Modify: `packaging/CatType.iss`
- Modify: `packaging/version_info.txt`
- Modify: `README.md`
- Modify: `tests/test_release_version_check.py`
- Create: `docs/superpowers/specs/2026-08-13-v1.0.7-release-design.md`

**Interfaces:**
- Consumes: repository version checker, `.github/workflows/build.yml`, and `.github/workflows/release.yml`.
- Produces: version `1.0.7`, annotated tag `v1.0.7`, and a GitHub Release containing all required assets.

- [ ] **Step 1: Write the failing release-version test**

Change `tests/test_release_version_check.py` so the repository checker accepts `v1.0.7` and rejects `v1.0.6`.

- [ ] **Step 2: Verify the version test is RED**

Run:

```bash
python -m unittest tests.test_release_version_check -v
```

Expected: failure because runtime and packaging metadata still declare `1.0.6`.

- [ ] **Step 3: Update every version-bearing file**

Change `1.0.6` to `1.0.7`, `v1.0.6` to `v1.0.7`, and numeric tuples
`(1, 0, 6, 0)` to `(1, 0, 7, 0)` in the files listed above. Add the release
design document recording the required assets, validation gates, immutable tag
policy, and the publish workflow.

- [ ] **Step 4: Verify the version test is GREEN**

Run:

```bash
python -m unittest tests.test_release_version_check -v
python scripts/check_release_version.py v1.0.7
```

Expected: all tests and checks pass with zero failures.

- [ ] **Step 5: Run final local verification**

Run:

```bash
xvfb-run --auto-servernum python -m unittest discover -s tests -v
python -m compileall -q .
git diff --check
git status --short
```

Expected: the full suite passes, compile and whitespace checks exit zero, and status lists only the intended release files.

- [ ] **Step 6: Commit and push main**

```bash
git add app_version.py CatType.spec packaging/CatType.iss \
  packaging/version_info.txt README.md tests/test_release_version_check.py \
  docs/superpowers/specs/2026-08-13-v1.0.7-release-design.md
git commit -m "release: prepare Cat Type 1.0.7"
git push origin main
```

- [ ] **Step 7: Verify the cross-platform branch build**

Use `gh run list --workflow build.yml --branch main` to find the run for the
pushed commit, then `gh run watch <run-id> --exit-status`. Inspect the run with
`gh run view <run-id>` and require successful Windows, macOS Intel, and Linux
jobs before tagging.

- [ ] **Step 8: Tag and publish the release**

```bash
git tag -a v1.0.7 -m "Cat Type 1.0.7"
git push origin v1.0.7
```

Use `gh run list --workflow release.yml --branch v1.0.7` and
`gh run watch <run-id> --exit-status`. Do not move or recreate the tag if a
job fails.

- [ ] **Step 9: Audit the published release**

Run:

```bash
gh release view v1.0.7 --json tagName,isDraft,isPrerelease,url,assets
git status --short --branch
```

Require a non-draft, non-prerelease release with these exact asset names:

```text
Cat-Type-Windows-x64.exe
Cat-Type-macOS-x64.dmg
Cat-Type-macOS-arm64.dmg
Cat-Type-Linux-x64.tar.gz
Cat-Type-Linux-arm64.tar.gz
SHA256SUMS.txt
```
