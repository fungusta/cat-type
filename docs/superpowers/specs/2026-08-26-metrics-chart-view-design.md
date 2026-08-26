# Metrics Chart View Selection

## Problem

The Metrics page currently renders hourly and seven-day activity with
Tkinter's smoothed canvas line. The recorded point markers represent exact
hourly or daily aggregate counts, but the spline can bend between and visually
away from those points. That makes the chart look polished at the cost of
misrepresenting the underlying buckets. The 30-day view already avoids
smoothing, so the chart also behaves inconsistently across ranges.

Users should be able to choose between the familiar line treatment and a
column treatment without changing the selected time range. Line remains the
default, and Cat Type remembers the saved view preference.

## User Experience

The existing Activity card keeps one chart and gains two independent,
labelled segmented controls in its header:

- **Range:** `1d`, `7d`, and `30d`, retaining the existing seven-day initial
  selection.
- **View:** `Line` and `Columns`, with `Line` selected for a new or invalid
  configuration.

Both controls use the card's existing peach selected state, focus treatment,
and keyboard-operable radiobutton behavior. At narrower supported window
widths, the controls may move below the Activity title while remaining in the
same card. The summary cards, chart axes, range labels, privacy note, and empty
state copy remain unchanged.

Changing either control redraws the chart immediately. The view choice applies
to every range: any of the 1-day, 7-day, and 30-day series can be shown as a
line or as columns. Changing the range does not reset the selected view.

Changing the view also persists that display preference immediately. It does
not save any unrelated edits that may be pending on the Settings page. Closing
the window without using **Save changes** therefore keeps the chosen chart
view while continuing to discard other unsaved setting edits. On the next
launch or Settings-window opening, the saved view is restored. The range
selection is not added to persisted settings and continues to start at seven
days.

## Chart Treatments

### Line

The line renderer connects adjacent recorded positions using straight
segments. It never enables Tkinter canvas smoothing. A point marker remains at
every hourly or daily bucket, and every segment endpoint intersects the center
of its corresponding marker. Existing line color, width, rounded caps, rounded
joins, scaling, grid lines, axes, and labels remain in place.

This treatment intentionally presents a trend between adjacent aggregate
buckets. It does not claim that an interpolated point is another recorded
measurement; the visible markers identify the exact observations.

### Columns

The column renderer draws one vertical column for each recorded bucket: 24
hourly columns in the 1-day range, 7 daily columns in the 7-day range, and 30
daily columns in the 30-day range. Each column is centered in an equal-width
bucket and extends from the shared zero baseline to the scaled count. Column
width is derived from the bucket width and capped so sparse ranges do not
produce oversized marks. Rounded caps and the existing accent color keep the
treatment consistent with Cat Type's visual language.

Zero values have no visible column. Labels align with bucket centers rather
than the line chart's endpoint positions. The y-axis maximum and grid lines
use the same calculation as the line view, so switching views does not change
the perceived scale for the same range and data.

## State and Components

`AppSettings` gains a `metrics_view` string with valid values `line` and
`columns`; its default is `line`. Normalization replaces any other value with
the default. The existing settings store can load older files without the
field and will include the normalized value on the next save.

`SettingsWindow` initializes a `StringVar` from `settings.metrics_view` and
builds the View segmented control next to the existing Range control. A small
view-change handler refreshes selected button colors, requests a redraw, and
passes only the normalized view value to a narrow persistence callback. The
handler does not construct or save the window's other editable values. `_save`
also includes the selected view when constructing the normalized `AppSettings`
passed to the existing save callback, preventing a later settings save from
reverting the preference.

`CatTypeApp` supplies the view-persistence callback. It creates an updated
`AppSettings` from the application's last saved settings plus the new view,
then writes that normalized value through `SettingsStore`. This isolates the
immediate preference update from any unsaved controls in `SettingsWindow`.

The chart code retains one canvas and one data-selection path. After the
selected range produces `values` and `labels`, rendering branches only at the
mark layer:

1. Shared code clears the canvas, selects hourly or daily data, computes the
   y scale, and draws grid lines and y-axis values.
2. The line renderer calculates endpoint positions and draws straight
   segments plus point markers.
3. The column renderer calculates bucket-center positions and draws bars.
4. Shared code draws range labels and the existing empty message when all
   values are zero.

This keeps data meaning, scaling, labelling, and empty-state behavior
independent from the chosen visual treatment.

## Error Handling and Compatibility

- Missing or unrecognized `metrics_view` values normalize to `line`, so older
  and manually edited settings files remain safe.
- A failed settings-file load already falls back to `AppSettings()` and
  therefore to the line view.
- View persistence follows the existing settings-store write behavior. The
  in-memory selection and chart redraw still occur before persistence, so the
  current window remains usable if a write cannot be retained for a later
  launch.
- Empty series retain the current range-specific message in either view and
  do not draw line, point, or column marks.
- Canvas width and height continue to use the existing minimums, preventing
  zero-sized geometry during initial layout and resize events.
- Live usage updates and canvas resize events redraw using the currently
  selected range and view.
- The persisted usage metrics format and its privacy properties do not
  change. No key names, typed text, application names, or window titles are
  introduced.

## Testing

Automated coverage will verify:

- `AppSettings` defaults `metrics_view` to `line`, preserves `columns`, and
  normalizes invalid values to `line`;
- settings storage round-trips the chosen view and loads pre-feature settings
  as line view;
- the Metrics page exposes independent controls for all three ranges and both
  views, initializes the saved view, and updates selected styling;
- switching views redraws without changing the selected range, while changing
  ranges does not reset the view;
- switching views persists only `metrics_view`, does not capture unrelated
  unsaved controls, and reopening restores the preference;
- the existing **Save changes** path includes the selected view and does not
  revert an immediately saved preference;
- line geometry uses the exact recorded positions with smoothing disabled;
- column geometry centers 24, 7, and 30 buckets correctly and keeps them on a
  shared zero baseline;
- line and column renderers use the same y scale for identical data;
- both views retain range labels, empty-state messages, resize behavior, and
  live metric refreshes; and
- the existing settings, metrics, behavior, and full unit test suites remain
  green.

## Out of Scope

This refinement does not add hover tooltips, per-point value labels, new date
ranges, persisted range selection, metric export, new metrics, or changes to
usage collection. It also does not introduce a third chart style or choose a
different view automatically for different ranges.
