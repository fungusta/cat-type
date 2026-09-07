"""Build native application icons from the gray tabby SVG."""

from pathlib import Path
import sys

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cat_artwork import load_frame

ICO_OUTPUT = PROJECT_ROOT / "assets" / "cat-type.ico"
ICNS_OUTPUT = PROJECT_ROOT / "assets" / "cat-type.icns"
PNG_OUTPUT = PROJECT_ROOT / "assets" / "cat-type.png"


def main() -> None:
    source = load_frame(PROJECT_ROOT / "assets", "gray", "idle", 224)

    icon = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    position = (
        (icon.width - source.width) // 2,
        (icon.height - source.height) // 2,
    )
    icon.alpha_composite(source, position)
    icon.save(
        ICO_OUTPUT,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    icon.save(PNG_OUTPUT, format="PNG")

    mac_icon = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    mac_source = load_frame(PROJECT_ROOT / "assets", "gray", "idle", 896)
    mac_icon.alpha_composite(mac_source, (64, 64))
    mac_icon.save(ICNS_OUTPUT, format="ICNS")


if __name__ == "__main__":
    main()
