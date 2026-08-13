from __future__ import annotations

import queue
import threading
import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
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
TERMINAL_EVENT_KINDS = {
    "not-due",
    "unavailable",
    "error",
    "cancelled",
    "install-started",
}


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
        download_error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.download_error = download_error
        self.check_calls: list[tuple[str, str]] = []
        self.downloads: list[AvailableUpdate] = []
        self.on_download: object | None = None
        self.progress_events: list[tuple[int, int]] = []

    def check(self, platform: str, machine: str) -> AvailableUpdate | None:
        self.check_calls.append((platform, machine))
        if self.error is not None:
            raise self.error
        return self.result

    def download_verified(self, update: AvailableUpdate, progress=None) -> Path:
        self.downloads.append(update)
        if progress is not None:
            progress(50, 100)
            self.progress_events.append((50, 100))
            progress(100, 100)
            self.progress_events.append((100, 100))
        if self.download_error is not None:
            raise self.download_error
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


class BlockingInstaller(FakeInstaller):
    def __init__(self, blocking_stage: str) -> None:
        super().__init__()
        self.blocking_stage = blocking_stage
        self.handoff_entered = threading.Event()
        self.release_handoff = threading.Event()

    def prepare(self, package: Path, update: AvailableUpdate) -> object:
        if self.blocking_stage == "prepare":
            self.handoff_entered.set()
            if not self.release_handoff.wait(timeout=1.0):
                raise RuntimeError("prepare test barrier timed out")
        return super().prepare(package, update)

    def start(self, prepared: object) -> None:
        if self.blocking_stage == "start":
            self.handoff_entered.set()
            if not self.release_handoff.wait(timeout=1.0):
                raise RuntimeError("start test barrier timed out")
        super().start(prepared)


