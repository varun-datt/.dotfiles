"""Check files before a merge: redaction patterns matched on word boundaries, and literal \\u escapes.

Usage: python3 -B merge_check.py [--patterns <file>] <file> [<file> ...]
The patterns file is a JSON list of patterns or [pattern, replacement] pairs; it defaults to
$OW_REDACTION_PATTERNS. Prints counts per file and pattern index, never the pattern text.
Exit 0 only when every file is clean.
"""
import argparse
import json
import os
import pathlib
import re
import sys

ESCAPE = re.compile(r'\\u[0-9a-f]{4}')


def load_patterns(path):
    items = json.loads(pathlib.Path(path).expanduser().read_text())
    return [item[0] if isinstance(item, list) else item for item in items]


def findings(text, patterns):
    hits = []
    for index, pattern in enumerate(patterns):
        count = len(re.findall(rf'\b(?:{pattern})\b', text))
        if count:
            hits.append(f'pattern#{index}={count}')
    escapes = len(ESCAPE.findall(text))
    if escapes:
        hits.append(f'escapes={escapes}')
    return hits


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--patterns', default=os.environ.get('OW_REDACTION_PATTERNS'))
    parser.add_argument('files', nargs='+')
    args = parser.parse_args(argv)
    if not args.patterns:
        parser.error('name the patterns file with --patterns or OW_REDACTION_PATTERNS')
    patterns = load_patterns(args.patterns)
    dirty = 0
    for name in args.files:
        hits = findings(pathlib.Path(name).read_text(errors='replace'), patterns)
        dirty += bool(hits)
        print(f"{name}: {'CLEAN' if not hits else ' '.join(hits)}")
    return 1 if dirty else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
