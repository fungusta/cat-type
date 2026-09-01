#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "$0")/.." && pwd)"
identity="${CAT_TYPE_DEVELOPER_ID_APPLICATION_IDENTITY:-${CAT_TYPE_CODESIGN_IDENTITY:-Developer ID Application: Peter Fung (9B98U2J5Q2)}}"
build_number="${CAT_TYPE_BUILD_NUMBER:-1}"
python_command="${CAT_TYPE_PYTHON:-$project_root/.venv/bin/python}"
app_path="$project_root/dist/Cat Type.app"

case "$(uname -m)" in
    arm64) package_arch="arm64" ;;
    x86_64) package_arch="x64" ;;
    *)
        echo "Unsupported macOS architecture: $(uname -m)" >&2
        exit 1
        ;;
esac
dmg_path="${CAT_TYPE_MACOS_DMG_PATH:-$project_root/dist/Cat-Type-macOS-$package_arch.dmg}"

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
    echo "Direct macOS packages must be built on macOS." >&2
    exit 1
fi
if [[ ! "$build_number" =~ ^[0-9]+(\.[0-9]+){0,2}$ ]]; then
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
if ! command -v create-dmg >/dev/null 2>&1; then
    echo "create-dmg is required. Install it with: brew install create-dmg" >&2
    exit 1
fi
if ! security find-identity -v -p codesigning | grep -Fq "$identity"; then
    echo "Missing Developer ID Application identity: $identity" >&2
    exit 1
fi

cd "$project_root"
export CAT_TYPE_BUILD_NUMBER="$build_number"
export CAT_TYPE_CODESIGN_IDENTITY="$identity"
export CAT_TYPE_REQUIRE_SIGNING=1

"$python_command" scripts/build_icon.py
"$python_command" -m PyInstaller --noconfirm --clean CatType.spec
"$python_command" -m scripts.check_bundled_icon \
    "$app_path/Contents/MacOS/Cat Type"

retry codesign --force --deep --strict --timestamp \
    --options runtime \
    --sign "$identity" \
    "$app_path"
codesign --verify --deep --strict --verbose=2 "$app_path"

signature_details="$(codesign --display --verbose=4 "$app_path" 2>&1)"
grep -Fq "Authority=Developer ID Application:" <<< "$signature_details"
grep -Fq "TeamIdentifier=9B98U2J5Q2" <<< "$signature_details"
grep -Fq "Identifier=com.fungusta.cat-type" <<< "$signature_details"
grep -Fq "Runtime Version=" <<< "$signature_details"

dmg_source="$(mktemp -d "${TMPDIR:-/tmp}/cat-type-dmg.XXXXXX")"
cleanup() {
    case "$dmg_source" in
        "${TMPDIR:-/tmp}"/cat-type-dmg.*) rm -rf -- "$dmg_source" ;;
        *) echo "Refusing to remove unexpected temporary path: $dmg_source" >&2 ;;
    esac
}
trap cleanup EXIT

ditto "$app_path" "$dmg_source/Cat Type.app"
rm -f -- "$dmg_path"
create-dmg \
    --volname "Cat Type" \
    --window-pos 200 120 \
    --window-size 600 360 \
    --background "$project_root/packaging/dmg-background-v3.png" \
    --volicon "$project_root/assets/cat-type.icns" \
    --icon-size 120 \
    --icon "Cat Type.app" 132 182 \
    --hide-extension "Cat Type.app" \
    --app-drop-link 468 182 \
    --no-internet-enable \
    "$dmg_path" \
    "$dmg_source"

retry codesign --force --timestamp --sign "$identity" "$dmg_path"
codesign --verify --strict --verbose=2 "$dmg_path"
hdiutil verify "$dmg_path"

echo "$dmg_path"
