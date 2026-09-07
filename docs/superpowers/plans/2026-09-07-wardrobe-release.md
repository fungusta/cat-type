# Cat Type v1.0.36 release plan

**Goal:** Publish the approved achievement wardrobe as the next stable release.

**Architecture:** Keep the existing five-platform GitHub Actions release pipeline.
Synchronize version metadata, include wardrobe regression tests and accessory
asset checks in CI, validate the candidate, then tag the exact tested commit.

**Tech stack:** Python 3.12, unittest, PyInstaller, Inno Setup, GitHub Actions/CLI.

## Constraints

- User explicitly authorized creating a new release.
- Version is 1.0.36; never move or reuse a published tag.
- Ship Windows x64 installer, signed/notarized macOS x64 and arm64 DMGs,
  Linux x64 and arm64 tarballs, and SHA256SUMS.txt.
- Preserve installed applications and live user data. Tests use temporary paths.
- Do not publish until the Release workflow's five-platform dry run passes.

## Steps

- [x] Set release tests to 1.0.36, verify their expected failure, then update
  app_version.py, CatType.spec, packaging/CatType.iss, packaging/version_info.txt
  and README.md. Run `scripts/check_release_version.py v1.0.36`.
- [x] Add a failing missing-accessory test for the bundle validator. Implement
  `validate_bundled_accessories(entries)` from catalog IDs and invoke it in the
  existing checker. Add achievements, accessory artwork, wardrobe and integration
  test modules to both workflow test commands.
- [x] Run the full local suite and build a versioned Windows candidate; verify
  package metadata, bundled accessories, and candidate diff.
- [x] Commit and fast-forward main, push without force, dispatch Release on main,
  and wait for both ordinary CI and all five dry-run builds at the same commit.
- [x] Create and push annotated v1.0.36 on the tested commit. Wait for all tag
  builds and publication. Replace generated notes with reviewed wardrobe notes.
- [x] Verify latest release/tag/commit, all six assets, and downloaded SHA-256
  digests. Record final release evidence and return the public release URL.
