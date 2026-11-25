"""Compile the macOS update swap helper that ships inside Cat Type.app."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
HELPER_SOURCE = PROJECT_ROOT / "packaging" / "macos_update_helper.c"


def build_update_helper(output: Path) -> Path:
    """Compile the helper with the Xcode toolchain and return its path."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "xcrun",
            "clang",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-mmacosx-version-min=12.0",
            "-o",
            str(output),
            str(HELPER_SOURCE),
        ],
        check=True,
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    print(build_update_helper(parser.parse_args().output))


if __name__ == "__main__":
    main()
