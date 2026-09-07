"""Permanent local rewards derived exclusively from aggregate typing activity."""

from __future__ import annotations

import json
from pathlib import Path

from cat_accessories import ACCESSORIES, ACCESSORY_BY_ID, Accessory, normalize_accessory
from usage_metrics import UsageMetrics


def progress(item: Accessory, metrics: UsageMetrics) -> int:
    count = (
        sum(count > 0 for count in metrics.daily.values())
        if item.metric == "days"
        else metrics.total_keystrokes
    )
    return min(item.target, max(0, count))


class AchievementStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> set[str]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return set()
        values = payload.get("unlocked") if isinstance(payload, dict) else None
        if not isinstance(values, list):
            return set()
        return {value for value in values if isinstance(value, str) and value in ACCESSORY_BY_ID}

    def save(self, unlocked: set[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"version": 1, "unlocked": sorted(unlocked & ACCESSORY_BY_ID.keys())}, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)


class AchievementTracker:
    def __init__(self, store: AchievementStore, metrics: UsageMetrics) -> None:
        self.store = store
        self.unlocked = store.load()
        self._dirty = False
        # Honor old activity silently; initialization never sends notifications.
        self.evaluate(metrics)

    def evaluate(self, metrics: UsageMetrics) -> tuple[Accessory, ...]:
        newly_unlocked = tuple(
            item for item in ACCESSORIES
            if item.id not in self.unlocked and progress(item, metrics) >= item.target
        )
        if newly_unlocked:
            self.unlocked.update(item.id for item in newly_unlocked)
            self._dirty = True
            self.flush()
        return newly_unlocked

    def flush(self) -> bool:
        if self._dirty:
            try:
                self.store.save(self.unlocked)
            except OSError:
                return False
            self._dirty = False
        return True

    def allowed(self, value: object, slot: str) -> str:
        item_id = normalize_accessory(value, slot)
        return item_id if item_id in self.unlocked else "none"
