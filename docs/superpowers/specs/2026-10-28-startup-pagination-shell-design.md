# Startup, Pagination, and Themed Window Shell Design

## Problem

The first Settings opening feels slow because the Tk UI thread constructs the
entire Settings, Metrics, Wardrobe, and Achievements experience before the
window becomes usable. The current opening path renders every cat preview,
every visible accessory thumbnail, every achievement card, and then performs
full-page geometry settling.

The current page also mounts long Wardrobe and Achievements shelves as one
continuous list. At constrained sizes, card copy can be clipped before the
outer canvas scrollbar becomes useful. The native Windows title bar and the
scrollbar styling do not express the approved Butter Sun toybox theme.

## Goals

- Make the Settings shell interactive before noncritical content is built.
- Defer hidden pages, unused cat poses, and off-page collection cards.
- Add local pagination to Wardrobe and Achievements while preserving their toy
  shelf grouping and global selection state.
- Let card heights grow with their content and prevent text clipping.
- Replace the native Settings window frame with a cross-platform themed title
  bar that preserves window behavior and accessibility.
- Bring the scrollbar into the same neutral-surface, Butter Sun, and ink-focus
  visual language.
- Keep the outer scrollbar as an accessibility and extreme-size fallback.
- Add timing and construction-count regression checks for the startup path.

## Non-goals

- Changing the four top-level destinations or their order.
- Replacing the approved toybox visual language.
- Reworking the metrics chart or the app's persistence model.
- Removing native window capabilities such as minimize, maximize, restore,
  close, keyboard focus, or platform window movement.
- Adding a second navigation hierarchy for Settings shelves.

## Evidence and research

The local timing harness measured approximately 270–390 ms for `CatTypeApp`
initialization and 1.3–1.8 seconds for the first `open_settings()` call. The
first opening performed 92 `load_frame` calls: 48 Settings preview frames, 22
Wardrobe thumbnails, and 22 Achievement thumbnails. Full-page `_center()`
measurement was the largest Settings phase after construction.

Microsoft's startup guidance defines startup through the first meaningful
interactive frame, recommends measuring cold and warm paths, and recommends
deferring noncritical work. Tk's event model supports deferring idle work with
`after_idle` while keeping Tk calls on the interpreter's UI thread. Linear page
controls are appropriate for bounded, ordered collections; a text page label
and previous/next controls are preferred here over a large row of dots because
the collections can contain more than ten items.

## Design

### Themed window shell

Settings uses a custom title bar inside a frameless window.

- Height is approximately 36–40 px and uses the Butter Sun accent with neutral
  surfaces and ink text.
- The left side contains the cat mark and `Cat Type Settings`.
- The center is a draggable region.
- The right side contains consistent soft-toybox minimize, maximize/restore,
  and close controls.
- The close control routes through the existing save/close path. Alt+F4 and the
  window close action use the same path.
- Controls expose accessible names, keyboard focus, hover, pressed, disabled,
  and high-contrast states.
- The shell preserves minimize, maximize, restore, DPI scaling, and native
  window positioning on Windows, macOS, and Linux.
- Title text contracts before controls become unreachable at narrow widths.

The scrollbar is a themed control with a neutral trough, a Butter Sun active
thumb, a darker ink hover/focus state, and a pointer/keyboard target large
enough for accessibility. It remains hidden when the active page fits.

### Startup and lazy construction

The first frame creates only the root, title bar, rail, page heading, footer,
scroll host, scrollbar shell, and Settings page container. A lightweight
current-cat placeholder appears before preview hydration completes.

After the first frame is interactive, `after_idle` work proceeds in small
batches:

1. Load the selected cat's current preview.
2. Hydrate the rail preview and animation.
3. Build visible Settings shelves.
4. Render remaining selected-page details as needed.

Metrics, Wardrobe, and Achievements are created on first selection and retained
for later reuse. Wardrobe and Achievements render only their active page. Cat
poses and accessory combinations are loaded on demand and use the existing
render cache.

