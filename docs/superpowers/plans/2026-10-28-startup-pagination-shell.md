# Startup, Pagination, and Themed Window Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Settings interactive sooner, paginate Wardrobe and Achievements without clipping, and replace the mismatched native shell with the approved Butter Sun toybox title bar and scrollbar.

**Architecture:** Keep `SettingsWindow` as the page coordinator, but give it lazy page factories so only the Settings page is built before the first interactive frame. Add a pure pagination model plus shared Tk page controls; Wardrobe and Achievements render only their active page. Move the custom title bar into a focused `window_chrome.py` component while keeping the existing ttk scrollbar semantics and theming it through the existing style layer.

**Tech Stack:** Python 3.12, Tkinter/ttk, Pillow/ImageTk, existing `RoundedPanel`/`RoundedAction` surfaces, `unittest`, real-Tk layout tests, and the existing cross-platform GitHub Actions matrix.

## Global Constraints

- Preserve the four top-level destinations and their order.
- Keep the Butter Sun, toybox, toy rail, toy shelves, soft toybox pill, and roomy playroom language from `CONTEXT.md`.
- Wardrobe uses four cards per normal page and two cards per compact page.
- Achievements uses four cards per normal page and two cards per compact page.
- Card height is content-driven; no fixed-height text region may clip copy or actions.
- The outer scrollbar remains available for extreme text scaling and unusually small windows.
- All Tk calls stay on the Tk interpreter's UI thread.
- Preserve minimize, maximize, restore, close, keyboard focus, DPI scaling, and platform window movement.
- Do not change the metrics chart or persistence model.
- Existing tests and the full CI matrix must remain green.

---

### Task 1: Add a pure pagination model and shared page controls

**Files:**
- Create: `pagination.py`
- Modify: `ui_surfaces.py`
- Create: `tests/test_pagination.py`
- Modify: `tests/test_settings_window.py` for real-Tk control metadata

**Interfaces:**
- `pagination.py` provides `PageWindow`, `page_window(total_items: int, page_index: int, page_size: int) -> PageWindow`, `page_slice(items: Sequence[T], page_index: int, page_size: int) -> tuple[T, ...]`, and `page_label(window: PageWindow) -> str`.
- `ui_surfaces.py` provides `PaginationControls(tk.Frame)` with `set_state(window: PageWindow) -> None`, `previous_button`, `next_button`, and `page_label` attributes. Its constructor accepts `on_previous: Callable[[], None]`, `on_next: Callable[[], None]`, `palette`, and `fonts` and uses `RoundedAction` for both buttons.

- [ ] **Step 1: Write pure pagination tests**

  Cover empty collections, one-page collections, page-index clamping, a partial final page, and the exact visible-range label. Example expectations:

  ```python
  window = page_window(total_items=22, page_index=5, page_size=4)
  self.assertEqual((window.index, window.page_count, window.start, window.end), (5, 6, 20, 22))
  self.assertEqual(page_label(window), "Page 6 of 6")
  self.assertEqual(page_slice(tuple(range(6)), 1, 4), (4, 5))
  ```

- [ ] **Step 2: Run the pure tests and confirm they fail**

  Run: `python -m unittest tests.test_pagination -v`

  Expected: import/attribute failures because the model does not exist yet.

- [ ] **Step 3: Implement the immutable page model**

  Validate `total_items >= 0`, `page_size > 0`, and clamp `page_index` into `[0, page_count - 1]` when `page_count > 0`. For an empty collection return `page_count=0`, `start=0`, and `end=0`. Keep all indexing zero-based internally and expose one-based labels.

- [ ] **Step 4: Implement shared page controls**

  Build the controls with the existing soft-pill surfaces. Disable Previous on the first page and Next on the last page. Keep the page label as a plain text label between the buttons, with keyboard focus landing on the first enabled action. Set accessible `title`/metadata strings to `Previous page`, `Next page`, and the current page label.

