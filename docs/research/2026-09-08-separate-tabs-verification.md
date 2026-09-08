# Separate tabs verification

Wardrobe now owns outfit selection and previews. Achievements owns requirements,
reward names, counts, and permanent unlock status. Each wardrobe item links to
the matching achievement, scrolling it into view and giving it keyboard focus.
Switching tabs preserves pending choices and existing Save/Cancel behavior.

Validation on Windows:

- Baseline: 57 focused tests passed.
- Red check: six new/updated UI checks failed because Achievements was absent.
- Focused implementation check: 58 tests passed.
- Final full suite: 354 tests run, 31 skipped, no failures. The existing Tk
  `ThemeChanged` teardown diagnostic remains in full-suite output.
- Real Tk captures inspected at 920×860 and 620×600, with both default scaling
  and Tk scaling 2.5. Both tabs, all four navigation labels, and footer controls
  fit. Long pages use the existing scrollbar.
- The regression test follows the Crown link at 620×500 and confirms the entire
  achievement card is visible and focused.
- PyInstaller Windows build passed. Package checks verified both view modules,
  settings, achievement logic, runtime icon/backends, six cats, and six accessories.
- Independent read-only review found no actionable regressions. Additional real
  Tk checks covered all six reward links, active-day counts, and narrow layouts
  at higher scaling.

Local evidence is under `.debug/separate-tabs/`; the preview executable is copied
to `dist/separate-tabs-preview/Cat Type.exe`. Release metadata stays at 1.0.36.
