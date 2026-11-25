# macOS Automatic Updates

## Intent

Updating Cat Type on a Mac today means downloading the DMG, dragging the app
to Applications, and confirming the replacement by hand. Windows and Linux
already update themselves after one confirmation. The goal is the same
one-click update on macOS, modelled on how Sparkle (the standard macOS update
framework) installs updates, without adopting Sparkle itself.

## Current State

- `UpdateService` in `auto_update.py` already discovers releases, selects
  `Cat-Type-macOS-x64.dmg` or `Cat-Type-macOS-arm64.dmg`, and downloads and
  verifies them against `SHA256SUMS.txt`.
- `_default_update_installer` in `cat_type.py` returns
  `_UnavailableUpdateInstaller` on macOS, so a found update only produces a
  status line and a link to the release page.
- `CatTypeApp.run` schedules the automatic startup check only on Windows and
  Linux. Packaged Mac builds check only when the user presses **Check for
  updates**, although the README says all platforms check at startup.
- The macOS app is a PyInstaller one-folder bundle (`Cat Type.app`, bundle ID
  `com.fungusta.cat-type`, team `9B98U2J5Q2`), signed with Developer ID and the
  hardened runtime, shipped in a notarized, stapled DMG. Minimum macOS is 12.

## Goals

- Packaged builds on all three platforms check for updates at startup and
  then every 24 hours while running, as Sparkle does. Cat Type runs all day
  from login, so a startup-only check could leave users weeks behind.
- When an update is found, a Sparkle-style prompt offers **Install Update**,
  **Skip This Version**, and **Remind Me Later**.
- **Install Update** downloads, verifies, swaps the app in place, and relaunches
  the new version with no further user action.
- A failed update never leaves the user without a working Cat Type.
- Settings, usage metrics, achievements, and the Input Monitoring permission
  survive the update.

## Non-goals

- Admin-password prompt for protected install locations (a standard account in
  `/Applications`). These users keep today's manual link. It can be added later.
- Install on Quit, silent background installs, or an "automatically install
  updates" preference. Cat Type runs all day from login, so install-on-quit
  would often mean weeks of delay.
- Release notes inside the prompt.
- Delta updates, phased rollouts, a separate appcast feed, or EdDSA keys.
- Changing the Windows or Linux update prompt. (They do gain the in-session
  24-hour check, because it lives in shared controller code.)
- Adopting the Sparkle framework itself.

## Anti-goals

These would make the feature a failure even if updates technically install:

- Installing any bundle not signed by team `9B98U2J5Q2` with bundle ID
  `com.fungusta.cat-type`, or installing an older or equal version.
- Leaving the install location empty or with a half-copied app.
- Losing the Input Monitoring grant, so every update forces the user back
  through System Settings.
- Prompting again for a version the user chose to skip during automatic checks.

## Approaches Considered

1. **Native swap modelled on Sparkle (chosen).** Cat Type stages the verified
   new app beside the current one, quits, and a small helper swaps the bundles
   and relaunches. Reuses the existing download, checksum, and controller
   seams, adds no runtime dependencies, and mirrors the Linux portable
   installer's structure. Falls back to the manual link where the app's folder
   isn't writable.
2. **Native swap plus admin password prompt.** Same, but asks for admin rights
   when the folder is protected. Rejected for now: a privileged code path is
   more to secure for a minority of users, and can be layered on later.
3. **Sparkle framework.** The proven standard, but it is Objective-C and would
   need bridging from Python/Tk, an appcast feed, EdDSA keys in CI, and its own
   update UI competing with the Settings flow. Rejected as too many new moving
   parts.

## User Experience

### Checking

- `run()` schedules the 2-second startup check on macOS as it does on Windows
  and Linux.
- After that, a repeating Tk timer (on all three platforms) calls the
  automatic check periodically, for example hourly. The existing
  `UpdateStateStore.is_due` 24-hour rule decides whether it actually contacts
  GitHub, so a long-running session checks about once a day. The timer skips a
  tick while an update operation or prompt is already active.
- **Check for updates** in Settings works as today.

