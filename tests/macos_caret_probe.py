"""Isolated native probe used by the macOS caret integration test."""

from __future__ import annotations

import json
import subprocess
import time

import ApplicationServices as accessibility
from AppKit import NSWorkspace

from cat_type import CaretLocator


def emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload), flush=True)


def main() -> int:
    if not accessibility.AXIsProcessTrusted():
        emit(
            {
                "status": "skipped",
                "reason": "test process lacks macOS Accessibility permission",
            }
        )
        return 0

    dialog = subprocess.Popen(
        [
            "osascript",
            "-e",
            (
                'display dialog "Cat Type caret integration test" '
                'default answer "Caret probe" '
                'with title "Cat Type Test" giving up after 5'
            ),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(0.2)
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            activation = subprocess.run(
                [
                    "osascript",
                    "-e",
                    (
                        'tell application "System Events" to set frontmost '
                        "of first process whose unix id is "
                        f"{dialog.pid} to true"
                    ),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if activation.returncode != 0:
                emit(
                    {
                        "status": "error",
                        "reason": "could not focus the test text field",
                    }
                )
                return 1
            frontmost = NSWorkspace.sharedWorkspace().frontmostApplication()
            if (
                frontmost is not None
                and frontmost.processIdentifier() == dialog.pid
            ):
                break
            time.sleep(0.05)
        else:
            emit(
                {
                    "status": "error",
                    "reason": "the test text field did not become focused",
                }
            )
            return 1

        snapshot = CaretLocator().locate()
        if snapshot.rect is None:
            emit(
                {
                    "status": "error",
                    "reason": f"provider returned {snapshot.source}",
                }
            )
            return 1
        emit(
            {
                "status": "ok",
                "source": snapshot.source,
                "width": snapshot.rect.width,
                "height": snapshot.rect.height,
            }
        )
        return 0
    finally:
        dialog.terminate()
        try:
            dialog.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            dialog.kill()
            dialog.wait(timeout=2.0)


if __name__ == "__main__":
    raise SystemExit(main())
