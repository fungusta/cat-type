# Cross-Platform Icon Packaging Design

## Goal

Make the packaged Linux and macOS applications start with the correct runtime
icon, and prevent a release when its PyInstaller archive omits that icon.
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

### Finished-package validation

Add `scripts/check_bundled_icon.py`. It will open a completed PyInstaller
CArchive, derive the expected `assets/<icon filename>` entry from the shared
mapping, and exit unsuccessfully with a clear message when that entry is
missing.

The build and release workflows will run this checker after PyInstaller on
every matrix platform. macOS will pass the executable inside the `.app`
bundle; Windows and Linux will pass their top-level executable. Artifact upload
and release packaging will remain downstream of this check.

### Error behavior

The checker will fail closed: an unreadable PyInstaller archive or a missing
icon stops the job. Its success output will name the verified archive entry so
CI logs show which platform asset was checked.

The application will retain its current tray-start behavior. The fix ensures
the required file exists rather than hiding asset errors at runtime.

## Tests

Unit tests will cover the icon filename for Windows, macOS, and Linux and will
verify that the archive-entry validator accepts the expected icon and rejects
an archive containing only another platform's icon.

The tests will be written and observed failing before implementation. After
the implementation passes them, the full unit test suite will run. A local
PyInstaller build will then be inspected with the same checker used by CI.
Because the host is Windows, Linux and macOS executable generation remains the
responsibility of their native GitHub Actions runners, where the checker runs
before artifacts can be published.

## Out of Scope

- Native Wayland global-input support; the documented X11/XWayland requirement
  remains unchanged.
- Native caret accessibility providers for Linux or macOS.
- Code signing or notarization.
- Changes to artwork or application behavior unrelated to startup packaging.
