"""Create three metadata-free public examples from a photograph supplied by its owner."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "helper"))
import frame_helper


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("photograph", type=Path, help="User-supplied source photograph; never copied into the repository")
    arguments = parser.parse_args()
    source = arguments.photograph.resolve(strict=True)
    if not source.is_file():
        parser.error("photograph must be a file")
    os.environ.setdefault("EXIF_FRAME_MAGICK", str(ROOT / "vendor/imagemagick/magick.exe"))
    os.environ.setdefault("EXIF_FRAME_EXIFTOOL", str(ROOT / "vendor/exiftool/exiftool.exe"))
    magick = frame_helper.tool("EXIF_FRAME_MAGICK", "imagemagick/magick.exe")
    exiftool = frame_helper.tool("EXIF_FRAME_EXIFTOOL", "exiftool/exiftool.exe")
    srgb = frame_helper.srgb_profile(magick)
    public = ROOT / "docs/images"
    public.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="EXIF 공개 예시 ") as temporary:
        work = Path(temporary)
        body = work / "rendered.tif"
        # Render at reference body width before framing; resize the completed public image later.
        frame_helper.run(magick, [str(source), "-auto-orient", "-profile", str(srgb), "-resize", "1920x1920>", "-strip", "-profile", str(srgb), "-depth", "16", str(body)])
        for name, theme, appearance in (("strap-light", "strap", "light"), ("strap-dark", "strap", "dark"), ("simple", "simple", "light")):
            job = dict(schema_version=1, input_path=str(body), source_path=str(source), output_path=str(work / (name + ".jpg")),
                       result_path=str(work / (name + "-result.json")), format="jpg", bit_depth=8, color_space="sRGB", quality=95,
                       theme=theme, appearance=appearance, focal_mode="equivalent", metadata={}, logos={},
                       templates=frame_helper.DEFAULT_TEMPLATES, font_percent=1.65, band_percent=7.3, padding_percent=1.7, logo_percent=10)
            result = frame_helper.render(job)
            final = work / (name + "-public.jpg")
            frame_helper.run(magick, [result["output_path"], "-resize", "1600x1600>", "-strip", "-quality", "90", str(final)])
            frame_helper.run(exiftool, ["-config", "", "-charset", "filename=UTF8", "-all=", "-overwrite_original", str(final)])
            width, height, *_ = frame_helper.image_info(magick, str(final))
            if max(width, height) > 1600:
                raise RuntimeError("Public example exceeded 1600 px")
            tags = json.loads(frame_helper.run(exiftool, ["-config", "", "-j", "-EXIF:all", "-IPTC:all", "-XMP:all", "-ICC_Profile", "-Comment", "-Photoshop:all", str(final)]))[0]
            if set(tags) != {"SourceFile"}:
                raise RuntimeError(f"Public example retained embedded metadata: {sorted(tags)}")
            destination = public / (name + ".jpg")
            # The completed public derivative is the only photograph artifact placed in docs.
            handle, stage_name = tempfile.mkstemp(prefix=".example-", suffix=".jpg", dir=public)
            os.close(handle)
            stage = Path(stage_name)
            try:
                stage.write_bytes(final.read_bytes())
                stage.replace(destination)
            finally:
                stage.unlink(missing_ok=True)
            print(json.dumps({"image": str(destination.relative_to(ROOT)), "width": width, "height": height,
                              "bytes": destination.stat().st_size, "embedded_metadata": "none", "warnings": result["warnings"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
