"""Generate pure-vector historical CI SVG logos for 61 camera/mobile/drone brands.

Every SVG contains pure geometric paths/primitives (zero <text> tags) and uses
semantic tokens for frame polarity adaptation:
  {{INK}}        Primary ink (dark on light frames, light on dark frames)
  {{INK_MUTED}}  Secondary ink
  {{CONTRAST}}   Knockout/reversed color inside badges
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "helper" / "assets" / "logos"

# ---------------------------------------------------------------------------
# Parametric Geometric / Slab-Serif / Rounded / Dot-Matrix Glyph Engine
# All glyphs live in local coordinates: x in [0, adv], y in [0, 100] (0=top, 100=baseline).
# ---------------------------------------------------------------------------

def _r(val: float) -> str:
    return f"{val:.2f}".rstrip("0").rstrip(".") or "0"


def _circle_path(cx: float, cy: float, rx: float, ry: float, cw: bool = True) -> str:
    d = 1 if cw else 0
    return (
        f"M {_r(cx - rx)} {_r(cy)} "
        f"A {_r(rx)} {_r(ry)} 0 1 {d} {_r(cx + rx)} {_r(cy)} "
        f"A {_r(rx)} {_r(ry)} 0 1 {d} {_r(cx - rx)} {_r(cy)} Z"
    )


def _ensure_cw(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Ensure polygon vertices are wound clockwise in SVG Y-down coordinates for nonzero union."""
    area2 = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        area2 += (x2 - x1) * (y2 + y1)
    # In Y-down coordinates, CW loop gives negative sum((x2-x1)*(y2+y1))
    if area2 > 0:
        return list(reversed(pts))
    return pts


def _poly(pts: list[tuple[float, float]], cw: bool = True) -> str:
    ordered = _ensure_cw(pts) if cw else list(reversed(_ensure_cw(pts)))
    return "M " + " L ".join(f"{_r(x)} {_r(y)}" for x, y in ordered) + " Z"


def _cubic_pt(p0: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float],
              p3: tuple[float, float], t: float) -> tuple[float, float]:
    u = 1.0 - t
    x = u ** 3 * p0[0] + 3 * u ** 2 * t * p1[0] + 3 * u * t ** 2 * p2[0] + t ** 3 * p3[0]
    y = u ** 3 * p0[1] + 3 * u ** 2 * t * p1[1] + 3 * u * t ** 2 * p2[1] + t ** 3 * p3[1]
    return x, y


def _stroke_beziers(segments: list[tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]],
                    width: float, steps_per_seg: int = 24) -> str:
    """Convert connected cubic Bezier centerline segments into a smooth closed CW outline."""
    pts: list[tuple[float, float]] = []
    for seg_idx, (p0, p1, p2, p3) in enumerate(segments):
        start = 0 if seg_idx == 0 else 1
        for k in range(start, steps_per_seg + 1):
            pts.append(_cubic_pt(p0, p1, p2, p3, k / steps_per_seg))
    left_pts: list[tuple[float, float]] = []
    right_pts: list[tuple[float, float]] = []
    half = width / 2.0
    for i, (px, py) in enumerate(pts):
        if i == 0:
            tx, ty = pts[1][0] - px, pts[1][1] - py
        elif i == len(pts) - 1:
            tx, ty = px - pts[-2][0], py - pts[-2][1]
        else:
            tx, ty = pts[i + 1][0] - pts[i - 1][0], pts[i + 1][1] - pts[i - 1][1]
        length = math.hypot(tx, ty) or 1.0
        nx, ny = -ty / length * half, tx / length * half
        left_pts.append((px + nx, py + ny))
        right_pts.append((px - nx, py - ny))
    return _poly(left_pts + list(reversed(right_pts)), cw=True)


def _rounded_rect_path(x: float, y: float, w: float, h: float, r: float) -> str:
    r = min(r, w / 2, h / 2)
    if r <= 0:
        return _poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], cw=True)
    return (
        f"M {_r(x + r)} {_r(y)} L {_r(x + w - r)} {_r(y)} "
        f"A {_r(r)} {_r(r)} 0 0 1 {_r(x + w)} {_r(y + r)} "
        f"L {_r(x + w)} {_r(y + h - r)} "
        f"A {_r(r)} {_r(r)} 0 0 1 {_r(x + w - r)} {_r(y + h)} "
        f"L {_r(x + r)} {_r(y + h)} "
        f"A {_r(r)} {_r(r)} 0 0 1 {_r(x)} {_r(y + h - r)} "
        f"L {_r(x)} {_r(y + r)} "
        f"A {_r(r)} {_r(r)} 0 0 1 {_r(x + r)} {_r(y)} Z"
    )


def _thick_line(x1: float, y1: float, x2: float, y2: float, w: float) -> str:
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length * (w / 2), dx / length * (w / 2)
    return _poly([(x1 + nx, y1 + ny), (x2 + nx, y2 + ny), (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)], cw=True)


def _arc_ring_segment(
    cx: float, cy: float, rx_o: float, ry_o: float, rx_i: float, ry_i: float,
    a0_deg: float, a1_deg: float
) -> str:
    """Elliptical ring arc from a0_deg to a1_deg (0=right, 90=down, clockwise)."""
    a0 = math.radians(a0_deg)
    a1 = math.radians(a1_deg)
    ox0, oy0 = cx + rx_o * math.cos(a0), cy + ry_o * math.sin(a0)
    ox1, oy1 = cx + rx_o * math.cos(a1), cy + ry_o * math.sin(a1)
    ix1, iy1 = cx + rx_i * math.cos(a1), cy + ry_i * math.sin(a1)
    ix0, iy0 = cx + rx_i * math.cos(a0), cy + ry_i * math.sin(a0)
    span = (a1_deg - a0_deg) % 360
    large = 1 if span > 180 else 0
    return (
        f"M {_r(ox0)} {_r(oy0)} "
        f"A {_r(rx_o)} {_r(ry_o)} 0 {large} 1 {_r(ox1)} {_r(oy1)} "
        f"L {_r(ix1)} {_r(iy1)} "
        f"A {_r(rx_i)} {_r(ry_i)} 0 {large} 0 {_r(ix0)} {_r(iy0)} Z"
    )


def _bowl_cw_ccw(x_left: float, y_top: float, y_bot: float, cx: float, rx_o: float, sw: float, hs: float) -> str:
    """Closed D-shaped lobe: CW outer + CCW inner hole for nonzero union without seams."""
    ry_o = (y_bot - y_top) / 2.0
    rx_i = max(2.0, rx_o - sw)
    ry_i = max(2.0, ry_o - hs)
    outer = (
        f"M {_r(x_left)} {_r(y_top)} L {_r(cx)} {_r(y_top)} "
        f"A {_r(rx_o)} {_r(ry_o)} 0 0 1 {_r(cx)} {_r(y_bot)} "
        f"L {_r(x_left)} {_r(y_bot)} Z"
    )
    hx = x_left + sw
    hy0 = y_top + hs
    hy1 = y_bot - hs
    inner = (
        f"M {_r(hx)} {_r(hy0)} L {_r(hx)} {_r(hy1)} L {_r(cx)} {_r(hy1)} "
        f"A {_r(rx_i)} {_r(ry_i)} 0 0 0 {_r(cx)} {_r(hy0)} Z"
    )
    return outer + " " + inner


