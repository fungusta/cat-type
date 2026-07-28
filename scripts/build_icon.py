"""Build application icons from the gray tabby idle frame."""

from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT_ROOT / "assets" / "tabby-frames" / "gray" / "idle.png"
ICO_OUTPUT = PROJECT_ROOT / "assets" / "cat-type.ico"
ICNS_OUTPUT = PROJECT_ROOT / "assets" / "cat-type.icns"
PNG_OUTPUT = PROJECT_ROOT / "assets" / "cat-type.png"


def main() -> None:
    source = Image.open(SOURCE).convert("RGBA")
    source.thumbnail((224, 224), Image.Resampling.LANCZOS)

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
    mac_source = Image.open(SOURCE).convert("RGBA")
    mac_source = mac_source.resize((896, 896), Image.Resampling.NEAREST)
    mac_icon.alpha_composite(mac_source, (64, 64))
    mac_icon.save(ICNS_OUTPUT, format="ICNS")


if __name__ == "__main__":
    main()
