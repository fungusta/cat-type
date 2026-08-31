# Cat Type

Cat Type is a desktop companion for Windows, macOS, and Linux that makes a tiny
animated cat appear while you type. Its paws follow the side of the keyboard
you use, spacebar taps both paws, fast typing makes it excited, and it fades
away after you stop.

Cat Type was inspired by [Bongo Cat on Steam](https://store.steampowered.com/app/3419430/Bongo_Cat/).
I loved the idea of a tiny companion that reacts as you type and wanted to
create my own take on it.

On Windows, Cat Type puts the companion beside the place where text is being
inserted. On macOS and Linux, it uses pointer placement instead. Its four-frame
cat sprite sheets are original artwork created for this project; it does not
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

Cat Type for macOS is distributed only through the Mac App Store. On first
launch, open Settings and choose **Enable Input Monitoring**. macOS controls
the permission under **System Settings > Privacy & Security > Input
Monitoring**. Cat Type never shows a separate consent alert.

## Install on Linux

Download **Cat-Type-Linux-x64.tar.gz** for most PCs or
**Cat-Type-Linux-arm64.tar.gz** for ARM64 devices, extract it, and run
`Cat Type`. The overlay and global keyboard listener require X11 or XWayland.
A system tray implementation such as AppIndicator is also recommended.

On Windows, Cat Type uses native accessibility APIs to place the cat beside the
text caret when that geometry is available, falling back to the current mouse
pointer when needed. On macOS, it prefers the latest primary-click position for
eight seconds and otherwise uses the current pointer. Linux uses the current
pointer directly.

## Settings

Settings are saved for the current user and take effect immediately:

- Enable or pause the typing companion.
- Choose gray, ginger, charcoal, brown-tabby, white, or black-and-white cats,
  or cycle through all of them.
- Change the cat size from 60% to 175%.
- Choose which corner of the caret or pointer the cat prefers.
- Adjust how long the cat remains and how quickly it fades.
- Start Cat Type automatically when you sign in.
- View all-time activity and navigate through current or previous 1-day, 7-day,
  or 30-day trends as an exact line or columns; Cat Type remembers the selected
  chart view.

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

macOS updates are delivered through the Mac App Store, and apps run from source
never self-install.
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

On Linux:

```bash
python scripts/build_icon.py
python -m pip install -r requirements.txt -r requirements-build.txt
python -m PyInstaller --noconfirm --clean CatType.spec
```

The Linux output is `dist/Cat Type`. Push a tag such as `v1.0.31` to build the
Windows and Linux architectures and publish those assets on a GitHub Release.

The only supported macOS package is the sandboxed Mac App Store build. See
[`docs/app-store-release.md`](docs/app-store-release.md) for its build and
upload workflow.

## Privacy behavior

- The keyboard listener classifies each key as left, right, both, or an
  alternating fallback, then immediately discards the key itself.
- While enabled, Cat Type persists only aggregate keystroke counts by local
  day and hour in `usage.json`. It never stores key names, typed text, app
  names, or window titles, and it does not send usage metrics over the network.
- On Windows, accessible password fields are detected before showing the cat.
- macOS pointer placement cannot identify password fields, apps, controls, or
  window titles.
- The overlay is click-through and cannot take focus from the text field.

## How caret tracking works

On Windows, Cat Type combines two mechanisms:

1. UI Automation `TextPattern2.GetCaretRange` for modern accessible text
   controls.
2. `GetGUIThreadInfo` and `rcCaret` as a fallback for traditional Win32
   controls.

On macOS, Cat Type remembers only the coordinate and time of the latest primary
click. If typing starts within eight seconds, the cat anchors beside that click;
otherwise it anchors beside the pointer's current position. The anchor remains
fixed until that visible typing burst ends. Cat Type never asks which app or
control was clicked.

Some canvas-based editors, terminals, games, elevated applications, or other
controls do not publish a usable caret. On Windows, Cat Type falls back to the
current mouse pointer. Windows password fields detected through UI Automation
stay hidden and never use the pointer fallback.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

See [`assets/SPRITES.md`](assets/SPRITES.md) to edit or replace the sprite
sheet.
