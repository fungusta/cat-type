"""Remove chroma spill and rebuild the runtime Bongo Cat sprite assets."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


FRAME_NAMES = ("idle", "tap-left", "tap-right", "excited")
FRAME_SIZE = 160
CROP_SIZE = 430
CROP_CENTER_Y = 370
COLOR_KEY_ALPHA_THRESHOLD = 96


def neutralize_green_spill(image: Image.Image) -> Image.Image:
    """Remove excess green while preserving transparency and other colours."""
    image = image.convert("RGBA")
    cleaned_pixels = []
    for red, green, blue, alpha in image.get_flattened_data():
        if alpha == 0:
            cleaned_pixels.append((0, 0, 0, 0))
        else:
            cleaned_pixels.append(
                (red, min(green, max(red, blue)), blue, alpha)
            )
    image.putdata(cleaned_pixels)
    return image


def make_color_key_safe(image: Image.Image) -> Image.Image:
    """Prevent Tk's green background from bleeding through soft alpha edges."""
    image = image.convert("RGBA")
    hardened_pixels = []
    for red, green, blue, alpha in image.get_flattened_data():
        if alpha < COLOR_KEY_ALPHA_THRESHOLD:
            hardened_pixels.append((0, 0, 0, 0))
        else:
            hardened_pixels.append((red, green, blue, 255))
    image.putdata(hardened_pixels)
    return image


def rebuild(input_path: Path, assets_dir: Path) -> None:
    source = neutralize_green_spill(Image.open(input_path))
    source.save(assets_dir / "bongo-cat-sprites-alpha.png")

    frames_dir = assets_dir / "bongo-frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    cell_width = source.width / len(FRAME_NAMES)
    frames = []

    for index, name in enumerate(FRAME_NAMES):
        center_x = (index + 0.5) * cell_width
        crop_box = (
            round(center_x - CROP_SIZE / 2),
            round(CROP_CENTER_Y - CROP_SIZE / 2),
            round(center_x + CROP_SIZE / 2),
            round(CROP_CENTER_Y + CROP_SIZE / 2),
        )
        frame = source.crop(crop_box).resize(
            (FRAME_SIZE, FRAME_SIZE),
            Image.Resampling.LANCZOS,
        )
        frame = neutralize_green_spill(frame)
        frame = make_color_key_safe(frame)
        frame.save(frames_dir / f"{name}.png")
        frames.append(frame)

    sheet = Image.new(
        "RGBA",
        (FRAME_SIZE * len(frames), FRAME_SIZE),
        (0, 0, 0, 0),
    )
    for index, frame in enumerate(frames):
        sheet.alpha_composite(frame, (index * FRAME_SIZE, 0))
    sheet.save(assets_dir / "bongo-cat-sprite-sheet.png")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="Background-removed source PNG")
    parser.add_argument(
        "--assets-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "assets",
    )
    args = parser.parse_args()
    rebuild(args.input, args.assets_dir)


if __name__ == "__main__":
    main()
