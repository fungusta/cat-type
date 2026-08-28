# Deterministic Small-Screen Layout Test Design

## Problem

`test_opening_measures_after_reducing_minimum_for_small_screen` fixes the
reported screen width but inherits the host's screen height and window-manager
maximum size. On a sufficiently tall display, the settings window grows until
its content exactly fits, so production correctly hides the scrollbar while
the test unconditionally expects it to be mapped.

On the current 3440x1440 display the settled content and viewport heights are
both 1271 pixels. At an 800-pixel screen height, the same long status content
overflows deterministically and the scrollbar is correctly mapped.

## Decision

Keep production layout code unchanged. Extend the test fixture to report an
800-pixel screen height and a non-constraining `(5000, 5000)` window-manager
maximum size. Strengthen the assertions to verify the resulting 720-pixel
window height and confirm that content is taller than the actual canvas
viewport before asserting that the scrollbar is mapped.

This preserves the test's intended small-screen overflow branch while removing
dependence on the developer's monitor dimensions and window-manager policy.

## Alternatives Considered

- Make the scrollbar assertion conditional on the measured overflow state.
  This is portable but no longer guarantees the intended overflow branch runs.
- Remove the scrollbar assertion. This narrows the test but loses integration
  coverage for long update status content on a constrained screen.

## Verification

- Preserve the current deterministic failure on the tall Windows display as
  the pre-change signal.
- Run the focused test after constraining its screen fixture.
- Run all `SettingsWindowTkLayoutTests` and the complete settings-window suite.
- Run the full Windows discovery suite.
