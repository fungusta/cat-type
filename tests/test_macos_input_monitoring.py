from __future__ import annotations

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from macos_input_monitoring import open_input_monitoring_settings


class MacOSInputMonitoringTests(unittest.TestCase):
    def test_open_input_monitoring_settings_uses_privacy_pane_url(self) -> None:
        url = object()
        workspace = Mock()
        workspace.openURL_.return_value = True
        ns_workspace = Mock()
        ns_workspace.sharedWorkspace.return_value = workspace
        ns_url = Mock()
        ns_url.URLWithString_.return_value = url

        with patch.dict(
            sys.modules,
            {
                "AppKit": SimpleNamespace(NSWorkspace=ns_workspace),
                "Foundation": SimpleNamespace(NSURL=ns_url),
            },
        ):
            self.assertTrue(open_input_monitoring_settings())

        ns_url.URLWithString_.assert_called_once_with(
            "x-apple.systempreferences:com.apple.preference.security?"
            "Privacy_ListenEvent"
        )
        workspace.openURL_.assert_called_once_with(url)

    def test_open_input_monitoring_settings_fails_closed_without_appkit(
        self,
    ) -> None:
        with patch.dict(sys.modules, {"AppKit": None}):
            self.assertFalse(open_input_monitoring_settings())


if __name__ == "__main__":
    unittest.main()
