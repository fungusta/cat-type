# More Achievements Implementation Plan

**Goal:** Add 15 achievement/item pairs to the existing collection.

**Architecture:** Add data to `cat_accessories.py` and standalone vectors to
`assets/accessories`. Existing tracking, persistence, rendering, and settings
views consume the catalog without new metrics or schema changes.

**Tech stack:** Python, Tkinter, SVG, resvg, Pillow, unittest.

## Constraints

- Preserve existing reward IDs, requirements, and beta eligibility.
- Use existing aggregate history and permanent unlocks; never auto-equip.
- Keep the three new secret rewards hidden until earned.
- Preserve face readability, moving paws, and transparent canvas margins.

## Tasks

- [x] Update existing achievement and wardrobe expectations for the expanded
  catalog, including the 250-key starter and 22 public rewards. Verify they fail
  against the old catalog before adding entries.
- [x] Add the 15 catalog entries specified in the design and corresponding
  editable vectors. Run the achievement and accessory artwork suites.
- [x] Verify unlocking, persistence, all five slots, and small settings windows
  with wardrobe and integration tests. Inspect rendered contact sheets.
- [x] Document the public milestones and slot-specific SVG editing rules.
- [x] Run the full test suite and diff checks, request an independent review,
  and record verification results.

## Commands

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_achievements.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_accessory_artwork.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_wardrobe*.py' -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
git diff --check
```
