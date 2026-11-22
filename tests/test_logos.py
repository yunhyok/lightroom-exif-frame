"""Tests for brand/era catalog integrity, release-year CI detection, and pure-vector SVG rasterization."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "helper"))
import logos

DATA = ROOT / "helper" / "data"
ASSETS = ROOT / "helper" / "assets" / "logos"


class LogoTests(unittest.TestCase):
    def test_catalog_integrity_and_pure_vector_svgs(self):
        brands_raw = json.loads((DATA / "brands.json").read_text(encoding="utf-8"))["brands"]
        cameras_raw = json.loads((DATA / "cameras.json").read_text(encoding="utf-8"))["brands"]

        self.assertEqual(len(brands_raw), 61)
        total_eras = 0
        total_models = 0
        seen_svgs: set[Path] = set()

        for brand in brands_raw:
            eras = brand["eras"]
            self.assertGreaterEqual(len(eras), 1, brand["id"])
            total_eras += len(eras)

            # Check era non-overlap (Leica allows documented overlap where range fits chronologically)
            prev_end: int | None = None
            for idx, era in enumerate(eras):
                start = int(era["start_year"])
                end = int(era["end_year"]) if era.get("end_year") is not None else None
                if end is not None:
                    self.assertGreaterEqual(end, start, f"{brand['id']} {era['id']}")
                if idx > 0 and prev_end is not None and brand["id"] != "leica":
                    self.assertGreater(start, prev_end, f"Overlapping eras in {brand['id']}: {era['id']}")
                prev_end = end

                svg_path = ASSETS / era["svg"]
                self.assertTrue(svg_path.is_file(), f"Missing SVG: {svg_path}")
                seen_svgs.add(svg_path.resolve())
                svg_text = svg_path.read_text(encoding="utf-8")
                self.assertIn("<svg", svg_text.lower())
                self.assertNotIn("<text", svg_text.lower(), f"Disallowed <text> in {era['svg']}")
                self.assertNotIn("<image", svg_text.lower(), f"Disallowed <image> in {era['svg']}")

            models = cameras_raw.get(brand["id"], [])
            self.assertGreaterEqual(len(models), 1, f"No models for {brand['id']}")
            total_models += len(models)

        self.assertEqual(total_eras, 93)
        self.assertEqual(len(seen_svgs), 93)
        self.assertGreaterEqual(total_models, 1100)

    def test_brand_disambiguation(self):
        cases = [
            (("RICOH IMAGING COMPANY, LTD.", "PENTAX K-3 Mark III"), "pentax"),
            (("RICOH", "GR IIIx"), "ricoh"),
            (("RICOH", "RICOH THETA X"), "ricoh-theta"),
            (("OLYMPUS CORPORATION", "E-M1MarkIII"), "olympus"),
            (("OM Digital Solutions", "OM-1MarkII"), "om-system"),
            (("SONY", "ILCE-7RM5"), "sony-alpha"),
            (("SONY", "DSC-RX100M7"), "sony"),
            (("Panasonic", "DC-S5M2"), "lumix"),
            (("Panasonic", "PV-GS500"), "panasonic"),
            (("Arashi Vision", "Insta360 X4"), "insta360"),
            (("DJI", "FC8482"), "dji"),
            (("EASTMAN KODAK COMPANY", "KODAK C875 ZOOM DIGITAL CAMERA"), "kodak"),
            (("DJI", "L2D-20c"), "hasselblad"),
            (("LGE", "Nexus 5"), "google"),
            (("Lucky-GoldStar", "GC-10"), "goldstar"),
        ]
        for (make, model), expected in cases:
            self.assertEqual(logos.resolve_brand(make, model), expected, f"Failed: {(make, model)}")

    def test_era_transitions_and_unknown_model_fallback(self):
        cases = [
            # Kodak C875 (2006) stays 2006 CI even for 2026 capture year
            (("EASTMAN KODAK COMPANY", "KODAK C875 ZOOM DIGITAL CAMERA"), "kodak", "2006", 2006),
            (("EASTMAN KODAK COMPANY", "KODAK DC4800"), "kodak", "1987", 2000),
            (("JK Imaging", "KODAK PIXPRO FZ55"), "kodak", "2016", 2022),
            # Canon & Nikon & Fujifilm & Sigma & Samsung & Apple & Xiaomi & GoPro
            (("Canon", "Canon EOS D30"), "canon", "1956", 2000),
            (("NIKON CORPORATION", "NIKON D100"), "nikon", "1988", 2002),
            (("NIKON CORPORATION", "NIKON Z 8"), "nikon", "2003", 2023),
            (("FUJIFILM", "FinePix F30"), "fujifilm", "1980", 2006),
            (("FUJIFILM", "X100VI"), "fujifilm", "2006", 2024),
            (("SIGMA", "SIGMA SD14"), "sigma", "1961", 2007),
            (("SIGMA", "SIGMA fp"), "sigma", "2012", 2019),
            (("SIGMA", "SIGMA BF"), "sigma", "2025", 2025),
            (("samsung", "GT-I9300"), "samsung", "1993", 2012),
            (("samsung", "SM-S928N"), "samsung", "2015", 2024),
            (("Apple", "iPhone 4S"), "apple", "2007", 2011),
            (("Apple", "iPhone 16 Pro"), "apple", "2013", 2024),
            (("Xiaomi", "24031PN60G"), "xiaomi", "2021", 2024),
            (("GoPro", "HERO13 Black"), "gopro", "2012", 2024),
        ]
        for (make, model), exp_brand, exp_era, exp_year in cases:
            res = logos.resolve_logo(make, model, logo_mode="auto_era")
            self.assertEqual(res.brand_id, exp_brand, (make, model))
            self.assertEqual(res.era_id, exp_era, (make, model))
            self.assertEqual(res.detected_year, exp_year, (make, model))
            self.assertEqual(res.logo_source, "builtin_svg")

        # Unknown future model falls back to latest CI era
        fut = logos.resolve_logo("NIKON CORPORATION", "NIKON Z 99 Mark IV", logo_mode="auto_era")
        self.assertEqual((fut.brand_id, fut.era_id, fut.detected_year, fut.year_source), ("nikon", "2003", None, "unknown_latest_fallback"))

        # Algorithmic year detection for unlisted pattern models
        y_iphone, src_iphone, _ = logos.detect_release_year("apple", "iPhone 27 Ultra")
        self.assertGreaterEqual(y_iphone or 0, 2030)
        self.assertEqual(src_iphone, "model_pattern")

    def test_logo_modes_and_user_override_precedence(self):
        latest = logos.resolve_logo("NIKON CORPORATION", "NIKON D100", logo_mode="auto_latest")
        self.assertEqual((latest.brand_id, latest.era_id, latest.year_source), ("nikon", "2003", "latest_policy"))

        manual = logos.resolve_logo(
            "NIKON CORPORATION", "NIKON Z 8",
            logo_mode="manual_era", manual_brand="canon", manual_era="1935",
        )
        self.assertEqual((manual.brand_id, manual.era_id, manual.year_source), ("canon", "1935", "manual_era"))

        txt = logos.resolve_logo("EASTMAN KODAK COMPANY", "KODAK C875 ZOOM DIGITAL CAMERA", logo_mode="text_only")
        self.assertEqual((txt.brand_id, txt.logo_source), ("kodak", "text_fallback"))

        none_mode = logos.resolve_logo("Canon", "Canon EOS R5", logo_mode="none")
        self.assertEqual(none_mode.logo_source, "none")

        with tempfile.TemporaryDirectory() as tmp:
            override = Path(tmp) / "custom_kodak.svg"
            override.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 40"><rect width="100" height="40" fill="#ff0000"/></svg>', encoding="utf-8")
            over = logos.resolve_logo("EASTMAN KODAK COMPANY", "KODAK C875", user_logos={"kodak": override})
            self.assertEqual(over.logo_source, "user_override")
            self.assertEqual(over.user_logo_path, override)

    def test_rasterize_all_93_svgs_across_styles_and_polarities(self):
        brands_raw = json.loads((DATA / "brands.json").read_text(encoding="utf-8"))["brands"]
        count = 0
        for brand in brands_raw:
            for era in brand["eras"]:
                svg_path = ASSETS / era["svg"]
                for style in ("brand", "mono"):
                    for is_dark in (False, True):
                        png = logos.rasterize_svg_to_png(
                            svg_path, 220, 90,
                            is_dark=is_dark,
                            style=style,
                            text_color="#f4f4f4" if is_dark else "#161616",
                            background_color="#171717" if is_dark else "#ffffff",
                            secondary_color="#bbbbbb" if is_dark else "#555555",
                        )
                        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"), f"Invalid PNG for {era['svg']}")
                        self.assertGreater(len(png), 150, f"Empty PNG for {era['svg']}")
                        count += 1
        self.assertEqual(count, 93 * 4)

    def test_sony_wide_aspect_and_nikon_dark_badge_black_lettering(self):
        import struct
        import zlib

        sony_svg = (ASSETS / "sony" / "1973.svg").read_text(encoding="utf-8")
        vw, vh = logos._svg_dimensions(sony_svg)
        self.assertGreaterEqual(vw / vh, 3.5)

        nikon_png = logos.rasterize_svg_to_png(
            ASSETS / "nikon" / "2003.svg",
            200,
            200,
            is_dark=True,
            style="brand",
            text_color="#f4f4f4",
            background_color="#171717",
            secondary_color="#bbbbbb",
        )
        # Decode PNG RGBA scanlines and verify pure-black pixels remain inside the yellow badge
        pos = 8
        w = h = 0
        idat = bytearray()
        while pos + 8 <= len(nikon_png):
            length = struct.unpack(">I", nikon_png[pos:pos + 4])[0]
            ctype = nikon_png[pos + 4:pos + 8]
            chunk = nikon_png[pos + 8:pos + 8 + length]
            pos += 12 + length
            if ctype == b"IHDR":
                w, h = struct.unpack(">II", chunk[:8])
            elif ctype == b"IDAT":
                idat.extend(chunk)
        raw = zlib.decompress(bytes(idat))
        stride = w * 4
        prev = bytearray(stride)
        dark_pixels = 0
        off = 0
        for _ in range(h):
            ft = raw[off]
            off += 1
            row = bytearray(raw[off:off + stride])
            off += stride
            for i in range(stride):
                a = row[i - 4] if i >= 4 else 0
                b = prev[i]
                c = prev[i - 4] if i >= 4 else 0
                if ft == 1:
                    row[i] = (row[i] + a) & 0xFF
                elif ft == 2:
                    row[i] = (row[i] + b) & 0xFF
                elif ft == 3:
                    row[i] = (row[i] + ((a + b) >> 1)) & 0xFF
                elif ft == 4:
                    p = a + b - c
                    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                    row[i] = (row[i] + (a if pa <= pb and pa <= pc else (b if pb <= pc else c))) & 0xFF
            prev = row
            for x in range(0, stride, 4):
                if row[x + 3] > 200 and row[x] < 30 and row[x + 1] < 30 and row[x + 2] < 30:
                    dark_pixels += 1
        self.assertGreater(dark_pixels, 200, "Yellow Nikon badge must keep crisp black text on dark frames")


if __name__ == "__main__":
    unittest.main()
