# Cross-Platform Small-Screen Layout Test Correction Design

## Problem

Cat Type v1.0.28 did not publish because the macOS arm64 release job failed
`test_opening_measures_after_reducing_minimum_for_small_screen`. The test
reported an 800-pixel screen and expected Tk to realize an exact 720-pixel
top-level height. Native macOS arm64 Tk instead realized 653 pixels. The same
test passed on Windows, Linux, and macOS Intel.

The exact-height assertion confuses a requested geometry with a native window
manager guarantee. Tk geometry requests are advisory: decorations, usable
screen space, and platform policy may produce a smaller realized height. The
test's actual contract is not an exact outer-window size. It is that the
small-screen path reduces the minimum width before measuring content, measures
the settled content, detects genuine vertical overflow, and maps the scrollbar.

## Decision

Keep `settings_window.py` unchanged. Preserve the deterministic test inputs:
an 800-pixel reported screen height and a non-constraining `(5000, 5000)`
reported maximum size. Replace the exact `winfo_height() == 720` assertion with
portable bounds on the realized height:

- the height is at least the 600-pixel opening height; and
- the height is no greater than the 720-pixel available height derived from
  the reported screen height and `SCREEN_VERTICAL_MARGIN`.

Retain the assertions that the realized width is 620 pixels and below the
normal minimum, the final content height was passed through
`_content_fitted_height`, content is taller than the actual canvas viewport,
and the scrollbar is mapped. These assertions exercise the intended production
behavior without treating native geometry realization as deterministic.

## Alternatives Considered

- Mock the top-level geometry and measurement methods completely. This would
  make exact dimensions deterministic but turn the integration test into a
  mock contract and lose coverage of real Tk layout behavior.
- Skip the test on macOS arm64. This would conceal a portable test defect and
  leave release confidence weaker on a supported target.
- Rerun v1.0.28 until it passes. The observed 653-pixel result is consistent
  with native window-manager policy, not an intermittent infrastructure error,
  and rerunning would not correct the invalid assertion on `main`.

## Verification and Release Recovery

The existing v1.0.28 tag remains immutable and unpublished. First reproduce the
failure against the tagged commit on macOS arm64, then apply only the portable
assertion change and run the focused Tk test, the complete settings-window
module, and the full local suite. Push the correction to `main` and require a
successful cross-platform build.

Because v1.0.28 cannot be moved or reused, synchronize all release metadata to
`1.0.29`, create a new annotated `v1.0.29` tag only after the pushed-main gate
passes, and require the five-platform Release workflow to succeed. Publication
is complete only when the stable GitHub Release contains five non-empty
platform packages plus `SHA256SUMS.txt`.

