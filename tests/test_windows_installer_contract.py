from __future__ import annotations

import os
import re
import unittest
from pathlib import Path
from unittest.mock import patch

from auto_update import AvailableUpdate, ReleaseAsset
from platform_updater import WindowsControllerInstaller, WindowsInstaller


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "packaging" / "CatType.iss"
SMOKE_SCRIPT_PATH = ROOT / "scripts" / "smoke_windows_installer_update.ps1"
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
    def test_starts_verified_installer_with_fresh_pyinstaller_environment(
        self,
    ) -> None:
        popen = RecordingPopen()
        installer = WindowsInstaller(popen=popen)
        package = Path("/verified") / INSTALLER_NAME

        with patch.dict(
            os.environ,
            {
                "CAT_TYPE_ENV_SENTINEL": "preserved",
                "PYINSTALLER_RESET_ENVIRONMENT": "stale",
            },
        ):
            result = installer.start(package)
            self.assertEqual(
                os.environ["PYINSTALLER_RESET_ENVIRONMENT"],
                "stale",
            )

        self.assertIsNone(result)
        self.assertEqual(len(popen.calls), 1)
        args, kwargs = popen.calls[0]
        self.assertEqual(args, [str(package), *EXPECTED_FLAGS])
        self.assertFalse(kwargs["shell"])
        self.assertIn("env", kwargs)
        environment = kwargs["env"]
        self.assertEqual(environment["CAT_TYPE_ENV_SENTINEL"], "preserved")
        self.assertEqual(
            environment["PYINSTALLER_RESET_ENVIRONMENT"],
            "1",
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
        body = self.script[self.script.index("function PrepareToInstall") :]
        self.assertIn("SignalCatTypeShutdown", body)
        self.assertIn("WaitForCatTypeExit", body)
        self.assertLess(
            body.index("SignalCatTypeShutdown"),
            body.index("WaitForCatTypeExit"),
        )
        self.assertIn("Local\\CatTypeShutdown", self.script)
        self.assertIn("Local\\CatTypeDesktopApp", self.script)

    def test_silent_non_auto_install_stops_before_shutdown_or_restart_manager(
        self,
    ) -> None:
        prepare = self.script[self.script.index("function PrepareToInstall") :]
        invalid_silent = re.search(
            r"(?is)if\s+WizardSilent\s+then\s+begin\s+"
            r"if\s+not\s+IsAutoUpdate\s+then\s+begin\s+"
            r"Result\s*:=\s*'[^']+'\s*;\s+Exit\s*;\s+end\s*;",
            prepare,
        )
        self.assertIsNotNone(invalid_silent)
        assert invalid_silent is not None
        self.assertLess(
            invalid_silent.end(),
            prepare.index("OpenCatTypeShutdownEvent"),
        )
        self.assertLess(
            invalid_silent.end(),
            prepare.index("SignalCatTypeShutdown"),
        )

    def test_valid_silent_auto_update_signals_and_waits(self) -> None:
        prepare = self.script[self.script.index("function PrepareToInstall") :]
        self.assertRegex(
            prepare,
            r"(?is)if\s+WizardSilent\s+then\s+begin.*?"
            r"if\s+not\s+IsAutoUpdate\s+then.*?Exit\s*;.*?"
            r"ShutdownEvent\s*:=\s*OpenCatTypeShutdownEvent\s*;.*?"
            r"end\s+else\s+begin",
        )
        self.assertRegex(
            prepare,
            r"(?is)if\s+ShutdownEvent\s*<>\s*0\s+then\s+begin\s+"
            r"SignalCatTypeShutdown\s*\(\s*ShutdownEvent\s*\)\s*;\s+"
            r"WaitForCatTypeExit\s*;",
        )

    def test_interactive_current_app_prompts_before_signal_and_honors_answer(
        self,
    ) -> None:
        prepare = self.script[self.script.index("function PrepareToInstall") :]
        interactive = re.search(
            r"(?is)end\s+else\s+begin(?P<body>.*?)end\s*;\s+"
            r"if\s+ShutdownEvent\s*<>\s*0",
            prepare,
        )
        self.assertIsNotNone(interactive)
        body = interactive.group("body")
        self.assertRegex(
            body,
            r"ShutdownEvent\s*:=\s*OpenCatTypeShutdownEvent\s*;",
        )
        self.assertRegex(
            body,
            r"(?is)if\s+ShutdownEvent\s*=\s*0\s+then\s+Exit\s*;",
        )
        self.assertRegex(
            body,
            r"(?is)MsgBox\s*\(.*?Cat Type must close to update.*?"
            r"MB_YESNO.*?\)\s*<>\s*IDYES",
        )
        declined = re.search(
            r"(?is)if\s+MsgBox\s*\(.*?\)\s*<>\s*IDYES\s+then\s+"
            r"begin(?P<body>.*?)end\s*;",
            body,
        )
        self.assertIsNotNone(declined)
        declined_body = declined.group("body")
        self.assertIn("CloseHandle(ShutdownEvent)", declined_body)
        self.assertRegex(declined_body, r"Result\s*:=\s*'[^']+'\s*;")
        self.assertIn("Exit;", declined_body)
        self.assertNotIn("SignalCatTypeShutdown", body)

    def test_interactive_old_app_falls_through_to_restart_manager_prompt(
        self,
    ) -> None:
        prepare = self.script[self.script.index("function PrepareToInstall") :]
        self.assertRegex(
            prepare,
            r"(?is)Result\s*:=\s*''\s*;.*?end\s+else\s+begin\s+"
            r"ShutdownEvent\s*:=\s*OpenCatTypeShutdownEvent\s*;\s+"
            r"if\s+ShutdownEvent\s*=\s*0\s+then\s+Exit\s*;\s+"
            r"if\s+MsgBox",
        )

    def test_shutdown_event_opened_by_prepare_is_closed_on_every_path(
        self,
    ) -> None:
        signal = re.search(
            r"(?is)procedure\s+SignalCatTypeShutdown\s*"
            r"\(\s*ShutdownEvent\s*:\s*THandle\s*\)\s*;.*?"
            r"begin(?P<body>.*?)end\s*;",
            self.script,
        )
        self.assertIsNotNone(signal)
        self.assertIn("CloseHandle(ShutdownEvent)", signal.group("body"))
        self.assertRegex(
            self.script[self.script.index("function PrepareToInstall") :],
            r"(?is)if\s+MsgBox.*?<>\s*IDYES\s+then\s+begin.*?"
            r"CloseHandle\s*\(\s*ShutdownEvent\s*\).*?Exit\s*;",
        )

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


class WindowsInstallerSmokeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = SMOKE_SCRIPT_PATH.read_text(encoding="utf-8")

    def test_waits_for_installer_without_waiting_for_relaunched_process_tree(
        self,
    ) -> None:
        installer_run = self.script[self.script.index("$install = Start-Process") :]

        self.assertNotRegex(
            installer_run,
            r"(?is)Start-Process.*?\s-Wait\s+.*?\s-PassThru",
        )
        self.assertRegex(
            installer_run,
            r"(?i)Wait-Process\s+-InputObject\s+\$install\s+-Timeout\s+\d+",
        )


if __name__ == "__main__":
    unittest.main()
