from __future__ import annotations

import re
import unittest
from pathlib import Path

from auto_update import AvailableUpdate, ReleaseAsset
from platform_updater import WindowsControllerInstaller, WindowsInstaller


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "packaging" / "CatType.iss"
INSTALLER_NAME = "Cat-Type-Windows-x64.exe"
EXPECTED_FLAGS = [
    "/VERYSILENT",
    "/SUPPRESSMSGBOXES",
    "/CLOSEAPPLICATIONS",
    "/FORCECLOSEAPPLICATIONS",
    "/NORESTART",
    "/AUTOUPDATE=1",
]


def windows_update() -> AvailableUpdate:
    return AvailableUpdate(
        version="1.1.0",
        tag_name="v1.1.0",
        html_url="https://example.test/v1.1.0",
        package=ReleaseAsset(
            INSTALLER_NAME,
            f"https://example.test/{INSTALLER_NAME}",
            100,
        ),
        checksums=ReleaseAsset(
            "SHA256SUMS.txt",
            "https://example.test/SHA256SUMS.txt",
            80,
        ),
    )


class RecordingPopen:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def __call__(self, args: list[str], **kwargs: object) -> object:
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        return object()


class WindowsInstallerTests(unittest.TestCase):
    def test_starts_verified_installer_with_exact_silent_flags_and_no_shell(
        self,
    ) -> None:
        popen = RecordingPopen()
        installer = WindowsInstaller(popen=popen)
        package = Path("/verified") / INSTALLER_NAME

        result = installer.start(package)

        self.assertIsNone(result)
        self.assertEqual(
            popen.calls,
            [([str(package), *EXPECTED_FLAGS], {"shell": False})],
        )

    def test_popen_failure_propagates_instead_of_permitting_shutdown(self) -> None:
        popen = RecordingPopen(OSError("could not launch installer"))
        installer = WindowsInstaller(popen=popen)

        with self.assertRaisesRegex(OSError, "could not launch installer"):
            installer.start(Path("/verified") / INSTALLER_NAME)

    def test_rejects_any_other_installer_filename_before_launch(self) -> None:
        popen = RecordingPopen()
        installer = WindowsInstaller(popen=popen)

        with self.assertRaisesRegex(ValueError, INSTALLER_NAME):
            installer.start(Path("/verified/Cat-Type-Windows-x86.exe"))

        self.assertEqual(popen.calls, [])

    def test_controller_prepare_only_validates_and_returns_package(self) -> None:
        package = Path("/verified") / INSTALLER_NAME
        adapter = WindowsControllerInstaller()

        prepared = adapter.prepare(package, windows_update())

        self.assertIs(prepared, package)

    def test_controller_rejects_mismatched_verified_asset(self) -> None:
        package = Path("/verified") / INSTALLER_NAME
        update = windows_update()
        mismatched = AvailableUpdate(
            version=update.version,
            tag_name=update.tag_name,
            html_url=update.html_url,
            package=ReleaseAsset(
                "renamed.exe",
                update.package.url,
                update.package.size,
            ),
            checksums=update.checksums,
        )

        with self.assertRaisesRegex(ValueError, INSTALLER_NAME):
            WindowsControllerInstaller().prepare(package, mismatched)

    def test_controller_start_delegates_to_low_level_installer(self) -> None:
        class FakeInstaller:
            def __init__(self) -> None:
                self.started: list[Path] = []

            def start(self, package: Path) -> None:
                self.started.append(package)

        low_level = FakeInstaller()
        adapter = WindowsControllerInstaller(installer=low_level)
        package = Path("/verified") / INSTALLER_NAME

        adapter.start(package)

        self.assertEqual(low_level.started, [package])


class InnoInstallerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = SCRIPT_PATH.read_text(encoding="utf-8")

    def test_restart_manager_force_fallback_does_not_restart_applications(
        self,
    ) -> None:
        self.assertRegex(self.script, r"(?mi)^CloseApplications=force$")
        self.assertRegex(self.script, r"(?mi)^RestartApplications=no$")

    def test_uses_official_unicode_kernel32_event_and_mutex_declarations(
        self,
    ) -> None:
        for api in ("OpenEventW", "SetEvent", "CloseHandle", "OpenMutexW"):
            with self.subTest(api=api):
                self.assertRegex(
                    self.script,
                    rf"(?is)external\s+'{api}@kernel32\.dll\s+stdcall'",
                )

    def test_prepare_to_install_signals_event_then_waits_for_exact_mutex(
        self,
    ) -> None:
        prepare = re.search(
            r"(?is)function\s+PrepareToInstall\s*\([^)]*\).*?"
            r"begin(?P<body>.*?)end\s*;",
            self.script,
        )
        self.assertIsNotNone(prepare)
        body = prepare.group("body")
        self.assertIn("SignalCatTypeShutdown", body)
        self.assertIn("WaitForCatTypeExit", body)
        self.assertLess(
            body.index("SignalCatTypeShutdown"),
            body.index("WaitForCatTypeExit"),
        )
        self.assertIn("Local\\CatTypeShutdown", self.script)
        self.assertIn("Local\\CatTypeDesktopApp", self.script)

    def test_graceful_wait_is_bounded_to_five_seconds_in_short_intervals(
        self,
    ) -> None:
        wait = re.search(
            r"(?is)procedure\s+WaitForCatTypeExit\s*;.*?"
            r"begin(?P<body>.*?)end\s*;",
            self.script,
        )
        self.assertIsNotNone(wait)
        body = wait.group("body")
        self.assertRegex(body, r"(?i)for\s+\w+\s*:=\s*1\s+to\s+50\s+do")
        self.assertRegex(body, r"(?i)Sleep\s*\(\s*100\s*\)")
        self.assertRegex(body, r"(?i)OpenMutex\w*\s*\(")

    def test_auto_update_parameter_check_is_exact_and_case_insensitive(
        self,
    ) -> None:
        auto_update = re.search(
            r"(?is)function\s+IsAutoUpdate\s*:\s*Boolean\s*;.*?"
            r"begin(?P<body>.*?)end\s*;",
            self.script,
        )
        self.assertIsNotNone(auto_update)
        self.assertIn("WizardSilent", auto_update.group("body"))
        self.assertRegex(
            self.script,
            r"(?is)for\s+\w+\s*:=\s*1\s+to\s+ParamCount\s+do",
        )
        self.assertRegex(
            self.script,
            r"(?is)CompareText\s*\(\s*ParamStr\s*\(\s*\w+\s*\)\s*,"
            r"\s*'/AUTOUPDATE=1'\s*\)\s*=\s*0",
        )

    def test_silent_auto_update_relaunch_is_gated_without_duplication(
        self,
    ) -> None:
        run_section = self.script.split("[Run]", 1)[1].split("[Code]", 1)[0]
        entries = [
            line.strip()
            for line in run_section.splitlines()
            if line.strip().lower().startswith("filename:")
        ]
        self.assertEqual(len(entries), 2)
        auto_entries = [
            line
            for line in entries
            if "skipifnotsilent" in line.lower()
            and "Check: IsAutoUpdate" in line
        ]
        self.assertEqual(len(auto_entries), 1)
        self.assertNotIn("postinstall", auto_entries[0].lower())

    def test_interactive_postinstall_launch_is_preserved_and_skips_silent(
        self,
    ) -> None:
        interactive = [
            line
            for line in self.script.splitlines()
            if "Description: \"Launch Cat Type\"" in line
        ]
        self.assertEqual(len(interactive), 1)
        flags = interactive[0].lower()
        self.assertIn("postinstall", flags)
        self.assertIn("skipifsilent", flags)
        self.assertNotIn("skipifnotsilent", flags)


if __name__ == "__main__":
    unittest.main()
