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


ACCESSORIES = (
    Accessory("round-glasses", "Round glasses", "glasses", "First Steps", "keystrokes", 1_000),
    Accessory("sunglasses", "Sunglasses", "glasses", "Regular Companion", "days", 7),
    Accessory("star-glasses", "Star glasses", "glasses", "Star Typist", "keystrokes", 25_000),
    Accessory("beanie", "Beanie", "hat", "Getting Comfortable", "keystrokes", 10_000),
    Accessory("party-hat", "Party hat", "hat", "Cause for Celebration", "keystrokes", 50_000),
    Accessory("crown", "Crown", "hat", "Keyboard Royalty", "keystrokes", 100_000),
)
ACCESSORY_BY_ID = {item.id: item for item in ACCESSORIES}


def normalize_accessory(value: object, slot: str) -> str:
    item = ACCESSORY_BY_ID.get(value) if isinstance(value, str) else None
    return item.id if item is not None and item.slot == slot else "none"
