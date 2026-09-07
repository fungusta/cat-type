"""Pose editable cat vectors and render them for the existing image surfaces."""

from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image
import resvg_py

from cat_settings import CAT_VARIANTS


POSE_NAMES = ("idle", "tap-left", "tap-right", "excited")
BASE_SIZE = 120
ET.register_namespace("", "http://www.w3.org/2000/svg")


def frame_source_path(assets_root: Path, variant: str, name: str) -> Path:
    if variant not in CAT_VARIANTS:
        raise ValueError(f"Unknown cat: {variant}")
    return assets_root / "vector-cats" / f"{variant}.svg"


def posed_svg(source: Path, name: str) -> str:
    """Derive a pose from the master without changing the editable source."""
    if name not in POSE_NAMES:
        raise ValueError(f"Unknown cat pose: {name}")
    root = ET.fromstring(source.read_text(encoding="utf-8"))
    parts = {element.get("id"): element for element in root.iter()}
    for side in ("left", "right"):
        tapping = name in (f"tap-{side}", "excited")
        parts[f"pads-{side}"].set("display", "none" if tapping else "inline")
        if tapping:
            # Compress toward the baseline: the paw drops while the head stays put.
            parts[f"paw-{side}"].set(
                "transform", "translate(0 102) scale(1 0.66) translate(0 -102)"
            )
    parts["mouth-idle"].set("display", "none" if name == "excited" else "inline")
    parts["mouth-excited"].set("display", "inline" if name == "excited" else "none")
    return ET.tostring(root, encoding="unicode")


@lru_cache(maxsize=128)
def vector_png(source: Path, name: str, size: int) -> bytes:
    """Cache rendered bytes, never mutable Pillow or interpreter-owned Tk images."""
    if size < 1:
        raise ValueError("Cat render size must be positive")
    return resvg_py.svg_to_bytes(
        svg_string=posed_svg(source, name),
        width=size,
        height=size,
        skip_system_fonts=True,
    )


def load_frame(
    assets_root: Path,
    variant: str,
    name: str,
    size: int,
    *,
    color_key_safe: bool = False,
) -> Image.Image:
    """Return an independent RGBA frame for a preview or platform surface."""
    source = frame_source_path(assets_root, variant, name)
    with Image.open(BytesIO(vector_png(source, name, size))) as image:
        frame = image.convert("RGBA")
    if color_key_safe:
        # Windows' transparent-color surface cannot composite partial alpha.
        frame.putalpha(frame.getchannel("A").point(lambda alpha: 255 if alpha >= 128 else 0))
    return frame
