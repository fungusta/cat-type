from __future__ import annotations

import json
import os
import plistlib
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any


APP_NAME = "Cat Type"
SETTINGS_VERSION = 1
VALID_CAT_STYLES = ("alternate", "gray", "ginger")
VALID_PLACEMENTS = ("above-right", "above-left", "below-right", "below-left")
VALID_METRICS_VIEWS = ("line", "columns")


@dataclass
class AppSettings:
    enabled: bool = True
    cat_style: str = "alternate"
    size_percent: int = 100
    hold_seconds: float = 1.5
    fade_seconds: float = 0.35
    placement: str = "above-right"
    launch_at_startup: bool = False
    metrics_view: str = "line"
    monitoring_consent: bool = False

    def normalized(self) -> "AppSettings":
        cat_style = (
            self.cat_style
            if self.cat_style in VALID_CAT_STYLES
            else AppSettings.cat_style
        )
        placement = (
            self.placement
            if self.placement in VALID_PLACEMENTS
            else AppSettings.placement
        )
        metrics_view = (
            self.metrics_view
            if self.metrics_view in VALID_METRICS_VIEWS
            else AppSettings.metrics_view
        )
        hold_seconds = min(5.0, max(0.5, float(self.hold_seconds)))
        fade_seconds = min(1.5, max(0.0, float(self.fade_seconds)))
        fade_seconds = min(fade_seconds, hold_seconds)
        return AppSettings(
            enabled=bool(self.enabled),
            cat_style=cat_style,
            size_percent=min(175, max(60, int(self.size_percent))),
            hold_seconds=round(hold_seconds, 2),
            fade_seconds=round(fade_seconds, 2),
            placement=placement,
            launch_at_startup=bool(self.launch_at_startup),
            metrics_view=metrics_view,
            monitoring_consent=bool(self.monitoring_consent),
        )


def default_settings_path() -> Path:
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        base = (
            Path(local_app_data)
            if local_app_data
            else Path.home() / "AppData" / "Local"
        )
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / APP_NAME / "settings.json"


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_settings_path()

    def load(self) -> AppSettings:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return AppSettings()
            known = {field.name for field in fields(AppSettings)}
            values = {key: value for key, value in payload.items() if key in known}
            return AppSettings(**values).normalized()
        except (OSError, ValueError, TypeError):
            return AppSettings()

    def save(self, settings: AppSettings) -> AppSettings:
        normalized = settings.normalized()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "version": SETTINGS_VERSION,
            **asdict(normalized),
        }
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)
        return normalized


def startup_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}"'
    return f'"{Path(sys.executable).resolve()}" "{Path(__file__).resolve().with_name("cat_type.py")}"'


def set_launch_at_startup(enabled: bool) -> None:
    if sys.platform == "darwin":
        launch_agents = Path.home() / "Library" / "LaunchAgents"
        launch_agent = launch_agents / "com.fungusta.cat-type.plist"
        if not enabled:
            launch_agent.unlink(missing_ok=True)
            return
        launch_agents.mkdir(parents=True, exist_ok=True)
        command = (
            [str(Path(sys.executable).resolve())]
            if getattr(sys, "frozen", False)
            else [
                str(Path(sys.executable).resolve()),
                str(Path(__file__).resolve().with_name("cat_type.py")),
            ]
        )
        launch_agent.write_bytes(
            plistlib.dumps(
                {
                    "Label": "com.fungusta.cat-type",
                    "ProgramArguments": command,
                    "RunAtLoad": True,
                }
            )
        )
        return

    if sys.platform != "win32":
        autostart = (
            Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
            / "autostart"
        )
        desktop_file = autostart / "cat-type.desktop"
        if not enabled:
            desktop_file.unlink(missing_ok=True)
            return
        autostart.mkdir(parents=True, exist_ok=True)
        desktop_file.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Cat Type\n"
            f"Exec={startup_command()}\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n",
            encoding="utf-8",
        )
        return

    import winreg

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER,
        key_path,
        0,
        winreg.KEY_SET_VALUE,
    ) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
