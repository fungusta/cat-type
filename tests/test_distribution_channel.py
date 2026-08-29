import os
import plistlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from distribution_channel import (
    APP_STORE_CHANNEL,
    DIRECT_CHANNEL,
    distribution_channel,
    is_app_store_build,
)


class DistributionChannelTests(unittest.TestCase):
    def test_source_runs_default_to_direct_distribution(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(distribution_channel(frozen=False), DIRECT_CHANNEL)

    def test_environment_override_supports_local_store_testing(self) -> None:
        with patch.dict(
            os.environ,
            {"CAT_TYPE_DISTRIBUTION_CHANNEL": APP_STORE_CHANNEL},
            clear=True,
        ):
            self.assertTrue(is_app_store_build(frozen=False))

    def test_frozen_macos_build_reads_channel_from_info_plist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            contents = Path(directory) / "Cat Type.app" / "Contents"
            executable = contents / "MacOS" / "Cat Type"
            executable.parent.mkdir(parents=True)
            (contents / "Info.plist").write_bytes(
                plistlib.dumps(
                    {"CatTypeDistributionChannel": APP_STORE_CHANNEL}
                )
            )

            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(
                    distribution_channel(
                        platform_name="darwin",
                        executable=executable,
                        frozen=True,
                    ),
                    APP_STORE_CHANNEL,
                )


if __name__ == "__main__":
    unittest.main()