def _glyph_geom(ch: str, sw: float = 14.0, w_scale: float = 1.0, rounded: bool = False,
                serif: bool = False, crossbar_a: bool = True) -> tuple[str, float]:
    """Return (SVG path data in [0,adv] x [0,100], advance width) for ASCII chars."""
    if ch == " ":
        return "", 34.0 * w_scale
    hs = sw * (0.86 if serif else 0.94)
    cr = sw * 0.45 if rounded else 0.0

    def rect(x: float, y: float, w: float, h: float) -> str:
        return _rounded_rect_path(x, y, w, h, min(cr, min(w, h) * 0.45))

    def serif_bar(cx: float, y: float, width: float, sh: float | None = None) -> str:
        if not serif:
            return ""
        h = sh or sw * 0.52
        return _poly([(cx - width / 2, y), (cx + width / 2, y), (cx + width / 2, y + h), (cx - width / 2, y + h)])

    # Uppercase letters (height 0..100)
    W = 68.0 * w_scale
    parts: list[str] = []
    adv = W

    if ch == "A":
        adv = 72 * w_scale
        top_w = sw * 1.15
        parts.append(_poly([(adv / 2 - top_w / 2, 0), (adv / 2 + top_w / 2, 0), (adv, 100), (adv - sw * 1.05, 100),
                            (adv / 2, 16), (sw * 1.05, 100), (0, 100)]))
        if crossbar_a:
            parts.append(rect(adv * 0.22, 62, adv * 0.56, hs))
        if serif:
            parts.append(serif_bar(sw * 0.6, 100 - sw * 0.52, sw * 1.7))
            parts.append(serif_bar(adv - sw * 0.6, 100 - sw * 0.52, sw * 1.7))
    elif ch == "B":
        adv = 66 * w_scale
        parts.append(_bowl_cw_ccw(0, 0, 52 + hs * 0.35, adv * 0.48, adv * 0.46, sw, hs))
        parts.append(_bowl_cw_ccw(0, 46 - hs * 0.25, 100, adv * 0.50, adv * 0.50, sw, hs))
    elif ch == "C":
        adv = 68 * w_scale
        parts.append(_arc_ring_segment(adv * 0.54, 50, adv * 0.54, 50, max(2, adv * 0.54 - sw), max(2, 50 - hs), 35, 325))
    elif ch == "D":
        adv = 68 * w_scale
        parts.append(_bowl_cw_ccw(0, 0, 100, adv * 0.46, adv * 0.54, sw, hs))
    elif ch == "E":
        adv = 60 * w_scale
        parts.extend([rect(0, 0, sw, 100), rect(0, 0, adv, hs), rect(0, 50 - hs / 2, adv * 0.84, hs), rect(0, 100 - hs, adv, hs)])
        if serif:
            parts.append(rect(adv - sw * 0.5, 0, sw * 0.5, hs * 1.9))
            parts.append(rect(adv - sw * 0.5, 100 - hs * 1.9, sw * 0.5, hs * 1.9))
    elif ch == "F":
        adv = 58 * w_scale
        parts.extend([rect(0, 0, sw, 100), rect(0, 0, adv, hs), rect(0, 50 - hs / 2, adv * 0.82, hs)])
        if serif:
            parts.append(serif_bar(sw / 2, 100 - sw * 0.52, sw * 1.8))
    elif ch == "G":
        adv = 72 * w_scale
        parts.append(_arc_ring_segment(adv * 0.50, 50, adv * 0.50, 50, max(2, adv * 0.50 - sw), max(2, 50 - hs), 2, 326))
        parts.append(rect(adv * 0.52, 49, adv * 0.48, hs))
        parts.append(rect(adv - sw, 49, sw, 42))
    elif ch == "H":
        adv = 68 * w_scale
        parts.extend([rect(0, 0, sw, 100), rect(adv - sw, 0, sw, 100), rect(0, 50 - hs / 2, adv, hs)])
        if serif:
            parts.extend([serif_bar(sw / 2, 0, sw * 1.7), serif_bar(adv - sw / 2, 0, sw * 1.7),
                          serif_bar(sw / 2, 100 - sw * 0.52, sw * 1.7), serif_bar(adv - sw / 2, 100 - sw * 0.52, sw * 1.7)])
    elif ch == "I":
        adv = (36 if serif else 24) * max(0.9, w_scale * 0.95)
        cx = adv / 2
        parts.append(rect(cx - sw / 2, 0, sw, 100))
        if serif:
            parts.append(rect(0, 0, adv, sw * 0.55))
            parts.append(rect(0, 100 - sw * 0.55, adv, sw * 0.55))
    elif ch == "J":
        adv = 54 * w_scale
        parts.append(rect(adv - sw, 0, sw, 68))
        parts.append(_arc_ring_segment(adv * 0.48, 66, adv * 0.52, 34, max(2, adv * 0.52 - sw), max(2, 34 - hs), 0, 168))
    elif ch == "K":
        adv = 68 * w_scale
        parts.append(rect(0, 0, sw, 100))
        parts.append(_poly([(sw * 0.7, 52), (adv - sw * 1.05, 0), (adv, 0), (sw * 1.15, 58)]))
        parts.append(_poly([(sw * 1.15, 44), (adv, 100), (adv - sw * 1.08, 100), (sw * 0.72, 54)]))
    elif ch == "L":
        adv = 56 * w_scale
        parts.extend([rect(0, 0, sw, 100), rect(0, 100 - hs, adv, hs)])
    elif ch == "M":
        adv = 82 * w_scale
        parts.append(rect(0, 0, sw * 0.95, 100))
        parts.append(rect(adv - sw * 0.95, 0, sw * 0.95, 100))
        parts.append(_poly([(0, 0), (sw * 1.05, 0), (adv / 2, 72), (adv - sw * 1.05, 0), (adv, 0),
                            (adv, 14), (adv / 2 + sw * 0.45, 92), (adv / 2 - sw * 0.45, 92), (0, 14)]))
    elif ch == "N":
        adv = 70 * w_scale
        parts.append(rect(0, 0, sw * 0.95, 100))
        parts.append(rect(adv - sw * 0.95, 0, sw * 0.95, 100))
        parts.append(_poly([(0, 0), (sw * 1.05, 0), (adv, 100), (adv - sw * 1.05, 100)]))
        if serif:
            parts.extend([serif_bar(sw / 2, 0, sw * 1.7), serif_bar(adv - sw / 2, 0, sw * 1.7),
                          serif_bar(sw / 2, 100 - sw * 0.52, sw * 1.7), serif_bar(adv - sw / 2, 100 - sw * 0.52, sw * 1.7)])
    elif ch == "O":
        adv = 76 * w_scale
        parts.append(_circle_path(adv / 2, 50, adv / 2, 50, True) + " " +
                     _circle_path(adv / 2, 50, max(2, adv / 2 - sw), max(2, 50 - hs), False))
    elif ch == "P":
        adv = 64 * w_scale
        parts.append(rect(0, 0, sw, 100))
        parts.append(_bowl_cw_ccw(0, 0, 56, adv * 0.50, adv * 0.50, sw, hs))
    elif ch == "Q":
        adv = 76 * w_scale
        parts.append(_circle_path(adv / 2, 50, adv / 2, 50, True) + " " +
                     _circle_path(adv / 2, 50, max(2, adv / 2 - sw), max(2, 50 - hs), False))
        parts.append(_thick_line(adv * 0.54, 64, adv * 0.96, 102, sw * 0.86))
    elif ch == "R":
        adv = 68 * w_scale
        parts.append(rect(0, 0, sw, 100))
        parts.append(_bowl_cw_ccw(0, 0, 55, adv * 0.50, adv * 0.50, sw, hs))
        parts.append(_poly([(adv * 0.44, 50), (adv * 0.62, 50), (adv, 100), (adv - sw * 1.15, 100)]))
    elif ch == "S":
        adv = 62 * w_scale
        st = hs * 0.92
        p_top = (adv * 0.88, st * 1.05)
        p_mid_l = (adv * 0.14, 28.0)
        p_mid_r = (adv * 0.86, 72.0)
        p_bot = (adv * 0.10, 100.0 - st * 1.05)
        parts.append(_stroke_beziers([
            (p_top, (adv * 0.72, st * 0.45), (adv * 0.14, st * 0.45), p_mid_l),
            (p_mid_l, (adv * 0.14, 52.0), (adv * 0.86, 48.0), p_mid_r),
            (p_mid_r, (adv * 0.86, 100.0 - st * 0.45), (adv * 0.24, 100.0 - st * 0.45), p_bot),
        ], st))
        if serif:
            parts.append(rect(adv * 0.84, 2, sw * 0.45, st * 1.35))
            parts.append(rect(0, 100 - st * 1.35 - 2, sw * 0.45, st * 1.35))
    elif ch == "T":
        adv = 62 * w_scale
        parts.extend([rect(0, 0, adv, hs), rect(adv / 2 - sw / 2, 0, sw, 100)])
        if serif:
            parts.append(serif_bar(adv / 2, 100 - sw * 0.52, sw * 1.9))
    elif ch == "U":
        adv = 68 * w_scale
        parts.append(rect(0, 0, sw, 68))
        parts.append(rect(adv - sw, 0, sw, 68))
        parts.append(_arc_ring_segment(adv / 2, 66, adv / 2, 34, max(2, adv / 2 - sw), max(2, 34 - hs), 0, 180))
    elif ch == "V":
        adv = 70 * w_scale
        parts.append(_poly([(0, 0), (sw * 1.08, 0), (adv / 2, 82), (adv - sw * 1.08, 0), (adv, 0),
                            (adv / 2 + sw * 0.52, 100), (adv / 2 - sw * 0.52, 100)]))
    elif ch == "W":
        adv = 92 * w_scale
        parts.append(_poly([(0, 0), (sw * 1.0, 0), (adv * 0.27, 80), (adv * 0.45, 0), (adv * 0.55, 0),
                            (adv * 0.73, 80), (adv - sw * 1.0, 0), (adv, 0), (adv * 0.79, 100), (adv * 0.67, 100),
                            (adv * 0.50, 22), (adv * 0.33, 100), (adv * 0.21, 100)]))
    elif ch == "X":
        adv = 68 * w_scale
        parts.append(_poly([(0, 0), (sw * 1.15, 0), (adv, 100), (adv - sw * 1.15, 100)]))
        parts.append(_poly([(adv - sw * 1.15, 0), (adv, 0), (sw * 1.15, 100), (0, 100)]))
    elif ch == "Y":
        adv = 66 * w_scale
        parts.append(_poly([(0, 0), (sw * 1.15, 0), (adv / 2, 52), (adv - sw * 1.15, 0), (adv, 0),
                            (adv / 2 + sw * 0.54, 60), (adv / 2 + sw * 0.54, 100), (adv / 2 - sw * 0.54, 100), (adv / 2 - sw * 0.54, 60)]))
        if serif:
            parts.extend([serif_bar(sw * 0.6, 0, sw * 1.6), serif_bar(adv - sw * 0.6, 0, sw * 1.6),
                          serif_bar(adv / 2, 100 - sw * 0.52, sw * 1.8)])
    elif ch == "Z":
        adv = 64 * w_scale
        parts.extend([rect(0, 0, adv, hs), rect(0, 100 - hs, adv, hs),
                      _poly([(adv - sw * 1.15, hs * 0.7), (adv, hs * 0.7), (sw * 1.15, 100 - hs * 0.7), (0, 100 - hs * 0.7)])])

    # Lowercase letters (x-height 26..100, ascender 0..100, descender 26..122)
    elif ch == "a":
        adv = 56 * w_scale
        # Clean geometric single-story 'a' (circle + right stem)
        parts.append(_circle_path(adv * 0.45, 63, adv * 0.45, 37, True) + " " +
                     _circle_path(adv * 0.45, 63, max(2, adv * 0.45 - sw * 0.88), max(2, 37 - hs * 0.85), False))
        parts.append(rect(adv - sw * 0.92, 26, sw * 0.92, 74))
    elif ch == "b":
        adv = 58 * w_scale
        parts.append(rect(0, 0, sw * 0.92, 100))
        parts.append(_circle_path(adv * 0.55, 63, adv * 0.45, 37, True) + " " +
                     _circle_path(adv * 0.55, 63, max(2, adv * 0.45 - sw * 0.88), max(2, 37 - hs * 0.85), False))
    elif ch == "c":
        adv = 52 * w_scale
        parts.append(_arc_ring_segment(adv * 0.54, 63, adv * 0.54, 37, max(2, adv * 0.54 - sw * 0.9), max(2, 37 - hs * 0.86), 38, 322))
    elif ch == "d":
        adv = 58 * w_scale
        parts.append(rect(adv - sw * 0.92, 0, sw * 0.92, 100))
        parts.append(_circle_path(adv * 0.45, 63, adv * 0.45, 37, True) + " " +
                     _circle_path(adv * 0.45, 63, max(2, adv * 0.45 - sw * 0.88), max(2, 37 - hs * 0.85), False))
    elif ch == "e":
        adv = 56 * w_scale
        parts.append(_arc_ring_segment(adv * 0.50, 63, adv * 0.50, 37, max(2, adv * 0.50 - sw * 0.9), max(2, 37 - hs * 0.86), 35, 358))
        parts.append(rect(sw * 0.3, 57, adv - sw * 0.45, hs * 0.82))
    elif ch == "f":
        adv = 36 * w_scale
        parts.append(rect(adv * 0.24, 16, sw * 0.9, 84))
        parts.append(_arc_ring_segment(adv * 0.68, 18, adv * 0.44, 18, max(2, adv * 0.44 - sw * 0.85), max(2, 18 - hs * 0.8), 180, 290))
        parts.append(rect(0, 28, adv * 0.88, hs * 0.82))
    elif ch == "g":
        adv = 58 * w_scale
        parts.append(_circle_path(adv * 0.46, 63, adv * 0.46, 37, True) + " " +
                     _circle_path(adv * 0.46, 63, max(2, adv * 0.46 - sw * 0.88), max(2, 37 - hs * 0.85), False))
        parts.append(rect(adv - sw * 0.92, 26, sw * 0.92, 74))
        parts.append(_arc_ring_segment(adv * 0.48, 98, adv * 0.48, 26, max(2, adv * 0.48 - sw * 0.88), max(2, 26 - hs * 0.82), 0, 165))
    elif ch == "h":
        adv = 56 * w_scale
        parts.append(rect(0, 0, sw * 0.92, 100))
        parts.append(rect(adv - sw * 0.92, 54, sw * 0.92, 46))
        parts.append(_arc_ring_segment(adv * 0.52, 56, adv * 0.48, 30, max(2, adv * 0.48 - sw * 0.9), max(2, 30 - hs * 0.85), 180, 360))
    elif ch == "i":
        adv = 24 * max(0.85, w_scale * 0.9)
        cx = adv / 2
        parts.append(rect(cx - sw * 0.45, 28, sw * 0.90, 72))
        parts.append(_circle_path(cx, 10, sw * 0.52, sw * 0.52, True))
    elif ch == "j":
        adv = 28 * max(0.9, w_scale)
        parts.append(rect(adv - sw * 0.92, 28, sw * 0.92, 72))
        parts.append(_circle_path(adv - sw * 0.46, 10, sw * 0.52, sw * 0.52, True))
        parts.append(_arc_ring_segment(adv * 0.42, 98, adv * 0.58, 24, max(2, adv * 0.58 - sw * 0.88), max(2, 24 - hs * 0.8), 0, 155))
    elif ch == "k":
        adv = 54 * w_scale
        parts.append(rect(0, 0, sw * 0.92, 100))
        parts.append(_poly([(sw * 0.7, 65), (adv - sw * 0.95, 28), (adv, 28), (sw * 1.15, 70)]))
        parts.append(_poly([(sw * 1.1, 56), (adv, 100), (adv - sw * 0.98, 100), (sw * 0.7, 66)]))
    elif ch == "l":
        adv = 24 * max(0.85, w_scale * 0.9)
        parts.append(rect(adv / 2 - sw * 0.46, 0, sw * 0.92, 100))
    elif ch == "m":
        adv = 82 * w_scale
        parts.append(rect(0, 28, sw * 0.90, 72))
        parts.append(rect(adv * 0.5 - sw * 0.45, 52, sw * 0.90, 48))
        parts.append(rect(adv - sw * 0.90, 52, sw * 0.90, 48))
        parts.append(_arc_ring_segment(adv * 0.27, 54, adv * 0.27, 28, max(2, adv * 0.27 - sw * 0.88), max(2, 28 - hs * 0.82), 180, 360))
        parts.append(_arc_ring_segment(adv * 0.73, 54, adv * 0.27, 28, max(2, adv * 0.27 - sw * 0.88), max(2, 28 - hs * 0.82), 180, 360))
    elif ch == "n":
        adv = 56 * w_scale
        parts.append(rect(0, 28, sw * 0.92, 72))
        parts.append(rect(adv - sw * 0.92, 54, sw * 0.92, 46))
        parts.append(_arc_ring_segment(adv * 0.50, 56, adv * 0.50, 30, max(2, adv * 0.50 - sw * 0.9), max(2, 30 - hs * 0.85), 180, 360))
    elif ch == "o":
        adv = 58 * w_scale
        parts.append(_circle_path(adv / 2, 63, adv / 2, 37, True) + " " +
                     _circle_path(adv / 2, 63, max(2, adv / 2 - sw * 0.90), max(2, 37 - hs * 0.86), False))
    elif ch == "p":
        adv = 58 * w_scale
        parts.append(rect(0, 28, sw * 0.92, 92))
        parts.append(_circle_path(adv * 0.55, 63, adv * 0.45, 37, True) + " " +
                     _circle_path(adv * 0.55, 63, max(2, adv * 0.45 - sw * 0.88), max(2, 37 - hs * 0.85), False))
    elif ch == "q":
        adv = 58 * w_scale
        parts.append(rect(adv - sw * 0.92, 28, sw * 0.92, 92))
        parts.append(_circle_path(adv * 0.45, 63, adv * 0.45, 37, True) + " " +
                     _circle_path(adv * 0.45, 63, max(2, adv * 0.45 - sw * 0.88), max(2, 37 - hs * 0.85), False))
    elif ch == "r":
        adv = 38 * w_scale
        parts.append(rect(0, 28, sw * 0.92, 72))
        parts.append(_arc_ring_segment(adv * 0.64, 52, adv * 0.56, 26, max(2, adv * 0.56 - sw * 0.88), max(2, 26 - hs * 0.82), 180, 285))
    elif ch == "s":
        adv = 48 * w_scale
        st = hs * 0.84
        p_top = (adv * 0.88, 28.0 + st * 0.90)
        p_mid_l = (adv * 0.14, 46.0)
        p_mid_r = (adv * 0.86, 80.0)
        p_bot = (adv * 0.10, 100.0 - st * 0.90)
        parts.append(_stroke_beziers([
            (p_top, (adv * 0.72, 28.0 + st * 0.4), (adv * 0.14, 28.0 + st * 0.4), p_mid_l),
            (p_mid_l, (adv * 0.14, 63.0), (adv * 0.86, 61.0), p_mid_r),
            (p_mid_r, (adv * 0.86, 100.0 - st * 0.4), (adv * 0.24, 100.0 - st * 0.4), p_bot),
        ], st))
    elif ch == "t":
        adv = 36 * w_scale
        parts.append(rect(adv * 0.28, 6, sw * 0.90, 74))
        parts.append(rect(0, 28, adv * 0.88, hs * 0.82))
        parts.append(_arc_ring_segment(adv * 0.70, 80, adv * 0.42, 20, max(2, adv * 0.42 - sw * 0.85), max(2, 20 - hs * 0.8), 90, 185))
    elif ch == "u":
        adv = 56 * w_scale
        parts.append(rect(0, 28, sw * 0.92, 44))
        parts.append(rect(adv - sw * 0.92, 28, sw * 0.92, 72))
        parts.append(_arc_ring_segment(adv * 0.50, 70, adv * 0.50, 30, max(2, adv * 0.50 - sw * 0.9), max(2, 30 - hs * 0.85), 0, 180))
    elif ch == "v":
        adv = 54 * w_scale
        parts.append(_poly([(0, 28), (sw * 0.96, 28), (adv / 2, 85), (adv - sw * 0.96, 28), (adv, 28),
                            (adv / 2 + sw * 0.46, 100), (adv / 2 - sw * 0.46, 100)]))
    elif ch == "w":
        adv = 74 * w_scale
        parts.append(_poly([(0, 28), (sw * 0.9, 28), (adv * 0.26, 84), (adv * 0.45, 28), (adv * 0.55, 28),
                            (adv * 0.74, 84), (adv - sw * 0.9, 28), (adv, 28), (adv * 0.79, 100), (adv * 0.67, 100),
                            (adv * 0.50, 44), (adv * 0.33, 100), (adv * 0.21, 100)]))
    elif ch == "x":
        adv = 52 * w_scale
        parts.append(_poly([(0, 28), (sw * 1.0, 28), (adv, 100), (adv - sw * 1.0, 100)]))
        parts.append(_poly([(adv - sw * 1.0, 28), (adv, 28), (sw * 1.0, 100), (0, 100)]))
    elif ch == "y":
        adv = 54 * w_scale
        parts.append(_poly([(0, 28), (sw * 0.96, 28), (adv / 2, 86), (adv - sw * 0.96, 28), (adv, 28),
                            (adv * 0.42, 122), (adv * 0.26, 122), (adv * 0.42, 96)]))
    elif ch == "z":
        adv = 50 * w_scale
        parts.extend([rect(0, 28, adv, hs * 0.85), rect(0, 100 - hs * 0.85, adv, hs * 0.85),
                      _poly([(adv - sw * 1.0, 28 + hs * 0.6), (adv, 28 + hs * 0.6), (sw * 1.0, 100 - hs * 0.6), (0, 100 - hs * 0.6)])])
    elif ch == "0":
        adv = 62 * w_scale
        parts.append(_circle_path(adv / 2, 50, adv / 2, 50, True) + " " +
                     _circle_path(adv / 2, 50, max(2, adv / 2 - sw * 0.9), max(2, 50 - hs * 0.9), False))
    elif ch == "1":
        adv = 42 * w_scale
        parts.append(rect(adv * 0.45, 0, sw * 0.9, 100))
        parts.append(_poly([(adv * 0.14, 16), (adv * 0.45, 0), (adv * 0.6, 0), (adv * 0.6, 16), (adv * 0.14, 28)]))
    elif ch == "3":
        adv = 58 * w_scale
        parts.append(_arc_ring_segment(adv * 0.46, 27, adv * 0.50, 27, max(2, adv * 0.50 - sw * 0.9), max(2, 27 - hs * 0.86), -145, 95))
        parts.append(_arc_ring_segment(adv * 0.46, 73, adv * 0.50, 27, max(2, adv * 0.50 - sw * 0.9), max(2, 27 - hs * 0.86), -95, 145))
        parts.append(rect(adv * 0.30, 50 - hs * 0.45, adv * 0.36, hs * 0.9))
    elif ch == "6":
        adv = 60 * w_scale
        parts.append(_arc_ring_segment(adv * 0.52, 50, adv * 0.48, 50, max(2, adv * 0.48 - sw * 0.9), max(2, 50 - hs * 0.9), 150, 325))
        parts.append(_circle_path(adv * 0.50, 68, adv * 0.50, 32, True) + " " +
                     _circle_path(adv * 0.50, 68, max(2, adv * 0.50 - sw * 0.9), max(2, 32 - hs * 0.88), False))
    elif ch == "+":
        adv = 58 * w_scale
        parts.extend([rect(adv / 2 - sw * 0.45, 16, sw * 0.9, 68), rect(0, 50 - hs * 0.45, adv, hs * 0.9)])
    else:
        return "", 30 * w_scale

    return " ".join(p for p in parts if p), adv


