# Achievement wardrobe verification

Implementation source: `ba89d9a`, based on `8580184`. The feature provides three
hats and three glasses, one shared outfit, permanent local achievement unlocks,
historical credit, live wardrobe progress, previews and Save/Cancel behavior.

## Automated verification

- Baseline: 322 unittest tests, 31 platform skips, passed.
- Final: 352 unittest tests, 31 platform skips, passed in 39.579 seconds.
- The existing Tcl `ThemeChanged` shutdown diagnostic appeared in both baseline
  and final full-suite runs; it produced no test failure.
- Tests cover thresholds, distinct active days, historical credit, permanent and
  idempotent unlocks, malformed data, failed writes and retries, lock/slot
  validation, settings migration, real Tk selection/preview/save/cancel/live
  unlocking, paused activity, and a slow notification that cannot block typing.
- Real Windows window captures verify the saved crown at 60%, 100% and 175%.
- Platform boundary tests verify composed macOS Retina pixels/cache invalidation
  and Linux binary transparency/shape masks. Native macOS and Linux window-manager
  behavior was not executed on this Windows host.

## Artwork and interface verification

- Inspected the six-cat accessory contact sheet and Wardrobe at 920 x 860 and
  620 x 600. Selected states, thumbnails, achievement requirements and progress
  are readable; narrow layouts scroll while Save/Cancel remain reachable.
- The packaged render matrix covers all 6 cats, 4 poses, 3 sizes (72, 120, 210),
  4 hat choices and 4 glasses choices: 1,152 renders. Every alpha bounding box
  stays strictly inside the canvas.
- That matrix initially found the party hat touching the top edge. Commit
  `af8b088` lowers the cone/pompom and adds a full-border regression for every
  accessory at all three sizes. The corrected matrix passes.

## Build and review

- PyInstaller 6.21.0 successfully built the local Windows executable.
- Inspected its archive for `achievements`, `cat_accessories` and `wardrobe_view`.
  Extracted all 12 cat/accessory SVGs and verified exact byte equality with source,
  then used those extracted files for the 1,152-render matrix.
- Independent task reviews passed progression, artwork and app/UI integration.
  Final whole-branch review found no actionable issues.
- No release version, tag, remote push or publication was requested or performed.

The local executable is copied to `dist/wardrobe-preview/Cat Type.exe`. Diagnostic
logs, screenshots and reproducible inspection scripts are in `.debug/wardrobe/`.
