from __future__ import annotations

import gc
import queue
import threading
import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from unittest.mock import Mock, patch

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

    skipped: str | None = None

    def skipped_version(self) -> str | None:
        return self.skipped

    def skip_version(self, version: str) -> None:
        self.skipped = version


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
        self.discarded: list[object] = []
        self.start_error: Exception | None = None

    def availability(self) -> InstallerAvailability:
        return self._availability

    def prepare(self, package: Path, update: AvailableUpdate) -> object:
        prepared = (package, update.version)
        self.prepared.append((package, update))
        return prepared

    def start(self, prepared: object) -> None:
        if self.start_error is not None:
            raise self.start_error
        self.started.append(prepared)

    def discard(self, prepared: object) -> None:
        self.discarded.append(prepared)


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


def setUpModule() -> None:
    # Earlier UI tests leave Tk roots in reference cycles. If the cycle
    # collector first runs on one of this module's worker threads, Tcl
    # deletes the interpreter from the wrong thread ("Tcl_AsyncDelete") and
    # can stall the thread under test. Collect them on the main thread first.
    gc.collect()


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
        prompt_factory: object | None = None,
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
            prompt_factory=prompt_factory,
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

    def test_startup_check_runs_only_when_due_on_packaged_platforms(self) -> None:
        for platform_name, due, expected_checks in (
            ("linux", True, 1),
            ("win32", True, 1),
            ("linux", False, 0),
            ("darwin", True, 1),
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

    def test_shutdown_during_prepare_returns_promptly_and_discards_it(self) -> None:
        installer = BlockingInstaller("prepare")
        runner = DeferredRunner()
        app = self.make_app(
            service=FakeService(result=available_update()),
            installer=installer,
            confirm=Mock(return_value=True),
            runner=runner,
        )
        app.check_for_updates(manual=True)
        runner.jobs.pop()[0]()  # type: ignore[operator]
        app._drain_update_events()
        install_thread = threading.Thread(target=runner.jobs.pop()[0])  # type: ignore[arg-type]
        try:
            install_thread.start()
            self.assertTrue(installer.handoff_entered.wait(timeout=1.0))
            shutdown_thread = threading.Thread(target=app.shutdown)
            shutdown_thread.start()
            shutdown_thread.join(timeout=0.5)
            self.assertFalse(shutdown_thread.is_alive(), "shutdown waited on prepare")
        finally:
            installer.release_handoff.set()
            install_thread.join(timeout=1.0)
        self.assertEqual(installer.started, [])
        self.assertEqual(len(installer.discarded), 1)

    def test_event_drain_is_not_blocked_while_prepare_runs(self) -> None:
        installer = BlockingInstaller("prepare")
        runner = DeferredRunner()
        app = self.make_app(
            service=FakeService(result=available_update()),
            installer=installer,
            confirm=Mock(return_value=True),
            runner=runner,
        )
        app.check_for_updates(manual=True)
        runner.jobs.pop()[0]()  # type: ignore[operator]
        app._drain_update_events()
        install_thread = threading.Thread(target=runner.jobs.pop()[0])  # type: ignore[arg-type]
        try:
            install_thread.start()
            self.assertTrue(installer.handoff_entered.wait(timeout=1.0))
            drain = threading.Thread(target=app._drain_update_events)
            drain.start()
            drain.join(timeout=0.5)
            self.assertFalse(drain.is_alive(), "Tk event drain blocked on prepare")
        finally:
            installer.release_handoff.set()
            install_thread.join(timeout=1.0)

    def test_start_failure_discards_prepared_update(self) -> None:
        installer = FakeInstaller()
        installer.start_error = RuntimeError("An update is already in progress.")
        app = self.make_app(
            service=FakeService(result=available_update()),
            installer=installer,
            confirm=Mock(return_value=True),
        )
        app.shutdown = Mock()

        app.check_for_updates(manual=True)
        app._drain_update_events()

        self.assertEqual(len(installer.discarded), 1)
        self.assertEqual(app._update_status, "Update failed: An update is already in progress.")
        app.shutdown.assert_not_called()

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

    def test_source_checkout_never_checks_or_downloads(self) -> None:
        status = "Source checkouts cannot update themselves."
        service = FakeService(result=available_update())
        installer = FakeInstaller(InstallerAvailability(False, status))
        app = self.make_app(
            service=service,
            installer=installer,
            platform_name="linux",
            frozen=False,
        )

        app.check_for_updates(manual=True)
        app._drain_update_events()

        self.assertEqual(service.check_calls, [])
        self.assertEqual(service.downloads, [])
        self.assertEqual(app._update_status, status)

    def test_packaged_macos_discovers_update_without_downloading_it(self) -> None:
        status = "Download the signed macOS release manually."
        service = FakeService(result=available_update())
        installer = FakeInstaller(InstallerAvailability(False, status))
        app = self.make_app(
            service=service,
            installer=installer,
            platform_name="darwin",
            frozen=True,
        )

        app.check_for_updates(manual=True)
        app._drain_update_events()

        self.assertEqual(service.check_calls, [("darwin", "x86_64")])
        self.assertEqual(service.downloads, [])
        self.assertEqual(
            app._update_status,
            f"Cat Type {available_update().version} is available. {status}",
        )

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


class PeriodicUpdateCheckTests(unittest.TestCase):
    make_app = UpdateControllerTests.make_app

    def test_run_schedules_startup_and_periodic_check_on_each_platform(self) -> None:
        for platform_name in ("darwin", "win32", "linux"):
            with self.subTest(platform=platform_name):
                app = CatTypeApp.__new__(CatTypeApp)
                app._start_tray = Mock()
                app._ensure_activity_monitoring = Mock()
                app.animation = Mock()
                app.tracker = Mock()
                app.root = Mock()
                app._first_run = False
                app._platform_name = platform_name

                app.run()

                app.root.after.assert_any_call(2000, app.check_for_updates)
                app.root.after.assert_any_call(
                    3_600_000, app._schedule_periodic_update_check
                )
                self.assertEqual(CatTypeApp.UPDATE_RECHECK_INTERVAL_MS, 3_600_000)

    def test_periodic_check_rearms_and_stops_after_shutdown(self) -> None:
        app = self.make_app()
        app.check_for_updates = Mock()

        app._schedule_periodic_update_check()

        app.check_for_updates.assert_called_once_with()
        app.root.after.assert_called_once_with(
            3_600_000, app._schedule_periodic_update_check
        )

        app.check_for_updates.reset_mock()
        app.root.after.reset_mock()
        app._shutting_down = True
        app._schedule_periodic_update_check()

        app.check_for_updates.assert_not_called()
        app.root.after.assert_not_called()

    def test_periodic_check_is_noop_while_operation_active(self) -> None:
        service = FakeService(result=available_update())
        app = self.make_app(service=service)
        self.assertIsNotNone(app._begin_update_operation())

        app._schedule_periodic_update_check()

        self.assertEqual(service.check_calls, [])

    def test_periodic_check_respects_not_due(self) -> None:
        service = FakeService(result=available_update())
        app = self.make_app(service=service, state=FakeState(due=False))

        app._schedule_periodic_update_check()
        app._drain_update_events()

        self.assertEqual(service.check_calls, [])
        self.assertIsNone(app._active_update_operation_id)


class SkippedVersionControllerTests(unittest.TestCase):
    make_app = UpdateControllerTests.make_app

    def skipped_app(self, skipped: str) -> tuple[CatTypeApp, Mock]:
        state = FakeState()
        state.skipped = skipped
        confirm = Mock(return_value=False)
        app = self.make_app(
            service=FakeService(result=available_update()),
            state=state,
            confirm=confirm,
        )
        return app, confirm

    def test_automatic_check_skips_prompt_for_skipped_version(self) -> None:
        app, confirm = self.skipped_app("1.1.0")

        app.check_for_updates()
        app._drain_update_events()

        confirm.assert_not_called()
        self.assertEqual(app._update_status, "Cat Type 1.1.0 is available (skipped).")
        self.assertIsNone(app._active_update_operation_id)

    def test_manual_check_prompts_even_for_skipped_version(self) -> None:
        app, confirm = self.skipped_app("1.1.0")

        app.check_for_updates(manual=True)
        app._drain_update_events()

        confirm.assert_called_once()

    def test_newer_than_skipped_version_prompts(self) -> None:
        app, confirm = self.skipped_app("1.0.99")

        app.check_for_updates()
        app._drain_update_events()

        confirm.assert_called_once()


def mac_available_update() -> AvailableUpdate:
    return AvailableUpdate(
        version="1.1.0",
        tag_name="v1.1.0",
        html_url="https://example.test/releases/v1.1.0",
        package=ReleaseAsset(
            "Cat-Type-macOS-arm64.dmg",
            "https://example.test/Cat-Type-macOS-arm64.dmg",
            100,
        ),
        checksums=ReleaseAsset(
            "SHA256SUMS.txt",
            "https://example.test/SHA256SUMS.txt",
            80,
        ),
    )


class FakePrompt:
    def __init__(self, root: object, update: AvailableUpdate, current_version: str, **callbacks: object) -> None:
        self.update = update
        self.current_version = current_version
        self.take_focus = callbacks.pop("take_focus")
        self.callbacks = callbacks
        self.progress: list[tuple[str, float | None]] = []
        self.errors: list[str] = []
        self.fronted: list[bool] = []
        self.closed = False

    def choose(self, choice: str) -> None:
        self.callbacks["on_choice"](choice)  # type: ignore[operator]

    def show_progress(self, text: str, fraction: float | None) -> None:
        self.progress.append((text, fraction))

    def show_error(self, message: str) -> None:
        self.errors.append(message)

    def bring_to_front(self, take_focus: bool) -> None:
        self.fronted.append(take_focus)

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            self.callbacks["on_closed"]()  # type: ignore[operator]


class MacPromptControllerTests(unittest.TestCase):
    make_app = UpdateControllerTests.make_app

    def mac_app(self, **overrides: object) -> tuple[CatTypeApp, list[FakePrompt]]:
        prompts: list[FakePrompt] = []

        def factory(*args: object, **kwargs: object) -> FakePrompt:
            prompt = FakePrompt(*args, **kwargs)
            prompts.append(prompt)
            return prompt

        options: dict[str, object] = {
            "service": FakeService(result=mac_available_update()),
            "platform_name": "darwin",
            "prompt_factory": factory,
        }
        options.update(overrides)
        app = self.make_app(**options)  # type: ignore[arg-type]
        app.shutdown = Mock()
        app._return_to_macos_background_policy = Mock()
        return app, prompts

    def test_macos_update_opens_prompt_without_focus_for_automatic_check(self) -> None:
        confirm = Mock(return_value=True)
        app, prompts = self.mac_app(confirm=confirm)

        app.check_for_updates()
        app._drain_update_events()

        self.assertEqual(len(prompts), 1)
        self.assertFalse(prompts[0].take_focus)
        self.assertEqual(prompts[0].update.version, "1.1.0")
        confirm.assert_not_called()
        self.assertIsNotNone(app._active_update_operation_id)

    def test_unfocused_prompt_becomes_clickable_without_taking_focus(self) -> None:
        app, prompts = self.mac_app()
        policies: list[int] = []
        accessors = (lambda: 2, lambda policy: policies.append(policy) or True, lambda: False)

        app.check_for_updates()
        app._drain_update_events()

        app.root.after.assert_any_call(
            CatTypeApp.UPDATE_PROMPT_CLICKABLE_DELAY_MS,
            app._make_update_prompt_clickable,
        )
        with patch("cat_type._macos_activation_policy_accessors_for_app", return_value=accessors):
            app._make_update_prompt_clickable()
            prompts[0].choose("later")
            app._make_update_prompt_clickable()

        self.assertEqual(policies, [1])

    def test_macos_manual_check_opens_prompt_with_focus(self) -> None:
        app, prompts = self.mac_app()

        app.check_for_updates(manual=True)
        app._drain_update_events()

        self.assertTrue(prompts[0].take_focus)

    def test_manual_check_with_open_prompt_brings_it_to_front(self) -> None:
        service = FakeService(result=mac_available_update())
        app, prompts = self.mac_app(service=service)
        app.check_for_updates()
        app._drain_update_events()

        app.check_for_updates(manual=True)
        app._drain_update_events()

        self.assertEqual(len(prompts), 1)
        self.assertEqual(prompts[0].fronted, [True])
        self.assertEqual(len(service.check_calls), 1)

    def test_choice_install_starts_install_and_routes_progress_to_prompt(self) -> None:
        installer = FakeInstaller()
        app, prompts = self.mac_app(installer=installer)
        app.check_for_updates()
        app._drain_update_events()

        prompts[0].choose("install")
        app._drain_update_events()

        progress = prompts[0].progress
        self.assertEqual(progress[0], ("Downloading update… 0%", 0.0))
        self.assertIn(("Downloading update… 50%", 0.5), progress)
        self.assertIn(("Verifying Cat Type 1.1.0…", None), progress)
        self.assertIn(("Installing Cat Type 1.1.0…", None), progress)
        self.assertEqual(len(installer.started), 1)
        self.assertTrue(prompts[0].closed)
        app.shutdown.assert_called_once_with()

    def test_choice_skip_records_version(self) -> None:
        state = FakeState()
        app, prompts = self.mac_app(state=state)
        app.check_for_updates()
        app._drain_update_events()

        prompts[0].choose("skip")

        self.assertEqual(state.skipped, "1.1.0")
        self.assertTrue(prompts[0].closed)
        self.assertIsNone(app._active_update_operation_id)

    def test_choice_later_records_nothing(self) -> None:
        state = FakeState()
        service = FakeService(result=mac_available_update())
        app, prompts = self.mac_app(state=state, service=service)
        app.check_for_updates()
        app._drain_update_events()

        prompts[0].choose("later")

        self.assertIsNone(state.skipped)
        self.assertEqual(service.downloads, [])
        self.assertTrue(prompts[0].closed)
        self.assertIsNone(app._active_update_operation_id)

    def test_error_is_shown_in_prompt_and_current_app_keeps_running(self) -> None:
        service = FakeService(
            result=mac_available_update(),
            download_error=UpdateError("package checksum does not match SHA256SUMS.txt"),
        )
        installer = FakeInstaller()
        app, prompts = self.mac_app(service=service, installer=installer)
        app.check_for_updates()
        app._drain_update_events()

        prompts[0].choose("install")
        app._drain_update_events()

        self.assertEqual(
            prompts[0].errors, ["package checksum does not match SHA256SUMS.txt"]
        )
        self.assertFalse(prompts[0].closed)
        self.assertEqual(installer.started, [])
        app.shutdown.assert_not_called()
        self.assertIsNone(app._active_update_operation_id)

    def test_new_check_after_error_replaces_the_error_prompt(self) -> None:
        service = FakeService(
            result=mac_available_update(), download_error=UpdateError("offline")
        )
        app, prompts = self.mac_app(service=service)
        app.check_for_updates()
        app._drain_update_events()
        prompts[0].choose("install")
        app._drain_update_events()

        app.check_for_updates(manual=True)
        app._drain_update_events()

        self.assertTrue(prompts[0].closed)
        self.assertEqual(len(prompts), 2)

    def test_cancel_during_download_emits_cancelled_and_closes_prompt(self) -> None:
        runner = DeferredRunner()
        installer = FakeInstaller()
        app, prompts = self.mac_app(runner=runner, installer=installer)
        app.check_for_updates()
        runner.jobs.pop(0)[0]()  # type: ignore[operator]
        app._drain_update_events()

        prompts[0].choose("install")
        prompts[0].callbacks["on_cancel"]()  # type: ignore[operator]
        runner.jobs.pop(0)[0]()  # type: ignore[operator]
        app._drain_update_events()

        self.assertEqual(installer.prepared, [])
        self.assertTrue(prompts[0].closed)
        self.assertEqual(app._update_status, "Update cancelled.")
        self.assertIsNone(app._active_update_operation_id)

    def test_shutdown_with_open_prompt_closes_it_and_never_starts_helper(self) -> None:
        runner = DeferredRunner()
        installer = FakeInstaller()
        app, prompts = self.mac_app(runner=runner, installer=installer)
        del app.shutdown
        app.check_for_updates()
        runner.jobs.pop(0)[0]()  # type: ignore[operator]
        app._drain_update_events()
        prompts[0].choose("install")

        app.shutdown()
        runner.jobs.pop(0)[0]()  # type: ignore[operator]

        self.assertTrue(prompts[0].closed)
        self.assertEqual(installer.prepared, [])
        self.assertEqual(installer.started, [])

    def test_prompt_close_returns_to_background_policy_when_settings_closed(self) -> None:
        app, prompts = self.mac_app()
        app._return_to_macos_background_policy = Mock()
        app.check_for_updates()
        app._drain_update_events()

        prompts[0].choose("later")

        app._return_to_macos_background_policy.assert_called_once_with()

    def test_download_manually_opens_release_page(self) -> None:
        app, prompts = self.mac_app()
        app.check_for_updates()
        app._drain_update_events()

        with patch("cat_type.webbrowser.open") as browser:
            prompts[0].callbacks["on_download_manually"]()  # type: ignore[operator]

        browser.assert_called_once_with("https://example.test/releases/v1.1.0")

    def test_windows_and_linux_still_use_confirm_update(self) -> None:
        for platform_name in ("win32", "linux"):
            with self.subTest(platform=platform_name):
                confirm = Mock(return_value=False)
                app = self.make_app(
                    service=FakeService(result=available_update()),
                    confirm=confirm,
                    platform_name=platform_name,
                )
                app.check_for_updates(manual=True)
                app._drain_update_events()
                confirm.assert_called_once()


if __name__ == "__main__":
    unittest.main()
