"""Shared accessory catalog; independent of rendering and saved progression."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Accessory:
    id: str
    name: str
    slot: str
    achievement: str
    metric: str
    target: int
    hidden: bool = False


ACCESSORY_SLOTS = ("hat", "glasses", "neck", "back", "ears")
SLOT_LABELS = {"hat": "Hats", "glasses": "Glasses", "neck": "Neckwear", "back": "Back accessories", "ears": "Ear accessories"}


ACCESSORIES = (
    # Total typing milestones, from the first session to long-term goals.
    Accessory("ribbon-clip", "Ribbon clip", "ears", "A Little Flair", "keystrokes", 250),
    Accessory("round-glasses", "Round glasses", "glasses", "First Steps", "keystrokes", 1_000),
    Accessory("bell-collar", "Bell collar", "neck", "Bells and Whiskers", "keystrokes", 2_500),
    Accessory("bow-tie", "Bow tie", "neck", "Helping Paw", "keystrokes", 5_000),
    Accessory("beanie", "Beanie", "hat", "Getting Comfortable", "keystrokes", 10_000),
    Accessory("leaf-sprout", "Leaf sprout", "ears", "Growing Together", "keystrokes", 15_000),
    Accessory("star-glasses", "Star glasses", "glasses", "Star Typist", "keystrokes", 25_000),
    Accessory("party-hat", "Party hat", "hat", "Cause for Celebration", "keystrokes", 50_000),
    Accessory("travel-satchel", "Travel satchel", "back", "Packed for Adventure", "keystrokes", 75_000),
    Accessory("crown", "Crown", "hat", "Keyboard Royalty", "keystrokes", 100_000),
    Accessory("pixel-glasses", "Pixel glasses", "glasses", "Pixel Purrfect", "keystrokes", 150_000),
    Accessory("wizard-hat", "Wizard hat", "hat", "Spellbound", "keystrokes", 250_000),
    Accessory("dragon-wings", "Dragon wings", "back", "Here Be Dragons", "keystrokes", 500_000),
    Accessory("golden-wings", "Golden wings", "back", "Million Meows", "keystrokes", 1_000_000),
    Accessory("royal-cape", "Royal cape", "back", "Legendary Companion", "keystrokes", 2_000_000),
    # Active days are cumulative, never a consecutive-day streak.
    Accessory("daisy-clip", "Daisy clip", "ears", "Budding Friendship", "days", 3),
    Accessory("sunglasses", "Sunglasses", "glasses", "Regular Companion", "days", 7),
    Accessory("aviator-goggles", "Aviator goggles", "glasses", "Taking Flight", "days", 14),
    Accessory("red-bandana", "Red bandana", "neck", "Daily Purr", "days", 30),
    Accessory("sailor-hat", "Sailor hat", "hat", "Steady Sailing", "days", 60),
    Accessory("adventure-cape", "Adventure cape", "back", "Faithful Feline", "days", 100),
    Accessory("laurel-wreath", "Laurel wreath", "hat", "A Year of Purrs", "days", 365),
    # Discoveries are omitted from both tabs until earned.
    Accessory("angel-wings", "Angel wings", "back", "Nine Lives", "days", 9, hidden=True),
    Accessory("moon-pendant", "Moon pendant", "neck", "Night Owl", "night_keystrokes", 1_000, hidden=True),
    Accessory("sunflower-clip", "Sunflower clip", "ears", "Early Bird", "early_keystrokes", 1_000, hidden=True),
    Accessory("cozy-scarf", "Cozy scarf", "neck", "Welcome Back", "return_gap", 7, hidden=True),
    Accessory("beta-bandana", "Beta bandana", "neck", "Beta Buddy", "beta", 1, hidden=True),
    Accessory("shooting-star-clip", "Shooting star clip", "ears", "Written in the Stars", "night_keystrokes", 10_000, hidden=True),
    Accessory("sunrise-scarf", "Sunrise scarf", "neck", "Rise and Shine", "early_keystrokes", 10_000, hidden=True),
    Accessory("butterfly-wings", "Butterfly wings", "back", "Metamorphosis", "days", 42, hidden=True),
)
ACCESSORY_BY_ID = {item.id: item for item in ACCESSORIES}


def visible_accessories(unlocked: set[str]) -> tuple[Accessory, ...]:
    return tuple(item for item in ACCESSORIES if not item.hidden or item.id in unlocked)


def normalize_accessory(value: object, slot: str) -> str:
    item = ACCESSORY_BY_ID.get(value) if isinstance(value, str) else None
    return item.id if item is not None and item.slot == slot else "none"
