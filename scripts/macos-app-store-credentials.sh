#!/usr/bin/env bash

set -euo pipefail

fail() {
  echo "::error::$*" >&2
  exit 1
}

require_env() {
  local name="$1"
  [ -n "${!name:-}" ] || fail "Missing required environment variable: $name"
}

decode_secret() {
  local value="$1"
  local destination="$2"

  printf '%s' "$value" | openssl base64 -d -A -out "$destination"
  [ -s "$destination" ] || fail "Decoded credential is empty: $destination"
  chmod 600 "$destination"
}

certificate_fingerprint() {
  openssl x509 \
    -in "$1" \
    -noout \
    -fingerprint \
    -sha1 \
    | sed -E 's/^[Ss][Hh][Aa]1 Fingerprint=//; s/://g'
}

validate_certificate() {
  local certificate_path="$1"
  local expected_name="$2"
  local description="$3"
  local subject

  openssl x509 -in "$certificate_path" -checkend 0 -noout \
    || fail "$description certificate has expired."
  subject="$(openssl x509 -in "$certificate_path" -noout -subject -nameopt RFC2253)"
  grep -Fq "CN=$expected_name" <<< "$subject" \
    || fail "$description certificate has the wrong common name."
  grep -Fq "UID=$DEVELOPMENT_TEAM" <<< "$subject" \
    || fail "$description certificate is not for team $DEVELOPMENT_TEAM."
}

extract_identity() {
  local p12_path="$1"
  local password_path="$2"
  local certificate_path="$3"
  local description="$4"
  local certificate_count

  openssl pkcs12 \
    -in "$p12_path" \
    -passin "file:$password_path" \
    -clcerts \
    -nokeys \
    -out "$certificate_path" \
    || fail "Unable to read the $description PKCS#12 file."
  chmod 600 "$certificate_path"

  certificate_count="$(grep -c -- '-----BEGIN CERTIFICATE-----' "$certificate_path")"
  [ "$certificate_count" = "1" ] \
    || fail "$description PKCS#12 file must contain exactly one leaf certificate."

  openssl pkcs12 \
    -in "$p12_path" \
    -passin "file:$password_path" \
    -nocerts \
    -nodes \
    2>/dev/null \
    | openssl pkey -check -noout >/dev/null \
    || fail "$description PKCS#12 file does not contain a usable private key."
}

