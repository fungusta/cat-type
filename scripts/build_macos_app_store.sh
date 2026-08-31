#!/bin/bash

set -euo pipefail

project_root="$(cd "$(dirname "$0")/.." && pwd)"
profile_path="${CAT_TYPE_APP_STORE_PROFILE:-}"
app_identity="${CAT_TYPE_APP_STORE_APP_IDENTITY:-3rd Party Mac Developer Application: Peter Fung (9B98U2J5Q2)}"
installer_identity="${CAT_TYPE_APP_STORE_INSTALLER_IDENTITY:-3rd Party Mac Developer Installer: Peter Fung (9B98U2J5Q2)}"
build_number="${CAT_TYPE_BUILD_NUMBER:-}"
python_command="${CAT_TYPE_PYTHON:-$project_root/.venv/bin/python}"
app_path="$project_root/dist/Cat Type.app"
package_path="$project_root/dist/Cat-Type-macOS-App-Store.pkg"
entitlements_path="$project_root/packaging/macos-app-store.entitlements"

retry() {
    local attempt=1
    local max_attempts=3
    until "$@"; do
        if (( attempt >= max_attempts )); then
            return 1
        fi
        echo "Command failed; retrying signing service request ($attempt/$max_attempts)." >&2
        sleep $((attempt * 3))
        ((attempt += 1))
    done
}

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "Mac App Store packages must be built on macOS." >&2
    exit 1
fi
if [[ -z "$profile_path" || ! -f "$profile_path" ]]; then
    echo "Set CAT_TYPE_APP_STORE_PROFILE to the downloaded .provisionprofile." >&2
    exit 1
fi
if [[ ! "$build_number" =~ ^[1-9][0-9]*(\.[0-9]+){0,2}$ ]]; then
    echo "Set CAT_TYPE_BUILD_NUMBER to one to three numeric segments." >&2
    exit 1
fi
if [[ "$python_command" == */* ]]; then
    if [[ ! -x "$python_command" ]]; then
        echo "Python interpreter is not executable: $python_command" >&2
        exit 1
    fi
elif ! command -v "$python_command" >/dev/null 2>&1; then
    echo "Python interpreter is not on PATH: $python_command" >&2
    exit 1
fi
if ! security find-identity -v -p codesigning | grep -Fq "$app_identity"; then
    echo "Missing Mac App Distribution identity: $app_identity" >&2
    exit 1
fi
if ! security find-identity -v | grep -Fq "$installer_identity"; then
    echo "Missing Mac Installer Distribution identity: $installer_identity" >&2
    exit 1
fi

cd "$project_root"
export CAT_TYPE_BUILD_NUMBER="$build_number"
export CAT_TYPE_CODESIGN_IDENTITY="$app_identity"
export CAT_TYPE_REQUIRE_SIGNING=1

"$python_command" scripts/build_icon.py
"$python_command" -m PyInstaller --noconfirm --clean CatType.spec
"$python_command" -m scripts.check_bundled_icon \
    "$app_path/Contents/MacOS/Cat Type"
cp "$profile_path" "$app_path/Contents/embedded.provisionprofile"
chmod -R a+rX "$app_path"

retry codesign --force --deep --strict --timestamp \
    --options runtime \
    --entitlements "$entitlements_path" \
    --sign "$app_identity" \
    "$app_path"
codesign --verify --deep --strict --verbose=2 "$app_path"

signed_entitlements="$(codesign --display --entitlements :- "$app_path" 2>/dev/null)"
grep -Fq "com.apple.security.app-sandbox" <<< "$signed_entitlements"
grep -Fq "9B98U2J5Q2.com.fungusta.cat-type" <<< "$signed_entitlements"

retry productbuild \
    --component "$app_path" /Applications \
    --sign "$installer_identity" \
    "$package_path"
pkgutil --check-signature "$package_path"

echo "$package_path"
