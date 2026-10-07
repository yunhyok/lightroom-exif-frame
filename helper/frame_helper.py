"""Lightroom TIFF16 frame renderer. Runtime dependencies: ImageMagick Q16, ExifTool."""
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

import metadata

ROOT = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATES = ["ISO{iso} {focal}mm F{aperture} {shutter}s", "{date}", "{make} {model}", "{lens}"]
FIELDS = {"make", "model", "lens", "iso", "aperture", "shutter", "focal", "focal35", "date", "artist"}


def run(executable: Path, arguments: list[str], *, binary: bool = False) -> str | bytes:
    if executable.stem.lower().startswith("exiftool"):
        result = metadata.run_exiftool(executable, *map(str, arguments), binary=binary)
        return result.stdout if binary else result.stdout.strip()
    if executable.stem.lower() == "magick" and arguments != ["-version"]:
        limits = ["-limit", "memory", "512MiB", "-limit", "map", "1GiB", "-limit", "disk", "2GiB", "-limit", "time", "120"]
        arguments = ([arguments[0], *limits, *arguments[1:]] if arguments and arguments[0] == "identify"
                     else [*limits, *arguments])
    result = subprocess.run([str(executable), *map(str, arguments)], shell=False, capture_output=True,
                            timeout=180, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise ValueError(result.stderr.decode("utf-8", "replace").strip()[:2000] or "External tool failed")
    return result.stdout if binary else result.stdout.decode("utf-8", "replace").strip()


def absolute_path(value, name: str, *, exists: bool = False) -> Path:
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
    return absolute_path(os.environ.get(name, str(ROOT / relative)), name, exists=True)


def number(job: dict, name: str, default, low, high) -> float:
    value = job.get(name, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return value


def validate(job: dict) -> dict:
    if not isinstance(job, dict) or job.get("schema_version") != 1:
        raise ValueError("Unsupported job schema")
    result = dict(job)
    for key in ("input_path", "output_path", "result_path"):
        result[key] = absolute_path(job.get(key), key, exists=key == "input_path")
    if not result["output_path"].parent.is_dir() or not result["result_path"].parent.is_dir():
        raise ValueError("Output and result directories must exist")
    if len({result[key] for key in ("input_path", "output_path", "result_path")}) != 3:
        raise ValueError("Input, output, and result paths must differ")
    if job.get("source_path"):
        result["source_path"] = absolute_path(job["source_path"], "source_path", exists=True)
        if result["source_path"] == result["result_path"]:
            raise ValueError("Source path must differ from result path")
    with result["input_path"].open("rb") as stream:
        if stream.read(4) not in (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"):
            raise ValueError("Input must be a Lightroom-rendered TIFF")
    for name, default, choices in (("format", "jpg", {"jpg", "png", "webp"}),
                                    ("theme", "strap", {"strap", "simple", "none"}),
                                    ("appearance", "light", {"light", "dark", "custom"}),
                                    ("color_space", "sRGB", {"sRGB", "AdobeRGB", "ProPhotoRGB"}),
                                    ("focal_mode", "equivalent", {"equivalent", "actual"})):
        result[name] = job.get(name, default)
        if result[name] not in choices:
            raise ValueError(f"Invalid {name}")
    for name in ("preview", "lossless", "remove_person_info"):
        result[name] = job.get(name, False)
        if not isinstance(result[name], bool):
            raise ValueError(f"{name} must be boolean")
    result["bit_depth"] = job.get("bit_depth", 8)
    if type(result["bit_depth"]) is not int or result["bit_depth"] not in (8, 16):
        raise ValueError("bit_depth must be 8 or 16")
    if result["format"] != "png" and result["bit_depth"] != 8:
        raise ValueError("Only PNG supports 16-bit output")
    if result["format"] == "webp" and result["color_space"] != "sRGB":
        raise ValueError("WebP output requires sRGB")
    suffixes = {"jpg": {".jpg", ".jpeg"}, "png": {".png"}, "webp": {".webp"}}
    if result["output_path"].suffix.lower() not in ({".png"} if result["preview"] else suffixes[result["format"]]):
        raise ValueError("Output extension does not match format")
    for name, default, low, high in (("quality", 95, 1, 100), ("preview_max_size", 1200, 64, 4096),
                                    ("font_percent", 1.65, .2, 10), ("band_percent", 7.3, 1, 40),
                                    ("padding_percent", 1.7, 0, 20), ("logo_percent", 10, 1, 50)):
        result[name] = number(job, name, default, low, high)
    for name, default in (("background_color", "#ffffff"), ("text_color", "#161616"), ("secondary_color", "#555555")):
        result[name] = job.get(name, default)
        if not isinstance(result[name], str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", result[name]):
            raise ValueError(f"{name} must be #RRGGBB")
    if result["appearance"] != "custom":
        result.update(zip(("background_color", "text_color", "secondary_color"),
                          ("#ffffff", "#161616", "#555555") if result["appearance"] == "light" else ("#171717", "#f4f4f4", "#bbbbbb")))
    templates = job.get("templates", DEFAULT_TEMPLATES)
    if not isinstance(templates, list) or len(templates) != 4 or any(not isinstance(t, str) or len(t) > 2048 or "\x00" in t for t in templates):
        raise ValueError("templates must contain four strings of at most 2048 characters")
    result["templates"] = templates
    data = job.get("metadata", {})
    if not isinstance(data, dict) or any(not isinstance(v, (str, int, float)) or isinstance(v, bool) or len(str(v)) > 2048 or "\x00" in str(v) for v in data.values()):
        raise ValueError("metadata must contain short string or numeric values")
    result["metadata"] = {key: str(value).strip() for key, value in data.items() if key in FIELDS}
    if not isinstance(job.get("artist", ""), str) or len(job.get("artist", "")) > 2048 or "\x00" in job.get("artist", ""):
        raise ValueError("artist must be a short string")
    result["artist"] = job.get("artist", "")
    if not isinstance(job.get("logos", {}), dict):
        raise ValueError("logos must be a brand-to-PNG-path object")
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
    result["font_path"] = absolute_path(job.get("font_path", str(font_default)), "font_path", exists=result["theme"] != "none")
    return result


def canonical_brand(make: str, model: str) -> str:
    text = f"{make} {model}".upper()
    if "PENTAX" in model.upper() or "PENTAX" in make.upper():
        return "PENTAX"
    for brand in ("RICOH", "CANON", "NIKON", "SONY", "FUJIFILM", "PANASONIC", "OLYMPUS", "LEICA", "SIGMA", "HASSELBLAD"):
        if brand in text:
            return brand
    if "OM DIGITAL" in text or "OM SYSTEM" in text:
        return "OM SYSTEM"
    return make.strip()


def visible_text(job: dict, exiftool: Path, warnings: list[str]) -> tuple[list[str], str]:
    values = dict(job["metadata"])
    needed = FIELDS - {"artist"}
    if job["focal_mode"] == "actual":
        needed -= {"focal35"}
    if job.get("source_path") and any(not values.get(key) for key in needed):
        try:
            for key, value in metadata.read_display_metadata(job["source_path"], exiftool).items():
                if key in FIELDS and not values.get(key):
                    values[key] = value
        except Exception as error:
            warnings.append(f"Visible metadata fallback failed: {error}")
    brand = canonical_brand(values.get("make", ""), values.get("model", ""))
    values["make"] = brand
    if values.get("model", "").upper().startswith(brand.upper() + " ") and brand:
        values["model"] = values["model"][len(brand):].lstrip()
    focal = values.get("focal35") if job["focal_mode"] == "equivalent" else values.get("focal")
    if not focal and job["focal_mode"] == "equivalent":
        focal = values.get("focal", "")
        if focal:
            warnings.append("35mm-equivalent focal length unavailable; using actual focal length")
    values["focal"] = re.sub(r"\s*mm$", "", str(focal), flags=re.IGNORECASE) if focal else "—"
    values["artist"] = job["artist"] or values.get("artist", "")
    values["date"] = re.sub(r"^(\d{4}):(\d{2}):(\d{2})", r"\1/\2/\3", values.get("date", ""))
    def replace(match):
        return str(values.get(match.group(1), "") or "—") if match.group(1) in FIELDS else match.group(0)
    return [re.sub(r"\{([a-zA-Z0-9_]+)\}", replace, template) for template in job["templates"]], brand


def image_info(magick: Path, image: str) -> tuple[int, int, int, str, str]:
    info = run(magick, ["identify", "-ping", "-quiet", "-format", "%w|%h|%z|%[profiles]|%[icc:description]", image]).split("|", 4)
    return int(info[0]), int(info[1]), int(info[2]), info[3], info[4]


def srgb_profile(magick: Path) -> Path:
    candidates = [magick.parent / "sRGB.icc", magick.parent / "sRGB.icm",
                  Path(os.environ.get("WINDIR", "C:/Windows")) / "System32/spool/drivers/color/sRGB Color Space Profile.icm"]
    for candidate in candidates:
        if candidate.is_file():
            # Reading this tiny synthetic image verifies that this is actually an sRGB ICC.
            description = run(magick, ["-size", "1x1", "xc:white", "-profile", str(candidate), "-format", "%[icc:description]", "info:"])
            if "srgb" in description.lower().replace(" ", ""):
                return candidate
    raise ValueError("A verified sRGB ICC profile is required for frame colors and previews")


def publish(stage: Path, requested: Path) -> Path:
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


def atomic_json(path: Path, data: dict) -> None:
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


def render(raw_job: dict) -> dict:
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
    band = max(1, round(body_width * job["band_percent"] / 100)) if job["theme"] != "none" else 0
    padding = max(0, round(body_width * job["padding_percent"] / 100))
    offset_x = offset_y = padding if job["theme"] == "simple" else 0
    width, height = body_width + 2 * offset_x, body_height + band + 2 * offset_y
    footer_y = offset_y + body_height
    if max(width, height) > 32768 or width * height > 100_000_000 or (job["format"] == "webp" and not job["preview"] and max(width, height) > 16383):
        raise ValueError("Framed image exceeds output dimension limits")
    with tempfile.TemporaryDirectory(prefix=".exif-frame-", dir=job["output_path"].parent) as temporary:
        work = Path(temporary)
        profile = work / "body.icc"
        run(magick, [source, "ICC:" + str(profile)])
        srgb = profile if job["color_space"] == "sRGB" else srgb_profile(magick)
        args = [source, "+profile", "*", "-profile", str(profile), "+repage"]
        if band:
            args = ["-size", f"{width}x{height}", "xc:" + job["background_color"], "-profile", str(srgb), "-profile", str(profile),
                    "(", *args, ")", "-gravity", "NorthWest", "-compose", "Copy", "-geometry", f"+{offset_x}+{offset_y}", "-composite"]
            texts, brand = visible_text(job, exiftool, warnings)
            vertical = min(padding, max(1, round(band * .16)))
            fontsize = max(6, round(body_width * job["font_percent"] / 100))

            def colored_layer(prefix: list[str], path: Path) -> None:
                run(magick, [*prefix, "-profile", str(srgb), "-profile", str(profile), "+profile", "!icc,*", "-depth", "16", str(path)])

            def text_layer(text: str, slot: tuple[int, int, int, int], index: int, color: str, centered=False, nominal=None) -> None:
                if not text.strip():
                    return
                x, y, available_width, available_height = slot
                if available_width < 1 or available_height < 1:
                    warnings.append(f"Text area {index + 1} has no space")
                    return
                textfile, layer = work / f"text-{index}.utf8", work / f"text-{index}.miff"
                textfile.write_text(text, encoding="utf-8")
                point = nominal or fontsize
                for attempt in range(8):
                    settings = ["-background", "none", "-fill", color, "-font", str(job["font_path"]), "-density", "72", "-pointsize", str(point),
                                "-gravity", "Center" if centered else "NorthWest"]
                    colored_layer([*settings, "label:@" + str(textfile)], layer)
                    tw, th, *_ = image_info(magick, str(layer))
                    if tw > available_width:
                        colored_layer([*settings, "-size", f"{available_width}x", "caption:@" + str(textfile)], layer)
                        tw, th, *_ = image_info(magick, str(layer))
                    if tw <= available_width and th <= available_height:
                        break
                    smaller = max(4, min(point - 1, int(point * min(available_width / tw, available_height / th) * .95)))
                    if smaller >= point:
                        warnings.append(f"Text area {index + 1} omitted: cannot fit without overlap")
                        return
                    point = smaller
                else:
                    warnings.append(f"Text area {index + 1} omitted: cannot fit without overlap")
                    return
                if centered:
                    x += (available_width - tw) // 2
                y += (available_height - th) // 2
                args.extend(["(", str(layer), ")", "-compose", "Over", "-gravity", "NorthWest", "-geometry", f"+{x}+{y}", "-composite"])

            if job["theme"] == "simple":
                text_layer("\n".join(t for t in texts if t.strip()), (padding, footer_y + vertical, width - 2 * padding, band - 2 * vertical), 0, job["text_color"], True)
            else:
                gap, line_width = max(1, round(body_width * .015)), max(1, round(body_width / 1920))
                usable = max(1, width - 2 * padding)
                right_width = max(1, round(usable * .43))
                desired_logo = max(1, round(body_width * job["logo_percent"] / 100))
                logo_width = max(1, min(desired_logo, usable - right_width - 3 * gap - line_width - max(1, round(usable * .15))))
                if logo_width < desired_logo:
                    warnings.append("Logo area reduced to retain space for metadata")
                left_width = max(1, usable - right_width - logo_width - 3 * gap - line_width)
                logo_x = padding + left_width + gap
                separator = logo_x + logo_width + gap
                right_edge = separator + line_width + gap
                row = max(1, (band - 2 * vertical) // 2)
                for index, text in enumerate(texts):
                    x = padding if index < 2 else right_edge
                    slotwidth = left_width if index < 2 else width - padding - right_edge
                    text_layer(text, (x, footer_y + vertical + (index % 2) * row, slotwidth, row), index,
                               job["text_color"] if index % 2 == 0 else job["secondary_color"])
                line = work / "separator.miff"
                colored_layer(["-size", f"{line_width}x{max(1, band - 2 * vertical)}", "xc:" + job["secondary_color"]], line)
                args.extend(["(", str(line), ")", "-compose", "Over", "-geometry", f"+{separator}+{footer_y + vertical}", "-composite"])
                logo = job["logos"].get(brand.lower().replace(" ", "-"))
                if logo:
                    if not logo.is_file() or logo.stat().st_size > 32 * 1024 * 1024:
                        raise ValueError("Logo must be an existing PNG smaller than 32 MiB")
                    with logo.open("rb") as stream:
                        if stream.read(8) != b"\x89PNG\r\n\x1a\n":
                            raise ValueError("Logo must be a PNG image")
                    logo_source = "PNG:" + str(logo) + "[0]"
                    lw, lh, _, logo_profiles, _ = image_info(magick, logo_source)
                    if lw > 32768 or lh > 32768 or lw * lh > 32_000_000:
                        raise ValueError("Logo exceeds supported dimensions")
                    boxwidth = logo_width
                    boxheight = max(1, band - 2 * vertical)
                    rendered_logo = work / "logo.miff"
                    logo_args = [logo_source]
                    if "icc" not in logo_profiles.lower():
                        logo_args.extend(["-profile", str(srgb)])
                        warnings.append("Untagged logo assumed sRGB")
                    run(magick, [*logo_args, "-profile", str(profile), "+profile", "!icc,*", "-resize", f"{boxwidth}x{boxheight}", "-depth", "16", str(rendered_logo)])
                    lw, lh, *_ = image_info(magick, str(rendered_logo))
                    x = logo_x + (logo_width - lw) // 2
                    y = footer_y + (band - lh) // 2
                    args.extend(["(", str(rendered_logo), ")", "-compose", "Over", "-geometry", f"+{x}+{y}", "-composite"])
                elif brand:
                    brand_font = max(fontsize, min(round(band * .6), round(body_width * job["logo_percent"] / 100 * .3)))
                    text_layer(brand, (logo_x, footer_y + vertical, logo_width, band - 2 * vertical), 4, job["text_color"], True, brand_font)
        fmt = "png" if job["preview"] else job["format"]
        outdepth = 8 if job["preview"] else job["bit_depth"]
        if job["preview"]:
            args.extend(["-profile", str(srgb), "-resize", f"{int(job['preview_max_size'])}x{int(job['preview_max_size'])}>"])
        args.extend(["-strip", "-alpha", "off", "-depth", str(outdepth)])
        if fmt == "png":
            args.extend(["-define", f"png:bit-depth={outdepth}", "-define", "png:color-type=2", "-define", "png:exclude-chunk=sRGB,gAMA,cHRM,date,tEXt,zTXt,iTXt,eXIf"])
        elif fmt == "jpg":
            args.extend(["-sampling-factor", "4:4:4", "-quality", str(int(job["quality"]))])
        else:
            args.extend(["-quality", "100" if job["lossless"] else str(int(job["quality"])), "-define", "webp:lossless=" + str(job["lossless"]).lower()])
        stage = work / f"rendered.{fmt}"
        run(magick, ["-limit", "memory", "512MiB", "-limit", "map", "1GiB", "-limit", "disk", "2GiB", "-limit", "time", "120", *args, str(stage)])
        # -strip removes PNG ICC chunks too; reattach only the verified destination profile,
        # without another pixel conversion or restoring any original metadata.
        run(exiftool, ["-config", "", "-charset", "filename=UTF8", "-overwrite_original",
                       "-ICC_Profile<=" + str(srgb if job["preview"] else profile), str(stage)])
        final_width, final_height, _, _, _ = image_info(magick, str(stage))
        embedded = run(exiftool, ["-config", "", "-b", "-ICC_Profile", str(stage)], binary=True)
        if embedded != (srgb if job["preview"] else profile).read_bytes():
            raise ValueError("Renderer lost or changed destination ICC profile")
        if not job["preview"]:
            warnings.extend(metadata.copy_metadata(job["input_path"], stage, exiftool=exiftool, format=fmt,
                            width=final_width, height=final_height, body_width=body_width, body_height=body_height,
                            offset_x=offset_x, offset_y=offset_y, remove_person_info=job["remove_person_info"]))
        output = publish(stage, job["output_path"])
    return {"schema_version": 1, "ok": True, "output_path": str(output), "width": final_width, "height": final_height, "warnings": warnings}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True)
    arguments = parser.parse_args(argv)
    result_path = None
    try:
        job_path = absolute_path(arguments.job, "job", exists=True)
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
        result = render(job)
    except Exception as error:
        result = {"schema_version": 1, "ok": False, "error": str(error), "warnings": []}
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
