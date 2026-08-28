# Linux Update Test Platform Scope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make cross-platform `unittest` discovery skip the Linux update integration module outside Linux while preserving its complete execution on Linux.

**Architecture:** Express the platform boundary in the test module with the repository's existing `unittest.skipUnless` convention. Guard both Linux helper test classes because their setup and behavior depend on POSIX executable bits, `/bin/sh`, `/proc`, and Linux filesystem semantics.

**Tech Stack:** Python 3.12, `unittest`, Linux shell/process APIs

## Global Constraints

- Do not modify `platform_updater.py` or CI workflow selections.
- All 13 tests must continue to execute on Linux.
- All 13 tests must be reported as skipped during non-Linux discovery.
- Use `sys.platform.startswith("linux")` to match the repository's existing platform-test convention.

---

### Task 1: Guard Linux Helper Tests at Their Platform Boundary

**Files:**
- Modify: `tests/test_linux_update_integration.py:3-25`
- Modify: `tests/test_linux_update_integration.py:212`

**Interfaces:**
- Consumes: Python's `sys.platform` and `unittest.skipUnless(condition, reason)`
- Produces: Linux-only execution of `LinuxHelperContractTests` and `LinuxHelperIntegrationTests`

- [ ] **Step 1: Verify the current non-Linux failure signal**

Run on Windows:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_linux_update_integration -v
```

Expected: `FAILED (failures=3, errors=8)` because executable bits and `/bin/sh` are unavailable.

- [ ] **Step 2: Add the minimal class guards**

Add the import:

```python
import sys
```

Apply the same guard to both test classes:

```python
@unittest.skipUnless(
    sys.platform.startswith("linux"),
    "Linux helper integration requires Linux process and filesystem semantics",
)
class LinuxHelperContractTests(unittest.TestCase):
```

```python
@unittest.skipUnless(
    sys.platform.startswith("linux"),
    "Linux helper integration requires Linux process and filesystem semantics",
)
class LinuxHelperIntegrationTests(unittest.TestCase):
```

- [ ] **Step 3: Verify the guarded module on Windows**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_linux_update_integration -v
```

Expected: `OK (skipped=13)` with no failures or errors.

- [ ] **Step 4: Inspect and commit the focused test-boundary fix**

Run:

```powershell
git diff --check
git diff -- tests/test_linux_update_integration.py docs/superpowers/plans/2026-08-28-linux-update-test-platform-scope.md
git add -- tests/test_linux_update_integration.py docs/superpowers/plans/2026-08-28-linux-update-test-platform-scope.md
git commit -m "test: scope Linux update integration to Linux"
```
