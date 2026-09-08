"""Permanent local rewards from aggregate activity and explicit beta eligibility."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from cat_accessories import ACCESSORIES, ACCESSORY_BY_ID, Accessory, normalize_accessory
from usage_metrics import UsageMetrics


def progress(item: Accessory, metrics: UsageMetrics, *, beta_eligible: bool = False) -> int:
    if item.metric == "days":
        count = sum(count > 0 for count in metrics.daily.values())
    elif item.metric == "keystrokes":
        count = metrics.total_keystrokes
    elif item.metric in {"night_keystrokes", "early_keystrokes"}:
        hours = {"00", "01", "02", "03"} if item.metric == "night_keystrokes" else {"05", "06", "07"}
        count = sum(max(0, count) for hour, count in metrics.hourly.items() if hour[-2:] in hours)
    elif item.metric == "return_gap":
        days = sorted(date.fromisoformat(day) for day, count in metrics.daily.items() if count > 0)
        count = max(((later - earlier).days - 1 for earlier, later in zip(days, days[1:])), default=0)
    elif item.metric == "beta":
        count = int(beta_eligible)
    else:
        raise ValueError(f"Unknown achievement metric: {item.metric}")
    return min(item.target, max(0, count))


def requirement(item: Accessory) -> str:
    if item.metric == "keystrokes":
        return f"{item.target:,} total keystrokes"
    if item.metric == "days":
        return f"Type on {item.target} different days"
    if item.metric == "night_keystrokes":
        return f"{item.target:,} keystrokes between midnight and 4 a.m."
    if item.metric == "early_keystrokes":
        return f"{item.target:,} keystrokes between 5 and 8 a.m."
    if item.metric == "return_gap":
        return f"Return after {item.target} full inactive days"
    if item.metric == "beta":
        return "Run a designated beta build"
    raise ValueError(f"Unknown achievement metric: {item.metric}")


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
    def __init__(self, store: AchievementStore, metrics: UsageMetrics, *, beta_eligible: bool = False) -> None:
        self.store = store
        self.beta_eligible = beta_eligible
        self.unlocked = store.load()
        self._dirty = False
        self._progress: dict[str, int] = {}
        self._last_total: int | None = None
        self._latest_active_day: date | None = None
        # Honor old activity silently; initialization never sends notifications.
        self.evaluate(metrics)

    def evaluate(self, metrics: UsageMetrics, *, recorded_at: datetime | None = None) -> tuple[Accessory, ...]:
        # The live caller supplies the timestamp of exactly one newly recorded
        # key. Imports, nonsequential totals, and clock rollback use full history.
        day = recorded_at.date() if recorded_at is not None else None
        incremental = (
            day is not None and self._last_total is not None
            and metrics.total_keystrokes == self._last_total + 1
            and (self._latest_active_day is None or day >= self._latest_active_day)
        )
        earned = []
        for item in ACCESSORIES:
            if item.id in self.unlocked:
                continue
            if incremental and item.id in self._progress:
                current = self._progress_after_key(item, metrics, recorded_at)
            else:
                current = progress(item, metrics, beta_eligible=self.beta_eligible)
            self._progress[item.id] = current
            if current >= item.target:
                earned.append(item)
        self._last_total = metrics.total_keystrokes
        if incremental:
            self._latest_active_day = day
        else:
            self._latest_active_day = max(
                (date.fromisoformat(key) for key, count in metrics.daily.items() if count > 0), default=None,
            )
        newly_unlocked = tuple(earned)
        if newly_unlocked:
            self.unlocked.update(item.id for item in newly_unlocked)
            self._dirty = True
            self.flush()
        return newly_unlocked

    def _progress_after_key(self, item: Accessory, metrics: UsageMetrics, when: datetime) -> int:
        previous = self._progress[item.id]
        if item.metric == "keystrokes":
            value = metrics.total_keystrokes
        elif item.metric == "days":
            value = previous + int(metrics.daily.get(when.strftime("%Y-%m-%d")) == 1)
        elif item.metric == "night_keystrokes":
            value = previous + int(0 <= when.hour < 4)
        elif item.metric == "early_keystrokes":
            value = previous + int(5 <= when.hour < 8)
        elif item.metric == "return_gap":
            gap = (when.date() - self._latest_active_day).days - 1 if self._latest_active_day else 0
            value = max(previous, gap)
        else:
            value = progress(item, metrics, beta_eligible=self.beta_eligible)
        return min(item.target, max(0, value))

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
