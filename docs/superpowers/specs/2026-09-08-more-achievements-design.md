# More achievements and items

Expand the existing 15 achievement/item pairs to 30. Add early rewards, fill
the gap between 100,000 and 1,000,000 keystrokes, and provide more choices for
all five outfit slots, particularly ears and back accessories.

## Approach

Extend the shared catalog and editable SVG assets. This fits the established
progression, automatically supports both settings tabs and all platforms, and
credits existing history. Alternatives considered were adding new activity
metrics or introducing a shop; both add mechanics beyond this content expansion.

## Public additions

| Item | Slot | Achievement | Requirement |
| --- | --- | --- | --- |
| Ribbon clip | ears | A Little Flair | 250 total keystrokes |
| Bell collar | neck | Bells and Whiskers | 2,500 total keystrokes |
| Leaf sprout | ears | Growing Together | 15,000 total keystrokes |
| Travel satchel | back | Packed for Adventure | 75,000 total keystrokes |
| Pixel glasses | glasses | Pixel Purrfect | 150,000 total keystrokes |
| Wizard hat | hat | Spellbound | 250,000 total keystrokes |
| Dragon wings | back | Here Be Dragons | 500,000 total keystrokes |
| Royal cape | back | Legendary Companion | 2,000,000 total keystrokes |
| Daisy clip | ears | Budding Friendship | 3 different active days |
| Aviator goggles | glasses | Taking Flight | 14 different active days |
| Sailor hat | hat | Steady Sailing | 60 different active days |
| Laurel wreath | hat | A Year of Purrs | 365 different active days |

## Secret additions

| Item | Slot | Achievement | Requirement |
| --- | --- | --- | --- |
| Shooting star clip | ears | Written in the Stars | 10,000 keystrokes from midnight to 4 a.m. |
| Sunrise scarf | neck | Rise and Shine | 10,000 keystrokes from 5 to 8 a.m. |
| Butterfly wings | back | Metamorphosis | 42 different active days |

Secrets stay absent from both tabs and their totals until earned. Times use
existing local hourly buckets; active days need not be consecutive. Unlocks
remain permanent, never auto-equip, and use the existing save schema. The stable
build's beta eligibility stays unchanged.

## Artwork and verification

Use original editable shapes in standalone 120-by-120 SVGs, matching existing
outlines and pastel colors. Hats and ear items avoid the face; neckwear sits
below the mouth and behind paws; back items remain visible around the silhouette.
Each asset uses its catalog ID as its root artwork group ID, without external
references or raster images.

The bell collar's band uses `data-clip-to-body="true"` so the shared renderer
fits it to each cat's outline. Only the band is clipped; its bell hangs freely,
and the existing paw layering is preserved. This avoids protruding side corners
across the slightly different cat silhouettes.

Run achievement, wardrobe, integration, and rendering tests. Verify all items
at 60%, 100%, and 175%, all six cats, and all four poses using the shared renderer.
Inspect a contact sheet for silhouette, clipping, layering, and readability.
Update README with public rewards and artwork guidance for all five slots.