- [ ] **Step 5: Add control metadata tests and run the focused suite**

  Extend the real-Tk settings fixture to assert the controls expose their labels, disabled states, and shared button face styling. Run:

  ```powershell
  python -m unittest tests.test_pagination tests.test_settings_window.SettingsWindowTkLayoutTests.test_custom_actions_expose_button_accessibility_metadata -v
  ```

- [ ] **Step 6: Commit**

  ```powershell
  git add pagination.py ui_surfaces.py tests/test_pagination.py tests/test_settings_window.py
  git commit -m "feat: add shared pagination controls"
  ```

### Task 2: Paginate Wardrobe without changing outfit state

**Files:**
- Modify: `wardrobe_view.py`
- Modify: `settings_window.py` where Wardrobe is created and updated
- Modify: `tests/test_wardrobe.py`
- Modify: `tests/test_wardrobe_integration.py`

**Interfaces:**
- `WardrobeView` owns `_visible_items: tuple[Accessory, ...]`, `_page_index: int`, `_page_size: int`, and `pagination_controls: PaginationControls`.
- Add `WardrobeView.show_page(page_index: int) -> None`, `WardrobeView.focus_item(item_id: str) -> tk.Widget`, and `WardrobeView.page_for_item(item_id: str) -> int`.
- `WardrobeView.update_unlocks()` recomputes the visible model, clamps the page, rebuilds only the current slice, and refreshes selection/status state.

- [ ] **Step 1: Write failing page/state tests**

  Add tests that unlock 22 items, assert only the current page's tile IDs are mounted, move to the next page, assert the new slice, equip an item, change page, and verify the `StringVar` slot state persists. Add tests for page clamping after an unlock set shrinks and for `focus_item("round-glasses")` navigating before focusing the tile.

- [ ] **Step 2: Run Wardrobe tests and confirm the new expectations fail**

  Run: `python -m unittest tests.test_wardrobe tests.test_wardrobe_integration -v`

  Expected: missing pagination attributes/methods and the current all-items rendering behavior.

- [ ] **Step 3: Separate the visible accessory model from mounted Tk tiles**

  Keep the full visible/unlocked model in `_visible_items`. Compute the page size from the actual available width: return `4` when the choices area is at least the existing wide breakpoint and `2` otherwise. Recompute on `<Configure>` without losing the current item identity; clamp `_page_index` after page-size changes.

- [ ] **Step 4: Move page controls outside the card list**

  Add `PaginationControls` below `choices_area` inside `tray_shelf`. Keep slot headers and `None` actions for slots represented on the active page. Use the visible range in `tray_count` and keep `Mix it up` owned by the page heading.

- [ ] **Step 5: Render only the active page and make copy columns elastic**

  Change `_build_choices` to accept the current page slice. Destroy only the previous page's mounted tiles and thumbnails. Configure the tile grid as thumbnail / weighted copy / action columns; set status wrap length from the copy frame's `<Configure>` width rather than the constant `145`. Preserve `buttons`, `status_text`, `new_badges`, and `achievement_links` for the active page only.

- [ ] **Step 6: Add focus/navigation and state refresh behavior**

  Implement `page_for_item`, `show_page`, and `focus_item`. When an achievement link targets Wardrobe, navigate to the target page, call `update_idletasks`, then focus the target action. When unlocks or visible IDs change, clamp the page and rebuild the current slice before applying status and new badges.

- [ ] **Step 7: Update integration tests and run the focused suite**

  Replace direct assumptions that every item exists in `wardrobe.buttons` with `focus_item`/`page_for_item` where the test targets an off-page item. Run:

  ```powershell
  python -m unittest tests.test_wardrobe tests.test_wardrobe_integration tests.test_settings_window.SettingsWindowTkLayoutTests.test_wardrobe_fits_narrow_width_and_switches_pages -v
  ```

