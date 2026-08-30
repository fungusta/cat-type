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


def open_input_monitoring_settings() -> bool:
    """Open the macOS privacy pane where Input Monitoring can be changed."""
    try:
        from AppKit import NSWorkspace
        from Foundation import NSURL

        url = NSURL.URLWithString_(
            "x-apple.systempreferences:com.apple.preference.security?"
            "Privacy_ListenEvent"
        )
        if url is None:
            return False
        return bool(NSWorkspace.sharedWorkspace().openURL_(url))
    except (AttributeError, ImportError, OSError):
        return False
