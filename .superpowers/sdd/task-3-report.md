# Task 3 Report: Settings UI and Tk-Safe Update Orchestration

## Outcome

- Added a presentation-only Updates card showing `APP_VERSION`, live status,
  and a callback-driven **Check for updates** button.
- Added immutable `InstallerAvailability` and `UpdateEvent` values.
- Added injected service/state/installer/thread/clock/confirmation boundaries to
  `CatTypeApp`.
- Scheduled packaged Windows/Linux startup checks after two seconds, subject to
  persisted due state. Manual checks bypass due state and concurrent requests
  collapse.
- Kept network, state I/O, verified download, preparation, and installer start
  on one reusable daemon worker. Workers communicate with Tk only through
  `update_events`; `_tick` drains and handles those events.
- Confirmation occurs before download on the Tk thread. Shutdown guards prevent
  preparation or installation after closing begins.
- The narrow default installer is deliberately manual-only until Tasks 4 and 5
  provide real platform adapters. macOS, source checkouts, and otherwise
  unavailable packaged installs receive an actionable GitHub release URL and
  never download or self-install.

## RED evidence

Settings RED:

```text
python -m unittest tests.test_settings_window.SettingsWindowTkLayoutTests -v
```

Observed: 5 errors. `SettingsWindow.__init__` rejected the new
`on_check_for_updates` argument, proving the new tests exercised a missing
interface.

Controller RED:

```text
python -m unittest tests.test_update_controller -v
```

Observed: import error because `InstallerAvailability` did not exist, proving
the orchestration contract was absent.

Production-runner hardening RED:

```text
python -m unittest \
  tests.test_update_controller.ProductionUpdateRunnerTests -v
```

Observed: import error because `_DaemonUpdateRunner` did not exist. This caught
the initial implementation's creation of a new thread per operation rather
than one real daemon worker for all update jobs.

## GREEN evidence

Focused Settings GREEN under the documented local Tk environment:

```text
python -m unittest tests.test_settings_window.SettingsWindowTkLayoutTests -v
```

Observed: 5 tests passed.

Focused controller GREEN:

```text
python -m unittest tests.test_update_controller -v
```

Observed: 11 tests passed.

Portable affected suite:

```text
python -m unittest \
  tests.test_behavior tests.test_settings tests.test_settings_window \
  tests.test_platform_assets tests.test_bundled_icon_check \
  tests.test_package_smoke tests.test_release_version_check \
  tests.test_auto_update tests.test_update_controller -v
```

Observed: 119 tests passed with no failures, errors, or skips. The command used
the existing project virtualenv plus the documented locally extracted Tk
libraries and `DISPLAY=:0`.

`tests.test_overlay_rendering` was also attempted during broader verification;
it cannot import on Linux because it unconditionally requires Windows-only
`win32gui`, so it is excluded from the portable count.

## Self-review

- Settings imports only `APP_VERSION` and local presentation dependencies; it
  has no network, update service, or installer imports.
- `UpdateEvent` and `InstallerAvailability` are frozen dataclasses, and tests
  prove mutation raises `FrozenInstanceError`.
- Due-state reads, release discovery, successful-check state writes, downloads,
  preparation, and installer start occur within the injected worker runner.
- The Settings callback and confirmation dialog run only on the Tk thread.
- A successful check records state whether it finds a release or is up to date;
  check errors do not record state.
- Declining confirmation performs no download. Closing during download prevents
  preparation and installer start.
- The production runner queues every update operation onto one lazily started
  daemon thread; synchronous and deferred fake runners keep unit tests
  deterministic.
- Existing Settings footer/scroll behavior and constructor/open-settings tests
  remain covered. The added card increases scroll overflow and makes the prior
  narrow-footer display-sensitive baseline assertion pass in the local Tk
  environment.
- Task 4/5 platform mechanics were not implemented. Their adapters can replace
  the injected `availability`/`prepare`/`start` boundary without changing the
  Tk presentation contract.
