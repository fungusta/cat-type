# Modern settings surface refresh

Date: 2026-11-03

## Question

Which parts of the toybox settings surface read as dated, and what current
desktop conventions can modernize them without leaving the approved
Quiet companion / Butter Sun direction?

## What looked dated

- Every pill and shelf carried a 2px warm outline plus a hard offset "rail"
  under each button, a skeuomorphic depth cue.
- Rail navigation items were full bordered buttons, so four equal-weight boxes
  competed with the content.
- Trebuchet MS / Arial Rounded MT Bold typography.
- An 18px Butter-yellow scrollbar with arrow buttons, which spent the single
  accent on chrome.
- Every state change (hover, toggle, focus) snapped instantly.
- Slider thumbs and tracks drawn with non-anti-aliased canvas primitives.

## Findings

- Motion: WinUI's standard timings are about 83ms (faster), 167ms (fast) and
  250ms (normal), and content entering a state uses a decelerating
  (fast-out, slow-in) curve.
  [Timing and easing](https://learn.microsoft.com/en-us/windows/apps/design/motion/timing-and-easing),
  [Fluent 2 motion](https://fluent2.microsoft.design/motion)
- Typography: Windows 11 uses Segoe UI Variable with a ramp of caption 12px,
  body 14px, subtitle 16/20px semibold and title 24px+ semibold, and
  recommends a single family across an app.
  [Typography in Windows 11](https://learn.microsoft.com/en-us/windows/apps/design/signature-experiences/typography),
  [Fluent 2 typography](https://fluent2.microsoft.design/typography)
- Surfaces: recent product refreshes moved from heavy shadows and thick
  outlines toward hairline borders, keeping soft elevation for accents rather
  than as a whole-app system.
  [Card shadows replaced with borders](https://www.pravinkumar.co/blog/webflow-card-shadows-replaced-with-borders-2026),
  [What is soft UI design](https://vp0.com/blogs/what-is-soft-ui-design)

## Decisions

- One hairline border plus a faint, blurred ambient shadow for pills and
  shelves. Hover raises the shadow and tints the face toward Butter. Press
  keeps the existing 1px shift.
- Rail navigation becomes a "ghost" list: flush until hovered, Butter pill when
  selected.
- Segoe UI Variable Display/Text (semibold optical families) on Windows 11,
  with Avenir Next and common Linux UI families as fallbacks. Point sizes are
  unchanged to avoid layout churn.
- Hover tint/lift eases over 120ms and toggles glide over 167ms with a cubic
  ease-out. Windows' "Animation effects" setting
  (`SPI_GETCLIENTAREAANIMATION`) disables both.
- Slim neutral, arrowless scrollbar (darkens to ink on hover, drag or focus).
- Sliders and switches are rasterized at 4x for anti-aliasing. Switch focus
  uses the Butter + ink ring around the switch rather than a rectangle around
  the row.
- Windows 11 DWM rounded window corners and a warm border color for the
  client-drawn frame. Earlier Windows versions ignore the request.

## Validation scope

Native visual checks were taken on Windows 11 at 96 DPI. macOS and Linux
fallback fonts and the DWM-free frame were not visually verified.
