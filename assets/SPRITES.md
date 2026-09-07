# Cat Type SVG artwork

Cat Type ships six editable master files in `assets/vector-cats`: `gray.svg`,
`ginger.svg`, `charcoal.svg`, `brown-tabby.svg`, `white.svg`, and
`black-white.svg`. Each uses a `120 × 120` view box. The runtime derives the
idle, left-paw, right-paw, and excited poses from the same master, so the head,
body, and baseline remain steady throughout the animation.

## Editing a cat

Open the relevant master in a vector editor and preserve its view box and these
IDs:

- `paw-left` and `paw-right` identify the paws moved for tapping poses.
- `pads-left` and `pads-right` identify the toe beans hidden while tapping.
- `mouth-idle` and `mouth-excited` identify the two expressions.
- `outline` is the continuous outer contour of the body, head, and both ears.
- `ear-inner-left` and `ear-inner-right` are the colored ear interiors. Change
  their `fill` values to recolor the ears without changing the outer contour.

Keep artwork inside the existing canvas, retain transparent areas, and edit the
fur shapes and colors directly in the master. Changes take effect after Cat
Type restarts and clears its in-memory render cache.

## Editing accessories

The six unlockable accessories are standalone SVG masters in
`assets/accessories`: `round-glasses.svg`, `sunglasses.svg`,
`star-glasses.svg`, `beanie.svg`, `party-hat.svg`, and `crown.svg`. They share
the cats' `0 0 120 120` view box, so their coordinates map directly onto every
cat master. Glasses are centered on the eyes at `(42, 62)` and `(78, 62)`;
hats sit between or across the ears. Keep all accessory artwork above y=74 so
it cannot alter the animated paws, and leave the mouth readable.

Each accessory is made from ordinary editable SVG shapes inside a group whose
ID matches its catalog ID. Preserve that group ID and the shared view box when
editing. Do not add raster images, linked images, or external references. Cat
Type reads the selected files and composes their shapes into the posed cat
before rasterizing and caching the frame.

## Checking artwork

Open the focused preview to inspect every cat at 60%, 100%, and 175% and test
the keyboard animation:

```powershell
.\.venv\Scripts\python.exe .\scripts\preview_svg_cat.py
```

Export all 24 posed SVGs plus a six-row, four-pose `preview.png` sheet without
opening a window:

```powershell
.\.venv\Scripts\python.exe .\scripts\preview_svg_cat.py --export-dir .\.debug\svg-cat-preview
```

Review each pose for stable alignment, intact outlines, readable coat markings,
and complete paws and expressions at all three supported preview sizes.
