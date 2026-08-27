# Cat Type

Cat Type is a desktop companion for Windows, macOS, and Linux that makes a tiny
animated cat appear while you type. Its paws follow the side of the keyboard
you use, spacebar taps both paws, fast typing makes it excited, and it fades
away after you stop.

Cat Type was inspired by [Bongo Cat on Steam](https://store.steampowered.com/app/3419430/Bongo_Cat/).
I loved the idea of a tiny companion that reacts as you type and wanted to
create my own take on it.

On Windows, Cat Type puts the companion beside the place where text is being
inserted rather than on the taskbar. Its four-frame gray and ginger tabby
sprite sheets are original artwork created for this project; it does not
extract or redistribute Bongo Cat's game assets.

## Install on Windows

Download and run **Cat Type Setup.exe**. The installer adds Cat Type to the
Start Menu and can optionally add a desktop shortcut and launch it when you
sign in.

You can also use the portable **Cat Type.exe** without installing it.

When Cat Type is running, its icon lives in the Windows system tray. Double
click the tray icon to open Settings, or right click it to enable/disable the
cat, open Settings, or quit.

## Install on macOS

Download **Cat-Type-macOS-arm64.dmg** for Apple Silicon (M1 and newer), or
**Cat-Type-macOS-x64.dmg** for an Intel Mac, then drag Cat Type to
Applications. These community builds are not notarized, so the first launch
may require right clicking the app and choosing **Open**. Allow Cat Type under
**System Settings > Privacy & Security > Input Monitoring** when macOS asks.

## Install on Linux

Download **Cat-Type-Linux-x64.tar.gz** for most PCs or
**Cat-Type-Linux-arm64.tar.gz** for ARM64 devices, extract it, and run
`Cat Type`. The overlay and global keyboard listener require X11 or XWayland.
A system tray implementation such as AppIndicator is also recommended.

On Windows, Cat Type uses native accessibility APIs to place the cat beside the
text caret when that geometry is available. If no usable caret can be detected,
it falls back to the current mouse pointer. macOS and Linux currently use the
mouse pointer directly.

## Settings

Settings are saved for the current user and take effect immediately:

- Enable or pause the typing companion.
- Choose alternating tabbies, gray only, or ginger only.
- Change the cat size from 60% to 175%.
- Choose which corner of the caret the cat prefers.
- Adjust how long the cat remains and how quickly it fades.
- Start Cat Type automatically when you sign in.
- View all-time activity and 1-day, 7-day, or 30-day trends as an exact line
  or columns; Cat Type remembers the selected chart view.

Press **Ctrl+Alt+Q** at any time to quit.

## Automatic updates

Packaged Windows and Linux builds check GitHub for a newer stable release at
startup. After a successful check, Cat Type waits at least 24 hours before
checking automatically again. You can check at any time with **Check for
updates** in Settings. Cat Type always asks for confirmation before it
downloads or installs an available update; declining leaves the running copy
unchanged.

Downloads come from the public Cat Type GitHub release and are accepted only
when their SHA-256 digest matches the exact asset entry in the release's
`SHA256SUMS.txt`. This detects corruption and asset mix-ups, but the checksum
and download have the same GitHub release as their trust source. Current
releases are not code-signed, and macOS builds are not notarized, so checksum
verification is not a substitute for platform signing.

On Windows, a confirmed update starts the verified installer silently, shuts
down Cat Type through its normal cleanup path, and relaunches the new version.
When updating an older version that does not support graceful shutdown, the
installer may force-close it; the in-app confirmation is the user's consent
for that fallback.

On Linux, self-installation is limited to the frozen portable executable from
the published tarball when its containing folder is writable. Cat Type stages
the replacement beside the current executable, atomically keeps the old copy
as a `.previous` backup, and rolls back and relaunches that backup if the new
copy fails its startup health check. Installations in protected locations are
left unchanged and show instructions to update manually. The replacement
helper requires Linux `/proc` plus the standard `sh`, `mv`, `sed`, and `awk`
command-line tools included by mainstream desktop distributions.

macOS updates remain manual, and apps run from source never self-install.
Checking or downloading contacts GitHub's API and release download hosts; Cat
Type does not include keyboard input or local usage metrics in those requests.

## Run from source

On Windows, from PowerShell:

```powershell
.\start.ps1
```

The first run creates a local Python virtual environment and installs the
runtime dependencies. After starting, type in Notepad, Word, a browser text
box, or VS Code. The Settings window opens automatically on the first run.

On macOS or Linux:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python cat_type.py
```

For diagnostics, run it in a visible terminal:

```powershell
.\.venv\Scripts\python.exe .\cat_type.py --debug
```

## Build

Create the Windows portable app and installer:

```powershell
.\build.ps1
```

The outputs are `dist\Cat Type.exe` and, when Inno Setup 6 is installed,
`dist\Cat Type Setup.exe`. They bundle Python, the runtime dependencies, the
application icon, and both tabby sprite sets. Windows may warn about local
builds because they are not code-signed.

On macOS or Linux:

```bash
python scripts/build_icon.py
python -m pip install -r requirements.txt -r requirements-build.txt
python -m PyInstaller --noconfirm --clean CatType.spec
```

The macOS output is `dist/Cat Type.app`; the Linux output is
`dist/Cat Type`. Push a tag such as `v1.0.20` to build every supported
architecture and publish the assets together on a GitHub Release.

## Privacy behavior

- The keyboard listener classifies each key as left, right, both, or an
  alternating fallback, then immediately discards the key itself.
- While enabled, Cat Type persists only aggregate keystroke counts by local
  day and hour in `usage.json`. It never stores key names, typed text, app
  names, or window titles, and it does not send usage metrics over the network.
- On Windows, UI Automation's password-field flag is checked before showing
  the cat.
- The overlay is click-through and cannot take focus from the text field.

## How caret tracking works on Windows

Cat Type combines two Windows mechanisms:

1. UI Automation `TextPattern2.GetCaretRange` for modern accessible text
   controls.
2. `GetGUIThreadInfo` and `rcCaret` as a fallback for traditional Win32
   controls.

Some canvas-based editors, terminals, games, elevated applications, or other
controls do not publish a usable caret. In those cases, Cat Type falls back to
the current mouse pointer. Password fields detected through UI Automation stay
hidden and never use the pointer fallback.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

See [`assets/SPRITES.md`](assets/SPRITES.md) to edit or replace the sprite
sheet.
