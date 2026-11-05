"""Run the CI unittest matrix and expose failures as GitHub annotations."""

from __future__ import annotations

import codecs
from contextlib import contextmanager
import io
import os
import queue
import re
import signal
import subprocess
import sys
import threading
import time


TEST_MODULES = (
    "tests.test_ci_runner",
    "tests.test_macos_overlay_focus",
    "tests.test_macos_pointer",
    "tests.test_behavior",
    "tests.test_settings",
    "tests.test_cat_artwork",
    "tests.test_achievements",
    "tests.test_achievements_layout",
    "tests.test_accessory_artwork",
    "tests.test_wardrobe",
    "tests.test_wardrobe_integration",
    "tests.test_cat_comparison",
    "tests.test_vector_platform_surfaces",
    "tests.test_ui_surfaces",
    "tests.test_overlay_rendering",
    "tests.test_usage_metrics",
    "tests.test_settings_window",
    "tests.test_window_chrome",
    "tests.test_startup_performance",
    "tests.test_platform_assets",
    "tests.test_bundled_icon_check",
    "tests.test_package_smoke",
    "tests.test_site_build",
    "tests.test_download_report",
    "tests.test_release_version_check",
    "tests.test_auto_update",
    "tests.test_update_controller",
    "tests.test_platform_updater",
    "tests.test_windows_installer_contract",
)


def _escape_annotation(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


@contextmanager
def _test_process(command: list[str]):
    """Own a process tree, including Windows children whose parent has exited."""
    options = dict(stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
    if os.name != "nt":
        with subprocess.Popen(command, start_new_session=True, **options) as process:
            yield process, None
        return

    import ctypes
    from ctypes import wintypes

    class BasicLimits(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BasicLimits),
            ("IoInfo", ctypes.c_ulonglong * 6),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.TerminateJobObject.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    resume = ctypes.WinDLL("ntdll").NtResumeProcess
    resume.argtypes = [wintypes.HANDLE]
    resume.restype = wintypes.LONG

    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        limits = ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        # Assignment precedes execution, so even a fast-exiting parent cannot
        # create descendants outside our job. Popen owns the process handle.
        with subprocess.Popen(command, creationflags=0x4, **options) as process:
            try:
                if not kernel.AssignProcessToJobObject(job, int(process._handle)):
                    raise ctypes.WinError(ctypes.get_last_error())
                status = resume(int(process._handle))
                if status < 0:
                    raise OSError(f"NtResumeProcess failed with NTSTATUS {status & 0xffffffff:#x}")

                def terminate_job():
                    if not kernel.TerminateJobObject(job, 124):
                        raise ctypes.WinError(ctypes.get_last_error())

                yield process, terminate_job
            finally:
                # Also handles exceptions before the suspended process resumes.
                kernel.TerminateJobObject(job, 124)
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)
    finally:
        kernel.CloseHandle(job)


def _run_streaming(command: list[str], *, timeout: float = 480) -> tuple[int, str]:
    """Tee merged output immediately and bound the child process lifetime."""
    timed_out = False
    with _test_process(command) as (process, terminate_job):
        def kill_tests() -> None:
            if terminate_job is not None:
                terminate_job()
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

        assert process.stdout is not None
        pipe = process.stdout
        # The reader owns the handle. Popen.__exit__ must not close a pipe
        # while a Windows ReadFile is blocked on an orphaned descendant.
        process.stdout = None
        pending: queue.Queue[bytes | None] = queue.Queue()
        stop_reading = threading.Event()

        def read_output() -> None:
            try:
                while data := pipe.read(4096):
                    if stop_reading.is_set():
                        break
                    pending.put(data)
            finally:
                pipe.close()
                pending.put(None)

        # EOF can be held open by an orphaned descendant. Keep pipe reads off
        # the controlling thread so the deadline never depends on EOF.
        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        deadline = time.monotonic() + timeout
        chunks = []
        decoder = io.IncrementalNewlineDecoder(
            codecs.getincrementaldecoder("utf-8")(errors="replace"), translate=True,
        )
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(command, timeout)
                try:
                    data = pending.get(timeout=remaining)
                except queue.Empty:
                    raise subprocess.TimeoutExpired(command, timeout) from None
                text = decoder.decode(data or b"", final=data is None)
                if text:
                    chunks.append(text)
                    print(text, end="", flush=True)
                if data is None:
                    break
            returncode = process.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            timed_out = True
            kill_tests()
            returncode = process.wait(timeout=5)
            # Preserve traceback bytes already queued or still in the pipe.
            # An escaped descendant must not turn this drain into another hang.
            drain_deadline = time.monotonic() + .5
            while time.monotonic() < drain_deadline:
                try:
                    data = pending.get(timeout=max(0, drain_deadline - time.monotonic()))
                except queue.Empty:
                    break
                if data is None:
                    break
                text = decoder.decode(data)
                if text:
                    chunks.append(text)
                    print(text, end="", flush=True)
            stop_reading.set()
            text = decoder.decode(b"", final=True)
            if text:
                chunks.append(text)
                print(text, end="", flush=True)
        finally:
            if process.poll() is None:
                kill_tests()
                process.wait(timeout=5)
    if timed_out:
        print(
            f"::error title=Test timeout::unittest exceeded {timeout:g} seconds",
            flush=True,
        )
        returncode = 124
    return returncode, "".join(chunks)


def _test_command(modules: list[str], *, traceback_interval: float = 60) -> list[str]:
    # Run inside the child so a blocked native/UI call still yields Python stacks.
    bootstrap = (
        "import faulthandler, runpy; "
        f"faulthandler.dump_traceback_later({traceback_interval!r}, repeat=True); "
        "runpy.run_module('unittest', run_name='__main__')"
    )
    return [sys.executable, "-u", "-X", "utf8", "-c", bootstrap, *modules, "-v"]


def main() -> int:
    modules = list(TEST_MODULES)
    if sys.platform.startswith("linux"):
        modules.append("tests.test_linux_update_integration")
    returncode, output = _run_streaming(_test_command(modules))
    if returncode:
        failures = []
        headers = list(re.finditer(r"^(?:FAIL|ERROR): (.+)$", output, re.MULTILINE))
        for index, header in enumerate(headers):
            end = headers[index + 1].start() if index + 1 < len(headers) else len(output)
            body = output[header.end():end]
            body_lines = body.splitlines()
            detail = ""
            for line_index, line in enumerate(body_lines):
                if re.match(r"(?:AssertionError|[A-Za-z]+Error):", line.strip()):
                    detail = line.strip()
                    for extra in body_lines[line_index + 1:]:
                        extra = extra.strip()
                        if extra.startswith(":"):
                            detail += " " + extra[1:].strip()
                        elif extra.startswith(("- ", "+ ")):
                            continue
                        elif extra:
                            break
                    break
            failures.append(header.group(1) + (f" — {detail}" if detail else ""))
        if not failures:
            failures = [f"unittest exited with code {returncode}"]
        for failure in failures:
            print(
                "::error title=Automated test failure::"
                + _escape_annotation(failure)
            )
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