install_credentials() {
  require_env RUNNER_TEMP
  require_env GITHUB_ENV
  require_env DEVELOPMENT_TEAM
  require_env BUNDLE_ID
  require_env CAT_TYPE_MAC_APP_CERTIFICATE_P12_B64
  require_env CAT_TYPE_MAC_APP_CERTIFICATE_PASSWORD
  require_env CAT_TYPE_MAC_INSTALLER_CERTIFICATE_P12_B64
  require_env CAT_TYPE_MAC_INSTALLER_CERTIFICATE_PASSWORD
  require_env CAT_TYPE_MAC_APP_STORE_PROFILE_B64

  local app_p12_path="$RUNNER_TEMP/Cat-Type-Mac-App-Distribution.p12"
  local app_password_path="$RUNNER_TEMP/Cat-Type-Mac-App-Distribution.password"
  local app_certificate_path="$RUNNER_TEMP/Cat-Type-Mac-App-Distribution.pem"
  local installer_p12_path="$RUNNER_TEMP/Cat-Type-Mac-Installer-Distribution.p12"
  local installer_password_path="$RUNNER_TEMP/Cat-Type-Mac-Installer-Distribution.password"
  local installer_certificate_path="$RUNNER_TEMP/Cat-Type-Mac-Installer-Distribution.pem"
  local profile_path="$RUNNER_TEMP/Cat-Type-Mac-App-Store.provisionprofile"
  local profile_plist_path="$RUNNER_TEMP/Cat-Type-Mac-App-Store.plist"
  local profile_certificate_path="$RUNNER_TEMP/Cat-Type-profile-certificate.der"
  local keychain_path="$RUNNER_TEMP/Cat-Type-signing.keychain-db"
  local original_keychains_path="$RUNNER_TEMP/Cat-Type-original-keychains.txt"
  local keychain_password
  keychain_password="$(openssl rand -base64 32)"

  {
    echo "CAT_TYPE_SIGNING_KEYCHAIN_PATH=$keychain_path"
    echo "CAT_TYPE_SIGNING_ORIGINAL_KEYCHAINS_PATH=$original_keychains_path"
    echo "CAT_TYPE_SIGNING_APP_P12_PATH=$app_p12_path"
    echo "CAT_TYPE_SIGNING_APP_PASSWORD_PATH=$app_password_path"
    echo "CAT_TYPE_SIGNING_APP_CERTIFICATE_PATH=$app_certificate_path"
    echo "CAT_TYPE_SIGNING_INSTALLER_P12_PATH=$installer_p12_path"
    echo "CAT_TYPE_SIGNING_INSTALLER_PASSWORD_PATH=$installer_password_path"
    echo "CAT_TYPE_SIGNING_INSTALLER_CERTIFICATE_PATH=$installer_certificate_path"
    echo "CAT_TYPE_APP_STORE_PROFILE=$profile_path"
    echo "CAT_TYPE_SIGNING_PROFILE_PLIST_PATH=$profile_plist_path"
    echo "CAT_TYPE_SIGNING_PROFILE_CERTIFICATE_PATH=$profile_certificate_path"
  } >> "$GITHUB_ENV"

  decode_secret "$CAT_TYPE_MAC_APP_CERTIFICATE_P12_B64" "$app_p12_path"
  decode_secret "$CAT_TYPE_MAC_INSTALLER_CERTIFICATE_P12_B64" "$installer_p12_path"
  decode_secret "$CAT_TYPE_MAC_APP_STORE_PROFILE_B64" "$profile_path"
  printf '%s' "$CAT_TYPE_MAC_APP_CERTIFICATE_PASSWORD" > "$app_password_path"
  printf '%s' "$CAT_TYPE_MAC_INSTALLER_CERTIFICATE_PASSWORD" > "$installer_password_path"
  chmod 600 "$app_password_path" "$installer_password_path"

  extract_identity \
    "$app_p12_path" \
    "$app_password_path" \
    "$app_certificate_path" \
    "Mac App Distribution"
  extract_identity \
    "$installer_p12_path" \
    "$installer_password_path" \
    "$installer_certificate_path" \
    "Mac Installer Distribution"

  local app_identity="3rd Party Mac Developer Application: Peter Fung ($DEVELOPMENT_TEAM)"
  local installer_identity="3rd Party Mac Developer Installer: Peter Fung ($DEVELOPMENT_TEAM)"
  validate_certificate "$app_certificate_path" "$app_identity" "Mac App Distribution"
  validate_certificate "$installer_certificate_path" "$installer_identity" "Mac Installer Distribution"

  security cms -D -i "$profile_path" > "$profile_plist_path"
  plutil -extract DeveloperCertificates.0 raw -o - "$profile_plist_path" \
    | base64 -D > "$profile_certificate_path"
  chmod 600 "$profile_plist_path" "$profile_certificate_path"

  local profile_team profile_app_identifier profile_platform profile_expiration
  local profile_expiration_epoch current_epoch
  profile_team="$(/usr/libexec/PlistBuddy -c 'Print :TeamIdentifier:0' "$profile_plist_path")"
  profile_app_identifier="$(/usr/libexec/PlistBuddy -c 'Print :Entitlements:com.apple.application-identifier' "$profile_plist_path")"
  profile_platform="$(/usr/libexec/PlistBuddy -c 'Print :Platform:0' "$profile_plist_path")"
  profile_expiration="$(plutil -extract ExpirationDate raw -o - "$profile_plist_path")"
  profile_expiration_epoch="$(date -juf '%Y-%m-%dT%H:%M:%SZ' "$profile_expiration" '+%s')"
  current_epoch="$(date -u '+%s')"

  [ "$profile_team" = "$DEVELOPMENT_TEAM" ] \
    || fail "Provisioning profile team is $profile_team; expected $DEVELOPMENT_TEAM."
  [ "$profile_app_identifier" = "$DEVELOPMENT_TEAM.$BUNDLE_ID" ] \
    || fail "Provisioning profile app identifier is $profile_app_identifier; expected $DEVELOPMENT_TEAM.$BUNDLE_ID."
  [ "$profile_platform" = "OSX" ] \
    || fail "Provisioning profile platform is $profile_platform; expected OSX."
  [ "$profile_expiration_epoch" -gt "$current_epoch" ] \
    || fail "Provisioning profile expired at $profile_expiration."
  if /usr/libexec/PlistBuddy -c 'Print :ProvisionedDevices' "$profile_plist_path" >/dev/null 2>&1; then
    fail "Provisioning profile is device-limited, not a Mac App Store profile."
  fi
  if /usr/libexec/PlistBuddy -c 'Print :ProvisionsAllDevices' "$profile_plist_path" >/dev/null 2>&1; then
    fail "Provisioning profile is for Developer ID distribution, not the Mac App Store."
  fi

  local app_certificate_hash profile_certificate_hash
  app_certificate_hash="$(certificate_fingerprint "$app_certificate_path")"
  profile_certificate_hash="$(openssl x509 \
    -inform DER \
    -in "$profile_certificate_path" \
    -noout \
    -fingerprint \
    -sha1 \
    | sed -E 's/^[Ss][Hh][Aa]1 Fingerprint=//; s/://g')"
  [ "$app_certificate_hash" = "$profile_certificate_hash" ] \
    || fail "Mac App Distribution certificate does not match the provisioning profile."

  security list-keychains -d user \
    | sed -E 's/^[[:space:]]*"//; s/"[[:space:]]*$//' \
    > "$original_keychains_path"
  chmod 600 "$original_keychains_path"

  security create-keychain -p "$keychain_password" "$keychain_path"
  security set-keychain-settings -lut 21600 "$keychain_path"
  security unlock-keychain -p "$keychain_password" "$keychain_path"
  security import "$app_p12_path" \
    -k "$keychain_path" \
    -P "$CAT_TYPE_MAC_APP_CERTIFICATE_PASSWORD" \
    -A \
    -t cert \
    -f pkcs12
  security import "$installer_p12_path" \
    -k "$keychain_path" \
    -P "$CAT_TYPE_MAC_INSTALLER_CERTIFICATE_PASSWORD" \
    -A \
    -t cert \
    -f pkcs12
  security set-key-partition-list \
    -S apple-tool:,apple: \
    -s \
    -k "$keychain_password" \
    "$keychain_path" >/dev/null

  local original_keychains=()
  while IFS= read -r keychain; do
    [ -n "$keychain" ] && original_keychains+=("$keychain")
  done < "$original_keychains_path"
  security list-keychains -d user -s "$keychain_path" "${original_keychains[@]}"

  security find-identity -v -p codesigning "$keychain_path" \
    | grep -Fq "\"$app_identity\"" \
    || fail "Temporary keychain is missing the Mac App Distribution identity."
  security find-identity -v "$keychain_path" \
    | grep -Fq "\"$installer_identity\"" \
    || fail "Temporary keychain is missing the Mac Installer Distribution identity."

  {
    echo "CAT_TYPE_APP_STORE_APP_IDENTITY=$app_identity"
    echo "CAT_TYPE_APP_STORE_INSTALLER_IDENTITY=$installer_identity"
  } >> "$GITHUB_ENV"

  echo "Installed validated Mac App Store signing credentials for $BUNDLE_ID."
}

