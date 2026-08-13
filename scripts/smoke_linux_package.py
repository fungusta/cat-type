"""Launch a Linux package briefly and reject fatal startup diagnostics."""

from __future__ import annotations

import argparse
import os
import subprocess
from collections.abc import Sequence
from pathlib import Path


FAILURE_DIAGNOSTICS = (
    "Could not install the keyboard activity listener",
    "Keyboard listener unavailable:",
    "ModuleNotFoundError:",
    "ImportError:",
    "Update startup failed:",
    "Exception in Tkinter callback",
)


def ensure_clean_startup_output(output: str) -> None:
    for diagnostic in FAILURE_DIAGNOSTICS:
        if diagnostic in output:
            raise RuntimeError(f"package startup emitted: {diagnostic}")


def run_startup_smoke(
    command: Sequence[str],
    duration: float = 5.0,
) -> str:
    environment = {**os.environ, "CAT_TYPE_DEBUG": "1"}
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=environment,
    )
    try:
        output, _ = process.communicate(timeout=duration)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            output, _ = process.communicate(timeout=2.0)
        except subprocess.TimeoutExpired:
            process.kill()
            output, _ = process.communicate()
        ensure_clean_startup_output(output)
        return output

    ensure_clean_startup_output(output)
    raise RuntimeError(
        f"package exited with status {process.returncode} during startup"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Smoke test a packaged Linux Cat Type executable."
    )
    parser.add_argument("executable", type=Path)
    parser.add_argument("--duration", type=float, default=5.0)
    args = parser.parse_args()
    try:
        output = run_startup_smoke(
            [str(args.executable), "--debug"],
            duration=args.duration,
        )
    except (OSError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc
    if output:
        print(output.rstrip())
    print(f"Linux package startup smoke passed ({args.duration:g} seconds).")


if __name__ == "__main__":
    main()
