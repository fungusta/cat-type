# Cat Type

Cat Type is a desktop companion for Windows, macOS, and Linux that makes a tiny
animated cat appear while you type. It alternates paws with each key press,
becomes excited during fast typing, and fades away after you stop.

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

Windows uses native accessibility APIs to place the cat beside the text caret.
The initial macOS and Linux builds fall back to the mouse pointer when a native
caret rectangle is unavailable.

## Settings

Settings are saved for the current user and take effect immediately:

- Enable or pause the typing companion.
- Choose alternating tabbies, gray only, or ginger only.
- Change the cat size from 60% to 175%.
- Choose which corner of the caret the cat prefers.
- Adjust how long the cat remains and how quickly it fades.
- Start Cat Type automatically when you sign in.

Press **Ctrl+Alt+Q** at any time to quit.

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
`dist/Cat Type`. Push a tag such as `v1.0.3` to build every supported
architecture and publish the assets together on a GitHub Release.

## Privacy behavior

- The keyboard listener discards each key after recognizing the
  **Ctrl+Alt+Q** quit shortcut and emitting an activity signal.
- Cat Type never reconstructs text, writes keystrokes to disk, or sends input
  over the network.
- On Windows, UI Automation's password-field flag is checked before showing
  the cat.
- The overlay is click-through and cannot take focus from the text field.

## How caret tracking works on Windows

Cat Type combines two Windows mechanisms:

1. UI Automation `TextPattern2.GetCaretRange` for modern accessible text
   controls.
2. `GetGUIThreadInfo` and `rcCaret` as a fallback for traditional Win32
   controls.

Some canvas-based editors, terminals, games, or applications that do not
publish an accessible caret cannot be tracked. Elevated applications are also
outside the reach of a normally launched process.

When a focused, non-password text control is available but does not publish a
usable caret rectangle, Cat Type falls back to the matching corner of the
active monitor's work area.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

See [`assets/SPRITES.md`](assets/SPRITES.md) to edit or replace the sprite
sheet.