- [ ] **Step 8: Commit**

  ```powershell
  git add wardrobe_view.py settings_window.py tests/test_wardrobe.py tests/test_wardrobe_integration.py
  git commit -m "feat: paginate wardrobe accessory tiles"
  ```

### Task 3: Paginate Achievements and preserve focus/new state

**Files:**
- Modify: `achievements_view.py`
- Modify: `settings_window.py` focus and page-switch paths
- Modify: `tests/test_wardrobe.py`
- Modify: `tests/test_wardrobe_integration.py`

**Interfaces:**
- `AchievementsView` owns `_visible_items: tuple[Accessory, ...]`, `_page_index`, `_page_size`, and `pagination_controls`.
- Add `AchievementsView.show_page(page_index: int) -> None`, `AchievementsView.focus_reward(accessory_id: str) -> tk.Frame`, and `AchievementsView.page_for_item(accessory_id: str) -> int`.
- `AchievementsView.update_progress()` refreshes model values and rebuilds only the active page when visible IDs change.

- [ ] **Step 1: Write failing pagination/focus tests**

  Add tests for 22 rewards split into pages, compact one-column pages, page clamping, preserving `new_badges`, and `focus_reward` navigating to an off-page reward before focusing it. Assert card copy labels receive a wrap length based on their measured copy column.

- [ ] **Step 2: Run the focused tests and confirm failure**

  Run: `python -m unittest tests.test_wardrobe.WardrobeTests.test_achievements_reward_album_reflows_between_grid_columns tests.test_wardrobe_integration.WardrobeIntegrationTests.test_locked_items_link_to_separate_achievement_and_cannot_be_equipped -v`

  Expected: current all-card rendering and missing page state fail the new assertions.

- [ ] **Step 3: Split the achievement model from mounted cards**

  Keep the full visible reward tuple and progress dictionaries as model state. Make `_build_cards` accept only the active page slice, clear the old page's cards/thumbnails, and retain the current card layout logic for the slice.

- [ ] **Step 4: Add page controls and responsive page size**

  Add controls below the album grid. Use four cards per page at wide width and two per page at compact width. Re-run `_layout_cards`, `_sync_album_size`, and `_schedule_album_layout` after page changes and after `<Configure>` changes.

- [ ] **Step 5: Make reward copy and actions content-driven**

  Keep the existing `_fit_reward_copy` callback but calculate each label's wrap length from its measured copy frame. Ensure the card's action/status column remains visible after wrapping and let `RoundedPanel` request the resulting height.

- [ ] **Step 6: Update focus and new-reward behavior**

  Make `focus_reward` call `show_page(page_for_item(...))`, update idle layout, then focus the card. Keep new badges in the card model and reapply them after every page rebuild. Update `SettingsWindow._show_achievement` to call this method before calculating canvas coordinates.

- [ ] **Step 7: Run the focused Wardrobe/Achievement suite**

  Run:

  ```powershell
  python -m unittest tests.test_wardrobe tests.test_wardrobe_integration -v
  ```

- [ ] **Step 8: Commit**

  ```powershell
  git add achievements_view.py settings_window.py tests/test_wardrobe.py tests/test_wardrobe_integration.py
  git commit -m "feat: paginate achievement rewards"
  ```

### Task 4: Lazy-build Settings pages and stage preview rendering

**Files:**
- Modify: `settings_window.py`
- Modify: `cat_type.py`
- Modify: `tests/test_settings_window.py`
- Modify: `tests/test_behavior.py`
- Create: `tests/test_startup_performance.py`

**Interfaces:**
- `SettingsWindow` adds `_page_views: dict[str, tk.Misc]`, `_page_factories: dict[str, Callable[[], tk.Misc]]`, and `_ensure_page(label: str) -> tk.Misc`.
- `SettingsWindow` adds `_hydrate_preview_step() -> None`, scheduled with `after_idle`, and `_preview_hydration_after_id: str | None` for cancellation.
- `CatTypeApp` adds `_ensure_frame_variant(variant: str) -> None` and allows `_load_frames(size_percent, variants: tuple[str, ...] | None = None)` so startup can load only the active variant while later variants remain lazy.

