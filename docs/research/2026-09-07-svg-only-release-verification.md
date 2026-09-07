# SVG-only release candidate verification

Candidate: Cat Type 1.0.34.

All six canonical cat styles now use the approved SVG masters. Existing style
identifiers remain valid, and temporary `-svg` selections normalize to the
matching canonical cat. The masters are byte-for-byte unchanged from the
approved SVG collection. Settings, animation previews, exports, and all platform
surfaces share the SVG renderer.

Removed 48 obsolete raster artwork/metadata files and two sprite rebuild scripts.
Native application icons are generated from the gray SVG at their target sizes.
The package verifier requires all six vector masters and rejects obsolete frame
directories while permitting native application icons.

## Local checks

- Full suite: 322 tests ran in 25.215 seconds; 291 passed and 31 platform tests
  were skipped. The existing Tk `ThemeChanged` teardown diagnostic did not fail
  the suite.
- Tests exercise saved-style migration, real rendered poses, toe-bean visibility,
  native image and mask boundaries, actual Windows overlay captures, settings,
  focused preview interaction, SVG export, and package contracts.
- `scripts/check_release_version.py v1.0.34` and `git diff --check` pass.
- Separate Windows PyInstaller build succeeds. Its file version is 1.0.34.0;
  all six embedded SVG masters match source bytes, and package validation finds
  no obsolete raster animation frames.
- Frozen SVG preview opens successfully. Frozen normal startup and graceful
  shutdown pass with isolated settings directories after confirming that no
  existing overlay instance owns the Windows mutex.
- Inspected all 24 poses in the exported preview sheet and the frozen preview.
  The approved rounded ears, connected nose/mouth, and hidden tapping toe beans
  remain intact.

The installed application and live user settings were not modified. Native
macOS/Linux release validation is performed by the five-platform Release dry run
before the immutable release tag is created; the local checks above ran on Windows.
