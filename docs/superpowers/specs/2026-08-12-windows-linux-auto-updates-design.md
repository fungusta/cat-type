# Windows and Linux Automatic Updates

## Goal

Cat Type will check for stable GitHub releases on Windows and Linux, ask the
user before downloading or installing one, verify the published checksum,
replace the application safely, and relaunch it. macOS remains a manual
download because the current DMG has no installer or privileged update
helper.

## User Experience

- A packaged Windows or Linux build checks at startup when its last completed
  check is at least 24 hours old.
- Settings contains a **Check for updates** button and a short status line.
- Source checkouts never self-install; they may report that automatic updates
  are available only in packaged Windows and Linux builds.
- A newer stable release produces a confirmation dialog before any asset is
  downloaded. Declining leaves the running application unchanged.
- After confirmation, Settings reports download, verification, and install
  progress. Failure never shuts down or overwrites the current executable.
- Windows installs the verified release and relaunches Cat Type.
- A writable Linux portable installation is atomically replaced and
  relaunched. A protected location shows manual-update instructions instead.
- macOS shows that updates are manual and links users to the release page.

## Release Discovery and Trust Boundary

The updater uses the public GitHub endpoint
`https://api.github.com/repos/fungusta/cat-type/releases/latest` with a finite
timeout and a Cat Type user agent. It accepts only a published, non-draft,
non-prerelease tag with a strict `vMAJOR.MINOR.PATCH` version newer than the
running `APP_VERSION`.

Platform assets are selected by exact published names:

- Windows x64: `Cat-Type-Windows-x64.exe`;
- Linux x64: `Cat-Type-Linux-x64.tar.gz`;
- Linux arm64: `Cat-Type-Linux-arm64.tar.gz`; and
- all supported platforms: `SHA256SUMS.txt`.

The selected asset and checksum file are downloaded to Cat Type's cache over
HTTPS. The asset is accepted only when its SHA-256 digest matches the exact
filename entry in `SHA256SUMS.txt`. Paths, redirects, missing assets, malformed
versions, oversized responses, network errors, and checksum mismatches become
user-visible failures without starting installation.

The checksum protects against corruption and asset mix-ups. Because the asset
and checksum share the same GitHub release, it does not replace platform code
signing; the current unsigned-release trust model remains unchanged.

## Version and Scheduling State

`app_version.py` provides `APP_VERSION` as the application's runtime version.
The release-version checker validates it alongside every package metadata
file so tagged builds cannot drift.

`UpdateStateStore` writes only the last successful check timestamp to
`update-state.json` beside `settings.json`. A failed check is retryable on the
next launch. Session keystrokes and keyboard data never enter update state or
network requests.

## Application Boundaries

`auto_update.py` is a deep module that owns semantic-version comparison,
GitHub response validation, platform/architecture selection, download limits,
checksum parsing, staging, and the Windows/Linux install adapters. Its public
surface is limited to immutable release/status values, `UpdateService`, and
`UpdateStateStore`.

`CatTypeApp` owns asynchronous orchestration. Network and disk work run on one
background worker at a time and return typed update events through a separate
queue. Tk widgets and confirmation dialogs are touched only on the Tk thread.
Closing Cat Type while work is in flight leaves the downloaded cache harmless
and does not begin installation.

`SettingsWindow` accepts a check callback and exposes a narrow status update
method. It does not perform network, version, checksum, or installation work.

## Windows Installation

The packaged application creates a per-session Windows event named
`Local\CatTypeShutdown`. The Tk polling loop consumes that signal and uses the
normal `shutdown()` path, allowing the tray, keyboard listener, and caret
tracker to stop cleanly.

The Inno Setup script signals this event from `PrepareToInstall` before file
in-use detection. It then retains Restart Manager handling with force-close
fallback. Interactive installation asks before closing applications; silent
auto-update is allowed to force-close because Cat Type already obtained the
user's confirmation.

The in-app updater launches the verified installer with an explicit
`/AUTOUPDATE=1` parameter and silent close flags, then shuts down. A dedicated
`[Run]` entry launches the newly installed executable after silent auto-update;
the existing interactive post-install launch option remains.

This first fixed installer can update v1.0.5 and older applications that do
not understand the shutdown event: Restart Manager attempts normal closure,
then uses the user-approved force-close fallback. Later versions normally use
the graceful event.

## Linux Portable Installation

Linux automatic installation is supported only for a frozen Cat Type
executable whose containing directory can accept a staged file and atomic
rename. The verified archive is opened without `extractall`; exactly the
`Cat Type` regular-file member is copied beside the running executable with
its executable mode preserved.

A detached `/bin/sh` helper receives paths as positional arguments, waits for
the current process to exit, renames the old executable to a `.previous`
backup, moves the staged executable into place, and launches it. If replacement
or launch fails, the helper restores and relaunches the previous executable.
After the replacement remains alive through a short health window, the helper
removes the backup.

The shell program is constant text; file paths are never interpolated into
shell source. Updates fail before shutdown when the installation directory is
not writable, the archive member is unsafe, or staging cannot complete.

## Error Handling

- Concurrent automatic and manual checks collapse into one active operation.
- HTTP operations use timeouts, response-size limits, and temporary files.
- Partial downloads and failed staging are cleaned without touching the
  installed executable.
- The application does not shut down until a verified Windows installer has
  started or a verified Linux replacement and helper have started.
- UI status distinguishes up to date, update available, downloading,
  verification failure, unsupported installation, cancelled, and installing.
- Debug output may describe update stages and errors but never keyboard input.

## Testing

Automated tests cover strict version parsing and comparison, the 24-hour
schedule, state persistence, exact asset selection for Windows/Linux
architectures, GitHub payload validation, bounded downloads, checksum parsing
and mismatch rejection, safe tar extraction, Settings callbacks/status, Tk
thread event handling, graceful shutdown signaling, Windows installer script
requirements, Linux atomic replacement and rollback, source/macOS/manual
fallbacks, and unchanged keyboard/privacy behavior.

Windows integration verification launches a packaged Cat Type build, signals
the shutdown event, proves both PyInstaller processes exit, then installs over
a running older build and confirms the new version relaunches. Linux package
verification runs the portable update helper against temporary executables and
confirms both successful replacement and failed-launch rollback.
