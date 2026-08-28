# Windows Updater PyInstaller Environment Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure a Windows auto-update relaunch starts as a fresh PyInstaller one-file application instead of reusing the deleted extraction directory of the previous version.

**Architecture:** Keep the fix at the Python-to-installer process boundary. `WindowsInstaller.start()` will copy the current environment, add PyInstaller's documented public reset flag, and pass that copy to `subprocess.Popen`; the Inno installer and the Cat Type process it launches will inherit the reset request.

**Tech Stack:** Python 3.12, `subprocess`, `unittest`, PyInstaller 6.21, Inno Setup 6

## Global Constraints

- Preserve all environment variables other than setting `PYINSTALLER_RESET_ENVIRONMENT` to exactly `"1"`.
- Do not mutate `os.environ` in the running Cat Type process.
- Preserve the existing installer arguments and `shell=False` behavior.
- Make no changes to the Inno Setup script or non-Windows updater implementations.

---

### Task 1: Reset PyInstaller State Across the Windows Installer Handoff

**Files:**
- Modify: `tests/test_windows_installer_contract.py:55-69`
- Modify: `platform_updater.py:217-219`

**Interfaces:**
- Consumes: `WindowsInstaller(popen: Callable[..., object] | None = None)` and `WindowsInstaller.start(package: Path) -> None`
- Produces: a `subprocess.Popen` call whose keyword arguments include `shell=False` and an `env: dict[str, str]` containing `PYINSTALLER_RESET_ENVIRONMENT="1"`

- [ ] **Step 1: Write the failing contract test**

Update the existing launch-contract test to seed a sentinel variable with `unittest.mock.patch.dict`, then assert separately on the positional arguments and keyword arguments recorded by `RecordingPopen`:

```python
def test_starts_verified_installer_with_fresh_pyinstaller_environment(self) -> None:
    popen = RecordingPopen()
    installer = WindowsInstaller(popen=popen)
    package = Path("/verified") / INSTALLER_NAME

    with patch.dict(
        os.environ,
        {
            "CAT_TYPE_ENV_SENTINEL": "preserved",
            "PYINSTALLER_RESET_ENVIRONMENT": "stale",
        },
    ):
        result = installer.start(package)
        self.assertEqual(
            os.environ["PYINSTALLER_RESET_ENVIRONMENT"],
            "stale",
        )

    self.assertIsNone(result)
    self.assertEqual(len(popen.calls), 1)
    args, kwargs = popen.calls[0]
    self.assertEqual(args, [str(package), *EXPECTED_FLAGS])
    self.assertFalse(kwargs["shell"])
    self.assertIn("env", kwargs)
    environment = kwargs["env"]
    self.assertEqual(environment["CAT_TYPE_ENV_SENTINEL"], "preserved")
    self.assertEqual(environment["PYINSTALLER_RESET_ENVIRONMENT"], "1")
```

Add the required imports at the top of the test module:

```python
import os
from unittest.mock import patch
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_windows_installer_contract.WindowsInstallerTests.test_starts_verified_installer_with_fresh_pyinstaller_environment -v
```

Expected: FAIL because `kwargs` has no `env` entry.

- [ ] **Step 3: Implement the minimal process-boundary reset**

Change `WindowsInstaller.start()` to copy the current process environment, set the documented reset flag on the copy, and pass it to the installer process:

```python
def start(self, package: Path) -> None:
    package = _validated_windows_installer(package)
    environment = os.environ.copy()
    environment["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    self._popen(
        [str(package), *self.FLAGS],
        shell=False,
        env=environment,
    )
```

- [ ] **Step 4: Run focused verification and verify GREEN**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_windows_installer_contract -v
```

Expected: all Windows installer contract tests pass.

- [ ] **Step 5: Run the full regression suite**

Run:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: all tests pass with no failures or errors.

- [ ] **Step 6: Inspect and commit the focused patch**

Run:

```powershell
git diff --check
git diff -- platform_updater.py tests/test_windows_installer_contract.py docs/superpowers/plans/2026-08-28-windows-updater-pyinstaller-environment-reset.md
git add -- platform_updater.py tests/test_windows_installer_contract.py docs/superpowers/plans/2026-08-28-windows-updater-pyinstaller-environment-reset.md
git commit -m "fix: reset PyInstaller state for Windows updates"
```