The initial path does not run a blocking full-window `update()` loop while
constructing content. A quiet inline loading state is allowed inside a shelf
while deferred content is being hydrated; modal spinners are not used.

### Wardrobe pagination

Wardrobe keeps its accessory tray shelf and global equipped state.

- Four cards appear per page at normal width.
- Two cards appear per page at compact width.
- The heading exposes the visible range, such as `1–4 of 22 unlocked`.
- Controls use the shared soft-pill treatment: `← Previous`, `Page X of Y`,
  and `Next →`.
- Page changes reset only the local shelf view position.
- Equipping, unlocking, mixing, and saving remain global operations.
- If a selected or newly unlocked accessory is off-page, the view moves to its
  page before focusing it.
- Page count and current index are clamped after unlocks or filtering changes.

Only the active page's tiles and thumbnails are mounted. Card text wraps from
the measured copy-column width; no fixed-height text area is allowed.

### Achievements pagination

Achievements keeps its reward album and new-reward semantics.

- Four reward cards appear per page in a 2×2 layout when width allows.
- Two cards appear per page in a single column at compact width.
- The album heading exposes the page position and reward count.
- New indicators remain attached to reward cards, not to page controls.
- Achievement links and unlock notifications jump to the correct page before
  moving keyboard focus.
- Page changes preserve the active-day and progress state.

Only the active page's cards are mounted. Card height is content-driven, and
the copy wrap length is calculated from the actual available column width.

### Overflow and responsive behavior

The active page is designed to fit a normal viewport without vertical
scrolling. The outer canvas scrollbar remains available for extreme text
scaling, unusually small windows, and accessibility settings. When overflow
does occur, the scrollbar reflects actual content bounds and never masks a
card's copy or action controls.

The page controls live outside the paged card list so they remain reachable
when the list grows. Resizing recomputes the compact/wide layout and clamps the
current page without losing selection state.

## Data flow and boundaries

- `CatTypeApp` owns app state, persistence, active settings, and the first-frame
  timing markers.
- `SettingsWindow` owns the shell, destination switching, lazy page factories,
  title-bar commands, scrollbar presentation, and page lifecycle.
- `WardrobeView` owns the accessory model, active page index, page controls, and
  current-page tile construction.
- `AchievementsView` owns the reward model, active page index, page controls,
  and current-page album construction.
- Rendering helpers remain pure and cached; Tk `PhotoImage` instances stay on
  the Tk thread and are released when a page is rebuilt.

State changes update the model first, then refresh the active page. A refresh
preserves the selected page when it remains valid and clamps it otherwise.

## Failure handling

- If deferred preview rendering fails, the shell remains interactive and shows
  the existing inline error/retry surface.
- If a page cannot render a thumbnail, its card keeps its text and action area
  and uses the existing empty/fallback visual treatment.
- If a custom title-bar command is unavailable on a platform, the control uses
  the platform's supported fallback without removing close or keyboard access.
- If the window is too small for a page, the outer scrollbar appears and page
  controls remain outside the scrollable card list.

## Verification plan

Add deterministic timing and construction-count checks for:

- `CatTypeApp` initialization;
- shell-to-first-interactive Settings frame;
- first Settings page construction;
- first navigation to Metrics, Wardrobe, and Achievements;
- first Wardrobe/Achievements page render;
- warm page switches after the first build.

Extend real-Tk tests for:

- title-bar drag and window command accessibility metadata;
- themed scrollbar states and hidden/visible transitions;
- card text wrapping without clipped action controls;
- Wardrobe page counts, state preservation, clamping, and off-page focus;
- Achievements page counts, new indicators, and off-page focus;
- compact and wide layouts with extreme scaling and narrow windows.

The final verification must include the full existing unittest matrix and a
fresh startup benchmark on the Windows development environment.
