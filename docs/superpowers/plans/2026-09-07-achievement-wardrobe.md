# Achievement Wardrobe Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development for the artwork task and reviews; the controller implements progression and integration in this session. Steps use checkbox syntax for tracking.

**Goal:** Add a shared cat outfit with three hats, three glasses and permanent typing achievement rewards.

**Architecture:** A dependency-free accessory catalog feeds an achievement evaluator and the shared SVG renderer. A standalone Tk wardrobe component integrates into Settings; the app owns progression and persistence.

**Tech Stack:** Python, Tkinter, Pillow, resvg-py, unittest, PyInstaller.

## Global Constraints

- One shared outfit across all six cats; one hat and one glasses item, each defaulting to `none`.
- Slots persist as `hat` and `glasses` on AppSettings. Unlocks persist separately beside settings in achievements.json.
- Existing history counts. Unlocks are permanent, idempotent and never auto-equip.
- Reward catalog: round-glasses / Round glasses / glasses / First Steps / keystrokes / 1000; sunglasses / Sunglasses / glasses / Regular Companion / days / 7; star-glasses / Star glasses / glasses / Star Typist / keystrokes / 25000; beanie / Beanie / hat / Getting Comfortable / keystrokes / 10000; party-hat / Party hat / hat / Cause for Celebration / keystrokes / 50000; crown / Crown / hat / Keyboard Royalty / keystrokes / 100000.
- Reuse aggregate typing counts only. No network services or new dependencies.
- All cats retain the 120 x 120 canvas and four existing poses; preserve platform alpha behavior.
- Wardrobe selections preview immediately and apply through the existing Save button.
- Work in the isolated feature worktree; never modify actual user settings/metrics during verification.

### Task 1: Catalog, unlocks and settings

Files: create cat_accessories.py, achievements.py, tests/test_achievements.py; modify cat_settings.py and tests/test_settings.py.

Interfaces: `Accessory(id, name, slot, achievement, metric, target)` is a frozen dataclass. `ACCESSORIES` is an ordered tuple and `ACCESSORY_BY_ID` maps IDs. `normalize_accessory(value: object, slot: str) -> str` returns a valid ID or `none`. `progress(item: Accessory, metrics: UsageMetrics) -> int` clamps to target. `AchievementStore(path: Path)` loads/saves sets of known IDs atomically. `AchievementTracker(store, metrics)` exposes `unlocked: set[str]`, `evaluate(metrics) -> tuple[Accessory, ...]`, `flush() -> bool`, and `allowed(value, slot) -> str`.

- [x] Write real temporary-store tests, including the boundary below; run and observe missing feature failures.

```python
tracker = AchievementTracker(AchievementStore(path), UsageMetrics(total_keystrokes=999))
assert not tracker.unlocked
assert [item.id for item in tracker.evaluate(UsageMetrics(total_keystrokes=1000))] == ['round-glasses']
assert tracker.evaluate(UsageMetrics(total_keystrokes=1000)) == ()
assert AchievementTracker(AchievementStore(path), UsageMetrics()).unlocked == {'round-glasses'}
```

- [x] Implement catalog, sanitized persistence with atomic replacement and retryable dirty state, initialization from history, cumulative days and settings normalization.
- [x] Verify round-trip, wrong-slot normalization, invalid/malformed state, threshold boundaries, historical unlocks and write failure followed by successful retry. Commit owned files.

### Task 2: Accessory artwork and composition

Files: create assets/accessories/{round-glasses,sunglasses,star-glasses,beanie,party-hat,crown}.svg and tests/test_accessory_artwork.py; modify cat_artwork.py, CatType.spec, assets/SPRITES.md.

Interfaces: consume catalog IDs and normalization. Extend `posed_svg(source, name, *, hat='none', glasses='none')`, `vector_png(source, name, size, *, hat='none', glasses='none')`, and `load_frame(assets_root, variant, name, size, *, color_key_safe=False, hat='none', glasses='none')`. Existing no-accessory calls keep identical output. Accessory files resolve beside the vector-cats directory under assets/accessories. The root may be copying the catalog concurrently; use exact IDs above until it exists.

- [x] Write and run renderer tests showing that an outfit changes face/head pixels and preserves paws, that distinct outfits produce distinct cached output and that None matches the old renderer.

```python
plain = load_frame(ASSETS, 'white', 'idle', 120)
dressed = load_frame(ASSETS, 'white', 'idle', 120, hat='crown', glasses='round-glasses')
assert plain.tobytes() != dressed.tobytes()
assert plain.crop((0, 74, 120, 120)).tobytes() == dressed.crop((0, 74, 120, 120)).tobytes()
```

- [x] Draw editable original SVG accessories with matching bold rounded linework. Keep hats inside canvas, glasses aligned to eyes for every cat and the mouth visible. Avoid raster images or external SVG references.
- [x] Add composition before rasterization with hat/glasses in cache keys; validate IDs and slot without a progression dependency. Preserve alpha behavior and empty outfit. Bundle assets and document editing.
- [x] Render all six cats/four poses at 72, 120 and 210 pixels with accessories; verify transparent borders and stable upper-head alignment. Export a contact sheet in .debug and inspect it. Run focused existing artwork tests and commit only owned files.

### Task 3: Wardrobe and app integration

Files: create wardrobe_view.py, tests/test_wardrobe.py, tests/test_wardrobe_integration.py; modify settings_window.py, cat_type.py, README.md.

Interfaces: `WardrobeView(parent, *, assets_root, hat, glasses, unlocked, metrics, on_change, palette, fonts)` holds item widgets and refreshes through `update_progress(metrics, unlocked, newly_unlocked=())`; selected slot variables belong to SettingsWindow. SettingsWindow accepts `unlocked_accessories: set[str] | None = None`, exposes `update_achievements(unlocked, newly_unlocked=())`, renders both previews from equipped selections, and includes slots in saved settings. App initialization owns AchievementTracker and clamps saved outfits through `allowed`; live accepted key activity evaluates rules and updates UI plus nonblocking tray notice. Persist failures retry with existing usage flushes. Frame rebuilding triggers for size or outfit changes. Linux masks use equipped slots.

- [x] Write failing tests for locked choices, selecting None, real preview changes, saved shared outfit, cancellation, live unlocking, paused activity and load-frame outfit propagation.

```python
window.hat.set('crown')
window.glasses.set('round-glasses')
window._save()
assert saved[-1].hat == 'crown'
assert saved[-1].glasses == 'round-glasses'
```

- [x] Build the wardrobe with thumbnails, one choice per slot, requirement/progress text, shared animated preview, scrollable layout and a compact unlock notice.
- [x] Integrate persistence, enabled-key evaluation, historical startup rewards, safe optional tray notifications and all platform render paths. Retain existing settings save/cancel behavior.
- [x] Run focused wardrobe/app tests; document rewards and preview/apply behavior. Commit owned files.

### Task 4: Review and delivery

- [x] Run the full unittest suite from the feature worktree using the shared .venv Python.
- [x] Inspect Wardrobe at normal and narrow sizes with temporary data, plus all accessory combinations in rendered artwork; verify changes do not clip or cover the mouth.
- [x] Review spec compliance and code quality with a separate reviewer; resolve actionable findings.
- [x] Build with PyInstaller from the feature worktree and inspect bundled accessory entries; do not publish a release.
- [x] Record test and visual evidence, then integrate the verified feature into the original clean checkout and leave it ready to run.