def _word_elements(
    text: str,
    x: float,
    y: float,
    scale: float = 1.0,
    fill: str = "{{INK}}",
    sw: float = 14.0,
    w_scale: float = 1.0,
    tracking: float = 10.0,
    rounded: bool = False,
    serif: bool = False,
    italic_deg: float = 0.0,
    crossbar_a: bool = True,
    outline: bool = False,
    stroke_w: float = 4.0,
    per_char_fill: list[str] | None = None,
) -> tuple[str, float]:
    """Build SVG group for text using pure geometric vector paths. Returns (svg_xml, total_width)."""
    cursor = 0.0
    elems: list[str] = []
    for idx, ch in enumerate(text):
        d, adv = _glyph_geom(ch, sw=sw, w_scale=w_scale, rounded=rounded, serif=serif, crossbar_a=crossbar_a)
        if d:
            c_fill = per_char_fill[idx] if per_char_fill and idx < len(per_char_fill) else fill
            if outline:
                style = f'fill="none" stroke="{c_fill}" stroke-width="{_r(stroke_w)}" stroke-linejoin="miter"'
            else:
                style = f'fill="{c_fill}" fill-rule="nonzero"'
            elems.append(f'<path d="{d}" transform="translate({_r(cursor)},0)" {style}/>')
        cursor += adv + (tracking if idx < len(text) - 1 else 0.0)
    total_w = cursor * scale
    if italic_deg:
        # Skew around vertical midpoint y=50 so baseline shifts predictably
        tan_a = math.tan(math.radians(italic_deg))
        off_x = tan_a * 50 * scale
        inner = "\n  ".join(elems)
        xml = (
            f'<g transform="translate({_r(x + off_x)},{_r(y)}) scale({_r(scale)}) '
            f'matrix(1 0 {_r(-tan_a)} 1 0 0)">\n  {inner}\n</g>'
        )
        return xml, total_w + abs(tan_a) * 100 * scale * 0.45
    inner = "\n  ".join(elems)
    xml = f'<g transform="translate({_r(x)},{_r(y)}) scale({_r(scale)})">\n  {inner}\n</g>'
    return xml, total_w


def _svg(w: int, h: int, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">\n'
        f'{body}\n'
        f'</svg>\n'
    )


# ---------------------------------------------------------------------------
# Handcrafted Signature Brand SVG Generators
# ---------------------------------------------------------------------------

