import importlib
import importlib.util
import re
import sys
import unittest
from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UPDATE_TEST_MODULES = (
    "tests.test_usage_metrics",
    "tests.test_distribution_channel",
    "tests.test_release_version_check",
    "tests.test_auto_update",
    "tests.test_update_controller",
    "tests.test_platform_updater",
    "tests.test_windows_installer_contract",
    "tests.test_linux_update_integration",
)


class PlatformIconTests(unittest.TestCase):
    def test_selects_native_icon_filename_for_each_platform(self) -> None:
        spec = importlib.util.find_spec("platform_assets")
        self.assertIsNotNone(spec, "platform_assets module must exist")
        platform_assets = importlib.import_module("platform_assets")

        expected = {
            "win32": "cat-type.ico",
            "darwin": "cat-type.icns",
            "linux": "cat-type.png",
        }
        for platform, filename in expected.items():
            with self.subTest(platform=platform):
                self.assertEqual(
                    platform_assets.icon_filename(platform),
                    filename,
                )

    def test_runtime_requests_current_platform_icon(self) -> None:
        from cat_type import APP_ICON

        expected = {
            "win32": "cat-type.ico",
            "darwin": "cat-type.icns",
        }.get(sys.platform, "cat-type.png")
        self.assertEqual(APP_ICON.name, expected)


class PlatformBackendTests(unittest.TestCase):
    def test_selects_native_input_and_tray_backends(self) -> None:
        platform_assets = importlib.import_module("platform_assets")
        self.assertTrue(
            hasattr(platform_assets, "backend_modules"),
            "platform_assets.backend_modules must exist",
        )

        expected = {
            "darwin": (
                "pynput.keyboard._darwin",
                "pynput.mouse._darwin",
                "pystray._darwin",
            ),
            "linux": (
                "pynput.keyboard._xorg",
                "pynput.mouse._xorg",
                "pystray._xorg",
            ),
        }
        for platform, modules in expected.items():
            with self.subTest(platform=platform):
                self.assertEqual(
                    platform_assets.backend_modules(platform),
                    modules,
                )

    def test_runtime_modules_include_pillow_tk_bridge(self) -> None:
        platform_assets = importlib.import_module("platform_assets")
        self.assertTrue(
            hasattr(platform_assets, "runtime_modules"),
            "platform_assets.runtime_modules must exist",
        )
        self.assertEqual(
            platform_assets.runtime_modules("linux"),
            (
                "PIL._tkinter_finder",
                "pynput.keyboard._xorg",
                "pynput.mouse._xorg",
                "pystray._xorg",
            ),
        )
        self.assertEqual(
            platform_assets.runtime_modules("win32"),
            (
                "PIL._tkinter_finder",
                "pynput.keyboard._win32",
                "pynput.mouse._win32",
            ),
        )


