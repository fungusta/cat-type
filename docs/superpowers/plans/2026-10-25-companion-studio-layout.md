# Companion Studio Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recompose the native Cat Type settings window around the approved Companion Studio layout while preserving all existing settings, metrics, wardrobe, achievement, persistence, and keyboard behavior.

**Architecture:** Keep `SettingsWindow` as the owner of navigation, page composition, shared save state, and the scrollable host. Keep reusable rounded surfaces in `ui_surfaces.py`; keep wardrobe and achievement content in their existing view classes. The production shell will use a compact cat preview in the Cat Type rail brand area, page-specific rounded shelves, and a shared transient Saved! status instead of a persistent save message.

**Tech Stack:** Python 3, Tkinter/ttk, Pillow for native rendered surfaces, unittest/pytest, existing Cat Type artwork and accessory assets.

## Global Constraints

- Keep a persistent left toy rail for Settings, Metrics, Wardrobe, and Achievements.
- Put the cat preview inside the Cat Type brand area at the top of the rail.
- Remove the large middle Companion Studio title card.
- Page names provide enough orientation; do not add repeated purpose paragraphs beneath page titles.
- Use neutral shelves, dark ink, restrained muted text, and one Butter Sun accent.
- Keep the shared soft pill treatment for navigation, choices, and actions.
- Show a prominent Butter Sun **Saved!** pill only after a setting interaction completes; do not show “Saved automatically” persistently.
- Preserve visible keyboard focus and pressed-state movement.
- Do not change the settings data model, metrics calculations, wardrobe inventory, achievement rules, persistence behavior, or page destinations.
- Preserve narrow-window scrolling and footer/action accessibility.

## File Map

- Modify `settings_window.py`: shell geometry, rail brand preview, page host, Settings/Metrics composition, save feedback placement and timing, and shared typography tokens.
- Modify `ui_surfaces.py`: keep rounded shelf/pill rendering reusable; add only the minimal APIs needed for a focusable page status pill or responsive shelf content.
- Modify `wardrobe_view.py`: use the shared shelf/tile composition and keep Wardrobe scoped to outfit selection.
- Modify `achievements_view.py`: use the shared shelf/reward album composition while preserving focus-to-reward behavior.
- Modify `tests/test_settings_window.py`: shell, page composition, status feedback, responsive, and keyboard regressions.
- Modify `tests/test_wardrobe.py`: Wardrobe shelf ownership and tile/link behavior regressions.
- Modify `docs/superpowers/specs/2026-10-25-companion-studio-layout-design.md` only if implementation evidence requires a clarified decision; do not silently change the approved design.

---

### Task 1: Rebuild the shared Companion Studio shell

**Files:**
- Modify: `settings_window.py:778-856` (`_build_page_switcher`, `_switch_page`) and the body construction around `settings_window.py:640-760`.
- Modify: `ui_surfaces.py:323-390` (`RoundedPanel`) only if the rail brand preview needs a focus-safe child container.
- Test: `tests/test_settings_window.py` in `SettingsWindowTkLayoutTests`.

**Interfaces:**
- Consumes: existing `SettingsWindow.active_page`, `page_host`, page view instances, `load_frame` preview frames, and shared palette/font tokens.
- Produces: `SettingsWindow.page_switcher` as the persistent rail, `SettingsWindow.page_host` as the active-page host, and a rail brand area containing the cat preview plus Cat Type label.

- [ ] **Step 1: Write the failing shell tests.** Add tests that assert the rail owns the cat preview and that no middle Companion Studio title widget exists:

```python
def test_companion_studio_shell_puts_preview_in_the_rail(self) -> None:
    rail = self.settings_window.page_switcher
    self.assertIs(self.settings_window.rail_preview.master, rail.content)
    self.assertEqual(self.settings_window.rail_brand_title.cget("text"), "Cat Type")
    self.assertFalse(hasattr(self.settings_window, "companion_header"))

def test_page_content_starts_in_the_main_host(self) -> None:
    self.settings_window.active_page.set("Settings")
    self.settings_window._switch_page()
    self.settings_window.window.update_idletasks()
    self.assertIs(self.settings_window.columns.master, self.settings_window.page_host)
    self.assertIs(self.settings_window.metrics_page.master, self.settings_window.page_host)
```

