from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


project_root = Path(SPECPATH)
icon_path = project_root / "assets" / "cat-type.ico"
version_path = project_root / "packaging" / "version_info.txt"

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
    hiddenimports=collect_submodules("comtypes.gen"),
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
    version=str(version_path),
    uac_admin=False,
)
