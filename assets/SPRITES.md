# Cat Type sprite sheets

The runtime sheets are `tabby-gray-sprite-sheet.png` and
`tabby-ginger-sprite-sheet.png`. Each is a transparent `480 × 120` PNG
containing four equal `120 × 120` cells in one row:

| Cell | X position | Runtime filename | Meaning |
| --- | ---: | --- | --- |
| 1 | 0 | `idle.png` | Both paws hovering |
| 2 | 120 | `tap-left.png` | Left paw taps |
| 3 | 240 | `tap-right.png` | Right paw taps |
| 4 | 360 | `excited.png` | Both paws tap during fast typing |

The individual runtime frames are under `tabby-frames/gray/` and
`tabby-frames/ginger/`. Their alpha is intentionally binary because Windows
color-key transparency otherwise produces a green fringe around soft edges.

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
