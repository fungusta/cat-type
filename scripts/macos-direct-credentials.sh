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

install_credentials() {
  require_env RUNNER_TEMP
  require_env GITHUB_ENV
  require_env EXPECTED_APPLE_TEAM_ID
  require_env APPLE_DEVELOPER_ID_CERT_BASE64
  require_env APPLE_DEVELOPER_ID_CERT_PASSWORD

  local p12_path="$RUNNER_TEMP/Cat-Type-Developer-ID.p12"
  local certificate_path="$RUNNER_TEMP/Cat-Type-Developer-ID.pem"
  local password_path="$RUNNER_TEMP/Cat-Type-Developer-ID.password"
  local keychain_path="$RUNNER_TEMP/Cat-Type-signing.keychain-db"
  local original_keychains_path="$RUNNER_TEMP/Cat-Type-original-keychains.txt"
  local keychain_password
  keychain_password="$(openssl rand -base64 32)"

  printf '%s' "$APPLE_DEVELOPER_ID_CERT_BASE64" \
    | openssl base64 -d -A -out "$p12_path"
  [ -s "$p12_path" ] || fail "Decoded Developer ID credential is empty."
  printf '%s' "$APPLE_DEVELOPER_ID_CERT_PASSWORD" > "$password_path"
  chmod 600 "$p12_path" "$password_path"

  openssl pkcs12 \
    -in "$p12_path" \
    -passin "file:$password_path" \
    -clcerts \
    -nokeys \
    -out "$certificate_path" \
    || fail "Unable to read the Developer ID PKCS#12 file."
  chmod 600 "$certificate_path"
  openssl x509 -in "$certificate_path" -checkend 0 -noout \
    || fail "Developer ID certificate has expired."
  openssl pkcs12 \
    -in "$p12_path" \
    -passin "file:$password_path" \
    -nocerts \
    -nodes \
    2>/dev/null \
    | openssl pkey -check -noout >/dev/null \
    || fail "Developer ID PKCS#12 file does not contain a usable private key."

  security list-keychains -d user \
    | sed -E 's/^[[:space:]]*"//; s/"[[:space:]]*$//' \
    > "$original_keychains_path"
  chmod 600 "$original_keychains_path"

  security create-keychain -p "$keychain_password" "$keychain_path"
  security set-keychain-settings -lut 21600 "$keychain_path"
  security unlock-keychain -p "$keychain_password" "$keychain_path"
  security import "$p12_path" \
    -k "$keychain_path" \
    -P "$APPLE_DEVELOPER_ID_CERT_PASSWORD" \
    -A \
    -t cert \
    -f pkcs12
  security set-key-partition-list \
    -S apple-tool:,apple:,codesign: \
    -s \
    -k "$keychain_password" \
    "$keychain_path" >/dev/null

  local original_keychains=()
  while IFS= read -r keychain; do
    [ -n "$keychain" ] && original_keychains+=("$keychain")
  done < "$original_keychains_path"
  security list-keychains -d user -s "$keychain_path" "${original_keychains[@]}"

  local identity_line identity_hash
  identity_line="$(
    security find-identity -v -p codesigning "$keychain_path" \
      | grep -m1 '"Developer ID Application:' \
      || true
  )"
  identity_hash="$(printf '%s\n' "$identity_line" | awk '{print $2}')"
  if [ -z "$identity_hash" ] \
    || [[ "$identity_line" != *"($EXPECTED_APPLE_TEAM_ID)"* ]]; then
    fail "Developer ID identity is missing or belongs to another team."
  fi

  {
    echo "CAT_TYPE_CODESIGN_IDENTITY=$identity_hash"
    echo "CAT_TYPE_REQUIRE_SIGNING=1"
    echo "CAT_TYPE_SIGNING_KEYCHAIN_PATH=$keychain_path"
    echo "CAT_TYPE_SIGNING_ORIGINAL_KEYCHAINS_PATH=$original_keychains_path"
    echo "CAT_TYPE_SIGNING_P12_PATH=$p12_path"
    echo "CAT_TYPE_SIGNING_CERTIFICATE_PATH=$certificate_path"
    echo "CAT_TYPE_SIGNING_PASSWORD_PATH=$password_path"
  } >> "$GITHUB_ENV"

  echo "Installed validated Developer ID signing credentials."
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
      *) fail "Refusing to delete a signing keychain outside RUNNER_TEMP." ;;
    esac
  fi

  local path_variable path
  for path_variable in \
    CAT_TYPE_SIGNING_ORIGINAL_KEYCHAINS_PATH \
    CAT_TYPE_SIGNING_P12_PATH \
    CAT_TYPE_SIGNING_CERTIFICATE_PATH \
    CAT_TYPE_SIGNING_PASSWORD_PATH; do
    path="${!path_variable:-}"
    if [ -n "$path" ]; then
      case "$path" in
        "$RUNNER_TEMP"/*) rm -f -- "$path" ;;
        *) fail "Refusing to delete a signing artifact outside RUNNER_TEMP." ;;
      esac
    fi
  done

  echo "Removed temporary Developer ID signing credentials."
}

case "${1:-}" in
  install) install_credentials ;;
  cleanup) cleanup_credentials ;;
  *) fail "Usage: $0 install|cleanup" ;;
esac
