# Secret achievement rewards verification

Nine achievements each grant a new item. Neckwear, back accessories and ear
accessories combine with existing hats and glasses. Hidden achievements/items
and their contribution to totals appear only after earning them. Beta Buddy
and the purple beta bandana unlock on explicitly designated beta builds and
remain available after stable upgrades. The current local preview is beta.

## Evidence

- Existing reward baseline: 30 tests passed.
- New core, rendering and UI checks failed before their implementation.
- Final full suite: `python -m unittest discover -s tests` ran 375 tests, with
  31 platform-specific skips and no failures. The pre-existing Tcl ThemeChanged
  teardown diagnostic remains in the full-suite output.
- Real Tk tests cover hidden cards/items/counts, immediate reveal, preservation
  of pending choices, all five slots, Save/Cancel, removal and locked selection.
- Native UI captures inspected at 920×860 and 620×600, at default scaling and
  Tk scaling 2.5. All categories and long secret requirements fit horizontally;
  the existing vertical scrollbar handles the expanded wardrobe.
- 648 production-compositor renders cover nine new items, six cats, four poses,
  and three sizes. New items are visible, preserve face pixels, and stay inside
  the canvas. Combined outfits and editable SVG structure were also checked.
- Review found legacy date parsing and repeated history traversal issues. Both
  were fixed with reproductions: accepted aliases canonicalize and preserve
  counts, while live keys update cached progress from the changed bucket. Imports
  and clock rollback use full-history evaluation. The reviewer ran 7,000
  differential checks and found no remaining actionable regressions.
- A 116,800-hour-bucket benchmark measured about 0.011 ms per record/evaluation
  after initialization. A regression test rejects history traversal on live keys.
- PyInstaller Windows build passed; archive inspection verified all 15 SVG item
  sources match the checkout, all required modules/assets are present, and the
  embedded `IS_BETA_BUILD` flag is true. The numeric version remains 1.0.36.

Local screenshots, contact sheets, logs and inspection scripts are preserved in
`.debug/secret-rewards/`. The executable is copied to
`dist/secret-rewards-beta/Cat Type.exe`. No public release was published.
