# What polished metrics dashboards do

**Research date:** 2026-08-29

**Scope:** First-party product documentation, design systems, and source code only. The recommendations below are a synthesis for Cat Type; they are not claims that every cited product uses every pattern.

## Executive summary

Polished dashboards are not distinguished by more decoration. They are distinguished by a clear reading order, restrained chart furniture, precise interaction, and honest data states.

The recurring pattern is:

1. Lead with the answer: a small number of summary metrics, the active period, and—when meaningful—a comparison with the prior period.
2. Keep the data mark visually dominant: a clean line or bars, subdued gridlines and labels, and only a few annotations.
3. Make exact values inspectable: a whole-plot hover/focus target, crosshair, one active marker, and a compact tooltip.
4. Preserve context: make the selected date range explicit, mark incomplete periods, and use a visibly different treatment for comparison data.
5. Treat zero, missing, loading, error, and partial data as different states.
6. Make the chart understandable without color, precise pointer control, or hover.

Cat Type already has a sound base: three summary cards, 1d/7d/30d range controls, truthful straight-line interpolation, responsive redraw on canvas resize, a zero-data message, and a consistent zero baseline shared by line and column views. Its largest polish gaps are the always-visible point markers, non-“nice” Y-axis values, lack of exact-value interaction, no previous-period context, and no distinction between empty and unavailable data.

## Current Cat Type baseline

