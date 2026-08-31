# Cat Type sprite sheets

Every runtime sheet is a transparent `480 × 120` PNG containing four equal
`120 × 120` cells in one row. The bundled variants are gray, ginger,
charcoal, brown tabby, white, and black and white.

| Cell | X position | Runtime filename | Meaning |
| --- | ---: | --- | --- |
| 1 | 0 | `idle.png` | Both paws hovering |
| 2 | 120 | `tap-left.png` | Left paw taps |
| 3 | 240 | `tap-right.png` | Right paw taps |
| 4 | 360 | `excited.png` | Both paws tap during fast typing |

The individual runtime frames are under `tabby-frames/<variant>/`. Their alpha
is intentionally binary because Windows color-key transparency otherwise
produces a green fringe around soft edges.

## Editing it in Aseprite or Piskel

1. Open either `tabby-gray-sprite-sheet.png` or
   `tabby-ginger-sprite-sheet.png`.
2. Set the grid to `120 × 120` pixels.
3. Keep each frame's head, ears, body baseline, and overall scale in exactly
   the same position.
4. Copy the idle cell before drawing a new pose. Change only the paws and,
   when needed, the face. This prevents animation jitter.
5. Keep the background transparent.
6. Export the complete image as a `480 × 120` RGBA PNG.
7. Export each cell into the matching `tabby-frames/<variant>/` directory
   using the runtime filenames in the table above.

For a smoother animation later, add in-between frames rather than moving the
head. The most useful expansion would be eight frames: two idle, two left-tap,
two right-tap, and two rapid-typing frames.

## Generating a new cat from photos

Use image generation to regenerate the approved sprite design; do not create a
new cat by mechanically recoloring pixels. Use
`tabby-charcoal-sprite-sheet.png` as the current geometry, style, pose, and
layout reference. Use the supplied cat photo only as the coat pattern and
palette reference.

The generation prompt must preserve these invariants:

- Exactly four frames in one row: idle, tap-left, tap-right, and excited.
- The same silhouette, head and body proportions, ears, eyes, mouth, paws,
  toe-bean sizes and positions, frame spacing, and body baseline.
- The same flat 2D style, rounded black outlines, black dot eyes, black mouth,
  and pink excited tongue.
- Change only the fur pattern and colors, inner-ear color, and toe-bean color.
  Add stripes or patches only when they are visible on the reference cat.
- Render on a perfectly flat `#00ff00` chroma-key background with no shadows,
  gradients, texture, text, props, or watermark.

Generate each cat in a separate image-generation call. After generation:

1. Remove the chroma-key background with the image-generation skill's
   `remove_chroma_key.py` helper, using border auto-keying, soft matte, and
   despill.
2. Split the result into four equal vertical source cells and crop each cat to
   its alpha bounds.
3. Use one shared scale for all four frames. Fit the largest crop within
   `114 × 92` pixels so pose changes do not resize the cat.
4. Center every frame horizontally in a `120 × 120` transparent cell. Align
   the idle frame to bottom pixel 103 and the other poses to bottom pixel 105.
5. Neutralize any remaining green spill and harden alpha at threshold 96 for
   Windows color-key safety.
6. Assemble the cells into a `480 × 120` RGBA PNG and verify that all four
   cells are nonempty and alpha contains only 0 or 255.
7. Export the four cells to `tabby-frames/<variant>/` using the runtime
   filenames in the table above before adding the variant to `CAT_VARIANTS`.

## Files

- `tabby-gray-sprites-source.png` and `tabby-ginger-sprites-source.png` —
  generated chroma-key source sheets.
- `tabby-gray-sprites-alpha.png` and `tabby-ginger-sprites-alpha.png` —
  full generated sheets after background removal.
- `tabby-gray-sprite-sheet.png` and `tabby-ginger-sprite-sheet.png` —
  clean, exact-size sheets to edit.
- `tabby-frames/` — individual PNGs loaded by Cat Type.
- `scripts/rebuild_tabby_sprites.py` — removes leftover green spill, resizes
  the art, and rebuilds both runtime variants.
- `bongo-*` and `frames/` — preserved earlier sprite assets.
