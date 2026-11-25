"""Notice when macOS Secure Keyboard Entry hides typing from Cat Type.

While any app has Secure Keyboard Entry on, macOS stops delivering key events
to every other app, so the cat goes quiet. Password fields turn it on briefly,
which is expected; the trouble is an app that leaves it on (Terminal's or
iTerm2's menu option, or a password prompt that never let go). This module
reports who holds it so Cat Type can say so instead of silently failing.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SecureInputState:
    enabled: bool = False
    holder_pid: int | None = None
    holder_name: str | None = None

    @property
    def holder_label(self) -> str:
        return self.holder_name or "another app"


SECURE_INPUT_OFF = SecureInputState()
_carbon = None


def _secure_event_input_enabled() -> bool:
    global _carbon
    if _carbon is None:
        _carbon = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/Carbon.framework/Carbon"
        )
        _carbon.IsSecureEventInputEnabled.restype = ctypes.c_bool
        _carbon.IsSecureEventInputEnabled.argtypes = []
    # Despite its name this reports the whole login session, not just us.
    return bool(_carbon.IsSecureEventInputEnabled())


def _holder_pid() -> int | None:
    import Quartz

    session = Quartz.CGSessionCopyCurrentDictionary()
    if session is None:
        return None
    pid = session.get("kCGSSessionSecureInputPID")
    return int(pid) if pid else None


def _app_name(pid: int) -> str | None:
    from AppKit import NSRunningApplication

    app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
    name = app.localizedName() if app is not None else None
    return str(name) if name else None


def read_secure_input_state() -> SecureInputState:
    """The current Secure Keyboard Entry state; off whenever it can't be read."""
    try:
        if not _secure_event_input_enabled():
            return SECURE_INPUT_OFF
    except (AttributeError, OSError):
        return SECURE_INPUT_OFF
    try:
        pid = _holder_pid()
        name = _app_name(pid) if pid is not None else None
    except (AttributeError, ImportError, OSError, TypeError, ValueError):
        pid, name = None, None
    return SecureInputState(True, pid, name)


@dataclass
class SecureInputWatch:
    """Decide when Secure Keyboard Entry has been on long enough to mention.

    A password field holds it for a few seconds, so only a stretch longer than
    ``notice_after`` seconds earns a notice, once per holding app per run.
    """

    notice_after: float = 30.0
    state: SecureInputState = SECURE_INPUT_OFF
    since: float | None = None
    _noticed: set[str] = field(default_factory=set)

    def update(self, state: SecureInputState, now: float) -> bool:
        """Record a reading; True when a notice should be posted now."""
        if not state.enabled:
            self.state, self.since = SECURE_INPUT_OFF, None
            return False
        if not self.state.enabled or state.holder_pid != self.state.holder_pid:
            self.since = now
        self.state = state
        key = state.holder_name or str(state.holder_pid)
        if self.since is None or now - self.since < self.notice_after or key in self._noticed:
            return False
        self._noticed.add(key)
        return True