### The prompt (macOS only)

A Cat Type–styled modal window (Tk `messagebox` cannot show three custom
buttons) titled "A new version of Cat Type is available", reading
"Cat Type {new} is available — you have {current}." with three buttons:

| Button | Default | Effect |
|---|---|---|
| Install Update | yes (Return) | Start download, verify, install, relaunch. |
| Remind Me Later | Escape / window close | Dismiss. The next due automatic check (24 h) prompts again. |
| Skip This Version | | Record `{new}` as skipped. Automatic checks stay silent for that version; a newer version prompts normally. |

**Focus.** A prompt raised by an **automatic** check appears on top but must
not take keyboard focus or activate Cat Type. The user is usually typing in
another app, and a keypress must never answer the prompt. It accepts keys only
after the user clicks it. A prompt raised by a **manual** check (the user just
pressed the button) may take focus normally.

A **manual** check always shows the prompt, even for a skipped version
(Sparkle behaves the same way). The skipped version is stored in the existing
`update-state.json` beside `last_successful_check`.

When installation is unavailable (see Fallbacks), no prompt appears. Settings
shows "Cat Type {new} is available." with the reason and the existing release
link, as today.

### Installing

After **Install Update**, the prompt window turns into a progress window, as
Sparkle's does, because the Settings status line is usually closed after an
automatic check:

- A progress bar with the existing stages ("Downloading…", "Verifying…",
  "Preparing…", "Installing…"), also mirrored to the Settings status line.
- A **Cancel** button while downloading, which discards the download and
  leaves the current app running.
- On failure: the error message, a **Download Manually** button that opens
  the release page, and **Close**.

After the handoff Cat Type quits, the helper swaps the app, and the new
version opens on its own within a few seconds.

The controller's `confirm_update` hook, which today returns yes/no, needs a
three-way answer on macOS (install, skip, later) and a way to feed progress,
errors, and cancellation back to the open window.

## Install Mechanics

These follow Sparkle 2's installer (`SUPlainInstaller`, `SUFileManager`,
`AppInstaller`), read from its source.

### Capability (availability check)

Automatic installation is available only when all hold. Otherwise
`availability()` returns `can_install=False` with a specific reason and the
manual release link:

- The app is frozen and `sys.executable` resolves to
  `<bundle>.app/Contents/MacOS/Cat Type`.
- The bundle path is not translocated (`/AppTranslocation/` in the path) and
  not on a read-only volume (for example, running from the mounted DMG).
- The bundle's parent folder allows creating and renaming entries (probe as
  the Linux installer does), and the user can write to the bundle itself.
- The bundled update helper (below) is present and executable.

### Prepare (before Cat Type quits)

1. Confirm the verified package's name equals the selected macOS DMG asset.
2. Mount the DMG read-only, without opening Finder or browsing
   (`hdiutil attach -readonly -nobrowse -noautoopen` to a private mount
   point). Always detach, even on failure.
3. Require exactly one `Cat Type.app` at the volume root. Copy it with `ditto`
   into a new hidden staging folder in the **same parent folder** as the
   installed bundle, so the swap is a same-volume rename.
