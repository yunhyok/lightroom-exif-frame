"""Small ExifTool integration checks for the metadata helper."""

from __future__ import annotations

import json
import hashlib
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

from helper.metadata import copy_metadata, read_display_metadata, run_exiftool


ROOT = pathlib.Path(__file__).resolve().parents[1]


def _tool(env: str, bundled: pathlib.Path, name: str) -> pathlib.Path | None:
    configured = os.environ.get(env)
    if configured and pathlib.Path(configured).is_file():
        return pathlib.Path(configured)
    if bundled.is_file():
        return bundled
    found = shutil.which(name)
    return pathlib.Path(found) if found else None


EXIFTOOL = _tool("EXIF_FRAME_EXIFTOOL", ROOT / "vendor" / "exiftool" / "exiftool.exe", "exiftool")
MAGICK = _tool("EXIF_FRAME_MAGICK", ROOT / "vendor" / "imagemagick" / "magick.exe", "magick")


@unittest.skipUnless(EXIFTOOL and MAGICK, "ExifTool and ImageMagick are needed for metadata integration tests")
class MetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.directory = pathlib.Path(self.temp.name)
        self.source = self.directory / "원본.tif"
        subprocess.run([str(MAGICK), "-size", "100x80", "xc:white", str(self.source)], check=True,
                       capture_output=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write(self, image: pathlib.Path, tags: dict[str, object]) -> None:
        payload = self.directory / "tags.json"
        payload.write_text(json.dumps([{"SourceFile": str(image), **tags},], ensure_ascii=False), encoding="utf-8")
        run_exiftool(EXIFTOOL, "-struct", f"-j={payload}", "-overwrite_original", str(image))

    def _read(self, image: pathlib.Path) -> dict[str, object]:
        result = run_exiftool(EXIFTOOL, "-j", "-G1", "-a", "-s", "-struct", "-n", str(image))
        return json.loads(result.stdout)[0]

    def test_display_metadata_returns_only_visible_frame_fields(self) -> None:
        self._write(self.source, {
            "EXIF:Make": "RICOH IMAGING COMPANY, LTD.", "EXIF:Model": "PENTAX K-3 Mark III",
            "EXIF:ISO": 1000, "EXIF:FNumber": 9, "EXIF:ExposureTime": "1/800",
            "EXIF:FocalLength": "630 mm", "EXIF:FocalLengthIn35mmFormat": 973,
            "EXIF:DateTimeOriginal": "2024:04:08 12:31:11", "EXIF:GPSLatitude": 37.0,
            "XMP-dc:Title": "ignored", "XMP-aux:Lens": "Test Lens",
        })
        metadata = read_display_metadata(self.source, EXIFTOOL)
        self.assertEqual(set(metadata), {"make", "model", "lens", "iso", "aperture", "shutter", "focal", "focal35", "date"})
        self.assertNotIn("GPSLatitude", metadata)
        self.assertEqual(metadata["lens"], "Test Lens")
        self.assertEqual(metadata["shutter"], "1/800")

    def test_copy_preserves_lightroom_metadata_and_maps_mwg_region(self) -> None:
        self._write(self.source, {
            "EXIF:Make": "PENTAX", "EXIF:GPSLatitude": 37.5, "EXIF:GPSLongitude": 127.0,
            "EXIF:Orientation": 6, "EXIF:ImageWidth": 100, "EXIF:ImageHeight": 80,
            "XMP-dc:Description-ko-KR": "한국어 설명", "XMP-dc:Title-en-US": "A title",
            "XMP-dc:Subject": ["한국어", "주제"], "XMP-lr:HierarchicalSubject": ["장소|경기도|화성시"],
            "XMP-mwg-rs:RegionInfo": {
                "AppliedToDimensions": {"W": 100, "H": 80, "Unit": "pixel"},
                "RegionList": [{"Area": {"X": 0.5, "Y": 0.5, "W": 0.2, "H": 0.2,
                                       "Unit": "normalized"}, "Name": "Person", "Type": "Face"}],
            },
            "XMP-MP:RegionInfoMP": {
                "Regions": [{"PersonDisplayName": "Person", "Rectangle": "0.2,0.25,0.4,0.5"}],
            },
        })
        output = self.directory / "frame.jpg"
        profile = pathlib.Path(r"C:\Windows\System32\spool\drivers\color\sRGB Color Space Profile.icm")
        create = [str(MAGICK), "-size", "120x100", "xc:white"]
        if profile.is_file():
            create += ["-profile", str(profile)]
        subprocess.run([*create, str(output)], check=True, capture_output=True)
        icc_before = run_exiftool(EXIFTOOL, "-b", "-ICC_Profile", str(output), binary=True).stdout
        warnings = copy_metadata(self.source, output, exiftool=EXIFTOOL, format="jpg", width=120, height=100,
                                 body_width=100, body_height=80, offset_x=10, offset_y=10)
        icc_after = run_exiftool(EXIFTOOL, "-b", "-ICC_Profile", str(output), binary=True).stdout
        tags = self._read(output)
        self.assertFalse(warnings)
        self.assertEqual(hashlib.sha256(icc_before).digest(), hashlib.sha256(icc_after).digest())
        self.assertIn("GPSLatitude", " ".join(tags))
        self.assertIn("GPSLongitude", " ".join(tags))
        self.assertIn("한국어 설명", str(tags.values()))
        self.assertIn("장소|경기도|화성시", str(tags.values()))
        self.assertEqual(next(value for key, value in tags.items() if key.endswith(":Orientation")), 1)
        self.assertEqual(next(value for key, value in tags.items() if key.endswith(":ImageWidth")), 120)
        self.assertEqual(next(value for key, value in tags.items() if key.endswith(":ImageHeight")), 100)
        region = tags["XMP-mwg-rs:RegionInfo"]["RegionList"][0]["Area"]
        self.assertAlmostEqual(float(region["X"]), 0.5)
        self.assertAlmostEqual(float(region["Y"]), 0.5)
        self.assertAlmostEqual(float(region["W"]), 1 / 6)
        self.assertEqual(tags["XMP-mwg-rs:RegionInfo"]["AppliedToDimensions"]["W"], 120)
        rect = [float(value) for value in tags["XMP-MP:RegionInfoMP"]["Regions"][0]["Rectangle"].split(",")]
        self.assertAlmostEqual(rect[0], 0.25)
        self.assertAlmostEqual(rect[1], 0.3)
        self.assertAlmostEqual(rect[2], 1 / 3)
        self.assertAlmostEqual(rect[3], 0.4)

    def test_literal_percent_source_path_copies_artist_and_caption(self) -> None:
        source = self.directory / "렌더 [16bit] & %.tif"
        subprocess.run([str(MAGICK), "-size", "100x80", "xc:white", str(source)], check=True, capture_output=True)
        self._write(source, {"EXIF:Artist": "Yunhy", "XMP-dc:Description": "Percent path caption"})
        output = self.directory / "percent-path.jpg"
        subprocess.run([str(MAGICK), "-size", "120x100", "xc:white", str(output)], check=True, capture_output=True)
        percent_temp = self.directory / "temp % directory"
        percent_temp.mkdir()
        old_tempdir = tempfile.tempdir
        tempfile.tempdir = str(percent_temp)
        try:
            copy_metadata(source, output, exiftool=EXIFTOOL, format="jpg", width=120, height=100,
                          body_width=100, body_height=80, offset_x=10, offset_y=10)
        finally:
            tempfile.tempdir = old_tempdir
        tags = self._read(output)
        self.assertIn("Yunhy", str(tags.values()))
        self.assertIn("Percent path caption", str(tags.values()))

    def test_copy_does_not_restore_gps_or_face_regions_removed_by_lightroom(self) -> None:
        self._write(self.source, {"EXIF:Make": "PENTAX", "XMP-dc:Title": "Retained"})
        output = self.directory / "filtered.jpg"
        subprocess.run([str(MAGICK), "-size", "120x100", "xc:white", str(output)], check=True, capture_output=True)
        copy_metadata(self.source, output, exiftool=EXIFTOOL, format="jpg", width=120, height=100,
                      body_width=100, body_height=80, offset_x=10, offset_y=10)
        tags = self._read(output)
        self.assertFalse(any("GPS" in key or "RegionInfo" in key for key in tags))
        self.assertIn("Retained", str(tags.values()))

    def test_remove_person_info_filters_typed_person_and_regions_only(self) -> None:
        self._write(self.source, {
            "EXIF:Artist": "Photographer",
            "XMP-dc:Description": "Caption stays",
            "XMP-dc:Rights": "Copyright stays",
            "XMP-dc:Subject": ["wildlife", "shorebird"],
            "XMP-iptcExt:PersonInImage": ["Ada Lovelace"],
            "XMP-iptcExt:PersonInImageWDetails": [{"PersonId": ["person-1"]}],
            "XMP-mwg-rs:RegionInfo": {
                "AppliedToDimensions": {"W": 100, "H": 80, "Unit": "pixel"},
                "RegionList": [{"Area": {"X": 0.5, "Y": 0.5, "W": 0.2, "H": 0.2,
                                         "Unit": "normalized"}, "Name": "Ada", "Type": "Face"}],
            },
            "XMP-MP:RegionInfoMP": {"Regions": [{"PersonDisplayName": "Ada", "Rectangle": "0.2,0.2,0.3,0.3"}]},
        })
        for extension in ("jpg", "png", "webp"):
            with self.subTest(extension=extension):
                output = self.directory / f"no-person-info.{extension}"
                subprocess.run([str(MAGICK), "-size", "120x100", "xc:white", str(output)], check=True,
                               capture_output=True)
                warnings = copy_metadata(self.source, output, exiftool=EXIFTOOL, format=extension,
                                         width=120, height=100, body_width=100, body_height=80,
                                         offset_x=10, offset_y=10, remove_person_info=True)
                tags = self._read(output)
                self.assertEqual(warnings, [])
                self.assertFalse(any(key.startswith("XMP-iptcExt:PersonInImage") for key in tags))
                self.assertFalse(any("RegionInfo" in key or key.endswith(":ImageRegion") for key in tags))
                self.assertEqual(tags.get("XMP-dc:Description"), "Caption stays")
                self.assertEqual(tags.get("XMP-dc:Rights"), "Copyright stays")
                self.assertEqual(tags.get("XMP-dc:Subject"), ["wildlife", "shorebird"])
                self.assertEqual(tags.get("IFD0:Artist"), "Photographer")

    def test_copy_uses_only_filtered_tiff_for_jpg_png_and_webp(self) -> None:
        self._write(self.source, {"XMP-dc:Description": "Filtered TIFF only"})
        for extension in ("jpg", "png", "webp"):
            with self.subTest(extension=extension):
                output = self.directory / f"filtered.{extension}"
                subprocess.run([str(MAGICK), "-size", "120x100", "xc:white", str(output)], check=True,
                               capture_output=True)
                copy_metadata(self.source, output, exiftool=EXIFTOOL, format=extension, width=120, height=100,
                              body_width=100, body_height=80, offset_x=10, offset_y=10)
                tags = self._read(output)
                self.assertIn("Filtered TIFF only", str(tags.values()))
                self.assertFalse(any(key.endswith(":Make") or key.endswith(":Model") for key in tags))

    def test_copy_updates_xmp_dimensions_and_drops_thumbnail_and_unsupported_region_unit(self) -> None:
        self._write(self.source, {
            "XMP-tiff:ImageWidth": 100, "XMP-tiff:ImageHeight": 80,
            "XMP-xmp:Thumbnails": [{"Format": "JPEG", "Width": 5, "Height": 4, "Image": "old preview"}],
            "XMP-mwg-rs:RegionInfo": {
                "AppliedToDimensions": {"W": 100, "H": 80, "Unit": "pixel"},
                "RegionList": [{"Area": {"X": 50, "Y": 40, "W": 20, "H": 16,
                                       "Unit": "pixel"}, "Name": "Person", "Type": "Face"}],
            },
        })
        run_exiftool(EXIFTOOL, "-XMP-tiff:Orientation#=6", "-overwrite_original", str(self.source))
        output = self.directory / "xmp-clean.png"
        subprocess.run([str(MAGICK), "-size", "120x100", "xc:white", str(output)], check=True, capture_output=True)
        warnings = copy_metadata(self.source, output, exiftool=EXIFTOOL, format="png", width=120, height=100,
                                 body_width=100, body_height=80, offset_x=10, offset_y=10)
        tags = self._read(output)
        self.assertTrue(any("Unsupported spatial metadata omitted" in warning for warning in warnings))
        self.assertFalse(any("RegionInfo" in key or "Thumbnail" in key for key in tags))
        self.assertEqual(tags.get("XMP-tiff:Orientation"), 1)
        self.assertEqual(tags.get("XMP-tiff:ImageWidth"), 120)
        self.assertEqual(tags.get("XMP-tiff:ImageHeight"), 100)

    def test_copy_keeps_non_exif_copyright_without_creating_exif(self) -> None:
        self._write(self.source, {"XMP-dc:Rights": "Copyright Yunhy", "IPTC:CopyrightNotice": "Copyright Yunhy"})
        output = self.directory / "copyright.png"
        subprocess.run([str(MAGICK), "-size", "120x100", "xc:white", str(output)], check=True, capture_output=True)
        copy_metadata(self.source, output, exiftool=EXIFTOOL, format="png", width=120, height=100,
                      body_width=100, body_height=80, offset_x=10, offset_y=10)
        tags = self._read(output)
        self.assertIn("Copyright Yunhy", str(tags.values()))
        self.assertFalse(any(key.startswith("EXIF:") for key in tags))

    def test_copy_preserves_utf8_iptc_character_set_and_values(self) -> None:
        values = {
            "IPTC:CodedCharacterSet": "UTF8",
            "IPTC:ObjectName": "SDK 한국어 日本語 fixture",
            "IPTC:Keywords": ["SDK 테스트", "日本語", "왜가리"],
            "IPTC:By-line": "Yunhyok SDK 테스트",
            "IPTC:Caption-Abstract": "한국어 촬영 설명 · 日本語の撮影説明",
        }
        self._write(self.source, values)
        source_tags = self._read(self.source)
        for extension in ("jpg", "png"):
            with self.subTest(extension=extension):
                output = self.directory / f"utf8-iptc.{extension}"
                subprocess.run([str(MAGICK), "-size", "120x100", "xc:white", str(output)], check=True,
                               capture_output=True)
                copy_metadata(self.source, output, exiftool=EXIFTOOL, format=extension, width=120, height=100,
                              body_width=100, body_height=80, offset_x=10, offset_y=10)
                tags = self._read(output)
                self.assertEqual(tags.get("IPTC:CodedCharacterSet"), source_tags.get("IPTC:CodedCharacterSet"))
                self.assertEqual(tags.get("IPTC:ObjectName"), values["IPTC:ObjectName"])
                self.assertEqual(tags.get("IPTC:Keywords"), values["IPTC:Keywords"])
                self.assertEqual(tags.get("IPTC:By-line"), values["IPTC:By-line"])
                self.assertEqual(tags.get("IPTC:Caption-Abstract"), values["IPTC:Caption-Abstract"])

    def test_copy_marks_unmarked_iptc_as_utf8(self) -> None:
        self._write(self.source, {"IPTC:ObjectName": "ASCII title", "IPTC:Keywords": ["one", "two"]})
        self.assertNotIn("IPTC:CodedCharacterSet", self._read(self.source))
        output = self.directory / "unmarked-iptc.jpg"
        subprocess.run([str(MAGICK), "-size", "120x100", "xc:white", str(output)], check=True,
                       capture_output=True)
        copy_metadata(self.source, output, exiftool=EXIFTOOL, format="jpg", width=120, height=100,
                      body_width=100, body_height=80, offset_x=10, offset_y=10)
        tags = self._read(output)
        self.assertEqual(tags.get("IPTC:CodedCharacterSet"), "\x1b%G")
        self.assertEqual(tags.get("IPTC:ObjectName"), "ASCII title")

    def test_webp_converts_iim_title_when_xmp_title_missing(self) -> None:
        self._write(self.source, {"IPTC:CodedCharacterSet": "UTF8", "IPTC:ObjectName": "IIM title",
                                  "IPTC:Keywords": ["하늘", "바다"], "IPTC:Contact": "photo@example.test",
                                  "IPTC:DateCreated": "2024:04:08", "IPTC:TimeCreated": "12:31:11",
                                  "IPTC:DigitalCreationDate": "2024:04:09",
                                  "IPTC:DigitalCreationTime": "13:45:00"})
        output = self.directory / "frame.webp"
        subprocess.run([str(MAGICK), "-size", "120x100", "xc:white", str(output)], check=True, capture_output=True)
        warnings = copy_metadata(self.source, output, exiftool=EXIFTOOL, format="webp", width=120, height=100,
                                 body_width=100, body_height=80, offset_x=10, offset_y=10)
        tags = self._read(output)
        self.assertEqual(warnings, ["WebP IPTC field not mapped to XMP: IPTC:Contact"])
        self.assertIn("IIM title", str(tags.get("XMP-dc:Title")))
        self.assertIn("하늘", str(tags.values()))
        self.assertIn("2024:04:08", str(tags.get("XMP-photoshop:DateCreated")))
        self.assertIn("12:31:11", str(tags.get("XMP-photoshop:DateCreated")))
        self.assertIn("2024:04:09", str(tags.get("XMP-xmp:CreateDate")))
        self.assertIn("13:45:00", str(tags.get("XMP-xmp:CreateDate")))

    def test_webp_keeps_native_xmp_over_iim_fallback(self) -> None:
        self._write(self.source, {"IPTC:ObjectName": "IIM title", "XMP-dc:Title-en-US": "Native XMP title"})
        output = self.directory / "native.webp"
        subprocess.run([str(MAGICK), "-size", "120x100", "xc:white", str(output)], check=True, capture_output=True)
        copy_metadata(self.source, output, exiftool=EXIFTOOL, format="webp", width=120, height=100,
                      body_width=100, body_height=80, offset_x=10, offset_y=10)
        tags = self._read(output)
        self.assertIn("Native XMP title", str(tags.get("XMP-dc:Title-en-US")))


if __name__ == "__main__":
    unittest.main()