cleanup_credentials() {
  require_env RUNNER_TEMP

  if [ -n "${CAT_TYPE_SIGNING_ORIGINAL_KEYCHAINS_PATH:-}" ] \
    && [ -f "$CAT_TYPE_SIGNING_ORIGINAL_KEYCHAINS_PATH" ]; then
    local original_keychains=()
    while IFS= read -r keychain; do
      [ -n "$keychain" ] && original_keychains+=("$keychain")
    done < "$CAT_TYPE_SIGNING_ORIGINAL_KEYCHAINS_PATH"
    if [ "${#original_keychains[@]}" -gt 0 ]; then
      security list-keychains -d user -s "${original_keychains[@]}" 2>/dev/null || true
    fi
  fi

  if [ -n "${CAT_TYPE_SIGNING_KEYCHAIN_PATH:-}" ]; then
    case "$CAT_TYPE_SIGNING_KEYCHAIN_PATH" in
      "$RUNNER_TEMP"/*)
        security delete-keychain "$CAT_TYPE_SIGNING_KEYCHAIN_PATH" 2>/dev/null || true
        ;;
      *)
        fail "Refusing to delete a signing keychain outside RUNNER_TEMP."
        ;;
    esac
  fi

  local path_variable path
  for path_variable in \
    CAT_TYPE_SIGNING_ORIGINAL_KEYCHAINS_PATH \
    CAT_TYPE_SIGNING_APP_P12_PATH \
    CAT_TYPE_SIGNING_APP_PASSWORD_PATH \
    CAT_TYPE_SIGNING_APP_CERTIFICATE_PATH \
    CAT_TYPE_SIGNING_INSTALLER_P12_PATH \
    CAT_TYPE_SIGNING_INSTALLER_PASSWORD_PATH \
    CAT_TYPE_SIGNING_INSTALLER_CERTIFICATE_PATH \
    CAT_TYPE_APP_STORE_PROFILE \
    CAT_TYPE_SIGNING_PROFILE_PLIST_PATH \
    CAT_TYPE_SIGNING_PROFILE_CERTIFICATE_PATH; do
    path="${!path_variable:-}"
    if [ -n "$path" ]; then
      case "$path" in
        "$RUNNER_TEMP"/*) rm -f -- "$path" ;;
        *) fail "Refusing to delete a signing artifact outside RUNNER_TEMP." ;;
      esac
    fi
  done

  echo "Removed temporary Mac App Store signing credentials."
}

case "${1:-}" in
  install) install_credentials ;;
  cleanup) cleanup_credentials ;;
  *) fail "Usage: $0 install|cleanup" ;;
esac
