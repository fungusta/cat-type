"""Verify that a PyInstaller executable contains its runtime icon."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Collection
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader

from platform_assets import icon_filename, runtime_modules


def expected_icon_entry(platform: str) -> str:
    return f"assets/{icon_filename(platform)}"


def external_bundle_entries(executable: Path, platform: str) -> tuple[str, ...]:
    if platform != "darwin":
        return ()
    resources = executable.parent.parent / "Resources"
    if not resources.is_dir():
        return ()
    return tuple(
        path.relative_to(resources).as_posix()
        for path in resources.rglob("*")
        if path.is_file()
    )


def validate_bundled_icon(entries: Collection[str], platform: str) -> str:
    expected = expected_icon_entry(platform)
    normalized_entries = {entry.replace("\\", "/") for entry in entries}
    if expected not in normalized_entries:
        raise ValueError(f"PyInstaller archive is missing {expected}")
    return expected


def validate_bundled_runtime_modules(
    modules: Collection[str],
    platform: str,
) -> tuple[str, ...]:
    expected = runtime_modules(platform)
    missing = tuple(module for module in expected if module not in modules)
    if missing:
        raise ValueError(
            "PyInstaller archive is missing runtime modules: "
            + ", ".join(missing)
        )
    return expected


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify the runtime icon in a PyInstaller executable."
    )
    parser.add_argument("executable", type=Path)
    args = parser.parse_args()
    archive = CArchiveReader(str(args.executable))
    try:
        entries = set(archive.toc)
        entries.update(external_bundle_entries(args.executable, sys.platform))
        expected = validate_bundled_icon(entries, sys.platform)
        expected_modules = runtime_modules(sys.platform)
        if expected_modules:
            pyz = archive.open_embedded_archive("PYZ.pyz")
            validate_bundled_runtime_modules(pyz.toc, sys.platform)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Verified bundled runtime icon: {expected}")
    if expected_modules:
        print(
            "Verified bundled runtime modules: "
            + ", ".join(expected_modules)
        )


if __name__ == "__main__":
    main()
