"""Render contact sheets of all 93 brand-era SVG logos in Light/Dark x Brand/Mono."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "helper"))
import logos


def main() -> None:
    magick = Path(os.environ.get("EXIF_FRAME_MAGICK", ROOT / "vendor/imagemagick/magick.exe"))
    if not magick.is_file():
        raise FileNotFoundError(f"magick.exe not found: {magick}")
    out_dir = ROOT / "build" / "verify"
    out_dir.mkdir(parents=True, exist_ok=True)
    catalog = logos.list_brands_and_eras()
    assets_dir = logos._locate_dir("assets/logos")

    entries: list[tuple[str, Path]] = []
    for b in catalog:
        for e in b["eras"]:
            svg_rel = f"{b['id']}/{e['id']}.svg"
            entries.append((f"{b['id']}/{e['id']}", assets_dir / svg_rel))

    cols = 6
    cell_w, cell_h = 280, 110
    pad = 12
    label_h = 22
    rows = (len(entries) + cols - 1) // cols
    canvas_w = cols * cell_w + (cols + 1) * pad
    canvas_h = rows * cell_h + (rows + 1) * pad

    configs = [
        ("brand", False, "#FFFFFF", "#141414", "#666666", "logo-sheet-brand-light.png"),
        ("brand", True, "#171717", "#F2F2F2", "#AAAAAA", "logo-sheet-brand-dark.png"),
        ("mono", False, "#FFFFFF", "#141414", "#666666", "logo-sheet-mono-light.png"),
        ("mono", True, "#171717", "#F2F2F2", "#AAAAAA", "logo-sheet-mono-dark.png"),
    ]

    font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/segoeui.ttf"
    if not font.is_file():
        font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/malgun.ttf"

    # Build in 2 halves per mode if command-line size matters; actually write an ImageMagick script file!
    for style, is_dark, bg, fg, muted, filename in configs:
        with tempfile.TemporaryDirectory(prefix="logo-sheet-") as tmp:
            work = Path(tmp)
            script_lines = [f'-size {canvas_w}x{canvas_h} "xc:{bg}"']
            for idx, (label, svg_path) in enumerate(entries):
                r = idx // cols
                c = idx % cols
                cx = pad + c * (cell_w + pad)
                cy = pad + r * (cell_h + pad)
                png_path = work / f"cell_{idx}.png"
                logos.rasterize_svg_to_png(
                    svg_path,
                    cell_w - 20,
                    cell_h - label_h - 14,
                    is_dark=is_dark,
                    style=style,
                    text_color=fg,
                    background_color=bg,
                    secondary_color=muted,
                    output_path=png_path,
                )
                border_c = "#D8DCE2" if not is_dark else "#2E333B"
                script_lines.append(f'-fill none -stroke "{border_c}" -strokewidth 1 -draw "rectangle {cx},{cy} {cx + cell_w - 1},{cy + cell_h - 1}"')
                script_lines.append(
                    f'( "{png_path.as_posix()}" ) -gravity NorthWest -geometry +{cx + 10}+{cy + 6} -compose Over -composite'
                )
                script_lines.append(
                    f'-gravity NorthWest -stroke none -fill "{muted}" -font "{font.as_posix()}" -pointsize 13 '
                    f'-annotate +{cx + 8}+{cy + cell_h - label_h + 2} "{label}"'
                )
            dest = out_dir / filename
            script_lines.append(f'-write "{dest.as_posix()}"')
            script_file = work / "sheet.mgk"
            script_file.write_text("\n".join(script_lines), encoding="utf-8")
            subprocess.run([str(magick), "-script", str(script_file)], check=True, capture_output=True)
            print(f"Wrote {dest}")


if __name__ == "__main__":
    main()
