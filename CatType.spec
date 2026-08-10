from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_submodules
from platform_assets import icon_filename


project_root = Path(SPECPATH)
is_windows = sys.platform == "win32"
is_macos = sys.platform == "darwin"
icon_path = project_root / "assets" / icon_filename(sys.platform)
version_path = project_root / "packaging" / "version_info.txt"
hidden_imports = (
    collect_submodules("comtypes.gen")
    if is_windows
    else collect_submodules("pynput") + collect_submodules("pystray")
)

a = Analysis(
    ["cat_type.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (
            str(project_root / "assets" / "tabby-frames"),
            "assets/tabby-frames",
        ),
        (str(icon_path), "assets"),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Cat Type",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(icon_path)],
    version=str(version_path) if is_windows else None,
    uac_admin=False,
)

if is_macos:
    app = BUNDLE(
        exe,
        name="Cat Type.app",
        icon=str(icon_path),
        bundle_identifier="com.fungusta.cat-type",
        version="1.0.3",
        info_plist={
            "LSUIElement": True,
            "NSHighResolutionCapable": True,
        },
    )
