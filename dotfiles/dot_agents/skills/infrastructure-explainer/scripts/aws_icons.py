"""Find and extract icons from the official AWS Architecture Icons package (the zip from aws.amazon.com/architecture/icons).

    python3 aws_icons.py --zip Asset-Package.zip --find bucket          # list icon files whose name contains every word
    python3 aws_icons.py --zip Asset-Package.zip --out icons/ NAME...   # copy those files (exact file names) into icons/
"""
import argparse
import sys
import zipfile
from pathlib import Path


def entries(zf):
    for name in zf.namelist():
        base = name.rsplit("/", 1)[-1]
        if name.startswith("__MACOSX") or base.startswith("._") or not base.endswith(".svg"):
            continue
        yield name, base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, type=Path)
    ap.add_argument("--find", nargs="+", metavar="WORD")
    ap.add_argument("--size", default="48", help="icon size suffix to keep when finding (16, 32, 48, 64)")
    ap.add_argument("--out", type=Path)
    ap.add_argument("names", nargs="*", help="exact icon file names to extract")
    a = ap.parse_args()
    with zipfile.ZipFile(a.zip) as zf:
        found = dict((base, name) for name, base in entries(zf))
        if a.find:
            words = [w.lower() for w in a.find]
            hits = sorted(b for b in found if all(w in b.lower() for w in words) and b.endswith(f"_{a.size}.svg"))
            print("\n".join(hits) if hits else f"no icon name contains: {' '.join(a.find)}", file=sys.stdout if hits else sys.stderr)
            return 0 if hits else 1
        if not a.out or not a.names:
            ap.error("give --find WORDS, or --out DIR and icon file names")
        missing = [n for n in a.names if n not in found]
        if missing:
            print("not in the package: " + ", ".join(missing), file=sys.stderr)
            return 1
        a.out.mkdir(parents=True, exist_ok=True)
        for n in a.names:
            (a.out / n).write_bytes(zf.read(found[n]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
