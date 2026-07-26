"""Build the Windows application icon from the gray tabby idle frame."""

from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT_ROOT / "assets" / "tabby-frames" / "gray" / "idle.png"
OUTPUT = PROJECT_ROOT / "assets" / "cat-type.ico"


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
        OUTPUT,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )


if __name__ == "__main__":
    main()
