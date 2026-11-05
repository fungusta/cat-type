"""Assemble the static landing page from site/ and the app's own artwork."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cat_accessories import ACCESSORIES, ACCESSORY_BLURBS, ACCESSORY_BY_ID, Accessory  # noqa: E402
from cat_settings import CAT_VARIANTS  # noqa: E402


SHOWCASE_IDS = ("beanie", "party-hat", "crown", "dragon-wings")
EQUIPPED_ID = "beanie"
# One pretend first-week user, oldest day first and today last. The Unlock
# and Track bands both read from it so their numbers always agree.
PRETEND_WEEK = (1180, 1620, 940, 1850, 1410, 2060, 1440)
ANALYTICS_MARKER = "<!-- analytics -->"


def analytics_tag(code: str) -> str:
    """GoatCounter's script for a site code, or nothing when no code is set."""
    if not code:
        return ""
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,49}", code):
        raise ValueError(f"Invalid GoatCounter site code: {code!r}")
    return (f'<script data-goatcounter="https://{code}.goatcounter.com/count" '
            'async src="https://gc.zgo.at/count.js"></script>')


def starter_items() -> tuple[Accessory, ...]:
    """Visible items earned within about a first week of ordinary use."""
    return tuple(
        item for item in ACCESSORIES
        if not item.hidden and (
            (item.metric == "keystrokes" and item.target <= 10_000)
            or (item.metric == "days" and item.target <= 7)
        )
    )


def _progress(item: Accessory, total: int) -> int:
    return min(100, total * 100 // item.target)


def catalog() -> dict:
    total = sum(PRETEND_WEEK)
    showcase = [ACCESSORY_BY_ID[item_id] for item_id in SHOWCASE_IDS]
    return {
        "cats": list(CAT_VARIANTS),
        "starters": [
            {"id": item.id, "name": item.name, "slot": item.slot}
            for item in starter_items()
        ],
        "showcase": [
            {
                "id": item.id,
                "name": item.name,
                "blurb": ACCESSORY_BLURBS[item.id],
                "target": item.target,
                "metric": item.metric,
                "progress": _progress(item, total),
                "equipped": item.id == EQUIPPED_ID,
            }
            for item in showcase
        ],
        "week": list(PRETEND_WEEK),
        "today": PRETEND_WEEK[-1],
        "last7": total,
        "allTime": total,
    }


def build_site(out_dir: Path = PROJECT_ROOT / "build" / "site", goatcounter_code: str | None = None) -> Path:
    data = catalog()
    if goatcounter_code is None:
        goatcounter_code = os.environ.get("GOATCOUNTER_CODE", "").strip()
    tag = analytics_tag(goatcounter_code)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(PROJECT_ROOT / "site", out_dir, ignore=shutil.ignore_patterns("tests"))
    cats = out_dir / "assets" / "cats"
    accessories = out_dir / "assets" / "accessories"
    cats.mkdir(parents=True)
    accessories.mkdir(parents=True)
    for variant in data["cats"]:
        shutil.copy2(PROJECT_ROOT / "assets" / "vector-cats" / f"{variant}.svg", cats)
    for item_id in [item["id"] for item in data["starters"]] + list(SHOWCASE_IDS):
        if ACCESSORY_BY_ID[item_id].hidden:
            raise ValueError(f"Secret accessory cannot be published: {item_id}")
        shutil.copy2(PROJECT_ROOT / "assets" / "accessories" / f"{item_id}.svg", accessories)
    for page in out_dir.glob("*.html"):
        text = page.read_text(encoding="utf-8")
        page.write_text(text.replace(ANALYTICS_MARKER, tag), encoding="utf-8")
    (out_dir / "catalog.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return out_dir


if __name__ == "__main__":
    print(build_site())
