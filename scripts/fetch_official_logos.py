"""Fetch (optional), sanitize, color-normalize, and tightly crop all 93 official vector SVGs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zlib

import resvg_py

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "build" / "logo-cache" / "raw"
ASSETS_DIR = ROOT / "helper" / "assets" / "logos"
SOURCES_JSON = Path(__file__).resolve().parent / "logo_sources.json"
UA = "LightroomExifFrame/0.2.2 (https://github.com/yunhyok/lightroom-exif-frame; contact@yunhyok.dev) python-urllib"

NAMED_HEX = {
    "black": "#000000",
    "white": "#FFFFFF",
    "red": "#FF0000",
    "green": "#008000",
    "blue": "#0000FF",
    "yellow": "#FFFF00",
    "navy": "#000080",
    "gray": "#808080",
    "grey": "#808080",
    "silver": "#C0C0C0",
}


def _fmt(v: float) -> str:
    return f"{v:.4f}".rstrip("0").rstrip(".") or "0"


def _expand_hex(h: str) -> str:
    h = h.strip().upper()
    if re.fullmatch(r"#[0-9A-F]{3}", h):
        return f"#{h[1]*2}{h[2]*2}{h[3]*2}"
    return h


def _parse_color_token(val: str) -> str | None:
    v = val.strip()
    low = v.lower()
    if low in NAMED_HEX:
        return NAMED_HEX[low]
    if re.fullmatch(r"#[0-9a-fA-F]{3,6}", v):
        return _expand_hex(v)
    m = re.fullmatch(r"rgb\(\s*([0-9.]+%?)\s*,\s*([0-9.]+%?)\s*,\s*([0-9.]+%?)\s*\)", low)
    if m:
        nums = []
        for g in m.groups():
            if g.endswith("%"):
                nums.append(max(0, min(255, round(float(g[:-1]) * 2.55))))
            else:
                nums.append(max(0, min(255, round(float(g)))))
        return f"#{nums[0]:02X}{nums[1]:02X}{nums[2]:02X}"
    return None


def _rgb_metrics(hex6: str) -> tuple[int, float]:
    r, g, b = (int(hex6[i:i + 2], 16) for i in (1, 3, 5))
    chroma = max(r, g, b) - min(r, g, b)
    lum = 0.2126 * (r / 255.0) + 0.7152 * (g / 255.0) + 0.0722 * (b / 255.0)
    return chroma, lum


def _png_alpha_bbox(png_bytes: bytes) -> tuple[int, int, int, int, int, int] | None:
    if not png_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    pos = 8
    w = h = bit_depth = color_type = 0
    idat = bytearray()
    while pos + 8 <= len(png_bytes):
        length = struct.unpack(">I", png_bytes[pos:pos + 4])[0]
        ctype = png_bytes[pos + 4:pos + 8]
        chunk = png_bytes[pos + 8:pos + 8 + length]
        pos += 12 + length
        if ctype == b"IHDR":
            w, h, bit_depth, color_type = struct.unpack(">IIBB", chunk[:10])
        elif ctype == b"IDAT":
            idat.extend(chunk)
        elif ctype == b"IEND":
            break
    if color_type != 6 or bit_depth != 8 or not w or not h:
        return None
    raw = zlib.decompress(bytes(idat))
    stride = w * 4
    prev = bytearray(stride)
    min_x, min_y, max_x, max_y = w, h, -1, -1

    def paeth(a: int, b: int, c: int) -> int:
        p = a + b - c
        pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
        return a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)

    offset = 0
    for y in range(h):
        ftype = raw[offset]
        offset += 1
        row = bytearray(raw[offset:offset + stride])
        offset += stride
        if ftype == 1:
            for i in range(4, stride):
                row[i] = (row[i] + row[i - 4]) & 0xFF
        elif ftype == 2:
            for i in range(stride):
                row[i] = (row[i] + prev[i]) & 0xFF
        elif ftype == 3:
            for i in range(stride):
                a = row[i - 4] if i >= 4 else 0
                row[i] = (row[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:
            for i in range(stride):
                a = row[i - 4] if i >= 4 else 0
                c = prev[i - 4] if i >= 4 else 0
                row[i] = (row[i] + paeth(a, prev[i], c)) & 0xFF
        prev = row
        alphas = row[3::4]
        if max(alphas) > 2:
            if y < min_y:
                min_y = y
            if y > max_y:
                max_y = y
            for x in range(w):
                if alphas[x] > 2:
                    if x < min_x:
                        min_x = x
                    break
            for x in range(w - 1, -1, -1):
                if alphas[x] > 2:
                    if x > max_x:
                        max_x = x
                    break
    if max_x < min_x or max_y < min_y:
        return None
    return w, h, min_x, min_y, max_x, max_y


def _strip_bloat(svg: str, strip_ids: list[str] | None = None) -> str:
    entities = {
        "&ns_svg;": "http://www.w3.org/2000/svg",
        "&ns_xlink;": "http://www.w3.org/1999/xlink",
        "&ns_flows;": "http://ns.adobe.com/Flows/1.0/",
        "&ns_extend;": "http://ns.adobe.com/Extensibility/1.0/",
        "&ns_ai;": "http://ns.adobe.com/AdobeIllustrator/10.0/",
        "&ns_graphs;": "http://ns.adobe.com/Graphs/1.0/",
        "&ns_vars;": "http://ns.adobe.com/Variables/1.0/",
        "&ns_imrep;": "http://ns.adobe.com/ImageReplacement/1.0/",
        "&ns_sfw;": "http://ns.adobe.com/SaveForWeb/1.0/",
        "&ns_custom;": "http://ns.adobe.com/GenericCustomNamespace/1.0/",
        "&ns_adobe_xpath;": "http://ns.adobe.com/XPath/1.0/",
    }
    for k, v in entities.items():
        svg = svg.replace(k, v)
    svg = svg.lstrip("\ufeff")
    svg = re.sub(r"<\?xml[^>]*\?>\s*", "", svg, flags=re.I)
    svg = re.sub(r"<!DOCTYPE\b[^>\[]*(?:\[.*?\]\s*)?>\s*", "", svg, flags=re.I | re.S)
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.S)
    svg = re.sub(r"<metadata\b[^>]*>.*?</metadata>", "", svg, flags=re.S | re.I)
    svg = re.sub(r"<title\b[^>]*>.*?</title>", "", svg, flags=re.S | re.I)
    svg = re.sub(r"<desc\b[^>]*>.*?</desc>", "", svg, flags=re.S | re.I)
    svg = re.sub(r"<sodipodi:namedview\b[^>]*?(?:/>|>.*?</sodipodi:namedview>)", "", svg, flags=re.S | re.I)
    svg = re.sub(r"<inkscape:perspective\b[^>]*?(?:/>|>.*?</inkscape:perspective>)", "", svg, flags=re.S | re.I)
    # Remove empty Inkscape text/tspan leftovers
    svg = re.sub(r"<text\b[^>]*>(?:\s|<tspan\b[^>]*?(?:/>|>\s*</tspan>))*</text>", "", svg, flags=re.S | re.I)
    svg = re.sub(r'\s+(?:inkscape|sodipodi):[a-zA-Z0-9_-]+\s*=\s*(?:"[^"]*"|\'[^\']*\')', "", svg)
    svg = re.sub(r'\s+xmlns:(?:inkscape|sodipodi|dc|cc|rdf|a|x|i|graph)\s*=\s*(?:"[^"]*"|\'[^\']*\')', "", svg)
    svg = re.sub(r'\s+i:[a-zA-Z0-9_-]+\s*=\s*(?:"[^"]*"|\'[^\']*\')', "", svg)

    for sid in strip_ids or []:
        esc = re.escape(sid)
        svg = re.sub(rf"<[a-zA-Z0-9:]+\b[^>]*\bid\s*=\s*([\"']){esc}\1[^>]*/>", "", svg, flags=re.S)
        svg = re.sub(rf"<([a-zA-Z0-9:]+)\b[^>]*\bid\s*=\s*([\"']){esc}\2[^>]*>.*?</\1>", "", svg, flags=re.S)

    low = svg.lower()
    if "<text" in low or "<tspan" in low:
        raise ValueError("SVG contains non-empty <text> elements")
    if "<image" in low:
        raise ValueError("SVG contains embedded <image> bitmap")
    if re.search(r'(?:xlink:)?href\s*=\s*["\']https?://', svg, re.I):
        raise ValueError("SVG contains external http(s) reference")
    return svg.strip()


def _normalize_viewbox_header(svg: str) -> tuple[str, float, float, float, float]:
    m = re.search(r"<svg\b([^>]*)>", svg, re.S | re.I)
    if not m:
        raise ValueError("Missing <svg> root")
    attrs = m.group(1)
    vb_m = re.search(r'\bviewBox\s*=\s*(["\'])([^"\']+)\1', attrs, re.I)
    w_m = re.search(r'\bwidth\s*=\s*(["\'])([0-9.eE+-]+)\s*([a-z%]*)\1', attrs, re.I)
    h_m = re.search(r'\bheight\s*=\s*(["\'])([0-9.eE+-]+)\s*([a-z%]*)\1', attrs, re.I)
    if vb_m:
        parts = [float(p) for p in re.split(r"[,\s]+", vb_m.group(2).strip()) if p]
        vx, vy, vw, vh = parts[0], parts[1], max(1e-3, parts[2]), max(1e-3, parts[3])
    elif w_m and h_m and w_m.group(3) != "%" and h_m.group(3) != "%":
        vx, vy = 0.0, 0.0
        vw, vh = max(1e-3, float(w_m.group(2))), max(1e-3, float(h_m.group(2)))
    else:
        raise ValueError("SVG missing usable viewBox or width/height")

    new_attrs = re.sub(r'\s*\b(?:viewBox|width|height)\s*=\s*(["\'])[^"\']*\1', "", attrs, flags=re.I)
    new_attrs = f' viewBox="{_fmt(vx)} {_fmt(vy)} {_fmt(vw)} {_fmt(vh)}" width="{_fmt(vw)}" height="{_fmt(vh)}"' + new_attrs
    return svg[:m.start(1)] + new_attrs + svg[m.end(1):], vx, vy, vw, vh


def _normalize_colors(
    svg: str,
    *,
    color_mode: str,
    gray_to_muted: bool = False,
    recolor: dict[str, str] | None = None,
    default_fill: str | None = None,
) -> str:
    recolor_up = {_expand_hex(k): v for k, v in (recolor or {}).items()}

    def map_hex(raw_tok: str, prop: str) -> str:
        parsed = _parse_color_token(raw_tok)
        if not parsed:
            return raw_tok
        if parsed in recolor_up:
            mapped = recolor_up[parsed]
            if mapped.startswith("{{"):
                return mapped
            parsed = mapped

        if color_mode == "badge":
            return parsed

        chroma, lum = _rgb_metrics(parsed)
        if color_mode == "ink":
            if prop != "stop-color" and chroma <= 28 and lum < 0.28:
                return "{{INK}}"
            if gray_to_muted and prop != "stop-color" and chroma <= 28 and 0.28 <= lum <= 0.78:
                return "{{INK_MUTED}}"
        elif color_mode == "brand_color" and default_fill:
            if chroma <= 28 and lum < 0.28:
                return default_fill
        return parsed

    def attr_sub(match: re.Match[str]) -> str:
        prop, val = match.group(1), match.group(3)
        if val.strip().lower() in ("none", "currentcolor") or "url(" in val.lower() or "{{" in val:
            return match.group(0)
        return f'{prop}="{map_hex(val, prop.lower())}"'

    def css_sub(match: re.Match[str]) -> str:
        prop, val = match.group(1), match.group(2).strip()
        if val.lower() in ("none", "currentcolor") or "url(" in val.lower() or "{{" in val:
            return match.group(0)
        return f"{prop}:{map_hex(val, prop.lower())}"

    svg = re.sub(r'\b(fill|stroke|stop-color)\s*=\s*(["\'])([^"\']+)\2', attr_sub, svg, flags=re.I)
    svg = re.sub(r'(?<![a-zA-Z-])(fill|stroke|stop-color)\s*:\s*([^;"\'}<]+)', css_sub, svg, flags=re.I)

    # Set default root fill / badge flag cleanly
    svg = re.sub(r'\s+data-logo-badge\s*=\s*(["\'])[^"\']*\1', "", svg, flags=re.I)
    m = re.search(r"<svg\b([^>]*)>", svg, re.S | re.I)
    assert m is not None
    attrs = m.group(1)
    if color_mode == "badge":
        attrs = ' data-logo-badge="1"' + attrs
    elif color_mode == "ink":
        if not re.search(r"\bfill\s*[:=]", attrs, re.I):
            attrs = ' fill="{{INK}}"' + attrs
    elif default_fill:
        attrs = re.sub(r'\s*\bfill\s*=\s*(["\'])[^"\']*\1', "", attrs, flags=re.I)
        attrs = f' fill="{default_fill}"' + attrs
    return svg[:m.start(1)] + attrs + svg[m.end(1):]


def _tighten_viewbox(svg: str) -> str:
    svg, vx, vy, vw, vh = _normalize_viewbox_header(svg)
    probe_svg = (
        svg.replace("{{INK}}", "#141414")
        .replace("{{INK_MUTED}}", "#555555")
        .replace("{{CONTRAST}}", "#FFFFFF")
        .replace("{{BADGE_FG}}", "#FFFFFF")
        .replace("{{BADGE_DARK}}", "#141414")
        .replace("{{KODAK_K}}", "#ED0000")
    )
    if vw >= vh:
        pw = 512
        ph = max(48, round(512 * vh / vw))
    else:
        ph = 512
        pw = max(48, round(512 * vw / vh))
    png = bytes(resvg_py.svg_to_bytes(svg_string=probe_svg, width=pw, height=ph, skip_system_fonts=True))
    bbox = _png_alpha_bbox(png)
    if bbox is None:
        raise ValueError("Rasterized SVG produced zero visible pixels")
    w, h, min_x, min_y, max_x, max_y = bbox
    x0 = vx + (min_x / w) * vw
    x1 = vx + ((max_x + 1) / w) * vw
    y0 = vy + (min_y / h) * vh
    y1 = vy + ((max_y + 1) / h) * vh
    cw = max(1e-3, x1 - x0)
    ch = max(1e-3, y1 - y0)
    pad = 0.02 * max(cw, ch)
    nx, ny, nw, nh = x0 - pad, y0 - pad, cw + 2 * pad, ch + 2 * pad
    m = re.search(r"<svg\b([^>]*)>", svg, re.S | re.I)
    assert m is not None
    attrs = re.sub(r'\s*\b(?:viewBox|width|height)\s*=\s*(["\'])[^"\']*\1', "", m.group(1), flags=re.I)
    new_attrs = f' viewBox="{_fmt(nx)} {_fmt(ny)} {_fmt(nw)} {_fmt(nh)}" width="{_fmt(nw)}" height="{_fmt(nh)}"' + attrs
    tight = svg[:m.start(1)] + new_attrs + svg[m.end(1):]

    # Verify final SVG renders crisply with resvg
    probe2 = (
        tight.replace("{{INK}}", "#141414")
        .replace("{{INK_MUTED}}", "#555555")
        .replace("{{CONTRAST}}", "#FFFFFF")
        .replace("{{BADGE_FG}}", "#FFFFFF")
        .replace("{{BADGE_DARK}}", "#141414")
        .replace("{{KODAK_K}}", "#ED0000")
    )
    res_test = bytes(resvg_py.svg_to_bytes(svg_string=probe2, width=220, height=90, skip_system_fonts=True))
    if len(res_test) < 120:
        raise ValueError("Final tightened SVG rendered empty PNG")
    return tight


def _inner_svg_body(raw_svg: str, strip_ids: list[str] | None = None) -> tuple[str, float, float, float, float]:
    clean = _strip_bloat(raw_svg, strip_ids=strip_ids)
    clean, vx, vy, vw, vh = _normalize_viewbox_header(clean)
    inner = re.sub(r"^\s*<svg\b[^>]*>", "", clean, count=1, flags=re.S | re.I)
    inner = re.sub(r"</svg>\s*$", "", inner, count=1, flags=re.I)
    return inner.strip(), vx, vy, vw, vh


ASAHI_GROUP = (
    '<g transform="translate(110,18) scale(0.4)">'
    '<path d="M 31.84 0 L 47.36 0 L 79.2 100 L 65.03 100 L 39.6 16 L 14.18 100 L 0 100 Z M 17.42 62 L 61.78 62 L 61.78 74.69 L 17.42 74.69 Z" transform="translate(0,0)" fill="{{INK_MUTED}}" fill-rule="nonzero"/>'
    '<path d="M 57.18 17.36 L 55.96 16.67 L 54.67 16.12 L 53.06 15.59 L 51.19 15.1 L 49.1 14.69 L 46.83 14.36 L 44.43 14.13 L 41.93 14.01 L 39.37 14 L 36.79 14.11 L 34.22 14.35 L 31.7 14.72 L 29.26 15.22 L 26.94 15.85 L 24.78 16.61 L 22.81 17.48 L 21.06 18.45 L 19.54 19.52 L 18.28 20.66 L 17.26 21.86 L 16.47 23.15 L 15.89 24.55 L 15.52 26.14 L 15.39 27.95 L 15.54 29.84 L 15.98 31.39 L 16.67 32.81 L 17.66 34.18 L 19 35.56 L 20.68 36.93 L 22.7 38.27 L 25.02 39.59 L 27.59 40.87 L 30.36 42.12 L 33.28 43.36 L 36.31 44.6 L 39.41 45.87 L 42.52 47.18 L 45.62 48.59 L 48.66 50.11 L 51.62 51.79 L 54.44 53.68 L 57.09 55.84 L 59.49 58.33 L 61.55 61.21 L 63.15 64.49 L 64.15 68.12 L 64.49 71.96 L 64.2 75.65 L 63.34 79.1 L 61.95 82.27 L 60.11 85.1 L 57.9 87.58 L 55.41 89.7 L 52.7 91.51 L 49.83 93.03 L 46.82 94.29 L 43.71 95.32 L 40.52 96.15 L 37.28 96.78 L 34.02 97.24 L 30.76 97.54 L 27.53 97.67 L 24.36 97.66 L 21.26 97.52 L 18.26 97.23 L 15.39 96.82 L 12.66 96.28 L 10.1 95.6 L 7.7 94.76 L 5.45 93.74 L 3.76 92.71 L 9.88 82.77 L 10.9 83.42 L 12 83.91 L 13.48 84.42 L 15.29 84.9 L 17.35 85.31 L 19.63 85.64 L 22.08 85.87 L 24.65 85.99 L 27.3 86 L 29.99 85.89 L 32.69 85.64 L 35.35 85.27 L 37.94 84.76 L 40.41 84.13 L 42.72 83.36 L 44.85 82.47 L 46.74 81.47 L 48.38 80.38 L 49.75 79.22 L 50.84 78 L 51.68 76.72 L 52.29 75.34 L 52.67 73.8 L 52.81 72.04 L 52.66 70.16 L 52.22 68.61 L 51.53 67.19 L 50.54 65.82 L 49.2 64.44 L 47.52 63.07 L 45.5 61.73 L 43.18 60.41 L 40.61 59.13 L 37.84 57.88 L 34.92 56.64 L 31.89 55.4 L 28.79 54.13 L 25.68 52.82 L 22.58 51.41 L 19.54 49.89 L 16.58 48.21 L 13.76 46.32 L 11.11 44.16 L 8.71 41.67 L 6.65 38.79 L 5.05 35.51 L 4.05 31.88 L 3.71 28.05 L 3.98 24.41 L 4.77 21.01 L 6.06 17.86 L 7.79 15.04 L 9.88 12.55 L 12.26 10.4 L 14.85 8.57 L 17.6 7.03 L 20.5 5.75 L 23.49 4.7 L 26.56 3.86 L 29.68 3.22 L 32.83 2.76 L 35.99 2.47 L 39.13 2.33 L 42.23 2.34 L 45.27 2.49 L 48.22 2.77 L 51.07 3.18 L 53.79 3.72 L 56.36 4.39 L 58.79 5.2 L 61.06 6.17 L 62.85 7.16 Z" transform="translate(107.2,0)" fill="{{INK_MUTED}}" fill-rule="nonzero"/>'
    '<path d="M 31.84 0 L 47.36 0 L 79.2 100 L 65.03 100 L 39.6 16 L 14.18 100 L 0 100 Z M 17.42 62 L 61.78 62 L 61.78 74.69 L 17.42 74.69 Z" transform="translate(203.4,0)" fill="{{INK_MUTED}}" fill-rule="nonzero"/>'
    '<path d="M 0 0 L 13.5 0 L 13.5 100 L 0 100 Z M 61.3 0 L 74.8 0 L 74.8 100 L 61.3 100 Z M 0 43.66 L 74.8 43.66 L 74.8 56.34 L 0 56.34 Z" transform="translate(310.6,0)" fill="{{INK_MUTED}}" fill-rule="nonzero"/>'
    '<path d="M 5.79 0 L 19.29 0 L 19.29 100 L 5.79 100 Z" transform="translate(413.4,0)" fill="{{INK_MUTED}}" fill-rule="nonzero"/>'
    '</g>'
)

THETA_PATHS = (
    '<path d="M 0 0 L 63.24 0 L 63.24 10.34 L 0 10.34 Z M 26.12 0 L 37.12 0 L 37.12 100 L 26.12 100 Z" transform="translate(0,0)" fill="{{INK}}" fill-rule="nonzero"/>'
    '<path d="M 0 0 L 11 0 L 11 100 L 0 100 Z M 58.36 0 L 69.36 0 L 69.36 100 L 58.36 100 Z M 0 44.83 L 69.36 44.83 L 69.36 55.17 L 0 55.17 Z" transform="translate(77.24,0)" fill="{{INK}}" fill-rule="nonzero"/>'
    '<path d="M 0 0 L 11 0 L 11 100 L 0 100 Z M 0 0 L 61.2 0 L 61.2 10.34 L 0 10.34 Z M 0 44.83 L 51.41 44.83 L 51.41 55.17 L 0 55.17 Z M 0 89.66 L 61.2 89.66 L 61.2 100 L 0 100 Z" transform="translate(160.6,0)" fill="{{INK}}" fill-rule="nonzero"/>'
    '<path d="M 0 0 L 63.24 0 L 63.24 10.34 L 0 10.34 Z M 26.12 0 L 37.12 0 L 37.12 100 L 26.12 100 Z" transform="translate(235.8,0)" fill="{{INK}}" fill-rule="nonzero"/>'
    '<path d="M 30.39 0 L 43.05 0 L 73.44 100 L 61.89 100 L 36.72 16 L 11.55 100 L 0 100 Z M 16.16 62 L 57.28 62 L 57.28 72.34 L 16.16 72.34 Z" transform="translate(313.04,0)" fill="{{INK}}" fill-rule="nonzero"/>'
)


def _build_derived(source_key: str) -> str:
    if source_key == "nikon_1988":
        raw = (CACHE_DIR / "nikon__2003.svg").read_text(encoding="utf-8")
        m = re.search(r'<path\b[^>]*fill\s*=\s*"#150301"[^>]*\bd="([^"]+)"', raw, re.I)
        if not m:
            raise ValueError("Nikon wordmark path not found in nikon__2003.svg")
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 280 400 115" width="400" height="115">\n'
            f'  <path fill="{{{{INK}}}}" d="{m.group(1)}"/>\n'
            "</svg>"
        )

    if source_key == "nikon_1968":
        raw = (CACHE_DIR / "nikon__2003.svg").read_text(encoding="utf-8")
        m = re.search(r'<path\b[^>]*fill\s*=\s*"#150301"[^>]*\bd="([^"]+)"', raw, re.I)
        if not m:
            raise ValueError("Nikon wordmark path not found")
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 176" width="480" height="176">\n'
            '  <rect x="8" y="8" width="464" height="160" rx="80" ry="80" fill="#FFE100" stroke="#000000" stroke-width="12"/>\n'
            f'  <g transform="translate(42, -246)"><path fill="#000000" d="{m.group(1)}"/></g>\n'
            "</svg>"
        )

    if source_key == "sony_alpha_2006":
        sony_raw = (CACHE_DIR / "sony__1973.svg").read_text(encoding="utf-8")
        alpha_raw = (CACHE_DIR / "sony-alpha__2006.svg").read_text(encoding="utf-8")
        s_body, sx, sy, sw, sh = _inner_svg_body(sony_raw)
        a_body, ax, ay, aw, ah = _inner_svg_body(alpha_raw, strip_ids=["g8", "g12"])
        scale_a = sh / ah
        sep_x = sw + 75.0
        a_x = sep_x + 24.0 + 75.0 - ax * scale_a
        total_w = a_x + (ax + aw) * scale_a
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_fmt(total_w)} {_fmt(sh)}" width="{_fmt(total_w)}" height="{_fmt(sh)}">\n'
            f'  <g transform="translate({_fmt(-sx)},{_fmt(-sy)})">{s_body}</g>\n'
            f'  <rect x="{_fmt(sep_x)}" y="10" width="22" height="{_fmt(sh - 20)}" fill="{{{{INK_MUTED}}}}"/>\n'
            f'  <g transform="translate({_fmt(a_x)},{_fmt(-ay * scale_a)}) scale({_fmt(scale_a)})">{a_body}</g>\n'
            "</svg>"
        )

    if source_key == "olympus_1970":
        raw = (CACHE_DIR / "olympus__2001.svg").read_text(encoding="utf-8")
        return _strip_bloat(raw, strip_ids=["_137713304", "_137995520", "_138002232"])

    if source_key == "pentax_1957":
        pentax_raw = (CACHE_DIR / "pentax__1987_b.svg").read_text(encoding="utf-8")
        elems = re.findall(r"<(?:path|polygon)\b[^>]*/>", pentax_raw)[:6]
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 440 160" width="440" height="160">\n'
            f'  {ASAHI_GROUP}\n'
            '  <g transform="translate(20,70) scale(0.50)" fill="{{INK}}">\n    '
            + "\n    ".join(re.sub(r'\s*style\s*=\s*"[^"]*"', "", e) for e in elems)
            + "\n  </g>\n</svg>"
        )

    if source_key == "hasselblad_1990":
        raw = (CACHE_DIR / "hasselblad__1990.svg").read_text(encoding="utf-8")
        body, vx, vy, vw, vh = _inner_svg_body(raw)
        # Scale wordmark cleanly next to bold H-square
        scale_w = 52.0 / vh
        wx = 148.0 - vx * scale_w
        wy = 44.0 - vy * scale_w
        total_w = wx + (vx + vw) * scale_w + 12.0
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_fmt(total_w)} 140" width="{_fmt(total_w)}" height="140">\n'
            '  <rect x="12" y="14" width="112" height="112" rx="6" fill="{{INK}}"/>\n'
            '  <path d="M 38 34 L 54 34 L 54 62 L 82 62 L 82 34 L 98 34 L 98 106 L 82 106 L 82 78 L 54 78 L 54 106 L 38 106 Z" fill="{{CONTRAST}}"/>\n'
            f'  <g transform="translate({_fmt(wx)},{_fmt(wy)}) scale({_fmt(scale_w)})">{body}</g>\n'
            "</svg>"
        )

    if source_key == "blackmagic_2001":
        raw = (CACHE_DIR / "blackmagic__2001.svg").read_text(encoding="utf-8")
        cleaned = _strip_bloat(raw, strip_ids=["Background_Square"])
        # Convert light typography colors on black bg to adapt to frame polarity cleanly
        cleaned = re.sub(r'\bfill\s*=\s*"#(?:FFFFFF|fff)"', 'fill="#000000"', cleaned, flags=re.I)
        return cleaned

    if source_key in ("huawei_2018", "huawei_2006"):
        flower_raw = (CACHE_DIR / "huawei__2018_a.svg").read_text(encoding="utf-8")
        word_raw = (CACHE_DIR / "huawei__2018_b.svg").read_text(encoding="utf-8")
        defs_m = re.search(r"<defs[^>]*>(.*?)</defs>", flower_raw, re.S)
        if not defs_m:
            raise ValueError("Missing <defs> in huawei__2018_a.svg")
        petals = re.findall(r'<path[^>]*\bd="([^"]+)"', defs_m.group(1))
        unique_petals: list[str] = []
        for p in petals:
            if len(p) > 80 and p not in unique_petals:
                unique_petals.append(p)
            if len(unique_petals) == 8:
                break
        if len(unique_petals) != 8:
            raise ValueError(f"Expected 8 Huawei petals, found {len(unique_petals)}")
        word_m = re.search(r'<path[^>]*\bd="([^"]+)"', word_raw)
        if not word_m:
            raise ValueError("Missing wordmark path in huawei__2018_b.svg")
        if source_key == "huawei_2018":
            p_defs = ""
            p_fill = "#CF0A2C"
        else:
            p_defs = (
                "  <defs>\n"
                '    <radialGradient id="hwgrad" cx="11.7" cy="9.2" r="14.5" gradientUnits="userSpaceOnUse">\n'
                '      <stop offset="0" stop-color="#FF5247"/>\n'
                '      <stop offset="0.58" stop-color="#E60012"/>\n'
                '      <stop offset="1" stop-color="#8A000C"/>\n'
                "    </radialGradient>\n"
                "  </defs>\n"
            )
            p_fill = "url(#hwgrad)"
        # Flower resides in x=[0.85..22.6], y=[6.5..23.3] in Y-up -> scale 1.75 => width 38.0, height ~29.4
        # Wordmark is 57.582 x 9.842 -> placed below flower centered at x=0..57.582
        # Translate flower horizontally so center (11.72 * 1.75 = 20.51) aligns with 57.582/2 = 28.79 => tx = 8.28
        petal_elems = "\n    ".join(f'<path d="{d}" fill="{p_fill}"/>' for d in unique_petals)
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 58 46" width="58" height="46">\n'
            f"{p_defs}"
            '  <g transform="translate(8.28, 41.1) scale(1.75, -1.75)">\n    '
            f"{petal_elems}\n"
            "  </g>\n"
            f'  <g transform="translate(0, 34.5)"><path fill="{{{{INK}}}}" d="{word_m.group(1)}"/></g>\n'
            "</svg>"
        )

    if source_key == "oneplus_2013":
        raw = (CACHE_DIR / "oneplus__2020_a.svg").read_text(encoding="utf-8")
        body, vx, vy, vw, vh = _inner_svg_body(raw)
        clean = re.sub(r"#F50514", "#EB0029", body, flags=re.I)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_fmt(vw * 0.92)} {_fmt(vh)}" width="{_fmt(vw * 0.92)}" height="{_fmt(vh)}">\n'
            f'  <g transform="scale(0.92, 1.0)">{clean}</g>\n'
            "</svg>"
        )

    if source_key == "lg_2023":
        raw = (CACHE_DIR / "lg__2014.svg").read_text(encoding="utf-8")
        return re.sub(r"#A50034", "#FD312E", raw, flags=re.I)

    if source_key == "gopro_2004":
        raw = (CACHE_DIR / "gopro__2004_a.svg").read_text(encoding="utf-8")
        stripped = re.sub(r"<rect\b[^>]*st[123][^>]*/>", "", raw, flags=re.I)
        return re.sub(r'\.st[123]\s*\{[^}]*\}', "", stripped, flags=re.I)

    if source_key == "ricoh_theta_2013":
        ricoh_raw = (CACHE_DIR / "ricoh__2005.svg").read_text(encoding="utf-8")
        r_body, rx, ry, rw, rh = _inner_svg_body(ricoh_raw)
        scale_r = 100.0 / rh
        total_w = rw * scale_r + 36.0 + 390.0
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_fmt(total_w)} 104" width="{_fmt(total_w)}" height="104">\n'
            f'  <g transform="translate({_fmt(-rx * scale_r)},{_fmt(2 - ry * scale_r)}) scale({_fmt(scale_r)})">{r_body}</g>\n'
            f'  <g transform="translate({_fmt(rw * scale_r + 36.0)},2)">\n    {THETA_PATHS}\n  </g>\n'
            "</svg>"
        )

    raise ValueError(f"Unknown derived key: {source_key}")


def _fetch_missing(entries: list[dict]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    needed: dict[tuple[str, str], Path] = {}
    for e in entries:
        if e["mode"] == "raw":
            dest = CACHE_DIR / e["source"]
            if not dest.is_file() or dest.stat().st_size == 0:
                needed[(e["wiki_host"], e["wiki_title"])] = dest
        elif e["mode"] == "derived" and e.get("wiki_title"):
            pass
    if not needed:
        return

    by_host: dict[str, list[tuple[str, Path]]] = {}
    for (hk, title), dest in needed.items():
        by_host.setdefault(hk, []).append((title, dest))

    for hk, items in by_host.items():
        host = "commons.wikimedia.org" if hk == "commons" else f"{hk}.wikipedia.org"
        for i in range(0, len(items), 25):
            chunk = items[i:i + 25]
            url = f"https://{host}/w/api.php?" + urllib.parse.urlencode({
                "action": "query", "prop": "imageinfo", "iiprop": "url",
                "titles": "|".join(t for t, _ in chunk), "format": "json",
            })
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            data = json.loads(urllib.request.urlopen(req, timeout=25).read().decode("utf-8"))
            norm = {n["to"]: n["from"] for n in data.get("query", {}).get("normalized", [])}
            urls: dict[str, str] = {}
            for p in data["query"]["pages"].values():
                if "imageinfo" in p:
                    u = p["imageinfo"][0]["url"]
                    urls[p["title"]] = u
                    if p["title"] in norm:
                        urls[norm[p["title"]]] = u
            for t, dest in chunk:
                u = urls.get(t)
                if not u:
                    raise RuntimeError(f"Could not resolve Wikimedia URL for {hk}:{t}")
                delay = 0.8
                for attempt in range(5):
                    try:
                        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=25)
                        dest.write_bytes(r.read())
                        break
                    except urllib.error.HTTPError as err:
                        if err.code == 429 and attempt < 4:
                            time.sleep(float(err.headers.get("Retry-After") or delay))
                            delay *= 2
                            continue
                        raise
                print(f"Downloaded {dest.name} ({dest.stat().st_size} B)")
                time.sleep(0.7)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true", help="Download missing raw SVGs into build/logo-cache/raw")
    args = parser.parse_args()

    manifest = json.loads(SOURCES_JSON.read_text(encoding="utf-8"))
    entries: list[dict] = manifest["entries"]
    assert len(entries) == 93, f"Expected 93 entries, got {len(entries)}"

    if args.download:
        _fetch_missing(entries)

    for e in entries:
        bid, eid = e["brand_id"], e["era_id"]
        out_path = ASSETS_DIR / bid / f"{eid}.svg"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        mode = e["mode"]
        if mode == "retained":
            raw_svg = out_path.read_text(encoding="utf-8")
            clean = _strip_bloat(raw_svg, strip_ids=e.get("strip_ids"))
            # Already authored with {{INK}} / {{BADGE_FG}}; only ensure data-logo-badge & tight viewBox
            clean = _normalize_colors(
                clean,
                color_mode=e["color_mode"],
                gray_to_muted=e.get("gray_to_muted", False),
                recolor=e.get("recolor"),
                default_fill=e.get("default_fill"),
            )
            final = _tighten_viewbox(clean)
        elif mode == "raw":
            src = CACHE_DIR / e["source"]
            if not src.is_file():
                raise FileNotFoundError(f"Missing cached raw SVG {src} (re-run with --download)")
            clean = _strip_bloat(src.read_text(encoding="utf-8", errors="replace"), strip_ids=e.get("strip_ids"))
            clean = _normalize_colors(
                clean,
                color_mode=e["color_mode"],
                gray_to_muted=e.get("gray_to_muted", False),
                recolor=e.get("recolor"),
                default_fill=e.get("default_fill"),
            )
            final = _tighten_viewbox(clean)
        elif mode == "derived":
            built = _build_derived(e["source"])
            clean = _strip_bloat(built, strip_ids=e.get("strip_ids"))
            clean = _normalize_colors(
                clean,
                color_mode=e["color_mode"],
                gray_to_muted=e.get("gray_to_muted", False),
                recolor=e.get("recolor"),
                default_fill=e.get("default_fill"),
            )
            final = _tighten_viewbox(clean)
        else:
            raise ValueError(f"Invalid mode {mode}")

        # Validate well-formed XML
        ET.fromstring(final.encode("utf-8"))
        out_path.write_text(final.strip() + "\n", encoding="utf-8")

    print(f"Successfully normalized and verified {len(entries)} official pure-vector SVGs.")


if __name__ == "__main__":
    main()
