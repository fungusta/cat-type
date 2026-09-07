# SVG cat collection verification

The approved white SVG now has five companions: gray tabby, ginger tabby,
charcoal, brown tabby, and black & white. Each has a standalone editable master
in `assets/vector-cats`. The white master was preserved during this extension.

All six SVG styles appear in settings alongside the six original PNG styles.
The comparison window defaults to white and switches original/SVG pairs through
its family selector. Export produces 24 posed SVGs and a complete contact sheet.

## Visual checks

- Inspected all 24 SVG poses beside their original PNG counterparts at 220 px.
- Inspected idle/excited SVG pairs at 240 px and the packaged comparison at 100%.
- Checked rounded ear joins, clipped coat markings, stationary head during taps,
  independent paws, hidden toe beans on lowered paws, and the retained nose with
  the attached excited mouth.

## Automated and packaged checks

`.venv/Scripts/python.exe -m unittest discover -s tests` ran 323 tests in
29.245 seconds: 292 passed and 31 platform-specific tests were skipped.
The existing Tk `ThemeChanged` teardown diagnostic appeared without a test
failure.

Coverage includes all six SVGs at multiple sizes, original style compatibility,
saved SVG styles, toe-bean visibility, independent paws, actual Windows overlay
captures, macOS backing-resolution image data, X11 alpha masks, settings previews,
narrow-window access, family selection preserving pose/size, and full export.
macOS/X11 native window-manager behavior was not exercised on this Windows host;
their rendering boundaries were tested with platform adapters.

The separate PyInstaller build succeeds at
`dist/svg-cat-collection/Cat Type.exe`. Its comparison window opened at 464 × 434.
All six SVG masters extracted from the executable match the source bytes.
`dist/svg-cat-collection/Editable SVG cats.zip` contains six masters and 24 posed
SVGs, with no corrupt entries.

Preview artifacts are under `.debug/svg-cat-preview`: `svg-collection.png`,
`all-poses-large.png`, `comparison.png`, and `packaged-comparison.png`.
The installed application and saved user settings were not modified.
