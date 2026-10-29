"""Render an HTML page with headless Chrome and crop each card (section) into its own PNG.

    python3 render_cards.py page.html outdir/ [--width 1360] [--height 3000]

Writes outdir/full.png and outdir/card-1.png, card-2.png ... Cards are found as runs of the card colour
(white) in a column just inside the page's left edge, so it fits pages built with diagram_kit's CSS.
Make --height taller than the page: anything below the window is not captured.
"""
import argparse
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

CHROME = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "google-chrome", "chromium", "chromium-browser"]


def chrome():
    for c in CHROME:
        if Path(c).exists() or shutil.which(c):
            return c
    sys.exit("no Chrome or Chromium found")


def read_png(path):
    d = path.read_bytes()
    i, idat, w = 8, b"", 0
    while i < len(d):
        n = struct.unpack(">I", d[i:i + 4])[0]
        t, c = d[i + 4:i + 8], d[i + 8:i + 8 + n]
        if t == b"IHDR":
            w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", c)
            if depth != 8 or ctype not in (2, 6) or interlace:
                sys.exit("expected an 8-bit RGB or RGBA PNG without interlacing")
            bpp = 4 if ctype == 6 else 3
        elif t == b"IDAT":
            idat += c
        i += 12 + n
    raw, stride, rows, prev, p = zlib.decompress(idat), w * bpp, [], bytearray(w * bpp), 0
    for _ in range(h):
        f, line = raw[p], bytearray(raw[p + 1:p + 1 + stride])
        p += 1 + stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(bytes(line))
        prev = line
    return w, bpp, rows


def write_png(path, w, bpp, rows):
    def chunk(t, c):
        return struct.pack(">I", len(c)) + t + c + struct.pack(">I", zlib.crc32(t + c) & 0xFFFFFFFF)
    head = struct.pack(">IIBBBBB", w, len(rows), 8, 6 if bpp == 4 else 2, 0, 0, 0)
    body = zlib.compress(b"".join(b"\x00" + r for r in rows), 9)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", head) + chunk(b"IDAT", body) + chunk(b"IEND", b""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html", type=Path)
    ap.add_argument("outdir", type=Path)
    ap.add_argument("--width", type=int, default=1360)
    ap.add_argument("--height", type=int, default=3000)
    ap.add_argument("--margin", type=int, default=10, help="pixels kept around each card")
    a = ap.parse_args()
    a.outdir.mkdir(parents=True, exist_ok=True)
    full = a.outdir / "full.png"
    subprocess.run([chrome(), "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={a.width},{a.height}",
                    f"--screenshot={full.resolve()}", a.html.resolve().as_uri()],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    w, bpp, rows = read_png(full)
    x = max(0, (w - 1280) // 2) + 6
    cards, start = [], None
    for y, r in enumerate(rows + [b""]):
        white = r[x * bpp:x * bpp + 3] == b"\xff\xff\xff"
        if white and start is None:
            start = y
        elif not white and start is not None:
            if y - start > 20:
                cards.append((start, y - 1))
            start = None
    if not cards:
        sys.exit("no cards found; is the page built with diagram_kit's CSS?")
    if cards[-1][1] >= len(rows) - 2:
        print("warning: the last card reaches the bottom of the window; raise --height", file=sys.stderr)
    for n, (top, bottom) in enumerate(cards, 1):
        lo, hi = max(0, top - a.margin), min(len(rows), bottom + 1 + a.margin)
        write_png(a.outdir / f"card-{n}.png", w, bpp, rows[lo:hi])
    return 0


if __name__ == "__main__":
    sys.exit(main())