def gen_canon_1935() -> str:
    # Early 1935 Canon: sharper serif-hook C and classic upright proportions
    c_hook = (
        "M 118 44 C 107 24 85 18 65 23 C 39 30 22 57 22 86 C 22 117 42 140 72 140 "
        "C 92 140 107 132 118 117 L 111 111 C 102 122 90 128 74 128 "
        "C 51 128 38 110 38 86 C 38 61 52 38 74 34 C 89 31 101 38 106 54 L 82 52 L 118 44 Z"
    )
    a_d = (
        "M 142 66 C 154 58 178 58 184 74 L 184 128 L 195 128 L 195 137 L 172 137 L 172 127 "
        "C 164 136 152 140 142 138 C 127 135 122 117 131 104 C 141 91 159 91 171 91 L 171 76 "
        "C 170 67 156 66 146 72 Z "
        "M 171 99 C 159 99 144 101 143 114 C 142 124 150 130 160 127 C 166 125 170 120 171 114 Z"
    )
    rest, _ = _word_elements("non", 206, 38, scale=0.98, fill="{{INK}}", sw=13.5, w_scale=0.95, tracking=12, serif=True)
    return _svg(460, 160, f'  <path d="{c_hook}" fill="{{{{INK}}}}"/>\n  <path d="{a_d}" fill="{{{{INK}}}}" fill-rule="evenodd"/>\n  {rest}')


def gen_canon_1956() -> str:
    # Iconic 1956-present Canon Red wordmark: inward hooked C + distinctive Canon 'anon'
    red = "#CC0000"
    c_hook = (
        "M 122 44 C 110 21 86 14 62 20 C 30 28 16 58 16 86 C 16 119 40 144 74 144 "
        "C 96 144 114 134 124 118 L 115 111 C 107 123 93 130 76 130 "
        "C 51 130 37 112 37 86 C 37 59 52 35 76 32 C 91 30 101 38 103 55 L 77 45 L 122 44 Z"
    )
    a_d = (
        "M 135 64 C 150 56 184 55 188 76 L 188 140 L 171 140 L 171 129 "
        "C 162 139 149 143 138 141 C 122 138 117 119 127 104 C 138 89 157 90 171 91 L 171 78 "
        "C 170 67 154 66 141 72 Z "
        "M 171 100 C 158 99 143 102 142 115 C 141 125 149 130 159 128 C 166 126 170 121 171 115 Z"
    )
    n1 = "M 206 60 L 224 60 L 224 72 C 234 59 253 56 266 64 C 274 70 278 81 278 96 L 278 140 L 260 140 L 260 95 C 260 80 252 72 241 72 C 231 72 224 81 224 94 L 224 140 L 206 140 Z"
    o = (
        "M 332 57 C 357 57 374 75 374 99 C 374 124 357 142 332 142 C 307 142 290 124 290 99 C 290 75 307 57 332 57 Z "
        "M 332 70 C 321 70 314 82 314 99 C 314 117 321 129 332 129 C 343 129 350 117 350 99 C 350 82 343 70 332 70 Z"
    )
    n2 = "M 388 60 L 406 60 L 406 72 C 234 59 253 56 266 64".replace("234", "416").replace("253", "435").replace("266", "448")
    n2 = "M 388 60 L 406 60 L 406 72 C 416 59 435 56 448 64 C 456 70 460 81 460 96 L 460 140 L 442 140 L 442 95 C 442 80 434 72 423 72 C 413 72 406 81 406 94 L 406 140 L 388 140 Z"
    return _svg(476, 160, (
        f'  <path d="{c_hook}" fill="{red}"/>\n'
        f'  <path d="{a_d}" fill="{red}" fill-rule="evenodd"/>\n'
        f'  <path d="{n1}" fill="{red}"/>\n'
        f'  <path d="{o}" fill="{red}" fill-rule="evenodd"/>\n'
        f'  <path d="{n2}" fill="{red}"/>'
    ))


def gen_nikon_1968() -> str:
    # Kamekura Track Oval: black outer stadium, contrast inner ring, yellow fill, bold upright Nikon wordmark
    word, _ = _word_elements("Nikon", 52, 50, scale=0.66, fill="{{BADGE_DARK}}", sw=16.5, w_scale=0.98, tracking=8)
    return _svg(360, 160, (
        f'  <rect x="8" y="8" width="344" height="144" rx="72" fill="{{{{INK}}}}"/>\n'
        f'  <rect x="17" y="17" width="326" height="126" rx="63" fill="{{{{CONTRAST}}}}"/>\n'
        f'  <rect x="23" y="23" width="314" height="114" rx="57" fill="#FFE100"/>\n'
        f'  {word}'
    ))


def gen_nikon_1988() -> str:
    # 1988-2002 Italic Nikon Wordmark (slanted ~13 deg)
    word, _ = _word_elements("Nikon", 24, 30, scale=0.98, fill="{{INK}}", sw=18.0, w_scale=1.02, tracking=8, italic_deg=13.5)
    return _svg(360, 160, f"  {word}")


def gen_nikon_2003() -> str:
    # 2003-present Nikon Yellow square with ascending white light-beam bands + italic Nikon wordmark
    rays = []
    # Diagonal radiating light beams sweeping left-to-right across yellow square
    for x_l, h_l, x_r, h_r in [
        (0, 6, 148, 30),
        (0, 8, 148, 22),
        (0, 6, 148, 14),
    ]:
        pass
    beam_polys = [
        [(0, 128), (148, 88), (148, 108), (0, 144)],
        [(0, 104), (148, 52), (148, 70), (0, 118)],
        [(0, 82), (148, 20), (148, 36), (0, 94)],
        [(0, 62), (132, 0), (148, 0), (148, 6), (0, 72)],
        [(0, 44), (92, 0), (116, 0), (0, 52)],
    ]
    ray_svg = "\n    ".join(f'<path d="{_poly(p)}" fill="{{{{BADGE_FG}}}}"/>' for p in beam_polys)
    word, _ = _word_elements("Nikon", 174, 34, scale=0.92, fill="{{INK}}", sw=18.5, w_scale=1.02, tracking=8, italic_deg=13.5)
    return _svg(500, 160, (
        f'  <defs><clipPath id="nikon-sq"><rect x="10" y="10" width="140" height="140" rx="10"/></clipPath></defs>\n'
        f'  <rect x="10" y="10" width="140" height="140" rx="10" fill="#FFE100"/>\n'
        f'  <g transform="translate(10,10)" clip-path="url(#nikon-sq)">\n    {ray_svg}\n  </g>\n'
        f'  {word}'
    ))


def gen_sony_1973() -> str:
    # Classic Clarendon high-contrast slab serif SONY
    word, w = _word_elements("SONY", 30, 32, scale=0.96, fill="{{INK}}", sw=16.5, w_scale=1.06, tracking=16, serif=True)
    return _svg(390, 160, f"  {word}")


def gen_sony_alpha_2006() -> str:
    # Sony wordmark + iconic Cinnabar Orange sweeping alpha ribbon
    word, _ = _word_elements("SONY", 16, 38, scale=0.84, fill="{{INK}}", sw=16.5, w_scale=1.06, tracking=14, serif=True)
    alpha = (
        "M 426 60 C 402 22 356 26 346 66 C 337 103 360 132 388 128 "
        "C 409 125 421 103 431 76 C 438 56 446 42 460 36 L 466 50 "
        "C 453 56 445 71 437 94 C 443 111 452 118 466 114 L 469 128 "
        "C 449 135 434 126 425 106 C 412 128 394 142 374 140 "
        "C 339 136 321 99 330 60 C 340 16 392 8 424 44 Z"
    )
    return _svg(492, 160, (
        f"  {word}\n"
        f'  <rect x="304" y="34" width="3" height="92" fill="{{{{INK_MUTED}}}}"/>\n'
        f'  <path d="{alpha}" fill="#E34234"/>'
    ))


def gen_minolta_1981() -> str:
    # Saul Bass striped blue optical globe + lowercase minolta
    stripes = []
    for sy, sh in [(12, 16), (34, 15), (56, 14), (77, 12), (96, 10)]:
        stripes.append(f'<rect x="0" y="{sy}" width="124" height="{sh}" fill="{{{{BADGE_FG}}}}"/>')
    word, _ = _word_elements("minolta", 150, 32, scale=0.72, fill="{{INK}}", sw=13.5, w_scale=0.94, tracking=10)
    return _svg(520, 160, (
        f'  <defs><clipPath id="min-g"><circle cx="62" cy="62" r="56"/></clipPath></defs>\n'
        f'  <g transform="translate(14,18)">\n'
        f'    <circle cx="62" cy="62" r="56" fill="#005BAC"/>\n'
        f'    <g clip-path="url(#min-g)">\n      ' + "\n      ".join(stripes) + '\n    </g>\n'
        f'  </g>\n'
        f'  {word}'
    ))


def gen_konica_minolta_2003() -> str:
    stripes = [f'<rect x="0" y="{sy}" width="112" height="{sh}" fill="{{{{BADGE_FG}}}}"/>'
               for sy, sh in [(12, 14), (32, 13), (52, 12), (71, 10), (88, 8)]]
    w1, _ = _word_elements("KONICA", 140, 26, scale=0.52, fill="#005BAC", sw=14.5, w_scale=0.98, tracking=10)
    w2, _ = _word_elements("MINOLTA", 140, 84, scale=0.52, fill="#005BAC", sw=14.5, w_scale=0.98, tracking=10)
    return _svg(460, 160, (
        f'  <defs><clipPath id="km-g"><circle cx="56" cy="56" r="52"/></clipPath></defs>\n'
        f'  <g transform="translate(14,24)">\n'
        f'    <circle cx="56" cy="56" r="52" fill="#005BAC"/>\n'
        f'    <g clip-path="url(#km-g)">\n      ' + "\n      ".join(stripes) + '\n    </g>\n'
        f'  </g>\n'
        f'  {w1}\n  {w2}'
    ))


def gen_fujifilm_1980() -> str:
    # 1980-2006 Landor Green/Red Film Box FUJI + bold FUJIFILM wordmark
    fuji_box, _ = _word_elements("FUJI", 28, 36, scale=0.44, fill="{{BADGE_FG}}", sw=17.0, w_scale=1.0, tracking=8)
    word, _ = _word_elements("FUJIFILM", 162, 40, scale=0.76, fill="#00843D", sw=15.5, w_scale=0.92, tracking=8)
    return _svg(580, 160, (
        f'  <rect x="12" y="20" width="132" height="120" rx="8" fill="#00843D"/>\n'
        f'  <rect x="12" y="100" width="132" height="6" fill="{{{{CONTRAST}}}}"/>\n'
        f'  <rect x="12" y="106" width="132" height="18" fill="#FB0020"/>\n'
        f'  {fuji_box}\n'
        f'  {word}'
    ))


