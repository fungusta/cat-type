# Resizable and Scrollable Settings Window

## Problem

The settings window disables vertical resizing, enforces an 800-pixel minimum
height, and lays out all content in a non-scrollable frame. On short displays
or systems using display scaling, settings and action buttons can fall outside
the usable screen area with no way to reach them.

## Behavior

- The settings window can be resized in both dimensions.
- Its normal minimum size is 700 by 480 pixels, which keeps the existing
  two-column layout usable while allowing it to fit shorter screens. If the
  available display area is smaller, keeping the footer reachable takes
  precedence and the effective minimum is reduced to fit.
- The header and settings cards occupy a vertically scrollable content region.
- The footer remains outside that region so **Not now** and
  **Save my setup** are always visible.
- At narrow widths, the footer hides its nonessential privacy reminder before
  allowing either action button to be clipped.
- Users can scroll with the visible vertical scrollbar, a mouse wheel or
  trackpad on Windows and macOS, and wheel buttons on Linux.
- Scrolling occurs only while the pointer is over the scrollable settings
  region, so the window does not intercept wheel input elsewhere.
- When the window is wider than the content's requested width, the content
  expands to fill the viewport. When its height exceeds the viewport, the
  canvas scroll region covers the full content.

## Implementation

`SettingsWindow._build` will create a fixed footer at the bottom and a
`tk.Canvas` plus `ttk.Scrollbar` above it. The existing header and two-column
settings layout will move into a frame embedded in the canvas.

Canvas and content `<Configure>` handlers will keep the embedded frame width
aligned with the viewport and update the canvas scroll region. The settings
toplevel will handle platform-specific wheel events and scroll only when the
event originated inside the canvas's embedded content. The wheel handler will
normalize event deltas into vertical canvas scroll units and ignore input when
all content already fits.

The preferred initial geometry remains 920 by 800 for users whose screens can
accommodate it. Centering will clamp that geometry to the available screen
dimensions and the window manager's maximum size so the title bar and fixed
footer are visible on shorter displays.

## Error Handling

Wheel callbacks will tolerate platform-specific event shapes and return
without scrolling when no supported delta or wheel button is present. Because
the callbacks are bound to the settings toplevel instead of globally, they are
naturally removed when that window is destroyed and cannot alter bindings in
the rest of the application.

## Testing

Regression tests will construct the settings window when a Tk display is
available and otherwise skip cleanly. They will verify:

- both dimensions are resizable, the normal minimum is 700 by 480, and the
  effective minimum shrinks only when the available display is smaller;
- initial geometry is clamped when the screen is smaller than the preferred
  920 by 800 size;
- the footer is a sibling of, rather than a child of, the scrollable content;
- overflowing content produces a larger scroll region and can be moved with
  the scroll handler;
- the full existing unit test suite still passes.
