"""Privacy-preserving, persistent keystroke activity metrics."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from cat_settings import default_settings_path


USAGE_VERSION = 1
DEFAULT_FLUSH_THRESHOLD = 50
DAY_KEY_FORMAT = "%Y-%m-%d"
HOUR_KEY_FORMAT = "%Y-%m-%dT%H"


def default_usage_path() -> Path:
    return default_settings_path().with_name("usage.json")


def _clean_count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(0, value)


def _clean_buckets(
    value: object,
    key_format: str,
) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    cleaned: dict[str, int] = {}
    for key, count in value.items():
        if not isinstance(key, str):
            continue
        try:
            datetime.strptime(key, key_format)
        except ValueError:
            continue
        cleaned_count = _clean_count(count)
        if cleaned_count:
            cleaned[key] = cleaned_count
    return cleaned


@dataclass
class UsageMetrics:
    """Aggregate activity counts without any key or text content."""

    total_keystrokes: int = 0
    daily: dict[str, int] = field(default_factory=dict)
    hourly: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: object) -> "UsageMetrics":
        if not isinstance(payload, dict):
            return cls()
        return cls(
            total_keystrokes=_clean_count(payload.get("total_keystrokes")),
            daily=_clean_buckets(payload.get("daily"), DAY_KEY_FORMAT),
            hourly=_clean_buckets(payload.get("hourly"), HOUR_KEY_FORMAT),
        ).normalized()

    def normalized(self) -> "UsageMetrics":
        daily = _clean_buckets(self.daily, DAY_KEY_FORMAT)
        hourly = _clean_buckets(self.hourly, HOUR_KEY_FORMAT)
        hourly_by_day: dict[str, int] = {}
        for hour_key, count in hourly.items():
            day_key = hour_key[:10]
            hourly_by_day[day_key] = hourly_by_day.get(day_key, 0) + count
        for day_key, count in hourly_by_day.items():
            daily[day_key] = max(daily.get(day_key, 0), count)
        return UsageMetrics(
            total_keystrokes=max(
                _clean_count(self.total_keystrokes),
                sum(daily.values()),
                sum(hourly.values()),
            ),
            daily=daily,
            hourly=hourly,
        )

    def record(self, when: datetime) -> None:
        if when.tzinfo is None:
            when = when.astimezone()
        day_key = when.strftime(DAY_KEY_FORMAT)
        hour_key = when.strftime(HOUR_KEY_FORMAT)
        self.total_keystrokes += 1
        self.daily[day_key] = self.daily.get(day_key, 0) + 1
        self.hourly[hour_key] = self.hourly.get(hour_key, 0) + 1

    def count_for_day(self, day: date) -> int:
        return self.daily.get(day.strftime(DAY_KEY_FORMAT), 0)

    def daily_series(
        self,
        days: int,
        *,
        ending_on: date,
    ) -> list[tuple[date, int]]:
        days = max(1, days)
        first_day = ending_on - timedelta(days=days - 1)
        return [
            (day := first_day + timedelta(days=offset), self.count_for_day(day))
            for offset in range(days)
        ]

    def hourly_series(self, day: date) -> list[int]:
        day_key = day.strftime(DAY_KEY_FORMAT)
        return [
            self.hourly.get(f"{day_key}T{hour:02d}", 0)
            for hour in range(24)
        ]

    def to_payload(self) -> dict[str, Any]:
        normalized = self.normalized()
        return {
            "version": USAGE_VERSION,
            "total_keystrokes": normalized.total_keystrokes,
            "daily": normalized.daily,
            "hourly": normalized.hourly,
        }


class UsageStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_usage_path()

    def load(self) -> UsageMetrics:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return UsageMetrics()
        return UsageMetrics.from_payload(payload)

    def save(self, metrics: UsageMetrics) -> UsageMetrics:
        normalized = metrics.normalized()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                normalized.to_payload(),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)
        return normalized


class UsageTracker:
    """Own in-memory recording and bounded, atomic persistence."""

    def __init__(
        self,
        store: UsageStore | None = None,
        *,
        now: Callable[[], datetime] | None = None,
        flush_threshold: int = DEFAULT_FLUSH_THRESHOLD,
    ) -> None:
        self.store = store or UsageStore()
        self.now = now or (lambda: datetime.now().astimezone())
        self.flush_threshold = max(1, flush_threshold)
        self.metrics = self.store.load()
        self.pending_keystrokes = 0

    def record(self) -> UsageMetrics:
        self.metrics.record(self.now())
        self.pending_keystrokes += 1
        if self.pending_keystrokes >= self.flush_threshold:
            self.flush()
        return self.metrics

    def flush(self) -> bool:
        if not self.pending_keystrokes:
            return True
        try:
            self.metrics = self.store.save(self.metrics)
        except OSError:
            return False
        self.pending_keystrokes = 0
        return True