class UpdateControllerTests(unittest.TestCase):
    def make_app(
        self,
        *,
        service: FakeService | None = None,
        state: FakeState | None = None,
        installer: FakeInstaller | None = None,
        runner: object | None = None,
        confirm: object | None = None,
        before_handoff: Callable[[str], None] | None = None,
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
            before_handoff=before_handoff,
        )
        app._hide = Mock()
        app._tray_icon = None
        app.keyboard = Mock()
        app.tracker = Mock()
        app.root = Mock()
        return app

    def test_update_events_and_installer_status_are_immutable(self) -> None:
        event = UpdateEvent(1, "stage", message="Checking")
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

    def test_manual_check_racing_fresh_startup_check_is_replayed(self) -> None:
        service = FakeService()
        runner = DeferredRunner()
        app = self.make_app(
            service=service,
            state=FakeState(due=False),
            runner=runner,
        )

        app.check_for_updates(manual=False)
        app.check_for_updates(manual=True)
        automatic_target, _name = runner.jobs.pop()
        automatic_target()
        app._drain_update_events()

        self.assertEqual(len(runner.jobs), 1)
        manual_target, _name = runner.jobs.pop()
        manual_target()
        app._drain_update_events()
        self.assertEqual(service.check_calls, [("linux", "x86_64")])
        self.assertEqual(app._update_status, "Cat Type is up to date.")

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
        app.shutdown = Mock()

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
        app.shutdown.assert_called_once_with()

    def test_reentrant_check_during_confirmation_collapses_into_original_flow(
        self,
    ) -> None:
        update = available_update()
        service = FakeService(result=update)
        installer = FakeInstaller()
        app = self.make_app(service=service, installer=installer)
        app.shutdown = Mock()

        def confirm(_update: AvailableUpdate) -> bool:
            app.check_for_updates(manual=True)
            return True

        app._confirm_update = confirm

        app.check_for_updates(manual=True)
        app._drain_update_events()

        self.assertEqual(service.check_calls, [("linux", "x86_64")])
        self.assertEqual(service.downloads, [update])
        self.assertEqual(len(installer.started), 1)
        app.shutdown.assert_called_once_with()

    def test_stale_generation_event_cannot_overwrite_active_operation(self) -> None:
        runner = DeferredRunner()
        app = self.make_app(runner=runner)

        app.check_for_updates(manual=True)
        active_operation = app._active_update_operation_id
        assert active_operation is not None
        app.update_events.put(
            UpdateEvent(
                active_operation - 1,
                "stage",
                message="stale status",
            )
        )

        app._drain_update_events()

        self.assertEqual(app._update_status, "Checking for updates…")
        self.assertTrue(app._update_worker_active)

    def test_install_error_is_terminal_and_does_not_shutdown(self) -> None:
        update = available_update()
        app = self.make_app(
            service=FakeService(
                result=update,
                download_error=UpdateError("checksum mismatch"),
            ),
            confirm=Mock(return_value=True),
        )
        app.shutdown = Mock()

        app.check_for_updates(manual=True)
        app._drain_update_events()

        self.assertFalse(app._update_worker_active)
        self.assertIn("checksum mismatch", app._update_status)
        app.shutdown.assert_not_called()

    def test_installer_helper_launch_failure_is_terminal_and_does_not_shutdown(
        self,
    ) -> None:
        update = available_update()

        class LaunchFailingInstaller(FakeInstaller):
            def start(self, prepared: object) -> None:
                del prepared
                raise OSError("could not launch Linux update helper")

        app = self.make_app(
            service=FakeService(result=update),
            installer=LaunchFailingInstaller(),
            confirm=Mock(return_value=True),
        )
        app.shutdown = Mock()

        app.check_for_updates(manual=True)
        app._drain_update_events()

        self.assertIn("could not launch Linux update helper", app._update_status)
        app.shutdown.assert_not_called()

    def test_success_shutdown_occurs_only_after_installer_start_returns(self) -> None:
        update = available_update()
        sequence: list[str] = []

        class SequencedInstaller(FakeInstaller):
            def start(self, prepared: object) -> None:
                super().start(prepared)
                sequence.append("start-returned")

        app = self.make_app(
            service=FakeService(result=update),
            installer=SequencedInstaller(),
            confirm=Mock(return_value=True),
        )
        app.shutdown = Mock(side_effect=lambda: sequence.append("shutdown"))
        handled: list[UpdateEvent] = []
        original_handler = app._handle_update_event
        app._handle_update_event = lambda event: (
            handled.append(event),
            original_handler(event),
        )[-1]

        app.check_for_updates(manual=True)
        app._drain_update_events()

        self.assertEqual(sequence, ["start-returned", "shutdown"])
        app.shutdown.assert_called_once_with()
        self.assertEqual(
            [
                event.kind
                for event in handled
                if event.kind in TERMINAL_EVENT_KINDS
            ],
            ["install-started"],
        )

    def test_tick_stops_after_install_started_triggers_normal_shutdown(self) -> None:
        app = self.make_app()
        operation_id = app._begin_update_operation()
        assert operation_id is not None
        app.update_events.put(
            UpdateEvent(
                operation_id,
                "install-started",
                message="Installing Cat Type 1.1.0…",
            )
        )
        app.events = queue.SimpleQueue()

        app._tick()

        self.assertTrue(app._shutting_down)
        app.root.destroy.assert_called_once_with()
        app.root.after.assert_not_called()

    def test_verification_and_preparation_statuses_follow_real_boundaries(
        self,
    ) -> None:
        update = available_update()
        settings = Mock()
        settings.window.winfo_exists.return_value = True
        app = self.make_app(
            service=FakeService(result=update),
            confirm=Mock(return_value=True),
        )
        app._settings_window = settings
        app.shutdown = Mock()

        app.check_for_updates(manual=True)
        app._drain_update_events()

        statuses = [call.args[0] for call in settings.set_update_status.call_args_list]
        self.assertLess(
            statuses.index("Downloading update… 50%"),
            statuses.index("Verifying Cat Type 1.1.0…"),
        )
        self.assertNotIn("Downloading update… 100%", statuses)
        self.assertLess(
            statuses.index("Verifying Cat Type 1.1.0…"),
            statuses.index("Preparing Cat Type 1.1.0…"),
        )
        self.assertLess(
            statuses.index("Preparing Cat Type 1.1.0…"),
            statuses.index("Installing Cat Type 1.1.0…"),
        )

    def test_checksum_error_stops_after_real_verification_status(self) -> None:
        update = available_update()
        settings = Mock()
        settings.window.winfo_exists.return_value = True
        app = self.make_app(
            service=FakeService(
                result=update,
                download_error=UpdateError("checksum mismatch"),
            ),
            confirm=Mock(return_value=True),
        )
        app._settings_window = settings
        app.shutdown = Mock()

        app.check_for_updates(manual=True)
        app._drain_update_events()

        statuses = [call.args[0] for call in settings.set_update_status.call_args_list]
        self.assertIn("Verifying Cat Type 1.1.0…", statuses)
        self.assertNotIn("Downloading update… 100%", statuses)
        self.assertNotIn("Preparing Cat Type 1.1.0…", statuses)
        self.assertIn("Update failed: checksum mismatch", statuses)

    def test_shutdown_winning_prepare_handoff_prevents_prepare_and_start(self) -> None:
        update = available_update()
        installer = FakeInstaller()
        app_ref: list[CatTypeApp] = []

        def before_handoff(stage: str) -> None:
            if stage != "prepare":
                return
            shutdown = threading.Thread(target=app_ref[0].shutdown)
            shutdown.start()
            shutdown.join(timeout=1.0)
            self.assertFalse(shutdown.is_alive())

        app = self.make_app(
            service=FakeService(result=update),
            installer=installer,
            confirm=Mock(return_value=True),
            before_handoff=before_handoff,
        )
        app_ref.append(app)

        app.check_for_updates(manual=True)
        app._drain_update_events()

        self.assertEqual(installer.prepared, [])
        self.assertEqual(installer.started, [])
        self.assertFalse(app._update_worker_active)

    def test_shutdown_winning_start_handoff_prevents_start(self) -> None:
        update = available_update()
        installer = FakeInstaller()
        app_ref: list[CatTypeApp] = []

        def before_handoff(stage: str) -> None:
            if stage != "start":
                return
            shutdown = threading.Thread(target=app_ref[0].shutdown)
            shutdown.start()
            shutdown.join(timeout=1.0)
            self.assertFalse(shutdown.is_alive())

        app = self.make_app(
            service=FakeService(result=update),
            installer=installer,
            confirm=Mock(return_value=True),
            before_handoff=before_handoff,
        )
        app_ref.append(app)

        app.check_for_updates(manual=True)
        app._drain_update_events()

        self.assertEqual(len(installer.prepared), 1)
        self.assertEqual(installer.started, [])
        self.assertFalse(app._update_worker_active)

    def test_shutdown_waits_for_prepare_handoff_that_already_began(self) -> None:
        self._assert_shutdown_waits_for_active_handoff("prepare")

    def test_shutdown_waits_for_start_handoff_that_already_began(self) -> None:
        self._assert_shutdown_waits_for_active_handoff("start")

    def _assert_shutdown_waits_for_active_handoff(self, stage: str) -> None:
        update = available_update()
        installer = BlockingInstaller(stage)
        runner = DeferredRunner()
        app = self.make_app(
            service=FakeService(result=update),
            installer=installer,
            confirm=Mock(return_value=True),
            runner=runner,
        )
        app.check_for_updates(manual=True)
        check_target, _name = runner.jobs.pop()
        check_target()
        app._drain_update_events()
        install_target, _name = runner.jobs.pop()
        install_thread = threading.Thread(target=install_target)
        shutdown_started = threading.Event()
        shutdown_done = threading.Event()

        def shutdown() -> None:
            shutdown_started.set()
            app.shutdown()
            shutdown_done.set()

        shutdown_thread = threading.Thread(target=shutdown)
        try:
            install_thread.start()
            self.assertTrue(installer.handoff_entered.wait(timeout=1.0))
            shutdown_thread.start()
            self.assertTrue(shutdown_started.wait(timeout=1.0))
            self.assertFalse(shutdown_done.wait(timeout=0.05))
        finally:
            installer.release_handoff.set()
            install_thread.join(timeout=1.0)
            shutdown_thread.join(timeout=1.0)
        self.assertFalse(install_thread.is_alive())
        self.assertFalse(shutdown_thread.is_alive())
        self.assertTrue(shutdown_done.is_set())

    def test_source_and_macos_statuses_never_check_or_download(self) -> None:
        cases = (
            ("darwin", True, "macOS updates are manual."),
            ("linux", False, "Source checkouts cannot update themselves."),
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

    def test_protected_packaged_linux_still_discovers_available_update(self) -> None:
        update = available_update()
        service = FakeService(result=update)
        state = FakeState()
        confirm = Mock(return_value=True)
        installer = FakeInstaller(
            InstallerAvailability(False, "This Linux location is protected.")
        )
        app = self.make_app(
            service=service,
            state=state,
            installer=installer,
            confirm=confirm,
            platform_name="linux",
            frozen=True,
        )

        app.check_for_updates(manual=True)
        app._drain_update_events()

        self.assertEqual(service.check_calls, [("linux", "x86_64")])
        self.assertEqual(state.successes, [NOW])
        self.assertEqual(service.downloads, [])
        confirm.assert_not_called()
        self.assertIn("Cat Type 1.1.0 is available.", app._update_status)
        self.assertIn("protected", app._update_status)

    def test_shutdown_during_download_prevents_prepare_or_install(self) -> None:
        update = available_update()
        service = FakeService(result=update)
        installer = FakeInstaller()
        app = self.make_app(
            service=service,
            installer=installer,
            confirm=Mock(return_value=True),
        )
        service.on_download = app.shutdown
        handled: list[UpdateEvent] = []
        original_handler = app._handle_update_event
        app._handle_update_event = lambda event: (
            handled.append(event),
            original_handler(event),
        )[-1]

        app.check_for_updates(manual=True)
        app._drain_update_events()

        self.assertEqual(service.downloads, [update])
        self.assertEqual(installer.prepared, [])
        self.assertEqual(installer.started, [])
        self.assertFalse(app._update_worker_active)
        self.assertEqual(
            [
                event.kind
                for event in handled
                if event.kind in TERMINAL_EVENT_KINDS
            ],
            ["cancelled"],
        )


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

    def test_escaping_base_exception_does_not_strand_later_job(self) -> None:
        runner = _DaemonUpdateRunner()
        first_started = threading.Event()
        second_done = threading.Event()

        def broken_job() -> None:
            first_started.set()
            raise SystemExit("broken update job")

        runner(broken_job, "broken-update")
        self.assertTrue(first_started.wait(timeout=1.0))
        runner(second_done.set, "later-update")

        self.assertTrue(second_done.wait(timeout=1.0))


if __name__ == "__main__":
    unittest.main()
