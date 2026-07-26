# Cat Type

Cat Type is a Windows desktop companion that makes a tiny animated cat appear
beside the active text caret while you type. It alternates paws with each key
press, becomes excited during fast typing, and fades away after you stop.

This is deliberately different from Bongo Cat on Steam: the companion is
attached to the place where text is being inserted rather than to the taskbar.
The project alternates between newly created four-frame gray and ginger tabby
sprite sheets; it does not extract or redistribute Steam game assets.

## Install

Download and run **Cat Type Setup.exe**. The installer adds Cat Type to the
Start Menu and can optionally add a desktop shortcut and launch it when you
sign in.

You can also use the portable **Cat Type.exe** without installing it.

When Cat Type is running, its icon lives in the Windows system tray. Double
click the tray icon to open Settings, or right click it to enable/disable the
cat, open Settings, or quit.

## Settings

Settings are saved for the current Windows user and take effect immediately:

- Enable or pause the typing companion.
- Choose alternating tabbies, gray only, or ginger only.
- Change the cat size from 60% to 175%.
- Choose which corner of the caret the cat prefers.
- Adjust how long the cat remains and how quickly it fades.
- Start Cat Type automatically when you sign in.

Press **Ctrl+Alt+Q** at any time to quit.

## Run from source

From PowerShell:

```powershell
.\start.ps1
```

The first run creates a local Python virtual environment and installs the one
runtime dependency. After starting, type in Notepad, Word, a browser text box,
or VS Code. The Settings window opens automatically on the first run.

For diagnostics, run it in a visible terminal:

```powershell
.\.venv\Scripts\python.exe .\cat_type.py --debug
```

## Build

Create the portable app and installer:

```powershell
.\build.ps1
```

The outputs are `dist\Cat Type.exe` and, when Inno Setup 6 is installed,
`dist\Cat Type Setup.exe`. They bundle Python, the runtime dependencies, the
application icon, and both tabby sprite sets. Windows may warn about local
builds because they are not code-signed.

## Privacy behavior

- The keyboard hook emits only an activity signal.
- Cat Type never converts key codes into characters, reconstructs text, writes
  keystrokes to disk, or sends input over the network.
- UI Automation's password-field flag is checked before showing the cat.
- The overlay is click-through and cannot take focus from the text field.

## How caret tracking works

Cat Type combines two Windows mechanisms:

1. UI Automation `TextPattern2.GetCaretRange` for modern accessible text
   controls.
2. `GetGUIThreadInfo` and `rcCaret` as a fallback for traditional Win32
   controls.

Some canvas-based editors, terminals, games, or applications that do not
publish an accessible caret cannot be tracked. Elevated applications are also
outside the reach of a normally launched process.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

See [`assets/SPRITES.md`](assets/SPRITES.md) to edit or replace the sprite
sheet.
