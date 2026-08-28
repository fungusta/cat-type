# Deterministic Small-Screen Layout Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the small-screen settings layout test exercise a deterministic vertical-overflow scenario on every host display.

**Architecture:** Keep production layout behavior unchanged and fully specify the test's virtual screen constraints. Pin screen height and window-manager maximum size, then assert the resulting geometry and real overflow state before checking scrollbar mapping.

**Tech Stack:** Python 3.12, `unittest`, Tk 8.6

## Global Constraints

- Do not modify `settings_window.py`.
- Report an 800-pixel screen height and a `(5000, 5000)` window-manager maximum size in the test fixture.
- Require a 720-pixel final settings-window height.
- Verify content height exceeds the actual canvas viewport before requiring a mapped scrollbar.

---

### Task 1: Pin the Small-Screen Overflow Fixture

**Files:**
- Modify: `tests/test_settings_window.py:569-614`

**Interfaces:**
- Consumes: `SettingsWindow._center()` and Tk geometry inspection methods
- Produces: a deterministic integration contract for the narrow, vertically constrained opening path

- [ ] **Step 1: Verify the current host-dependent failure signal**

Run on the current Windows display:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_settings_window.SettingsWindowTkLayoutTests.test_opening_measures_after_reducing_minimum_for_small_screen -v
```

Expected: FAIL at the unconditional scrollbar assertion because the 1440-pixel host screen lets content fit exactly.

- [ ] **Step 2: Constrain the complete virtual screen fixture**

Immediately after the existing screen-width override, add:

```python
fitted_window.window.winfo_screenheight = lambda: 800
fitted_window.window.maxsize = lambda: (5000, 5000)
```

- [ ] **Step 3: Strengthen the overflow assertions**

After calculating `bounds`, retain the existing width and remeasurement assertions, then add the deterministic geometry and overflow checks before the scrollbar assertion:

```python
self.assertEqual(fitted_window.window.winfo_height(), 720)
self.assertGreater(
    bounds[3] - bounds[1],
    fitted_window.scroll_canvas.winfo_height(),
)
self.assertTrue(fitted_window.scrollbar.winfo_ismapped())
```

- [ ] **Step 4: Verify the focused test and Tk layout class**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_settings_window.SettingsWindowTkLayoutTests.test_opening_measures_after_reducing_minimum_for_small_screen -v
.venv\Scripts\python.exe -m unittest tests.test_settings_window.SettingsWindowTkLayoutTests -v
```

Expected: the focused test and all 23 Tk layout tests pass.

- [ ] **Step 5: Verify the complete settings-window module**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_settings_window -v
```

Expected: all settings-window tests pass.

- [ ] **Step 6: Inspect and commit the deterministic fixture fix**

Run:

```powershell
git diff --check
git diff -- tests/test_settings_window.py docs/superpowers/plans/2026-08-28-deterministic-small-screen-layout-test.md
git add -- tests/test_settings_window.py docs/superpowers/plans/2026-08-28-deterministic-small-screen-layout-test.md
git commit -m "test: make small-screen layout fixture deterministic"
```
