"""Frozen-package smoke under a restricted environment; this is not a pristine-OS test."""
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "helper"))
import metadata


class PackageSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = ROOT / "LightroomExifFrame.lrplugin/bin"
        if os.name != "nt" or not (source / "frame-helper.exe").is_file():
            raise unittest.SkipTest("Build the Windows frozen package before this smoke test")
        cls.temporary = tempfile.TemporaryDirectory(prefix="EXIF 패키지 [한글] & 100% @ ")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.folder = Path(cls.temporary.name)
        cls.bundle = cls.folder / "압축 해제 [패키지] & % @"
        shutil.copytree(source, cls.bundle)
        cls.helper = cls.bundle / "frame-helper.exe"
        cls.magick = ROOT / "vendor/imagemagick/magick.exe"
        cls.exiftool = ROOT / "vendor/exiftool/exiftool.exe"
        windir = Path(os.environ.get("SystemRoot", "C:/Windows"))
        cls.icc = windir / "System32/spool/drivers/color/sRGB Color Space Profile.icm"
        cls.font = Path(os.environ.get("EXIF_FRAME_TEST_FONT", windir / "Fonts/malgun.ttf"))
        if not all(path.is_file() for path in (cls.magick, cls.exiftool, cls.icc, cls.font)):
            raise unittest.SkipTest("Vendor validators, real sRGB ICC and Unicode font are required")
        cls.environment = {key: value for key, value in os.environ.items()
                           if key.upper() not in {"PATH", "PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "PERL5LIB", "PERL5OPT"}
                           and not key.upper().startswith("EXIF_FRAME_")}
        cls.environment["SystemRoot"] = str(windir)
        cls.environment["PATH"] = str(windir / "System32")
        cls.environment.update({"LANG": "C", "LC_ALL": "C"})
        cls.width, cls.height = 512, 320
        cls.pixels = b"".join(struct.pack("<HHH", (i * 53 + 7) % 65536, (i * 97 + 11) % 65536, (i * 19 + 13) % 65536)
                              for i in range(cls.width * cls.height))
        raw = cls.folder / "입력 [16bit] & %.rgb"
        raw.write_bytes(cls.pixels)
        cls.input = cls.folder / "렌더 [16bit] & %.tif"
        cls.validator(cls.magick, ["-size", "512x320", "-depth", "16", "-endian", "LSB", "RGB:" + str(raw), "-profile", str(cls.icc), str(cls.input)])
        cls.validator(cls.exiftool, ["-config", "", "-overwrite_original", "-Artist=Filtered Package Copyright", str(cls.input)])

    @staticmethod
    def validator(executable, arguments, *, binary=False):
        if executable.stem.lower().startswith("exiftool"):
            result = metadata.run_exiftool(executable, *arguments, binary=binary)
            return result.stdout
        result = subprocess.run([str(executable), *arguments], shell=False, capture_output=True, timeout=180,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode:
            raise AssertionError(result.stderr.decode("utf-8", "replace"))
        return result.stdout if binary else result.stdout.decode("utf-8", "replace")

    def invoke(self, job, name):
        jobfile = self.folder / (name + " [작업] & %.json")
        jobfile.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8-sig")
        completed = subprocess.run([str(self.helper), "--job", str(jobfile)], cwd=self.folder,
                                   env=self.environment, shell=False, capture_output=True, timeout=180,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.assertTrue(Path(job["result_path"]).is_file(), completed.stderr.decode("utf-8", "replace"))
        return completed.returncode, json.loads(Path(job["result_path"]).read_text(encoding="utf-8"))

    def test_frozen_outputs_and_failure_with_no_development_runtime_paths(self):
        self.assertFalse(any(key.upper().startswith("EXIF_FRAME_") for key in self.environment))
        self.assertNotIn("PYTHONHOME", self.environment)
        self.assertNotIn("PYTHONPATH", self.environment)
        self.assertEqual(self.environment["PATH"], str(Path(self.environment["SystemRoot"]) / "System32"))
        outputs = {}
        for fmt, depth in (("jpg", 8), ("png", 16), ("webp", 8)):
            job = dict(schema_version=1, input_path=str(self.input), output_path=str(self.folder / ("결과 [파일] & %." + fmt)),
                       result_path=str(self.folder / (fmt + "-result.json")), format=fmt, bit_depth=depth, color_space="sRGB",
                       quality=95, lossless=fmt == "webp", theme="strap", font_path=str(self.font),
                       templates=["@literal 100% 한글", "{date}", "{make} {model}", "{lens}"],
                       metadata={"make": "RICOH IMAGING COMPANY, LTD.", "model": "PENTAX K-3 Mark III", "lens": "HD PENTAX-D FA 150-450mm", "date": "2024/04/08"})
            code, result = self.invoke(job, fmt)
            self.assertEqual(code, 0, result)
            self.assertTrue(result["ok"], result)
            self.assertEqual((result["width"], result["height"]), (512, 357))
            output = Path(result["output_path"])
            outputs[fmt] = output
            data = output.read_bytes()
            if fmt == "jpg":
                self.assertTrue(data.startswith(b"\xff\xd8\xff"))
            elif fmt == "png":
                self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
                self.assertEqual(data[24:26], bytes((16, 2)))
                pixels = self.validator(self.magick, [str(output), "-crop", "512x320+0+0", "+repage", "-depth", "16", "-endian", "LSB", "RGB:-"], binary=True)
                self.assertEqual(pixels, self.pixels)
            else:
                self.assertEqual(data[:4], b"RIFF")
                self.assertEqual(data[8:12], b"WEBP")
                self.assertIn(b"VP8L", data)
            profile = self.validator(self.exiftool, ["-config", "", "-b", "-ICC_Profile", str(output)], binary=True)
            self.assertEqual(profile, self.icc.read_bytes())
            artist = json.loads(self.validator(self.exiftool, ["-config", "", "-j", "-Artist", str(output)]))[0]
            self.assertIn("Artist", artist, f"{fmt} metadata result: {artist}")
            self.assertEqual(artist["Artist"], "Filtered Package Copyright")
        png8 = self.validator(self.magick, [str(outputs["png"]), "-alpha", "off", "-depth", "8", "RGB:-"], binary=True)
        webp8 = self.validator(self.magick, [str(outputs["webp"]), "-alpha", "off", "-depth", "8", "RGB:-"], binary=True)
        self.assertEqual(webp8, png8)
        failed_output = self.folder / "실패.png"
        bad = dict(job, format="png", bit_depth=16, output_path=str(failed_output), result_path=str(self.folder / "failure-result.json"), quality=0)
        code, result = self.invoke(bad, "failure")
        self.assertNotEqual(code, 0)
        self.assertFalse(result["ok"])
        self.assertIn("quality", result["error"])
        self.assertFalse(failed_output.exists())
        self.assertFalse(list(self.folder.glob(".exif-frame-*")))


if __name__ == "__main__":
    unittest.main()
