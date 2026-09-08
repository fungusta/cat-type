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
    Accessory("round-glasses", "Round glasses", "glasses", "First Steps", "keystrokes", 1_000),
    Accessory("sunglasses", "Sunglasses", "glasses", "Regular Companion", "days", 7),
    Accessory("star-glasses", "Star glasses", "glasses", "Star Typist", "keystrokes", 25_000),
    Accessory("beanie", "Beanie", "hat", "Getting Comfortable", "keystrokes", 10_000),
    Accessory("party-hat", "Party hat", "hat", "Cause for Celebration", "keystrokes", 50_000),
    Accessory("crown", "Crown", "hat", "Keyboard Royalty", "keystrokes", 100_000),
    Accessory("bow-tie", "Bow tie", "neck", "Helping Paw", "keystrokes", 5_000),
    Accessory("red-bandana", "Red bandana", "neck", "Daily Purr", "days", 30),
    Accessory("adventure-cape", "Adventure cape", "back", "Faithful Feline", "days", 100),
    Accessory("golden-wings", "Golden wings", "back", "Million Meows", "keystrokes", 1_000_000),
    Accessory("angel-wings", "Angel wings", "back", "Nine Lives", "days", 9, hidden=True),
    Accessory("moon-pendant", "Moon pendant", "neck", "Night Owl", "night_keystrokes", 1_000, hidden=True),
    Accessory("sunflower-clip", "Sunflower clip", "ears", "Early Bird", "early_keystrokes", 1_000, hidden=True),
    Accessory("cozy-scarf", "Cozy scarf", "neck", "Welcome Back", "return_gap", 7, hidden=True),
    Accessory("beta-bandana", "Beta bandana", "neck", "Beta Buddy", "beta", 1, hidden=True),
)
ACCESSORY_BY_ID = {item.id: item for item in ACCESSORIES}


def visible_accessories(unlocked: set[str]) -> tuple[Accessory, ...]:
    return tuple(item for item in ACCESSORIES if not item.hidden or item.id in unlocked)


def normalize_accessory(value: object, slot: str) -> str:
    item = ACCESSORY_BY_ID.get(value) if isinstance(value, str) else None
    return item.id if item is not None and item.slot == slot else "none"
