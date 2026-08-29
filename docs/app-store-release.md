# Mac App Store release

The App Store build is a separate distribution channel from the GitHub DMG.
It enables App Sandbox, asks for explicit consent before requesting Input
Monitoring access, disables the direct-download updater, and packages the app
as a signed installer. Because App Sandbox does not permit Cat Type to inspect
other applications through the macOS Accessibility API, this distribution
uses the mouse-pointer placement fallback rather than native caret tracking.

## Account resources

- Team ID: `9B98U2J5Q2`
- Bundle ID: `com.fungusta.cat-type`
- App Store provisioning profile ID: `4LV2P28WS7`
- Application signing identity: `3rd Party Mac Developer Application: Peter Fung (9B98U2J5Q2)`
- Installer signing identity: `3rd Party Mac Developer Installer: Peter Fung (9B98U2J5Q2)`

The certificates and their private keys must be present in the login keychain.
Download the current profile when needed:

```bash
asc --profile cat-type-release profiles download \
  --id 4LV2P28WS7 \
  --output "$TMPDIR/Cat-Type-App-Store.provisionprofile"
```

## Build

Use a positive integer for `CAT_TYPE_BUILD_NUMBER`. It must increase for every
build uploaded for the same marketing version.

```bash
CAT_TYPE_APP_STORE_PROFILE="$TMPDIR/Cat-Type-App-Store.provisionprofile" \
CAT_TYPE_BUILD_NUMBER=30 \
./scripts/build_macos_app_store.sh
```

The signed installer is written to
`dist/Cat-Type-macOS-App-Store.pkg`. The script verifies the application and
installer signatures before it succeeds.

## Upload

Create the App Store Connect app record once with the macOS platform, the
bundle ID above, primary locale `en-US`, and a stable SKU. Then upload the
package with its numeric App Store Connect app ID:

```bash
asc --profile cat-type-release builds upload \
  --app APP_STORE_CONNECT_APP_ID \
  --pkg "dist/Cat-Type-macOS-App-Store.pkg" \
  --version 1.0.29 \
  --build-number 30 \
  --wait
```

Do not submit the version for App Review until the processed build, privacy
answers, description, support URL, screenshots, category, age rating, and
review notes have all been checked in App Store Connect.
