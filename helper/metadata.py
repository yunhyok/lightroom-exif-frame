"""Read Lightroom-rendered metadata and copy safe tags to framed images."""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import tempfile
from fractions import Fraction
from typing import Any


_DISPLAY_TAGS = {
    "make": ("Make",),
    "model": ("Model",),
    "lens": ("LensModel", "Lens"),
    "iso": ("ISO", "ISOSpeedRatings"),
    "aperture": ("FNumber", "ApertureValue"),
    "shutter": ("ExposureTime", "ShutterSpeedValue"),
    "focal": ("FocalLength",),
    "focal35": ("FocalLengthIn35mmFormat", "FocalLengthIn35mmFilm"),
    "date": ("DateTimeOriginal", "CreateDate", "DateCreated"),
}

_COPY_EXCLUDES = (
    "--MakerNotes:all", "--ICC_Profile", "--Orientation",
    "--ImageWidth", "--ImageHeight", "--ExifImageWidth", "--ExifImageHeight",
    "--PixelXDimension", "--PixelYDimension", "--ThumbnailImage", "--ThumbnailTIFF",
    "--PreviewImage", "--PreviewTIFF", "--JpgFromRaw", "--OtherImage",
    "--XMP-mwg-rs:RegionInfo", "--XMP-MP:RegionInfoMP", "--XMP-iptcExt:ImageRegion",
)
_IPTC_ENVELOPE_TAGS = {
    "ApplicationRecordVersion", "ARMIdentifier", "ARMVersion", "CodedCharacterSet",
    "DateSent", "Destination", "EnvelopeNumber", "EnvelopePriority", "EnvelopeRecordVersion",
    "FileFormat", "FileVersion", "ModelVersion", "RecordVersion", "ServiceIdentifier", "TimeSent",
}


def _run(exiftool: pathlib.Path, *args: str,
         cwd: pathlib.Path | None = None) -> subprocess.CompletedProcess[str]:
    command = [str(exiftool), "-config", "", "-charset", "filename=UTF8", *args]
    kwargs: dict[str, Any] = {
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "check": False,
        "timeout": 180,
    }
    env = os.environ.copy()
    env.update({"LANG": "C", "LC_ALL": "C"})
    kwargs["env"] = env
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    try:
        result = subprocess.run(command, cwd=cwd, **kwargs)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("ExifTool timed out after 180 seconds") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"ExifTool failed ({result.returncode}): {detail or 'unknown error'}")
    diagnostics = f"{result.stdout}\n{result.stderr}"
    if "Warning: Error opening file" in diagnostics:
        raise RuntimeError(f"ExifTool could not open metadata source: {diagnostics.strip()}")
    return result


def _read(source: pathlib.Path, exiftool: pathlib.Path) -> dict[str, Any]:
    result = _run(exiftool, "-j", "-G1", "-a", "-s", "-struct", "-n", str(source))
    try:
        data = json.loads(result.stdout)
        return data[0] if data else {}
    except (json.JSONDecodeError, TypeError, IndexError) as exc:
        raise RuntimeError(f"ExifTool returned invalid metadata for {source}") from exc


def _text(value: Any) -> str:
    if isinstance(value, (str, int, float)):
        return str(value).strip()
    if isinstance(value, list):
        return ", ".join(filter(None, (_text(item) for item in value)))
    return ""


def _value(tags: dict[str, Any], candidates: tuple[str, ...]) -> Any:
    for name in candidates:
        matches = [value for key, value in tags.items() if key.rsplit(":", 1)[-1] == name]
        for value in matches:
            if _text(value):
                return value
    return None


def read_display_metadata(source: pathlib.Path, exiftool: pathlib.Path) -> dict[str, str]:
    """Return only the fields allowed in the visible frame."""
    tags = _read(pathlib.Path(source), pathlib.Path(exiftool))
    result: dict[str, str] = {}
    for name, candidates in _DISPLAY_TAGS.items():
        value = _text(_value(tags, candidates))
        if value:
            if name == "shutter":
                try:
                    exposure = Fraction(value).limit_denominator(1_000_000)
                    if 0 < exposure < 1:
                        value = f"{exposure.numerator}/{exposure.denominator}"
                except (ValueError, ZeroDivisionError):
                    pass
            result[name] = value
    return result


