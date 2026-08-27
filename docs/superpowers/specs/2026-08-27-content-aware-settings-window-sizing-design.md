# Content-Aware Settings Window Sizing

## Goal

Open the Settings window tall enough to avoid unnecessary vertical scrolling
when the display has room, while preserving scrolling and reachable footer
actions on smaller screens.

## Confirmed Root Cause

The window requests a fixed initial size of 920 by 800 pixels. Its centering
logic clamps that size when the display is smaller, but never grows the height
when rendered content overflows the scroll viewport and additional screen
height is available.

A real Tk reproduction on a 1920 by 1200 display with scaled UI rendered 775
pixels of content in a 724-pixel viewport. The window still opened at 800
pixels even though an 851-pixel window would fit within the 1120-pixel usable
height.

## Opening Behavior

The normal preferred width remains 920 pixels. The normal opening height starts
at 800 pixels, then grows only by the amount of measured vertical overflow.
The resulting height is capped by the existing usable-screen and window-manager
limits.

This produces three outcomes:

- content that already fits continues to open at 920 by 800;
- overflowing content opens just tall enough to fit when the display permits;
- content that cannot fit within the usable display opens at the maximum safe
  height and remains scrollable.

The window must not automatically maximize or occupy unused space beyond what
its content needs.

## Sizing Sequence

Centering will remain the single owner of initial geometry. It will:

1. calculate the usable width and height from the screen, configured margins,
   and window-manager maximum size;
2. apply the clamped target width before measuring content, so the responsive
   one-column or two-column layout is final;
3. let Tk finish pending layout work;
4. measure the scroll content height and current scroll viewport height;
5. add only positive overflow to the current opening height;
6. cap the result to the usable height, update the effective minimum size, and
   center the final geometry.

A small pure height-calculation helper will keep the content-fit rule directly
testable. Real Tk tests will cover the timing and responsive-layout integration.

## Compatibility

Manual resizing, minimum dimensions, scroll-wheel behavior, scrollbar
visibility, the fixed footer, page switching, Metrics behavior, settings
persistence, and screen-edge margins remain unchanged. Switching pages after
opening will not resize the window.

## Testing

Automated coverage will verify that:

- an 800-pixel opening grows by the exact measured overflow when space exists;
- the calculated height never exceeds the usable display height;
- content that already fits remains at the preferred 800-pixel height;
- a scaled wide layout opens without an unnecessary scrollbar when the display
  has room;
- a narrow tall display uses the available height and retains scrolling only
  when stacked content still cannot fit; and
- the existing small-screen minimum-size and centering behavior remains valid.

## Out of Scope

This change does not alter window width preferences, remember a user-resized
window, maximize the window, reorganize cards, change responsive breakpoints,
or resize dynamically when Settings and Metrics are switched.
