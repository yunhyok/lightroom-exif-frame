"""Real Q16/ExifTool checks; run: python -m unittest discover -s tests -p test_render.py -v."""
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "helper"))
import frame_helper as renderer


class RenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        magick = Path(os.environ.get("EXIF_FRAME_MAGICK", ROOT / "vendor/imagemagick/magick.exe"))
        exiftool = Path(os.environ.get("EXIF_FRAME_EXIFTOOL", ROOT / "vendor/exiftool/exiftool.exe"))
        if not magick.is_file() or not exiftool.is_file():
            raise unittest.SkipTest("Set EXIF_FRAME_MAGICK and EXIF_FRAME_EXIFTOOL to real tools")
        os.environ["EXIF_FRAME_MAGICK"], os.environ["EXIF_FRAME_EXIFTOOL"] = str(magick), str(exiftool)
        cls.magick, cls.exiftool = magick, exiftool
        color = Path(os.environ.get("WINDIR", "C:/Windows")) / "System32/spool/drivers/color"
        cls.srgb = color / "sRGB Color Space Profile.icm"
        cls.adobe, cls.prophoto = color / "AdobeRGB1998.icc", color / "ProPhoto.icm"
        cls.font = Path(os.environ.get("EXIF_FRAME_TEST_FONT", Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/malgun.ttf"))
        if not cls.srgb.is_file() or not cls.font.is_file():
            raise unittest.SkipTest("Tests require real sRGB ICC and Unicode font")

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="EXIF 프레임 검사 ")
        self.addCleanup(self.directory.cleanup)
        self.folder = Path(self.directory.name)
        self.width, self.height = 384, 256
        self.pixels = b"".join(struct.pack("<HHH", (i * 53 + 7) % 65536, (i * 97 + 11) % 65536, (i * 19 + 13) % 65536)
                               for i in range(self.width * self.height))
        raw = self.folder / "gradient.rgb"
        raw.write_bytes(self.pixels)
        self.input = self.folder / "Lightroom 렌더.tif"
        self.cmd(["-size", f"{self.width}x{self.height}", "-depth", "16", "-endian", "LSB", "RGB:" + str(raw), "-profile", str(self.srgb), str(self.input)])
        renderer.run(self.exiftool, ["-overwrite_original", "-Artist=Filtered Copyright", "-EXIF:Make=RICOH IMAGING COMPANY, LTD.", "-EXIF:Model=PENTAX K-3 Mark III", "-EXIF:ISO=1000", "-EXIF:FNumber=9", "-EXIF:ExposureTime=1/800", str(self.input)])
        self.job = dict(schema_version=1, input_path=str(self.input), output_path=str(self.folder / "완성.png"), result_path=str(self.folder / "result.json"),
                        format="png", bit_depth=16, color_space="sRGB", theme="strap", font_path=str(self.font),
                        metadata={"make": "RICOH IMAGING COMPANY, LTD.", "model": "PENTAX K-3 Mark III", "iso": "1000", "aperture": "9", "shutter": "1/800", "focal": "630", "focal35": "973", "lens": "HD PENTAX-D FA 150-450mm", "date": "2024/04/08 12:31:11"})

    def cmd(self, args, binary=False):
        return renderer.run(self.magick, args, binary=binary)

    def raw(self, image, crop=None, depth=16):
        args = [str(image)]
        if crop:
            args += ["-crop", crop, "+repage"]
        return self.cmd([*args, "-alpha", "off", "-depth", str(depth), "-endian", "LSB", "RGB:-"], True)

    def icc(self, image):
        return renderer.run(self.exiftool, ["-b", "-ICC_Profile", str(image)], binary=True)

    def test_rgb16_body_samples_and_profile_survive_frame(self):
        result = renderer.render(self.job)
        image = Path(result["output_path"])
        self.assertEqual((result["width"], result["height"]), (384, 284))
        self.assertEqual(self.raw(image, "384x256+0+0"), self.pixels)
        self.assertEqual(image.read_bytes()[24:26], bytes([16, 2]))  # PNG IHDR depth and RGB type.
        self.assertEqual(self.icc(image), self.icc(self.input))
        tags = json.loads(renderer.run(self.exiftool, ["-j", "-Artist", str(image)]))[0]
        self.assertEqual(tags["Artist"], "Filtered Copyright")

    def test_person_privacy_flag_preserves_normal_keywords_and_pixels(self):
        renderer.run(self.exiftool, ["-overwrite_original", "-XMP-iptcExt:PersonInImage=SDK Synthetic Person",
                                    "-XMP-dc:Subject=SDK Synthetic Person", str(self.input)])
        self.job["remove_person_info"] = "true"
        with self.assertRaisesRegex(ValueError, "remove_person_info must be boolean"):
            renderer.render(self.job)
        self.job.pop("remove_person_info")
        regular = renderer.render(self.job)
        tags = json.loads(renderer.run(self.exiftool, ["-j", "-PersonInImage", str(regular["output_path"])]))[0]
        self.assertEqual(tags["PersonInImage"], "SDK Synthetic Person")
        self.job["remove_person_info"] = True
        private = renderer.render(self.job)
        tags = json.loads(renderer.run(self.exiftool, ["-j", "-PersonInImage", "-Subject", "-Artist", str(private["output_path"])]))[0]
        self.assertNotIn("PersonInImage", tags)
        self.assertEqual(tags["Subject"], "SDK Synthetic Person")
        self.assertEqual(tags["Artist"], "Filtered Copyright")
        self.assertEqual(self.raw(private["output_path"], "384x256+0+0"), self.pixels)

    def test_none_and_numbered_output_are_atomic_no_overwrite(self):
        self.job["theme"] = "none"
        first = Path(renderer.render(self.job)["output_path"])
        before = first.read_bytes()
        second = Path(renderer.render(self.job)["output_path"])
        self.assertNotEqual(first, second)
        self.assertEqual(first.read_bytes(), before)
        self.assertEqual(self.raw(first), self.pixels)
        self.assertEqual(self.raw(second), self.pixels)

    def test_simple_has_all_side_margins_and_correct_metadata_offsets(self):
        self.job["theme"] = "simple"
        with patch.object(renderer.metadata, "copy_metadata", wraps=renderer.metadata.copy_metadata) as copy:
            result = renderer.render(self.job)
        padding = round(384 * 1.7 / 100)
        self.assertEqual((result["width"], result["height"]), (384 + 2 * padding, 284 + 2 * padding))
        self.assertEqual(self.raw(result["output_path"], f"384x256+{padding}+{padding}"), self.pixels)
        self.assertEqual(copy.call_args.kwargs["offset_x"], padding)
        self.assertEqual(copy.call_args.kwargs["offset_y"], padding)
        self.assertEqual(copy.call_args.kwargs["body_width"], 384)
        self.job["padding_percent"] = 0
        zero = renderer.render(self.job)
        self.assertEqual((zero["width"], zero["height"]), (384, 284))
        self.assertEqual(self.raw(zero["output_path"], "384x256+0+0"), self.pixels)

    def test_source_equal_requested_output_is_preserved_and_numbered(self):
        self.job["theme"] = "none"
        first = Path(renderer.render(self.job)["output_path"])
        renderer.run(self.exiftool, ["-overwrite_original", "-Artist=Private Original Artist", str(first)])
        original = first.read_bytes()
        self.job["source_path"] = self.job["output_path"] = str(first)
        second = Path(renderer.render(self.job)["output_path"])
        self.assertNotEqual(first, second)
        self.assertEqual(first.read_bytes(), original)
        self.assertIn("Filtered Copyright", renderer.run(self.exiftool, ["-Artist", str(second)]))

    def test_lossless_webp_matches_prepared_srgb8(self):
        self.job.update(theme="none", bit_depth=8)
        png = Path(renderer.render(self.job)["output_path"])
        self.job.update(format="webp", output_path=str(self.folder / "무손실.webp"), lossless=True, quality=1)
        webp = Path(renderer.render(self.job)["output_path"])
        self.assertIn(b"VP8L", webp.read_bytes())
        self.assertEqual(self.raw(webp, depth=8), self.raw(png, depth=8))
        self.assertEqual(self.icc(webp), self.icc(self.input))

    def test_wide_gamut_png16_and_jpg_keep_profile(self):
        for space, profile in (("AdobeRGB", self.adobe), ("ProPhotoRGB", self.prophoto)):
            if not profile.is_file():
                self.skipTest(f"Real {space} ICC unavailable")
            rendered = self.folder / (space + ".tif")
            self.cmd([str(self.input), "+profile", "*", "-profile", str(profile), "-depth", "16", str(rendered)])
            self.job.update(input_path=str(rendered), color_space=space, output_path=str(self.folder / (space + ".png")), format="png", bit_depth=16)
            image = Path(renderer.render(self.job)["output_path"])
            self.assertEqual(self.icc(image), profile.read_bytes())
            self.assertEqual(self.raw(image, "384x256+0+0"), self.pixels)
            self.job.update(output_path=str(self.folder / (space + ".jpg")), format="jpg", bit_depth=8)
            jpg = Path(renderer.render(self.job)["output_path"])
            self.assertEqual(self.icc(jpg), profile.read_bytes())
            self.assertEqual(renderer.image_info(self.magick, str(jpg))[:3], (384, 284, 8))

    def test_preview_converts_wide_gamut_after_full_layout(self):
        if not self.adobe.is_file():
            self.skipTest("Adobe RGB profile unavailable")
        wide = self.folder / "wide.tif"
        self.cmd([str(self.input), "-profile", str(self.adobe), "-depth", "16", str(wide)])
        self.job.update(input_path=str(wide), color_space="AdobeRGB", preview=True, preview_max_size=192)
        result = renderer.render(self.job)
        image = Path(result["output_path"])
        self.assertEqual((result["width"], result["height"]), (192, 142))
        self.assertEqual(image.read_bytes()[24], 8)
        target = renderer.srgb_profile(self.magick)
        self.assertEqual(self.icc(image), target.read_bytes())
        self.job.update(preview=False, output_path=str(self.folder / "full-wide.png"))
        full = Path(renderer.render(self.job)["output_path"])
        reference = self.cmd([str(full), "-profile", str(target), "-resize", "192x192>", "-alpha", "off", "-depth", "8", "RGB:-"], True)
        self.assertEqual(self.raw(image, depth=8), reference)

    def test_korean_literal_text_logo_and_corrupt_logo_cleanup(self):
        logo = self.folder / "공식 로고.png"
        self.cmd(["-size", "80x20", "xc:none", "-fill", "red", "-draw", "rectangle 0,0 60,15", str(logo)])
        self.job.update(logos={"pentax": str(logo)}, templates=["@not-a-file %[fx:1/0] 100% 한글\n두 번째 줄", "날짜", "{make} {model}", "{lens}"])
        result = renderer.render(self.job)
        self.assertTrue(result["ok"])
        self.assertEqual(self.raw(result["output_path"], "384x256+0+0"), self.pixels)
        logo.write_bytes(b"not png")
        existing = set(self.folder.iterdir())
        with self.assertRaisesRegex(ValueError, "PNG"):
            renderer.render(self.job)
        self.assertEqual(existing, set(self.folder.iterdir()))

    def test_plain_brand_fallback_and_logo_percentage_change_visible_pixels(self):
        self.job["templates"] = ["", "", "", ""]
        brand = Path(renderer.render(self.job)["output_path"])
        area = self.raw(brand, "384x28+0+256", depth=8)
        original_metadata = self.job["metadata"]
        self.job["metadata"] = dict(original_metadata, make="", model="")
        no_brand = renderer.render(self.job)
        empty = self.raw(no_brand["output_path"], "384x28+0+256", depth=8)
        self.assertNotEqual(area, empty, "Canonical brand text was not drawn")
        self.job["metadata"] = original_metadata
        logo = self.folder / "registered-brand.png"
        self.cmd(["-size", "80x20", "xc:red", "-profile", str(self.srgb), str(logo)])
        self.job["logos"] = {"pentax": str(logo)}
        counts = []
        for percent in (6, 20):
            self.job["logo_percent"] = percent
            result = renderer.render(self.job)
            pixels = self.raw(result["output_path"], "384x28+0+256", depth=8)
            counts.append(sum(pixels[i] > 240 and pixels[i + 1] < 10 and pixels[i + 2] < 10 for i in range(0, len(pixels), 3)))
        self.assertGreater(counts[1], counts[0] * 2, "Logo control did not enlarge visible logo")

    def test_template_token_and_pentax_resolution(self):
        job = renderer.validate(self.job)
        warnings = []
        texts, brand = renderer.visible_text(job, self.exiftool, warnings)
        self.assertEqual(brand, "PENTAX")
        self.assertEqual(texts[0], "ISO1000 973mm F9 1/800s")
        self.assertEqual(texts[2], "PENTAX K-3 Mark III")
        job["focal_mode"] = "actual"
        self.assertIn("630mm", renderer.visible_text(job, self.exiftool, [])[0][0])
        job["metadata"]["artist"] = "Catalog Artist"
        job["templates"] = ["{focal}", "{artist}", "{make} {model}", "{lens}"]
        texts = renderer.visible_text(job, self.exiftool, [])[0]
        self.assertEqual(texts[0], "630")
        self.assertEqual(texts[1], "Catalog Artist")
        job["artist"] = "Override Artist"
        self.assertEqual(renderer.visible_text(job, self.exiftool, [])[0][1], "Override Artist")

    def test_webp_dimension_limit_fails_before_encoding(self):
        wide = self.folder / "too-wide.tif"
        self.cmd(["-size", "16384x2", "gradient:", "-profile", str(self.srgb), "-depth", "16", str(wide)])
        self.job.update(input_path=str(wide), theme="none", format="webp", bit_depth=8, output_path=str(self.folder / "too-wide.webp"))
        with self.assertRaisesRegex(ValueError, "16383"):
            renderer.render(self.job)
        self.assertFalse(Path(self.job["output_path"]).exists())

    def test_invalid_jobs_and_atomic_failure_result(self):
        for changes in ({"format": "webp", "color_space": "AdobeRGB", "bit_depth": 8},
                        {"format": "jpg", "bit_depth": 16}, {"quality": float("nan")},
                        {"background_color": "red;file"}, {"templates": ["one"]},
                        {"output_path": "relative.png"}, {"input_path": str(self.folder / "missing.tif")}):
            with self.assertRaises(ValueError):
                renderer.validate(dict(self.job, **changes))
        self.job["quality"] = 0
        jobfile = self.folder / "job.json"
        jobfile.write_text(json.dumps(self.job), encoding="utf-8-sig")
        self.assertEqual(renderer.main(["--job", str(jobfile)]), 1)
        result = json.loads(Path(self.job["result_path"]).read_text(encoding="utf-8"))
        self.assertFalse(result["ok"])
        self.assertFalse(Path(self.job["output_path"]).exists())
        self.job["result_path"] = str(self.folder / "missing" / "result.json")
        jobfile.write_text(json.dumps(self.job), encoding="utf-8")
        with patch.object(sys, "stderr", None):
            self.assertEqual(renderer.main(["--job", str(jobfile)]), 1)


if __name__ == "__main__":
    unittest.main()
