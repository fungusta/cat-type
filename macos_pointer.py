"""Privacy-safe recent-click tracking for macOS pointer placement."""

from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class PointerClick:
    x: float
    y: float
    happened_at: float


class RecentPointerClick:
    """Retain only the latest pointer coordinate for a short placement window."""

    def __init__(self, max_age_seconds: float = 8.0) -> None:
        self.max_age_seconds = max(0.0, float(max_age_seconds))
        self._latest: PointerClick | None = None
        self._lock = threading.Lock()

    def record(
        self,
        x: float,
        y: float,
        happened_at: float | None = None,
    ) -> None:
        click = PointerClick(
            x=float(x),
            y=float(y),
            happened_at=(
                time.monotonic() if happened_at is None else happened_at
            ),
        )
        with self._lock:
            self._latest = click

    def latest(self, now: float | None = None) -> PointerClick | None:
        checked_at = time.monotonic() if now is None else now
        with self._lock:
            click = self._latest
            if click is None:
                return None
            age = checked_at - click.happened_at
            if age < 0.0:
                return None
            if age > self.max_age_seconds:
                self._latest = None
                return None
            return click


class MacOSPointerMonitor:
    """Record primary pointer presses without inspecting their UI targets."""

    def __init__(self, recent_click: RecentPointerClick, debug: bool = False) -> None:
        self._recent_click = recent_click
        self._debug = debug
        self._listener: object | None = None

    def start(self) -> bool:
        if self._listener is not None:
            return True
        try:
            from pynput import mouse

            def on_click(
                x: float,
                y: float,
                button: object,
                pressed: bool,
            ) -> None:
                if pressed and button == mouse.Button.left:
                    self._recent_click.record(x, y)

            listener = mouse.Listener(on_click=on_click)
            listener.start()
            self._listener = listener
            return True
        except Exception as exc:
            self._listener = None
            if self._debug:
                print(
                    f"Pointer click monitoring unavailable: {exc}",
                    file=sys.stderr,
                )
            return False

    def stop(self) -> None:
        listener = self._listener
        self._listener = None
        if listener is None:
            return
        try:
            listener.stop()
            listener.join(timeout=1.0)
        except Exception as exc:
            if self._debug:
                print(
                    f"Could not stop pointer click monitoring: {exc}",
                    file=sys.stderr,
                )
