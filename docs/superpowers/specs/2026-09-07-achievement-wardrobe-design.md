# Achievement wardrobe

Approved direction: a Wardrobe page with separate SVG hats and glasses, permanent
achievement unlocks, previews, and credit for existing typing history. Use one
shared outfit across all six cats, including Alternate. Each slot permits None.

## Rewards

| ID | Slot | Name | Achievement | Requirement |
| --- | --- | --- | --- | --- |
| round-glasses | glasses | Round glasses | First Steps | 1,000 total keystrokes |
| sunglasses | glasses | Sunglasses | Regular Companion | Type on 7 different local days |
| star-glasses | glasses | Star glasses | Star Typist | 25,000 total keystrokes |
| beanie | hat | Beanie | Getting Comfortable | 10,000 total keystrokes |
| party-hat | hat | Party hat | Cause for Celebration | 50,000 total keystrokes |
| crown | hat | Crown | Keyboard Royalty | 100,000 total keystrokes |

Days need not be consecutive. Count days with at least one recorded keystroke.
Existing aggregate history grants eligible rewards at startup. Never revoke an
earned reward when metrics later decrease. Newly earned rewards never equip
automatically. No additional input content is collected.

## Components and persistence

`cat_accessories.py` is the dependency-free catalog and slot validation boundary.
`achievements.py` evaluates catalog rules from UsageMetrics and atomically saves
unlocked IDs to `achievements.json` beside settings.json. Malformed saved data
falls back safely, unknown IDs are ignored, failed saves remain dirty and retry
on existing periodic/shutdown flushes. Settings store the equipped `hat` and
`glasses` IDs; absent, invalid, wrong-slot, or locked selections resolve to None.

The app initializes progression before loading frames, evaluates after accepted
enabled key activity, refreshes an open wardrobe, and attempts one nonblocking
tray notice per newly unlocked batch. Unsupported tray notifications do not
interrupt typing. The Wardrobe shows a small notice while open. Historical
startup unlocks appear in the wardrobe without a burst of tray messages.

## Artwork

Store six editable SVGs in `assets/accessories`, using the cats' 120 x 120 view
box. Compose glasses and then hats above the posed cat before rasterization.
Heads remain still in all four poses. Include both accessory IDs in the render
cache key, preserve empty-outfit output, transparency and color-key handling.
All app rendering surfaces, settings previews and Linux shape masks use the same
composed renderer. Keep accessory silhouettes within the existing canvas and
the eyes and mouth legible at 60%, 100% and 175%. Bundle assets in PyInstaller.

## Wardrobe

Add Wardrobe beside Settings and Metrics. Show a shared animated cat preview,
Hat and Glasses choices including None, item thumbnails, achievement names,
explicit requirements and bounded progress. Locked items cannot be equipped.
Selecting an unlocked item updates the preview; the existing Save button applies
the outfit and other settings together. Closing without Save discards selection.
Live unlocks enable choices without reopening the window. Use the existing
scrolling, keyboard navigation and color/font system. Keep detailed wardrobe
widgets in `wardrobe_view.py` to avoid further growing settings_window.py.

## Verification

Test threshold boundaries, history migration, nonconsecutive days, permanent and
idempotent unlocks, malformed state, save failure/retry and locked selection
rejection. Verify rendering across every cat, pose and supported preview size,
cache distinction, unchanged paws and correct Linux masks. Exercise real Tk
wardrobe selection, save/cancel and live unlocks; run the complete existing test
suite and inspect a composed contact sheet and Wardrobe screenshot. Build a local
Windows executable to verify bundled accessory assets. No release is requested.
