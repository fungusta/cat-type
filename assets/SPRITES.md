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

Keep artwork inside the existing canvas, retain transparent areas, and edit the
fur shapes and colors directly in the master. Changes take effect after Cat
Type restarts and clears its in-memory render cache.

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
