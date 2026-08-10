"""Select runtime assets that vary by operating system."""


def icon_filename(platform: str) -> str:
    if platform == "win32":
        return "cat-type.ico"
    if platform == "darwin":
        return "cat-type.icns"
    return "cat-type.png"
