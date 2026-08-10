# Cross-Platform Icon Packaging Design

## Goal

Make the packaged Linux and macOS applications start with the correct runtime
icon and native backends, and prevent a release when its PyInstaller archive
omits any required runtime asset.
Windows remains covered by the same platform mapping so the existing working
package cannot drift from the other platforms.

## Problem

`CatType.spec` bundles a platform-native icon: `.ico` on Windows, `.icns` on
macOS, and `.png` on Linux. The runtime currently always looks for
`assets/cat-type.ico`. The packaged macOS and Linux applications therefore
reach tray startup without the file that `Image.open()` requires and exit with
`FileNotFoundError`.

The existing CI confirms that PyInstaller produces an artifact, but it does
not inspect that artifact for runtime assets. A successful build can therefore
publish an application that fails immediately after launch.

A native Linux startup probe also showed that display-dependent PyInstaller
discovery omitted `pynput`'s Xorg keyboard and mouse modules. Once those were
included, opening first-run Settings exposed a second omission,
`PIL._tkinter_finder`. These modules must be selected without importing GUI
backends during a headless build.

## Design

### Shared platform asset selection

Add a small `platform_assets.py` module that maps a Python platform string to
the runtime icon filename:

- `win32` -> `cat-type.ico`
- `darwin` -> `cat-type.icns`
- every other platform, including Linux -> `cat-type.png`

Both `cat_type.py` and `CatType.spec` will use this function. Source runs and
packaged runs will therefore resolve the same platform-specific asset, and the
build configuration will not maintain a separate mapping that can drift.

The same module will list required Python modules without importing them:

- every platform includes `PIL._tkinter_finder` for Settings previews;
- macOS includes the `pynput` and `pystray` Darwin backends;
- Linux includes the `pynput` and `pystray` Xorg backends.

`CatType.spec` will use these explicit names instead of `collect_submodules`
for GUI backends, because discovery imports those packages and fails when a
headless build has no active display.

### Finished-package validation

Add `scripts/check_bundled_icon.py`. It will open a completed PyInstaller
CArchive, derive the expected `assets/<icon filename>` entry from the shared
mapping, inspect the embedded PYZ module table, and exit unsuccessfully with a
clear message when an icon or required runtime module is missing.

The build and release workflows will run this checker after PyInstaller on
every matrix platform. macOS will pass the executable inside the `.app`
bundle; Windows and Linux will pass their top-level executable. Artifact upload
and release packaging will remain downstream of this check.

### Error behavior

The checker will fail closed: an unreadable PyInstaller archive, missing icon,
or missing runtime module stops the job. Its success output will name every
verified entry so CI logs show which platform assets were checked.

The application will retain its current tray-start behavior. The fix ensures
the required file exists rather than hiding asset errors at runtime.

## Tests

Unit tests will cover icon and runtime-module mappings for Windows, macOS, and
Linux. They will verify that archive validators accept complete platform
contents and reject another platform's icon, missing Xorg modules, or a missing
Pillow Tk bridge.

The tests will be written and observed failing before implementation. After
the implementation passes them, the full unit test suite will run. A local
PyInstaller build will then be inspected with the same checker used by CI.
Linux additionally receives an Ubuntu 22.04/Xvfb package startup probe during
development and CI. The smoke gate rejects early exit, keyboard-listener
failure, missing modules, and Tkinter callback exceptions before artifact
upload. macOS executable generation remains the responsibility of its native
GitHub Actions runners, where the archive checker runs before artifacts can be
published.

## Out of Scope

- Native Wayland global-input support; the documented X11/XWayland requirement
  remains unchanged.
- Native caret accessibility providers for Linux or macOS.
- Code signing or notarization.
- Changes to artwork or application behavior unrelated to startup packaging.
