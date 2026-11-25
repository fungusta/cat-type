# Direct macOS release

Cat Type is distributed for macOS as signed and notarized GitHub Release disk
images. The release publishes separate Intel and Apple Silicon DMGs, does not
use App Sandbox, and does not submit builds to App Store Connect for review.
This distribution model allows the user to grant Input Monitoring, which Cat
Type needs to react to typing in other applications.

Cat Type does not inspect other applications through the macOS Accessibility
API. It places the cat beside the most recent primary click when that click is
at most eight seconds old, otherwise beside the current pointer. Only the
latest click coordinate and timestamp are held in memory; the clicked app or
control is never identified.

## Account resources

- Team ID: `9B98U2J5Q2`
- Bundle ID: `com.fungusta.cat-type`
- Signing identity: `Developer ID Application: Peter Fung (9B98U2J5Q2)`

The Developer ID Application certificate and its private key must be present
in the login keychain for a local release build. No provisioning profile or
Mac Installer Distribution certificate is required.

## Local build

Install the disk image tool and Python dependencies first:

```bash
brew install create-dmg
python -m pip install -r requirements.txt -r requirements-build.txt
```

Then build the app and architecture-specific DMG:

```bash
CAT_TYPE_BUILD_NUMBER=1 ./scripts/build_macos_direct.sh
```

`CAT_TYPE_BUILD_NUMBER` accepts one to three numeric segments and defaults to
`1`. Set `CAT_TYPE_PYTHON` to use a Python interpreter other than
`.venv/bin/python`. The output is `dist/Cat-Type-macOS-arm64.dmg` on Apple
Silicon or `dist/Cat-Type-macOS-x64.dmg` on Intel.

The script requires a Developer ID identity, applies the hardened runtime,
verifies the app and disk image signatures, and verifies the disk image. A
local DMG still needs notarization before public distribution.

The build compiles the self-update helper (`packaging/macos_update_helper.c`)
with the Xcode command-line tools through `CatType.spec`, so it ships in
`Contents/Frameworks/cat-type-update-helper` and is signed with the app.

## Self-update

Installed copies update themselves from the notarized DMG; see the README's
Automatic updates section. CI smoke-tests the helper swap on every macOS build
and, in the release workflow, the full prepare-and-swap path against the
notarized DMG (`python -m scripts.smoke_macos_update`).

Before the first release that ships the updater, and after any change to the
updater, check on a real Mac:

1. Install the previous release in `/Applications`, grant Input Monitoring,
   and confirm the cat appears when typing.
2. On a fork, publish notarized test builds of the branch (for example
   `v1.0.61` and `v1.0.62`) with `GITHUB_LATEST_RELEASE_URL` pointed at the
   fork in those test builds only.
3. In the first test build, press **Check for updates**, choose
   **Install Update**, and confirm Cat Type quits and reopens as the newer
   version within about ten seconds, with Input Monitoring still granted and
   settings and achievements intact.
4. Let an automatic check find an update while typing in another app; confirm
   the prompt appears without taking focus and responds to a mouse click.
5. Repeat from `~/Applications/Cat Type 2.app`, and confirm that running from
   the mounted DMG shows the "Move Cat Type to Applications" message.

## Notarization

The release workflow submits each signed DMG with `xcrun notarytool`, waits for
Apple to accept it, staples the ticket, validates the ticket, and runs a
Gatekeeper assessment before uploading the artifact.

For a local notarization using an App Store Connect API key:

```bash
xcrun notarytool submit "dist/Cat-Type-macOS-arm64.dmg" \
  --key "/path/to/AuthKey_KEY_ID.p8" \
  --key-id "KEY_ID" \
  --issuer "ISSUER_ID" \
  --wait
xcrun stapler staple "dist/Cat-Type-macOS-arm64.dmg"
xcrun stapler validate "dist/Cat-Type-macOS-arm64.dmg"
spctl --assess --type open --context context:primary-signature --verbose=4 \
  "dist/Cat-Type-macOS-arm64.dmg"
```

Use the x64 filename when building on Intel.

## GitHub Actions

The `Release` workflow builds `Cat-Type-macOS-x64.dmg` on `macos-15-intel`
and `Cat-Type-macOS-arm64.dmg` on `macos-15`. A version tag publishes both
notarized DMGs together with the Windows and Linux assets and
`SHA256SUMS.txt`. A manual workflow run builds and verifies the artifacts
without publishing a GitHub Release.

Configure this repository variable:

- `APPLE_TEAM_ID` — `9B98U2J5Q2`

Configure these repository secrets:

- `APPLE_DEVELOPER_ID_CERT_BASE64`
- `APPLE_DEVELOPER_ID_CERT_PASSWORD`
- `ASC_KEY_ID`
- `ASC_ISSUER_ID`
- `ASC_PRIVATE_KEY_B64`

The certificate secret is a base64-encoded PKCS#12 containing the Developer ID
Application certificate and private key. `scripts/macos-direct-credentials.sh`
validates the identity and team before installing it in a temporary keychain.
The cleanup step removes that keychain, the decoded certificate material, and
the temporary notarization key even after a failed build.