- [ ] **Step 2: Run the focused tests and verify the expected failure.**

Run: `python -m pytest tests/test_settings_window.py -k "shell_puts_preview_in_the_rail or page_content_starts_in_the_main_host" -q`

Expected: FAIL because the production shell does not expose `rail_preview`/`rail_brand_title` and still owns the previous header structure.

- [ ] **Step 3: Implement the shell.** Move the cat preview image into the rail brand area, expose `rail_preview` and `rail_brand_title`, keep the four navigation pills in the rail, and mount `columns`, `metrics_page`, `wardrobe`, and `achievements` under `page_host`. Remove the middle title/header card and delete page-purpose paragraphs from the page headers. Keep the scroll canvas and footer outside the page host so narrow-window scrolling remains unchanged.

- [ ] **Step 4: Run the focused tests and the existing shell/scroll tests.**

Run: `python -m pytest tests/test_settings_window.py -k "shell or page_content_starts or scrolling or footer or narrow" -q`

Expected: PASS with no geometry regressions.

- [ ] **Step 5: Commit the shell change.**

```bash
git add settings_window.py ui_surfaces.py tests/test_settings_window.py
git commit -m "feat: add companion studio shell"
```

### Task 2: Move save feedback into a transient page status

**Files:**
- Modify: `settings_window.py:400-420`, `settings_window.py:2076-2130`, and `settings_window.py:2400-2460`.
- Test: `tests/test_settings_window.py` save/error tests around lines 1760-1855.

**Interfaces:**
- Consumes: existing `save_status`, `_schedule_save`, `_save`, `retry_button`, and auto-save traces.
- Produces: a page-heading status widget that is empty at rest, displays `Saved!` after a successful save, clears after a short scheduled interval, and displays the existing actionable failure text plus Retry when saving fails.

- [ ] **Step 1: Write failing save-feedback tests.** Replace the persistent-copy expectation with explicit idle/success/error behavior:

```python
def test_save_feedback_is_empty_until_a_change_saves(self) -> None:
    self.assertEqual(self.settings_window.save_status.get(), "")
    self.settings_window.enabled.set(not self.settings_window.enabled.get())
    self.settings_window.window.update()
    self.assertEqual(self.settings_window.save_status.get(), "Saved!")

def test_save_feedback_clears_after_success_timeout(self) -> None:
    self.settings_window.save_status.set("Saved!")
    self.settings_window._clear_save_feedback()
    self.assertEqual(self.settings_window.save_status.get(), "")

def test_save_failure_keeps_actionable_status_and_retry(self) -> None:
    self.on_save.side_effect = OSError("disk full")
    self.settings_window.enabled.set(not self.settings_window.enabled.get())
    self.settings_window._save()
    self.assertEqual(
        self.settings_window.save_status.get(),
        "Couldn't save this change. Try again.",
    )
    self.assertEqual(str(self.settings_window.retry_button.cget("state")), "normal")
```

- [ ] **Step 2: Run the focused tests and verify they fail for the old persistent status.**

Run: `python -m pytest tests/test_settings_window.py -k "save_feedback or save_failure" -q`

Expected: FAIL because the initial status is currently `Changes save automatically.` and there is no transient clear method.

- [ ] **Step 3: Implement transient feedback.** Initialize `save_status` to `""`; add `_clear_save_feedback`; set `Saved!` only after `_on_save` succeeds; schedule `_clear_save_feedback` with `after`; cancel an older clear timer before showing a new success; keep failure text and Retry visible until a successful retry. Move the `textvariable` label from the footer into each page heading’s status area while keeping the footer for Close/Retry layout and preserving footer height calculations.

- [ ] **Step 4: Run save and footer tests.**

Run: `python -m pytest tests/test_settings_window.py -k "save or footer or retry" -q`

Expected: PASS; idle state has no status copy, success reads `Saved!`, and failures remain actionable.

- [ ] **Step 5: Commit the save-feedback change.**

```bash
git add settings_window.py tests/test_settings_window.py
git commit -m "feat: make save feedback transient"
```

### Task 3: Recompose the Settings page into Companion and Behavior shelves

**Files:**
- Modify: `settings_window.py` Settings page builders around `settings_window.py:885-1050` and `_card` at `settings_window.py:2129-2165`.
- Test: `tests/test_settings_window.py` layout and copy tests around lines 391-520 plus new shelf tests.