class PackagingContractTests(unittest.TestCase):
    def test_app_store_build_is_sandboxed_and_separate_from_dmg_release(self) -> None:
        spec_source = (PROJECT_ROOT / "CatType.spec").read_text(encoding="utf-8")
        entitlements = (
            PROJECT_ROOT / "packaging" / "macos-app-store.entitlements"
        ).read_text(encoding="utf-8")
        script = (
            PROJECT_ROOT / "scripts" / "build_macos_app_store.sh"
        ).read_text(encoding="utf-8")

        self.assertIn("CAT_TYPE_APP_STORE_BUILD", spec_source)
        self.assertIn("CatTypeDistributionChannel", spec_source)
        self.assertIn("CFBundleVersion", spec_source)
        self.assertIn("CAT_TYPE_BUILD_NUMBER is required", spec_source)
        self.assertIn("COLLECT(", spec_source)
        self.assertIn("exclude_binaries=is_app_store", spec_source)
        self.assertIn("com.apple.security.app-sandbox", entitlements)
        self.assertIn("9B98U2J5Q2.com.fungusta.cat-type", entitlements)
        self.assertIn("embedded.provisionprofile", script)
        self.assertIn("productbuild", script)
        self.assertIn("positive integer", script)
        self.assertIn("retry codesign", script)
        self.assertIn("retry productbuild", script)
        self.assertIn("Cat-Type-macOS-App-Store.pkg", script)

    def test_pyinstaller_explicitly_bundles_update_runtime_modules(self) -> None:
        spec_source = (PROJECT_ROOT / "CatType.spec").read_text(encoding="utf-8")

        for module in ("app_version", "auto_update", "platform_updater"):
            with self.subTest(module=module):
                self.assertIn(f'"{module}"', spec_source)

    def test_build_and_release_workflows_run_update_regressions(self) -> None:
        workflows = (
            PROJECT_ROOT / ".github" / "workflows" / "build.yml",
            PROJECT_ROOT / ".github" / "workflows" / "release.yml",
        )

        for workflow in workflows:
            source = workflow.read_text(encoding="utf-8")
            for module in UPDATE_TEST_MODULES:
                with self.subTest(workflow=workflow.name, module=module):
                    self.assertIn(module, source)

    def test_workflows_run_packaged_update_handoff_smokes(self) -> None:
        build = (
            PROJECT_ROOT / ".github" / "workflows" / "build.yml"
        ).read_text(encoding="utf-8")
        release = (
            PROJECT_ROOT / ".github" / "workflows" / "release.yml"
        ).read_text(encoding="utf-8")

        for source in (build, release):
            self.assertIn("scripts.smoke_linux_update", source)
            self.assertIn("scripts.smoke_windows_package", source)
        self.assertIn("smoke_windows_installer_update.ps1", release)
        self.assertIn("git worktree add --detach", release)
        self.assertIn("b0ce667", release)
        self.assertIn("MyAppId", release)
        self.assertIn("MyUninstallable=no", release)
        self.assertIn("SmokeTest=1", release)

        for relative_path in (
            "scripts/smoke_linux_update.py",
            "scripts/smoke_windows_package.py",
            "scripts/smoke_windows_installer_update.ps1",
        ):
            with self.subTest(path=relative_path):
                self.assertTrue((PROJECT_ROOT / relative_path).is_file())

    def test_release_builds_drag_to_applications_macos_disk_image(self) -> None:
        release = (
            PROJECT_ROOT / ".github" / "workflows" / "release.yml"
        ).read_text(encoding="utf-8")

        for expected in (
            "brew install create-dmg",
            'cp -R "dist/Cat Type.app" "$dmg_source/"',
            "--window-size 600 360",
            '--background "packaging/dmg-background-v3.png"',
            '--volicon "assets/cat-type.icns"',
            '--icon "Cat Type.app" 132 182',
            '--hide-extension "Cat Type.app"',
            "--app-drop-link 468 182",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, release)

    def test_release_signs_and_notarizes_every_macos_disk_image(self) -> None:
        spec_source = (PROJECT_ROOT / "CatType.spec").read_text(encoding="utf-8")
        release = (
            PROJECT_ROOT / ".github" / "workflows" / "release.yml"
        ).read_text(encoding="utf-8")

        self.assertIn('os.environ.get("CAT_TYPE_CODESIGN_IDENTITY")', spec_source)
        self.assertIn("CAT_TYPE_REQUIRE_SIGNING", spec_source)
        self.assertIn("codesign_identity=codesign_identity", spec_source)

        for credential in (
            "secrets.APPLE_DEVELOPER_ID_CERT_BASE64",
            "secrets.APPLE_DEVELOPER_ID_CERT_PASSWORD",
            "secrets.ASC_KEY_ID",
            "secrets.ASC_ISSUER_ID",
            "secrets.ASC_PRIVATE_KEY_B64",
            "vars.APPLE_TEAM_ID",
        ):
            with self.subTest(credential=credential):
                self.assertIn(credential, release)

        for expected in (
            "Developer ID Application:",
            "TeamIdentifier=$EXPECTED_APPLE_TEAM_ID",
            "Identifier=com.fungusta.cat-type",
            "rudrankriyam/setup-asc@5358c70a27a3f0d1517604b0f1fdc43e70c1cc4d",
            'version: "4.9.2"',
            'codesign --force --timestamp',
            '--sign "$CAT_TYPE_CODESIGN_IDENTITY"',
            'codesign --verify --strict --verbose=2 "$dmg_path"',
            "asc notarization submit",
            "xcrun stapler staple",
            "xcrun stapler validate",
            "spctl --assess",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, release)

    def test_macos_disk_image_background_matches_finder_window(self) -> None:
        background = PROJECT_ROOT / "packaging" / "dmg-background-v3.png"

        self.assertTrue(background.is_file())
        with Image.open(background) as image:
            self.assertEqual(image.size, (600, 360))
            self.assertEqual(image.mode, "RGB")

    def test_macos_disk_image_labels_do_not_cross_background_lines(self) -> None:
        release = (
            PROJECT_ROOT / ".github" / "workflows" / "release.yml"
        ).read_text(encoding="utf-8")
        positions = (
            re.search(r'--icon "Cat Type\.app" (\d+) (\d+)', release),
            re.search(r"--app-drop-link (\d+) (\d+)", release),
        )

        with Image.open(
            PROJECT_ROOT / "packaging" / "dmg-background-v3.png"
        ) as image:
            for match in positions:
                self.assertIsNotNone(match)
                assert match is not None
                center_x, center_y = map(int, match.groups())
                label_strip = image.crop(
                    (center_x - 65, center_y + 66, center_x + 65, center_y + 86)
                )
                dark_pixels = sum(
                    1
                    for red, green, blue in label_strip.get_flattened_data()
                    if red + green + blue < 390
                )
                self.assertEqual(dark_pixels, 0)


if __name__ == "__main__":
    unittest.main()
