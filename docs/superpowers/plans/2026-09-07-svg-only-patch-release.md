# SVG-only patch release implementation plan

> **For agentic workers:** Use subagent-driven-development for the bounded UI task and final review. The user explicitly authorized replacing PNG animations and publishing a new patch.

**Goal:** Publish Cat Type v1.0.34 with the six approved SVG cats as its only animation artwork.

**Architecture:** Keep the six original saved cat identifiers, route all poses through the shared SVG renderer, and normalize temporary `-svg` selections back to their corresponding original identifiers. Remove raster animation assets and loaders, retain native application icons, and build those icons from the SVG source.

**Tech stack:** Python 3.12, Tk, resvg-py, unittest, PyInstaller, Inno Setup, GitHub Actions.

## Global constraints

- Preserve the approved six SVG masters, ear joins, nose-connected excited mouth, and toe beans only on raised paws.
- Canonical `CAT_VARIANTS` is `("gray", "ginger", "charcoal", "brown-tabby", "white", "black-white")`; all are SVG-backed. Remove `SPRITE_CAT_VARIANTS`, `SVG_CAT_VARIANT`, and `SVG_CAT_VARIANTS` from production.
- Existing canonical saved selections remain unchanged; each temporary `<cat>-svg` saved selection normalizes to `<cat>`. Preserve other settings and keyboard/placement/fade behavior.
- No PNG animation assets or fallback loaders remain in the runtime or release bundle. Native ICO/ICNS/PNG application icons remain supported.
- The user authorized publication; verify concrete release artifacts before publishing. Do not move or reuse a published tag. Keep the installed application and live user settings untouched.

## Task 1: Runtime, migration, assets, and packaging

- [ ] Update settings and migration tests first; verify failures before switching the canonical registry and renderer.
- [ ] Make `frame_source_path` return `assets/vector-cats/<variant>.svg`, reject unknown cats, and render every frame through resvg. Export `BASE_SIZE = 120` from `cat_artwork.py`.
- [ ] Replace PNG branches in Tk, macOS, and X11 surfaces; preserve binary alpha where required and macOS backing-pixel resolution.
- [ ] Remove tracked raster animation assets and obsolete rebuild scripts. Generate native icons from the gray SVG. Bundle only vector animation masters.
- [ ] Extend the bundled asset checker to require all six masters and reject obsolete raster animation entries; include renderer/preview/platform tests in both CI workflows.
- [ ] Update runtime/asset/platform/migration tests and verify real renders, including Windows capture.

## Task 2: SVG-only settings and preview

Owned files: `settings_window.py`, `scripts/preview_svg_cat.py`, `tests/test_settings_window.py`, `tests/test_cat_comparison.py`, `README.md`, `assets/SPRITES.md`.

- [ ] Settings displays six ordinary cat labels plus Mix it up; remove duplicated `(SVG)` choices and PNG preview loading. Iterate `CAT_VARIANTS`, all rendered by `load_frame`.
- [ ] Replace the original/PNG comparison with a standalone SVG preview (`PreviewWindow`, `run_preview`) in the existing script. Default to White, offer all six cats, retain pose/size controls and focused keyboard behavior. A single cat display is sufficient; no PNG reads.
- [ ] Export all 24 posed SVGs as `<cat>-<pose>.svg` plus `preview.png`, a six-row/four-pose sheet. Use `CAT_VARIANTS` and `BASE_SIZE` from shared modules. The parent owns the application `--preview-cats` flag that calls `run_preview`.
- [ ] Adapt focused tests to actual SVG image changes, six choices, preview interaction, and SVG export. Update README and artwork editing guide to the shipped SVG workflow. Use version v1.0.34 where README has a live release example.
- [ ] No commits/builds/settings writes. Coordinate GUI tests with the parent. Report commands, outcomes, and any concerns.

## Task 3: Verify and publish v1.0.34

- [ ] Synchronize runtime, Windows/macOS/installer metadata and release test markers at 1.0.34.
- [ ] Run full local suite, metadata checker, actual frozen Windows smoke, SVG bundle verification, and a final integrated review.
- [ ] Commit reviewed work, push to main without force, and dispatch a five-platform Release dry run. Wait for normal CI and all dry-run packages before tagging the exact tested commit.
- [ ] Push annotated v1.0.34 once, monitor tag release, publish concise release notes, then audit five platform packages plus SHA256SUMS.txt, tag commit, latest status, and clean working tree.