**Interfaces:**
- Consumes: existing `Toggle`, `CatScale`, `RoundedPanel`, `RoundedChoice`, `RoundedAction`, and setting variables.
- Produces: two page shelves containing readable setting rows with right-aligned controls and no duplicate page-purpose copy.

- [ ] **Step 1: Write failing Settings composition tests.** Assert the two shelf headings and the absence of the removed filler copy:

```python
def test_settings_uses_companion_and_behavior_shelves(self) -> None:
    texts = self._widget_texts(self.settings_window.columns)
    self.assertIn("Companion", texts)
    self.assertIn("Behavior", texts)
    self.assertNotIn("Keep the cat close, calm, and easy to personalize.", texts)
    self.assertNotIn("Make it feel like yours.", texts)

def test_settings_rows_keep_controls_on_the_right(self) -> None:
    self.settings_window.active_page.set("Settings")
    self.settings_window._switch_page()
    self.settings_window.window.update_idletasks()
    self.assertLess(
        self.settings_window.cat_style_control.winfo_rootx(),
        self.settings_window.columns.winfo_rootx() + self.settings_window.columns.winfo_width(),
    )
```

- [ ] **Step 2: Run the focused tests and verify the old layout fails.**

Run: `python -m pytest tests/test_settings_window.py -k "settings_uses_companion_and_behavior or settings_rows_keep_controls" -q`

Expected: FAIL because the current Settings page still uses the previous card hierarchy and does not expose the row control handle.

- [ ] **Step 3: Implement the two-shelf Settings page.** Use the existing rounded shelf helper for `Companion` and `Behavior`; keep labels concise; place cat style, favorite spot, and hang-around timing in Companion; place visibility and launch-at-sign-in in Behavior; retain the existing controls and variables so persistence semantics do not change. Store stable handles such as `cat_style_control` only where tests need geometry evidence.

- [ ] **Step 4: Run Settings layout, keyboard, and save tests.**

Run: `python -m pytest tests/test_settings_window.py -q`

Expected: PASS with no regressions to setting invocation, keyboard focus, resizing, or persistence.

- [ ] **Step 5: Commit the Settings page change.**

```bash
git add settings_window.py tests/test_settings_window.py
git commit -m "feat: recompose settings shelves"
```

### Task 4: Align Metrics, Wardrobe, and Achievements with page-specific shelves

**Files:**
- Modify: `settings_window.py:1054-1325` (Metrics composition), `wardrobe_view.py:15-185`, and `achievements_view.py:17-115`.
- Test: `tests/test_settings_window.py`, `tests/test_wardrobe.py`, and `tests/test_wardrobe_integration.py`.

**Interfaces:**
- Consumes: `RoundedPanel`, `RoundedChoice`, `RoundedAction`, existing metric chart methods, wardrobe slot variables, achievement progress, and artwork loaders.
- Produces: Metrics summary/chart shelves, Wardrobe accessory tray scoped to outfit selection, and Achievements reward album/grid with focusable reward cards.

- [ ] **Step 1: Write failing page-specific composition tests.** Add assertions for the approved ownership boundaries:

```python
def test_wardrobe_does_not_contain_general_settings(self) -> None:
    window = self.window()
    def texts(widget: tk.Misc) -> set[str]:
        values: set[str] = set()
        for child in widget.winfo_children():
            try:
                value = child.cget("text")
            except tk.TclError:
                value = ""
            if value:
                values.add(str(value))
            values.update(texts(child))
        return values

    self.assertNotIn("Favorite spot", texts(window.wardrobe))
    self.assertTrue(window.wardrobe.choice_tiles)

def test_achievements_cards_are_focusable_rounded_shelves(self) -> None:
    window = self.window()
    for card in window.achievements.cards.values():
        self.assertTrue(bool(int(card.cget("takefocus"))))
        self.assertEqual(card._radius, 16)

def test_metrics_keeps_summary_above_one_activity_shelf(self) -> None:
    self.settings_window.active_page.set("Metrics")
    self.settings_window._switch_page()
    self.settings_window.window.update_idletasks()
    self.assertEqual(len(self.settings_window.metric_stat_cards), 3)
    self.assertTrue(self.settings_window.metrics_chart.winfo_ismapped())
```