def gen_fujifilm_2006() -> str:
    # 2006-present FUJIFILM: 4th letter (first I) has iconic diagonal red notch
    # Draw F U J  [I with notch]  F I L M manually on tight grid
    w_fuj, adv1 = _word_elements("FUJ", 16, 36, scale=0.84, fill="{{INK}}", sw=15.5, w_scale=0.96, tracking=8)
    ix = 16 + adv1 + 8 * 0.84
    # Notched 'I': main bottom stem + red top angled wedge
    i_stem = _poly([(ix + 2, 54), (ix + 16, 46), (ix + 16, 120), (ix + 2, 120)])
    i_notch = _poly([(ix + 2, 36), (ix + 16, 36), (ix + 16, 42), (ix + 2, 50)])
    w_film, _ = _word_elements("FILM", ix + 26, 36, scale=0.84, fill="{{INK}}", sw=15.5, w_scale=0.96, tracking=8)
    return _svg(540, 160, f'  {w_fuj}\n  <path d="{i_stem}" fill="{{{{INK}}}}"/>\n  <path d="{i_notch}" fill="#FB0020"/>\n  {w_film}')


def gen_olympus_1970() -> str:
    word, _ = _word_elements("OLYMPUS", 20, 34, scale=0.84, fill="#08107B", sw=15.0, w_scale=0.96, tracking=10)
    return _svg(540, 160, f"  {word}")


def gen_olympus_2001() -> str:
    word, _ = _word_elements("OLYMPUS", 20, 20, scale=0.82, fill="#08107B", sw=15.0, w_scale=0.96, tracking=10)
    # Opto-Digital Gold/Yellow underline bar
    bar = _poly([(20, 122), (512, 122), (506, 134), (20, 134)])
    return _svg(536, 160, f'  {word}\n  <path d="{bar}" fill="#EBB700"/>')


def gen_om_system_2021() -> str:
    om, _ = _word_elements("OM", 48, 22, scale=0.68, fill="{{INK}}", sw=16.5, w_scale=1.06, tracking=10)
    sys_w, _ = _word_elements("SYSTEM", 36, 108, scale=0.25, fill="{{INK}}", sw=12.5, w_scale=1.05, tracking=42)
    return _svg(220, 160, (
        f'  <rect x="14" y="10" width="192" height="140" fill="none" stroke="{{{{INK}}}}" stroke-width="6"/>\n'
        f'  {om}\n'
        f'  {sys_w}'
    ))


def gen_panasonic_1971() -> str:
    word, _ = _word_elements("Panasonic", 16, 36, scale=0.80, fill="#0041C0", sw=15.5, w_scale=0.95, tracking=6)
    return _svg(520, 160, f"  {word}")


def gen_lumix_2001() -> str:
    # Stylized crimson L emblem + bold geometric LUMIX
    l_emblem = _poly([(16, 26), (48, 26), (38, 106), (112, 106), (104, 134), (6, 134)])
    word, _ = _word_elements("LUMIX", 128, 34, scale=0.88, fill="{{INK}}", sw=16.0, w_scale=1.02, tracking=12)
    return _svg(500, 160, f'  <path d="{l_emblem}" fill="#E60012"/>\n  {word}')


def gen_pentax_1957() -> str:
    asahi, _ = _word_elements("ASAHI", 110, 18, scale=0.40, fill="{{INK_MUTED}}", sw=13.5, w_scale=1.1, tracking=28)
    pentax, _ = _word_elements("PENTAX", 24, 70, scale=0.72, fill="{{INK}}", sw=17.5, w_scale=1.0, tracking=8)
    return _svg(440, 160, f"  {asahi}\n  {pentax}")


def gen_pentax_1987() -> str:
    pentax, _ = _word_elements("PENTAX", 18, 30, scale=0.94, fill="#FF0013", sw=18.5, w_scale=1.0, tracking=6)
    return _svg(460, 160, f"  {pentax}")


def gen_ricoh_1986() -> str:
    # Solid red R + thick outline red ICOH
    r_solid, r_adv = _word_elements("R", 18, 30, scale=0.92, fill="#D61B3E", sw=18.0, w_scale=1.02, tracking=8)
    icoh_out, _ = _word_elements("ICOH", 18 + r_adv + 14, 30, scale=0.92, fill="#D61B3E", sw=18.0, w_scale=1.02, tracking=12, outline=True, stroke_w=4.2)
    return _svg(400, 160, f"  {r_solid}\n  {icoh_out}")


def gen_ricoh_2005() -> str:
    word, _ = _word_elements("RICOH", 20, 30, scale=0.94, fill="#D61B3E", sw=17.5, w_scale=1.04, tracking=14, rounded=True)
    return _svg(420, 160, f"  {word}")


def gen_leica_dot(script: str) -> str:
    # Classic Leica Red Dot with handcrafted white script ('Leitz' or 'Leica')
    if script == "Leitz":
        script_path = (
            # Stylized sweeping cursive 'Leitz'
            "M 56 46 C 46 68 38 92 32 106 C 48 104 64 102 74 100 "
            "M 76 86 C 84 82 92 78 90 73 C 86 68 74 75 74 86 C 74 96 86 98 96 92 "
            "M 102 73 L 98 95 M 104 58 L 105 60 "
            "M 114 62 L 109 95 M 106 72 L 120 71 "
            "M 122 74 L 136 74 L 120 95 L 136 95"
        )
    else:
        script_path = (
            # Signature cursive 'Leica' loop & underline tail
            "M 56 44 C 46 66 36 90 29 104 C 46 101 62 98 73 96 "
            "M 75 84 C 84 81 91 77 88 72 C 84 68 74 74 74 84 C 74 94 84 96 94 90 "
            "M 101 73 L 97 94 M 103 58 L 104 60 "
            "M 122 75 C 114 70 105 78 106 88 C 107 96 117 97 125 91 "
            "M 142 75 C 134 70 126 78 127 88 C 128 96 138 94 143 85 L 144 74 L 141 94 C 141 97 146 97 151 91"
        )
    return _svg(180, 180, (
        f'  <circle cx="90" cy="90" r="80" fill="#E20612"/>\n'
        f'  <path d="{script_path}" fill="none" stroke="{{{{BADGE_FG}}}}" stroke-width="6.5" '
        f'stroke-linecap="round" stroke-linejoin="round"/>\n'
        f'  <path d="M 38 112 Q 92 104 146 109" fill="none" stroke="{{{{BADGE_FG}}}}" stroke-width="4.2" stroke-linecap="round"/>'
    ))


def gen_sigma_1961() -> str:
    word, _ = _word_elements("SIGMA", 20, 32, scale=0.92, fill="{{INK}}", sw=17.5, w_scale=1.02, tracking=12, italic_deg=14.0)
    return _svg(440, 160, f"  {word}")


def gen_sigma_2012() -> str:
    word, _ = _word_elements("SIGMA", 20, 32, scale=0.94, fill="{{INK}}", sw=15.0, w_scale=1.02, tracking=16)
    return _svg(420, 160, f"  {word}")


def gen_sigma_2025() -> str:
    # 2025 Stockholm Design Lab rebrand: optical 2-lens circle Sigma emblem + Sigma Serif wordmark
    sigma_mark = (
        "M 12 20 L 108 20 L 108 38 L 46 38 L 82 80 L 46 122 L 108 122 L 108 140 L 12 140 L 58 80 Z"
    )
    lens_arc = (
        '<circle cx="96" cy="80" r="18" fill="none" stroke="{{INK}}" stroke-width="5"/>'
    )
    word, _ = _word_elements("SIGMA", 136, 36, scale=0.86, fill="{{INK}}", sw=13.5, w_scale=1.04, tracking=16, serif=True)
    return _svg(520, 160, f'  <path d="{sigma_mark}" fill="{{{{INK}}}}"/>\n  {lens_arc}\n  {word}')


def gen_hasselblad_1990() -> str:
    # Bold square H + heavy block HASSELBLAD
    h_box = (
        '<rect x="12" y="24" width="112" height="112" rx="6" fill="{{INK}}"/>'
        '<path d="M 38 44 L 54 44 L 54 72 L 82 72 L 82 44 L 98 44 L 98 116 L 82 116 L 82 88 L 54 88 L 54 116 L 38 116 Z" fill="{{CONTRAST}}"/>'
    )
    word, _ = _word_elements("HASSELBLAD", 142, 46, scale=0.64, fill="{{INK}}", sw=15.5, w_scale=0.96, tracking=10)
    return _svg(680, 160, f"  {h_box}\n  {word}")


def gen_hasselblad_2015() -> str:
    # Slim wide-tracked HASSELBLAD + clean open square H
    h_emblem = (
        '<rect x="14" y="42" width="76" height="76" fill="none" stroke="{{INK}}" stroke-width="5.5"/>'
        '<path d="M 34 58 L 43 58 L 43 76 L 61 76 L 61 58 L 70 58 L 70 102 L 61 102 L 61 84 L 43 84 L 43 102 L 34 102 Z" fill="{{INK}}"/>'
        '<circle cx="84" cy="48" r="4" fill="#FF6A00"/>'
    )
    word, _ = _word_elements("HASSELBLAD", 112, 54, scale=0.52, fill="{{INK}}", sw=10.5, w_scale=0.96, tracking=28)
    return _svg(650, 160, f"  {h_emblem}\n  {word}")


def gen_kodak_1987() -> str:
    # Classic K-Box (#FFB700 yellow outer + {{KODAK_K}} geometric K + Kodak)
    k_beam = _poly([(22, 22), (118, 22), (118, 46), (56, 80), (118, 114), (118, 138), (22, 138), (22, 108), (44, 108), (44, 52), (22, 52)])
    word, _ = _word_elements("Kodak", 146, 36, scale=0.86, fill="#ED0000", sw=16.0, w_scale=0.98, tracking=8)
    return _svg(520, 160, (
        f'  <rect x="10" y="10" width="124" height="140" rx="10" fill="#FFB700"/>\n'
        f'  <path d="{k_beam}" fill="{{{{KODAK_K}}}}"/>\n'
        f'  {word}'
    ))


def gen_kodak_2006() -> str:
    # 2006-2016 Allen Hori Rounded Red Wordmark + subtle gold underline accent (KODAK C875 era!)
    word, _ = _word_elements("Kodak", 24, 24, scale=0.98, fill="#ED0000", sw=17.5, w_scale=1.02, tracking=10, rounded=True)
    accent = _poly([(26, 132), (390, 132), (384, 142), (26, 142)])
    return _svg(416, 160, f'  {word}\n  <path d="{accent}" fill="#FFB700"/>')


def gen_kodak_2016() -> str:
    # Work-Order restored K-Box + vertically stacked KODAK
    k_beam = _poly([(16, 16), (110, 16), (110, 42), (48, 80), (110, 118), (110, 144), (16, 144), (16, 112), (40, 112), (40, 48), (16, 48)])
    letters = []
    for idx, ch in enumerate("KODAK"):
        g, _ = _word_elements(ch, 128, 12 + idx * 28, scale=0.22, fill="{{BADGE_DARK}}", sw=18.0, w_scale=1.0, tracking=0)
        letters.append(g)
    return _svg(172, 160, (
        f'  <rect x="6" y="6" width="158" height="148" rx="8" fill="#FFB700"/>\n'
        f'  <path d="{k_beam}" fill="{{{{KODAK_K}}}}"/>\n  ' + "\n  ".join(letters)
    ))


