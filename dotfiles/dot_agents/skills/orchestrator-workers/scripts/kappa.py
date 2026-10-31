#!/usr/bin/env python3
"""Agreement between two graded sheets: percent agreement and Cohen's kappa on one column.

Usage:
    python3 kappa.py SHEET_A.csv SHEET_B.csv --column NAME [--id id]

Compares the rows both sheets grade (same id, a non-empty value in both). kappa = (po - pe) / (1 - pe),
po the observed agreement, pe the chance agreement from each sheet's own class shares (Cohen 1960);
when pe is 1 (both sheets put every row in one class) kappa is undefined and is printed as such.
Rows present in only one sheet are named.
"""
import argparse, collections, csv, sys


def read(path, column, key):
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if column not in (reader.fieldnames or []) or key not in (reader.fieldnames or []):
            raise ValueError(f'{path}: needs columns {key!r} and {column!r}')
        out = {}
        for row in reader:
            i = (row[key] or '').strip()
            if not i:
                raise ValueError(f'{path}: line {reader.line_num} has an empty {key!r}')
            if i in out:
                raise ValueError(f'{path}: {key} {i!r} appears more than once')
            out[i] = (row[column] or '').strip()
        return out


def kappa(pairs):
    """(percent agreement, kappa or None when undefined) over (a, b) grade pairs."""
    n = len(pairs)
    if not n:
        return None, None
    po = sum(a == b for a, b in pairs) / n
    ca, cb = collections.Counter(a for a, _ in pairs), collections.Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in ca) / (n * n)
    return po, (None if pe == 1 else (po - pe) / (1 - pe))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Percent agreement and Cohen's kappa between two graded sheets.")
    ap.add_argument('a', help='first graded sheet (CSV)')
    ap.add_argument('b', help='second graded sheet (CSV)')
    ap.add_argument('--column', required=True, help='grade column to compare')
    ap.add_argument('--id', default='id', help='row id column (default: id)')
    x = ap.parse_args(argv)
    try:
        a, b = read(x.a, x.column, x.id), read(x.b, x.column, x.id)
    except (OSError, ValueError) as e:
        print(f'kappa.py: {e}', file=sys.stderr)
        return 2
    both = [k for k in a if k in b and a[k] and b[k]]
    po, k = kappa([(a[i], b[i]) for i in both])
    if po is None:
        print(f'no rows graded in both sheets on {x.column!r}')
    else:
        print(f'rows graded in both: {len(both)}')
        print(f'agreement: {po:.1%}')
        print('kappa: undefined (every row in one class in both sheets)' if k is None else f'kappa: {k:.3f}')
    for path, mine, other in ((x.a, a, b), (x.b, b, a)):
        only = [i for i in mine if i not in other]
        if only:
            print(f'only in {path}: {", ".join(only)}')
    ungraded = [i for i in a if i in b and not (a[i] and b[i])]
    if ungraded:
        print(f'ungraded in one sheet: {", ".join(ungraded)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
