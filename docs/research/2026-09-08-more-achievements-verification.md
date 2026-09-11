# More achievements and items verification

Date: 2026-09-08. Platform: Windows. Baseline: `e76183a`.

## Result

Added 15 achievement/item pairs: 12 public rewards and three secret discoveries.
The catalog now has 30 unique items and achievement names, with 22 rewards
visible before any secrets are earned. All 15 previous reward definitions,
including beta eligibility, remain unchanged.

The expansion adds catalog data and 15 standalone SVGs. The collar refinement
below also adds opt-in silhouette clipping to the shared renderer. Tracking,
metrics, save schemas, and packaging continue using their existing paths.
Public progression is ordered by total keystrokes, then active days.

## Automated verification

- Achievement suite: 19 tests passed. Before implementation, four updated
  expectations failed against the original catalog as expected.
- Accessory artwork suite: 12 tests passed.
- Wardrobe and integration suites: 22 tests passed, including secret visibility,
  permanent unlocks, automatic saving, and narrow settings windows.
- Full suite: 383 tests run in 200.090 seconds; 352 passed and 31 skipped for
  Linux/macOS-specific behavior unavailable on Windows. Exit code 0.
- `git diff --check`: passed.

The full suite command was:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Additional temporary verification exercised each new reward immediately below
its threshold, then crossed that threshold through a recorded key. Each reward
unlocked once, became visible, persisted after restarting without history, and
round-tripped through equipped settings. Day fixtures used nonconsecutive days;
secret hourly fixtures used the existing local-hour rules. An AST comparison
against the baseline confirmed every previous catalog definition is unchanged.

## Visual verification

Rendered all 15 new items across six cats, four poses, and three sizes
(72, 120, and 210 pixels): 1,080 renders passed. Every item changed the image,
stayed inside transparent canvas margins, and preserved the relevant face or
paw region. Mixed outfits exercised all five slots together.

Inspected public, secret, and mixed-outfit contact sheets. Corrected opaque
underlying lens fills to expose the eyes through the new glasses, and enlarged
the visible portions of the dragon wings before the final checks.

Local preview artifacts and the temporary verification scripts are under
`.debug/more-achievements/`, which is ignored by Git. They do not modify real
user settings or achievement history.

An independent read-only review checked the catalog, all new SVGs, documentation,
tests, integration paths, and contact sheets. No actionable defects were found.

## Collar fit follow-up

User feedback identified that the bell collar ended midway across the chest,
and extending a fixed band produced protruding side corners. The final band
curves around the neck and uses `data-clip-to-body="true"` to follow each cat's
actual outline. Smooth shading replaces the angular side panels. Clipping
applies only to the band; the bell hangs freely and paws stay in front.

A regression test checks that the band reaches both neck edges without adding
opaque corners outside existing silhouette coverage across all six cats, four
poses, and three sizes. It failed on all 72 combinations before the correction
and passes with fitting. Removing fitting from a rendered SVG reproduces the
protrusion. The check allows compositing within existing antialiased edge pixels.

Follow-up validation: 13 accessory artwork tests, 8 cat artwork tests, 4 platform
surface tests, and 22 Wardrobe/integration tests passed (47 total). All-cat and
mixed-outfit previews were refreshed and inspected. Independent review found
no actionable defects. `git diff --check` passed.

Local comparison: `.debug/more-achievements/collar-edge-comparison.png`.

## Cape fit follow-up

User feedback identified that the original full-width capes hung below the
cropped cat and looked detached. Reworked both adventure and royal capes into
short shoulder panels. Their back sections end at the cat's crop line, while
foreground sections add a visible neck fastening and remain behind the paws.
The renderer now extracts marked `data-render-layer="front"` sections from
nested accessory groups and inserts them immediately before the paw layer.

Added a regression test that rejects opaque cape pixels beneath the existing
crop line and requires a visible fastening below the mouth. The test failed
for both original capes, then passed after the asset and layer changes. Focused
validation passed: 14 accessory-artwork tests, 8 cat-artwork tests, 4 platform
surface tests, and 22 Wardrobe/integration tests. Final cape renders were
inspected on all six cats.
