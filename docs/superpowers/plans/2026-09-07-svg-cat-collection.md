# SVG cat collection

Extend the approved white SVG to gray, ginger, charcoal, brown tabby, and black-and-white cats, using the existing PNGs as color and marking references.

## Global constraints

- Preserve the approved white SVG, rounded ears, joined ear bases, and nose-connected excited mouth.
- Every SVG uses the existing four poses. Toe beans appear only on raised paws.
- Keep all six PNG styles and their saved identifiers. Add matching `-svg` styles; preserve `white-svg` settings.
- Render every SVG through the existing renderer on Windows, macOS, Linux, settings previews, and comparison previews.
- Keep the installed application untouched. Build a separate executable and compare original/SVG pairs without changing user settings.

## Task 1: Artwork and rendering

- [x] Draw five standalone editable masters in `assets/vector-cats`, matching each original's coat and markings.
- [x] Add `SVG_CAT_VARIANTS = tuple(f"{variant}-svg" for variant in SPRITE_CAT_VARIANTS)`; retain `SVG_CAT_VARIANT = "white-svg"` for compatibility. Include all originals and vectors in `CAT_VARIANTS`.
- [x] Generalize vector path selection, frame loading, macOS native images, and X11 masks to the full SVG collection.
- [x] Verify real renders, independent paws, pads, face, alpha, saved styles, and platform routing.

## Task 2: Settings and comparison

Owned files: `settings_window.py`, `scripts/preview_svg_cat.py`, `tests/test_settings_window.py`, `tests/test_cat_comparison.py`, and SVG-related README prose.

- [x] Offer all six SVG styles in settings and load their animated previews. Retain original styles and responsive layout.
- [x] Add a family selector to the comparison window; default to white to preserve the previous comparison workflow. Each selection shows original PNG and matching SVG at the chosen pose/size. Preserve keyboard reactions and timer behavior.
- [x] Generalize export to produce every family's four posed SVGs and a complete original/SVG comparison sheet. Preserve `comparison.png` output and existing white SVG filenames.
- [x] Update relevant tests and README. Use `SPRITE_CAT_VARIANTS` / `SVG_CAT_VARIANTS` from `cat_settings.py`, which Task 1 owns. No changes outside owned files, no commits, no settings writes, and no builds. Coordinate GUI tests with the main agent.

## Task 3: Review and delivery

- [x] Inspect every original/SVG pair and pose at normal/enlarged size.
- [x] Review integration, run appropriate suite, build isolated executable, inspect packaged assets, and capture packaged comparison UI.
- [x] Deliver preview and editable sources with concise verification results.