The current implementation in [`settings_window.py`](../../settings_window.py#L793) renders three summary cards above an Activity card. The chart itself:

- draws a 3 px straight line and a 6 px point at every bucket;
- uses exactly three horizontal rules at 0%, 50%, and 100% of the observed maximum;
- puts the maximum directly on the top edge of the plot;
- supports fixed 1d, 7d, and 30d ranges and Line/Columns views;
- redraws when the canvas resizes;
- shows an instructional message when the selected series is all zero; and
- has no hover, focus/scrub, comparison series, partial-period marker, loading state, error state, or accessible data alternative.

There is also a data-state ambiguity: [`UsageStore.load`](../../usage_metrics.py#L129) returns a new empty `UsageMetrics` object for a missing, unreadable, or malformed file. The UI therefore cannot distinguish “no activity yet” from “activity could not be loaded.”

## What leading systems do

### 1. Visual hierarchy: answer first, evidence second

Apple recommends making the data the most prominent chart element while descriptions and axes provide context without competing with it. It also recommends a useful title or summary that communicates the chart’s main message before someone examines the marks. [Apple Human Interface Guidelines: Charts](https://developer.apple.com/design/human-interface-guidelines/charts)

Stripe’s app analytics uses single-number summaries for the selected period and comparison badges against the previous period, then chooses an aggregation resolution based on the date range. This turns the chart into evidence for a headline rather than an isolated shape. [Stripe App analytics](https://docs.stripe.com/stripe-apps/analytics)

Linear combines charts, metric blocks, and tables in one dashboard and lets a chart selection open the filtered underlying issues. The top level stays scannable, while detail remains one interaction away. [Linear Dashboards](https://linear.app/docs/dashboards)

**Synthesis for Cat Type:** Keep the three summary cards, but make the Activity card’s current question explicit: for example, “Activity · Last 7 days” with exact dates in subdued copy. The range and view controls should remain secondary to the title and chart. If a period comparison is added, show one neutral delta near the current-period total rather than adding more summary cards.

### 2. Line styling: restrained by default, detail on demand

Apple describes a line as the trend carrier and recommends adding point marks when individual observations need emphasis—not as an automatic requirement for every line. [Apple Human Interface Guidelines: Charts](https://developer.apple.com/design/human-interface-guidelines/charts)

Grafana’s time-series visualization has an `Auto` point mode that displays points when data density is low, alongside `Always` and `Never`; line width, interpolation, fill, and line style are separately controlled. [Grafana Time series: Graph styles](https://grafana.com/docs/grafana/latest/visualizations/panels-visualizations/visualizations/time-series/#graph-styles-options)

Datadog labels only notable points such as peaks and troughs by default, caps automatic labels at three per series, and suppresses them when a chart has more than six series. That is a concrete example of progressive disclosure protecting readability. [Datadog Timeseries Widget](https://docs.datadoghq.com/dashboards/widgets/timeseries/)

**Synthesis for Cat Type:** Preserve the straight segments—the bucketed data does not justify a spline—but reduce the line from 3 px to about 2 px and remove persistent markers. Reveal one 6–8 px marker at the active bucket on hover or keyboard focus. For the seven-point view, tiny default points can remain an optional style choice, but the 24- and 30-bucket views should not show every dot. Avoid a heavy gradient or glow; Cat Type’s warm accent and rounded joins already provide identity.

### 3. Axes and gridlines: familiar numbers and visual quiet

Apple recommends familiar tick sequences such as 0, 5, 10 and says gridline density and visual weight should reflect how the chart is used. When users can inspect exact values interactively, fewer gridlines and lighter labels keep the data prominent. It also recommends short Y-axis labels in compact layouts to maximize plot width. [Apple Human Interface Guidelines: Charts](https://developer.apple.com/design/human-interface-guidelines/charts)

Grafana supports automatic axis bounds plus soft minimum and maximum values so mostly-flat data is not visually exaggerated, and exposes grid visibility separately from the data series. [Grafana Time series: Axis options](https://grafana.com/docs/grafana/latest/visualizations/panels-visualizations/visualizations/time-series/#axis-options)

Stripe’s LineChart API exposes “nice” domains, tick counts and formatting, and an explicit zero option rather than making callers hand-calculate arbitrary fractions. [Stripe Apps LineChart](https://docs.stripe.com/stripe-apps/components/linechart)

**Synthesis for Cat Type:** Replace `round(maximum * fraction)` with a “nice maximum” and 3–4 evenly spaced ticks (1/2/5 × powers of ten). Keep zero because the same scale serves count-based lines and columns. Add roughly 8–12% headroom so the peak does not touch the top gridline. Keep horizontal rules only, use the existing low-contrast border color, and abbreviate large labels (`1.2k`) while the tooltip shows the full integer. This also prevents duplicated ticks such as `0, 0, 1` for a maximum of 1.

### 4. Tooltip and hover/focus: make precision easy without clutter

Grafana supports single-series and all-series tooltips, configurable proximity, sorted values, and zero suppression. [Grafana Time series: Tooltip options](https://grafana.com/docs/grafana/latest/visualizations/panels-visualizations/visualizations/time-series/#tooltip-options)

Apple’s Stocks example lets people drag a vertical indicator across the entire chart to reveal values and explicitly recommends enlarging the hit target to the whole plot when marks are too small. It also says critical information must not require interaction. [Apple Human Interface Guidelines: Charts](https://developer.apple.com/design/human-interface-guidelines/charts)

Linear links graph and table interaction: hovering a graph highlights related table data, and hovering a point reveals the issue’s identifying details. [Linear Insights: Graph interactions](https://linear.app/docs/insights#graph-interactions)

Stripe’s chart component exposes a hover tooltip, while Stripe’s tooltip guidance makes the same information appear on keyboard focus and keeps tooltips free of interactive content. [Stripe Apps LineChart](https://docs.stripe.com/stripe-apps/components/linechart) and [Stripe Apps Tooltip](https://docs.stripe.com/stripe-apps/components/tooltip)

**Synthesis for Cat Type:** Use nearest-bucket selection across the full plot, not tiny point hitboxes. On hover or focus, draw a subtle vertical crosshair, one active marker, and a compact tooltip containing the full date/time and exact count. Clamp the tooltip inside the canvas. Make the canvas focusable and use Left/Right, Home, and End to move across buckets; the same tooltip should update for keyboard users.

### 5. Time ranges and comparisons: preserve the analytical question

Vercel Speed Insights combines a predefined/custom time range with device and environment filters, and changes the inspected percentile without replacing the overall view. Vercel Web Analytics also supports dragging across the chart to focus a custom period. [Vercel Speed Insights](https://vercel.com/docs/speed-insights) and [Vercel custom date ranges](https://vercel.com/changelog/filter-by-custom-date-ranges-in-web-analytics)

Stripe analytics shows current-period summaries, previous-period comparison badges, and range-dependent aggregation. [Stripe App analytics](https://docs.stripe.com/stripe-apps/analytics)

Datadog’s Compare Time supports prior period/day/week/month/custom offsets in overlay or side-by-side views. [Datadog Timeseries Widget: Compare time](https://docs.datadoghq.com/dashboards/widgets/timeseries/#compare-time)

Shopify’s first-party Polaris Viz LineChart source explicitly models comparison series, and its examples pair current and comparison data without changing the chart type. [Shopify Polaris Viz comparison example](https://github.com/Shopify/polaris-viz/blob/main/packages/polaris-viz/src/components/LineChart/stories/MultipleComparisons.stories.tsx)

**Synthesis for Cat Type:** Keep 1d/7d/30d; they fit the product and avoid a heavyweight date picker. Make the actual interval legible beneath the title. A later “Compare previous period” control would add more decision value than another chart style: use the accent solid line for current data and a muted dashed line for the previous equal-length interval, with both named in the tooltip. Do not use red/green because more typing is not inherently good or bad.

### 6. Color and semantic encoding: stable meaning, never color alone

Datadog distinguishes categorical, sequential, and diverging palettes; its semantic palette reserves meaning-bearing colors for recognized concepts such as errors. It also provides accessible color modes for color-vision deficiency, low visual acuity, and contrast sensitivity. [Datadog: Selecting colors](https://docs.datadoghq.com/dashboards/guide/widget_colors/)

Apple advises against using color alone and recommends supplementing color with shapes or patterns. [Apple Human Interface Guidelines: Charts](https://developer.apple.com/design/human-interface-guidelines/charts)

Shopify likewise requires text or iconography in addition to color for errors, warnings, and success states. [Shopify App Design: Visual design](https://shopify.dev/docs/apps/design/visual-design)

**Synthesis for Cat Type:** One series should keep one stable accent. A comparison should differ by dash and label as well as color. The selected controls should use a border, fill, or check state in addition to text color. The current `ACCENT_DARK` (`#C95238`) on `PEACH` (`#FFE4D8`) is approximately 3.65:1, below the 4.5:1 target Apple cites for small text, so selected small-label text should use `INK` or a darker accent while the accent remains in the non-text selection treatment. [Apple Accessibility: contrast](https://developer.apple.com/design/human-interface-guidelines/accessibility#Vision)

### 7. Empty, missing, loading, error, and partial states: do not collapse them

Shopify’s Polaris Viz LineChart has separate `emptyStateText` and `errorText` inputs and renders an explicit Loading/Error/Success chart state. Its loading skeleton preserves chart structure; its error state replaces the shimmer with readable error copy. [Shopify Polaris Viz LineChart source](https://github.com/Shopify/polaris-viz/blob/main/packages/polaris-viz/src/components/LineChart/LineChart.tsx) and [ChartSkeleton source](https://github.com/Shopify/polaris-viz/blob/main/packages/polaris-viz/src/components/ChartSkeleton/ChartSkeleton.tsx)

Grafana treats nulls as gaps with explicit connect-never/always/threshold behavior and separately configures the display for an empty/null field. [Grafana Time series: Connect null values](https://grafana.com/docs/grafana/latest/visualizations/panels-visualizations/visualizations/time-series/#connect-null-values)

Datadog shades and labels the last incomplete aggregation interval as partial data. [Datadog Timeseries Widget](https://docs.datadoghq.com/dashboards/widgets/timeseries/)

Atlassian defines an empty state as “no data to display” plus what the user can do next; its content guidance says to explain both the reason and the next step. [Atlassian Empty state](https://atlassian.design/components/empty-state) and [Atlassian empty-state content guidance](https://atlassian.design/foundations/content/designing-messages/empty-state)

**Synthesis for Cat Type:** Keep “Start typing to see your daily rhythm” for a genuine first-run empty state. Distinguish it from an unreadable metrics file and offer a clear recovery action or explanation. Treat unavailable buckets as gaps rather than zero; genuine “no keys in this hour” remains zero. Mark the active hour/day as “so far” in the tooltip or with a light partial background. Because Cat Type reads local data synchronously, it does not need a loading spinner today; if loading later becomes asynchronous, use a stable-height skeleton rather than a blank/jumping card.

### 8. Accessibility: provide the message and the data without hover

Apple recommends a chart title and descriptive summary, per-mark or grouped accessibility labels, keyboard navigation in a logical X-axis order, and support that does not depend solely on animation or color. [Apple Human Interface Guidelines: Charts](https://developer.apple.com/design/human-interface-guidelines/charts)

The U.S. Web Design System says the intended message should be stated in text, hover must not be required, and a screen-reader-accessible table plus a plain-language trend summary can provide equivalent access for a simple dataset. [USWDS Data visualizations](https://designsystem.digital.gov/components/data-visualizations/)

**Synthesis for Cat Type:** A Tk canvas is primarily visual, so pair it with a programmatically exposed summary such as “1,842 keystrokes, peak 482 on Thursday” and an accessible bucket list/table. Give range/view controls visible focus and meaningful group labels. Make crosshair inspection work with the keyboard, and announce the selected date and value outside the canvas as it changes. Do not rely on the peach selected fill or a dashed line alone to communicate state.

### 9. Responsiveness: preserve the plot before preserving decoration

Apple recommends maximizing plot width in compact spaces and shortening vertical-axis labels without losing meaning. [Apple Human Interface Guidelines: Charts](https://developer.apple.com/design/human-interface-guidelines/charts)

Shopify’s official Polaris Viz implementation measures its container, recalculates chart bounds, hides the legend/X-axis for small charts, disables animation for large datasets or reduced-motion users, and has a resizable chart example. [Shopify Polaris Viz ChartContainer source](https://github.com/Shopify/polaris-viz/blob/main/packages/polaris-viz/src/components/ChartContainer/ChartContainer.tsx), [LineChart source](https://github.com/Shopify/polaris-viz/blob/main/packages/polaris-viz/src/components/LineChart/Chart.tsx), and [resizable example](https://github.com/Shopify/polaris-viz/blob/main/packages/polaris-viz/src/components/LineChart/stories/ResizeableChart.stories.tsx)

**Synthesis for Cat Type:** Continue redrawing from measured canvas size, but make tick density width-aware. At narrow widths, move Range/View controls below the title, shorten Y labels, retain the first/last X label plus a few interior anchors, and reduce chart-side padding before reducing the plot itself. Never horizontally scale text or squeeze all 30 labels into the width.

## Recommended visual specification for Cat Type

This is a deliberately small target, not a full analytics suite:

- **Hierarchy:** `Activity` → muted exact interval → optional current-period total/delta → chart → controls.
- **Current series:** 2 px `ACCENT_DARK`, straight segments, rounded caps/joins, no default dots for 1d/30d.
- **Active point:** 7 px filled marker with a white 2 px ring; only one visible during hover/focus.
- **Comparison (later):** 1.5–2 px muted dashed line, explicitly labelled “Previous period.”
- **Grid:** 3–4 horizontal rules only, `BORDER`, no surrounding plot box.
- **Y-axis:** zero baseline, nice upper bound with 8–12% headroom, compact labels, full values in tooltip.
- **X-axis:** width-dependent label count; use unambiguous dates in tooltips and concise labels on-axis.
- **Interaction:** full-plot nearest-bucket hover/focus, vertical crosshair, clamped tooltip, Left/Right/Home/End navigation.
- **Motion:** a short fade/position transition at most; respect reduced-motion preferences. Never animate in a way that changes the perceived value.
- **States:** explicit empty, unavailable/error, and partial-period treatments; no loading UI until loading can actually occur.

## Prioritized checklist

### P0 — highest visible return

- [ ] Replace always-visible point markers with a single hover/focus marker and crosshair.
- [ ] Add a compact tooltip with exact bucket date/time and full keystroke count; make the whole plot the hit target.
- [ ] Replace raw half/max labels with a nice zero-based scale, 3–4 ticks, and top headroom.
- [ ] Reduce the primary line to about 2 px while retaining straight segments and rounded joins.
- [ ] Add the exact active interval near “Activity”; keep the controls visually secondary.
- [ ] Use `INK` or a darker token for small selected-control text so selection meets contrast guidance.

### P1 — comprehension and quality

- [ ] Make tick count and control layout responsive; reflow the controls below the title when narrow.
- [ ] Mark the active hour/day as an incomplete “so far” period.
- [ ] Add keyboard bucket navigation and an exposed text summary of total, peak, and interval.
- [ ] Preserve the existing honest zero-data state, but make its reason and next step explicit.
- [ ] Distinguish unreadable/unavailable metrics from a genuine all-zero dataset.

### P2 — analytical depth, after the base chart feels right

- [ ] Add an optional previous-period comparison using a labelled muted dashed line and a neutral delta.
- [ ] Add an accessible bucket table/list if the platform accessibility tree cannot expose canvas marks reliably.
- [ ] Consider a few automatic notable labels only if user testing shows that the tooltip alone hides important peaks; cap them aggressively.

## What not to copy

- Do not add gradients, glow, smoothing, or many colors solely to make the chart look “premium.” Those increase visual weight without improving the reading task.
- Do not put a label on every bucket; leading systems reveal detail selectively.
- Do not add more time ranges or a custom picker until 1d/7d/30d is shown to be insufficient.
- Do not treat more keystrokes as automatically positive with green, or fewer as negative with red.
- Do not connect genuinely missing data as if it were measured zero.
- Do not add a spinner to synchronous local data; state fidelity matters more than UI ceremony.
