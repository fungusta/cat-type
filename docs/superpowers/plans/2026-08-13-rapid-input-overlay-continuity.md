# Rapid-Input Overlay Continuity and v1.0.8 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the cat overlay continuously visible during rapid input when caret discovery briefly trails keyboard activity, then publish the verified fix as Cat Type v1.0.8.

**Architecture:** Preserve the existing asynchronous keyboard and caret threads and the 50 ms freshness threshold. Change only the Tk tick's render eligibility so a stale snapshot can continue rendering an already-visible, already-anchored overlay, while a hidden overlay still waits for fresh geometry and all existing hide conditions retain precedence.

**Tech Stack:** Python 3.12, tkinter, `unittest`, `unittest.mock`, Git, GitHub Actions, GitHub CLI.

## Global Constraints

- The existing 50 ms freshness threshold remains the gate for a new appearance.
- A visible overlay may continue rendering from a temporarily stale snapshot only when that snapshot still contains a usable rectangle.
- Disabled state, expired animation, missing geometry, and password-field detection must continue to hide the overlay immediately.
- A continuing appearance must retain its existing anchor while frames and opacity continue updating.
- The release version is `1.0.8` and the immutable annotated Git tag is `v1.0.8`.
- The tag may be pushed only after the exact pushed `main` commit passes the cross-platform build workflow.
- Publication requires a non-draft GitHub Release containing five platform packages plus `SHA256SUMS.txt`.

---

### Task 1: Preserve a visible overlay across a stale caret snapshot

**Files:**
- Modify: `tests/test_behavior.py`
- Modify: `cat_type.py:1826-1843`

**Interfaces:**
- Consumes: `AppEvent(kind="key", happened_at: float, paw: PawAction)`, `CaretSnapshot.captured_at`, `CaretSnapshot.rect`, `CaretSnapshot.is_password`, `AnimationState.is_visible(now: float)`, and `CatTypeApp._overlay_visible`.
- Produces: Tk tick behavior in which `_show(snapshot, now)` is called when all normal render conditions hold and either the snapshot is fresh or the overlay is already visible.

- [ ] **Step 1: Add the tick-level regression fixture and tests**

Add `CaretSnapshot` to the imports from `cat_type`, then add this class after `CatTypeKeyActivityTests`:

```python
class CatTypeTickRenderingTests(unittest.TestCase):
    @staticmethod
    def make_app(
        *,
        overlay_visible: bool,
        snapshot: CaretSnapshot,
    ) -> CatTypeApp:
        app = CatTypeApp.__new__(CatTypeApp)
        app._shutdown_signal = None
        app.root = Mock()
        app.root.winfo_exists.return_value = True
        app._drain_update_events = Mock()
        app._shutting_down = False
        app._hook_failed = False
        app.settings = AppSettings(
            enabled=True,
            hold_seconds=1.5,
            fade_seconds=0.35,
        )
        app.animation = AnimationState(
            hide_after=1.5,
            fade_seconds=0.35,
        )
        app.animation.record_key(10.0, "left")
        app.events = queue.SimpleQueue()
        app.events.put(AppEvent("key", 10.10, "right"))
        app.keystroke_count = 1
        app._last_key_at = 10.0
        app._anchor_position = (100, 100) if overlay_visible else None
        app._overlay_visible = overlay_visible
        app._settings_window = None
        app.tracker = Mock()
        app.tracker.snapshot.return_value = snapshot
        app._show = Mock()
        app._hide = Mock()
        return app

    def test_visible_overlay_survives_briefly_stale_snapshot(self) -> None:
        snapshot = CaretSnapshot(
            captured_at=10.04,
            rect=ScreenRect(500, 300, 502, 320),
            source="test",
        )
        app = self.make_app(overlay_visible=True, snapshot=snapshot)

        with patch("cat_type.time.monotonic", return_value=10.11):
            app._tick()

        app._show.assert_called_once_with(snapshot, 10.11)
        app._hide.assert_not_called()

    def test_hidden_overlay_still_waits_for_fresh_snapshot(self) -> None:
        snapshot = CaretSnapshot(
            captured_at=10.04,
            rect=ScreenRect(500, 300, 502, 320),
            source="test",
        )
        app = self.make_app(overlay_visible=False, snapshot=snapshot)

        with patch("cat_type.time.monotonic", return_value=10.11):
            app._tick()

        app._show.assert_not_called()
        app._hide.assert_called_once_with(reset_anchor=False)

    def test_password_snapshot_hides_visible_overlay(self) -> None:
        snapshot = CaretSnapshot(
            captured_at=10.04,
            rect=None,
            is_password=True,
            source="uia-password",
        )
        app = self.make_app(overlay_visible=True, snapshot=snapshot)

        with patch("cat_type.time.monotonic", return_value=10.11):
            app._tick()

        app._show.assert_not_called()
        app._hide.assert_called_once_with(reset_anchor=True)
```

- [ ] **Step 2: Run the targeted tests and verify RED**

Run:

```bash
python -m unittest \
  tests.test_behavior.CatTypeTickRenderingTests -v
```

Expected: `test_visible_overlay_survives_briefly_stale_snapshot` fails because `_tick()` calls `_hide(reset_anchor=False)` instead of `_show(snapshot, 10.11)`; the hidden-overlay and password tests pass.

- [ ] **Step 3: Allow continuity only for an already-visible overlay**

Change the render condition in `CatTypeApp._tick()` to:

```python
        if (
            self.settings.enabled
            and
            self.animation.is_visible(now)
            and (snapshot_is_current or self._overlay_visible)
            and snapshot.rect is not None
            and not snapshot.is_password
        ):
```

Do not change the 50 ms threshold, `_show()`, `_hide()`, caret tracking, or the reset-anchor rule.

- [ ] **Step 4: Run the targeted tests and verify GREEN**

Run the Step 2 command again.

Expected: all three `CatTypeTickRenderingTests` pass with zero failures.

- [ ] **Step 5: Run the complete behavior module**

Run:

```bash
python -m unittest tests.test_behavior -v
```

Expected: every behavior test passes with zero failures.

- [ ] **Step 6: Commit the fix and regression coverage**

```bash
git add cat_type.py tests/test_behavior.py
git commit -m "fix: keep cat visible during rapid input"
```

---

### Task 2: Prepare Cat Type v1.0.8 metadata

**Files:**
- Modify: `tests/test_release_version_check.py`
- Modify: `app_version.py`
- Modify: `CatType.spec:73`
- Modify: `packaging/CatType.iss:2`
- Modify: `packaging/version_info.txt`
- Modify: `README.md:148`

**Interfaces:**
- Consumes: `metadata_mismatches(expected: str, project_root: Path) -> list[str]` and `scripts/check_release_version.py vMAJOR.MINOR.PATCH`.
- Produces: internally consistent runtime and package metadata for version `1.0.8`, documented release tag `v1.0.8`, and a release checker that rejects `v1.0.7` as stale.

- [ ] **Step 1: Advance the release-version test expectation first**

Change `test_current_version_matches_every_platform_marker` and its fixture assertions to:

```python
    def test_current_version_matches_every_platform_marker(self) -> None:
        self.assertEqual(APP_VERSION, "1.0.8")
        self.assertEqual(metadata_mismatches("1.0.8", PROJECT_ROOT), [])
        self.assertNotEqual(metadata_mismatches("1.0.7", PROJECT_ROOT), [])

    def test_runtime_version_drift_is_reported(self) -> None:
        root = self.copy_version_files()
        self.assertEqual(metadata_mismatches("1.0.8", root), [])

        (root / "app_version.py").write_text('APP_VERSION = "1.0.4"\n')

        self.assertIn("app_version.py", metadata_mismatches("1.0.8", root))
```

- [ ] **Step 2: Run the release-version test and verify RED**

Run:

```bash
python -m unittest \
  tests.test_release_version_check.ReleaseVersionCheckTests.test_current_version_matches_every_platform_marker \
  tests.test_release_version_check.ReleaseVersionCheckTests.test_runtime_version_drift_is_reported \
  -v
```

Expected: failures report that `APP_VERSION` and package metadata are still `1.0.7`.

- [ ] **Step 3: Advance every version-bearing file to 1.0.8**

Apply these exact values:

```python
# app_version.py
APP_VERSION: str = "1.0.8"
```

```python
# CatType.spec, inside BUNDLE(...)
version="1.0.8",
```

```text
; packaging/CatType.iss
#define MyAppVersion "1.0.8"
```

```python
# packaging/version_info.txt
filevers=(1, 0, 8, 0),
prodvers=(1, 0, 8, 0),
StringStruct('FileVersion', '1.0.8'),
StringStruct('ProductVersion', '1.0.8')
```

Update the README release example to:

```text
Push a tag such as `v1.0.8` to build every supported architecture and publish
the assets together on a GitHub Release.
```

- [ ] **Step 4: Run the release-version tests and checker and verify GREEN**

Run:

```bash
python -m unittest tests.test_release_version_check -v
python scripts/check_release_version.py v1.0.8
```

Expected: all release-version tests pass and the checker exits zero without output.

- [ ] **Step 5: Prove stale v1.0.7 metadata is rejected**

Run:

```bash
if python scripts/check_release_version.py v1.0.7; then
  echo "unexpectedly accepted stale v1.0.7 metadata" >&2
  exit 1
fi
```

Expected: the checker reports every version-bearing metadata file as mismatched and the shell wrapper exits zero.

- [ ] **Step 6: Commit the v1.0.8 metadata**

```bash
git add \
  app_version.py \
  CatType.spec \
  packaging/CatType.iss \
  packaging/version_info.txt \
  tests/test_release_version_check.py \
  README.md
git commit -m "release: prepare Cat Type 1.0.8"
```

---

### Task 3: Verify and push the exact main commit

**Files:**
- Verify: all tracked project files
- Verify: `.github/workflows/build.yml`