def gen_samsung_1993() -> str:
    # Tilted -10 deg Samsung Blue ellipse with rim-breaking S and G, crossbar-less A
    word, _ = _word_elements("SAMSUNG", 22, 48, scale=0.58, fill="{{BADGE_FG}}", sw=17.0, w_scale=0.94, tracking=10, crossbar_a=False)
    return _svg(390, 160, (
        f'  <ellipse cx="195" cy="80" rx="182" ry="62" transform="rotate(-9 195 80)" fill="#1428A0"/>\n'
        f'  {word}'
    ))


def gen_samsung_2015() -> str:
    word, _ = _word_elements("SAMSUNG", 16, 36, scale=0.80, fill="#1428A0", sw=16.5, w_scale=0.94, tracking=12, crossbar_a=False)
    return _svg(490, 160, f"  {word}")


def gen_polaroid(era: str) -> str:
    colors = ["#D60026", "#FF8200", "#FFB500", "#00A651", "#00AEEF"]
    if era == "1977":
        bars = "\n  ".join(f'<rect x="{18 + i * 22}" y="20" width="18" height="118" fill="{c}"/>' for i, c in enumerate(colors))
        word, _ = _word_elements("Polaroid", 142, 36, scale=0.76, fill="{{INK}}", sw=15.0, w_scale=0.95, tracking=6, rounded=True)
        return _svg(530, 160, f"  {bars}\n  {word}")
    if era == "2017":
        bars = "\n  ".join(f'<rect x="{20 + i * 76}" y="122" width="76" height="14" fill="{c}"/>' for i, c in enumerate(colors))
        w1, _ = _word_elements("Polaroid", 20, 16, scale=0.58, fill="{{INK}}", sw=14.0, w_scale=0.96, tracking=8)
        w2, _ = _word_elements("Originals", 20, 74, scale=0.40, fill="{{INK_MUTED}}", sw=12.0, w_scale=0.96, tracking=10)
        return _svg(420, 160, f"  {w1}\n  {w2}\n  {bars}")
    bars = "\n  ".join(f'<rect x="14" y="{24 + i * 22}" width="92" height="18" fill="{c}"/>' for i, c in enumerate(colors))
    word, _ = _word_elements("Polaroid", 124, 34, scale=0.78, fill="{{INK}}", sw=15.0, w_scale=0.96, tracking=6, rounded=True)
    return _svg(520, 160, f"  {bars}\n  {word}")


def _apple_body_path() -> str:
    # Classic balanced bitten-apple contour inside [25..155] x [42..168]
    return (
        "M 134 94 C 134 78 147 70 148 69 C 140 58 128 56 123 56 "
        "C 113 55 103 62 98 62 C 93 62 84 56 76 56 C 64 56 53 63 47 74 "
        "C 34 96 44 128 56 146 C 62 155 69 165 78 164 C 87 164 90 158 101 158 "
        "C 112 158 114 164 124 164 C 134 164 140 155 146 146 "
        "C 153 136 156 126 156 125 C 156 125 134 116 134 94 Z"
    )


def _apple_leaf_path() -> str:
    return "M 114 48 C 120 40 123 30 122 20 C 113 21 103 26 98 34 C 93 41 89 51 90 61 C 100 62 109 56 114 48 Z"


def gen_apple(era: str) -> str:
    body = _apple_body_path()
    leaf = _apple_leaf_path()
    if era == "1977":
        rainbow = ["#61BB46", "#FDB827", "#F5821F", "#E03A3E", "#963D97", "#009DDC"]
        stripes = "\n    ".join(
            f'<rect x="20" y="{16 + i * 26}" width="150" height="27" fill="{c}"/>'
            for i, c in enumerate(rainbow)
        )
        return _svg(180, 180, (
            f'  <defs><clipPath id="ap77"><path d="{body} {leaf}"/></clipPath></defs>\n'
            f'  <g clip-path="url(#ap77)">\n    {stripes}\n  </g>'
        ))
    if era == "2007":
        return _svg(180, 180, (
            '  <defs>\n'
            '    <linearGradient id="ap-chrome" x1="0" y1="0" x2="0" y2="1">\n'
            '      <stop offset="0%" stop-color="#E4E7EA"/><stop offset="48%" stop-color="#9BA2A8"/>\n'
            '      <stop offset="52%" stop-color="#6E757C"/><stop offset="100%" stop-color="#C8CFD4"/>\n'
            '    </linearGradient>\n'
            '    <clipPath id="ap07"><path d="' + body + ' ' + leaf + '"/></clipPath>\n'
            '  </defs>\n'
            f'  <path d="{body} {leaf}" fill="url(#ap-chrome)"/>\n'
            '  <ellipse cx="90" cy="54" rx="58" ry="38" fill="#FFFFFF" fill-opacity="0.34" clip-path="url(#ap07)"/>'
        ))
    return _svg(180, 180, f'  <path d="{body} {leaf}" fill="{{{{INK}}}}"/>')


def gen_google(era: str) -> str:
    colors = ["#4285F4", "#EA4335", "#FBBC05", "#4285F4", "#34A853", "#EA4335"]
    if era == "2010":
        catull = ["#4285F4", "#DB4437", "#FBBC04", "#4285F4", "#0F9D58", "#DB4437"]
        word, _ = _word_elements("Google", 18, 28, scale=0.86, sw=14.0, w_scale=0.96, tracking=8, serif=True, per_char_fill=catull)
        return _svg(390, 160, f"  {word}")
    # 2015 Product Sans + 4-color G mark
    g_mark = (
        f'<path d="{_arc_ring_segment(72, 80, 56, 56, 34, 34, 315, 45)}" fill="#EA4335"/>'
        f'<path d="{_arc_ring_segment(72, 80, 56, 56, 34, 34, 145, 225)}" fill="#FBBC05"/>'
        f'<path d="{_arc_ring_segment(72, 80, 56, 56, 34, 34, 45, 145)}" fill="#34A853"/>'
        f'<path d="{_arc_ring_segment(72, 80, 56, 56, 34, 34, 355, 55)}" fill="#4285F4"/>'
        '<rect x="72" y="70" width="56" height="20" fill="#4285F4"/>'
    )
    # Build proper 4-color G arc cleanly (top red, left yellow, bottom green, right blue)
    g_mark = (
        f'<path d="{_arc_ring_segment(72, 80, 56, 56, 34, 34, 215, 325)}" fill="#EA4335"/>'
        f'<path d="{_arc_ring_segment(72, 80, 56, 56, 34, 34, 140, 220)}" fill="#FBBC05"/>'
        f'<path d="{_arc_ring_segment(72, 80, 56, 56, 34, 34, 30, 144)}" fill="#34A853"/>'
        f'<path d="{_arc_ring_segment(72, 80, 56, 56, 34, 34, -5, 36)}" fill="#4285F4"/>'
        '<rect x="72" y="69" width="56" height="22" fill="#4285F4"/>'
    )
    word, _ = _word_elements("Google", 150, 34, scale=0.84, sw=14.5, w_scale=0.96, tracking=8, per_char_fill=colors)
    return _svg(520, 160, f"  {g_mark}\n  {word}")


def _squircle_path(cx: float, cy: float, r: float, n: float = 3.0, steps: int = 72) -> str:
    pts = []
    for k in range(steps):
        t = 2 * math.pi * k / steps
        ct, st = math.cos(t), math.sin(t)
        x = cx + r * math.copysign(abs(ct) ** (2 / n), ct)
        y = cy + r * math.copysign(abs(st) ** (2 / n), st)
        pts.append((x, y))
    return _poly(pts)


def gen_xiaomi(era: str) -> str:
    mi_glyphs = (
        '<path d="M 38 112 L 38 52 L 88 52 C 98 52 104 58 104 68 L 104 112 L 88 112 L 88 68 L 78 68 L 78 112 L 62 112 L 62 68 L 54 68 L 54 112 Z" fill="{{BADGE_FG}}"/>'
        '<rect x="114" y="52" width="16" height="60" fill="{{BADGE_FG}}"/>'
    )
    if era == "2014":
        return _svg(170, 170, f'  <rect x="12" y="12" width="146" height="146" rx="14" fill="#FF6700"/>\n  {mi_glyphs}')
    sq = _squircle_path(85, 85, 73, n=3.0)
    word, _ = _word_elements("xiaomi", 174, 44, scale=0.72, fill="{{INK}}", sw=13.5, w_scale=0.96, tracking=10, rounded=True)
    return _svg(460, 170, f'  <path d="{sq}" fill="#FF6700"/>\n  {mi_glyphs}\n  {word}')


def gen_huawei(era: str) -> str:
    # 8 symmetrical radiating petals
    petals = []
    angles = [-67.5, -45, -22.5, -6, 6, 22.5, 45, 67.5]
    cx, cy = 84.0, 114.0
    for idx, ang in enumerate(angles):
        rad = math.radians(ang - 90)
        ux, uy = math.cos(rad), math.sin(rad)
        px, py = -uy, ux
        tip = 78 if abs(ang) < 35 else 66
        w_mid = 11.5
        p_svg = _poly([
            (cx + ux * 16, cy + uy * 16),
            (cx + ux * (tip * 0.55) + px * w_mid, cy + uy * (tip * 0.55) + py * w_mid),
            (cx + ux * tip, cy + uy * tip),
            (cx + ux * (tip * 0.55) - px * w_mid, cy + uy * (tip * 0.55) - py * w_mid),
        ])
        if era == "2006":
            petals.append(f'<path d="{p_svg}" fill="url(#hw-grad)"/>')
        else:
            petals.append(f'<path d="{p_svg}" fill="#CF0A2C"/>')
    defs = (
        '  <defs><linearGradient id="hw-grad" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#FF5544"/><stop offset="100%" stop-color="#A60014"/>'
        '</linearGradient></defs>\n'
    ) if era == "2006" else ""
    word, _ = _word_elements(
        "HUAWEI", 168, 42, scale=0.76, fill="{{INK}}", sw=15.0, w_scale=0.96, tracking=10,
        rounded=(era == "2006")
    )
    return _svg(540, 160, f'{defs}  ' + "\n  ".join(petals) + f"\n  {word}")


def gen_lg(era: str) -> str:
    face = (
        '<circle cx="76" cy="80" r="64" fill="' + ("#FD312E" if era == "2023" else ("url(#lg3d)" if era == "1995" else "#A50034")) + '"/>'
        '<path d="M 76 36 L 76 86 L 94 86" fill="none" stroke="{{BADGE_FG}}" stroke-width="8" stroke-linecap="square"/>'
        '<circle cx="52" cy="58" r="7" fill="{{BADGE_FG}}"/>'
        '<path d="M 116 78 A 42 42 0 1 1 76 38 M 92 78 L 118 78" fill="none" stroke="{{BADGE_FG}}" stroke-width="8" stroke-linecap="round"/>'
    )
    defs = (
        '  <defs><radialGradient id="lg3d" cx="35%" cy="30%" r="70%">'
        '<stop offset="0%" stop-color="#E6225E"/><stop offset="100%" stop-color="#8A0028"/>'
        '</radialGradient></defs>\n'
    ) if era == "1995" else ""
    word, _ = _word_elements("LG", 158, 34, scale=0.90, fill="{{INK_MUTED}}", sw=16.5 if era == "1995" else 13.5, w_scale=1.0, tracking=10)
    return _svg(310, 160, f"{defs}  {face}\n  {word}")


