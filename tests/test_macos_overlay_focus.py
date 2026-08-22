import os
import re
import subprocess
import time
import unittest

from cat_type import (
    IS_MACOS,
    CaretSnapshot,
    CatTypeApp,
    ScreenRect,
    _macos_activation_policy_accessors_for_app,
)


@unittest.skipUnless(IS_MACOS, "requires the macOS window manager")
class MacOSOverlayFocusTests(unittest.TestCase):
    def test_showing_overlay_does_not_activate_cat_type(self) -> None:
        frontmost_before = self._frontmost_pid()
        if frontmost_before == os.getpid():
            self.skipTest("Cat Type was already the frontmost application")
        app = CatTypeApp(hold_seconds=10.0)
        try:
            self._activate_app(frontmost_before)
            activation_policy = _macos_activation_policy_accessors_for_app()
            assert activation_policy is not None
            previous_policy = activation_policy[0]()
            self.assertEqual(
                previous_policy,
                2,
                "Cat Type used a regular Dock policy while idle",
            )

            now = time.monotonic()
            app.animation.record_key(now, "left")
            app._show(
                CaretSnapshot(
                    captured_at=now,
                    rect=ScreenRect(600, 400, 602, 420),
                    source="focus-regression",
                ),
                now,
            )
            self._run_event_loop(app.root, 0.25)

            self.assertEqual(
                self._frontmost_pid(),
                frontmost_before,
                "showing the cat overlay activated Cat Type",
            )
            app._hide()
            self.assertEqual(
                activation_policy[0](),
                2,
                "Cat Type restored a regular Dock policy after hiding",
            )
        finally:
            activation_policy = _macos_activation_policy_accessors_for_app()
            if activation_policy is not None:
                activation_policy[1](0)
            app.root.destroy()
            self._activate_app(frontmost_before)

    def test_showing_overlay_is_ordered_above_foreground_app(self) -> None:
        frontmost_pid = self._frontmost_pid()
        if frontmost_pid == os.getpid():
            self.skipTest("Cat Type was already the frontmost application")
        app = CatTypeApp(hold_seconds=10.0)
        try:
            self._activate_app(frontmost_pid)
            activation_policy = _macos_activation_policy_accessors_for_app()
            assert activation_policy is not None
            caret = ScreenRect(600, 400, 602, 420)
            now = time.monotonic()
            app.animation.record_key(now, "left")
            app._show(
                CaretSnapshot(
                    captured_at=now,
                    rect=caret,
                    source="render-regression",
                ),
                now,
            )
            self._run_event_loop(app.root, 0.25)

            ordered_windows = self._ordered_normal_windows()
            cat_indices = [
                index
                for index, window in enumerate(ordered_windows)
                if window["owner_pid"] == os.getpid()
            ]
            foreground_indices = [
                index
                for index, window in enumerate(ordered_windows)
                if window["owner_pid"] == frontmost_pid
            ]
            self.assertTrue(cat_indices, "the cat overlay was not onscreen")
            self.assertTrue(
                foreground_indices,
                "the foreground application had no normal window",
            )
            self.assertLess(
                cat_indices[0],
                foreground_indices[0],
                "the cat overlay was ordered behind the foreground app",
            )
        finally:
            app._hide()
            activation_policy = _macos_activation_policy_accessors_for_app()
            if activation_policy is not None:
                activation_policy[1](0)
            app.root.destroy()
            self._activate_app(frontmost_pid)

    def test_z_overlay_surface_corners_are_transparent(self) -> None:
        from AppKit import NSApplication, NSBitmapImageRep
        from Quartz import (
            CGImageGetHeight,
            CGImageGetWidth,
            CGWindowListCreateImage,
            CGRectNull,
            kCGWindowImageBoundsIgnoreFraming,
            kCGWindowListOptionIncludingWindow,
        )

        frontmost_before = self._frontmost_pid()
        app = CatTypeApp(hold_seconds=10.0)
        try:
            now = time.monotonic()
            app.animation.record_key(now, "left")
            app._show(
                CaretSnapshot(
                    captured_at=now,
                    rect=ScreenRect(600, 400, 602, 420),
                    source="surface-alpha-regression",
                ),
                now,
            )
            self._run_event_loop(app.root, 0.25)
            window = next(
                window
                for window in NSApplication.sharedApplication().windows()
                if window.isVisible() and str(window.title()) == "Cat Type"
            )
            image = CGWindowListCreateImage(
                CGRectNull,
                kCGWindowListOptionIncludingWindow,
                window.windowNumber(),
                kCGWindowImageBoundsIgnoreFraming,
            )
            self.assertIsNotNone(image, "WindowServer did not capture the overlay")
            width = CGImageGetWidth(image)
            height = CGImageGetHeight(image)
            representation = NSBitmapImageRep.alloc().initWithCGImage_(image)
            corner_alphas = tuple(
                float(representation.colorAtX_y_(x, y).alphaComponent())
                for x, y in (
                    (0, 0),
                    (width - 1, 0),
                    (0, height - 1),
                    (width - 1, height - 1),
                )
            )

            self.assertEqual(
                corner_alphas,
                (0.0, 0.0, 0.0, 0.0),
                f"the overlay surface had opaque corners: {corner_alphas!r}",
            )
        finally:
            app._hide()
            activation_policy = _macos_activation_policy_accessors_for_app()
            if activation_policy is not None:
                activation_policy[1](0)
            app.root.destroy()
            self._activate_app(frontmost_before)

    @staticmethod
    def _run_event_loop(root: object, duration: float) -> None:
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            root.update()
            time.sleep(0.01)

    @staticmethod
    def _activate_app(pid: int) -> None:
        if MacOSOverlayFocusTests._frontmost_pid() == pid:
            time.sleep(0.25)
            return
        from AppKit import (
            NSApplicationActivateIgnoringOtherApps,
            NSRunningApplication,
        )

        application = NSRunningApplication.runningApplicationWithProcessIdentifier_(
            pid
        )
        if application is None:
            raise AssertionError(f"foreground application {pid} exited")
        application.activateWithOptions_(
            NSApplicationActivateIgnoringOtherApps
        )
        time.sleep(0.25)

    @staticmethod
    def _frontmost_pid() -> int:
        asn = subprocess.run(
            ["lsappinfo", "front"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        output = subprocess.run(
            ["lsappinfo", "info", "-only", "pid", asn],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        match = re.search(r'"pid"=(\d+)', output)
        if match is None:
            raise AssertionError(f"could not parse frontmost PID from {output!r}")
        return int(match.group(1))

    @staticmethod
    def _ordered_normal_windows() -> list[dict[str, int]]:
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGNullWindowID,
            kCGWindowLayer,
            kCGWindowListOptionOnScreenOnly,
            kCGWindowOwnerPID,
        )

        return [
            {"owner_pid": int(window[kCGWindowOwnerPID])}
            for window in CGWindowListCopyWindowInfo(
                kCGWindowListOptionOnScreenOnly,
                kCGNullWindowID,
            )
            if window.get(kCGWindowLayer) == 0
        ]


if __name__ == "__main__":
    unittest.main()
