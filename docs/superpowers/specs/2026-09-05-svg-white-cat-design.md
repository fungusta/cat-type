# SVG white cat

The user requests steps 2 onward from the SVG workflow: redraw the existing white
cat as vector parts, derive poses, and add it as another fully functional cat for
comparison. Existing PNG artwork and behavior must remain available. Markings
such as stripes are out of scope.

## Design

Add `white-svg`, displayed as **White (SVG)** alongside **White**. Use one manually
authored `assets/vector-cats/white.svg` containing actual paths and named body,
head, ears, eyes, mouth, and paw groups. Match the reference silhouette, pink ears
and pads, rounded face, and proportions. Use a fixed 120 by 120 viewBox and baseline
across all poses. No embedded bitmap, fonts, external resources, stripes or other
fur patterns.

Programmatically pose the same drawing for idle, left tap, right tap and excited.
The tapped paw moves down and compresses; excitement taps both paws and changes
the mouth. Keep the existing four-state animation timing and input rules. This
is SVG source artwork rendered into cached images, not a new continuous animation
engine. Keeping Tk and its existing overlay preserves placement, click-through,
fading, idle hiding, keyboard-side selection, spacebar, rapid typing and metrics.

Use resvg-py 0.5.0 to render SVG directly at the requested pixel dimensions. A small
`cat_artwork.py` boundary owns vector posing, rendering, source-path selection and
image loading. The existing PNG loader remains in place for the six original
cats. Use the same vector output for the overlay, settings preview, Linux shape
mask and macOS native image. Cache vector PNG bytes in memory keyed by source,
pose and dimensions; no generated PNG runtime files are needed. Windows and X11
overlays need binary alpha to keep their opaque backing from bleeding at soft
edges and to keep the X Shape mask aligned with displayed pixels; previews and
native macOS images retain antialiasing.

Bundle the SVG and renderer in the packaged application. Add a comparison tool
that displays original White and White (SVG) together using the real animation
state and renderer, with keyboard input and explicit pose controls. It must not
modify the user's saved settings or start global input hooks. Include exportable
SVG poses so the drawing can be edited in a vector editor and visually inspected.

## Verification

- Settings save/load retains the new style and the selector previews all poses.
- Real renders have transparent corners, correct dimensions at 60/100/175 percent,
  aligned stationary body, independent paw actions and a distinct excited mouth.
- Old assets remain byte-for-byte unchanged and old rendering tests still pass.
- The real Windows overlay displays the SVG cat, stays click-through and fades;
  shared event tests cover left/right/both/fast typing, placement and enabled state.
- Platform data routes use the same SVG source; macOS/X11 behavior requiring those
  window managers is explicitly distinguished from Windows verification.
- Build and smoke-test the Windows executable with vector assets included.
- Show original and vector cats at actual and enlarged sizes and inspect the result.

## Progress

Follow-up artwork refinement requested by the user: curve the ear contours and
pink inner ears more like the original, with their bases extending behind the
head so no detached corners remain; show toe beans only on raised paws (hide
the tapping side, or both sides when excited). Preserve the idle nose and cheek
curve in the excited expression, attaching the open mouth below it with a shared
upper border rather than overlapping strokes.

Baseline: 298 unittest tests passed, 31 platform-specific skips on Windows.

Final: 318-test suite passes with 31 platform-specific skips; Windows build and packaged comparison verified. See ../../research/2026-09-05-svg-white-cat-verification.md for the requirement audit.
