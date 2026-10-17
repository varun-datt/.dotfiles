#!/usr/bin/env python3
"""Crop screenshots into the stills a film shows, and cut sprites out of a flat background.

Usage:
    uv run --with pillow python crop_stills.py CROPS_JSON --src DIR --out DIR [--max-width 2000]

CROPS_JSON maps an output name to its source and either a crop box or a cut-out:
    {"story": {"file": "01-story.png", "box": [0.0, 0.0, 0.52, 0.23]},
     "mascot": {"file": "14-mascot.png", "cutout": true}}
A box is [left, top, right, bottom] as fractions of the source image, so a retina and a standard capture crop
alike. A cut-out clears only the background connected to the image's edges, so dark details inside survive.
Writes OUT/<name>.png for every entry and removes other PNGs from OUT. Idempotent.
"""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image

TOLERANCE = 48


def cutout(path):
    img = Image.open(path).convert('RGBA')
    px, (w, h) = img.load(), img.size
    bg = px[0, 0]
    todo = [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]
    seen = set()
    while todo:
        x, y = todo.pop()
        if (x, y) in seen or not (0 <= x < w and 0 <= y < h):
            continue
        if sum(abs(px[x, y][i] - bg[i]) for i in range(3)) >= TOLERANCE:
            continue
        seen.add((x, y))
        px[x, y] = (0, 0, 0, 0)
        todo += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    return img, len(seen)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('crops', type=Path)
    parser.add_argument('--src', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--max-width', type=int, default=2000)
    args = parser.parse_args()

    crops = json.loads(args.crops.read_text())
    missing = sorted({c['file'] for c in crops.values() if not (args.src / c['file']).exists()})
    if missing:
        sys.exit(f'missing screenshots in {args.src}: {missing}')
    args.out.mkdir(parents=True, exist_ok=True)
    for stale in args.out.glob('*.png'):
        if stale.stem not in crops:
            stale.unlink()
    for name, spec in crops.items():
        source = args.src / spec['file']
        if spec.get('cutout'):
            img, cleared = cutout(source)
            img.save(args.out / f'{name}.png', optimize=True)
            print(f'{name:14} {img.width}x{img.height}  background cleared: {cleared} px')
            continue
        img = Image.open(source).convert('RGB')
        w, h = img.size
        left, top, right, bottom = spec['box']
        crop = img.crop((round(left * w), round(top * h), round(right * w), round(bottom * h)))
        if crop.width > args.max_width:
            crop = crop.resize((args.max_width, round(crop.height * args.max_width / crop.width)), Image.LANCZOS)
        crop.save(args.out / f'{name}.png', optimize=True)
        print(f'{name:14} {crop.width}x{crop.height}  from {spec["file"]}')


if __name__ == '__main__':
    main()