**Interfaces:**
- Consumes: the complete repository test suite, Python compilation, release-version checker, Git history, and the GitHub `Cross-platform build` workflow.
- Produces: one clean `main` commit on `origin/main` with successful Windows x64, macOS Intel, and Linux x64 build jobs.

- [ ] **Step 1: Run the complete local test suite in a Linux desktop environment**

Run in an environment containing Python 3.12, tkinter, Xvfb, and `requirements.txt` dependencies:

```bash
xvfb-run --auto-servernum \
  python -m unittest discover -s tests -v
```

Expected: every discovered test passes with zero failures or errors. Platform-specific skips are allowed only where the test's decorator names a different operating system.

- [ ] **Step 2: Run static, metadata, and worktree checks**

Run:

```bash
python -m compileall -q .
python scripts/check_release_version.py v1.0.8
git diff --check
git status --short
```

Expected: every command exits zero and `git status --short` prints nothing.

- [ ] **Step 3: Confirm the release commit set and push main**

Run:

```bash
git log --oneline origin/main..HEAD
git push origin main
```

Expected: the log contains only the approved design, flicker fix, implementation plan, and v1.0.8 preparation commits; the push advances `origin/main` to the current `HEAD` without force.

- [ ] **Step 4: Find the exact push-triggered build workflow**

Run:

```bash
head_sha=$(git rev-parse HEAD)
gh run list \
  --workflow build.yml \
  --branch main \
  --event push \
  --limit 10 \
  --json databaseId,headSha,status,conclusion,url \
  --jq ".[] | select(.headSha == \"${head_sha}\")"
```

Expected: exactly one run is returned with `headSha` equal to the pushed `HEAD`.

- [ ] **Step 5: Wait for the pre-tag cross-platform build**

Run `gh run watch --exit-status RUN_ID`, using the `databaseId` from Step 4.

Expected: the workflow concludes `success`; Windows x64, macOS Intel, and Linux x64 test/build/smoke jobs all pass. Do not create or push the release tag if this command fails.

---

### Task 4: Tag, publish, and audit v1.0.8

**Files:**
- Create externally: annotated Git tag `v1.0.8`
- Create externally: GitHub Release `v1.0.8`

**Interfaces:**
- Consumes: the exact successful `origin/main` commit, `.github/workflows/release.yml`, and the GitHub Release publication job.
- Produces: immutable tag `v1.0.8` and a non-draft GitHub Release containing `Cat-Type-Windows-x64.exe`, two macOS DMGs, two Linux tarballs, and `SHA256SUMS.txt`.

- [ ] **Step 1: Reconfirm tag absence and exact tested commit**

Run:

```bash
git fetch origin --tags
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
if git rev-parse -q --verify refs/tags/v1.0.8; then
  echo "v1.0.8 already exists" >&2
  exit 1
fi
```

Expected: `HEAD` equals `origin/main` and `v1.0.8` does not exist locally or after fetching remote tags.

- [ ] **Step 2: Create and push the immutable annotated tag**

Run:

```bash
git tag -a v1.0.8 -m "Cat Type v1.0.8"
git push origin v1.0.8
```

Expected: the push creates remote tag `v1.0.8` on the exact tested `main` commit. Never move, delete, or recreate this tag after the push.

- [ ] **Step 3: Find and wait for the tag-triggered release workflow**

Run:

```bash
tag_sha=$(git rev-list -n 1 v1.0.8)
gh run list \
  --workflow release.yml \
  --limit 10 \
  --json databaseId,headSha,status,conclusion,url \
  --jq ".[] | select(.headSha == \"${tag_sha}\")"
```

Use the returned `databaseId` with:

```bash
gh run watch --exit-status RUN_ID
```

Expected: all five matrix builds and the publish job conclude `success`.

- [ ] **Step 4: Audit the published GitHub Release and assets**

Run:

```bash
gh release view v1.0.8 \
  --json tagName,isDraft,isPrerelease,url,assets \
  --jq '{
    tagName,
    isDraft,
    isPrerelease,
    url,
    assets: [.assets[].name] | sort
  }'
```

Expected: `tagName` is `v1.0.8`, `isDraft` and `isPrerelease` are false, and the sorted asset names are exactly:

```text
Cat-Type-Linux-arm64.tar.gz
Cat-Type-Linux-x64.tar.gz
Cat-Type-macOS-arm64.dmg
Cat-Type-macOS-x64.dmg
Cat-Type-Windows-x64.exe
SHA256SUMS.txt
```

- [ ] **Step 5: Perform the final repository and remote-state audit**

Run:

```bash
git status --short
git rev-parse HEAD
git rev-parse origin/main
git rev-list -n 1 v1.0.8
git ls-remote origin refs/tags/v1.0.8^{}
python scripts/check_release_version.py v1.0.8
```

Expected: the worktree is clean; `HEAD`, `origin/main`, the peeled annotated tag commit, and the remote peeled tag commit are identical; the release checker exits zero.
