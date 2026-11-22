"""Metadata display formatting, date notations, focal modes, and token expansion."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from typing import Any

import logos
import metadata

FIELDS = {"make", "model", "lens", "iso", "aperture", "shutter", "focal", "focal35", "date", "artist"}

DATE_NOTATIONS = {
    "slash_datetime",
    "dash_datetime",
    "ko_datetime",
    "ja_datetime",
    "slash_date",
    "dash_date",
    "ko_date",
    "ja_date",
    "en_date",
    "none",
}

_MONTH_ABBR = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_EXIF_DT_RE = re.compile(
    r"^(\d{4})[:\-/](\d{2})[:\-/](\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?"
)


def format_date(raw_date: str, notation: str = "slash_datetime") -> str:
    text = (raw_date or "").strip()
    if not text or notation == "none":
        return ""
    m = _EXIF_DT_RE.match(text)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hh = int(m.group(4) or 0)
        mm = int(m.group(5) or 0)
        ss = int(m.group(6) or 0)
        has_time = m.group(4) is not None
    else:
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            year, month, day, hh, mm, ss = dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second
            has_time = True
        except ValueError:
            return re.sub(r"^(\d{4}):(\d{2}):(\d{2})", r"\1/\2/\3", text)

    if not 1 <= month <= 12:
        return re.sub(r"^(\d{4}):(\d{2}):(\d{2})", r"\1/\2/\3", text)

    hms = f"{hh:02d}:{mm:02d}:{ss:02d}"
    hm = f"{hh:02d}:{mm:02d}"
    del hm
    if notation == "slash_datetime":
        return f"{year:04d}/{month:02d}/{day:02d} {hms}" if has_time else f"{year:04d}/{month:02d}/{day:02d}"
    if notation == "dash_datetime":
        return f"{year:04d}-{month:02d}-{day:02d} {hms}" if has_time else f"{year:04d}-{month:02d}-{day:02d}"
    if notation == "ko_datetime":
        return (
            f"{year:04d}년 {month:02d}월 {day:02d}일 {hh:02d}시 {mm:02d}분"
            if has_time
            else f"{year:04d}년 {month:02d}월 {day:02d}일"
        )
    if notation == "ja_datetime":
        return (
            f"{year:04d}年{month:02d}月{day:02d}日 {hh:02d}時{mm:02d}分"
            if has_time
            else f"{year:04d}年{month:02d}月{day:02d}日"
        )
    if notation == "slash_date":
        return f"{year:04d}/{month:02d}/{day:02d}"
    if notation == "dash_date":
        return f"{year:04d}-{month:02d}-{day:02d}"
    if notation == "ko_date":
        return f"{year:04d}년 {month:02d}월 {day:02d}일"
    if notation == "ja_date":
        return f"{year:04d}年{month:02d}月{day:02d}日"
    if notation == "en_date":
        return f"{_MONTH_ABBR[month - 1]} {day:02d}, {year:04d}"
    return f"{year:04d}/{month:02d}/{day:02d} {hms}" if has_time else f"{year:04d}/{month:02d}/{day:02d}"


def canonical_brand(make: str, model: str) -> str:
    text = f"{make} {model}".upper()
    if re.search(r"\bPENTAX\b", text):
        return "PENTAX"
    if re.search(r"\bOM\s+DIGITAL\b|\bOM\s+SYSTEM\b", text):
        return "OM SYSTEM"
    for brand in (
        "RICOH", "CANON", "NIKON", "SONY", "FUJIFILM", "PANASONIC",
        "OLYMPUS", "LEICA", "SIGMA", "HASSELBLAD", "KODAK",
    ):
        if re.search(rf"\b{brand}\b", text):
            return brand
    resolved = logos.resolve_brand(make, model)
    if resolved:
        catalog = {b["id"]: b["name"] for b in logos.list_brands_and_eras()}
        if resolved in catalog:
            return catalog[resolved]
    return make.strip()


def resolve_display_values(
    job: dict[str, Any],
    exiftool: Path,
    warnings: list[str],
    *,
    era_label: str = "",
) -> tuple[dict[str, str], str]:
    values = dict(job.get("metadata", {}))
    needed = FIELDS - {"artist"}
    if job.get("focal_mode") == "actual":
        needed -= {"focal35"}
    if job.get("source_path") and any(not values.get(key) for key in needed):
        try:
            for key, value in metadata.read_display_metadata(job["source_path"], exiftool).items():
                if key in FIELDS and not values.get(key):
                    values[key] = value
        except Exception as error:
            warnings.append(f"Visible metadata fallback failed: {error}")

    raw_make = values.get("make", "")
    raw_model = values.get("model", "")
    brand = canonical_brand(raw_make, raw_model)

    # Apply metadata overrides before display toggles
    override_make = (job.get("override_make") or "").strip()
    override_model = (job.get("override_model") or "").strip()
    override_lens = (job.get("override_lens") or "").strip()

    disp_make = override_make if override_make else brand
    disp_model = override_model if override_model else raw_model
    if not override_model and disp_model and disp_make and disp_model.upper().startswith(disp_make.upper() + " "):
        disp_model = disp_model[len(disp_make):].lstrip()
    disp_lens = override_lens if override_lens else values.get("lens", "")

    show_make = job.get("show_make", True)
    show_model = job.get("show_model", True)
    show_lens = job.get("show_lens", True)
    show_exposure = job.get("show_exposure", True)

    values["make"] = disp_make if show_make else ""
    values["model"] = disp_model if show_model else ""
    values["lens"] = disp_lens if show_lens else ""

    # Focal length formatting
    focal_mode = job.get("focal_mode", "equivalent")
    actual_raw = re.sub(r"\s*mm$", "", str(values.get("focal", "")), flags=re.IGNORECASE).strip()
    eq_raw = re.sub(r"\s*mm$", "", str(values.get("focal35", "")), flags=re.IGNORECASE).strip()
    values["focal35"] = eq_raw
    if focal_mode == "ratio":
        crop = float(job.get("crop_factor", 1.0) or 1.0)
        try:
            chosen_focal = str(round(float(actual_raw) * crop)) if actual_raw else ""
        except ValueError:
            chosen_focal = actual_raw
    elif focal_mode == "equivalent":
        chosen_focal = eq_raw
        if not chosen_focal and actual_raw:
            chosen_focal = actual_raw
            warnings.append("35mm-equivalent focal length unavailable; using actual focal length")
    else:
        chosen_focal = actual_raw

    if show_exposure:
        values["focal"] = chosen_focal if chosen_focal else "—"
        values["iso"] = values.get("iso", "")
        values["aperture"] = values.get("aperture", "")
        values["shutter"] = values.get("shutter", "")
    else:
        values["focal"] = ""
        values["focal35"] = ""
        values["iso"] = ""
        values["aperture"] = ""
        values["shutter"] = ""

    values["artist"] = job.get("artist") or values.get("artist", "")
    values["label"] = (job.get("label") or "").strip()
    values["era"] = era_label
    values["date"] = format_date(values.get("date", ""), job.get("date_notation", "slash_datetime"))
    return values, brand


def expand_templates(
    templates: list[str],
    values: dict[str, str],
    *,
    show_make: bool = True,
    show_model: bool = True,
    show_lens: bool = True,
    show_exposure: bool = True,
) -> list[str]:
    hidden_tokens: set[str] = set()
    if not show_make:
        hidden_tokens.add("make")
    if not show_model:
        hidden_tokens.add("model")
    if not show_lens:
        hidden_tokens.add("lens")
    if not show_exposure:
        hidden_tokens.update({"iso", "focal", "focal35", "aperture", "shutter"})

    known_tokens = FIELDS | {"label", "era"}
    if not hidden_tokens:
        # Preserve exact v0.1.0 token rendering when no section is hidden
        def replace_compat(match: re.Match[str]) -> str:
            key = match.group(1)
            if key in known_tokens:
                return str(values.get(key, "") or "—")
            return match.group(0)

        return [re.sub(r"\{([a-zA-Z0-9_]+)\}", replace_compat, t) for t in templates]

    out: list[str] = []
    for template in templates:
        # Remove hidden tokens along with immediate unit prefixes/suffixes (ISO{iso}, {focal}mm, F{aperture}, {shutter}s)
        parts = template
        for tok in hidden_tokens:
            if tok == "iso":
                parts = re.sub(r"(?:ISO\s*)?\{iso\}", "", parts, flags=re.IGNORECASE)
            elif tok == "focal":
                parts = re.sub(r"\{focal\}(?:\s*mm)?", "", parts, flags=re.IGNORECASE)
            elif tok == "focal35":
                parts = re.sub(r"\{focal35\}(?:\s*mm)?", "", parts, flags=re.IGNORECASE)
            elif tok == "aperture":
                parts = re.sub(r"(?:[Ff]/?\s*)?\{aperture\}", "", parts)
            elif tok == "shutter":
                parts = re.sub(r"\{shutter\}(?:\s*s)?", "", parts)
            else:
                parts = parts.replace("{" + tok + "}", "")

        def replace_live(match: re.Match[str]) -> str:
            key = match.group(1)
            if key in known_tokens:
                return str(values.get(key, "") or "—")
            return match.group(0)

        rendered = re.sub(r"\{([a-zA-Z0-9_]+)\}", replace_live, parts)
        rendered = re.sub(r" {2,}", " ", rendered).strip()
        out.append(rendered)
    return out
