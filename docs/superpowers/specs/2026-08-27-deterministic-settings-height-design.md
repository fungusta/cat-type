# Deterministic Settings Viewport Height

## Goal

Complete content-aware Settings sizing on native Windows by removing the
remaining dependency on delayed child-widget height updates, then publish the
verified correction as v1.0.24 without rewriting failed public tags.

## Confirmed Root Cause

The v1.0.23 width correction made the small-screen regression pass, but the
responsive-breakpoint test still opened at 688 pixels instead of 363 pixels.
A focused native Windows trace showed that the top-level window accepted each
requested height while the canvas height remained stale:

| Pass | Top-level height | Reported canvas height | Fit result |
| --- | ---: | ---: | ---: |
| Opening | 300 | 239 | 514 |
| Second | 514 | 239 | 688 (screen cap) |
| Third | 688 | 239 | 688 |

Only a full `window.update()` changed the canvas height to 627 pixels, hid the
scrollbar, switched to the wide layout, and reduced content to 302 pixels. The
correct fitted height was then 302 pixels of content plus 61 pixels of fixed
footer/chrome, or 363 pixels.

The native minimum height and scrollbar manager state were both correct. The
fault is mixing a current top-level height with a stale child viewport height
after `update_idletasks()`.

## Considered Approaches

1. **Derive viewport height from evaluated top-level geometry — selected.**
   Subtract the footer's requested height and its declared vertical packing
   padding from the current sizing pass height. This mirrors the deterministic
   width seam and avoids native event timing.
2. **Call `window.update()` inside `_center`.** This delivers child geometry,
   but it can also process input, timers, close callbacks, and other unrelated
   events while the Settings constructor is incomplete.
3. **Add more idle passes or a delay.** The trace proves the child height does
   not advance through repeated idle flushes, so additional bounded retries
   preserve the same stale input.

## Design

The footer's external vertical padding becomes a named class tuple and remains
the existing `(12, 14)` pixels. A small pure height helper will compute:

```text
viewport height = max(
    1,
    evaluated top-level height
    - footer requested height
    - 12
    - 14,
)
```

`_center` will calculate that viewport height for every content-fit pass after
the top-level geometry request is accepted. It will pass the same deterministic
viewport height into both:

- layout settling, where scrollbar visibility is decided; and
- `_content_fitted_height`, where the next top-level height is calculated.

`_sync_scrollbar_visibility` will accept an optional viewport-height override.
Sizing passes supply the deterministic value. Normal canvas/content configure
events omit it and continue using the live canvas height after the native event
loop has delivered geometry.

The existing deterministic viewport-width calculation, two inner layout
passes, four outer height passes, screen caps, minimum-size clamping, centering,
manual resizing, and post-opening behavior remain unchanged. Production code
will not call the full Tk event loop.

## Testing

Test-first coverage will verify that:

- top-level heights 300, 514, and 363 with a 35-pixel footer and `(12, 14)`
  padding produce viewport heights 239, 453, and 302;
- a stale live canvas height of 239 does not keep a scrollbar visible when a
  deterministic 453-pixel viewport fits 453 pixels of content;
- `_center` passes the deterministic viewport height through layout settling
  and fitted-height calculation;
- the existing width/scrollbar ordering test remains intact; and
- both real-Tk opening regressions still pass locally before the new native
  Windows branch gate is run.

Temporary `[DEBUG-winh]` instrumentation and diagnostic workflow changes will
not be included in the release candidate. Before tagging, the exact release
suite must pass, a whole-candidate review must report no Critical or Important
findings, and a non-release native Windows branch run must pass the focused
test. Only then may v1.0.24 be tagged and the release workflow monitored.

## Out of Scope

This change does not alter card content, footer appearance, preferred window
size, responsive breakpoint, scrollbar policy, maximization, saved geometry,
page switching, or existing public tags v1.0.19 through v1.0.23.
