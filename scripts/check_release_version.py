"""Ensure a release tag matches all platform package metadata."""

from __future__ import annotations

import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def metadata_mismatches(
    expected: str,
    project_root: Path = PROJECT_ROOT,
) -> list[str]:
    """Return project-relative metadata paths that do not match *expected*."""
    major, minor, patch = expected.split(".")
    checks = {
        project_root / "app_version.py": [f'APP_VERSION: str = "{expected}"'],
        project_root / "CatType.spec": [f'version="{expected}"'],
        project_root / "packaging" / "CatType.iss": [
            f'#define MyAppVersion "{expected}"'
        ],
        project_root / "packaging" / "version_info.txt": [
            f"filevers=({major}, {minor}, {patch}, 0)",
            f"prodvers=({major}, {minor}, {patch}, 0)",
            f"StringStruct('FileVersion', '{expected}')",
            f"StringStruct('ProductVersion', '{expected}')",
        ],
    }
    return [
        str(path.relative_to(project_root))
        for path, markers in checks.items()
        if not all(marker in path.read_text(encoding="utf-8") for marker in markers)
    ]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_release_version.py vMAJOR.MINOR.PATCH")

    expected = sys.argv[1].removeprefix("v")
    if not re.fullmatch(r"\d+\.\d+\.\d+", expected):
        raise SystemExit(f"invalid release version: {expected}")

    mismatches = metadata_mismatches(expected)
    if mismatches:
        raise SystemExit(
            f"tag v{expected} does not match version metadata in: "
            + ", ".join(mismatches)
        )


if __name__ == "__main__":
    main()
