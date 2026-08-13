"""Exercise the graceful shutdown event in a packaged Windows executable."""

from __future__ import annotations

import argparse
import ctypes
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path


EVENT_MODIFY_STATE = 0x0002


def run_shutdown_smoke(executable: Path, timeout: float = 30.0) -> None:
    if sys.platform != "win32":
        raise RuntimeError("the Windows package smoke requires Windows")
    executable = executable.resolve(strict=True)
    process = subprocess.Popen([str(executable), "--debug"], shell=False)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_event = kernel32.OpenEventW
    set_event = kernel32.SetEvent
    close_handle = kernel32.CloseHandle
    open_event.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    open_event.restype = wintypes.HANDLE
    set_event.argtypes = [wintypes.HANDLE]
    set_event.restype = wintypes.BOOL
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    handle = None
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            status = process.poll()
            if status is not None:
                raise RuntimeError(
                    f"Windows package exited with status {status} before "
                    "creating its shutdown event"
                )
            handle = open_event(
                EVENT_MODIFY_STATE,
                False,
                "Local\\CatTypeShutdown",
            )
            if handle:
                break
            time.sleep(0.1)
        if not handle:
            raise RuntimeError("Windows package did not create its shutdown event")
        if not set_event(handle):
            raise OSError(ctypes.get_last_error(), "SetEvent failed")
        remaining = max(0.1, deadline - time.monotonic())
        try:
            status = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(
                "Windows package did not exit after its shutdown event"
            ) from error
        if status != 0:
            raise RuntimeError(
                f"Windows package exited with status {status} after shutdown"
            )
    finally:
        if handle:
            close_handle(handle)
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Smoke test a packaged Windows Cat Type shutdown event."
    )
    parser.add_argument("executable", type=Path)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    try:
        run_shutdown_smoke(args.executable, args.timeout)
    except (OSError, RuntimeError) as error:
        raise SystemExit(str(error)) from error
    print("Windows package shutdown smoke passed.")


if __name__ == "__main__":
    main()
