from __future__ import annotations

import hashlib
import io
import json
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.request import Request

from auto_update import (
    AvailableUpdate,
    ReleaseAsset,
    UpdateError,
    UpdateService,
    UpdateStateStore,
)
from cat_settings import default_settings_path


class FakeResponse:
    def __init__(
        self,
        body: bytes,
        *,
        content_length: int | None = None,
        url: str = "https://api.github.com/final",
    ) -> None:
        self._stream = io.BytesIO(body)
        self.headers = (
            {} if content_length is None else {"Content-Length": str(content_length)}
        )
        self.url = url

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


class ChunkedResponse(FakeResponse):
    def __init__(
        self,
        body: bytes,
        *,
        chunk_size: int,
        content_length: int | None = None,
        fail_after_reads: int | None = None,
        url: str = "https://objects.githubusercontent.com/final",
    ) -> None:
        super().__init__(body, content_length=content_length, url=url)
        self.chunk_size = chunk_size
        self.fail_after_reads = fail_after_reads
        self.read_count = 0

    def read(self, size: int = -1) -> bytes:
        if self.fail_after_reads is not None and self.read_count >= self.fail_after_reads:
            raise OSError("connection interrupted")
        self.read_count += 1
        bounded_size = self.chunk_size if size < 0 else min(size, self.chunk_size)
        return self._stream.read(bounded_size)


class FakeOpener:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[Request, float]] = []

    def __call__(self, request: Request, *, timeout: float) -> FakeResponse:
        self.calls.append((request, timeout))
        if not self.responses:
            raise AssertionError("unexpected HTTP request")
        return self.responses.pop(0)


def release_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "url": "https://api.github.com/repos/fungusta/cat-type/releases/110",
        "html_url": "https://github.com/fungusta/cat-type/releases/tag/v1.1.0",
        "tag_name": "v1.1.0",
        "name": "Cat Type 1.1.0",
        "draft": False,
        "prerelease": False,
        "published_at": "2026-08-12T00:00:00Z",
        "assets": [
            {
                "name": "Cat-Type-Windows-x64.exe",
                "browser_download_url": "https://github.com/fungusta/cat-type/releases/download/v1.1.0/Cat-Type-Windows-x64.exe",
                "size": 14,
            },
            {
                "name": "Cat-Type-macOS-x64.dmg",
                "browser_download_url": "https://github.com/fungusta/cat-type/releases/download/v1.1.0/Cat-Type-macOS-x64.dmg",
                "size": 17,
            },
            {
                "name": "Cat-Type-macOS-arm64.dmg",
                "browser_download_url": "https://github.com/fungusta/cat-type/releases/download/v1.1.0/Cat-Type-macOS-arm64.dmg",
                "size": 18,
            },
            {
                "name": "Cat-Type-Linux-x64.tar.gz",
                "browser_download_url": "https://github.com/fungusta/cat-type/releases/download/v1.1.0/Cat-Type-Linux-x64.tar.gz",
                "size": 15,
            },
            {
                "name": "Cat-Type-Linux-arm64.tar.gz",
                "browser_download_url": "https://github.com/fungusta/cat-type/releases/download/v1.1.0/Cat-Type-Linux-arm64.tar.gz",
                "size": 16,
            },
            {
                "name": "SHA256SUMS.txt",
                "browser_download_url": "https://github.com/fungusta/cat-type/releases/download/v1.1.0/SHA256SUMS.txt",
                "size": 256,
            },
        ],
    }
    payload.update(overrides)
    return payload


def service_from_payload(
    payload: object, *, current_version: str = "1.0.5"
) -> tuple[UpdateService, FakeOpener]:
    body = json.dumps(payload).encode("utf-8")
    opener = FakeOpener([FakeResponse(body, content_length=len(body))])
    return UpdateService(current_version=current_version, opener=opener), opener


