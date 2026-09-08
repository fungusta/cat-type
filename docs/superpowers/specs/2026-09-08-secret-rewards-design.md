# Expanded achievement rewards

Approved direction: every achievement unlocks an equippable item; hidden
achievements and their items are absent until earned. Start with neckwear,
back accessories and ear accessories alongside hats and glasses. Beta Buddy
belongs to anyone who runs a designated beta build and survives stable upgrades.

## New rewards

| Item ID | Name | Slot | Achievement | Rule | Hidden |
| --- | --- | --- | --- | --- | --- |
| bow-tie | Bow tie | neck | Helping Paw | 5,000 total keystrokes | No |
| red-bandana | Red bandana | neck | Daily Purr | 30 active local days | No |
| adventure-cape | Adventure cape | back | Faithful Feline | 100 active local days | No |
| golden-wings | Golden wings | back | Million Meows | 1,000,000 total keystrokes | No |
| angel-wings | Angel wings | back | Nine Lives | 9 active local days | Yes |
| moon-pendant | Moon pendant | neck | Night Owl | 1,000 cumulative keystrokes during local hours 00–03 | Yes |
| sunflower-clip | Sunflower clip | ears | Early Bird | 1,000 cumulative keystrokes during local hours 05–07 | Yes |
| cozy-scarf | Cozy scarf | neck | Welcome Back | Two active dates separated by at least 7 full inactive dates | Yes |
| beta-bandana | Beta bandana | neck | Beta Buddy | Run a build explicitly designated beta | Yes |

Keep the original six rewards and their saved IDs unchanged. Days need not be
consecutive. Existing aggregate history counts, including historical return gaps.
Use existing local hourly/daily buckets; never inspect text, key identities or apps.

## Behavior and data

Keep the one-item-per-achievement catalog; add a hidden flag and explicit metric
rules. Beta is a build entitlement, never an implicit fallback for unknown metric
names. `app_version.IS_BETA_BUILD` explicitly designates this development preview;
future stable builds set it false. Inject eligibility into the tracker so tests
and non-beta builds cannot accidentally award it. Its stored unlock is permanent.

Settings add `neck`, `back`, and `ears`, defaulting to `none`. Each slot permits
one item and remains compatible with other slots. Invalid or locked choices are
rejected consistently in preview, Save, and application startup. Preserve atomic
storage, save retries, history migration, and Save/Cancel behavior.

Both views show only public items plus earned hidden items. Hidden entries leave
no names, thumbnails, requirements, gaps or counted placeholders. Visible totals
include revealed secrets only. Reveal a newly earned secret immediately without
reopening or resetting pending outfit choices. Keep wardrobe grids at no more
than three columns. Omit empty slot sections. Link each item to its achievement.

Compose back items behind the cat, neckwear above the body but below paws, then
glasses, hats, and ear clips. Preserve face and typing paws. Extend every cached
rendering and platform surface to include all five slots. All art stays within
the existing 120×120 SVG view box and remains legible at supported sizes.

## Validation and delivery

Check threshold boundaries, hour ranges, inactive-day gaps, beta eligibility,
permanence, old-save migration, malformed state, and unknown metric rejection.
Test secrecy in both tabs, live reveal, navigation, pending selections, and
multislot Save/Cancel. Inspect all new items and representative combinations
across cats/poses/sizes; verify masks and native cache invalidation. Run the full
suite, review the diff, build and verify a local Windows beta preview. No public
release is requested. Public README describes secret discovery without spoilers.
