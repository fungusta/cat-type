# Mac App Store release

The Mac App Store package is the only supported macOS distribution. GitHub
releases intentionally contain no macOS DMG. The package enables App Sandbox,
uses macOS's native Input Monitoring permission as the source of truth, relies
on the App Store for updates, and ships as a signed installer. Its Settings
window explains the on-device activity handling inline instead of presenting a
second consent alert.

Cat Type does not inspect other applications through the macOS Accessibility
API. It places the cat beside the most recent primary click when that click is
at most eight seconds old, otherwise beside the current pointer. The position
is frozen for each visible typing burst. Only the latest click coordinate and
timestamp are held in memory; the clicked app or control is never identified.

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
CAT_TYPE_BUILD_NUMBER=32 \
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
  --version 1.0.31 \
  --build-number 32 \
  --wait
```

Do not submit the version for App Review until the processed build, privacy
answers, description, support URL, screenshots, category, age rating, and
review notes have all been checked in App Store Connect.