4. Validate the staged bundle (all must pass):
   - `codesign --verify --deep --strict` succeeds.
   - It satisfies the requirement
     `anchor apple generic and identifier "com.fungusta.cat-type" and certificate leaf[subject.OU] = "9B98U2J5Q2"`.
   - `spctl --assess --type execute` accepts it (Developer ID and notarized).
   - Its `CFBundleShortVersionString` equals the update's version and is newer
     than the running `APP_VERSION` (Sparkle's downgrade check).
5. Release the staged bundle from quarantine (remove `com.apple.quarantine`
   recursively). Copy the installed bundle's owner and group onto it.

Any failure deletes the staging folder and reports an error. The installed app
is untouched.

### Handoff

`start()` takes a lock (as the Linux installer does), copies the helper out of
the bundle to a private temporary folder, and launches it detached with the
Cat Type PID, process start time, installed bundle path, staged bundle path,
and staging folder. Cat Type then shuts down through the existing
`install-started` path.

The helper is copied out first, as Sparkle does with its Autoupdate tool, so
the swap never moves files out from under a running process.

### Helper (runs after Cat Type quits)

1. Wait until the Cat Type PID exits, confirming its start time so a reused
   PID is not mistaken for Cat Type. Give up after 5 minutes, removing staging
   and the lock.
2. **Atomic swap:** `renamex_np(staged, installed, RENAME_SWAP)`. The installed
   path now holds the new app, and the staging path holds the old one.
3. **Fallback** if the swap fails: rename the installed bundle into the
   staging folder, then rename the new bundle into place. If the second rename
   fails, rename the old bundle back.
4. On success, set the new bundle's modification time to now so Finder and
   LaunchServices notice the change. On macOS 14.4 and later, run
   `gktool scan` on it.
5. Delete the old bundle and the staging folder, release the lock.
6. Relaunch through LaunchServices (`/usr/bin/open` on the installed path), so
   macOS treats it as a normal app launch.
7. If the swap failed and the old bundle is back in place, relaunch the old
   app instead so the user isn't left with Cat Type closed.

Like Sparkle, there is no rollback after a successful swap if the new version
then fails to start. The pre-install signature and version checks are the
guard.

### Helper form

The helper is a small C program compiled by `scripts/build_macos_direct.sh`
with the Xcode command-line tools (already required for signing), bundled
through `CatType.spec` beside the app's other binaries (found at runtime via
`sys._MEIPASS`), and signed with the app. C is used because the
atomic swap needs `renamex_np`, which no shell tool exposes, and because a
Python helper running from inside the bundle would be moved by its own swap.

## Fallbacks

| Situation | Behaviour |
|---|---|
| Source checkout | Unchanged "Source checkouts cannot update themselves" message. |
| Translocated, on the DMG, or read-only volume | "Move Cat Type to Applications to enable automatic updates" plus release link. |
| Folder or bundle not writable | "Cat Type can't update itself in this location" plus release link. |
| Leftover lock or staging from a crashed attempt | Remove it if its helper is no longer running, then continue. |
| Download, checksum, mount, or signature failure | "Update failed: …" in Settings. Current app keeps running. |

## Input Monitoring

macOS stores the Input Monitoring grant against the app's code-signing
designated requirement (bundle ID plus team). The new bundle has the same
requirement, so the grant should carry over. This must be confirmed on a real
signed build, since CI cannot grant the permission.

## Testing and Verification

- **Unit tests** (`tests/test_platform_updater.py` and
  `tests/test_update_controller.py`, with injected command runners and file
  operations, as the Linux installer tests do): capability rules, DMG asset
  matching, staging location, every validation failure, version and downgrade
  checks, quarantine and ownership steps, lock handling, skip and remind
  behaviour, manual check ignoring the skipped version, the startup check
  now firing on macOS, the in-session timer respecting `is_due` and active
  operations, automatic prompts not taking focus, and the progress window's
  cancel and failure states.
- **Helper tests:** build the C helper and exercise swap, fallback, restore on
  failure, PID-reuse protection, timeout, and relaunch against throwaway
  bundles in a temporary folder.
- **Release workflow smoke** (both macOS runners): run `prepare` against the
  just-built notarized DMG with the "current" version faked lower, then run the
  helper to swap a copy of the built app in a temporary folder.
- **Manual check before the first release:** on a real Mac, install the
  previous release in `/Applications`, update to a test build through the
  prompt, and confirm the new version relaunches with Input Monitoring still
  granted and settings intact.

## Rollout

Users on releases before this feature still update manually once. The release
notes for the first version with it should say that later updates install
themselves. Update the README update section, `docs/macos-release.md`, and the
note in `2026-08-12-windows-linux-auto-updates-design.md` that macOS is manual.

## Left to the Builder

- Exact wording and styling of the prompt window, within the existing Settings
  look.
- Names of the staging folder, lock, and helper executable.
- How the helper reports failures (a log file in the user's Library is fine).
- The precise smoke-test harness shape.
