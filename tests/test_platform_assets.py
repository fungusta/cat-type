import importlib
import importlib.util
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UPDATE_TEST_MODULES = (
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
            '--icon "Cat Type.app" 150 180',
            '--hide-extension "Cat Type.app"',
            "--app-drop-link 450 180",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, release)


if __name__ == "__main__":
    unittest.main()