def _regions(tags: dict[str, Any], width: int, height: int, body_width: int,
             body_height: int, offset_x: int, offset_y: int) -> tuple[dict[str, Any], list[str]]:
    changed: dict[str, Any] = {}
    warnings: list[str] = []
    for key, value in tags.items():
        is_mwg = key.endswith("mwg-rs:RegionInfo")
        is_microsoft = key.endswith("MP:RegionInfoMP")
        if not (is_mwg or is_microsoft) or not isinstance(value, dict):
            continue
        mapped = json.loads(json.dumps(value))
        if is_mwg:
            dims = mapped.get("AppliedToDimensions")
            regions = mapped.get("RegionList")
            if not isinstance(dims, dict) or not isinstance(regions, list):
                warnings.append(f"Unsupported spatial metadata omitted: {key}")
                continue
            for region in regions:
                area = region.get("Area") if isinstance(region, dict) else None
                if (not isinstance(area, dict) or area.get("Unit") != "normalized"
                        or not all(isinstance(area.get(k), (int, float)) for k in ("X", "Y", "W", "H"))):
                    warnings.append(f"Unsupported spatial metadata omitted: {key}")
                    break
                area["X"] = (offset_x + area["X"] * body_width) / width
                area["Y"] = (offset_y + area["Y"] * body_height) / height
                area["W"] = area["W"] * body_width / width
                area["H"] = area["H"] * body_height / height
            else:
                dims["W"], dims["H"], dims["Unit"] = width, height, "pixel"
                changed[key] = mapped
        elif is_microsoft:
            regions = mapped.get("Regions")
            if not isinstance(regions, list):
                warnings.append(f"Unsupported spatial metadata omitted: {key}")
                continue
            for region in regions:
                rect = region.get("Rectangle") if isinstance(region, dict) else None
                try:
                    x, y, w, h = (float(part) for part in rect.split(","))
                except (AttributeError, ValueError):
                    warnings.append(f"Unsupported spatial metadata omitted: {key}")
                    break
                region["Rectangle"] = ",".join(map(str, (
                    (offset_x + x * body_width) / width,
                    (offset_y + y * body_height) / height,
                    w * body_width / width,
                    h * body_height / height,
                )))
            else:
                changed[key] = mapped
    return changed, warnings


def _dimension_args(tags: dict[str, Any], width: int, height: int) -> list[str]:
    values: list[str] = []
    for key in tags:
        if key.endswith(":Orientation"):
            values.append(f"-{key}#=1")
        elif key.rsplit(":", 1)[-1] in ("ImageWidth", "ExifImageWidth", "PixelXDimension"):
            values.append(f"-{key}={width}")
        elif key.rsplit(":", 1)[-1] in ("ImageHeight", "ImageLength", "ExifImageHeight", "PixelYDimension"):
            values.append(f"-{key}={height}")
    return values


def _write_structures(exiftool: pathlib.Path, destination: pathlib.Path,
                      structures: dict[str, Any]) -> None:
    if not structures:
        return
    payload = [{"SourceFile": str(destination), **structures}]
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as stream:
        json.dump(payload, stream, ensure_ascii=False)
        temp_path = pathlib.Path(stream.name)
    try:
        _run(exiftool, "-struct", f"-j={temp_path}", "-overwrite_original", str(destination))
    finally:
        temp_path.unlink(missing_ok=True)


def _copy_webp_iptc(exiftool: pathlib.Path, source: pathlib.Path, destination: pathlib.Path,
                    source_tags: dict[str, Any], cwd: pathlib.Path | None = None) -> str | None:
    args_file = _iptc_args_file(exiftool)
    if not args_file.is_file():
        return "IPTC-to-XMP mapping skipped: ExifTool arg_files/iptc2xmp.args is missing"

    filtered: list[str] = []
    for line in args_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("-") and "<" in stripped:
            target = stripped[1:].split("<", 1)[0].strip()
            if any(key == target or key.startswith(target + "-") for key in source_tags):
                continue
        filtered.append(line)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".args", delete=False) as stream:
        stream.write("\n".join(filtered))
        args_path = pathlib.Path(stream.name)
    try:
        _run(exiftool, "-tagsFromFile", str(source), "-@", str(args_path),
             "-overwrite_original", str(destination), cwd=cwd)
    finally:
        args_path.unlink(missing_ok=True)
    return None


def _iptc_args_file(exiftool: pathlib.Path) -> pathlib.Path:
    path = exiftool.parent / "exiftool_files" / "arg_files" / "iptc2xmp.args"
    if not path.is_file():
        path = exiftool.parent / "arg_files" / "iptc2xmp.args"
    return path


