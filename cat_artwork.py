"""Pose editable cat vectors and render them for the existing image surfaces."""

from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image
import resvg_py

from cat_accessories import normalize_accessory
from cat_settings import CAT_VARIANTS


POSE_NAMES = ("idle", "tap-left", "tap-right", "excited")
BASE_SIZE = 120
ET.register_namespace("", "http://www.w3.org/2000/svg")


def _accessory_id(value: object, slot: str) -> str:
    if value is None or value == "none":
        return "none"
    normalized = normalize_accessory(value, slot)
    if normalized == "none":
        raise ValueError(f"Unknown {slot} accessory: {value!r}")
    return normalized


def _add_accessory(root: ET.Element, source: Path, accessory_id: str, slot: str) -> None:
    if accessory_id == "none":
        return
    accessory_path = source.parent.parent / "accessories" / f"{accessory_id}.svg"
    accessory = ET.fromstring(accessory_path.read_text(encoding="utf-8"))
    layer = ET.Element("{http://www.w3.org/2000/svg}g", {"id": f"accessory-{slot}"})
    for child in accessory:
        if child.tag.rsplit("}", 1)[-1] not in {"title", "desc"}:
            layer.append(child)
    root.append(layer)


def frame_source_path(assets_root: Path, variant: str, name: str) -> Path:
    if variant not in CAT_VARIANTS:
        raise ValueError(f"Unknown cat: {variant}")
    return assets_root / "vector-cats" / f"{variant}.svg"


def posed_svg(
    source: Path,
    name: str,
    *,
    hat: object = "none",
    glasses: object = "none",
) -> str:
    """Derive a pose from the master without changing the editable source."""
    if name not in POSE_NAMES:
        raise ValueError(f"Unknown cat pose: {name}")
    hat_id = _accessory_id(hat, "hat")
    glasses_id = _accessory_id(glasses, "glasses")
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
    _add_accessory(root, source, glasses_id, "glasses")
    _add_accessory(root, source, hat_id, "hat")
    return ET.tostring(root, encoding="unicode")


def vector_png(
    source: Path,
    name: str,
    size: int,
    *,
    hat: object = "none",
    glasses: object = "none",
) -> bytes:
    """Cache rendered bytes, never mutable Pillow or interpreter-owned Tk images."""
    if size < 1:
        raise ValueError("Cat render size must be positive")
    hat_id = _accessory_id(hat, "hat")
    glasses_id = _accessory_id(glasses, "glasses")
    return _cached_vector_png(source, name, size, hat_id, glasses_id)


@lru_cache(maxsize=256)
def _cached_vector_png(
    source: Path, name: str, size: int, hat: str, glasses: str
) -> bytes:
    return resvg_py.svg_to_bytes(
        svg_string=posed_svg(source, name, hat=hat, glasses=glasses),
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
    hat: object = "none",
    glasses: object = "none",
) -> Image.Image:
    """Return an independent RGBA frame for a preview or platform surface."""
    source = frame_source_path(assets_root, variant, name)
    with Image.open(
        BytesIO(vector_png(source, name, size, hat=hat, glasses=glasses))
    ) as image:
        frame = image.convert("RGBA")
    if color_key_safe:
        # Windows' transparent-color surface cannot composite partial alpha.
        frame.putalpha(frame.getchannel("A").point(lambda alpha: 255 if alpha >= 128 else 0))
    return frame
