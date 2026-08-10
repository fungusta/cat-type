"""Verify that a PyInstaller executable contains its runtime icon."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Collection
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader

from platform_assets import icon_filename


def expected_icon_entry(platform: str) -> str:
    return f"assets/{icon_filename(platform)}"


def validate_bundled_icon(entries: Collection[str], platform: str) -> str:
    expected = expected_icon_entry(platform)
    if expected not in entries:
        raise ValueError(f"PyInstaller archive is missing {expected}")
    return expected


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify the runtime icon in a PyInstaller executable."
    )
    parser.add_argument("executable", type=Path)
    args = parser.parse_args()
    archive = CArchiveReader(str(args.executable))
    try:
        expected = validate_bundled_icon(archive.toc, sys.platform)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Verified bundled runtime icon: {expected}")


if __name__ == "__main__":
    main()
