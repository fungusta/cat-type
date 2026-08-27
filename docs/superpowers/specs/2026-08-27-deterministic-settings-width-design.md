# Deterministic Settings Width During Opening

## Goal

Make content-aware Settings sizing deterministic on Windows, Linux, and macOS,
then publish the correction as v1.0.23 without rewriting the existing failed
release tags.

## Root Cause

The current centering loop requests a new top-level width and calls
`update_idletasks()`, then reads `scroll_canvas.winfo_width()` to choose the
responsive layout. Native Windows applies the top-level geometry before it
delivers the canvas `Configure` event, so the canvas still reports its previous
width during every bounded sizing pass. The loop consequently measures the old
wide or narrow layout and selects the wrong height.

The repeated Windows release failures prove this boundary: after a requested
620-pixel opening, the final content is 1,274 pixels tall, while every in-loop
measurement sees the stale 701-pixel layout. A breakpoint case likewise keeps
the stale 688-pixel narrow height instead of settling at 363 pixels wide-layout
height.

## Considered Approaches

1. **Derive the viewport from the target window width — selected.** Pass the
   requested top-level width into layout settling and subtract the packed
   scrollbar's requested width. This uses inputs controlled by the sizing loop
   and avoids native event timing.
2. **Run the full Tk event loop with `update()`.** This would deliver native
   `Configure` events, but it can process unrelated input, timers, and close
   callbacks while the constructor is still running.
3. **Relax the Windows assertions.** This would unblock packaging but preserve
   the incorrect production opening size, so it does not meet the goal.

## Design

`_center` remains the sole owner of initial top-level geometry. For every
bounded content-fit pass it will provide its chosen `width` to
`_settle_content_layout(width)`.

Each layout-settling pass will:

1. check whether the vertical scrollbar is currently packed;
2. derive the canvas viewport width as the target window width minus the
   scrollbar's requested width when visible;
3. set the embedded scroll-content width and responsive layout from that
   derived width;
4. flush Tk geometry work, synchronize scrollbar visibility, and flush again;
5. repeat once so a scrollbar visibility transition is reflected before
   height measurement.

The calculation is clamped to at least one pixel. The existing four-pass
content-height bound, screen caps, centering, resizability, and post-opening
behavior remain unchanged.

## Testing

The regression test will fail first against the current no-argument helper. It
will then verify that a target width of 855 pixels produces a 839-pixel viewport
while a 16-pixel scrollbar is packed and an 855-pixel viewport after it is
hidden. It will continue to enforce the exact ordering of layout updates, idle
flushes, and scrollbar synchronization on both passes.

The two real-Tk opening tests remain the cross-platform outcome checks. Before
tagging, the exact release test command must pass locally, code review must have
no Critical or Important findings, and the v1.0.23 Windows job must pass before
waiting for the remaining packages and published release assets.

## Out of Scope

This change does not alter the preferred size, responsive breakpoint, card
layout, scrollbar policy, window maximization, saved geometry, or page-switch
behavior.