def gen_goldstar() -> str:
    crown = _poly([(16, 114), (24, 42), (48, 72), (72, 26), (96, 72), (120, 42), (128, 114)])
    word, _ = _word_elements("GoldStar", 148, 42, scale=0.72, fill="{{INK}}", sw=15.0, w_scale=0.95, tracking=6)
    return _svg(520, 160, f'  <path d="{crown}" fill="#C8102E"/>\n  {word}')


def gen_sony_ericsson() -> str:
    orb = (
        '  <defs><radialGradient id="se-orb" cx="38%" cy="30%" r="68%">'
        '<stop offset="0%" stop-color="#B7FF6A"/><stop offset="55%" stop-color="#00A651"/><stop offset="100%" stop-color="#1E4D2B"/>'
        '</radialGradient></defs>\n'
        '  <circle cx="68" cy="80" r="54" fill="#B8C0C8"/>\n'
        '  <circle cx="68" cy="80" r="46" fill="url(#se-orb)"/>\n'
        '  <path d="M 38 66 Q 68 42 98 76 Q 68 112 38 82" fill="none" stroke="{{BADGE_FG}}" stroke-width="5" stroke-opacity="0.7"/>\n'
    )
    word, _ = _word_elements("Sony Ericsson", 136, 48, scale=0.56, fill="{{INK}}", sw=14.0, w_scale=0.94, tracking=6)
    return _svg(620, 160, f"{orb}  {word}")


def gen_motorola(era: str) -> str:
    batwing = "M 32 122 L 54 34 L 74 88 L 94 34 L 116 122 L 99 122 L 91 84 L 74 114 L 57 84 L 49 122 Z"
    if era == "1955":
        circle = '<circle cx="74" cy="80" r="62" fill="#005FBE"/>'
        word, _ = _word_elements("MOTOROLA", 152, 42, scale=0.66, fill="{{INK}}", sw=16.0, w_scale=0.96, tracking=8, italic_deg=14)
        return _svg(600, 160, f'  {circle}\n  <path d="{batwing}" fill="{{{{BADGE_FG}}}}"/>\n  {word}')
    circle = '<circle cx="74" cy="80" r="62" fill="#5C92FA"/>'
    word, _ = _word_elements("motorola", 152, 42, scale=0.70, fill="{{INK}}", sw=13.5, w_scale=0.95, tracking=8, rounded=True)
    return _svg(550, 160, f'  {circle}\n  <path d="{batwing}" fill="{{{{BADGE_FG}}}}"/>\n  {word}')


def gen_nokia(era: str) -> str:
    if era == "1992":
        word, _ = _word_elements("NOKIA", 20, 30, scale=0.96, fill="#124191", sw=19.0, w_scale=1.06, tracking=10)
        return _svg(430, 160, f"  {word}")
    # 2023 Segmented Lippincott geometric NOKIA
    n = (
        _poly([(16, 126), (16, 34), (32, 34), (86, 108), (86, 126), (70, 126), (30, 68), (30, 126)])
        + " " + _poly([(72, 34), (86, 34), (86, 90), (72, 72)])
    )
    o = _arc_ring_segment(136, 80, 42, 46, 26, 30, 35, 325)
    k = _poly([(192, 34), (208, 34), (208, 126), (192, 126)]) + " " + _poly([(222, 80), (254, 34), (272, 34), (238, 80), (272, 126), (254, 126)])
    i = _poly([(286, 34), (302, 34), (302, 126), (286, 126)])
    a = _poly([(320, 126), (354, 34), (370, 34), (404, 126), (386, 126), (362, 56), (338, 126)])
    return _svg(424, 160, (
        f'  <path d="{n}" fill="#005AFF"/>\n'
        f'  <path d="{o}" fill="#005AFF"/>\n'
        f'  <path d="{k}" fill="#005AFF"/>\n'
        f'  <path d="{i}" fill="#005AFF"/>\n'
        f'  <path d="{a}" fill="#005AFF"/>'
    ))


def gen_gopro(era: str) -> str:
    if era == "2004":
        w1, a1 = _word_elements("Go", 20, 26, scale=1.0, fill="{{INK}}", sw=18.5, w_scale=1.04, tracking=6)
        w2, _ = _word_elements("Pro", 20 + a1 + 6, 32, scale=0.88, fill="{{INK}}", sw=15.0, w_scale=1.0, tracking=6)
        return _svg(360, 160, f"  {w1}\n  {w2}")
    word, _ = _word_elements("GoPro", 18, 16, scale=0.82, fill="{{INK}}", sw=15.5, w_scale=1.02, tracking=8)
    sq_colors = ["#00AEEF", "#0089CF", "#005DAC", "#FFFFFF"]
    squares = []
    for idx, c in enumerate(sq_colors):
        stroke = ' stroke="{{INK_MUTED}}" stroke-width="2"' if c == "#FFFFFF" else ""
        squares.append(f'<rect x="{22 + idx * 72}" y="114" width="60" height="28" rx="3" fill="{c}"{stroke}/>')
    return _svg(340, 160, f"  {word}\n  " + "\n  ".join(squares))


def gen_dji(era: str) -> str:
    if era == "2006":
        word, _ = _word_elements("DJI", 32, 32, scale=0.96, fill="#0971CE", sw=16.5, w_scale=1.08, tracking=18)
        return _svg(300, 160, f"  {word}")
    # Iconic 2012+ heavy slanted geometric DJI
    d_p = "M 32 32 L 106 32 C 134 32 146 52 140 80 C 134 108 112 128 84 128 L 16 128 L 22 100 L 82 100 C 98 100 108 92 110 80 C 112 68 106 60 90 60 L 26 60 Z"
    j_p = "M 164 32 L 204 32 L 188 104 C 184 122 168 134 146 134 L 122 134 L 128 106 L 146 106 C 154 106 158 102 160 94 Z"
    i_p = "M 222 32 L 262 32 L 242 128 L 202 128 Z"
    return _svg(280, 160, f'  <path d="{d_p}" fill="{{{{INK}}}}"/>\n  <path d="{j_p}" fill="{{{{INK}}}}"/>\n  <path d="{i_p}" fill="{{{{INK}}}}"/>')


def gen_insta360(era: str) -> str:
    if era == "2015":
        swirl = (
            '<circle cx="64" cy="80" r="46" fill="none" stroke="#0072CE" stroke-width="10"/>'
            '<circle cx="64" cy="80" r="22" fill="#0072CE"/>'
            '<circle cx="72" cy="72" r="7" fill="{{BADGE_FG}}"/>'
        )
        word, _ = _word_elements("Insta360", 128, 42, scale=0.72, fill="{{INK}}", sw=15.0, w_scale=0.95, tracking=6)
        return _svg(520, 160, f"  {swirl}\n  {word}")
    # 2020+ Think Bold Yellow Pill + crisp Insta360
    badge = '<rect x="14" y="42" width="16" height="76" rx="8" fill="#FFDE00"/>'
    word, _ = _word_elements("Insta360", 44, 42, scale=0.76, fill="{{INK}}", sw=13.0, w_scale=0.95, tracking=6)
    return _svg(460, 160, f"  {badge}\n  {word}")


def gen_zeiss_1991() -> str:
    # Emil Donitz Tessar Frame + bold ZEISS serif
    frame = _poly([(16, 18), (156, 18), (156, 86), (118, 140), (54, 140), (16, 86)])
    word, _ = _word_elements("ZEISS", 32, 48, scale=0.34, fill="{{BADGE_FG}}", sw=16.0, w_scale=0.96, tracking=8, serif=True)
    return _svg(172, 160, f'  <path d="{frame}" fill="#0F2DB3"/>\n  {word}')


def gen_red_2005() -> str:
    word, _ = _word_elements("RED", 28, 34, scale=0.92, fill="{{BADGE_FG}}", sw=19.0, w_scale=1.04, tracking=14)
    return _svg(270, 160, f'  <rect x="10" y="16" width="250" height="128" rx="10" fill="#DC2026"/>\n  {word}')


def gen_arri_2010() -> str:
    mark = _poly([(16, 128), (64, 32), (112, 128), (92, 128), (64, 68), (36, 128)])
    word, _ = _word_elements("ARRI", 126, 36, scale=0.86, fill="#005BA6", sw=16.0, w_scale=1.02, tracking=12)
    return _svg(390, 160, f'  <path d="{mark}" fill="#005BA6"/>\n  {word}')


def gen_blackmagic_2001() -> str:
    dots = (
        '<circle cx="38" cy="54" r="14" fill="#FFA200"/>'
        '<circle cx="72" cy="54" r="14" fill="#E31837"/>'
        '<circle cx="55" cy="84" r="14" fill="#0095DA"/>'
    )
    word, _ = _word_elements("Blackmagic", 104, 48, scale=0.64, fill="{{INK}}", sw=13.5, w_scale=0.94, tracking=6)
    return _svg(520, 160, f"  {dots}\n  {word}")


def gen_nothing_2020() -> str:
    # 5x7 Dot-Matrix NDot aesthetic for NOTHING
    font_5x7 = {
        "N": ["10001", "11001", "10101", "10011", "10001"],
        "O": ["01110", "10001", "10001", "10001", "01110"],
        "T": ["11111", "00100", "00100", "00100", "00100"],
        "H": ["10001", "10001", "11111", "10001", "10001"],
        "I": ["111", "010", "010", "010", "111"],
        "G": ["01110", "10000", "10111", "10001", "01110"],
    }
    circles = []
    cx = 20.0
    for ch in "NOTHING":
        rows = font_5x7[ch]
        for r_idx, row in enumerate(rows):
            for c_idx, bit in enumerate(row):
                if bit == "1":
                    circles.append(f'<circle cx="{_r(cx + c_idx * 14)}" cy="{_r(44 + r_idx * 16)}" r="5.5" fill="{{{{INK}}}}"/>')
        cx += len(rows[0]) * 14 + 22
    circles.append(f'<circle cx="{_r(cx + 6)}" cy="108" r="6" fill="#D71921"/>')
    return _svg(int(cx + 28), 160, "  " + "\n  ".join(circles))


def gen_garmin_2006() -> str:
    word, adv = _word_elements("GARMIN", 20, 36, scale=0.84, fill="{{INK}}", sw=15.0, w_scale=1.02, tracking=12)
    tri = _poly([(28 + adv, 118), (62 + adv, 42), (96 + adv, 118)])
    return _svg(int(114 + adv), 160, f'  {word}\n  <path d="{tri}" fill="#007CC3"/>')


def gen_autel_2014() -> str:
    a_mark = _poly([(16, 128), (62, 30), (108, 128), (86, 128), (62, 74), (38, 128)])
    word, _ = _word_elements("AUTEL", 122, 38, scale=0.84, fill="{{INK}}", sw=15.5, w_scale=1.0, tracking=12)
    return _svg(440, 160, f'  <path d="{a_mark}" fill="#FF7F00"/>\n  {word}')


def gen_blackberry_2004() -> str:
    dots = [(30, 52), (56, 52), (24, 78), (50, 78), (76, 78), (30, 104), (56, 104)]
    berry = "\n  ".join(f'<rect x="{x}" y="{y}" width="18" height="18" rx="6" fill="#1475DC"/>' for x, y in dots)
    word, _ = _word_elements("BlackBerry", 110, 48, scale=0.64, fill="{{INK}}", sw=13.5, w_scale=0.94, tracking=6)
    return _svg(540, 160, f"  {berry}\n  {word}")


