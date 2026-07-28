"""Ensure a release tag matches all platform package metadata."""

from __future__ import annotations

import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_release_version.py vMAJOR.MINOR.PATCH")

    expected = sys.argv[1].removeprefix("v")
    if not re.fullmatch(r"\d+\.\d+\.\d+", expected):
        raise SystemExit(f"invalid release version: {expected}")

    checks = {
        PROJECT_ROOT / "CatType.spec": f'version="{expected}"',
        PROJECT_ROOT / "packaging" / "CatType.iss": (
            f'#define MyAppVersion "{expected}"'
        ),
        PROJECT_ROOT / "packaging" / "version_info.txt": (
            f"StringStruct('ProductVersion', '{expected}')"
        ),
    }
    mismatches = [
        str(path.relative_to(PROJECT_ROOT))
        for path, marker in checks.items()
        if marker not in path.read_text(encoding="utf-8")
    ]
    if mismatches:
        raise SystemExit(
            f"tag v{expected} does not match version metadata in: "
            + ", ".join(mismatches)
        )


if __name__ == "__main__":
    main()
