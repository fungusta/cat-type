"""Small, testable wrappers around macOS Input Monitoring permission APIs."""

from __future__ import annotations


def preflight_input_monitoring() -> bool:
    try:
        import Quartz

        return bool(Quartz.CGPreflightListenEventAccess())
    except (AttributeError, ImportError, OSError):
        return False


def request_input_monitoring() -> bool:
    try:
        import Quartz

        return bool(Quartz.CGRequestListenEventAccess())
    except (AttributeError, ImportError, OSError):
        return False