class ReleaseDiscoveryTests(unittest.TestCase):
    def test_selects_windows_x64_assets_and_sends_bounded_github_request(self) -> None:
        service, opener = service_from_payload(release_payload())

        update = service.check("win32", "AMD64")

        self.assertEqual(
            update,
            AvailableUpdate(
                version="1.1.0",
                tag_name="v1.1.0",
                html_url="https://github.com/fungusta/cat-type/releases/tag/v1.1.0",
                package=ReleaseAsset(
                    name="Cat-Type-Windows-x64.exe",
                    url="https://github.com/fungusta/cat-type/releases/download/v1.1.0/Cat-Type-Windows-x64.exe",
                    size=14,
                ),
                checksums=ReleaseAsset(
                    name="SHA256SUMS.txt",
                    url="https://github.com/fungusta/cat-type/releases/download/v1.1.0/SHA256SUMS.txt",
                    size=256,
                ),
            ),
        )
        request, timeout = opener.calls[0]
        headers = {key.lower(): value for key, value in request.header_items()}
        self.assertEqual(
            request.full_url,
            "https://api.github.com/repos/fungusta/cat-type/releases/latest",
        )
        self.assertEqual(headers["accept"], "application/vnd.github+json")
        self.assertEqual(headers["x-github-api-version"], "2022-11-28")
        self.assertEqual(headers["user-agent"], "Cat-Type/1.0.5")
        self.assertEqual(timeout, 10)

    def test_selects_linux_x64_release_assets(self) -> None:
        service, _ = service_from_payload(release_payload())

        update = service.check("linux", "x86_64")

        self.assertIsNotNone(update)
        assert update is not None
        self.assertEqual(update.package.name, "Cat-Type-Linux-x64.tar.gz")
        self.assertEqual(update.checksums.name, "SHA256SUMS.txt")

    def test_selects_macos_release_asset_for_each_architecture(self) -> None:
        for machine, expected in (
            ("x86_64", "Cat-Type-macOS-x64.dmg"),
            ("arm64", "Cat-Type-macOS-arm64.dmg"),
            ("aarch64", "Cat-Type-macOS-arm64.dmg"),
        ):
            with self.subTest(machine=machine):
                service, _ = service_from_payload(release_payload())

                update = service.check("darwin", machine)

                self.assertIsNotNone(update)
                assert update is not None
                self.assertEqual(update.package.name, expected)
                self.assertEqual(update.checksums.name, "SHA256SUMS.txt")

    def test_selects_linux_arm64_release_assets(self) -> None:
        service, _ = service_from_payload(release_payload())

        update = service.check("linux", "aarch64")

        self.assertIsNotNone(update)
        assert update is not None
        self.assertEqual(update.package.name, "Cat-Type-Linux-arm64.tar.gz")
        self.assertEqual(update.checksums.name, "SHA256SUMS.txt")

    def test_returns_none_when_stable_release_is_not_newer(self) -> None:
        for tag in ("v1.0.5", "v1.0.4", "v0.99.99"):
            with self.subTest(tag=tag):
                service, _ = service_from_payload(release_payload(tag_name=tag))
                self.assertIsNone(service.check("linux", "x86_64"))

    def test_rejects_non_three_part_numeric_versions(self) -> None:
        malformed_tags = (
            "1.1.0",
            "V1.1.0",
            "v1.1",
            "v1.1.0.0",
            "v01.1.0",
            "v1.1.0-rc1",
            "v1.a.0",
        )
        for tag in malformed_tags:
            with self.subTest(tag=tag):
                service, _ = service_from_payload(release_payload(tag_name=tag))
                with self.assertRaisesRegex(UpdateError, "version|tag"):
                    service.check("linux", "x86_64")

    def test_rejects_malformed_running_version(self) -> None:
        for version in ("v1.0.5", "1.0", "1.0.5.0", "01.0.5"):
            with self.subTest(version=version):
                service, _ = service_from_payload(
                    release_payload(), current_version=version
                )
                with self.assertRaisesRegex(UpdateError, "current version"):
                    service.check("linux", "x86_64")

    def test_rejects_draft_and_prerelease_releases(self) -> None:
        for field in ("draft", "prerelease"):
            with self.subTest(field=field):
                service, _ = service_from_payload(release_payload(**{field: True}))
                with self.assertRaisesRegex(UpdateError, "stable"):
                    service.check("linux", "x86_64")

    def test_rejects_unsupported_platforms_and_architectures(self) -> None:
        for platform, machine in (
            ("darwin", "i686"),
            ("win32", "arm64"),
            ("win32", "x86"),
            ("linux", "i686"),
        ):
            with self.subTest(platform=platform, machine=machine):
                service, _ = service_from_payload(release_payload())
                with self.assertRaisesRegex(UpdateError, "unsupported"):
                    service.check(platform, machine)

    def test_rejects_missing_or_duplicate_package_assets(self) -> None:
        assets = release_payload()["assets"]
        assert isinstance(assets, list)
        linux_package = next(
            asset
            for asset in assets
            if asset["name"] == "Cat-Type-Linux-x64.tar.gz"
        )
        for changed_assets in (
            [asset for asset in assets if asset is not linux_package],
            [*assets, dict(linux_package)],
        ):
            with self.subTest(asset_count=len(changed_assets)):
                service, _ = service_from_payload(
                    release_payload(assets=changed_assets)
                )
                with self.assertRaisesRegex(UpdateError, "package asset"):
                    service.check("linux", "x86_64")

    def test_rejects_missing_or_duplicate_checksum_assets(self) -> None:
        assets = release_payload()["assets"]
        assert isinstance(assets, list)
        checksum = assets[-1]
        for changed_assets in (
            [asset for asset in assets if asset is not checksum],
            [*assets, dict(checksum)],
        ):
            with self.subTest(asset_count=len(changed_assets)):
                service, _ = service_from_payload(
                    release_payload(assets=changed_assets)
                )
                with self.assertRaisesRegex(UpdateError, "checksum asset"):
                    service.check("linux", "x86_64")

    def test_rejects_non_https_or_malformed_selected_assets(self) -> None:
        assets = release_payload()["assets"]
        assert isinstance(assets, list)
        linux_package = next(
            asset
            for asset in assets
            if asset["name"] == "Cat-Type-Linux-x64.tar.gz"
        )
        assert isinstance(linux_package, dict)
        invalid_assets = (
            {**linux_package, "browser_download_url": "http://example.test/file"},
            {**linux_package, "size": 0},
            {**linux_package, "size": -1},
            {**linux_package, "size": 256 * 1024 * 1024 + 1},
            {**linux_package, "size": "15"},
        )
        for invalid in invalid_assets:
            with self.subTest(invalid=invalid):
                changed_assets = [
                    invalid if asset is linux_package else asset for asset in assets
                ]
                service, _ = service_from_payload(
                    release_payload(assets=changed_assets)
                )
                with self.assertRaisesRegex(UpdateError, "package asset"):
                    service.check("linux", "x86_64")

    def test_rejects_oversized_release_response(self) -> None:
        opener = FakeOpener(
            [FakeResponse(b" " * (1024 * 1024 + 1), content_length=1024 * 1024 + 1)]
        )
        service = UpdateService(current_version="1.0.5", opener=opener)

        with self.assertRaisesRegex(UpdateError, "release response.*large"):
            service.check("linux", "x86_64")

    def test_rejects_non_https_release_response_redirect_target(self) -> None:
        payload = json.dumps(release_payload()).encode("utf-8")
        opener = FakeOpener(
            [
                FakeResponse(
                    payload,
                    content_length=len(payload),
                    url="http://untrusted.example/release",
                )
            ]
        )

        with self.assertRaisesRegex(UpdateError, "HTTPS"):
            UpdateService(current_version="1.0.5", opener=opener).check(
                "linux", "x86_64"
            )

    def test_extreme_numeric_versions_are_controlled_update_errors(self) -> None:
        huge_component = "9" * 5000
        service, _ = service_from_payload(
            release_payload(tag_name=f"v{huge_component}.1.0")
        )
        with self.assertRaisesRegex(UpdateError, "release version"):
            service.check("linux", "x86_64")

        service, opener = service_from_payload(
            release_payload(), current_version=f"{huge_component}.1.0"
        )
        with self.assertRaisesRegex(UpdateError, "current version"):
            service.check("linux", "x86_64")
        self.assertEqual(opener.calls, [])

    def test_rejects_malformed_release_payloads(self) -> None:
        malformed_payloads = (
            [],
            {**release_payload(), "draft": "false"},
            {**release_payload(), "prerelease": None},
            {**release_payload(), "html_url": "http://example.test/release"},
            {**release_payload(), "assets": "not-a-list"},
        )
        for payload in malformed_payloads:
            with self.subTest(payload=payload):
                service, _ = service_from_payload(payload)
                with self.assertRaises(UpdateError):
                    service.check("linux", "x86_64")

    def test_rejects_unpublished_release(self) -> None:
        for published_at in (None, "", "not-a-timestamp", "2026-08-12T00:00:00"):
            with self.subTest(published_at=published_at):
                service, _ = service_from_payload(
                    release_payload(published_at=published_at)
                )
                with self.assertRaisesRegex(UpdateError, "published"):
                    service.check("linux", "x86_64")

    def test_release_values_are_immutable(self) -> None:
        asset = ReleaseAsset("package", "https://example.test/package", 1)
        update = AvailableUpdate(
            "1.1.0", "v1.1.0", "https://example.test/release", asset, asset
        )

        with self.assertRaises((AttributeError, TypeError)):
            asset.name = "changed"  # type: ignore[misc]
        with self.assertRaises((AttributeError, TypeError)):
            update.version = "9.9.9"  # type: ignore[misc]


class UpdateStateStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.path = Path(temporary_directory.name) / "update-state.json"
        self.store = UpdateStateStore(self.path)

    def test_check_is_due_only_after_twenty_four_hours(self) -> None:
        checked_at = datetime(2026, 8, 12, tzinfo=timezone.utc)
        self.store.record_success(checked_at)

        self.assertFalse(
            self.store.is_due(checked_at + timedelta(hours=23, minutes=59))
        )
        self.assertTrue(self.store.is_due(checked_at + timedelta(hours=24)))

    def test_missing_or_corrupt_state_is_due(self) -> None:
        self.assertTrue(
            self.store.is_due(datetime(2026, 8, 12, tzinfo=timezone.utc))
        )
        for corrupt in (
            "{bad json",
            "[]",
            '{}',
            '{"last_successful_check": "not-a-time"}',
            '{"last_successful_check": "2026-08-12T00:00:00"}',
        ):
            with self.subTest(corrupt=corrupt):
                self.path.write_text(corrupt, encoding="utf-8")
                self.assertTrue(
                    self.store.is_due(datetime(2026, 8, 12, tzinfo=timezone.utc))
                )

    def test_record_success_normalizes_timestamp_to_utc(self) -> None:
        singapore = timezone(timedelta(hours=8))

        self.store.record_success(datetime(2026, 8, 12, tzinfo=singapore))

        self.assertEqual(
            json.loads(self.path.read_text(encoding="utf-8")),
            {"last_successful_check": "2026-08-11T16:00:00+00:00"},
        )
        self.assertFalse(
            self.store.is_due(datetime(2026, 8, 12, tzinfo=timezone.utc))
        )

    def test_state_write_atomically_replaces_existing_file(self) -> None:
        original = '{"last_successful_check": "2026-08-01T00:00:00+00:00"}\n'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(original, encoding="utf-8")
        real_replace = Path.replace

        with patch.object(
            Path,
            "replace",
            autospec=True,
            side_effect=lambda source, target: real_replace(source, target),
        ) as replace:
            self.store.record_success(datetime(2026, 8, 12, tzinfo=timezone.utc))

        replace.assert_called_once()
        temporary, destination = replace.call_args.args
        self.assertEqual(destination, self.path)
        self.assertEqual(temporary.parent, self.path.parent)
        self.assertNotEqual(temporary, self.path)
        self.assertFalse(temporary.exists())
        self.assertNotEqual(self.path.read_text(encoding="utf-8"), original)

    def test_interleaved_state_writes_use_independent_sibling_staging_paths(
        self,
    ) -> None:
        first_ready = threading.Event()
        release_first = threading.Event()
        staged_paths: list[Path] = []
        errors: list[BaseException] = []
        real_replace = Path.replace

        def interleaved_replace(source: Path, destination: Path) -> Path:
            staged_paths.append(source)
            if len(staged_paths) == 1:
                first_ready.set()
                if not release_first.wait(timeout=2):
                    raise AssertionError("second state write did not run")
            return real_replace(source, destination)

        def write_first() -> None:
            try:
                self.store.record_success(
                    datetime(2026, 8, 12, tzinfo=timezone.utc)
                )
            except BaseException as error:
                errors.append(error)

        with patch.object(
            Path, "replace", autospec=True, side_effect=interleaved_replace
        ):
            first_thread = threading.Thread(target=write_first)
            first_thread.start()
            self.assertTrue(first_ready.wait(timeout=2))
            try:
                self.store.record_success(
                    datetime(2026, 8, 13, tzinfo=timezone.utc)
                )
            finally:
                release_first.set()
                first_thread.join(timeout=2)

        self.assertFalse(first_thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(staged_paths), 2)
        self.assertNotEqual(staged_paths[0], staged_paths[1])
        self.assertTrue(all(path.parent == self.path.parent for path in staged_paths))

    def test_state_cleanup_failure_does_not_mask_replace_failure(self) -> None:
        with patch.object(Path, "replace", side_effect=OSError("replace failed")):
            with patch.object(Path, "unlink", side_effect=OSError("cleanup failed")):
                with self.assertRaisesRegex(OSError, "replace failed"):
                    self.store.record_success(
                        datetime(2026, 8, 12, tzinfo=timezone.utc)
                    )

    def test_state_cleanup_only_failure_is_a_controlled_update_error(self) -> None:
        real_replace = Path.replace

        with patch.object(
            Path,
            "replace",
            autospec=True,
            side_effect=lambda source, target: real_replace(source, target),
        ):
            with patch.object(
                Path, "unlink", side_effect=OSError("cleanup failed")
            ):
                with self.assertRaisesRegex(UpdateError, "clean up.*state"):
                    self.store.record_success(
                        datetime(2026, 8, 12, tzinfo=timezone.utc)
                    )

    def test_failed_atomic_replace_preserves_existing_state(self) -> None:
        original = '{"last_successful_check": "2026-08-01T00:00:00+00:00"}\n'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(original, encoding="utf-8")

        with patch.object(Path, "replace", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                self.store.record_success(
                    datetime(2026, 8, 12, tzinfo=timezone.utc)
                )

        self.assertEqual(self.path.read_text(encoding="utf-8"), original)

    def test_rejects_naive_datetimes(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone"):
            self.store.is_due(datetime(2026, 8, 12))
        with self.assertRaisesRegex(ValueError, "timezone"):
            self.store.record_success(datetime(2026, 8, 12))

    def test_default_state_is_beside_settings_file(self) -> None:
        self.assertEqual(
            UpdateStateStore().path,
            default_settings_path().with_name("update-state.json"),
        )


def available_update(
    package_body: bytes,
    checksum_body: bytes,
    *,
    package_size: int | None = None,
    checksum_size: int | None = None,
) -> AvailableUpdate:
    return AvailableUpdate(
        version="1.1.0",
        tag_name="v1.1.0",
        html_url="https://github.com/fungusta/cat-type/releases/tag/v1.1.0",
        package=ReleaseAsset(
            "Cat-Type-Linux-x64.tar.gz",
            "https://github.com/fungusta/cat-type/releases/download/v1.1.0/Cat-Type-Linux-x64.tar.gz",
            len(package_body) if package_size is None else package_size,
        ),
        checksums=ReleaseAsset(
            "SHA256SUMS.txt",
            "https://github.com/fungusta/cat-type/releases/download/v1.1.0/SHA256SUMS.txt",
            len(checksum_body) if checksum_size is None else checksum_size,
        ),
    )


def checksum_for(package_name: str, body: bytes) -> bytes:
    return f"{hashlib.sha256(body).hexdigest()}  {package_name}\n".encode("ascii")


class VerifiedDownloadTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.cache = Path(temporary_directory.name) / "cache"
        self.package_body = b"verified package bytes"
        self.package_name = "Cat-Type-Linux-x64.tar.gz"
        self.checksum_body = checksum_for(self.package_name, self.package_body)

    def service(
        self, responses: list[FakeResponse]
    ) -> tuple[UpdateService, FakeOpener]:
        opener = FakeOpener(responses)
        return (
            UpdateService(
                current_version="1.0.5", opener=opener, cache_dir=self.cache
            ),
            opener,
        )

    def test_downloads_checksum_first_and_atomically_places_verified_package(self) -> None:
        service, opener = self.service(
            [
                FakeResponse(
                    self.checksum_body,
                    content_length=len(self.checksum_body),
                    url="https://objects.githubusercontent.com/checksums",
                ),
                ChunkedResponse(
                    self.package_body,
                    chunk_size=5,
                    content_length=len(self.package_body),
                    url="https://objects.githubusercontent.com/package",
                ),
            ]
        )
        update = available_update(self.package_body, self.checksum_body)
        real_replace = Path.replace

        with patch.object(
            Path,
            "replace",
            autospec=True,
            side_effect=lambda source, target: real_replace(source, target),
        ) as replace:
            downloaded = service.download_verified(update)

        self.assertEqual(downloaded, self.cache / self.package_name)
        self.assertEqual(downloaded.read_bytes(), self.package_body)
        self.assertEqual(
            [call[0].full_url for call in opener.calls],
            [update.checksums.url, update.package.url],
        )
        self.assertEqual([call[1] for call in opener.calls], [10, 10])
        for request, _ in opener.calls:
            headers = {key.lower(): value for key, value in request.header_items()}
            self.assertEqual(headers["user-agent"], "Cat-Type/1.0.5")
        replace.assert_called_once()
        temporary, destination = replace.call_args.args
        self.assertEqual(destination, self.cache / self.package_name)
        self.assertEqual(temporary.parent, self.cache)
        self.assertNotEqual(temporary, destination)
        self.assertEqual(list(self.cache.iterdir()), [downloaded])

    def test_interleaved_downloads_use_independent_sibling_staging_paths(
        self,
    ) -> None:
        first_service, _ = self.service(
            [
                FakeResponse(
                    self.checksum_body, content_length=len(self.checksum_body)
                ),
                FakeResponse(self.package_body, content_length=len(self.package_body)),
            ]
        )
        second_service, _ = self.service(
            [
                FakeResponse(
                    self.checksum_body, content_length=len(self.checksum_body)
                ),
                FakeResponse(self.package_body, content_length=len(self.package_body)),
            ]
        )
        update = available_update(self.package_body, self.checksum_body)
        first_ready = threading.Event()
        release_first = threading.Event()
        staged_paths: list[Path] = []
        errors: list[BaseException] = []
        real_replace = Path.replace

        def interleaved_replace(source: Path, destination: Path) -> Path:
            staged_paths.append(source)
            if len(staged_paths) == 1:
                first_ready.set()
                if not release_first.wait(timeout=2):
                    raise AssertionError("second download did not run")
            return real_replace(source, destination)

        def download_first() -> None:
            try:
                first_service.download_verified(update)
            except BaseException as error:
                errors.append(error)

        with patch.object(
            Path, "replace", autospec=True, side_effect=interleaved_replace
        ):
            first_thread = threading.Thread(target=download_first)
            first_thread.start()
            self.assertTrue(first_ready.wait(timeout=2))
            try:
                second_service.download_verified(update)
            finally:
                release_first.set()
                first_thread.join(timeout=2)

        self.assertFalse(first_thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(staged_paths), 2)
        self.assertNotEqual(staged_paths[0], staged_paths[1])
        self.assertTrue(all(path.parent == self.cache for path in staged_paths))
        self.assertEqual(
            (self.cache / self.package_name).read_bytes(), self.package_body
        )

    def test_reports_monotonic_streamed_progress_with_declared_total(self) -> None:
        service, _ = self.service(
            [
                FakeResponse(self.checksum_body, content_length=len(self.checksum_body)),
                ChunkedResponse(
                    self.package_body,
                    chunk_size=4,
                    content_length=len(self.package_body),
                ),
            ]
        )
        values: list[tuple[int, int]] = []

        service.download_verified(
            available_update(self.package_body, self.checksum_body),
            lambda received, total: values.append((received, total)),
        )

        self.assertEqual(values[0], (0, len(self.package_body)))
        self.assertEqual(values[-1], (len(self.package_body), len(self.package_body)))
        self.assertEqual(values, sorted(values))
        self.assertTrue(all(total == len(self.package_body) for _, total in values))

    def test_rejects_declared_oversized_checksum_before_reading(self) -> None:
        response = FakeResponse(b"ignored", content_length=1024 * 1024 + 1)
        service, opener = self.service([response])
        update = available_update(
            self.package_body,
            self.checksum_body,
            checksum_size=1024 * 1024,
        )

        with self.assertRaisesRegex(UpdateError, "checksum.*large"):
            service.download_verified(update)

        self.assertEqual(len(opener.calls), 1)
        self.assertFalse(self.cache.exists())

    def test_rejects_actual_oversized_checksum_without_content_length(self) -> None:
        oversized = b"x" * (1024 * 1024 + 1)
        service, opener = self.service(
            [ChunkedResponse(oversized, chunk_size=64 * 1024)]
        )
        update = available_update(
            self.package_body, self.checksum_body, checksum_size=1024 * 1024
        )

        with self.assertRaisesRegex(UpdateError, "checksum.*large"):
            service.download_verified(update)

        self.assertEqual(len(opener.calls), 1)
        self.assertFalse(self.cache.exists())

    def test_cache_creation_failure_is_an_update_error(self) -> None:
        service, opener = self.service(
            [FakeResponse(self.checksum_body, content_length=len(self.checksum_body))]
        )

        with patch.object(Path, "mkdir", side_effect=OSError("read-only")):
            with self.assertRaisesRegex(UpdateError, "cache"):
                service.download_verified(
                    available_update(self.package_body, self.checksum_body)
                )

        self.assertEqual(len(opener.calls), 1)

    def test_rejects_package_content_length_larger_than_release_size(self) -> None:
        service, _ = self.service(
            [
                FakeResponse(self.checksum_body, content_length=len(self.checksum_body)),
                FakeResponse(
                    self.package_body + b"x",
                    content_length=len(self.package_body) + 1,
                ),
            ]
        )

        with self.assertRaisesRegex(UpdateError, "package size"):
            service.download_verified(
                available_update(self.package_body, self.checksum_body)
            )

        self.assertEqual(list(self.cache.iterdir()), [])

    def test_rejects_actual_package_larger_than_release_size(self) -> None:
        service, _ = self.service(
            [
                FakeResponse(self.checksum_body, content_length=len(self.checksum_body)),
                FakeResponse(self.package_body + b"x"),
            ]
        )

        with self.assertRaisesRegex(UpdateError, "package size"):
            service.download_verified(
                available_update(self.package_body, self.checksum_body)
            )

        self.assertEqual(list(self.cache.iterdir()), [])

    def test_rejects_package_shorter_than_release_size(self) -> None:
        service, _ = self.service(
            [
                FakeResponse(self.checksum_body, content_length=len(self.checksum_body)),
                FakeResponse(
                    self.package_body[:-1], content_length=len(self.package_body) - 1
                ),
            ]
        )

        with self.assertRaisesRegex(UpdateError, "package size"):
            service.download_verified(
                available_update(self.package_body, self.checksum_body)
            )

        self.assertEqual(list(self.cache.iterdir()), [])

    def test_interrupted_package_download_removes_partial_file(self) -> None:
        service, _ = self.service(
            [
                FakeResponse(self.checksum_body, content_length=len(self.checksum_body)),
                ChunkedResponse(
                    self.package_body,
                    chunk_size=4,
                    content_length=len(self.package_body),
                    fail_after_reads=2,
                ),
            ]
        )

        with self.assertRaisesRegex(UpdateError, "download package"):
            service.download_verified(
                available_update(self.package_body, self.checksum_body)
            )

        self.assertEqual(list(self.cache.iterdir()), [])

    def test_checksum_mismatch_removes_partial_package(self) -> None:
        bad_checksum = checksum_for(self.package_name, b"different bytes")
        service, _ = self.service(
            [
                FakeResponse(bad_checksum, content_length=len(bad_checksum)),
                FakeResponse(self.package_body, content_length=len(self.package_body)),
            ]
        )

        with self.assertRaisesRegex(UpdateError, "checksum"):
            service.download_verified(
                available_update(self.package_body, bad_checksum)
            )

        self.assertEqual(list(self.cache.iterdir()), [])

    def test_cleanup_failure_does_not_mask_checksum_mismatch(self) -> None:
        bad_checksum = checksum_for(self.package_name, b"different bytes")
        service, _ = self.service(
            [
                FakeResponse(bad_checksum, content_length=len(bad_checksum)),
                FakeResponse(self.package_body, content_length=len(self.package_body)),
            ]
        )

        with patch.object(Path, "unlink", side_effect=OSError("cleanup failed")):
            with self.assertRaisesRegex(UpdateError, "checksum does not match"):
                service.download_verified(
                    available_update(self.package_body, bad_checksum)
                )

    def test_cleanup_only_failure_is_a_controlled_update_error(self) -> None:
        service, _ = self.service(
            [
                FakeResponse(self.checksum_body, content_length=len(self.checksum_body)),
                FakeResponse(self.package_body, content_length=len(self.package_body)),
            ]
        )
        update = available_update(self.package_body, self.checksum_body)
        real_replace = Path.replace

        with patch.object(
            Path,
            "replace",
            autospec=True,
            side_effect=lambda source, target: real_replace(source, target),
        ):
            with patch.object(
                Path, "unlink", side_effect=OSError("cleanup failed")
            ):
                with self.assertRaisesRegex(UpdateError, "clean up"):
                    service.download_verified(update)

    def test_matches_only_the_exact_checksum_filename(self) -> None:
        correct = hashlib.sha256(self.package_body).hexdigest()
        wrong = hashlib.sha256(b"wrong").hexdigest()
        checksum_body = (
            f"{wrong}  prefix-{self.package_name}\n"
            f"{wrong}  {self.package_name}.bak\n"
            f"{correct}  {self.package_name}\n"
        ).encode("ascii")
        service, _ = self.service(
            [
                FakeResponse(checksum_body, content_length=len(checksum_body)),
                FakeResponse(self.package_body, content_length=len(self.package_body)),
            ]
        )

        downloaded = service.download_verified(
            available_update(self.package_body, checksum_body)
        )

        self.assertEqual(downloaded.read_bytes(), self.package_body)

    def test_rejects_missing_duplicate_or_malformed_checksum_entries(self) -> None:
        digest = hashlib.sha256(self.package_body).hexdigest()
        invalid_bodies = (
            f"{digest}  different-file.tar.gz\n".encode("ascii"),
            f"{digest}  {self.package_name}\n{digest}  {self.package_name}\n".encode(
                "ascii"
            ),
            f"{digest} {self.package_name}\n".encode("ascii"),
            f"{'g' * 64}  {self.package_name}\n".encode("ascii"),
            f"{digest} *{self.package_name}\n".encode("ascii"),
        )
        for checksum_body in invalid_bodies:
            with self.subTest(checksum_body=checksum_body):
                service, opener = self.service(
                    [FakeResponse(checksum_body, content_length=len(checksum_body))]
                )
                with self.assertRaisesRegex(UpdateError, "checksum"):
                    service.download_verified(
                        available_update(self.package_body, checksum_body)
                    )
                self.assertEqual(len(opener.calls), 1)
                self.assertFalse(self.cache.exists())

    def test_rejects_non_https_redirect_target(self) -> None:
        service, opener = self.service(
            [
                FakeResponse(
                    self.checksum_body,
                    content_length=len(self.checksum_body),
                    url="http://untrusted.example/checksums",
                )
            ]
        )

        with self.assertRaisesRegex(UpdateError, "HTTPS"):
            service.download_verified(
                available_update(self.package_body, self.checksum_body)
            )

        self.assertEqual(len(opener.calls), 1)
        self.assertFalse(self.cache.exists())


if __name__ == "__main__":
    unittest.main()
