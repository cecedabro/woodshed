"""Draw the Woodshed app icons (SPEC 10.3, docs/frontend.md §pwa). Stdlib only.

The icon is a shed whose front is a guitar: an amber gable (the "amp" theme's pilot-light
gradient) with a dark soundhole, six strings, a nut and a bridge, on the dark bar colour.
Everything sits inside the central 80 % circle, so the 192/512 icons also work as maskable
icons (Android crops them to a circle or squircle) and iOS can round the corners itself.

Run from backend/:  uv run python scripts/make_icons.py
Writes app/static/icons/icon-192.png, icon-512.png and apple-touch-icon.png (180 px).
"""

from __future__ import annotations

import math
import struct
import sys
import zlib
from collections.abc import Callable
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "app" / "static" / "icons"
SIZES = {"icon-192.png": 192, "icon-512.png": 512, "apple-touch-icon.png": 180}

RGB = tuple[float, float, float]


def hex_rgb(value: str) -> RGB:
    value = value.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


# Colours from static/css/tokens.css (theme "amp").
BG_TOP = hex_rgb("#241e18")  # --c-bar
BG_BOTTOM = hex_rgb("#16120f")  # --c-field
ACCENT_HI = hex_rgb("#f2b955")  # --c-accent-hi
ACCENT = hex_rgb("#e8a33a")  # --c-accent
ACCENT_LO = hex_rgb("#cf8a24")  # --c-accent-lo
ACCENT_EDGE = hex_rgb("#b97a1f")  # --c-accent-edge
HOLE = hex_rgb("#1b1714")  # --c-bg
STRING = hex_rgb("#f2e8d5")  # --c-text

# The shed / guitar body: a convex pentagon in unit coordinates (y down).
BODY = [(0.50, 0.19), (0.77, 0.42), (0.77, 0.78), (0.23, 0.78), (0.23, 0.42)]
HOLE_CENTRE, HOLE_R, RING_W = (0.50, 0.565), 0.105, 0.016
# Strings fan out from the nut to the bridge, like on a real guitar.
STRINGS = [(0.50 + (i - 2.5) * 0.024, 0.50 + (i - 2.5) * 0.034) for i in range(6)]
STRING_TOP, STRING_BOTTOM = 0.362, 0.714


def mix(a: RGB, b: RGB, t: float) -> RGB:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def polygon_sd(x: float, y: float, pts: list[tuple[float, float]]) -> float:
    """Signed distance to a convex polygon (negative inside); exact enough for anti-aliasing."""
    d = -math.inf
    n = len(pts)
    for i in range(n):
        (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % n]
        ex, ey = x2 - x1, y2 - y1
        length = math.hypot(ex, ey)
        # Outward normal for clockwise points in a y-down system.
        nx, ny = ey / length, -ex / length
        d = max(d, (x - x1) * nx + (y - y1) * ny)
    return d


def box_sd(x: float, y: float, x0: float, y0: float, x1: float, y1: float) -> float:
    dx = max(x0 - x, 0.0, x - x1)
    dy = max(y0 - y, 0.0, y - y1)
    outside = math.hypot(dx, dy)
    inside = min(max(x0 - x, x - x1, y0 - y, y - y1), 0.0)
    return outside + inside


def segment_sd(x: float, y: float, a: tuple[float, float], b: tuple[float, float]) -> float:
    """Distance to the line segment a-b."""
    abx, aby = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((x - a[0]) * abx + (y - a[1]) * aby) / (abx * abx + aby * aby)))
    return math.hypot(x - a[0] - t * abx, y - a[1] - t * aby)


def coverage(sd: float, px: float) -> float:
    """Signed distance (unit coords) → pixel coverage, with a one-pixel soft edge."""
    return min(1.0, max(0.0, 0.5 - sd / px))


def shade(x: float, y: float, px: float) -> RGB:
    colour = mix(BG_TOP, BG_BOTTOM, y)

    def paint(sd: float, col: RGB | Callable[[], RGB], alpha: float = 1.0) -> None:
        nonlocal colour
        a = coverage(sd, px) * alpha
        if a > 0:
            colour = mix(colour, col() if callable(col) else col, a)

    # Soft amber glow behind the body.
    glow = max(0.0, 1.0 - math.hypot(x - 0.5, y - 0.52) / 0.48)
    colour = mix(colour, ACCENT, 0.10 * glow * glow)

    body = polygon_sd(x, y, BODY)

    def body_fill() -> RGB:
        t = (y - 0.19) / (0.78 - 0.19)
        return (
            mix(ACCENT_HI, ACCENT, t / 0.55)
            if t < 0.55
            else mix(ACCENT, ACCENT_LO, (t - 0.55) / 0.45)
        )

    paint(body, body_fill)
    paint(abs(body) - 0.006, ACCENT_EDGE, 0.9)  # edge line, like the accent buttons

    hole = math.hypot(x - HOLE_CENTRE[0], y - HOLE_CENTRE[1]) - HOLE_R
    paint(abs(hole - RING_W) - RING_W / 3, ACCENT_EDGE)  # rosette
    paint(hole, HOLE)

    paint(box_sd(x, y, 0.418, 0.348, 0.582, 0.366) - 0.004, HOLE, 0.9)  # nut
    paint(box_sd(x, y, 0.395, 0.704, 0.605, 0.724) - 0.004, HOLE, 0.9)  # bridge
    half = max(0.0028, 0.55 * px)  # strings stay at least ~1 px wide
    for top_x, bottom_x in STRINGS:
        sd = segment_sd(x, y, (top_x, STRING_TOP), (bottom_x, STRING_BOTTOM)) - half
        paint(sd, STRING, 0.95)
    return colour


def render(size: int) -> bytes:
    px = 1.0 / size
    rows = bytearray()
    for j in range(size):
        rows.append(0)  # filter: none
        y = (j + 0.5) * px
        for i in range(size):
            r, g, b = shade((i + 0.5) * px, y, px)
            rows += bytes((round(r), round(g), round(b)))
    return png(size, size, bytes(rows))


def png(width: int, height: int, raw: bytes) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, size in SIZES.items():
        (OUT / name).write_bytes(render(size))
        print(f"wrote {OUT / name} ({size}x{size})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
