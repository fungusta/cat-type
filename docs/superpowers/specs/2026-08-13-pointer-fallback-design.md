# Pointer Fallback for Missing Carets

## Purpose

When Cat Type cannot detect a usable text caret, it will place the companion
beside the current mouse pointer. This makes the Windows behavior consistent
with the existing macOS and Linux behavior and keeps typing feedback available
in terminals, canvas-based editors, elevated applications, and other controls
that do not expose caret geometry.

Password fields remain an explicit exception: when UI Automation identifies
the focused control as a password field, Cat Type stays hidden and does not
query or use the pointer fallback.

## Considered Approaches

### Centralize pointer lookup in `CaretLocator` (selected)

Add a focused pointer-location method to `CaretLocator` and call it after the
platform's caret providers have failed. The locator continues to return a
normal `CaretSnapshot` with a narrow, caret-like `ScreenRect`, so monitor
selection, preferred placement, edge flipping, and overlay rendering require
no special pointer path.

This keeps all screen-position discovery in one component, makes the fallback
directly unit-testable, and reuses the bundled `pynput` dependency on every
platform. Because importing the `pynput` package initializes both input
subpackages, the frozen Windows build explicitly includes
`pynput.keyboard._win32` and `pynput.mouse._win32`, matching the existing
explicit macOS and Linux backend declarations.

### Query the pointer in `CatTypeApp._show`

The renderer could recognize a missing caret and query the pointer itself.
This would mix input discovery into overlay rendering, preserve two different
positioning paths, and make failures harder to isolate. It is not selected.

### Use a Windows-native pointer API only

Windows could use `GetCursorPos` while macOS and Linux keep using `pynput`.
This avoids one library call on Windows but adds an unnecessary platform split
for a dependency already shipped with the app. It is not selected.

## Behavior and Data Flow

`CaretLocator.locate()` keeps the following priority order:

1. On Windows, inspect UI Automation. If the focused control is a password
   field, return a password snapshot immediately with no fallback.
2. Use a usable UI Automation caret rectangle when available.
3. Use a usable Win32 caret rectangle when available.
4. If no caret provider produced a rectangle, read the current pointer
   coordinates and return a `pointer-fallback` snapshot.
5. If pointer lookup also fails, return the existing empty snapshot and keep
   the companion hidden.

On macOS and Linux, where no native caret provider is currently implemented,
the same pointer-location method remains the primary source.

The pointer is represented as a 2-by-20-pixel rectangle beginning at the
rounded pointer coordinates. Existing `choose_overlay_position()` behavior
therefore honors the configured corner, chooses the pointer's monitor, flips
at screen edges, and clamps the cat to the work area. As with a detected caret,
the overlay position is fixed for one appearance and is recalculated on the
next appearance after the animation hides.

The old Windows-only active-monitor-corner fallback and its
`fallback_allowed` flag are removed because every allowed missing-caret case
now attempts a more precise pointer fallback.

## Failure Handling and Diagnostics

Pointer lookup catches platform/backend errors. With debug logging enabled,
Cat Type prints `Pointer lookup failed: <error>` and returns an empty snapshot;
without debug logging it fails silently and leaves the overlay hidden. A
pointer failure never overrides password suppression.

Successful pointer fallback snapshots use `source="pointer-fallback"`, so the
existing debug output identifies the chosen provider and coordinates.

## Testing and Release

Unit tests will verify caret-provider precedence, pointer fallback after all
Windows caret providers fail, consistent non-Windows pointer behavior,
password suppression, coordinate rounding, and pointer-backend failure. The
obsolete preferred-monitor-corner rendering tests will be replaced by pointer
positioning coverage.

The complete test suite will run locally on Linux. The pushed commit will then
run the repository's GitHub Actions build matrix on `windows-latest`,
`macos-15-intel`, and `ubuntu-22.04`. Release `v1.0.7` will additionally build
and test Windows x64, macOS x64 and arm64, and Linux x64 and arm64 artifacts.
The release is complete only after all release jobs succeed and GitHub shows
the published release with all five platform assets plus `SHA256SUMS.txt`.