- [ ] **Step 1: Add construction-count regression tests**

  Patch `settings_window.load_frame`, `wardrobe_view.load_frame`, and `achievements_view.load_frame` with counting wrappers. Assert first Settings opening constructs only the Settings shell/current page and does not instantiate Metrics, Wardrobe, or Achievements. Assert first navigation creates exactly one deferred page and a second navigation reuses it. Add a `perf_counter` benchmark helper that reports, but does not gate on, wall-clock duration.

- [ ] **Step 2: Run the new startup tests and confirm failure**

  Run: `python -m unittest tests.test_startup_performance -v`

  Expected: current eager construction exceeds the call-count assertions.

- [ ] **Step 3: Split `_build()` into shell, Settings page, and page factories**

  Keep the rail, heading, footer, canvas, and Settings columns in the initial build. Register factories for Metrics, Wardrobe, and Achievements instead of constructing them unconditionally. `_switch_page()` must forget only page views that exist, call `_ensure_page(selected)`, pack the selected view, and preserve the current page model/state.

- [ ] **Step 4: Update app callbacks for optional pages**

  Guard `update_usage_metrics`, `update_achievements`, preview updates, and close cleanup with `getattr`/page existence checks. If a page is not built, store the latest model state; the first factory call consumes that state. Preserve the existing page-switch and focus behavior.

- [ ] **Step 5: Remove redundant preview loading and add idle hydration**

  Make `_load_preview_frames` accept a variant/pose subset. Load the selected variant and idle frame for the first Settings frame, then use `_hydrate_preview_step` to fill remaining poses/rail frames and call `_display_preview`. Remove the unconditional second full `_load_preview_frames` call from `_refresh_outfit_preview`; refresh only the affected selected outfit frames.

- [ ] **Step 6: Stage CatType overlay frame loading**

  Load the active cat variant needed for the first overlay immediately. Add `_ensure_frame_variant` for alternate cat changes and schedule nonactive variant preparation after the app is interactive. Keep the existing frame cache and ensure `_show()` always calls the helper before indexing a variant.

- [ ] **Step 7: Run startup, Settings, and behavior tests**

  Run:

  ```powershell
  python -m unittest tests.test_startup_performance tests.test_settings_window tests.test_behavior -v
  ```

  Confirm hidden pages are not built on first open, first navigation builds the requested page, and warm navigation reuses it.

- [ ] **Step 8: Commit**

  ```powershell
  git add settings_window.py cat_type.py tests/test_startup_performance.py tests/test_settings_window.py tests/test_behavior.py
  git commit -m "perf: lazy-build settings pages and previews"
  ```

### Task 5: Add the custom themed title bar and scrollbar treatment

**Files:**
- Create: `window_chrome.py`
- Modify: `settings_window.py`
- Modify: `ui_surfaces.py` only if shared button metadata is needed
- Create: `tests/test_window_chrome.py`
- Modify: `tests/test_settings_window.py`

**Interfaces:**
- `window_chrome.py` provides `ThemedTitleBar(tk.Frame)` with constructor callbacks `on_minimize`, `on_toggle_maximize`, and `on_close`, plus `set_maximized(value: bool) -> None`.
- `ThemedTitleBar` exposes `drag_start(event)`, `drag_move(event)`, and `set_title(title: str) -> None` for testable window behavior.
- `SettingsWindow` owns `_toggle_maximize()`, `_begin_window_drag(event)`, `_drag_window(event)`, and `_close_from_chrome()`.

- [ ] **Step 1: Write failing chrome tests**

  Test title text, accessible labels, callback invocation, maximize label toggling, and drag delta calculation with a fake window. Add a real-Tk test that the themed scrollbar uses the shared Butter/ink colors and remains reachable when overflow is present.

