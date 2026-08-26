# Metrics Chart Views and v1.0.17 Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users switch the Metrics chart between an exact straight line and columns, remember that choice, and publish the verified change as Cat Type v1.0.17.

**Architecture:** Add the view preference to the existing normalized `AppSettings` model. Keep one Metrics canvas and one range/data path, then select a focused line or column mark renderer after shared axis scaling. `SettingsWindow` redraws immediately and sends only the view value to `CatTypeApp`, which persists it without capturing unrelated unsaved controls.

**Tech Stack:** Python 3.12, Tkinter `Canvas`, `unittest`, GitHub Actions, GitHub CLI.

## Global Constraints

- Valid chart views are exactly `line` and `columns`; `line` is the default.
- Line rendering uses straight segments and exact point markers; Tk smoothing is never enabled.
- Both views work independently with `1d`, `7d`, and `30d`; the initial range remains `7d`.
- Switching views persists only `metrics_view` immediately and does not save unrelated Settings controls.
- The Metrics data format and privacy behavior do not change.
- Do not add tooltips, per-point labels, new ranges, persisted range selection, export, new metrics, or a third chart style.
- Release version is `1.0.17` with annotated tag `v1.0.17`.

---

## File Structure

- Modify `cat_settings.py`: define, normalize, load, and save the chart-view preference.
- Modify `settings_window.py`: expose the Line/Columns segmented control and render exact line or column marks on the existing canvas.
- Modify `cat_type.py`: persist view-only changes through the existing `SettingsStore` without applying unsaved window controls.
- Modify `tests/test_settings.py`: cover preference defaults, normalization, backward compatibility, and round trips.
- Modify `tests/test_settings_window.py`: cover control independence, exact line geometry, column geometry, rendering tags, and save behavior.
- Modify `tests/test_behavior.py`: cover the narrow persistence callback and Settings-window wiring.
- Modify `README.md`: describe the selectable Metrics views and update the release-tag example.
- Modify `app_version.py`, `CatType.spec`, `packaging/CatType.iss`, and `packaging/version_info.txt`: align runtime and package metadata to v1.0.17.
- Modify `tests/test_release_version_check.py`: make v1.0.17 the accepted version and v1.0.16 the rejected prior version.

---

### Task 1: Persist the chart-view preference

**Files:**
- Modify: `cat_settings.py`
- Test: `tests/test_settings.py`

**Interfaces:**
- Produces: `VALID_METRICS_VIEWS: tuple[str, str]` and `AppSettings.metrics_view: str`.
- Produces: `AppSettings.normalized()` guarantees `metrics_view in {"line", "columns"}`.

- [ ] **Step 1: Write failing model and store tests**

Add these assertions to `AppSettingsTests`:

```python
def test_metrics_view_defaults_to_line_and_normalizes_invalid_values(self) -> None:
    self.assertEqual(AppSettings().metrics_view, "line")
    self.assertEqual(AppSettings(metrics_view="columns").normalized().metrics_view, "columns")
    self.assertEqual(AppSettings(metrics_view="curve").normalized().metrics_view, "line")

def test_store_round_trips_metrics_view_and_defaults_older_files(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "settings.json"
        path.write_text('{"enabled": true}', encoding="utf-8")
        self.assertEqual(SettingsStore(path).load().metrics_view, "line")

        settings = SettingsStore(path).save(AppSettings(metrics_view="columns"))
        self.assertEqual(settings.metrics_view, "columns")
        self.assertEqual(SettingsStore(path).load().metrics_view, "columns")
```

- [ ] **Step 2: Run the settings tests and confirm the red state**

Run: `python -m unittest tests.test_settings -v`

Expected: errors report that `AppSettings` has no `metrics_view` field.

- [ ] **Step 3: Add and normalize the setting**

Add the valid values and field in `cat_settings.py`, then include the normalized value in the returned settings object:

```python
VALID_METRICS_VIEWS = ("line", "columns")

@dataclass
class AppSettings:
    enabled: bool = True
    cat_style: str = "alternate"
    size_percent: int = 100
    hold_seconds: float = 1.5
    fade_seconds: float = 0.35
    placement: str = "above-right"
    launch_at_startup: bool = False
    metrics_view: str = "line"

    def normalized(self) -> "AppSettings":
        metrics_view = (
            self.metrics_view
            if self.metrics_view in VALID_METRICS_VIEWS
            else AppSettings.metrics_view
        )
        # Preserve the existing cat_style, placement, timing, and size normalization.
        return AppSettings(
            enabled=bool(self.enabled),
            cat_style=cat_style,
            size_percent=min(175, max(60, int(self.size_percent))),
            hold_seconds=round(hold_seconds, 2),
            fade_seconds=round(fade_seconds, 2),
            placement=placement,
            launch_at_startup=bool(self.launch_at_startup),
            metrics_view=metrics_view,
        )
```

- [ ] **Step 4: Run the focused tests and confirm green**

Run: `python -m unittest tests.test_settings -v`

Expected: all `tests.test_settings` tests pass.

- [ ] **Step 5: Commit the preference model**

```bash
git add cat_settings.py tests/test_settings.py
git commit -m "feat: persist metrics chart view"
```

---

### Task 2: Add the view control and truthful renderers

**Files:**
- Modify: `settings_window.py`
- Test: `tests/test_settings_window.py`

**Interfaces:**
- Consumes: `AppSettings.metrics_view` from Task 1.
- Produces: `SettingsWindow.metrics_view: tk.StringVar` and `metrics_view_buttons: dict[str, tk.Radiobutton]`.
- Produces: `_metric_column_positions(values, width, height, *, left, right, top, bottom) -> list[tuple[float, float, float]]` where each tuple is `(x, baseline, value_y)`.
- Produces: canvas item tags `metric-line`, `metric-point`, and `metric-column` for stable rendering tests.
- Consumes: optional `on_metrics_view_change: Callable[[str], None]` passed to `SettingsWindow`.

- [ ] **Step 1: Write failing geometry and UI behavior tests**

Extend `SettingsWindowTkLayoutTests.setUp` with a `Mock` callback passed as `on_metrics_view_change`. Add tests equivalent to:

```python
def test_metric_column_positions_center_discrete_buckets(self) -> None:
    self.assertEqual(
        SettingsWindow._metric_column_positions(
            [0, 50, 100], 300, 200,
            left=40, right=20, top=20, bottom=30,
        ),
        [(80.0, 170, 170.0), (160.0, 170, 95.0), (240.0, 170, 20.0)],
    )

def test_metrics_view_switches_without_resetting_range(self) -> None:
    today = datetime.now().astimezone().date()
    self.settings_window.update_usage_metrics(
        UsageMetrics(
            total_keystrokes=30,
            daily={today.isoformat(): 30},
            hourly={f"{today.isoformat()}T09": 30},
        )
    )
    self.settings_window.active_page.set("Metrics")
    self.settings_window._switch_page()
    self.settings_window.window.update()

    self.assertEqual(self.settings_window.metrics_view.get(), "line")
    self.assertEqual(set(self.settings_window.metrics_view_buttons), {"line", "columns"})
    line_id = self.settings_window.metrics_chart.find_withtag("metric-line")[0]
    self.assertEqual(self.settings_window.metrics_chart.itemcget(line_id, "smooth"), "0")

    self.settings_window.metrics_range_days.set(1)
    self.settings_window.metrics_view.set("columns")
    self.settings_window._change_metrics_view()

    self.assertEqual(self.settings_window.metrics_range_days.get(), 1)
    self.on_metrics_view_change.assert_called_once_with("columns")
    self.assertTrue(self.settings_window.metrics_chart.find_withtag("metric-column"))
    self.assertFalse(self.settings_window.metrics_chart.find_withtag("metric-line"))

    self.settings_window.metrics_range_days.set(30)
    self.settings_window._change_metrics_range()
    self.assertEqual(self.settings_window.metrics_view.get(), "columns")
```

Add this save-path test, with `self.on_save = Mock()` passed to
`SettingsWindow` from `setUp`:

```python
def test_save_includes_the_selected_metrics_view(self) -> None:
    self.settings_window.metrics_view.set("columns")

    self.settings_window._save()

    saved = self.on_save.call_args.args[0]
    self.assertEqual(saved.metrics_view, "columns")
```

- [ ] **Step 2: Run the focused UI tests and confirm the red state**

Run: `xvfb-run --auto-servernum python -m unittest tests.test_settings_window -v`

Expected: failures report the missing view variable, buttons, callback, column-position helper, and canvas tags.

- [ ] **Step 3: Add constructor state and the View segmented control**

Insert the callback parameter between the existing usage metrics and update
callbacks, store it with the other callbacks, and initialize the view variable:

```python
usage_metrics: UsageMetrics | None = None,
on_metrics_view_change: Callable[[str], None] | None = None,
on_check_for_updates: Callable[[], None] | None = None,
on_open_release_page: Callable[[], None] | None = None,
update_status: str = "",
on_close: Callable[[], None] | None = None,

# In __init__ with the existing callback assignments:
    self._on_save = on_save
    self._on_metrics_view_change = on_metrics_view_change

# With the existing Tk variables:
    self.metrics_range_days = tk.IntVar(value=7)
    self.metrics_view = tk.StringVar(value=settings.metrics_view)
```

Build `Range` and `View` as separately labelled groups in the Activity-card
header. Keep the existing range radiobuttons, and create the new buttons with
the existing selected/unselected palette:

```python
self.metrics_view_buttons: dict[str, tk.Radiobutton] = {}
for index, (label, value) in enumerate((('Line', 'line'), ('Columns', 'columns'))):
    button = tk.Radiobutton(
        view_group,
        text=label,
        variable=self.metrics_view,
        value=value,
        command=self._change_metrics_view,
        indicatoron=False,
        relief="flat",
        borderwidth=0,
        highlightthickness=1,
        highlightbackground=self.BORDER,
        background=self.BLUSH,
        selectcolor=self.PEACH,
        activebackground=self.PEACH,
        foreground=self.INK,
        font=self.fonts["small"],
        padx=12,
        pady=5,
        cursor="hand2",
        takefocus=True,
    )
    button.grid(row=0, column=index)
    self.metrics_view_buttons[value] = button
```

Add a side-effect-free style refresh plus the user-change handler, and include
`metrics_view=self.metrics_view.get()` in `_save`:

```python
def _refresh_metrics_view_buttons(self) -> None:
    selected = self.metrics_view.get()
    for view, button in self.metrics_view_buttons.items():
        button.configure(
            background=self.PEACH if view == selected else self.BLUSH,
            foreground=self.ACCENT_DARK if view == selected else self.INK,
        )

def _change_metrics_view(self) -> None:
    self._refresh_metrics_view_buttons()
    self._draw_metrics()
    if self._on_metrics_view_change is not None:
        self._on_metrics_view_change(self.metrics_view.get())
```

- [ ] **Step 4: Implement exact line and column mark geometry**

Add the pure column helper beside `_metric_line_positions`:

```python
@staticmethod
def _metric_column_positions(
    values: list[int],
    width: int,
    height: int,
    *,
    left: int,
    right: int,
    top: int,
    bottom: int,
) -> list[tuple[float, float, float]]:
    if not values:
        return []
    usable_width = max(1, width - left - right)
    usable_height = max(1, height - top - bottom)
    maximum = max(1, max(values))
    step = usable_width / len(values)
    baseline = height - bottom
    return [
        (
            left + step * (index + 0.5),
            baseline,
            baseline - usable_height * value / maximum,
        )
        for index, value in enumerate(values)
    ]
```

In `_draw_metrics`, retain shared data, scale, grid, label, and empty-state
logic. Select mark positions and draw exactly one treatment:

```python
if self.metrics_view.get() == "columns":
    column_positions = self._metric_column_positions(
        values, width, height,
        left=left, right=right, top=top, bottom=bottom,
    )
    label_positions = [(x, y) for x, _baseline, y in column_positions]
    step = (width - left - right) / max(1, len(values))
    bar_width = max(3, min(22, step * 0.56))
    if maximum:
        for value, (x, column_baseline, y) in zip(values, column_positions):
            if value:
                canvas.create_line(
                    x, column_baseline, x, y,
                    fill=self.ACCENT_DARK,
                    width=bar_width,
                    capstyle="round",
                    tags=("metric-column",),
                )
else:
    line_positions = self._metric_line_positions(
        values, width, height,
        left=left, right=right, top=top, bottom=bottom,
    )
    label_positions = line_positions
    if maximum and len(line_positions) > 1:
        canvas.create_line(
            *[coordinate for point in line_positions for coordinate in point],
            fill=self.ACCENT_DARK,
            width=3,
            smooth=False,
            capstyle="round",
            joinstyle="round",
            tags=("metric-line",),
        )
        for x, y in line_positions:
            canvas.create_oval(
                x - 3, y - 3, x + 3, y + 3,
                fill=self.ACCENT_DARK,
                outline=self.CARD,
                width=1,
                tags=("metric-point",),
            )
```

Use `label_positions` for the existing x-axis label loop. Call
`_refresh_metrics_view_buttons()` after building the View buttons and whenever
the Metrics page opens; do not call `_change_metrics_view()` during
construction or page opening because that method persists a user action.

- [ ] **Step 5: Run the UI and settings tests**

Run: `xvfb-run --auto-servernum python -m unittest tests.test_settings_window tests.test_settings -v`

Expected: all focused tests pass, including exact `smooth == 0` and column rendering.

- [ ] **Step 6: Commit the Metrics UI**

```bash
git add settings_window.py tests/test_settings_window.py
git commit -m "feat: switch metrics chart views"
```

---

### Task 3: Persist view-only changes from the application

**Files:**
- Modify: `cat_type.py`
- Test: `tests/test_behavior.py`

**Interfaces:**
- Consumes: `SettingsWindow(on_metrics_view_change=...)` from Task 2.
- Produces: `CatTypeApp._persist_metrics_view(metrics_view: str) -> None`.

- [ ] **Step 1: Write failing application-wiring tests**

Add these behaviors to `CatTypeKeyActivityTests`:

```python
def test_metrics_view_persistence_does_not_capture_unsaved_controls(self) -> None:
    app = CatTypeApp.__new__(CatTypeApp)
    app.settings = AppSettings(size_percent=125, metrics_view="line")
    app.settings_store = Mock()
    app.settings_store.save.side_effect = lambda settings: settings.normalized()

    app._persist_metrics_view("columns")

    saved = app.settings_store.save.call_args.args[0]
    self.assertEqual(saved.metrics_view, "columns")
    self.assertEqual(saved.size_percent, 125)
    self.assertEqual(app.settings.metrics_view, "columns")

def test_metrics_view_write_failure_leaves_application_usable(self) -> None:
    app = CatTypeApp.__new__(CatTypeApp)
    app.settings = AppSettings(metrics_view="line")
    app.settings_store = Mock()
    app.settings_store.save.side_effect = OSError("read-only settings")

    app._persist_metrics_view("columns")

    self.assertEqual(app.settings.metrics_view, "line")
```

Extend `test_open_settings_receives_the_persistent_metrics` with:

```python
self.assertEqual(keywords["on_metrics_view_change"], app._persist_metrics_view)
```

- [ ] **Step 2: Run the behavior tests and confirm the red state**

Run: `python -m unittest tests.test_behavior.CatTypeKeyActivityTests -v`

Expected: failures report the missing `_persist_metrics_view` method and constructor keyword.

- [ ] **Step 3: Implement and wire the narrow persistence callback**

Add this method beside `apply_settings` and pass it to `SettingsWindow` in
`open_settings`:

```python
def _persist_metrics_view(self, metrics_view: str) -> None:
    updated = AppSettings(
        **{
            **self.settings.__dict__,
            "metrics_view": metrics_view,
        }
    ).normalized()
    try:
        self.settings = self.settings_store.save(updated)
    except OSError:
        return
```

