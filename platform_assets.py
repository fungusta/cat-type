"""Select runtime assets that vary by operating system."""


def icon_filename(platform: str) -> str:
    if platform == "win32":
        return "cat-type.ico"
    if platform == "darwin":
        return "cat-type.icns"
    return "cat-type.png"


def backend_modules(platform: str) -> tuple[str, ...]:
    if platform == "darwin":
        return (
            "pynput.keyboard._darwin",
            "pynput.mouse._darwin",
            "pystray._darwin",
        )
    if platform.startswith("linux"):
        return (
            "pynput.keyboard._xorg",
            "pynput.mouse._xorg",
            "pystray._xorg",
        )
    return ()


def runtime_modules(platform: str) -> tuple[str, ...]:
    return ("PIL._tkinter_finder",) + backend_modules(platform)
