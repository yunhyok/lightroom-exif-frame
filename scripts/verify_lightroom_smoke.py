"""Independently inspect the files produced by tests/lightroom_smoke.lua.

The Lightroom-filtered TIFF is the metadata and rendered-pixel authority.
Metadata modes: Adobe Lightroom Classic SDK 13 Guide, p. 68:
https://ioconsolerykerprodcdn.azureedge.net/static/installers/lr/sdk/2022/cross_platform/v13/doc/Lightroom%20Classic%20SDK%20Guide_1655133965.pdf
No Lightroom UI success flag substitutes for the file checks below.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_IDS = {f"{n:02}" for n in range(1, 14)}
CAMERA = {"Make", "Model", "LensModel", "LensInfo", "Lens", "LensID", "ExposureTime", "FNumber", "ISO",
          "ShutterSpeedValue", "ApertureValue", "ExposureProgram", "ExposureCompensation", "MeteringMode",
          "Flash", "FocalLength", "FocalLengthIn35mmFormat", "SerialNumber", "BodySerialNumber", "LensSerialNumber"}
GROUPS = {
    "camera": lambda key: key.split(":")[-1] in CAMERA and key.split(":")[0] in {"IFD0", "ExifIFD", "XMP-tiff", "XMP-exif", "XMP-exifEX", "XMP-aux"},
    "gps": lambda key: key.startswith("GPS:") or key.split(":")[-1].startswith("GPS"),
    "copyright": lambda key: key.split(":")[-1] in {"Copyright", "CopyrightNotice", "Rights", "UsageTerms"},
    "contact": lambda key: key.split(":")[-1] in {"Artist", "Creator", "By-line", "CreatorContactInfo"},
    "caption": lambda key: key.split(":")[-1] in {"ImageDescription", "Description", "Caption-Abstract", "UserComment"},
    "title": lambda key: key.split(":")[-1] in {"Title", "ObjectName"},
    "keywords": lambda key: key.split(":")[-1] in {"Subject", "Keywords", "HierarchicalSubject"},
    "person": lambda key: key.split(":")[-1] in {"PersonInImage", "PersonShown"},
}


def run(executable, args, binary=False):
    if executable.name.lower() == "magick.exe":
        limits = ["-limit", "memory", "512MiB", "-limit", "map", "1GiB", "-limit", "disk", "2GiB", "-limit", "time", "120"]
        args = [args[0], *limits, *args[1:]] if args and args[0] == "identify" else [*limits, *args]
    result = subprocess.run([str(executable), *map(str, args)], shell=False, capture_output=True, timeout=180,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip()[:1500])
    return result.stdout if binary else result.stdout.decode("utf-8", "replace")


def read_tags(exiftool, path):
    return json.loads(run(exiftool, ["-config", "", "-charset", "filename=UTF8", "-j", "-G1", "-a", "-s", "-n", "-struct", str(path)]))[0]


def category(tags, name):
    return {key: value for key, value in tags.items() if GROUPS[name](key)}


def atoms(value):
    if isinstance(value, dict):
        return [atom for item in value.values() for atom in atoms(item)]
    if isinstance(value, list):
        return [atom for item in value for atom in atoms(item)]
    return [json.dumps(value, ensure_ascii=False, sort_keys=True)]


def values(tags):
    return set(atom for value in tags.values() for atom in atoms(value))


def unmatched(expected, observed, numeric=False):
    def equivalent(first, second):
        if first == second:
            return True
        if numeric:
            try:
                return math.isclose(float(json.loads(first)), float(json.loads(second)), rel_tol=1e-6, abs_tol=1e-12)
            except (ValueError, TypeError):
                pass
        return False
    return sorted(value for value in expected if not any(equivalent(value, other) for other in observed))


def info(magick, path, tiff=False):
    image = "TIFF:" + str(path) + "[0]" if tiff else str(path)
    text = run(magick, ["identify", "-ping", "-format", "%w|%h|%z|%m|%[icc:description]", image])
    width, height, depth, fmt, description = text.split("|", 4)
    return {"width": int(width), "height": int(height), "depth": int(depth), "format": fmt, "icc_description": description}


def raw_pixels(magick, path, depth, crop=None, tiff=False):
    image = "TIFF:" + str(path) + "[0]" if tiff else str(path)
    args = [image]
    if crop:
        args.extend(["-crop", crop, "+repage"])
    args.extend(["-alpha", "off", "-depth", str(depth), "-endian", "LSB", "RGB:-"])
    return run(magick, args, binary=True)


def checked_path(value, directory):
    path = Path(value).resolve(strict=True)
    if not path.is_file() or not path.is_relative_to(directory):
        raise ValueError("Evidence file is outside its run directory: " + str(path))
    return path


def public_path(path):
    path = Path(path).resolve()
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.name


def sanitize(value):
    if isinstance(value, dict):
        return {key: sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        value = value.replace(str(ROOT), ".").replace(ROOT.as_posix(), ".")
        if os.environ.get("USERPROFILE"):
            value = value.replace(os.environ["USERPROFILE"], "%USERPROFILE%")
        return value
    return value


def verify(evidence_path, magick, exiftool):
    evidence = json.loads(evidence_path.read_text(encoding="utf-8-sig"))
    directory = evidence_path.parent.resolve()
    summary = {"schema_version": 1, "kind": "independent-actual-lightroom-file-verification",
               "evidence_path": public_path(evidence_path), "ok": False, "cases": [], "failures": [], "limitations": []}

    def global_check(condition, message):
        if not condition:
            summary["failures"].append(message)

    global_check(evidence.get("schema_version") == 1 and evidence.get("kind") == "manual-actual-lightroom-sdk", "Unexpected harness evidence schema")
    global_check(bool(evidence.get("completed_utc")), "Harness did not finish")
    global_check(not evidence.get("cancelled") and not evidence.get("harness_error"), "Harness cancelled or raised an error")
    global_check(evidence.get("fixture_setup", {}).get("ok") is True, "Catalog metadata fixture setup failed")
    rows = evidence.get("results", [])
    ids = [str(row.get("id", "")).split("-", 1)[0] for row in rows]
    global_check(set(ids) == EXPECTED_IDS and len(ids) == 13, "Expected exactly all 13 harness cases")
    fixture = evidence.get("catalog_fixture", {})
    seeds = evidence.get("synthetic_seed", {})
    gps_seeded = seeds.get("gps", {}).get("ok") is True
    person_seeded = seeds.get("personShown", {}).get("ok") is True
    summary["synthetic_seed"] = seeds
    if not gps_seeded:
        summary["limitations"].append("Synthetic GPS seed failed or is unavailable: no-GPS case verifies absence only, not removal of seeded coordinates.")
    if not person_seeded:
        summary["limitations"].append("Synthetic personShown seed failed or is unavailable: person filtering is not proven with populated data.")
    summary["limitations"].append("No actual face-region coordinates were seeded; Lightroom face-region UI/removal remains unverified.")
    summary["limitations"].append("File verification covers rendered TIFFs and outputs; it does not verify Lightroom UI controls or a pristine Windows installation.")
    for row in rows:
        item = {"id": row.get("id"), "format": row.get("format"), "metadata_mode": row.get("metadata_mode"),
                "checks": [], "failures": [], "metadata": {}}
        summary["cases"].append(item)

        def check(condition, name, detail=None):
            if condition:
                item["checks"].append(name)
            else:
                item["failures"].append(name + (": " + str(detail) if detail is not None else ""))

        try:
            check(row.get("ok") is True, "harness case success", row.get("error"))
            helper = row.get("helper", {})
            check(helper.get("ok") is True, "helper success", helper.get("error"))
            item["helper_warnings"] = helper.get("warnings", [])
            tiff = checked_path(row["filtered_tiff"], directory)
            output = checked_path(helper["output_path"], directory)
            body = info(magick, tiff, tiff=True)
            final = info(magick, output)
            item["tiff"] = {"path": public_path(tiff), **body}
            item["output"] = {"path": public_path(output), **final}
            tiff_header = tiff.read_bytes()[:4]
            check(tiff_header in (b"II*\0", b"MM\0*", b"II+\0", b"MM\0+"), "actual TIFF signature")
            check(body["depth"] == 16 and body["format"] == "TIFF", "actual TIFF16 decode")
            source_icc = run(exiftool, ["-config", "", "-b", "-ICC_Profile", str(tiff)], binary=True)
            final_icc = run(exiftool, ["-config", "", "-b", "-ICC_Profile", str(output)], binary=True)
            profile = {"sRGB": ("srgb",), "AdobeRGB": ("adobergb",), "ProPhotoRGB": ("prophoto", "romm")}.get(row.get("profile"), ())
            description = re.sub(r"[^a-z0-9]", "", body["icc_description"].lower())
            check(len(source_icc) >= 128 and bool(profile) and any(name in description for name in profile), "TIFF ICC matches requested profile", body["icc_description"])
            check(final_icc == source_icc and bool(final_icc), "final ICC bytes preserved")
            item["icc_sha256"] = hashlib.sha256(source_icc).hexdigest()
            settings = row.get("export_settings", {})
            is_simple = settings.get("ef_theme") == "simple"
            offset = max(0, round(body["width"] * float(settings.get("ef_paddingPercent", 1.7)) / 100)) if is_simple else 0
            band = max(1, round(body["width"] * float(settings.get("ef_bandPercent", 7.3)) / 100))
            expected_size = (body["width"] + 2 * offset, body["height"] + band + 2 * offset)
            check((final["width"], final["height"]) == expected_size, "frame dimensions", {"actual": [final["width"], final["height"]], "expected": expected_size})
            check((helper.get("width"), helper.get("height")) == expected_size, "helper dimensions agree with files")
            item["body_offset"] = [offset, offset]
            crop = f"{body['width']}x{body['height']}+{offset}+{offset}"
            data = output.read_bytes()
            fmt = row.get("format")
            if fmt == "png":
                check(data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR" and data[24:26] == bytes((16, 2)), "actual PNG16 RGB signature")
                source_pixels = raw_pixels(magick, tiff, 16, tiff=True)
                final_pixels = raw_pixels(magick, output, 16, crop)
                check(source_pixels == final_pixels, "PNG body pixels exactly equal rendered TIFF16")
                item["body_pixels_sha256"] = hashlib.sha256(source_pixels).hexdigest()
            elif fmt == "webp":
                check(data[:4] == b"RIFF" and data[8:12] == b"WEBP" and b"VP8L" in data, "actual lossless WebP signature")
                check(settings.get("ef_lossless") is True, "lossless requested")
                source_pixels = raw_pixels(magick, tiff, 8, tiff=True)
                check(source_pixels == raw_pixels(magick, output, 8, crop), "WebP body pixels exactly equal quantized TIFF8")
                item["body_pixels_sha256"] = hashlib.sha256(source_pixels).hexdigest()
            elif fmt == "jpg":
                check(data[:3] == b"\xff\xd8\xff" and final["format"] == "JPEG", "actual JPEG signature")
            else:
                check(False, "known output format", fmt)
            source_tags, final_tags = read_tags(exiftool, tiff), read_tags(exiftool, output)
            for name in GROUPS:
                source_group, final_group = category(source_tags, name), category(final_tags, name)
                item["metadata"][name] = {"tiff_tag_count": len(source_group), "final_tag_count": len(final_group),
                                          "tiff_values_sha256": hashlib.sha256(json.dumps(sorted(values(source_group)), ensure_ascii=False).encode("utf-8")).hexdigest()}
                # WebP may transport IPTC via XMP; verify values across namespaces rather than falsely requiring an IPTC container.
                missing = unmatched(values(source_group), values(final_group), numeric=name in {"camera", "gps"})
                extra = unmatched(values(final_group), values(source_group), numeric=name in {"camera", "gps"})
                check(not missing, name + " metadata values preserved", missing)
                check(not extra, name + " metadata has no source-external values", extra)
            for key, value in final_tags.items():
                leaf = key.split(":")[-1]
                if leaf in {"Orientation"}:
                    check(value == 1, "final metadata orientation normal", {key: value})
                if leaf in {"ExifImageWidth", "ImageWidth", "PixelXDimension"} and key.split(":")[0] not in {"File", "PNG", "JPEG", "RIFF"}:
                    check(value == final["width"], "metadata output width corrected", {key: value})
                if leaf in {"ExifImageHeight", "ImageHeight", "PixelYDimension"} and key.split(":")[0] not in {"File", "PNG", "JPEG", "RIFF"}:
                    check(value == final["height"], "metadata output height corrected", {key: value})
            item["tiff_orientation"] = {key: value for key, value in source_tags.items() if key.endswith(":Orientation")}
            mode = row.get("metadata_mode")
            if mode in {"copyrightOnly", "copyrightAndContactOnly", "allExceptCameraInfo"}:
                check(not category(source_tags, "camera"), "Lightroom mode omitted camera metadata")
            elif mode == "all":
                check(bool(category(source_tags, "camera")), "Lightroom all mode retained camera metadata")
            else:
                check(False, "known Lightroom metadata mode", mode)
            if row.get("remove_gps"):
                check(not category(source_tags, "gps") and not category(final_tags, "gps"), "removeGPS mode has no GPS tags")
                item["gps_removal_evidence"] = "synthetic catalog seed removal" if gps_seeded else "absence only; no GPS seed"
            elif mode == "all" and gps_seeded:
                gps = category(source_tags, "gps")
                latitudes = [value for key, value in gps.items() if key.endswith(":GPSLatitude")]
                longitudes = [value for key, value in gps.items() if key.endswith(":GPSLongitude")]
                check(any(isinstance(value, (int, float)) and abs(value - .125) < .00001 for value in latitudes)
                      and any(isinstance(value, (int, float)) and abs(value - .25) < .00001 for value in longitudes), "synthetic GPS retained by all mode")
            if row.get("remove_person"):
                person_values = values(category(source_tags, "person")) | values(category(source_tags, "keywords"))
                check(not category(source_tags, "person") and not any("SDK Synthetic Person" in value for value in person_values), "remove-person mode has no seeded person data or keyword")
            elif mode == "all" and person_seeded:
                check(any("SDK Synthetic Person" in value for value in values(category(source_tags, "person")) | values(category(source_tags, "keywords"))), "synthetic person data retained by all mode")
            if mode in {"all", "copyrightAndContactOnly", "allExceptCameraInfo"}:
                for key in ("creatorEmail", "creatorPhone"):
                    if seeds.get(key, {}).get("ok") is True:
                        check(json.dumps(seeds[key]["observed"], ensure_ascii=False) in values(category(source_tags, "contact")), "synthetic " + key + " retained by metadata mode")
            if fixture.get("copyright"):
                check(json.dumps(fixture["copyright"], ensure_ascii=False) in values(category(source_tags, "copyright")), "catalog copyright present in filtered TIFF")
            if mode in {"all", "allExceptCameraInfo"}:
                for name in ("caption", "title"):
                    if fixture.get(name):
                        check(json.dumps(fixture[name], ensure_ascii=False) in values(category(source_tags, name)), "catalog " + name + " present in filtered TIFF")
                hier = {key: value for key, value in source_tags.items() if key.endswith(":HierarchicalSubject")}
                check(any("SDK 테스트|日本語|왜가리" in str(value) for value in hier.values()), "catalog hierarchical keyword present in filtered TIFF")
            item["ok"] = not item["failures"]
        except Exception as error:
            item["failures"].append(str(error))
            item["ok"] = False
    virtual = evidence.get("virtual_copy", {})
    crop = virtual.get("applied_crop", {})
    develop = virtual.get("develop_settings", {})
    summary["virtual_copy"] = {"applied_crop": crop, "develop_orientation": develop.get("orientation")}
    global_check(all(isinstance(crop.get(key), (int, float)) for key in ("CropLeft", "CropRight", "CropTop", "CropBottom"))
                 and 0 < crop.get("CropRight", 0) - crop.get("CropLeft", 0) < 1
                 and 0 < crop.get("CropBottom", 0) - crop.get("CropTop", 0) < 1, "Virtual copy has no actual nontrivial applied crop")
    global_check(bool(crop) and all(develop.get(key) == value for key, value in crop.items()), "Applied crop does not match virtual-copy develop readback")
    master = next((case.get("tiff") for case in summary["cases"] if str(case["id"]).startswith("01-")), None)
    rotated = next((case.get("tiff") for case in summary["cases"] if str(case["id"]).startswith("12-")), None)
    if master and rotated:
        summary["virtual_copy"]["master_tiff_size"] = [master["width"], master["height"]]
        summary["virtual_copy"]["virtual_tiff_size"] = [rotated["width"], rotated["height"]]
        global_check(abs(rotated["width"] / rotated["height"] - master["height"] / master["width"]) < .002
                     and (master["width"] > master["height"]) != (rotated["width"] > rotated["height"]),
                     "Actual virtual TIFF dimensions do not demonstrate quarter-turn rotation")
    else:
        global_check(False, "Missing actual master/virtual TIFF geometry")
    summary["numeric_metadata_tolerance"] = {"relative": 1e-6, "absolute": 1e-12, "groups": ["camera", "gps"]}
    summary["case_count"] = len(summary["cases"])
    summary["passed_count"] = sum(case["ok"] for case in summary["cases"])
    summary["ok"] = not summary["failures"] and summary["passed_count"] == 13
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", nargs="?", type=Path, help="evidence.json; defaults to newest workspace harness run")
    parser.add_argument("--output", type=Path, default=ROOT / "work/live-validation.json")
    args = parser.parse_args()
    try:
        candidates = list((ROOT / "work/lr-sdk-output").glob("*/evidence.json"))
        evidence = args.evidence.resolve(strict=True) if args.evidence else max(candidates, key=lambda path: path.stat().st_mtime).resolve()
        magick, exiftool = ROOT / "vendor/imagemagick/magick.exe", ROOT / "vendor/exiftool/exiftool.exe"
        summary = verify(evidence, magick, exiftool)
    except Exception as error:
        summary = {"schema_version": 1, "kind": "independent-actual-lightroom-file-verification", "ok": False,
                   "failures": [str(error)], "cases": [], "case_count": 0, "passed_count": 0}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    summary = sanitize(summary)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": summary["ok"], "cases": summary["case_count"], "passed": summary["passed_count"],
                      "output": public_path(args.output), "failures": summary["failures"],
                      "failed_cases": [{"id": case["id"], "failures": case["failures"]} for case in summary["cases"] if not case["ok"]]}, ensure_ascii=False))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