```python
self._settings_window = SettingsWindow(
    self.root,
    self.settings,
    self.apply_settings,
    str(APP_ICON) if APP_ICON.exists() else None,
    keystroke_count=self.keystroke_count,
    usage_metrics=(
        self.usage_tracker.metrics
        if getattr(self, "usage_tracker", None) is not None
        else UsageMetrics(total_keystrokes=self.keystroke_count)
    ),
    on_metrics_view_change=self._persist_metrics_view,
    on_check_for_updates=lambda: self.check_for_updates(manual=True),
    on_open_release_page=lambda: webbrowser.open(
        _UnavailableUpdateInstaller.RELEASES_URL
    ),
    update_status=getattr(
        self,
        "_update_status",
        "Ready to check for updates.",
    ),
    on_close=self._return_to_macos_background_policy,
)
```

- [ ] **Step 4: Run behavior, settings, and window tests**

Run: `xvfb-run --auto-servernum python -m unittest tests.test_behavior tests.test_settings tests.test_settings_window -v`

Expected: all focused tests pass.

- [ ] **Step 5: Commit application persistence**

```bash
git add cat_type.py tests/test_behavior.py
git commit -m "feat: remember metrics chart view"
```

---

### Task 4: Document and fully verify the feature

**Files:**
- Modify: `README.md`
- Verify: all runtime and test files from Tasks 1-3

**Interfaces:**
- Consumes: complete chart-view feature.
- Produces: user-facing feature documentation and a locally verified feature commit.

- [ ] **Step 1: Update the Settings feature description**

Replace the existing Metrics bullet with:

```markdown
- View all-time activity and 1-day, 7-day, or 30-day trends as an exact line
  or columns; Cat Type remembers the selected chart view.
```

- [ ] **Step 2: Run the complete Linux CI-equivalent test selection**

Run:

```bash
xvfb-run --auto-servernum python -m unittest \
  tests.test_macos_overlay_focus \
  tests.test_behavior \
  tests.test_settings \
  tests.test_usage_metrics \
  tests.test_settings_window \
  tests.test_platform_assets \
  tests.test_bundled_icon_check \
  tests.test_package_smoke \
  tests.test_release_version_check \
  tests.test_auto_update \
  tests.test_update_controller \
  tests.test_platform_updater \
  tests.test_windows_installer_contract \
  tests.test_linux_update_integration \
  -v
```

Expected: every selected test passes with no failures or errors.

- [ ] **Step 3: Request and address code review**

Invoke the `requesting-code-review` skill against the feature branch diff from
its merge base with `main`. Fix any valid Standards or Spec findings, rerun the
affected focused tests, and repeat review until no blocking findings remain.

- [ ] **Step 4: Commit documentation or review fixes**

```bash
git add README.md cat_settings.py settings_window.py cat_type.py \
  tests/test_settings.py tests/test_settings_window.py tests/test_behavior.py
git commit -m "docs: describe selectable metrics views"
```

If review fixes changed code after that commit, commit those fixes separately
with a focused `fix:` message.

---

### Task 5: Prepare v1.0.17 metadata

**Files:**
- Modify: `app_version.py`
- Modify: `CatType.spec`
- Modify: `packaging/CatType.iss`
- Modify: `packaging/version_info.txt`
- Modify: `tests/test_release_version_check.py`
- Modify: `README.md`

**Interfaces:**
- Produces: all package metadata accepted by `python scripts/check_release_version.py v1.0.17`.

- [ ] **Step 1: Update the release-check test first**

Change accepted values in `tests/test_release_version_check.py` to `1.0.17`
and prior-version rejection values to `1.0.16`:

```python
def test_current_version_matches_every_platform_marker(self) -> None:
    self.assertEqual(APP_VERSION, "1.0.17")
    self.assertEqual(metadata_mismatches("1.0.17", PROJECT_ROOT), [])
    self.assertNotEqual(metadata_mismatches("1.0.16", PROJECT_ROOT), [])
```

