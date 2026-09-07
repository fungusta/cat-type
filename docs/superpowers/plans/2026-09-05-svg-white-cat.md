# SVG White Cat Implementation Plan

> **For agentic workers:** Use subagent-driven-development for the independent settings task and review; execute the coupled artwork and overlay changes together. Steps use checkbox syntax for tracking.

**Goal:** Add a white SVG cat alongside all existing PNG cats with identical app functionality and a visual comparison.

**Architecture:** A single editable SVG supplies four programmatically posed drawings. A cached renderer supplies display images to Tk, native macOS and X11 paths. Existing PNG loading and animation rules remain available.

**Tech Stack:** Python 3.12, Tkinter, Pillow, resvg-py 0.5.0, unittest, PyInstaller.

## Global Constraints

- Keep all six existing PNG cats and their assets unchanged.
- New style identifier `white-svg`, label `White (SVG)`; original `White` stays.
- Fixed 120 by 120 SVG viewBox; no bitmap embedding, external resources or fur markings.
- Same four states, keyboard mapping, metrics, placement, hold/fade, enable and size settings.
- Render at requested size and cache; no vector parsing on each keystroke.
- Work in the current checkout on `codex/svg-white-cat`; do not publish or change saved user settings.

### Task 1: Vector artwork and image boundary

Files: `assets/vector-cats/white.svg`, `cat_artwork.py`, `tests/test_cat_artwork.py`, `requirements.txt`.

Interfaces:
```python
def frame_source_path(assets_root: Path, variant: str, name: str) -> Path: ...
def posed_svg(source: Path, name: str) -> str: ...
def vector_png(source: Path, name: str, size: int) -> bytes: ...
def load_frame(assets_root: Path, variant: str, name: str, size: int,
               *, color_key_safe: bool = False) -> Image.Image: ...
```

- [x] Add failing tests for real rendering sizes and transparency, paw-local pose changes, excited face and SVG editability; run `python -m unittest discover -s tests -p test_cat_artwork.py`.
- [x] Trace the reference with paths and grouped ellipses; transform paw groups and toggle mouth groups per pose; render using `resvg_py.svg_to_bytes(svg_string=..., width=size, height=size, skip_system_fonts=True)`.
- [x] Cache encoded vector frames with a bounded cache. Threshold alpha for the Windows color-key and binary X11 overlays. Retain PNG behavior through existing loader and Pillow for shared consumers.
- [x] Run artwork tests; render a contact sheet and inspect actual-size art.

### Task 2: Settings registration and preview

Files: `cat_settings.py`, `settings_window.py`, `tests/test_settings.py`, `tests/test_settings_window.py`.

Interfaces: add `SPRITE_CAT_VARIANTS` for the six existing values, `SVG_CAT_VARIANT = "white-svg"`, and `CAT_VARIANTS = (*SPRITE_CAT_VARIANTS, SVG_CAT_VARIANT)`; consume `cat_artwork.load_frame` as defined above.

- [x] Add failing tests that save/reload the new style and select it in the settings UI with four real preview frames.
- [x] Add the new radio choice and load its previews at 148 pixels. Keep all original labels and previews. Preserve the existing behavior when an optional icon path is absent.
- [x] Run `python -m unittest discover -s tests -p test_settings*.py`; inspect responsive layout.

### Task 3: Overlay and packaging integration

Files: `cat_type.py`, `CatType.spec`, `tests/test_overlay_rendering.py`, additional platform boundary tests as necessary.

- [x] Add failing tests for selecting the vector cat and displaying each state, resizing, fading and retaining Windows click-through. Restrict PNG file-contract tests to `SPRITE_CAT_VARIANTS`; validate vector sources separately.
- [x] Extend `_load_frames` to add SVG-derived images without changing the original PNG path. Use shared image loading for the X11 alpha mask and encoded vector bytes for NSImage on macOS, keyed by dimensions.
- [x] Change startup asset validation to use `frame_source_path`; bundle `assets/vector-cats` and the resvg native extension.
- [x] Run the complete suite, build with PyInstaller and execute the real packaged rendering smoke check.

### Task 4: Reviewable comparison and documentation

Files: `scripts/preview_svg_cat.py`, `README.md`, `docs` progress evidence.

- [x] Create a standalone comparison window using `AnimationState`, `paw_for_key` or the app's existing key mapping, and `load_frame`, with original/vector columns, pose controls and a size control.
- [x] Export the four posed SVGs for editor inspection through the comparison tool. No persistent settings, global hooks or background monitoring.
- [x] Verify the comparison actually runs; capture the real rendered output. Document launch instructions and the source-to-rendered-frame architecture accurately.
- [x] Obtain independent code/spec review, address concrete findings, record test/build evidence, and show the comparison and how to select the new cat.
