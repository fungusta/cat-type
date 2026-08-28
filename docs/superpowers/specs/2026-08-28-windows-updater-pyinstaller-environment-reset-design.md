# Windows Updater PyInstaller Environment Reset Design

## Problem

Cat Type's frozen Windows process launches the downloaded Inno Setup installer
without overriding its environment. The installer inherits PyInstaller's private
process state and passes it to the newly installed `Cat Type.exe`. Because the
replacement executable has the same path as the old executable, its bootloader
can treat the relaunch as a child process and reuse the old `_MEI` extraction
directory. The old one-file parent deletes that directory during shutdown, so
the replacement process fails to load `python312.dll` on its first relaunch.

## Decision

`WindowsInstaller.start()` will pass a copy of the current environment to
`subprocess.Popen` with `PYINSTALLER_RESET_ENVIRONMENT` set to `"1"`. This is
PyInstaller's documented signal that a spawned process must be treated as a new
top-level application instance and unpack into a fresh `_MEI` directory.

The environment copy preserves all unrelated variables needed by Inno Setup.
The current Cat Type process's environment will not be mutated.

## Alternatives Considered

- Remove every `_PYI_*` variable before launching the installer. This depends on
  private implementation details and can miss variables added by PyInstaller.
- Set the reset variable in the Inno Setup `[Run]` entry. This fixes only the
  final relaunch and leaves the installer itself running with inherited frozen
  process state.
- Pass `PYINSTALLER_RESET_ENVIRONMENT=1` at the Python-to-installer boundary.
  This is the selected option because it uses the public PyInstaller contract
  and sanitizes the whole external installer process tree.

## Testing

The Windows installer contract test will provide a sentinel environment variable,
start the installer through the existing recording process launcher, and assert
that:

- the installer receives `PYINSTALLER_RESET_ENVIRONMENT="1"`;
- unrelated environment values are preserved; and
- the existing silent flags and `shell=False` behavior remain unchanged.

The focused Windows installer tests and the full unit-test suite must pass.
