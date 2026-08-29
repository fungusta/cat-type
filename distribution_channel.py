"""Identify behavior that differs between direct and App Store builds."""

from __future__ import annotations

import os
import plistlib
import sys
from pathlib import Path


APP_STORE_CHANNEL = "app-store"
DIRECT_CHANNEL = "direct"


def distribution_channel(
    *,
    platform_name: str | None = None,
    executable: Path | None = None,
    frozen: bool | None = None,
) -> str:
    """Return the packaged distribution channel without relying on launch env."""
    override = os.environ.get("CAT_TYPE_DISTRIBUTION_CHANNEL")
    if override in {APP_STORE_CHANNEL, DIRECT_CHANNEL}:
        return override

    current_platform = sys.platform if platform_name is None else platform_name
    is_frozen = (
        bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    )
    if current_platform != "darwin" or not is_frozen:
        return DIRECT_CHANNEL

    executable_path = Path(sys.executable) if executable is None else executable
    info_plist = executable_path.parent.parent / "Info.plist"
    try:
        payload = plistlib.loads(info_plist.read_bytes())
    except (OSError, ValueError, TypeError):
        return DIRECT_CHANNEL
    return (
        APP_STORE_CHANNEL
        if payload.get("CatTypeDistributionChannel") == APP_STORE_CHANNEL
        else DIRECT_CHANNEL
    )


def is_app_store_build(**kwargs: object) -> bool:
    return distribution_channel(**kwargs) == APP_STORE_CHANNEL
