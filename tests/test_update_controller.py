from __future__ import annotations

import queue
import threading
import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from auto_update import (
    AvailableUpdate,
    InstallerAvailability,
    ReleaseAsset,
    UpdateError,
    UpdateEvent,
)
from cat_type import CatTypeApp, _DaemonUpdateRunner


NOW = datetime(2026, 8, 12, 16, 0, tzinfo=timezone.utc)


def available_update() -> AvailableUpdate:
    return AvailableUpdate(
        version="1.1.0",
        tag_name="v1.1.0",
        html_url="https://example.test/releases/v1.1.0",
        package=ReleaseAsset(
            "Cat-Type-Linux-x64.tar.gz",
            "https://example.test/Cat-Type-Linux-x64.tar.gz",
            100,
        ),
        checksums=ReleaseAsset(
            "SHA256SUMS.txt",
            "https://example.test/SHA256SUMS.txt",
            80,
        ),
    )


class ImmediateRunner:
    def __init__(self) -> None:
        self.names: list[str] = []

    def __call__(self, target: object, name: str) -> object:
        self.names.append(name)
        target()
        return target


class DeferredRunner:
    def __init__(self) -> None:
        self.jobs: list[tuple[object, str]] = []

    def __call__(self, target: object, name: str) -> object:
        self.jobs.append((target, name))
        return target


class FakeState:
    def __init__(self, due: bool = True) -> None:
        self.due = due
        self.due_calls: list[datetime] = []
        self.successes: list[datetime] = []

    def is_due(self, now: datetime) -> bool:
        self.due_calls.append(now)
        return self.due

    def record_success(self, now: datetime) -> None:
        self.successes.append(now)


