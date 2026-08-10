# Cross-Platform Icon Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Linux and macOS packages select and contain their correct runtime icon, and reject broken packages before publication.

**Architecture:** A dependency-free `platform_assets.py` module owns the icon filename mapping used by both runtime and PyInstaller. A post-build checker reads the finished PyInstaller CArchive and both GitHub Actions workflows run it before uploading artifacts.

**Tech Stack:** Python 3.12, `unittest`, PyInstaller 6.21, GitHub Actions YAML

## Global Constraints

- Preserve the documented X11/XWayland requirement on Linux.
- Preserve the existing Windows package behavior.
- Do not hide missing runtime assets with exception handling.
- Validate the finished executable before artifact upload or release packaging.

---

### Task 1: Share the Platform Icon Mapping

**Files:**
- Create: `platform_assets.py`
- Create: `tests/test_platform_assets.py`
- Modify: `cat_type.py:24-35`
- Modify: `CatType.spec:1-12`

**Interfaces:**
- Produces: `icon_filename(platform: str) -> str`
- Consumed by: `cat_type.py`, `CatType.spec`, and Task 2's package checker

- [ ] **Step 1: Write the failing platform mapping test**

```python
import importlib
import importlib.util
import unittest


class PlatformIconTests(unittest.TestCase):
    def test_selects_native_icon_filename_for_each_platform(self) -> None:
        spec = importlib.util.find_spec("platform_assets")
        self.assertIsNotNone(spec, "platform_assets module must exist")
        platform_assets = importlib.import_module("platform_assets")

        expected = {
            "win32": "cat-type.ico",
            "darwin": "cat-type.icns",
            "linux": "cat-type.png",
        }
        for platform, filename in expected.items():
            with self.subTest(platform=platform):
                self.assertEqual(
                    platform_assets.icon_filename(platform),
                    filename,
                )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify the missing mapping fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_platform_assets -v`

Expected: FAIL at `platform_assets module must exist`.

- [ ] **Step 3: Implement the shared mapping and use it in runtime and build configuration**

```python
# platform_assets.py
def icon_filename(platform: str) -> str:
    if platform == "win32":
        return "cat-type.ico"
    if platform == "darwin":
        return "cat-type.icns"
    return "cat-type.png"
```

In `cat_type.py`, import `icon_filename` and define:

```python
APP_ICON = APP_DIR / "assets" / icon_filename(sys.platform)
```

In `CatType.spec`, import `icon_filename` and define:

```python
icon_path = project_root / "assets" / icon_filename(sys.platform)
```

- [ ] **Step 4: Run the mapping test and verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_platform_assets -v`

Expected: 1 test passes.

- [ ] **Step 5: Run the behavior and settings tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_behavior tests.test_settings -v`

Expected: all tests pass.

- [ ] **Step 6: Commit the shared mapping**

```powershell
git add -- platform_assets.py tests/test_platform_assets.py cat_type.py CatType.spec
git commit -m "fix: select packaged icon by platform"
```

---

### Task 2: Validate the Finished PyInstaller Archive

**Files:**
- Create: `scripts/check_bundled_icon.py`
- Create: `tests/test_bundled_icon_check.py`

**Interfaces:**
- Consumes: `icon_filename(platform: str) -> str` from Task 1
- Produces: `expected_icon_entry(platform: str) -> str`
- Produces: `validate_bundled_icon(entries: Collection[str], platform: str) -> str`
- CLI: `python scripts/check_bundled_icon.py <executable>`

- [ ] **Step 1: Write failing validator tests**

```python
import importlib
import importlib.util
import unittest


class BundledIconCheckTests(unittest.TestCase):
    def _module(self):
        spec = importlib.util.find_spec("scripts.check_bundled_icon")
        self.assertIsNotNone(spec, "bundled icon checker must exist")
        return importlib.import_module("scripts.check_bundled_icon")

    def test_accepts_expected_platform_icon(self) -> None:
        checker = self._module()
        entry = checker.validate_bundled_icon(
            {"assets/cat-type.icns"},
            "darwin",
        )
        self.assertEqual(entry, "assets/cat-type.icns")

    def test_rejects_another_platforms_icon(self) -> None:
        checker = self._module()
        with self.assertRaisesRegex(
            ValueError,
            "assets/cat-type.png",
        ):
            checker.validate_bundled_icon(
                {"assets/cat-type.ico"},
                "linux",
            )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and verify the missing checker fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_bundled_icon_check -v`

Expected: both tests FAIL at `bundled icon checker must exist`.

- [ ] **Step 3: Implement validation and the archive-reading CLI**

```python
from __future__ import annotations

import argparse
import sys
from collections.abc import Collection
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader

from platform_assets import icon_filename


def expected_icon_entry(platform: str) -> str:
    return f"assets/{icon_filename(platform)}"


def validate_bundled_icon(entries: Collection[str], platform: str) -> str:
    expected = expected_icon_entry(platform)
    if expected not in entries:
        raise ValueError(f"PyInstaller archive is missing {expected}")
    return expected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    args = parser.parse_args()
    archive = CArchiveReader(str(args.executable))
    try:
        expected = validate_bundled_icon(archive.toc, sys.platform)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Verified bundled runtime icon: {expected}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the validator tests and verify they pass**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_bundled_icon_check -v`

Expected: 2 tests pass.

- [ ] **Step 5: Commit the package checker**

```powershell
git add -- scripts/check_bundled_icon.py tests/test_bundled_icon_check.py
git commit -m "test: validate bundled platform icon"
```

---

### Task 3: Gate Build and Release Artifacts

**Files:**
- Modify: `.github/workflows/build.yml`
- Modify: `.github/workflows/release.yml`

**Interfaces:**
- Consumes: `python scripts/check_bundled_icon.py <executable>` from Task 2
- Produces: a CI gate between PyInstaller and artifact packaging/upload

- [ ] **Step 1: Add executable paths to both build matrices**

Use these exact platform paths:

```yaml
executable: dist/Cat Type.exe
executable: dist/Cat Type.app/Contents/MacOS/Cat Type
executable: dist/Cat Type
```

Use the macOS path for both release architectures and the Linux path for both
release architectures.

- [ ] **Step 2: Run the checker immediately after each PyInstaller build**

Add this step to both workflows directly after `Build application`:

```yaml
- name: Verify bundled platform icon
  run: python scripts/check_bundled_icon.py "${{ matrix.executable }}"
```

- [ ] **Step 3: Build the local Windows package**

Run:

```powershell
.\.venv\Scripts\python.exe scripts\build_icon.py
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean CatType.spec
```

Expected: PyInstaller exits 0 and produces `dist\Cat Type.exe`.

- [ ] **Step 4: Inspect the finished local package with the CI checker**

Run:

```powershell
.\.venv\Scripts\python.exe scripts\check_bundled_icon.py "dist\Cat Type.exe"
```

Expected: `Verified bundled runtime icon: assets/cat-type.ico`.

- [ ] **Step 5: Run the full test suite**

Run: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`

Expected: all tests pass with no errors or failures.

- [ ] **Step 6: Review configuration and commit the workflow gate**

Run: `git diff --check`

Expected: exit 0 with no output.

```powershell
git add -- .github/workflows/build.yml .github/workflows/release.yml
git commit -m "ci: reject packages missing runtime icon"
```