- [ ] **Step 2: Run the focused page tests and verify the old structure fails.**

Run: `python -m pytest tests/test_settings_window.py tests/test_wardrobe.py -k "metrics_keeps_summary or wardrobe_does_not or achievements_cards" -q`

Expected: FAIL for any page that still uses the old square card hierarchy or places general settings inside Wardrobe.

- [ ] **Step 3: Implement the page-specific compositions.** Keep Metrics as three compact aggregate cards above one chart shelf; keep the body font family and dark ink metric values; keep Wardrobe accessory tiles and achievement links inside rounded shelves without adding general Settings rows; keep Achievements reward cards focusable and preserve `focus_reward` scroll/focus behavior.

- [ ] **Step 4: Run all page behavior tests.**

Run: `python -m pytest tests/test_settings_window.py tests/test_wardrobe.py tests/test_wardrobe_integration.py tests/test_achievements.py -q`

Expected: PASS with the existing metric range/view behavior, wardrobe equipping, achievement unlock flow, and narrow-width behavior intact.

- [ ] **Step 5: Commit the page composition change.**

```bash
git add settings_window.py wardrobe_view.py achievements_view.py tests/test_settings_window.py tests/test_wardrobe.py tests/test_wardrobe_integration.py
git commit -m "feat: align pages with companion studio"
```

### Task 5: Visual and accessibility verification

**Files:**
- Modify: only the production files above if verification exposes a concrete defect.
- Test: `tests/test_settings_window.py`, `tests/test_wardrobe.py`, `tests/test_wardrobe_integration.py`, `tests/test_achievements.py`.

**Interfaces:**
- Consumes: the completed Companion Studio shell and page compositions.
- Produces: verified full-size and narrow-window behavior with no clipped controls, stale status copy, or inconsistent pill states.

- [ ] **Step 1: Run the complete affected test command.**

Run: `python -m pytest tests/test_settings_window.py tests/test_wardrobe.py tests/test_wardrobe_integration.py tests/test_achievements.py -q`

Expected: all tests pass; Tk-only tests may report the existing display-dependent skips.

- [ ] **Step 2: Run static checks.**

Run: `python -m py_compile settings_window.py ui_surfaces.py wardrobe_view.py achievements_view.py; git diff --check`

Expected: exit code 0; `git diff --check` may report only the repository’s existing CRLF normalization warnings.

- [ ] **Step 3: Run the Impeccable detector on changed UI files.**

Run: `C:\Users\Ryzen\.codex\plugins\cache\openai-curated-remote\impeccable\4.3.1\skills\impeccable.cmd detect --json settings_window.py ui_surfaces.py wardrobe_view.py achievements_view.py`

Expected: no unexplained detector findings.

- [ ] **Step 4: Launch the native preview and inspect every destination.**

Run: `python .superpowers/settings-preview.py`

Inspect Settings, Metrics, Wardrobe, and Achievements at the full-size window and at `620x500`. Exercise a pill hover, press, keyboard focus, setting change, successful save, failed save/retry, page switch, Metrics range/view control, Wardrobe selection, and Achievement focus link. Confirm that the cat preview remains in the rail, no middle title card appears, page-purpose copy is absent, and Saved! appears only after a change.

- [ ] **Step 5: Commit any final verification fixes separately.**

```bash
git add settings_window.py ui_surfaces.py wardrobe_view.py achievements_view.py tests/test_settings_window.py tests/test_wardrobe.py tests/test_wardrobe_integration.py tests/test_achievements.py
git commit -m "fix: polish companion studio verification findings"
```

## Plan self-review

- **Spec coverage:** shell, rail preview, removed middle title, page-specific Settings/Metrics/Wardrobe/Achievements structure, transient Saved! feedback, copy reduction, visual tokens, accessibility, persistence boundaries, and responsive behavior are each assigned to Tasks 1–5.
- **Placeholder scan:** no TBD/TODO/FIXME steps or unspecified implementation tasks are used.
- **Type consistency:** the plan uses the existing `SettingsWindow`, `RoundedPanel`, `RoundedChoice`, `RoundedAction`, `WardrobeView`, `AchievementsView`, `metric_stat_cards`, `save_status`, `retry_button`, and page variables consistently across tasks.
- **Scope:** the plan changes layout and feedback presentation only; it leaves the data model and page destinations intact.
