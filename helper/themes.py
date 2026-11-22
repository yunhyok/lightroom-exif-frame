"""16 EXIF frame themes, aspect-ratio canvas layout, and ImageMagick layer composer."""
from __future__ import annotations

import math
from pathlib import Path
import re
from typing import Any, Callable

import logos

THEMES = {
    "strap",
    "simple",
    "one_line",
    "two_line",
    "shot_on_one_line",
    "shot_on_two_line",
    "film",
    "monitor",
    "lightroom",
    "just_frame",
    "cinemascope",
    "custom_one_line",
    "custom_two_line",
    "poster",
    "tip",
    "none",
}

ASPECT_RATIOS = {"free", "1:1", "4:5", "5:4", "3:4", "4:3", "2:3", "3:2", "16:9", "9:16"}


def _is_dark_hex(color: str) -> bool:
    r, g, b = (int(color[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) < 0.45


def resolve_theme_colors(job: dict[str, Any]) -> tuple[str, str, str, bool]:
    """Return (background_color, text_color, secondary_color, is_dark)."""
    app = job.get("appearance", "light")
    theme = job.get("theme", "strap")

    if app == "custom":
        bg = job["background_color"]
        fg = job["text_color"]
        sec = job["secondary_color"]
        return bg, fg, sec, _is_dark_hex(bg)
    if app == "dark":
        return "#171717", "#f4f4f4", "#bbbbbb", True
    if app == "auto":
        if theme == "monitor":
            return "#0a0a0a", "#f4f4f4", "#a8a8a8", True
        if theme == "lightroom":
            return "#1f1f1f", "#f2f2f2", "#b0b0b0", True
        if theme == "cinemascope":
            return "#000000", "#f2f2f2", "#999999", True
        if theme == "film":
            return "#000000", "#FFA500", "#FFD080", True
        if theme in ("poster", "tip"):
            return "#000000", "#ffffff", "#d8d8d8", True
        return "#ffffff", "#161616", "#555555", False

    # Explicit "light" (preserves exact v0.1.0 color defaults)
    if theme == "cinemascope":
        return "#000000", "#f2f2f2", "#999999", True
    return "#ffffff", "#161616", "#555555", False


def _alpha_hex(color: str, alpha: float) -> str:
    if alpha >= 0.999:
        return color
    a = max(0, min(255, round(alpha * 255)))
    return f"{color}{a:02x}"


def prepare_body_transform(
    body_w: int,
    body_h: int,
    aspect_ratio: str,
    no_crop: bool,
    theme: str,
) -> tuple[int, int, str | None, bool]:
    """Return (effective_body_w, effective_body_h, crop_spec, pad_to_ratio)."""
    if theme == "cinemascope":
        target_ratio = 2.35
        current = body_w / body_h
        if current >= target_ratio:
            return body_w, max(1, round(body_w / target_ratio)), None, False
        eff_h = max(1, round(body_w / target_ratio))
        off_y = max(0, (body_h - eff_h) // 2)
        return body_w, eff_h, f"{body_w}x{eff_h}+0+{off_y}", False

    if aspect_ratio == "free":
        return body_w, body_h, None, False

    rw, rh = map(int, aspect_ratio.split(":"))
    target = rw / rh
    current = body_w / body_h
    if abs(current - target) < 1e-4:
        return body_w, body_h, None, False

    if no_crop:
        if current > target:
            eff_w = body_w
            eff_h = max(1, round(body_w / target))
        else:
            eff_h = body_h
            eff_w = max(1, round(body_h * target))
        return eff_w, eff_h, None, True

    if current > target:
        eff_w = max(1, round(body_h * target))
        eff_h = body_h
        off_x = max(0, (body_w - eff_w) // 2)
        return eff_w, eff_h, f"{eff_w}x{eff_h}+{off_x}+0", False
    eff_w = body_w
    eff_h = max(1, round(body_w / target))
    off_y = max(0, (body_h - eff_h) // 2)
    return eff_w, eff_h, f"{eff_w}x{eff_h}+0+{off_y}", False


def compute_canvas_geometry(
    job: dict[str, Any],
    eff_w: int,
    eff_h: int,
) -> tuple[int, int, int, int, int, int]:
    """Return (canvas_w, canvas_h, offset_x, offset_y, band, padding)."""
    theme = job["theme"]
    if theme == "none":
        return eff_w, eff_h, 0, 0, 0, 0
    if theme == "cinemascope":
        canvas_h = max(eff_h + 2, round(eff_h * 1.311875))
        bar = (canvas_h - eff_h) // 2
        return eff_w, canvas_h, 0, bar, bar, 0

    band = max(1, round(eff_w * job["band_percent"] / 100))
    padding = max(0, round(eff_w * job["padding_percent"] / 100))
    inside = bool(job.get("padding_inside", False))

    if theme in ("film", "poster", "tip"):
        return eff_w, eff_h, 0, 0, band, padding
    if theme == "just_frame":
        return eff_w + 2 * padding, eff_h + 2 * padding, padding, padding, 0, padding
    if theme in ("strap", "shot_on_one_line", "lightroom"):
        return eff_w, eff_h + band, 0, 0, band, padding
    if theme == "monitor":
        if inside:
            return eff_w, eff_h, 0, 0, band, padding
        return eff_w, eff_h + band, 0, 0, band, padding
    # simple, one_line, two_line, shot_on_two_line, custom_one_line, custom_two_line
    if inside and theme != "simple":
        return eff_w, eff_h, 0, 0, band, padding
    return eff_w + 2 * padding, eff_h + band + 2 * padding, padding, padding, band, padding


def compose_logo(
    *,
    job: dict[str, Any],
    resolution: logos.LogoResolution,
    box_w: int,
    box_h: int,
    is_dark: bool,
    bg_color: str,
    text_color: str,
    secondary_color: str,
    work: Path,
    profile: Path,
    srgb: Path,
    run_fn: Callable[..., Any],
    image_info_fn: Callable[..., tuple[int, int, int, str, str]],
    magick: Path,
    warnings: list[str],
) -> tuple[Path, int, int] | None:
    """Render user PNG/SVG or built-in era SVG to a 16-bit profile-matched MIFF."""
    if box_w < 1 or box_h < 1 or resolution.logo_source in ("none", "text_fallback"):
        return None

    logo_source_args: list[str] | None = None
    rendered_miff = work / "logo.miff"
    png_staged = work / "logo_svg.png"

    if resolution.logo_source == "user_override" and resolution.user_logo_path is not None:
        user_path = resolution.user_logo_path
        if not user_path.is_file() or user_path.stat().st_size > 32 * 1024 * 1024:
            raise ValueError("Logo must be an existing PNG or SVG smaller than 32 MiB")
        if user_path.suffix.lower() == ".svg":
            logos.rasterize_svg_to_png(
                user_path,
                box_w,
                box_h,
                is_dark=is_dark,
                style=job.get("logo_style", "brand"),
                text_color=text_color,
                background_color=bg_color,
                secondary_color=secondary_color,
                output_path=png_staged,
            )
            logo_source_args = ["PNG:" + str(png_staged) + "[0]", "-profile", str(srgb)]
        else:
            with user_path.open("rb") as stream:
                if stream.read(8) != b"\x89PNG\r\n\x1a\n":
                    raise ValueError("Logo must be a PNG image")
            png_src = "PNG:" + str(user_path) + "[0]"
            lw, lh, _, logo_profiles, _ = image_info_fn(magick, png_src)
            if lw > 32768 or lh > 32768 or lw * lh > 32_000_000:
                raise ValueError("Logo exceeds supported dimensions")
            logo_source_args = [png_src]
            if "icc" not in logo_profiles.lower():
                logo_source_args.extend(["-profile", str(srgb)])
                warnings.append("Untagged logo assumed sRGB")
    elif resolution.logo_source == "builtin_svg" and resolution.svg_path is not None:
        logos.rasterize_svg_to_png(
            resolution.svg_path,
            box_w,
            box_h,
            is_dark=is_dark,
            style=job.get("logo_style", "brand"),
            text_color=text_color,
            background_color=bg_color,
            secondary_color=secondary_color,
            output_path=png_staged,
        )
        logo_source_args = ["PNG:" + str(png_staged) + "[0]", "-profile", str(srgb)]

    if logo_source_args is None:
        return None

    run_fn(
        magick,
        [
            *logo_source_args,
            "-profile",
            str(profile),
            "+profile",
            "!icc,*",
            "-resize",
            f"{box_w}x{box_h}",
            "-depth",
            "16",
            str(rendered_miff),
        ],
    )
    lw, lh, *_ = image_info_fn(magick, str(rendered_miff))
    return rendered_miff, lw, lh


def build_theme_layers(
    *,
    job: dict[str, Any],
    canvas_w: int,
    canvas_h: int,
    eff_w: int,
    eff_h: int,
    offset_x: int,
    offset_y: int,
    band: int,
    padding: int,
    bg_color: str,
    text_color: str,
    secondary_color: str,
    is_dark: bool,
    texts: list[str],
    values: dict[str, str],
    brand: str,
    resolution: logos.LogoResolution,
    work: Path,
    profile: Path,
    srgb: Path,
    run_fn: Callable[..., Any],
    image_info_fn: Callable[..., tuple[int, int, int, str, str]],
    magick: Path,
    warnings: list[str],
) -> list[str]:
    """Compose all theme overlays/text/logos onto the base ImageMagick argument list."""
    args: list[str] = []
    theme = job["theme"]
    if theme in ("none", "just_frame", "cinemascope"):
        return args

    inside = bool(job.get("padding_inside", False))
    alpha = float(job.get("text_alpha", 1.0))
    shadow_size = float(job.get("shadow_size", 0.0))
    align = job.get("text_align", "center")
    font_style = job.get("font_style", "normal")
    divider = job.get("divider", "∙")
    fontsize = max(6, round(eff_w * job["font_percent"] / 100))
    vertical = min(padding, max(1, round(band * 0.16)))
    footer_y = (eff_h - band) if (inside and theme not in ("simple", "strap", "shot_on_one_line", "lightroom")) else (offset_y + eff_h)

    layer_seq = [0]

    def colored_layer(prefix: list[str], path: Path) -> None:
        run_fn(magick, [*prefix, "-profile", str(srgb), "-profile", str(profile), "+profile", "!icc,*", "-depth", "16", str(path)])

    def text_layer(
        text: str,
        slot: tuple[int, int, int, int],
        color: str,
        *,
        h_align: str = "left",
        nominal: int | None = None,
        layer_alpha: float = alpha,
        layer_shadow: float = shadow_size,
    ) -> None:
        if not text or not text.strip():
            return
        x, y, available_width, available_height = slot
        if available_width < 1 or available_height < 1:
            warnings.append(f"Text area {layer_seq[0] + 1} has no space")
            return
        idx = layer_seq[0]
        layer_seq[0] += 1
        textfile, layer = work / f"text-{idx}.utf8", work / f"text-{idx}.miff"
        textfile.write_text(text, encoding="utf-8")
        point = nominal or fontsize
        gravity = "Center" if h_align == "center" else ("NorthEast" if h_align == "right" else "NorthWest")
        fill_col = _alpha_hex(color, layer_alpha)
        for _ in range(8):
            settings = [
                "-background", "none",
                "-fill", fill_col,
                "-font", str(job["font_path"]),
                "-density", "72",
                "-pointsize", str(point),
                "-gravity", gravity,
            ]
            colored_layer([*settings, "label:@" + str(textfile)], layer)
            tw, th, *_ = image_info_fn(magick, str(layer))
            if tw > available_width:
                colored_layer([*settings, "-size", f"{available_width}x", "caption:@" + str(textfile)], layer)
                tw, th, *_ = image_info_fn(magick, str(layer))
            if tw <= available_width and th <= available_height:
                break
            smaller = max(4, min(point - 1, int(point * min(available_width / tw, available_height / th) * 0.95)))
            if smaller >= point:
                warnings.append(f"Text area {idx + 1} omitted: cannot fit without overlap")
                return
            point = smaller
        else:
            warnings.append(f"Text area {idx + 1} omitted: cannot fit without overlap")
            return

        if font_style == "italic":
            sheared = work / f"text-{idx}-it.miff"
            run_fn(magick, [str(layer), "-background", "none", "-shear", "-12x0", "+repage", str(sheared)])
            layer = sheared
            tw, th, *_ = image_info_fn(magick, str(layer))

        if layer_shadow > 0:
            shadowed = work / f"text-{idx}-sh.miff"
            sigma = max(1.0, round(layer_shadow * max(0.5, eff_w / 1920.0), 2))
            shadow_color = "#ffffff" if _is_dark_hex(color) else "#000000"
            run_fn(
                magick,
                [
                    str(layer),
                    "(",
                    "+clone",
                    "-background", shadow_color,
                    "-shadow", f"80x{sigma}+0+{max(1, round(sigma * 0.4))}",
                    ")",
                    "+swap",
                    "-background", "none",
                    "-layers", "merge",
                    "+repage",
                    "-profile", str(profile),
                    "+profile", "!icc,*",
                    "-depth", "16",
                    str(shadowed),
                ],
            )
            layer = shadowed
            tw, th, *_ = image_info_fn(magick, str(layer))

        draw_x = x
        if h_align == "center":
            draw_x += max(0, (available_width - tw) // 2)
        elif h_align == "right":
            draw_x += max(0, available_width - tw)
        draw_y = y + max(0, (available_height - th) // 2)
        args.extend(["(", str(layer), ")", "-compose", "Over", "-gravity", "NorthWest", "-geometry", f"+{draw_x}+{draw_y}", "-composite"])

    def composite_logo(slot_x: int, slot_y: int, slot_w: int, slot_h: int, h_align: str = "center") -> int:
        res = compose_logo(
            job=job,
            resolution=resolution,
            box_w=slot_w,
            box_h=slot_h,
            is_dark=is_dark,
            bg_color=bg_color,
            text_color=text_color,
            secondary_color=secondary_color,
            work=work,
            profile=profile,
            srgb=srgb,
            run_fn=run_fn,
            image_info_fn=image_info_fn,
            magick=magick,
            warnings=warnings,
        )
        if res is not None:
            miff_path, lw, lh = res
            lx = slot_x + (slot_w - lw) // 2 if h_align == "center" else (slot_x + slot_w - lw if h_align == "right" else slot_x)
            ly = slot_y + (slot_h - lh) // 2
            args.extend(["(", str(miff_path), ")", "-compose", "Over", "-gravity", "NorthWest", "-geometry", f"+{lx}+{ly}", "-composite"])
            return lw
        if resolution.logo_source == "text_fallback" and brand:
            brand_font = max(fontsize, min(round(band * 0.6), round(eff_w * job["logo_percent"] / 100 * 0.3)))
            text_layer(brand, (slot_x, slot_y, slot_w, slot_h), text_color, h_align=h_align, nominal=brand_font)
        return 0

    def exposure_line(sep: str = "  ") -> str:
        items = []
        if values.get("iso"):
            items.append(f"ISO{values['iso']}")
        if values.get("focal") and values["focal"] != "—":
            items.append(f"{values['focal']}mm")
        if values.get("aperture"):
            items.append(f"F{values['aperture']}")
        if values.get("shutter"):
            items.append(f"{values['shutter']}s")
        return sep.join(items)

    def camera_line(sep: str = " ") -> str:
        items = [values.get("make", ""), values.get("model", ""), values.get("lens", "")]
        return sep.join(i for i in items if i)

    # --- Theme layouts ---
    if theme == "strap":
        gap, line_width = max(1, round(eff_w * 0.015)), max(1, round(eff_w / 1920))
        usable = max(1, canvas_w - 2 * padding)
        right_width = max(1, round(usable * 0.43))
        desired_logo = max(1, round(eff_w * job["logo_percent"] / 100))
        logo_width = max(1, min(desired_logo, usable - right_width - 3 * gap - line_width - max(1, round(usable * 0.15))))
        if logo_width < desired_logo:
            warnings.append("Logo area reduced to retain space for metadata")
        left_width = max(1, usable - right_width - logo_width - 3 * gap - line_width)
        logo_x = padding + left_width + gap
        separator = logo_x + logo_width + gap
        right_edge = separator + line_width + gap
        row = max(1, (band - 2 * vertical) // 2)
        for index, text in enumerate(texts):
            x = padding if index < 2 else right_edge
            slotwidth = left_width if index < 2 else canvas_w - padding - right_edge
            text_layer(text, (x, footer_y + vertical + (index % 2) * row, slotwidth, row),
                       text_color if index % 2 == 0 else secondary_color, h_align="left")
        line = work / "separator.miff"
        colored_layer(["-size", f"{line_width}x{max(1, band - 2 * vertical)}", "xc:" + secondary_color], line)
        args.extend(["(", str(line), ")", "-compose", "Over", "-gravity", "NorthWest", "-geometry", f"+{separator}+{footer_y + vertical}", "-composite"])
        composite_logo(logo_x, footer_y + vertical, logo_width, max(1, band - 2 * vertical), h_align="center")

    elif theme == "simple":
        joined = "\n".join(t for t in texts if t.strip())
        if values.get("label"):
            joined = (joined + "\n" + values["label"]).strip()
        text_layer(joined, (padding, footer_y + vertical, canvas_w - 2 * padding, max(1, band - 2 * vertical)),
                   text_color, h_align="center")

    elif theme in ("one_line", "custom_one_line"):
        if values.get("label") and offset_y > 0:
            text_layer(values["label"], (padding, 2, canvas_w - 2 * padding, max(1, offset_y - 4)),
                       secondary_color, h_align="center", nominal=max(5, round(fontsize * 0.8)))
        if theme == "one_line":
            parts = [t.strip() for t in texts if t.strip()]
            line_text = f" {divider} ".join(parts) if parts else f" {divider} ".join(x for x in (camera_line(), exposure_line(f" {divider} ")) if x)
        else:
            line_text = texts[0].strip() or values.get("label", "")
        text_layer(line_text, (max(padding, 8), footer_y + vertical, max(1, canvas_w - 2 * max(padding, 8)), max(1, band - 2 * vertical)),
                   text_color, h_align=align, layer_shadow=max(shadow_size, 8.0) if inside else shadow_size)

    elif theme in ("two_line", "custom_two_line"):
        if values.get("label") and offset_y > 0:
            text_layer(values["label"], (padding, 2, canvas_w - 2 * padding, max(1, offset_y - 4)),
                       secondary_color, h_align="center", nominal=max(5, round(fontsize * 0.8)))
        if theme == "two_line":
            line1 = f" {divider} ".join(t.strip() for t in (texts[2], texts[3]) if t.strip()) or camera_line()
            line2 = f" {divider} ".join(t.strip() for t in (texts[0], texts[1]) if t.strip()) or exposure_line(f" {divider} ")
        else:
            line1, line2 = texts[0].strip(), texts[1].strip()
        row = max(1, (band - 2 * vertical) // 2)
        h_pad = max(padding, 8)
        sh = max(shadow_size, 8.0) if inside else shadow_size
        text_layer(line1, (h_pad, footer_y + vertical, max(1, canvas_w - 2 * h_pad), row), text_color, h_align=align, layer_shadow=sh)
        text_layer(line2, (h_pad, footer_y + vertical + row, max(1, canvas_w - 2 * h_pad), row), secondary_color, h_align=align, nominal=max(5, round(fontsize * 0.85)), layer_shadow=sh)

    elif theme == "shot_on_one_line":
        h_pad = max(padding, max(8, round(eff_w * 0.02)))
        usable = max(1, canvas_w - 2 * h_pad)
        box_h = max(1, band - 2 * vertical)
        logo_box_w = min(max(1, round(eff_w * job["logo_percent"] / 100 * 0.85)), max(1, round(usable * 0.16)))
        lw = composite_logo(h_pad, footer_y + vertical, logo_box_w, box_h, h_align="left")
        left_x = h_pad + (lw + max(8, round(eff_w * 0.012)) if lw > 0 else 0)
        right_w = max(1, round(usable * 0.38))
        left_w = max(1, canvas_w - h_pad - right_w - left_x - 8)
        cam_txt = f"Shot on {camera_line()}" if camera_line() else "Shot on"
        exp_txt = exposure_line("  ")
        text_layer(cam_txt, (left_x, footer_y + vertical, left_w, box_h), text_color, h_align="left")
        text_layer(exp_txt, (canvas_w - h_pad - right_w, footer_y + vertical, right_w, box_h), secondary_color, h_align="right")

    elif theme == "shot_on_two_line":
        if values.get("label") and offset_y > 0:
            text_layer(values["label"], (padding, 2, canvas_w - 2 * padding, max(1, offset_y - 4)),
                       secondary_color, h_align="center", nominal=max(5, round(fontsize * 0.8)))
        h_pad = max(padding, 8)
        row = max(1, (band - 2 * vertical) // 2)
        make_model = " ".join(x for x in (values.get("make", ""), values.get("model", "")) if x)
        line1 = f"shot on {make_model}".strip()
        line2 = exposure_line("   ")
        text_layer(line1, (h_pad, footer_y + vertical, max(1, canvas_w - 2 * h_pad), row), text_color, h_align="center")
        text_layer(line2, (h_pad, footer_y + vertical + row, max(1, canvas_w - 2 * h_pad), row), secondary_color, h_align="center", nominal=max(5, round(fontsize * 0.82)))

    elif theme == "film":
        # Retro camera data-back stamp in bottom corners of photo
        margin = max(12, round(eff_w * 0.03))
        stamp_h = max(24, round(eff_h * 0.18))
        stamp_y = eff_h - margin - stamp_h
        row = max(8, stamp_h // 3)
        half_w = max(1, (eff_w - 2 * margin) // 2 - 8)
        sh = max(shadow_size, 8.0)
        l1 = values.get("artist") or values.get("date")
        l2 = " ".join(x for x in (values.get("make", ""), values.get("model", "")) if x)
        l3 = values.get("lens", "")
        text_layer(l1, (margin, stamp_y, half_w, row), text_color, h_align="left", nominal=max(5, round(fontsize * 0.82)), layer_shadow=sh)
        text_layer(l2, (margin, stamp_y + row, half_w, row), text_color, h_align="left", nominal=fontsize, layer_shadow=sh)
        text_layer(l3, (margin, stamp_y + 2 * row, half_w, row), text_color, h_align="left", nominal=max(5, round(fontsize * 0.88)), layer_shadow=sh)
        r_lines = [
            f"ISO {values['iso']}" if values.get("iso") else "",
            f"{values['shutter']} s" if values.get("shutter") else "",
            f"F {values['aperture']}" if values.get("aperture") else "",
        ]
        for ri, r_txt in enumerate(r_lines):
            text_layer(r_txt, (eff_w - margin - half_w, stamp_y + ri * row, half_w, row), text_color, h_align="right", nominal=round(fontsize * 1.1), layer_shadow=sh)

    elif theme == "monitor":
        if inside:
            bar = work / "monitor-bar.miff"
            colored_layer(["-size", f"{canvas_w}x{band}", "xc:" + bg_color], bar)
            args.extend(["(", str(bar), ")", "-compose", "Over", "-gravity", "NorthWest", "-geometry", f"+0+{eff_h - band}", "-composite"])
        cols = [
            f"F{values['aperture']}" if values.get("aperture") else "",
            f"{values['shutter']}s" if values.get("shutter") else "",
            f"ISO{values['iso']}" if values.get("iso") else "",
            f"{values['focal']}mm" if values.get("focal") and values["focal"] != "—" else "",
        ]
        target_w = (canvas_w // 2) if job.get("compact") else canvas_w
        start_x = (canvas_w - target_w) // 2
        col_w = max(1, target_w // 4)
        for ci, txt in enumerate(cols):
            text_layer(txt, (start_x + ci * col_w, footer_y + vertical, col_w, max(1, band - 2 * vertical)), text_color, h_align="center")

    elif theme == "lightroom":
        h_pad = max(padding, max(12, round(eff_w * 0.025)))
        usable = max(1, canvas_w - 2 * h_pad)
        box_h = max(1, band - 2 * vertical)
        w_left = max(1, round(usable * 0.30))
        w_right = max(1, round(usable * 0.24))
        w_mid = max(1, usable - w_left - w_right - 16)
        text_layer(exposure_line("   "), (h_pad, footer_y + vertical, w_left, box_h), text_color, h_align="left")
        text_layer(camera_line("   "), (h_pad + w_left + 8, footer_y + vertical, w_mid, box_h), secondary_color, h_align="center")
        text_layer(values.get("date", ""), (canvas_w - h_pad - w_right, footer_y + vertical, w_right, box_h), secondary_color, h_align="right")

    elif theme == "poster":
        margin = max(14, round(eff_w * 0.04))
        sh = max(shadow_size, 12.0)
        top_y = max(12, round(eff_h * 0.06))
        top_w = max(1, eff_w - 2 * margin)
        t1 = texts[0] if texts[0].strip() else values.get("date", "")
        t2 = texts[1] if texts[1].strip() else (camera_line() or "EXIF FRAME")
        t3 = texts[2] if texts[2].strip() else exposure_line("  ")
        t4 = texts[3] if texts[3].strip() else (values.get("artist") or values.get("label", ""))
        text_layer(t1, (margin, top_y, top_w, max(10, round(fontsize * 1.4))), secondary_color, h_align="left", nominal=fontsize, layer_shadow=sh)
        text_layer(t2, (margin, top_y + round(fontsize * 1.7), top_w, max(12, round(fontsize * 2.6))), text_color, h_align="left", nominal=round(fontsize * 2.0), layer_shadow=sh)
        text_layer(t3, (margin, top_y + round(fontsize * 4.4), top_w, max(10, round(fontsize * 1.6))), text_color, h_align="left", nominal=round(fontsize * 1.15), layer_shadow=sh)
        bot_y = eff_h - margin - max(16, round(fontsize * 2.2))
        text_layer(t4, (margin, bot_y, max(1, round(top_w * 0.65)), max(12, round(fontsize * 1.8))), text_color, h_align="left", nominal=round(fontsize * 1.15), layer_shadow=sh)
        composite_logo(eff_w - margin - max(20, round(eff_w * job["logo_percent"] / 100)), bot_y,
                       max(20, round(eff_w * job["logo_percent"] / 100)), max(16, round(fontsize * 2.0)), h_align="right")

    elif theme == "tip":
        margin = max(14, round(eff_w * 0.04))
        sh = max(shadow_size, 12.0)
        top_w = max(1, eff_w - 2 * margin)
        tag = values.get("label") or texts[2] or "TIP"
        title = texts[3] or camera_line()
        desc = texts[1] or values.get("date", "")
        text_layer(tag, (margin, max(10, round(eff_h * 0.06)), top_w, max(12, round(fontsize * 2.0))), text_color, h_align="center", nominal=round(fontsize * 1.5), layer_shadow=sh)
        text_layer(title, (margin, max(16, round(eff_h * 0.06)) + round(fontsize * 2.2), top_w, max(12, round(fontsize * 1.8))), text_color, h_align="center", nominal=round(fontsize * 1.2), layer_shadow=sh)
        bot_y = eff_h - margin - max(18, round(fontsize * 3.0))
        text_layer(desc, (margin, bot_y, top_w, max(10, round(fontsize * 1.4))), secondary_color, h_align="center", nominal=fontsize, layer_shadow=sh)
        cols = [
            f"F{values['aperture']}" if values.get("aperture") else "",
            f"{values['shutter']}s" if values.get("shutter") else "",
            f"ISO{values['iso']}" if values.get("iso") else "",
            f"{values['focal']}mm" if values.get("focal") and values["focal"] != "—" else "",
        ]
        target_w = max(1, eff_w // 2)
        start_x = (eff_w - target_w) // 2
        col_w = max(1, target_w // 4)
        for ci, txt in enumerate(cols):
            text_layer(txt, (start_x + ci * col_w, eff_h - margin - round(fontsize * 1.4), col_w, max(10, round(fontsize * 1.3))), text_color, h_align="center", nominal=max(5, round(fontsize * 0.9)), layer_shadow=sh)

    return args