- [ ] **Step 2: Run the release-check test and confirm the red state**

Run: `python -m unittest tests.test_release_version_check -v`

Expected: current version and metadata assertions fail at `1.0.16`.

- [ ] **Step 3: Align every version-bearing file**

Set these exact values:

```text
app_version.py: APP_VERSION: str = "1.0.17"
CatType.spec: version="1.0.17"
packaging/CatType.iss: #define MyAppVersion "1.0.17"
packaging/version_info.txt: filevers=(1, 0, 17, 0)
packaging/version_info.txt: prodvers=(1, 0, 17, 0)
packaging/version_info.txt: StringStruct('FileVersion', '1.0.17')
packaging/version_info.txt: StringStruct('ProductVersion', '1.0.17')
README.md: example tag v1.0.17
```

- [ ] **Step 4: Verify release metadata and the complete suite**

Run: `python scripts/check_release_version.py v1.0.17`

Expected: exit 0 with no output.

Run: `python scripts/check_release_version.py v1.0.16`

Expected: non-zero exit listing every version-bearing metadata file.

Run the complete Linux CI-equivalent test selection from Task 4 again.

Expected: every selected test passes with version 1.0.17.

- [ ] **Step 5: Commit release preparation**

```bash
git add app_version.py CatType.spec packaging/CatType.iss \
  packaging/version_info.txt tests/test_release_version_check.py README.md
git commit -m "release: prepare Cat Type 1.0.17"
```

---

### Task 6: Integrate, push, and publish v1.0.17

**Files:**
- No source changes expected.
- External state: `origin/main`, annotated tag `v1.0.17`, GitHub Actions, and GitHub Release.

**Interfaces:**
- Consumes: reviewed, locally verified v1.0.17 release commit.
- Produces: successful cross-platform main build and published v1.0.17 release with six expected assets.

- [ ] **Step 1: Integrate the isolated branch into local main**

Invoke `finishing-a-development-branch`. With a clean worktree and all tests
green, fast-forward local `main` to the feature branch:

```bash
git switch main
git merge --ff-only feature/metrics-chart-views
```

Expected: `main` points at the verified v1.0.17 release commit and remains clean.

- [ ] **Step 2: Push main and verify the cross-platform build**

```bash
git push origin main
```

Use `gh run list` to identify the `Cross-platform build` run for the pushed
commit, then `gh run watch <run-id> --exit-status`.

Expected: Windows x64, macOS Intel, and Linux x64 build jobs all succeed.

- [ ] **Step 3: Create and push the immutable annotated tag**

Confirm `git rev-parse HEAD`, `git rev-parse origin/main`, and the successful
workflow `headSha` are identical. Then run:

```bash
git tag -a v1.0.17 -m "Cat Type v1.0.17"
git push origin v1.0.17
```

Expected: the tag is created once on the exact tested main commit.

- [ ] **Step 4: Verify the tag-triggered Release workflow**

Use `gh run list` to identify the `Release` run whose `headBranch` is
`v1.0.17`, then run `gh run watch <run-id> --exit-status`.

Expected: all five build-matrix jobs and the publish job succeed. Do not move,
delete, or recreate the tag if a post-tag job fails.

- [ ] **Step 5: Audit the published GitHub Release**

Run:

```bash
gh release view v1.0.17 \
  --json tagName,isDraft,isPrerelease,url,assets
```

Expected: `tagName` is `v1.0.17`, `isDraft` and `isPrerelease` are false, and
the asset names are exactly:

```text
Cat-Type-Windows-x64.exe
Cat-Type-macOS-x64.dmg
Cat-Type-macOS-arm64.dmg
Cat-Type-Linux-x64.tar.gz
Cat-Type-Linux-arm64.tar.gz
SHA256SUMS.txt
```

- [ ] **Step 6: Final completion audit**

Confirm the local worktree is clean, `main`, `origin/main`, and `v1.0.17`
resolve to the same commit, the cross-platform build and release workflows are
successful, and the public release has all six assets. Only then report the
implementation, tests, push, and release as complete.