def gen_asus_1995() -> str:
    word, adv = _word_elements("ASUS", 20, 32, scale=0.92, fill="#00539B", sw=17.0, w_scale=1.06, tracking=14)
    # Iconic horizontal slice line cutting through middle of ASUS
    slice_bar = f'<rect x="14" y="75" width="{_r(adv + 16)}" height="5" fill="{{{{CONTRAST}}}}"/>'
    return _svg(int(adv + 44), 160, f"  {word}\n  {slice_bar}")


def gen_kyocera_1982() -> str:
    kc = (
        '<path d="M 16 32 L 34 32 L 34 74 L 74 32 L 96 32 L 54 78 L 98 128 L 74 128 L 34 82 L 34 128 L 16 128 Z" fill="#E31A2F"/>'
        '<circle cx="94" cy="80" r="24" fill="none" stroke="#E31A2F" stroke-width="11"/>'
    )
    word, _ = _word_elements("KYOCERA", 136, 40, scale=0.76, fill="{{INK}}", sw=15.0, w_scale=0.98, tracking=10)
    return _svg(540, 160, f"  {kc}\n  {word}")


def gen_ricoh_theta_2013() -> str:
    w1, a1 = _word_elements("RICOH", 20, 42, scale=0.70, fill="#D61B3E", sw=17.0, w_scale=1.02, tracking=12, rounded=True)
    w2, a2 = _word_elements("THETA", 36 + a1, 42, scale=0.70, fill="{{INK}}", sw=11.0, w_scale=1.02, tracking=14)
    return _svg(int(56 + a1 + a2), 160, f"  {w1}\n  {w2}")


def gen_simple_wordmark(
    text: str,
    fill: str,
    sw: float = 15.0,
    w_scale: float = 1.0,
    tracking: float = 10.0,
    scale: float = 0.88,
    rounded: bool = False,
    serif: bool = False,
    italic_deg: float = 0.0,
    underline: str | None = None,
) -> str:
    word, adv = _word_elements(
        text, 22, 34, scale=scale, fill=fill, sw=sw, w_scale=w_scale,
        tracking=tracking, rounded=rounded, serif=serif, italic_deg=italic_deg
    )
    extra = f'\n  <rect x="22" y="132" width="{_r(adv)}" height="9" rx="4" fill="{underline}"/>' if underline else ""
    return _svg(int(max(200, adv + 44)), 160, f"  {word}{extra}")


GENERATORS: dict[str, Callable[[], str]] = {
    "canon/1935.svg": gen_canon_1935,
    "canon/1956.svg": gen_canon_1956,
    "nikon/1968.svg": gen_nikon_1968,
    "nikon/1988.svg": gen_nikon_1988,
    "nikon/2003.svg": gen_nikon_2003,
    "sony/1973.svg": gen_sony_1973,
    "sony-alpha/2006.svg": gen_sony_alpha_2006,
    "minolta/1981.svg": gen_minolta_1981,
    "konica-minolta/2003.svg": gen_konica_minolta_2003,
    "fujifilm/1980.svg": gen_fujifilm_1980,
    "fujifilm/2006.svg": gen_fujifilm_2006,
    "olympus/1970.svg": gen_olympus_1970,
    "olympus/2001.svg": gen_olympus_2001,
    "om-system/2021.svg": gen_om_system_2021,
    "panasonic/1971.svg": gen_panasonic_1971,
    "lumix/2001.svg": gen_lumix_2001,
    "pentax/1957.svg": gen_pentax_1957,
    "pentax/1987.svg": gen_pentax_1987,
    "ricoh/1986.svg": gen_ricoh_1986,
    "ricoh/2005.svg": gen_ricoh_2005,
    "ricoh-theta/2013.svg": gen_ricoh_theta_2013,
    "leica/1976.svg": lambda: gen_leica_dot("Leitz"),
    "leica/1986.svg": lambda: gen_leica_dot("Leica"),
    "sigma/1961.svg": gen_sigma_1961,
    "sigma/2012.svg": gen_sigma_2012,
    "sigma/2025.svg": gen_sigma_2025,
    "hasselblad/1990.svg": gen_hasselblad_1990,
    "hasselblad/2015.svg": gen_hasselblad_2015,
    "kodak/1987.svg": gen_kodak_1987,
    "kodak/2006.svg": gen_kodak_2006,
    "kodak/2016.svg": gen_kodak_2016,
    "samsung/1993.svg": gen_samsung_1993,
    "samsung/2015.svg": gen_samsung_2015,
    "polaroid/1977.svg": lambda: gen_polaroid("1977"),
    "polaroid/2017.svg": lambda: gen_polaroid("2017"),
    "polaroid/2020.svg": lambda: gen_polaroid("2020"),
    "phase-one/1993.svg": lambda: gen_simple_wordmark("PHASE ONE", "{{INK}}", sw=11.0, tracking=18, scale=0.72),
    "mamiya/1940.svg": lambda: gen_simple_wordmark("Mamiya", "#FC001B", sw=16.5, tracking=8, scale=0.86, rounded=True),
    "contax/1974.svg": lambda: gen_simple_wordmark("CONTAX", "{{INK}}", sw=10.5, tracking=28, scale=0.80),
    "casio/1972.svg": lambda: gen_simple_wordmark("CASIO", "#0055CC", sw=17.5, w_scale=1.08, tracking=12, scale=0.88),
    "epson/1994.svg": lambda: gen_simple_wordmark("EPSON", "#003399", sw=17.5, w_scale=1.04, tracking=10, scale=0.90),
    "kyocera/1982.svg": gen_kyocera_1982,
    "yashica/1983.svg": lambda: gen_simple_wordmark("YASHICA", "{{INK}}", sw=15.0, tracking=12, scale=0.82),
    "rollei/1962.svg": lambda: gen_simple_wordmark("Rollei", "{{INK}}", sw=16.0, tracking=8, scale=0.88, rounded=True),
    "zeiss/1991.svg": gen_zeiss_1991,
    "pixii/2017.svg": lambda: gen_simple_wordmark("PIXII", "{{INK}}", sw=9.5, tracking=34, scale=0.82),
    "red/2005.svg": gen_red_2005,
    "arri/2010.svg": gen_arri_2010,
    "blackmagic/2001.svg": gen_blackmagic_2001,
    "apple/1977.svg": lambda: gen_apple("1977"),
    "apple/2007.svg": lambda: gen_apple("2007"),
    "apple/2013.svg": lambda: gen_apple("2013"),
    "google/2010.svg": lambda: gen_google("2010"),
    "google/2015.svg": lambda: gen_google("2015"),
    "xiaomi/2014.svg": lambda: gen_xiaomi("2014"),
    "xiaomi/2021.svg": lambda: gen_xiaomi("2021"),
    "huawei/2006.svg": lambda: gen_huawei("2006"),
    "huawei/2018.svg": lambda: gen_huawei("2018"),
    "oppo/2013.svg": lambda: gen_simple_wordmark("oppo", "#1EA366", sw=15.0, w_scale=1.14, tracking=10, scale=0.92, rounded=True),
    "oppo/2019.svg": lambda: gen_simple_wordmark("oppo", "#2D683D", sw=12.5, w_scale=1.0, tracking=12, scale=0.92),
    "vivo/2009.svg": lambda: gen_simple_wordmark("vivo", "#0072B8", sw=15.0, tracking=10, scale=0.92, rounded=True),
    "vivo/2019.svg": lambda: gen_simple_wordmark("vivo", "#415FFF", sw=13.5, w_scale=0.92, tracking=10, scale=0.94),
    "oneplus/2013.svg": lambda: gen_simple_wordmark("1+ ONEPLUS", "#EB0029", sw=15.5, w_scale=0.84, tracking=8, scale=0.78),
    "oneplus/2020.svg": lambda: gen_simple_wordmark("1+ ONEPLUS", "#F50514", sw=14.5, w_scale=1.02, tracking=12, scale=0.76, rounded=True),
    "lg/1995.svg": lambda: gen_lg("1995"),
    "lg/2014.svg": lambda: gen_lg("2014"),
    "lg/2023.svg": lambda: gen_lg("2023"),
    "goldstar/1983.svg": gen_goldstar,
    "sony-ericsson/2001.svg": gen_sony_ericsson,
    "motorola/1955.svg": lambda: gen_motorola("1955"),
    "motorola/2013.svg": lambda: gen_motorola("2013"),
    "nokia/1992.svg": lambda: gen_nokia("1992"),
    "nokia/2023.svg": lambda: gen_nokia("2023"),
    "honor/2013.svg": lambda: gen_simple_wordmark("honor", "#00AEEF", sw=15.0, tracking=10, scale=0.90, rounded=True),
    "honor/2018.svg": lambda: gen_simple_wordmark("HONOR", "{{INK}}", sw=15.0, tracking=14, scale=0.86),
    "realme/2018.svg": lambda: gen_simple_wordmark("realme", "{{INK}}", sw=15.0, tracking=8, scale=0.84, rounded=True, underline="#FFC916"),
    "nothing/2020.svg": gen_nothing_2020,
    "asus/1995.svg": gen_asus_1995,
    "htc/2008.svg": lambda: gen_simple_wordmark("htc", "#339933", sw=15.5, tracking=10, scale=0.94, rounded=True),
    "sharp/1960.svg": lambda: gen_simple_wordmark("SHARP", "#E6000D", sw=18.0, w_scale=1.06, tracking=10, scale=0.90),
    "blackberry/2004.svg": gen_blackberry_2004,
    "pantech/2005.svg": lambda: gen_simple_wordmark("PANTECH", "#005BAC", sw=16.5, tracking=10, scale=0.80),
    "gopro/2004.svg": lambda: gen_gopro("2004"),
    "gopro/2012.svg": lambda: gen_gopro("2012"),
    "dji/2006.svg": lambda: gen_dji("2006"),
    "dji/2012.svg": lambda: gen_dji("2012"),
    "insta360/2015.svg": lambda: gen_insta360("2015"),
    "insta360/2020.svg": lambda: gen_insta360("2020"),
    "garmin/2006.svg": gen_garmin_2006,
    "autel/2014.svg": gen_autel_2014,
    "parrot/1994.svg": lambda: gen_simple_wordmark("Parrot", "{{INK}}", sw=14.0, tracking=8, scale=0.86, rounded=True),
    "sjcam/2010.svg": lambda: gen_simple_wordmark("SJCAM", "#E30613", sw=18.0, tracking=10, scale=0.88, italic_deg=14.0),
    "akaso/2013.svg": lambda: gen_simple_wordmark("AKASO", "{{INK}}", sw=16.0, tracking=12, scale=0.88, underline="#FF5500"),
}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for rel, fn in GENERATORS.items():
        path = OUT_DIR / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        svg = fn()
        assert "<text" not in svg.lower(), f"SVG must not contain <text>: {rel}"
        path.write_text(svg, encoding="utf-8")
    print(f"Generated {len(GENERATORS)} pure-vector SVG logos in {OUT_DIR}")


if __name__ == "__main__":
    main()
