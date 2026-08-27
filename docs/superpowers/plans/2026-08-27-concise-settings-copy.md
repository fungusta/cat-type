# Concise Settings Copy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Settings concise by removing decorative, explanatory, and privacy copy while preserving every functional control and behavior.

**Architecture:** Keep the existing scrollable Settings/Metrics structure and card components. Remove the shared hero, place its animated cat preview inside the Cat style card, simplify cards to title-only headings, and allow toggles to render without descriptions. Delete the footer-message fitting behavior because the footer will contain actions only.

**Tech Stack:** Python 3.12, Tkinter, Pillow, `unittest`.

---

### Task 1: Lock the concise UI contract with tests

**Files:**
- Modify: `tests/test_settings_window.py`

- [ ] Add a recursive widget-text assertion proving filler and privacy copy are absent while functional labels remain.
- [ ] Assert the page switcher is the first content section and the preview belongs to the Cat style card.
- [ ] Update responsive-layout and footer tests for the hero-free, message-free layout.
- [ ] Run `xvfb-run --auto-servernum python -m unittest tests.test_settings_window -v` and confirm the new expectations fail against the old UI.

### Task 2: Simplify the Settings UI

**Files:**
- Modify: `settings_window.py`

- [ ] Remove the hero and its page-specific marketing copy.
- [ ] Move the animated preview canvas into the Cat style card and keep it visible in both responsive modes.
- [ ] Remove every card subtitle, toggle description, size nickname, metrics privacy paragraph, and footer privacy message.
- [ ] Simplify the card and toggle interfaces so removed descriptions reserve no layout space.
- [ ] Remove obsolete hero and footer responsive logic.
- [ ] Run the focused Settings-window tests and confirm they pass.

### Task 3: Verify the change

**Files:**
- Verify only

- [ ] Run the complete test suite under Xvfb.
- [ ] Inspect the resulting diff for accidental behavior changes or leftover filler strings.
- [ ] Review the implementation against `docs/superpowers/specs/2026-08-27-concise-settings-copy-design.md`.