def _warn_unmapped_iptc(args_file: pathlib.Path, tags: dict[str, Any]) -> list[str]:
    mapped = set()
    for line in args_file.read_text(encoding="utf-8").splitlines():
        if "<" in line:
            source = line.rsplit("<", 1)[1].strip()
            if source.startswith("IPTC:"):
                mapped.add(source.rsplit(":", 1)[-1])
    return [
        f"WebP IPTC field not mapped to XMP: {key}"
        for key in tags
        if key.startswith("IPTC:")
        and key.rsplit(":", 1)[-1] not in mapped | _IPTC_ENVELOPE_TAGS
    ]


def _copy_metadata(source: pathlib.Path, copy_source: pathlib.Path, destination: pathlib.Path, *,
                   exiftool: pathlib.Path, format: str, width: int, height: int,
                   body_width: int, body_height: int, offset_x: int, offset_y: int,
                   copy_cwd: pathlib.Path | None = None) -> list[str]:
    """Copy Lightroom-filtered metadata while keeping renderer pixels and ICC intact."""
    source, destination, exiftool = map(pathlib.Path, (source, destination, exiftool))
    if format not in {"jpg", "png", "webp"}:
        raise ValueError(f"Unsupported metadata format: {format}")
    if min(width, height, body_width, body_height) <= 0 or min(offset_x, offset_y) < 0:
        raise ValueError("Image and body dimensions must be positive and offsets non-negative")

    tags = _read(source, exiftool)
    structures, warnings = _regions(tags, width, height, body_width, body_height, offset_x, offset_y)
    spatial = [key for key in tags if "Region" in key or key.endswith(":SubjectArea")]
    supported = set(structures)
    for key in spatial:
        if key not in supported and key not in ("XMP-mwg-rs:RegionInfo", "XMP-MP:RegionInfoMP"):
            warnings.append(f"Unsupported spatial metadata omitted: {key}")

    excludes = list(_COPY_EXCLUDES)
    for key in spatial:
        if key not in supported:
            excludes.append(f"--{key}")

    if format == "webp":
        copy_groups = ["-EXIF:all", "-XMP"]
    else:
        copy_groups = ["-EXIF:all", "-XMP", "-IPTC:all"]

    # ExifTool does not copy IPTC's CodedCharacterSet with the IIM records.
    # With no marker, its fallback encoding can replace non-ASCII text while
    # writing. Re-encode copied IPTC strings as UTF-8 and mark the new record.
    charset_args = ["-IPTC:CodedCharacterSet=UTF8"] if format != "webp" and any(
        key.startswith("IPTC:") for key in tags
    ) else []

    _run(exiftool, "-tagsFromFile", str(copy_source), *copy_groups, *excludes, *charset_args,
         "-overwrite_original", str(destination), cwd=copy_cwd)
    cleanup = [f"-{key}=" for key in spatial if key not in supported]
    cleanup.extend(("-XMP-xmp:Thumbnails=", "-XMP-xmp:ThumbnailImage="))
    if cleanup:
        _run(exiftool, *cleanup, "-overwrite_original", str(destination))
    if format == "webp" and any(key.startswith("IPTC:") for key in tags):
        args_file = _iptc_args_file(exiftool)
        if args_file.is_file():
            warnings.extend(_warn_unmapped_iptc(args_file, tags))
        warning = _copy_webp_iptc(exiftool, copy_source, destination, tags, copy_cwd)
        if warning:
            warnings.append(warning)
    dim_args = _dimension_args(tags, width, height)
    if dim_args:
        _run(exiftool, *dim_args, "-overwrite_original", str(destination))
    _write_structures(exiftool, destination, structures)
    return warnings


def copy_metadata(source: pathlib.Path, destination: pathlib.Path, *, exiftool: pathlib.Path,
                  format: str, width: int, height: int, body_width: int, body_height: int,
                  offset_x: int, offset_y: int) -> list[str]:
    source, destination, exiftool = (pathlib.Path(source).resolve(), pathlib.Path(destination).resolve(),
                                     pathlib.Path(exiftool).resolve())
    if "%" not in str(source):
        return _copy_metadata(source, source, destination, exiftool=exiftool, format=format, width=width,
                              height=height, body_width=body_width, body_height=body_height,
                              offset_x=offset_x, offset_y=offset_y)
    with tempfile.TemporaryDirectory(prefix="exiftool-source-") as temp_dir:
        copy_source = pathlib.Path("metadata.tif")
        staged_source = pathlib.Path(temp_dir) / copy_source
        shutil.copyfile(source, staged_source)
        return _copy_metadata(source, copy_source, destination, exiftool=exiftool, format=format, width=width,
                              height=height, body_width=body_width, body_height=body_height,
                              offset_x=offset_x, offset_y=offset_y, copy_cwd=pathlib.Path(temp_dir))
