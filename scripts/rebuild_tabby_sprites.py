"""Build the smaller gray and ginger tabby runtime sprite sets."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image

from rebuild_bongo_sprites import (
    FRAME_NAMES,
    make_color_key_safe,
    neutralize_green_spill,
)


FRAME_SIZE = 120
VARIANTS = ("gray", "ginger")


def align_upper_body(frames: list[Image.Image]) -> list[Image.Image]:
    """Translate frames so pose changes cannot shift the cat's upper body."""
    target_center_x = (FRAME_SIZE - 1) / 2
    aligned_frames = []

    for frame in frames:
        upper_alpha = frame.getchannel("A").crop(
            (0, 0, FRAME_SIZE, round(FRAME_SIZE * 0.6))
        )
        bounds = upper_alpha.getbbox()
        if bounds is None:
            raise ValueError("Sprite frame has no visible upper-body pixels")

        current_center_x = (bounds[0] + bounds[2] - 1) / 2
        delta = target_center_x - current_center_x
        shift_x = (
            math.floor(delta + 0.5)
            if delta >= 0
            else math.ceil(delta - 0.5)
        )

        aligned = Image.new(
            "RGBA",
            (FRAME_SIZE, FRAME_SIZE),
            (0, 0, 0, 0),
        )
        aligned.alpha_composite(frame, (shift_x, 0))
        aligned_frames.append(aligned)

    return aligned_frames


def rebuild_variant(
    variant: str,
    input_path: Path,
    assets_dir: Path,
) -> None:
    source = neutralize_green_spill(Image.open(input_path))
    cell_width = source.width // len(FRAME_NAMES)
    alpha_bounds = source.getchannel("A").getbbox()
    if alpha_bounds is None:
        raise ValueError(f"{input_path} contains no visible sprite pixels")

    center_y = (alpha_bounds[1] + alpha_bounds[3]) / 2
    crop_top = round(center_y - cell_width / 2)
    crop_top = max(0, min(crop_top, source.height - cell_width))

    frames_dir = assets_dir / "tabby-frames" / variant
    frames_dir.mkdir(parents=True, exist_ok=True)
    frames = []

    for index, frame_name in enumerate(FRAME_NAMES):
        crop_box = (
            index * cell_width,
            crop_top,
            (index + 1) * cell_width,
            crop_top + cell_width,
        )
        frame = source.crop(crop_box).resize(
            (FRAME_SIZE, FRAME_SIZE),
            Image.Resampling.LANCZOS,
        )
        frame = neutralize_green_spill(frame)
        frame = make_color_key_safe(frame)
        frames.append(frame)

    frames = align_upper_body(frames)
    for frame_name, frame in zip(FRAME_NAMES, frames, strict=True):
        frame.save(frames_dir / f"{frame_name}.png")

    sheet = Image.new(
        "RGBA",
        (FRAME_SIZE * len(frames), FRAME_SIZE),
        (0, 0, 0, 0),
    )
    for index, frame in enumerate(frames):
        sheet.alpha_composite(frame, (index * FRAME_SIZE, 0))
    sheet.save(assets_dir / f"tabby-{variant}-sprite-sheet.png")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("gray", type=Path)
    parser.add_argument("ginger", type=Path)
    parser.add_argument(
        "--assets-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "assets",
    )
    args = parser.parse_args()

    rebuild_variant("gray", args.gray, args.assets_dir)
    rebuild_variant("ginger", args.ginger, args.assets_dir)


if __name__ == "__main__":
    main()
