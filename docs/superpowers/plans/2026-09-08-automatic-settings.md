# Automatic Settings Implementation Plan

**Goal:** Save and apply settings whenever a user changes them.

**Architecture:** Observe persisted Tk variables in SettingsWindow and reuse
the existing AppSettings normalization and application callback. Include metrics
preferences in that same path and replace manual footer actions with Close.

**Tech Stack:** Python, Tkinter, unittest.

## Implementation

- [x] Add integration coverage using a temporary SettingsStore for changing
  controls, immediately closing, duplicate values, and failed-save recovery.
- [x] Update existing settings and wardrobe expectations for automatic saving.
- [x] Run focused tests and verify failures expose the missing behavior.
- [x] Register change callbacks after initialization, save without closing,
  and report/retry persistence errors. Preserve normalized values and avoid
  applying identical settings repeatedly.
- [x] Debounce size changes by 200 ms, flushing on other edits or close.
- [x] Preserve pending macOS permission requests during unrelated autosaves
  while retaining explicit pause cancellation.
- [x] Synchronize tray and permission enabled-state changes into the open
  window without another save, preventing autosave from undoing a pause.
- [x] Update footer actions, wardrobe hints, and README instructions.
- [x] Run focused tests, the full unittest suite, and git diff checks.

## Verification

`python -m unittest discover -s tests -q`: 383 tests run, 352 passed and 31
platform-specific tests skipped. `git diff --check` passed. The suite also
printed a Tk theme-change message during window teardown.
