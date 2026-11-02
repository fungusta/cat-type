"""Pure, zero-based pagination shared by collection views."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class PageWindow:
    index: int
    page_count: int
    start: int
    end: int


def page_window(total_items: int, page_index: int, page_size: int) -> PageWindow:
    """Clamp the requested page and return its half-open item bounds."""
    if total_items < 0:
        raise ValueError("total_items must be non-negative")
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    page_count = (total_items + page_size - 1) // page_size
    if not page_count:
        return PageWindow(0, 0, 0, 0)
    index = min(max(0, page_index), page_count - 1)
    start = index * page_size
    return PageWindow(index, page_count, start, min(start + page_size, total_items))


def page_slice(items: Sequence[T], page_index: int, page_size: int) -> tuple[T, ...]:
    window = page_window(len(items), page_index, page_size)
    return tuple(items[window.start:window.end])


def page_label(window: PageWindow) -> str:
    return f"Page {window.index + 1 if window.page_count else 0} of {window.page_count}"