- [ ] **Step 2: Run focused tests and confirm failure**

  Run: `python -m unittest tests.test_window_chrome -v`

  Expected: module/class and metadata failures because the custom shell does not exist.

- [ ] **Step 3: Implement `ThemedTitleBar`**

  Use the existing `RoundedAction`/palette treatment for the three window controls, attach `takefocus=True`, and expose clear labels. The center region must bind press/motion/release for dragging without stealing focus from controls.

- [ ] **Step 4: Replace the Settings native frame**

  Create the Toplevel with the custom frame configuration, set `overrideredirect(True)`, set `WM_DELETE_WINDOW` to the shared close callback, and implement minimize/maximize/restore through the platform-supported Tk window methods. Preserve the existing geometry and `_center()` path after accounting for the title-bar height.

- [ ] **Step 5: Finalize scrollbar styling**

  Keep `ttk.Scrollbar` for native keyboard and pointer behavior, use the existing `clam` style path, and configure the trough/thumb/active/pressed colors and width from the Butter Sun palette. Add state maps for hover/focus where the platform theme supports them; do not replace scrolling with a decorative-only canvas.

- [ ] **Step 6: Run chrome, layout, and settings tests**

  Run:

  ```powershell
  python -m unittest tests.test_window_chrome tests.test_settings_window -v
  ```

  Check narrow geometry, maximize/restore, Alt+F4 close routing, title-bar focus order, and scrollbar visibility.

- [ ] **Step 7: Commit**

  ```powershell
  git add window_chrome.py settings_window.py ui_surfaces.py tests/test_window_chrome.py tests/test_settings_window.py
  git commit -m "feat: add themed settings window chrome"
  ```

### Task 6: Full regression verification and performance report

**Files:**
- Modify: `docs/superpowers/specs/2026-10-28-startup-pagination-shell-design.md` only if measured behavior requires a clarified constraint
- Create: `docs/research/2026-10-28-startup-pagination-shell-verification.md`

**Interfaces:**
- Consumes the startup benchmark, pagination tests, chrome tests, and existing full matrix.
- Produces a dated verification report with cold/warm timings, construction counts, page-switch timings, and platform test results.

- [ ] **Step 1: Run the focused UI suite**

  ```powershell
  python -m unittest tests.test_pagination tests.test_window_chrome tests.test_settings_window tests.test_wardrobe tests.test_wardrobe_integration tests.test_startup_performance -v
  ```

- [ ] **Step 2: Run the full local CI-equivalent command**

  ```powershell
  $testTemp = Join-Path (Get-Location) '.test-tmp'
  New-Item -ItemType Directory -Force -Path $testTemp | Out-Null
  $env:TEMP = $testTemp
  $env:TMP = $testTemp
  python scripts/run_ci_tests.py
  ```

  Expected: zero failures, with only the platform-appropriate skips.

- [ ] **Step 3: Run the startup benchmark in a Release-like environment**

  Record five cold and five warm `CatTypeApp`/`open_settings` timings with the benchmark helper. Report median and worst-case shell-to-first-interactive and first navigation times; do not use a single lucky run as the result.

- [ ] **Step 4: Inspect the UI at representative sizes**

  Verify default, narrow, high-scaling, and overflow states. Confirm no card copy or action is clipped, page controls remain reachable, and the custom title bar still moves/resizes/closes the window.

- [ ] **Step 5: Write the verification report**

  Include command output summaries, timing tables, page/card counts, and any platform-specific fallback behavior in `docs/research/2026-10-28-startup-pagination-shell-verification.md`.

- [ ] **Step 6: Commit the report**

  ```powershell
  git add docs/research/2026-10-28-startup-pagination-shell-verification.md
  git commit -m "docs: record startup and pagination verification"
  ```

- [ ] **Step 7: Run the final clean-status review**

  Confirm `git diff --check`, inspect `git status --short`, verify no debug instrumentation remains, and summarize local and CI evidence before integration.
