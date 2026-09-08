# Separate Wardrobe and Achievements Implementation Plan

> **For agentic workers:** Execute the steps inline with verification before completion.

**Goal:** Give outfit selection and achievement progress their own settings tabs.

**Architecture:** Keep selection and preview in `WardrobeView`. Add `AchievementsView` for reward requirements and progress; `SettingsWindow` coordinates navigation and live updates using the existing catalog and saved unlocks.

**Tech Stack:** Python, Tkinter, Pillow, unittest.

## Constraints

- Keep existing achievements, permanent unlocks, and shared hat/glasses settings.
- Switching tabs preserves pending choices; Save applies them and Cancel discards them.
- Locked wardrobe items link to their achievement without equipping anything.
- Both tabs fit a 620-pixel window and use the existing vertical scrolling.
- Keep the current release version; this request changes the UI.

## Implementation

- [x] Extend `tests/test_wardrobe.py` to exercise separate pages, navigation to locked rewards, live progress/unlocks, pending outfit preservation, and narrow layout. Run `python -m unittest tests.test_wardrobe` and confirm the missing Achievements tab fails.
- [x] Create `achievements_view.py`: six reward cards using `ACCESSORIES` and `progress`, with requirements, counts, unlocked state, and a focusable target for wardrobe links.
- [x] Simplify `wardrobe_view.py`: keep outfit controls and preview; replace requirements/counts with Locked/Unlocked and a link callback.
- [x] Wire the fourth tab and both update paths in `settings_window.py`; update the expected navigation copy in `tests/test_settings_window.py` and the README instructions.
- [x] Run focused tests, then `python -m unittest discover -s tests`. Capture both pages at normal/narrow sizes and verify locked-link scrolling.
- [x] Request a bounded code review, resolve actionable findings, and build a Windows preview. Review found no actionable regressions; local integration follows the verified commit.
