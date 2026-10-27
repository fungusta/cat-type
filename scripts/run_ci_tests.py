"""Run the CI unittest matrix and expose failures as GitHub annotations."""

from __future__ import annotations

import re
import subprocess
import sys


TEST_MODULES = (
    "tests.test_macos_overlay_focus",
    "tests.test_macos_pointer",
    "tests.test_behavior",
    "tests.test_settings",
    "tests.test_cat_artwork",
    "tests.test_achievements",
    "tests.test_accessory_artwork",
    "tests.test_wardrobe",
    "tests.test_wardrobe_integration",
    "tests.test_cat_comparison",
    "tests.test_vector_platform_surfaces",
    "tests.test_overlay_rendering",
    "tests.test_usage_metrics",
    "tests.test_settings_window",
    "tests.test_platform_assets",
    "tests.test_bundled_icon_check",
    "tests.test_package_smoke",
    "tests.test_release_version_check",
    "tests.test_auto_update",
    "tests.test_update_controller",
    "tests.test_platform_updater",
    "tests.test_windows_installer_contract",
)


def _escape_annotation(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def main() -> int:
    modules = list(TEST_MODULES)
    if sys.platform.startswith("linux"):
        modules.append("tests.test_linux_update_integration")
    result = subprocess.run(
        [sys.executable, "-m", "unittest", *modules, "-v"],
        text=True,
        capture_output=True,
    )
    output = (result.stdout or "") + (result.stderr or "")
    print(output, end="")
    if result.returncode:
        failures = re.findall(r"^(?:FAIL|ERROR): (.+)$", output, re.MULTILINE)
        if not failures:
            failures = [f"unittest exited with code {result.returncode}"]
        for failure in failures:
            print(
                "::error title=Automated test failure::"
                + _escape_annotation(failure)
            )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
