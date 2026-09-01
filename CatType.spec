from pathlib import Path
import os
import sys

from PyInstaller.utils.hooks import collect_submodules
from platform_assets import icon_filename, runtime_modules


project_root = Path(SPECPATH)
is_windows = sys.platform == "win32"
is_macos = sys.platform == "darwin"
macos_build_number = os.environ.get("CAT_TYPE_BUILD_NUMBER", "1")
codesign_identity = (
    os.environ.get("CAT_TYPE_CODESIGN_IDENTITY") if is_macos else None
)
if (
    is_macos
    and os.environ.get("CAT_TYPE_REQUIRE_SIGNING") == "1"
    and not codesign_identity
):
    raise RuntimeError("CAT_TYPE_CODESIGN_IDENTITY is required for this macOS build")
if is_macos and (
    len(macos_build_number.split(".")) > 3
    or not all(part.isdigit() and part for part in macos_build_number.split("."))
):
    raise RuntimeError("CAT_TYPE_BUILD_NUMBER must have one to three numeric segments")
icon_path = project_root / "assets" / icon_filename(sys.platform)
version_path = project_root / "packaging" / "version_info.txt"
# Do not discover these by importing pynput/pystray: their native backends
# require an active display and disappear from headless CI builds otherwise.
hidden_imports = [
    "app_version",
    "auto_update",
    "platform_updater",
    *runtime_modules(sys.platform),
]
if is_windows:
    hidden_imports += collect_submodules("comtypes.gen")

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

exe_contents = [pyz, a.scripts]
if is_macos:
    # Keep support files inside the signed app. PyInstaller's one-file macOS
    # bundle extracts at runtime and is deprecated.
    exe_contents.append([])
else:
    exe_contents.extend([a.binaries, a.datas, []])

exe = EXE(
    *exe_contents,
    name="Cat Type",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    exclude_binaries=is_macos,
    codesign_identity=codesign_identity,
    entitlements_file=None,
    icon=[str(icon_path)],
    version=str(version_path) if is_windows else None,
    uac_admin=False,
)

if is_macos:
    bundle_input = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        name="Cat Type",
    )
    app = BUNDLE(
        bundle_input,
        name="Cat Type.app",
        icon=str(icon_path),
        bundle_identifier="com.fungusta.cat-type",
        version="1.0.33",
        info_plist={
            "LSUIElement": True,
            "NSHighResolutionCapable": True,
            "CFBundleVersion": macos_build_number,
            "LSMinimumSystemVersion": "12.0",
            "LSApplicationCategoryType": "public.app-category.utilities",
            "NSHumanReadableCopyright": (
                "Copyright © 2026 Peter Fung. All rights reserved."
            ),
            "ITSAppUsesNonExemptEncryption": False,
        },
    )
