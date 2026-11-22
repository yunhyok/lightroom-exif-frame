"""Historical brand & era CI logo resolution and pure-vector SVG rasterization."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

import resvg_py


@dataclass(frozen=True)
class EraInfo:
    id: str
    label: str
    label_ko: str
    start_year: int
    end_year: int | None
    svg: str
    accent_color: str


@dataclass(frozen=True)
class BrandInfo:
    id: str
    name: str
    category: str
    aliases: tuple[str, ...]
    eras: tuple[EraInfo, ...]


@dataclass(frozen=True)
class LogoResolution:
    brand_id: str
    brand_name: str
    era_id: str
    era_label: str
    era_label_ko: str
    detected_year: int | None
    year_source: str
    logo_source: str
    svg_path: Path | None
    user_logo_path: Path | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "brand_id": self.brand_id,
            "brand_name": self.brand_name,
            "era_id": self.era_id,
            "era_label": self.era_label,
            "era_label_ko": self.era_label_ko,
            "detected_year": self.detected_year,
            "year_source": self.year_source,
            "logo_source": self.logo_source,
        }


def _locate_dir(relative: str) -> Path:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / relative)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / relative)
    here = Path(__file__).resolve().parent
    candidates.append(here / relative)
    candidates.append(here.parent / "helper" / relative)
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(f"Required logo resource directory missing: {relative}")


def _norm_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).upper()


def _norm_compact(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (text or "").upper())


def _is_dark_hex(color: str | None) -> bool | None:
    if not color or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        return None
    r, g, b = (int(color[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return lum < 0.45


def _lift_dark_brand_hex(hex_color: str) -> str:
    """Ensure deep corporate brand blues/greens stay readable on dark #171717 frames."""
    srgb = [int(hex_color[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    lum = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    if lum >= 0.16:
        return hex_color
    import colorsys
    h, l, s = colorsys.rgb_to_hls(*srgb)
    l = max(l, 0.58)
    s = max(s, 0.72) if s > 0.05 else s
    nr, ng, nb = colorsys.hls_to_rgb(h, l, s)
    return f"#{round(nr * 255):02X}{round(ng * 255):02X}{round(nb * 255):02X}"


@lru_cache(maxsize=1)
def _load_db() -> tuple[dict[str, BrandInfo], dict[str, tuple[str, int, str | None]], dict[str, tuple[str, int, str | None]], list[tuple[str, str]]]:
    data_dir = _locate_dir("data")
    brands_raw = json.loads((data_dir / "brands.json").read_text(encoding="utf-8"))
    cameras_raw = json.loads((data_dir / "cameras.json").read_text(encoding="utf-8"))

    brands: dict[str, BrandInfo] = {}
    alias_pairs: list[tuple[str, str]] = []
    for item in brands_raw["brands"]:
        eras = tuple(
            EraInfo(
                id=e["id"],
                label=e["label"],
                label_ko=e.get("label_ko", e["label"]),
                start_year=int(e["start_year"]),
                end_year=int(e["end_year"]) if e.get("end_year") is not None else None,
                svg=e["svg"],
                accent_color=e.get("accent_color", "#000000"),
            )
            for e in item["eras"]
        )
        aliases = tuple(_norm_space(a) for a in item.get("aliases", []))
        info = BrandInfo(
            id=item["id"],
            name=item["name"],
            category=item.get("category", "camera"),
            aliases=aliases,
            eras=eras,
        )
        brands[info.id] = info
        for alias in aliases:
            alias_pairs.append((alias, info.id))
        alias_pairs.append((_norm_space(info.name), info.id))
        alias_pairs.append((_norm_space(info.id), info.id))
    alias_pairs.sort(key=lambda pair: len(pair[0]), reverse=True)

    exact_models: dict[str, tuple[str, int, str | None]] = {}
    compact_models: dict[str, tuple[str, int, str | None]] = {}
    ambiguous_compact: set[str] = set()
    for brand_id, entries in cameras_raw.get("brands", {}).items():
        if brand_id not in brands:
            continue
        for entry in entries:
            model = entry["model"]
            year = int(entry["year"])
            era_override = entry.get("era_override")
            norm_key = f"{brand_id}::{_norm_space(model)}"
            exact_models[norm_key] = (brand_id, year, era_override)
            # Also store global fallback key when model name itself is distinct
            g_key = _norm_space(model)
            if g_key not in exact_models:
                exact_models[g_key] = (brand_id, year, era_override)
            c_key = f"{brand_id}::{_norm_compact(model)}"
            if c_key in compact_models:
                ambiguous_compact.add(c_key)
            else:
                compact_models[c_key] = (brand_id, year, era_override)
    for bad in ambiguous_compact:
        compact_models.pop(bad, None)
    return brands, exact_models, compact_models, alias_pairs


def list_brands_and_eras() -> list[dict[str, Any]]:
    """Return full brand/era catalog sorted for UI selection or diagnostics."""
    brands, *_ = _load_db()
    return [
        {
            "id": b.id,
            "name": b.name,
            "category": b.category,
            "eras": [
                {
                    "id": e.id,
                    "label": e.label,
                    "label_ko": e.label_ko,
                    "start_year": e.start_year,
                    "end_year": e.end_year,
                    "accent_color": e.accent_color,
                }
                for e in b.eras
            ],
        }
        for b in brands.values()
    ]


def resolve_brand(make: str, model: str) -> str | None:
    """Disambiguate canonical brand_id from EXIF Make and Model strings."""
    brands, exact_models, _, alias_pairs = _load_db()
    make_up = _norm_space(make)
    model_up = _norm_space(model)
    combined = f"{make_up} {model_up}".strip()

    # 1. High-priority cross-brand / co-branded disambiguations
    if "PENTAX" in model_up or ("PENTAX" in make_up and "RICOH" not in make_up):
        return "pentax"
    if ("RICOH" in make_up or "RICOH" in model_up) and "THETA" in model_up:
        return "ricoh-theta"
    if "JK IMAGING" in make_up or "PIXPRO" in model_up:
        return "kodak"
    if "ARASHI VISION" in make_up or "INSTA360" in combined:
        return "insta360"
    if "EPSON" in make_up:
        return "epson"
    if re.search(r"\bOM\s+DIGITAL\b", make_up) or re.search(r"\bOM\s+SYSTEM\b", combined):
        return "om-system"
    if "OLYMPUS" in make_up:
        return "olympus"
    if "KONICA MINOLTA" in combined:
        return "konica-minolta"
    if "MINOLTA" in make_up:
        return "minolta"
    if "SONY ERICSSON" in make_up:
        return "sony-ericsson"
    if "SONY" in make_up:
        if re.search(r"\b(?:DSLR|SLT|NEX|ILCA|ILCE|ZV|ILME)-", model_up):
            return "sony-alpha"
        return "sony"
    if "PANASONIC" in make_up:
        if re.search(r"\b(?:DMC|DC)-", model_up) or "LUMIX" in combined:
            return "lumix"
        return "panasonic"
    if "NEXUS" in model_up and any(k in make_up for k in ("LGE", "LG", "MOTOROLA", "HUAWEI")):
        return "google"
    if model_up in {"L1D-20C", "L2D-20C", "L3D-100C"} or "HASSELBLAD" in make_up:
        return "hasselblad"
    if "GOLDSTAR" in make_up or "LUCKY-GOLDSTAR" in make_up:
        return "goldstar"
    if "SAMSUNG" in make_up:
        return "samsung"
    if "POLAROID" in make_up:
        return "polaroid"
    if any(k in make_up for k in ("REDMI", "POCO", "XIAOMI")):
        return "xiaomi"
    if any(k in make_up for k in ("HMD GLOBAL", "NOKIA", "MICROSOFT MOBILE")):
        return "nokia"
    if any(k in make_up for k in ("BLACKBERRY", "RESEARCH IN MOTION")) or make_up == "RIM":
        return "blackberry"
    if any(k in make_up for k in ("LGE", "LG ELECTRONICS")) or re.search(r"\bLG\b", make_up):
        return "lg"

    # 2. Alias matching (longest alias first; short aliases enforce word boundaries)
    for alias, brand_id in alias_pairs:
        if len(alias) <= 4:
            if re.search(r"(?<![A-Z0-9])" + re.escape(alias) + r"(?![A-Z0-9])", make_up):
                return brand_id
        elif alias in make_up:
            return brand_id

    for alias, brand_id in alias_pairs:
        if len(alias) <= 4:
            if re.search(r"(?<![A-Z0-9])" + re.escape(alias) + r"(?![A-Z0-9])", model_up):
                return brand_id
        elif alias in model_up:
            return brand_id

    # 3. Direct model lookup when Make is missing or unrecognizable
    if model_up in exact_models:
        return exact_models[model_up][0]

    # 4. Fallback: match against known Samsung/Xiaomi/Nikon/Canon model prefixes
    if re.match(r"^(?:SM-|GT-|SH[WV]-)", model_up):
        return "samsung"
    if re.match(r"^IPHONE\b|^IPAD\b", model_up):
        return "apple"
    if re.match(r"^PIXEL\b|^NEXUS\b", model_up):
        return "google"
    if re.match(r"^FC\d{3,4}[A-Z]?$|^OSMO|^OT\d{3}$|^PP-101$", model_up):
        return "dji"
    if re.match(r"^HERO\s*\d", model_up):
        return "gopro"

    return None


def _algorithmic_year(brand_id: str, model_up: str) -> tuple[int | None, str | None]:
    if brand_id == "xiaomi":
        m = re.match(r"^(?:M)?(\d{2})(\d{2})[A-Z0-9]{4,6}[GCIR]?$", model_up)
        if m:
            year = 2000 + int(m.group(1))
            if 2018 <= year <= 2035:
                return year, None
    elif brand_id == "samsung":
        if re.match(r"^(?:GT-[IN]9|GT-N7|SH[WV]-)", model_up):
            return 2012, None
        if re.match(r"^SM-G90", model_up):
            return 2014, None
        s_map = {"90": 2022, "91": 2023, "92": 2024, "93": 2025, "94": 2026}
        m_s = re.match(r"^SM-S(\d{2})\d", model_up)
        if m_s and m_s.group(1) in s_map:
            return s_map[m_s.group(1)], None
        g_map = {"92": 2015, "93": 2016, "95": 2017, "96": 2018, "97": 2019, "98": 2020, "99": 2021}
        m_g = re.match(r"^SM-G(\d{2})\d", model_up)
        if m_g and m_g.group(1) in g_map:
            return g_map[m_g.group(1)], None
        if re.match(r"^SM-(?:N9[2-8]|F[79]\d{2})", model_up):
            return 2020, None
    elif brand_id == "apple":
        m = re.match(r"^IPHONE\s*(\d+)", model_up)
        if m:
            gen = int(m.group(1))
            if gen <= 5:
                return 2007 + gen, None
            return 2008 + gen, None
        if model_up in {"IPHONE", "IPHONE 3G", "IPHONE 3GS", "IPHONE 4S", "IPHONE 5C"}:
            return 2010, None
    elif brand_id == "google":
        m = re.match(r"^PIXEL\s*(\d+)", model_up)
        if m:
            return 2015 + int(m.group(1)), None
        if re.match(r"^NEXUS\s*[456]$", model_up):
            return 2013, None
        if re.match(r"^NEXUS\s*[56][XP]$", model_up):
            return 2015, None
    elif brand_id == "gopro":
        m = re.match(r"^HERO\s*(\d+)", model_up)
        if m:
            num = int(m.group(1))
            return (2012 + max(0, num - 3)), None
    return None, None


def detect_release_year(brand_id: str, model: str) -> tuple[int | None, str, str | None]:
    """Return (release_year, year_source, era_override) without using capture date."""
    _, exact_models, compact_models, _ = _load_db()
    model_up = _norm_space(model)
    if not model_up:
        return None, "unknown_latest_fallback", None

    candidates = [model_up]
    for prefix in ("CANON ", "NIKON ", "PENTAX ", "SIGMA ", "LEICA ", "RICOH ", "KODAK ", "HUAWEI ", "FUJIFILM ", "OLYMPUS "):
        if model_up.startswith(prefix):
            candidates.append(model_up[len(prefix):].strip())

    # Samsung carrier/region code prefix e.g. SM-S928B -> SM-S928
    m_sam = re.match(r"^((?:GT|SM|SHW|SHV)-[A-Z]\d{3,4})", model_up)
    if m_sam:
        candidates.append(m_sam.group(1))

    for cand in candidates:
        b_key = f"{brand_id}::{cand}"
        if b_key in exact_models:
            _, year, era_ov = exact_models[b_key]
            return year, "database", era_ov

    for cand in candidates:
        c_key = f"{brand_id}::{_norm_compact(cand)}"
        if c_key in compact_models:
            _, year, era_ov = compact_models[c_key]
            return year, "database", era_ov

    algo_year, algo_era = _algorithmic_year(brand_id, model_up)
    if algo_year is not None:
        return algo_year, "model_pattern", algo_era

    return None, "unknown_latest_fallback", None


def _pick_era(brand: BrandInfo, year: int | None, era_override: str | None) -> EraInfo:
    if era_override:
        for era in brand.eras:
            if era.id == era_override:
                return era
    if year is not None:
        for era in brand.eras:
            end_ok = era.end_year is None or year <= era.end_year
            if era.start_year <= year and end_ok:
                return era
        if year < brand.eras[0].start_year:
            return brand.eras[0]
    return brand.eras[-1]


def resolve_logo(
    make: str,
    model: str,
    *,
    logo_mode: str = "auto_era",
    logo_style: str = "brand",
    manual_brand: str = "",
    manual_era: str = "",
    user_logos: dict[str, Path] | None = None,
    is_dark: bool = False,
) -> LogoResolution:
    """Resolve the manufacturer logo SVG (or user override) and historical era."""
    del is_dark  # polarity is applied at rasterization time
    del logo_style
    if logo_mode in ("off", "none"):
        return LogoResolution("", "", "", "", "", None, "off", "none", None, None)

    brands, *_ = _load_db()
    assets_dir = _locate_dir("assets/logos")

    if logo_mode == "text_only":
        b_id = (manual_brand.lower().strip() if manual_brand and manual_brand.lower().strip() in brands else None) or resolve_brand(make, model) or ""
        b_name = brands[b_id].name if b_id in brands else make.strip()
        return LogoResolution(b_id, b_name, "", "", "", None, "text_only", "text_fallback", None, None)

    brand_id: str | None = None
    if logo_mode in ("manual", "manual_era") and manual_brand:
        brand_id = manual_brand.lower().strip()
        if brand_id not in brands:
            brand_id = resolve_brand(manual_brand, model)
    if not brand_id:
        brand_id = resolve_brand(make, model)

    if not brand_id or brand_id not in brands:
        return LogoResolution("", make.strip(), "", "", "", None, "unmapped", "text_fallback", None, None)

    brand = brands[brand_id]
    user_logos_norm = {k.lower().strip(): v for k, v in (user_logos or {}).items() if v}
    user_path = user_logos_norm.get(brand_id)
    if not user_path and brand_id == "panasonic":
        user_path = user_logos_norm.get("lumix")
    elif not user_path and brand_id == "lumix":
        user_path = user_logos_norm.get("panasonic")
    elif not user_path and brand_id == "sony-alpha":
        user_path = user_logos_norm.get("sony")

    if logo_mode in ("manual", "manual_era") and manual_era and manual_era not in ("auto", "latest"):
        chosen = _pick_era(brand, None, manual_era)
        year, year_source = None, "manual_era"
    elif logo_mode == "auto_latest" or (logo_mode in ("manual", "manual_era") and manual_era == "latest"):
        chosen = brand.eras[-1]
        year, year_source = None, "latest_policy"
    else:
        year, year_source, era_override = detect_release_year(brand_id, model)
        chosen = _pick_era(brand, year, era_override)

    svg_path = assets_dir / chosen.svg
    if not svg_path.is_file():
        svg_path = None

    if user_path and Path(user_path).is_file():
        logo_source = "user_override"
    elif svg_path is not None:
        logo_source = "builtin_svg"
    else:
        logo_source = "text_fallback"

    return LogoResolution(
        brand_id=brand.id,
        brand_name=brand.name,
        era_id=chosen.id,
        era_label=chosen.label,
        era_label_ko=chosen.label_ko,
        detected_year=year,
        year_source=year_source,
        logo_source=logo_source,
        svg_path=svg_path,
        user_logo_path=Path(user_path) if user_path else None,
    )


def _transform_svg_colors(
    svg_text: str,
    *,
    is_dark: bool,
    style: str,
    text_color: str | None = None,
    background_color: str | None = None,
    secondary_color: str | None = None,
) -> str:
    dark = _is_dark_hex(background_color)
    if dark is None:
        dark = is_dark
    ink = text_color if (text_color and re.fullmatch(r"#[0-9a-fA-F]{6}", text_color)) else ("#F2F2F2" if dark else "#141414")
    ink_muted = secondary_color if (secondary_color and re.fullmatch(r"#[0-9a-fA-F]{6}", secondary_color)) else ("#BDBDBD" if dark else "#555555")
    bg = background_color if (background_color and re.fullmatch(r"#[0-9a-fA-F]{6}", background_color)) else ("#171717" if dark else "#FFFFFF")

    if style == "mono":
        contrast = bg
        badge_fg = contrast
        badge_dark = contrast
        kodak_k = contrast
        # Map distinct explicit hex brand colors to graded ink tones so multi-stripe marks stay legible
        seen_hex: dict[str, str] = {}
        opacities = ("1.0", "0.78", "0.60", "0.45", "0.88", "0.68")

        def mono_sub(match: re.Match[str]) -> str:
            attr, val = match.group(1), match.group(2).upper()
            if val in ("#FFFFFF", "#FFF"):
                return f'{attr}="{contrast}"'
            if val not in seen_hex:
                seen_hex[val] = opacities[len(seen_hex) % len(opacities)]
            op = seen_hex[val]
            op_attr = f' {attr}-opacity="{op}"' if op != "1.0" and attr in ("fill", "stroke") else ""
            return f'{attr}="{ink}"{op_attr}'

        transformed = re.sub(r'(fill|stroke|stop-color)="(#[0-9a-fA-F]{3,6})"', mono_sub, svg_text)
    else:
        contrast = "#FFFFFF" if not dark else bg
        badge_fg = "#FFFFFF"
        badge_dark = "#141414"
        kodak_k = "#ED0000"
        if dark:
            def dark_lift(match: re.Match[str]) -> str:
                attr, val = match.group(1), match.group(2)
                if len(val) == 7:
                    return f'{attr}="{_lift_dark_brand_hex(val)}"'
                return match.group(0)
            transformed = re.sub(r'(fill|stroke|stop-color)="(#[0-9a-fA-F]{6})"', dark_lift, svg_text)
        else:
            transformed = svg_text

    return (
        transformed
        .replace("{{INK}}", ink)
        .replace("{{INK_MUTED}}", ink_muted)
        .replace("{{CONTRAST}}", contrast)
        .replace("{{BADGE_FG}}", badge_fg)
        .replace("{{BADGE_DARK}}", badge_dark)
        .replace("{{KODAK_K}}", kodak_k)
    )


def _svg_dimensions(svg_text: str) -> tuple[float, float]:
    vb = re.search(r'viewBox="[^"]*?\s([0-9.]+)\s+([0-9.]+)"', svg_text)
    if vb:
        return max(1.0, float(vb.group(1))), max(1.0, float(vb.group(2)))
    wm = re.search(r'width="([0-9.]+)"', svg_text)
    hm = re.search(r'height="([0-9.]+)"', svg_text)
    if wm and hm:
        return max(1.0, float(wm.group(1))), max(1.0, float(hm.group(1)))
    return 400.0, 160.0


def rasterize_svg_to_png(
    svg_path: Path,
    box_width: int,
    box_height: int,
    *,
    is_dark: bool = False,
    style: str = "brand",
    text_color: str | None = None,
    background_color: str | None = None,
    secondary_color: str | None = None,
    output_path: Path | None = None,
) -> bytes:
    """Rasterize a pure-vector SVG logo to crisp RGBA PNG bytes sized to fit (box_width, box_height)."""
    raw_svg = Path(svg_path).read_text(encoding="utf-8")
    svg_styled = _transform_svg_colors(
        raw_svg,
        is_dark=is_dark,
        style=style,
        text_color=text_color,
        background_color=background_color,
        secondary_color=secondary_color,
    )
    vw, vh = _svg_dimensions(svg_styled)
    scale = min(max(1, box_width) / vw, max(1, box_height) / vh)
    target_w = max(1, round(vw * scale))
    target_h = max(1, round(vh * scale))
    # Rasterize cleanly at exact target dimensions (no system fonts needed for built-in pure-vector SVGs;
    # keep skip_system_fonts=False only if user SVG actually contains <text>).
    has_text = "<text" in svg_styled.lower()
    png_bytes = bytes(
        resvg_py.svg_to_bytes(
            svg_string=svg_styled,
            width=target_w,
            height=target_h,
            skip_system_fonts=not has_text,
        )
    )
    if output_path is not None:
        output_path.write_bytes(png_bytes)
    return png_bytes
