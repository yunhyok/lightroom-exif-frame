"""Lightroom TIFF16 frame renderer and brand/era inspector. Runtime dependencies: ImageMagick Q16, ExifTool, resvg."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any

import formatting
import logos
import metadata
import themes

SCHEMA_VERSION = 1
ROOT = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATES = [
    "ISO{iso} {focal}mm F{aperture} {shutter}s",
    "{date}",
    "{make} {model}",
    "{lens}",
]
FIELDS = formatting.FIELDS


def run(executable: Path, arguments: list[str], *, binary: bool = False) -> str | bytes:
    """Run bundled ImageMagick or ExifTool safely without shell expansion."""
    args = [str(a) for a in arguments]
    if executable.stem.lower().startswith("exiftool"):
        result = metadata.run_exiftool(executable, *args, binary=binary)
        return result.stdout if binary else result.stdout.strip()
    if executable.stem.lower() == "magick" and args != ["-version"]:
        limits = ["-limit", "memory", "512MiB", "-limit", "map", "1GiB", "-limit", "disk", "2GiB", "-limit", "time", "120"]
        args = ([args[0], *limits, *args[1:]] if args and args[0] == "identify" else [*limits, *args])
    result = subprocess.run(
        [str(executable), *args],
        shell=False,
        capture_output=True,
        timeout=180,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        raise ValueError(result.stderr.decode("utf-8", "replace").strip()[:2000] or "External tool failed")
    return result.stdout if binary else result.stdout.decode("utf-8", "replace").strip()


def absolute_path(value: object, name: str, *, exists: bool = False) -> Path:
    """Validate and resolve an absolute file path."""
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError(f"{name} must be an absolute path")
    path = Path(value)
    if not path.is_absolute():
        raise ValueError(f"{name} must be an absolute path")
    path = path.resolve()
    if exists and not path.is_file():
        raise ValueError(f"{name} does not exist: {path}")
    return path


def tool(name: str, relative: str) -> Path:
    """Resolve an external tool executable from environment override or plugin bundle."""
    override = os.environ.get(name)
    if override is not None:
        return absolute_path(override, name, exists=True)
    candidates = [ROOT / relative, ROOT / "vendor" / relative]
    if not getattr(sys, "frozen", False):
        candidates = [ROOT / "vendor" / relative, ROOT / relative]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return absolute_path(str(candidates[0]), name, exists=True)


def number(job: dict[str, Any], name: str, default: float, low: float, high: float) -> float:
    """Validate a finite numeric field within [low, high]."""
    value = job.get(name, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return float(value)


def _bool_opt(job: dict[str, Any], name: str, default: bool) -> bool:
    value = job.get(name, default)
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be boolean")
    return value


def _str_opt(job: dict[str, Any], name: str, default: str, max_len: int = 256) -> str:
    value = job.get(name, default)
    if not isinstance(value, str) or len(value) > max_len or "\x00" in value:
        raise ValueError(f"{name} must be a string of at most {max_len} characters")
    return value


def _allowed_opt(job: dict[str, Any], name: str, allowed: set[str] | tuple[str, ...], default: str) -> str:
    value = job.get(name, default)
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(f"Invalid {name}")
    return value


def validate(job: object, *, inspect_only: bool = False) -> dict[str, Any]:
    """Validate and normalize a JSON render or inspect job."""
    if not isinstance(job, dict) or job.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported job schema")
    result = dict(job)
    result["collision_mode"] = _allowed_opt(job, "collision_mode", ("rename", "overwrite", "skip", "ask"), "rename")
    result["result_path"] = absolute_path(job.get("result_path"), "result_path")
    if not result["result_path"].parent.is_dir():
        raise ValueError("Output and result directories must exist")

    if inspect_only:
        result["input_path"] = absolute_path(job["input_path"], "input_path", exists=True) if job.get("input_path") else None
        result["output_path"] = absolute_path(job["output_path"], "output_path") if job.get("output_path") else None
    else:
        for key in ("input_path", "output_path"):
            result[key] = absolute_path(job.get(key), key, exists=key == "input_path")
        if not result["output_path"].parent.is_dir():
            raise ValueError("Output and result directories must exist")
        if len({result["input_path"], result["output_path"], result["result_path"]}) != 3:
            raise ValueError("Input, output, and result paths must differ")
        with result["input_path"].open("rb") as stream:
            if stream.read(4) not in (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"):
                raise ValueError("Input must be a Lightroom-rendered TIFF")

    if job.get("source_path"):
        result["source_path"] = absolute_path(job["source_path"], "source_path", exists=True)
        if result["source_path"] == result["result_path"]:
            raise ValueError("Source path must differ from result path")
        if result["collision_mode"] == "overwrite" and result.get("output_path") and result["source_path"] == result["output_path"]:
            raise ValueError("Source path must differ from output path when overwriting")
    else:
        result["source_path"] = None

    for name, default, choices in (
        ("format", "jpg", {"jpg", "png", "webp"}),
        ("theme", "strap", themes.THEMES),
        ("appearance", "light", {"auto", "light", "dark", "custom"}),
        ("color_space", "sRGB", {"sRGB", "AdobeRGB", "ProPhotoRGB"}),
        ("focal_mode", "equivalent", {"equivalent", "actual", "ratio"}),
    ):
        result[name] = job.get(name, default)
        if result[name] not in choices:
            raise ValueError(f"Invalid {name}")

    for name in ("preview", "lossless", "remove_person_info"):
        result[name] = _bool_opt(job, name, False)

    result["bit_depth"] = job.get("bit_depth", 8)
    if type(result["bit_depth"]) is not int or result["bit_depth"] not in (8, 16):
        raise ValueError("bit_depth must be 8 or 16")
    if result["format"] != "png" and result["bit_depth"] != 8:
        raise ValueError("Only PNG supports 16-bit depth")
    if result["format"] == "webp" and result["color_space"] != "sRGB":
        raise ValueError("WebP requires sRGB")

    result["quality"] = round(number(job, "quality", 95, 1, 100))
    result["preview_max_size"] = round(number(job, "preview_max_size", 600, 64, 4096))
    result["font_percent"] = number(job, "font_percent", 1.65, 0.2, 10)
    result["band_percent"] = number(job, "band_percent", 7.3, 1, 40)
    result["padding_percent"] = number(job, "padding_percent", 1.7, 0, 20)
    result["logo_percent"] = number(job, "logo_percent", 10.0, 1, 50)
    result["crop_factor"] = number(job, "crop_factor", 1.0, 0.1, 20.0)

    # v0.2.0 layout, typography, logo CI, and metadata controls
    result["aspect_ratio"] = _allowed_opt(job, "aspect_ratio", themes.ASPECT_RATIOS, "free")
    result["no_crop"] = _bool_opt(job, "no_crop", False)
    result["padding_inside"] = _bool_opt(job, "padding_inside", False)
    result["text_alpha"] = number(job, "text_alpha", 1.0, 0.05, 1.0)
    result["shadow_size"] = number(job, "shadow_size", 0.0, 0.0, 50.0)
    result["text_align"] = _allowed_opt(job, "text_align", ("left", "center", "right"), "center")
    result["font_style"] = _allowed_opt(job, "font_style", ("normal", "italic"), "normal")
    result["compact"] = _bool_opt(job, "compact", False)
    result["logo_mode"] = _allowed_opt(job, "logo_mode", ("auto_era", "auto_latest", "manual_era", "text_only", "none"), "auto_era")
    result["logo_style"] = _allowed_opt(job, "logo_style", ("brand", "mono"), "brand")
    result["manual_brand"] = _str_opt(job, "manual_brand", "", 128)
    result["manual_era"] = _str_opt(job, "manual_era", "", 128)
    result["show_make"] = _bool_opt(job, "show_make", True)
    result["show_model"] = _bool_opt(job, "show_model", True)
    result["show_lens"] = _bool_opt(job, "show_lens", True)
    result["show_exposure"] = _bool_opt(job, "show_exposure", True)
    result["override_make"] = _str_opt(job, "override_make", "", 256)
    result["override_model"] = _str_opt(job, "override_model", "", 256)
    result["override_lens"] = _str_opt(job, "override_lens", "", 256)
    result["label"] = _str_opt(job, "label", "", 256)
    result["divider"] = _str_opt(job, "divider", "∙", 16)
    result["date_notation"] = _allowed_opt(job, "date_notation", formatting.DATE_NOTATIONS, "slash_datetime")

    for name, default in (("background_color", "#ffffff"), ("text_color", "#161616"), ("secondary_color", "#555555")):
        result[name] = job.get(name, default)
        if not isinstance(result[name], str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", result[name]):
            raise ValueError(f"{name} must be #RRGGBB")
    if result["appearance"] != "custom":
        bg, fg, sec, _ = themes.resolve_theme_colors(result)
        result["background_color"] = bg
        result["text_color"] = fg
        result["secondary_color"] = sec

    templates = job.get("templates", DEFAULT_TEMPLATES)
    if not isinstance(templates, list) or len(templates) != 4 or any(not isinstance(t, str) or len(t) > 2048 or "\x00" in t for t in templates):
        raise ValueError("templates must contain four strings of at most 2048 characters")
    result["templates"] = templates

    data = job.get("metadata", {})
    if not isinstance(data, dict) or any(not isinstance(v, (str, int, float)) or isinstance(v, bool) or len(str(v)) > 2048 or "\x00" in str(v) for v in data.values()):
        raise ValueError("metadata must contain short string or numeric values")
    result["metadata"] = {key: str(value).strip() for key, value in data.items() if key in FIELDS}

    result["artist"] = _str_opt(job, "artist", "", 2048)

    if not isinstance(job.get("logos", {}), dict):
        raise ValueError("logos must be a brand-to-logo-path object")
    result["logos"] = {}
    for brand, value in job.get("logos", {}).items():
        if not isinstance(brand, str):
            raise ValueError("Invalid logo brand")
        if value:
            path = absolute_path(value, "logo")
            if path in (result["input_path"], result["output_path"], result["result_path"]):
                raise ValueError("Logo must differ from input/output/result")
            result["logos"][brand.lower()] = path

    font_default = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/malgun.ttf"
    if inspect_only:
        result["font_path"] = absolute_path(job.get("font_path", str(font_default)), "font_path") if job.get("font_path") else font_default
    else:
        need_font = result["theme"] not in ("none", "just_frame", "cinemascope")
        result["font_path"] = absolute_path(job.get("font_path", str(font_default)), "font_path", exists=need_font)
    return result


def canonical_brand(make: str, model: str) -> str:
    """Return canonical camera manufacturer name for text display and presets."""
    return formatting.canonical_brand(make, model)


def _resolve_raw_make_model(job: dict[str, Any], exiftool: Path, warnings: list[str]) -> tuple[str, str]:
    """Obtain unstripped raw Make and Model before display overrides or hiding."""
    meta = job.get("metadata", {})
    raw_make = str(meta.get("make", "") or "").strip()
    raw_model = str(meta.get("model", "") or "").strip()
    if (not raw_make or not raw_model) and job.get("source_path"):
        try:
            disk = metadata.read_display_metadata(job["source_path"], exiftool)
            raw_make = raw_make or str(disk.get("make", "") or "").strip()
            raw_model = raw_model or str(disk.get("model", "") or "").strip()
        except Exception as error:
            warnings.append(f"Visible metadata fallback failed: {error}")
    return raw_make, raw_model


def visible_text(job: dict[str, Any], exiftool: Path, warnings: list[str], *, era_label: str = "") -> tuple[list[str], str]:
    """Resolve formatted display values and expand the 4 template strings."""
    values, brand = formatting.resolve_display_values(job, exiftool, warnings, era_label=era_label)
    texts = formatting.expand_templates(
        job["templates"],
        values,
        show_make=job.get("show_make", True),
        show_model=job.get("show_model", True),
        show_lens=job.get("show_lens", True),
        show_exposure=job.get("show_exposure", True),
    )
    return texts, brand


def image_info(magick: Path, image: str) -> tuple[int, int, int, str, str]:
    """Query image dimensions, bit depth, profile list, and ICC description via ImageMagick."""
    info = run(magick, ["identify", "-ping", "-quiet", "-format", "%w|%h|%z|%[profiles]|%[icc:description]", image]).split("|", 4)
    return int(info[0]), int(info[1]), int(info[2]), info[3], info[4]


def srgb_profile(magick: Path) -> Path:
    """Locate and verify an sRGB ICC profile on disk."""
    candidates = [
        magick.parent / "sRGB.icc",
        magick.parent / "sRGB.icm",
        Path(os.environ.get("WINDIR", "C:/Windows")) / "System32/spool/drivers/color/sRGB Color Space Profile.icm",
    ]
    for candidate in candidates:
        if candidate.is_file():
            # Reading this tiny synthetic image verifies that this is actually an sRGB ICC.
            description = run(magick, ["-size", "1x1", "xc:white", "-profile", str(candidate), "-format", "%[icc:description]", "info:"])
            if "srgb" in description.lower().replace(" ", ""):
                return candidate
    raise ValueError("A verified sRGB ICC profile is required for frame colors and previews")


def publish(
    stage: Path,
    requested: Path,
    *,
    overwrite: bool = False,
    source_path: Path | None = None,
) -> Path:
    """Move staged output into its destination safely without clobbering source images."""
    if overwrite:
        if source_path is not None:
            try:
                if requested.resolve() == source_path.resolve():
                    raise ValueError("Refusing to overwrite original source photo")
            except OSError:
                if str(requested).lower() == str(source_path).lower():
                    raise ValueError("Refusing to overwrite original source photo")
        os.replace(stage, requested)
        return requested

    for index in range(10000):
        destination = requested if index == 0 else requested.with_name(f"{requested.stem}_{index}{requested.suffix}")
        try:
            # Windows rename is atomic and refuses overwrite, including on exFAT.
            if os.name == "nt":
                stage.rename(destination)
            else:
                os.link(stage, destination)
                stage.unlink()
            return destination
        except FileExistsError:
            continue
    raise ValueError("Unable to allocate output filename")


def atomic_json(path: Path, data: dict[str, Any]) -> None:
    """Atomically write JSON to path inside its parent directory."""
    handle, name = tempfile.mkstemp(prefix=".exif-frame-result-", suffix=".json", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def inspect(raw_job: dict[str, Any]) -> dict[str, Any]:
    """Fast brand, era, and CI SVG detection for Lightroom Preview/UI feedback."""
    job = validate(raw_job, inspect_only=True)
    warnings: list[str] = []
    exiftool = tool("EXIF_FRAME_EXIFTOOL", "exiftool/exiftool.exe")
    raw_make, raw_model = _resolve_raw_make_model(job, exiftool, warnings)
    _, _, _, is_dark = themes.resolve_theme_colors(job)
    resolution = logos.resolve_logo(
        raw_make,
        raw_model,
        logo_mode=job["logo_mode"],
        logo_style=job["logo_style"],
        manual_brand=job["manual_brand"],
        manual_era=job["manual_era"],
        user_logos=job["logos"],
        is_dark=is_dark,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "brand_info": resolution.to_dict(),
        "warnings": warnings,
    }


def render(raw_job: dict[str, Any]) -> dict[str, Any]:
    """Render framed image in 16-bit LCMS color-managed pipeline and copy metadata."""
    job = validate(raw_job)
    warnings: list[str] = []
    magick = tool("EXIF_FRAME_MAGICK", "imagemagick/magick.exe")
    exiftool = tool("EXIF_FRAME_EXIFTOOL", "exiftool/exiftool.exe")
    version = run(magick, ["-version"])
    if not re.search(r"ImageMagick 7.*\bQ16\b", version) or "lcms" not in version.lower():
        raise ValueError("ImageMagick 7 Q16 with LCMS is required")

    source = "TIFF:" + str(job["input_path"]) + "[0]"
    body_width, body_height, depth, profiles, description = image_info(magick, source)
    if depth != 16 or "icc" not in profiles.lower():
        raise ValueError("Lightroom input must be TIFF16 with an embedded ICC profile")
    expected = {"sRGB": ("srgb",), "AdobeRGB": ("adobergb",), "ProPhotoRGB": ("prophoto", "romm")}[job["color_space"]]
    if not any(name in re.sub(r"[^a-z0-9]", "", description.lower()) for name in expected):
        raise ValueError(f"Input ICC does not match {job['color_space']}: {description}")
    if body_width < 1 or body_height < 1 or body_width > 32768 or body_height > 32768 or body_width * body_height > 100_000_000:
        raise ValueError("Image exceeds supported dimensions (32768 per side / 100 megapixels)")
    if job["format"] == "webp" and not job["preview"] and (body_width > 16383 or body_height > 16383):
        raise ValueError("WebP dimensions cannot exceed 16383 pixels")

    bg_color, text_color, secondary_color, is_dark = themes.resolve_theme_colors(job)
    eff_w, eff_h, crop_spec, pad_to_ratio = themes.prepare_body_transform(
        body_width, body_height, job["aspect_ratio"], job["no_crop"], job["theme"]
    )
    width, height, offset_x, offset_y, band, padding = themes.compute_canvas_geometry(job, eff_w, eff_h)

    if max(width, height) > 32768 or width * height > 100_000_000 or (job["format"] == "webp" and not job["preview"] and max(width, height) > 16383):
        raise ValueError("Framed image exceeds output dimension limits")

    pad_x = ((eff_w - body_width) // 2) if pad_to_ratio else 0
    pad_y = ((eff_h - body_height) // 2) if pad_to_ratio else 0

    raw_make, raw_model = _resolve_raw_make_model(job, exiftool, warnings)
    resolution = logos.resolve_logo(
        raw_make,
        raw_model,
        logo_mode=job["logo_mode"],
        logo_style=job["logo_style"],
        manual_brand=job["manual_brand"],
        manual_era=job["manual_era"],
        user_logos=job["logos"],
        is_dark=is_dark,
    )

    with tempfile.TemporaryDirectory(prefix=".exif-frame-", dir=job["output_path"].parent) as temporary:
        work = Path(temporary)
        profile = work / "body.icc"
        run(magick, [source, "ICC:" + str(profile)])
        srgb = profile if job["color_space"] == "sRGB" else srgb_profile(magick)

        body_args = [source, "+profile", "*", "-profile", str(profile), "+repage"]
        if crop_spec:
            body_args.extend(["-crop", crop_spec, "+repage"])

        need_canvas = (
            width != (eff_w if crop_spec else body_width)
            or height != (eff_h if crop_spec else body_height)
            or offset_x != 0
            or offset_y != 0
            or pad_to_ratio
        )
        if need_canvas:
            args = [
                "-size", f"{width}x{height}", "xc:" + bg_color,
                "-profile", str(srgb), "-profile", str(profile),
                "(", *body_args, ")",
                "-gravity", "NorthWest",
                "-compose", "Copy",
                "-geometry", f"+{offset_x + pad_x}+{offset_y + pad_y}",
                "-composite",
            ]
        else:
            args = body_args

        if job["theme"] not in ("none", "just_frame", "cinemascope"):
            values, brand = formatting.resolve_display_values(job, exiftool, warnings, era_label=resolution.era_label)
            texts = formatting.expand_templates(
                job["templates"],
                values,
                show_make=job["show_make"],
                show_model=job["show_model"],
                show_lens=job.get("show_lens", True),
                show_exposure=job["show_exposure"],
            )
            layer_args = themes.build_theme_layers(
                job=job,
                canvas_w=width,
                canvas_h=height,
                eff_w=eff_w,
                eff_h=eff_h,
                offset_x=offset_x,
                offset_y=offset_y,
                band=band,
                padding=padding,
                bg_color=bg_color,
                text_color=text_color,
                secondary_color=secondary_color,
                is_dark=is_dark,
                texts=texts,
                values=values,
                brand=brand,
                resolution=resolution,
                work=work,
                profile=profile,
                srgb=srgb,
                run_fn=run,
                image_info_fn=image_info,
                magick=magick,
                warnings=warnings,
            )
            args.extend(layer_args)

        fmt = "png" if job["preview"] else job["format"]
        outdepth = 8 if job["preview"] else job["bit_depth"]
        if job["preview"]:
            args.extend(["-profile", str(srgb), "-resize", f"{int(job['preview_max_size'])}x{int(job['preview_max_size'])}>"])
        args.extend(["-strip", "-alpha", "off", "-depth", str(outdepth)])
        if fmt == "png":
            args.extend([
                "-define", f"png:bit-depth={outdepth}",
                "-define", "png:color-type=2",
                "-define", "png:exclude-chunk=sRGB,gAMA,cHRM,date,tEXt,zTXt,iTXt,eXIf",
            ])
        elif fmt == "jpg":
            args.extend(["-sampling-factor", "4:4:4", "-quality", str(int(job["quality"]))])
        else:
            args.extend([
                "-quality", "100" if job["lossless"] else str(int(job["quality"])),
                "-define", "webp:lossless=" + str(job["lossless"]).lower(),
            ])

        stage = work / f"rendered.{fmt}"
        run(magick, [*args, str(stage)])
        # -strip removes PNG ICC chunks too; reattach only the verified destination profile,
        # without another pixel conversion or restoring any original metadata.
        run(exiftool, [
            "-config", "", "-charset", "filename=UTF8", "-overwrite_original",
            "-ICC_Profile<=" + str(srgb if job["preview"] else profile), str(stage),
        ])
        final_width, final_height, _, _, _ = image_info(magick, str(stage))
        embedded = run(exiftool, ["-config", "", "-b", "-ICC_Profile", str(stage)], binary=True)
        if embedded != (srgb if job["preview"] else profile).read_bytes():
            raise ValueError("Renderer lost or changed destination ICC profile")

        if not job["preview"]:
            meta_bw = body_width if pad_to_ratio else eff_w
            meta_bh = body_height if pad_to_ratio else eff_h
            meta_ox = offset_x + pad_x
            meta_oy = offset_y + pad_y
            warnings.extend(
                metadata.copy_metadata(
                    job["input_path"],
                    stage,
                    exiftool=exiftool,
                    format=fmt,
                    width=final_width,
                    height=final_height,
                    body_width=meta_bw,
                    body_height=meta_bh,
                    offset_x=meta_ox,
                    offset_y=meta_oy,
                    remove_person_info=job["remove_person_info"],
                )
            )

        output = publish(
            stage,
            job["output_path"],
            overwrite=(not job["preview"] and job["collision_mode"] == "overwrite"),
            source_path=job.get("source_path"),
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "output_path": str(output),
        "width": final_width,
        "height": final_height,
        "warnings": warnings,
        "brand_info": resolution.to_dict(),
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entry point supporting --job and --inspect."""
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--job")
    group.add_argument("--inspect")
    arguments = parser.parse_args(argv)
    mode = "inspect" if arguments.inspect else "job"
    raw_arg = arguments.inspect or arguments.job
    result_path: Path | None = None
    try:
        job_path = absolute_path(raw_arg, "job", exists=True)
        if job_path.stat().st_size > 1024 * 1024:
            raise ValueError("Job exceeds 1 MiB")
        job = json.loads(job_path.read_text(encoding="utf-8-sig"))
        result_path = absolute_path(job.get("result_path"), "result_path")
        protected = {job_path}
        for key in ("input_path", "source_path", "output_path", "font_path"):
            if job.get(key):
                protected.add(absolute_path(job[key], key))
        for value in job.get("logos", {}).values() if isinstance(job.get("logos", {}), dict) else []:
            if value:
                protected.add(absolute_path(value, "logo"))
        if result_path in protected:
            result_path = None
            raise ValueError("Result path cannot overwrite job, source, input, font, logo, or output")
        result = inspect(job) if mode == "inspect" else render(job)
    except Exception as error:
        result = {"schema_version": SCHEMA_VERSION, "ok": False, "error": str(error), "warnings": []}
    if result_path:
        try:
            atomic_json(result_path, result)
        except Exception as error:
            if sys.stderr is not None:
                print(f"Cannot write result: {error}", file=sys.stderr)
            return 1
    else:
        if sys.stderr is not None:
            print(result.get("error", "No result path"), file=sys.stderr)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
