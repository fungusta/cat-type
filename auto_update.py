"""Discover stable Cat Type releases and download verified update packages."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app_version import APP_VERSION
from cat_settings import default_settings_path


GITHUB_LATEST_RELEASE_URL = (
    "https://api.github.com/repos/fungusta/cat-type/releases/latest"
)
HTTP_TIMEOUT_SECONDS = 10
MAX_METADATA_BYTES = 1024 * 1024
MAX_PACKAGE_BYTES = 256 * 1024 * 1024
CHECK_INTERVAL = timedelta(hours=24)
_VERSION_PATTERN = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
_CHECKSUM_LINE_PATTERN = re.compile(r"([0-9a-fA-F]{64})  ([^\r\n]+)")


class UpdateError(Exception):
    """An update could not be safely discovered or verified."""


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    url: str
    size: int


@dataclass(frozen=True)
class AvailableUpdate:
    version: str
    tag_name: str
    html_url: str
    package: ReleaseAsset
    checksums: ReleaseAsset


@dataclass(frozen=True)
class InstallerAvailability:
    """Whether this installation can safely replace itself."""

    can_install: bool
    status: str


@dataclass(frozen=True)
class UpdateEvent:
    """An immutable result passed from an update worker to the Tk thread."""

    operation_id: int
    kind: Literal[
        "not-due",
        "unavailable",
        "check-result",
        "error",
        "cancelled",
        "progress",
        "stage",
        "install-started",
    ]
    message: str = ""
    update: AvailableUpdate | None = None
    received: int = 0
    total: int = 0


def _require_aware(moment: datetime) -> None:
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("update timestamps must include a timezone")


def _parse_version(value: str, *, label: str) -> tuple[int, int, int]:
    if not isinstance(value, str):
        raise UpdateError(f"invalid {label}")
    matched = _VERSION_PATTERN.fullmatch(value)
    if matched is None:
        raise UpdateError(f"invalid {label}: {value!r}")
    components = matched.groups()
    if any(len(component) > 9 for component in components):
        raise UpdateError(f"invalid {label}: numeric component is too large")
    try:
        major, minor, patch = (int(component) for component in components)
    except ValueError as error:
        raise UpdateError(
            f"invalid {label}: numeric component is too large"
        ) from error
    return major, minor, patch


def _is_https_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username


def _response_length(response: object) -> int | None:
    headers = getattr(response, "headers", {})
    raw_length = headers.get("Content-Length")
    if raw_length is None:
        return None
    try:
        length = int(raw_length)
    except (TypeError, ValueError) as error:
        raise UpdateError("invalid HTTP Content-Length") from error
    if length < 0:
        raise UpdateError("invalid HTTP Content-Length")
    return length


def _read_bounded(response: object, maximum: int, *, label: str) -> bytes:
    declared = _response_length(response)
    if declared is not None and declared > maximum:
        raise UpdateError(f"{label} is too large")
    payload = bytearray()
    try:
        while len(payload) <= maximum:
            remaining = maximum + 1 - len(payload)
            chunk = response.read(min(64 * 1024, remaining))  # type: ignore[attr-defined]
            if not chunk:
                break
            payload.extend(chunk)
    except (OSError, ValueError) as error:
        raise UpdateError(f"could not read {label}") from error
    if len(payload) > maximum:
        raise UpdateError(f"{label} is too large")
    return bytes(payload)


class UpdateStateStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_settings_path().with_name("update-state.json")

    def is_due(self, now: datetime) -> bool:
        _require_aware(now)
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return True
            raw_timestamp = payload["last_successful_check"]
            if not isinstance(raw_timestamp, str):
                return True
            checked_at = datetime.fromisoformat(raw_timestamp)
            _require_aware(checked_at)
        except (OSError, ValueError, TypeError, KeyError):
            return True
        elapsed = now.astimezone(timezone.utc) - checked_at.astimezone(timezone.utc)
        return elapsed >= CHECK_INTERVAL

    def record_success(self, now: datetime) -> None:
        _require_aware(now)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=self.path.parent,
        )
        temporary = Path(temporary_name)
        payload = {
            "last_successful_check": now.astimezone(timezone.utc).isoformat()
        }
        primary_error: BaseException | None = None
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as state_file:
                state_file.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            temporary.replace(self.path)
        except BaseException as error:
            primary_error = error
            raise
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError as cleanup_error:
                if primary_error is None:
                    raise UpdateError(
                        "could not clean up update state staging file"
                    ) from cleanup_error


class UpdateService:
    def __init__(
        self,
        current_version: str = APP_VERSION,
        opener: Callable[..., object] = urlopen,
        cache_dir: Path | None = None,
    ) -> None:
        self.current_version = current_version
        self.opener = opener
        self.cache_dir = cache_dir or default_settings_path().parent / "update-cache"

    def check(self, platform: str, machine: str) -> AvailableUpdate | None:
        current = _parse_version(self.current_version, label="current version")
        package_name = self._package_name(platform, machine)
        request = Request(
            GITHUB_LATEST_RELEASE_URL,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": f"Cat-Type/{self.current_version}",
            },
        )
        try:
            with self.opener(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                self._require_https_final_url(response)
                raw_payload = _read_bounded(
                    response, MAX_METADATA_BYTES, label="release response"
                )
        except UpdateError:
            raise
        except (HTTPError, URLError, OSError, TimeoutError, ValueError) as error:
            raise UpdateError("could not check for updates") from error

        try:
            payload = json.loads(raw_payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise UpdateError("invalid release response") from error
        if not isinstance(payload, dict):
            raise UpdateError("invalid release response")
        if (
            type(payload.get("draft")) is not bool
            or type(payload.get("prerelease")) is not bool
        ):
            raise UpdateError("invalid release stability metadata")
        if payload["draft"] or payload["prerelease"]:
            raise UpdateError("latest release is not stable")
        published_at = payload.get("published_at")
        if not isinstance(published_at, str):
            raise UpdateError("release is not published")
        try:
            _require_aware(datetime.fromisoformat(published_at))
        except ValueError as error:
            raise UpdateError("release has no valid published timestamp") from error

        tag_name = payload.get("tag_name")
        if not isinstance(tag_name, str) or not tag_name.startswith("v"):
            raise UpdateError("invalid release tag")
        version = tag_name[1:]
        available = _parse_version(version, label="release version")
        html_url = payload.get("html_url")
        if not _is_https_url(html_url):
            raise UpdateError("invalid release URL")
        if available <= current:
            return None

        assets = payload.get("assets")
        if not isinstance(assets, list):
            raise UpdateError("invalid release assets")
        package = self._select_asset(
            assets, package_name, "package asset", maximum=MAX_PACKAGE_BYTES
        )
        checksums = self._select_asset(
            assets, "SHA256SUMS.txt", "checksum asset", maximum=MAX_METADATA_BYTES
        )
        return AvailableUpdate(
            version=version,
            tag_name=tag_name,
            html_url=html_url,
            package=package,
            checksums=checksums,
        )

    @staticmethod
    def _package_name(platform: str, machine: str) -> str:
        platform_key = platform.lower()
        machine_key = machine.lower()
        if platform_key == "win32" and machine_key in {"amd64", "x86_64"}:
            return "Cat-Type-Windows-x64.exe"
        if platform_key == "darwin" and machine_key == "x86_64":
            return "Cat-Type-macOS-x64.dmg"
        if platform_key == "darwin" and machine_key in {"aarch64", "arm64"}:
            return "Cat-Type-macOS-arm64.dmg"
        if platform_key == "linux" and machine_key in {"amd64", "x86_64"}:
            return "Cat-Type-Linux-x64.tar.gz"
        if platform_key == "linux" and machine_key in {"aarch64", "arm64"}:
            return "Cat-Type-Linux-arm64.tar.gz"
        raise UpdateError(f"unsupported update platform: {platform}/{machine}")

    @staticmethod
    def _select_asset(
        assets: list[object], name: str, label: str, *, maximum: int
    ) -> ReleaseAsset:
        matches = [
            asset
            for asset in assets
            if isinstance(asset, dict) and asset.get("name") == name
        ]
        if len(matches) != 1:
            raise UpdateError(f"missing or duplicate {label}: {name}")
        asset = matches[0]
        url = asset.get("browser_download_url")
        size = asset.get("size")
        if (
            not _is_https_url(url)
            or type(size) is not int
            or size <= 0
            or size > maximum
        ):
            raise UpdateError(f"invalid {label}: {name}")
        return ReleaseAsset(name=name, url=url, size=size)

    def download_verified(
        self,
        update: AvailableUpdate,
        progress: Callable[[int, int], None] | None = None,
    ) -> Path:
        self._validate_download_asset(
            update.checksums, maximum=MAX_METADATA_BYTES, label="checksum"
        )
        self._validate_download_asset(
            update.package, maximum=MAX_PACKAGE_BYTES, label="package"
        )
        if Path(update.package.name).name != update.package.name:
            raise UpdateError("invalid package filename")

        checksum_payload = self._download_checksum(update.checksums)
        expected_digest = self._expected_checksum(
            checksum_payload, update.package.name
        )

        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise UpdateError("could not create update cache") from error
        destination = self.cache_dir / update.package.name
        try:
            descriptor, partial_name = tempfile.mkstemp(
                prefix=f".{update.package.name}.",
                suffix=".part",
                dir=self.cache_dir,
            )
        except OSError as error:
            raise UpdateError("could not create package staging file") from error
        partial = Path(partial_name)
        digest = hashlib.sha256()
        received = 0
        primary_error: BaseException | None = None
        try:
            request = self._download_request(update.package.url)
            with os.fdopen(descriptor, "wb") as package_file:
                with self.opener(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                    self._require_https_final_url(response)
                    declared = _response_length(response)
                    if declared is not None and declared != update.package.size:
                        raise UpdateError(
                            "package size does not match release metadata"
                        )
                    if progress is not None:
                        progress(0, update.package.size)
                    while True:
                        chunk = response.read(64 * 1024)
                        if not chunk:
                            break
                        received += len(chunk)
                        if received > update.package.size:
                            raise UpdateError(
                                "package size exceeds release metadata"
                            )
                        package_file.write(chunk)
                        digest.update(chunk)
                        if progress is not None:
                            progress(received, update.package.size)
            if received != update.package.size:
                raise UpdateError("package size does not match release metadata")
            if digest.hexdigest() != expected_digest:
                raise UpdateError("package checksum does not match SHA256SUMS.txt")
            partial.replace(destination)
            return destination
        except UpdateError as error:
            primary_error = error
            raise
        except (HTTPError, URLError, OSError, TimeoutError, ValueError) as error:
            primary_error = UpdateError("could not download package")
            raise primary_error from error
        except BaseException as error:
            primary_error = error
            raise
        finally:
            try:
                partial.unlink(missing_ok=True)
            except OSError as cleanup_error:
                if primary_error is None:
                    raise UpdateError(
                        "could not clean up package staging file"
                    ) from cleanup_error

    @staticmethod
    def _validate_download_asset(
        asset: ReleaseAsset, *, maximum: int, label: str
    ) -> None:
        if (
            not isinstance(asset.name, str)
            or not asset.name
            or not _is_https_url(asset.url)
            or type(asset.size) is not int
            or asset.size <= 0
            or asset.size > maximum
        ):
            raise UpdateError(f"invalid {label} asset")

    def _download_checksum(self, asset: ReleaseAsset) -> bytes:
        request = self._download_request(asset.url)
        try:
            with self.opener(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                self._require_https_final_url(response)
                payload = _read_bounded(
                    response,
                    min(asset.size, MAX_METADATA_BYTES),
                    label="checksum response",
                )
        except UpdateError:
            raise
        except (HTTPError, URLError, OSError, TimeoutError, ValueError) as error:
            raise UpdateError("could not download checksum file") from error
        if len(payload) != asset.size:
            raise UpdateError("checksum response size does not match release metadata")
        return payload

    def _download_request(self, url: str) -> Request:
        return Request(
            url,
            headers={
                "Accept": "application/octet-stream",
                "User-Agent": f"Cat-Type/{self.current_version}",
            },
        )

    @staticmethod
    def _require_https_final_url(response: object) -> None:
        geturl = getattr(response, "geturl", None)
        final_url = geturl() if callable(geturl) else getattr(response, "url", None)
        if not _is_https_url(final_url):
            raise UpdateError("download redirect did not remain on HTTPS")

    @staticmethod
    def _expected_checksum(payload: bytes, package_name: str) -> str:
        try:
            text = payload.decode("ascii")
        except UnicodeDecodeError as error:
            raise UpdateError("checksum file is not ASCII") from error
        lines = text.splitlines()
        parsed: list[tuple[str, str]] = []
        for line in lines:
            matched = _CHECKSUM_LINE_PATTERN.fullmatch(line)
            if matched is None:
                raise UpdateError("malformed checksum entry")
            parsed.append((matched.group(1).lower(), matched.group(2)))
        matches = [digest for digest, name in parsed if name == package_name]
        if len(matches) != 1:
            raise UpdateError("missing or duplicate checksum entry")
        return matches[0]
