"""Preview and export Cat Type's editable SVG cats."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw, ImageTk


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cat_artwork import (
    BASE_SIZE,
    POSE_NAMES,
    frame_source_path,
    load_frame,
    posed_svg,
)
from cat_settings import CAT_VARIANTS
from cat_type import AnimationState, classify_portable_key


ASSETS_ROOT = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT)) / "assets"
CAT_LABELS = {
    "gray": "Gray tabby",
    "ginger": "Ginger tabby",
    "charcoal": "Charcoal",
    "brown-tabby": "Brown tabby",
    "white": "White",
    "black-white": "Black & white",
}
CAT_BY_LABEL = {label: variant for variant, label in CAT_LABELS.items()}
TK_KEY_ALIASES = {
    "return": "enter",
    "control_l": "ctrl_l",
    "control_r": "ctrl_r",
    "escape": "esc",
    "prior": "page_up",
    "next": "page_down",
}


def classify_tk_key(event: object) -> str:
    """Translate a focused Tk key event through the app's portable classifier."""
    keysym = str(getattr(event, "keysym", ""))
    key = SimpleNamespace(
        char=getattr(event, "char", None),
        name=TK_KEY_ALIASES.get(keysym.lower(), keysym.lower()),
        _cat_type_keypad=keysym.startswith("KP_"),
    )
    return classify_portable_key(key)


def export_preview(export_dir: Path) -> None:
    """Export every pose as SVG plus a six-cat preview sheet."""
    export_dir.mkdir(parents=True, exist_ok=True)
    for variant in CAT_VARIANTS:
        source = frame_source_path(ASSETS_ROOT, variant, "idle")
        for pose in POSE_NAMES:
            (export_dir / f"{variant}-{pose}.svg").write_text(
                posed_svg(source, pose), encoding="utf-8"
            )

    label_width = 132
    header_height = 38
    row_height = BASE_SIZE + 24
    sheet = Image.new(
        "RGBA",
        (
            label_width + len(POSE_NAMES) * BASE_SIZE,
            header_height + len(CAT_VARIANTS) * row_height,
        ),
        "white",
    )
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 12), f"SVG cats - 100% / {BASE_SIZE} px", fill="#32251f")
    for column, pose in enumerate(POSE_NAMES):
        x = label_width + column * BASE_SIZE
        draw.text((x + 8, header_height + 4), pose, fill="#6b5147")
    for row, variant in enumerate(CAT_VARIANTS):
        y = header_height + row * row_height
        draw.text((12, y + 54), CAT_LABELS[variant], fill="#32251f")
        for column, pose in enumerate(POSE_NAMES):
            frame = load_frame(ASSETS_ROOT, variant, pose, BASE_SIZE)
            sheet.alpha_composite(
                frame,
                (label_width + column * BASE_SIZE, y + 20),
            )
    sheet.convert("RGB").save(export_dir / "preview.png")


class PreviewWindow:
    def __init__(self) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.root = tk.Tk()
        self.root.title("Cat Type — SVG cat preview")
        self.root.configure(background="#fff6f0")
        self.state = AnimationState()
        self.size_percent = tk.IntVar(value=100)
        self.cat = tk.StringVar(value=CAT_LABELS["white"])
        self.pose_text = tk.StringVar(value="idle")
        self.image: ImageTk.PhotoImage
        self._idle_after: str | None = None

        ttk.Label(
            self.root, text="SVG cat preview", font=("TkDefaultFont", 15, "bold")
        ).grid(row=0, column=0, pady=(16, 4))
        ttk.Label(
            self.root, text="Click this window and type to preview keyboard reactions."
        ).grid(row=1, column=0, pady=(0, 12))

        cat_picker = ttk.Frame(self.root)
        cat_picker.grid(row=2, column=0, pady=(0, 10))
        ttk.Label(cat_picker, text="Cat:").pack(side="left", padx=(0, 6))
        ttk.Combobox(
            cat_picker,
            textvariable=self.cat,
            values=tuple(CAT_BY_LABEL),
            state="readonly",
            width=18,
        ).pack(side="left")
        self.cat.trace_add(
            "write", lambda *_args: self.render(self.pose_text.get())
        )

        self.image_label = tk.Label(self.root, background="#ffe4d8")
        self.image_label.grid(row=3, column=0, padx=18, pady=8)

        controls = ttk.Frame(self.root)
        controls.grid(row=4, column=0, padx=16, pady=(8, 4))
        for index, (label, pose) in enumerate(
            (
                ("Idle", "idle"),
                ("Left paw", "tap-left"),
                ("Right paw", "tap-right"),
                ("Excited", "excited"),
            )
        ):
            ttk.Button(
                controls,
                text=label,
                command=lambda selected=pose: self.show_pose(selected),
            ).grid(row=0, column=index, padx=3)

        sizes = ttk.Frame(self.root)
        sizes.grid(row=5, column=0, pady=(6, 4))
        ttk.Label(sizes, text="Size:").pack(side="left", padx=(0, 6))
        for percent in (60, 100, 175):
            ttk.Radiobutton(
                sizes,
                text=f"{percent}%",
                value=percent,
                variable=self.size_percent,
                command=lambda: self.render(self.pose_text.get()),
            ).pack(side="left", padx=4)
        ttk.Label(self.root, textvariable=self.pose_text).grid(
            row=6, column=0, pady=(2, 14)
        )

        self.root.bind("<KeyPress>", self.on_key)
        self.render("idle")
        self.root.focus_force()

    def render(self, pose: str) -> None:
        size = round(BASE_SIZE * self.size_percent.get() / 100)
        variant = CAT_BY_LABEL[self.cat.get()]
        self.image = ImageTk.PhotoImage(
            load_frame(ASSETS_ROOT, variant, pose, size), master=self.root
        )
        self.image_label.configure(image=self.image, width=size, height=size)
        self.pose_text.set(pose)

    def show_pose(self, pose: str) -> None:
        if self._idle_after is not None:
            self.root.after_cancel(self._idle_after)
            self._idle_after = None
        self.state = AnimationState()
        now = time.monotonic()
        if pose == "idle":
            self.state.show_startup(now - 0.2)
        else:
            paw = {
                "tap-left": "left",
                "tap-right": "right",
                "excited": "both",
            }[pose]
            self.state.record_key(now, paw)
        self.render(pose)

    def on_key(self, event: object) -> None:
        now = time.monotonic()
        self.state.record_key(now, classify_tk_key(event))
        self.render(self.state.frame_name(now))
        if self._idle_after is not None:
            self.root.after_cancel(self._idle_after)
        self._idle_after = self.root.after(180, self._show_idle)

    def _show_idle(self) -> None:
        self._idle_after = None
        self.render("idle")

    def run(self) -> None:
        self.root.mainloop()


def run_preview() -> None:
    PreviewWindow().run()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--export-dir",
        type=Path,
        help="export every posed SVG and preview.png, then exit",
    )
    args = parser.parse_args()
    if args.export_dir is not None:
        export_preview(args.export_dir)
        print(f"Exported SVG poses and preview.png to {args.export_dir.resolve()}")
        return
    run_preview()


if __name__ == "__main__":
    main()