class FakeService:
    def __init__(
        self,
        result: AvailableUpdate | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.check_calls: list[tuple[str, str]] = []
        self.downloads: list[AvailableUpdate] = []
        self.on_download: object | None = None

    def check(self, platform: str, machine: str) -> AvailableUpdate | None:
        self.check_calls.append((platform, machine))
        if self.error is not None:
            raise self.error
        return self.result

    def download_verified(self, update: AvailableUpdate, progress=None) -> Path:
        self.downloads.append(update)
        if progress is not None:
            progress(50, 100)
            progress(100, 100)
        if self.on_download is not None:
            self.on_download()
        return Path("/cache") / update.package.name


class FakeInstaller:
    def __init__(
        self,
        availability: InstallerAvailability | None = None,
    ) -> None:
        self._availability = availability or InstallerAvailability(
            True,
            "Automatic updates are ready.",
        )
        self.prepared: list[tuple[Path, AvailableUpdate]] = []
        self.started: list[object] = []

    def availability(self) -> InstallerAvailability:
        return self._availability

    def prepare(self, package: Path, update: AvailableUpdate) -> object:
        prepared = (package, update.version)
        self.prepared.append((package, update))
        return prepared

    def start(self, prepared: object) -> None:
        self.started.append(prepared)


class UpdateControllerTests(unittest.TestCase):
    def make_app(
        self,
        *,
        service: FakeService | None = None,
        state: FakeState | None = None,
        installer: FakeInstaller | None = None,
        runner: object | None = None,
        confirm: object | None = None,
        platform_name: str = "linux",
        frozen: bool = True,
    ) -> CatTypeApp:
        app = CatTypeApp.__new__(CatTypeApp)
        app._shutting_down = False
        app._settings_window = None
        app._update_status = "Ready to check for updates."
        app._initialize_update_controller(
            update_service=service or FakeService(),
            update_state=state or FakeState(),
            update_installer=installer or FakeInstaller(),
            thread_runner=runner or ImmediateRunner(),
            confirm_update=confirm or Mock(return_value=False),
            platform_name=platform_name,
            machine="x86_64",
            frozen=frozen,
            now=lambda: NOW,
        )
        return app

    def test_update_events_and_installer_status_are_immutable(self) -> None:
        event = UpdateEvent("status", message="Checking")
        availability = InstallerAvailability(False, "Manual update required.")

        with self.assertRaises(FrozenInstanceError):
            event.message = "changed"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            availability.can_install = True  # type: ignore[misc]

    def test_startup_check_runs_only_when_due_on_windows_or_linux(self) -> None:
        for platform_name, due, expected_checks in (
            ("linux", True, 1),
            ("win32", True, 1),
            ("linux", False, 0),
            ("darwin", True, 0),
        ):
            with self.subTest(platform=platform_name, due=due):
                state = FakeState(due=due)
                service = FakeService()
                app = self.make_app(
                    service=service,
                    state=state,
                    platform_name=platform_name,
                )

                app.check_for_updates()

                self.assertEqual(len(service.check_calls), expected_checks)

    def test_manual_checks_ignore_fresh_state_and_concurrent_requests_collapse(
        self,
    ) -> None:
        service = FakeService()
        runner = DeferredRunner()
        app = self.make_app(
            service=service,
            state=FakeState(due=False),
            runner=runner,
        )

        app.check_for_updates(manual=True)
        app.check_for_updates(manual=True)

        self.assertEqual(len(runner.jobs), 1)
        target, _name = runner.jobs.pop()
        target()
        self.assertEqual(service.check_calls, [("linux", "x86_64")])

    def test_worker_results_change_settings_only_when_tk_drains_events(self) -> None:
        settings = Mock()
        settings.window.winfo_exists.return_value = True
        app = self.make_app(service=FakeService())
        app._settings_window = settings

        app.check_for_updates(manual=True)

        settings.set_update_status.assert_called_once_with(
            "Checking for updates…",
            checking=True,
        )
        settings.set_update_status.reset_mock()
        self.assertIsInstance(app.update_events, queue.SimpleQueue)
        app._drain_update_events()

        settings.set_update_status.assert_called_with(
            "Cat Type is up to date.",
            checking=False,
        )

    def test_successful_up_to_date_check_records_state_without_prompt(self) -> None:
        state = FakeState()
        confirm = Mock(return_value=True)
        app = self.make_app(state=state, confirm=confirm)

        app.check_for_updates(manual=True)
        app._drain_update_events()

        self.assertEqual(state.successes, [NOW])
        confirm.assert_not_called()
        self.assertEqual(app._update_status, "Cat Type is up to date.")

    def test_failed_check_reports_error_without_recording_state_or_prompt(self) -> None:
        state = FakeState()
        confirm = Mock(return_value=True)
        app = self.make_app(
            service=FakeService(error=UpdateError("network unavailable")),
            state=state,
            confirm=confirm,
        )

        app.check_for_updates(manual=True)
        app._drain_update_events()

        self.assertEqual(state.successes, [])
        confirm.assert_not_called()
        self.assertIn("network unavailable", app._update_status)

    def test_declining_available_update_performs_no_download(self) -> None:
        update = available_update()
        service = FakeService(result=update)
        confirm = Mock(return_value=False)
        app = self.make_app(service=service, confirm=confirm)

        app.check_for_updates(manual=True)
        app._drain_update_events()

        confirm.assert_called_once_with(update)
        self.assertEqual(service.downloads, [])
        self.assertEqual(app._update_status, "Update cancelled.")

    def test_accepting_downloads_verifies_prepares_and_starts_installer(self) -> None:
        update = available_update()
        service = FakeService(result=update)
        installer = FakeInstaller()
        app = self.make_app(
            service=service,
            installer=installer,
            confirm=Mock(return_value=True),
        )

        app.check_for_updates(manual=True)
        app._drain_update_events()
        app._drain_update_events()

        self.assertEqual(service.downloads, [update])
        self.assertEqual(
            installer.prepared,
            [(Path("/cache") / update.package.name, update)],
        )
        self.assertEqual(
            installer.started,
            [((Path("/cache") / update.package.name), update.version)],
        )
        self.assertEqual(app._update_status, "Installing Cat Type 1.1.0…")

    def test_manual_only_platform_statuses_never_check_or_download(self) -> None:
        cases = (
            ("darwin", True, "macOS updates are manual."),
            ("linux", False, "Source checkouts cannot update themselves."),
            ("linux", True, "This Linux location is protected."),
        )
        for platform_name, frozen, status in cases:
            with self.subTest(status=status):
                service = FakeService(result=available_update())
                installer = FakeInstaller(InstallerAvailability(False, status))
                app = self.make_app(
                    service=service,
                    installer=installer,
                    platform_name=platform_name,
                    frozen=frozen,
                )

                app.check_for_updates(manual=True)
                app._drain_update_events()

                self.assertEqual(service.check_calls, [])
                self.assertEqual(service.downloads, [])
                self.assertEqual(app._update_status, status)

    def test_shutdown_during_download_prevents_prepare_or_install(self) -> None:
        update = available_update()
        service = FakeService(result=update)
        installer = FakeInstaller()
        app = self.make_app(
            service=service,
            installer=installer,
            confirm=Mock(return_value=True),
        )
        service.on_download = lambda: setattr(app, "_shutting_down", True)

        app.check_for_updates(manual=True)
        app._drain_update_events()
        app._drain_update_events()

        self.assertEqual(service.downloads, [update])
        self.assertEqual(installer.prepared, [])
        self.assertEqual(installer.started, [])


class ProductionUpdateRunnerTests(unittest.TestCase):
    def test_all_operations_reuse_one_daemon_worker_thread(self) -> None:
        runner = _DaemonUpdateRunner()
        identities: queue.SimpleQueue[int] = queue.SimpleQueue()
        first_done = threading.Event()
        second_done = threading.Event()

        def operation(done: threading.Event) -> None:
            identities.put(threading.get_ident())
            done.set()

        first_worker = runner(lambda: operation(first_done), "first-update")
        self.assertTrue(first_done.wait(timeout=1.0))
        second_worker = runner(lambda: operation(second_done), "second-update")
        self.assertTrue(second_done.wait(timeout=1.0))

        self.assertIs(first_worker, second_worker)
        self.assertTrue(first_worker.daemon)
        self.assertEqual(identities.get(), identities.get())


if __name__ == "__main__":
    unittest.main()
