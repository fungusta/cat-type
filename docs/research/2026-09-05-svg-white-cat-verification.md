# SVG white cat verification

## Follow-up artwork refinement

The subsequent nose/ear correction restores the original nose-and-cheek curve
in the excited expression. The pink opening shares that curve as its upper
border, with only one visible stroke there. Both ear bases now extend beneath
the head fill so they meet its contour cleanly. Inspected normal-size exports
and enlarged ear/mouth renders; scoped independent review passed. All 29
relevant artwork, platform-surface, overlay and comparison tests pass in 4.503
seconds (`.debug/svg-nose-ear-tests.log`). The earlier refinement history follows.

The user requested rounder ears, hidden toe beans during taps/excitement, and an
excited mouth without overlapping strokes. The SVG now has curved outer and
inner ear contours, named pad groups hidden on lowered paws, and a single filled
excited mouth outline. Raised paws retain their beans.

The new pixel-based regression first failed for left tap, right tap and excited,
then passed after implementing pad visibility. The full updated suite ran 319
tests with 31 platform-specific skips and no failures in 21.718 seconds; log:
`.debug/svg-refinement-tests.log`. PyInstaller rebuild succeeded; log:
`.debug/svg-refinement-build.log`. Inspected `.debug/svg-cat-preview/refined-poses.png`
and regenerated all exported SVG poses. Independent scoped review found no defects.
The original PNG artwork remains unchanged. The following sections record the
initial implementation verification.

Verified on Windows on 2026-09-05, on local branch `codex/svg-white-cat`.

## Requirement evidence

| Requirement | Evidence |
| --- | --- |
| Recreate the existing white cat as editable vector parts | `assets/vector-cats/white.svg` contains paths and named body, head, ears, eyes, mouth and paw groups; no embedded images or fur markings. Inspected against all four original white PNGs. |
| Derive consistent poses from one drawing | `cat_artwork.posed_svg` changes paw transforms and mouth visibility. Artwork tests verify independent paws, stationary upper body, and the excited face. |
| Keep existing cats available | `SPRITE_CAT_VARIANTS` retains the six original styles; `white-svg` adds a seventh choice. No changes to original PNG assets; original loading and sprite tests pass. |
| Preserve all app reactions and settings | Same `AnimationState`, input classification, metrics, visibility, anchoring and settings controller. The new choice saves/reloads and previews all four poses. Windows integration exercises left/right/both/idle, fading, click-through flags and supported size boundaries. |
| Render vectors at selected size | Renderer tests exercise 72, 120, 148 and 210 pixels. The encoded-frame cache is bounded; runtime assets remain SVG. |
| Use correct platform image routes | Windows real overlay tests pass. macOS native data tests verify rendered bytes at backing resolution and resize cache keys. X11 data tests reconstruct the complete shape mask and match binary-alpha display pixels. |
| Show the difference | `scripts/preview_svg_cat.py` compares both cats using the real animation state and normalized local key classification. Controls cover all poses and 60/100/175 percent sizes. |
| Editable pose exports | `--export-dir .debug/svg-cat-preview` generated four posed SVGs and the labelled actual-size `comparison.png`; enlarged output was also inspected. |
| Packaged application contains and renders SVG | PyInstaller build succeeded. The actual new executable launched with `--compare-cats`, displayed both cats, and remained open; captured its window for visual inspection. |

## Commands and results

- `.venv\Scripts\python.exe -m unittest discover -s tests`: 318 tests, 31 platform-specific skips, no failures; 22.984 seconds. Log: `.debug/svg-final-tests.log`.
- `.venv\Scripts\python.exe -m PyInstaller --noconfirm --distpath dist\svg-white-cat --workpath build\svg-white-cat CatType.spec`: exit 0. Log: `.debug/svg-build.log`. Output: `dist/svg-white-cat/Cat Type.exe`.
- `.venv\Scripts\python.exe scripts\preview_svg_cat.py --export-dir .debug\svg-cat-preview`: exit 0; four SVG poses plus contact sheet.
- Actual packaged `--compare-cats` launch: visible 464 by 399 window containing both rendered cats and controls. Local report: `.debug/svg-cat-preview/packaged-smoke.json`; screenshot: `packaged-comparison.png` in that directory.
- `git diff --check`: clean. `git diff --name-only -- assets/tabby-frames`: empty.
- Independent code/spec review passed after fixing the Tk key-name adapter and matching the X11 binary-alpha image/mask. Local report: `.debug/svg-review-report.md`.

## Scope of verification

Native Windows overlay rendering and the packaged comparison were exercised.
Native macOS and X11 window managers were unavailable on this host; their data
boundaries were tested with real rendered SVG images and small native-API
adapters, not actual window-manager integration.

The installed Cat Type process remained running. The comparison uses only local
focused input and does not load or save the user's settings, start global hooks,
or acquire the normal overlay's single-instance mutex. No release was published.
