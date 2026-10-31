#!/usr/bin/env python3
"""Draw a stratified blind grading sheet from a findings CSV.

Usage:
    python3 sample.py FINDINGS.csv --n 40 --strata COLUMN --seed N [--out DIR] [--grades COL,...] [--text COL]

Writes DIR/sheet.csv (a sheet id S1, S2 ... in shuffled order and the finding's text, nothing else) and
DIR/key.csv (sheet id, source id, stratum, a cue flag and the removed grades). Each stratum gets its share
of n by largest remainder, so it stays within one row of its share in the input. The source id is the
CSV's id column, else the row's 1-based data line number. Text that names a grade or a prior ruling is
flagged in the key and on stderr for the orchestrator to edit before grading. The same input, n and seed
give the same sheet.
"""
import argparse, collections, csv, os, random, re, sys

GRADES = ('severity_today', 'severity_rubric', 'likelihood', 'impact', 'accepted', 'fixed_later', 'blocking_today',
          'security_severity', 'label', 'grade', 'severity')
TEXTS = ('paraphrase', 'finding', 'text')
CUE = re.compile(r'\b(blockers?|major|minor|nits?|severity|repeat of|rejected|accepted|demoted|promoted|'
                 r'not[- ]reproduced|ruled|ruling)\b', re.I)


def allocate(counts, n):
    """Rows per stratum: floor of each exact share, then the remainder to the largest fractions."""
    total = sum(counts.values())
    n = min(n, total)
    exact = {k: n * c / total for k, c in counts.items()}
    alloc = {k: int(v) for k, v in exact.items()}
    for k in sorted(exact, key=lambda k: (alloc[k] - exact[k], k))[:n - sum(alloc.values())]:
        alloc[k] += 1
    return alloc


def sample(rows, n, strata, seed):
    rng = random.Random(seed)
    groups = collections.OrderedDict()
    for row in rows:
        groups.setdefault(row[strata], []).append(row)
    alloc = allocate({k: len(v) for k, v in groups.items()}, n)
    picked = []
    for k in sorted(groups):
        picked += rng.sample(groups[k], alloc[k])
    rng.shuffle(picked)
    return picked, alloc


def main(argv=None):
    ap = argparse.ArgumentParser(description='Draw a stratified blind grading sheet and its key from a findings CSV.')
    ap.add_argument('findings', help='findings CSV')
    ap.add_argument('--n', type=int, default=40, help='rows to sample (default 40)')
    ap.add_argument('--strata', required=True, help='column whose values keep their share')
    ap.add_argument('--seed', type=int, required=True, help='random seed')
    ap.add_argument('--out', default='.', help='folder for sheet.csv and key.csv (default: here)')
    ap.add_argument('--grades', help='comma-separated grade columns to remove (default: the known ones present)')
    ap.add_argument('--text', help=f'text column (default: the first of {", ".join(TEXTS)} present)')
    a = ap.parse_args(argv)
    if a.n < 1:
        print('sample.py: --n must be 1 or more', file=sys.stderr)
        return 2
    with open(a.findings, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []
        rows = list(reader)
    text = a.text or next((c for c in TEXTS if c in cols), None)
    grades = [c.strip() for c in a.grades.split(',')] if a.grades else [c for c in GRADES if c in cols]
    missing = [c for c in [a.strata, text] + grades if c not in cols]
    if missing or not rows:
        print(f'sample.py: {a.findings}: ' + (f'no column {missing}' if missing else 'no rows'), file=sys.stderr)
        return 2
    has_id = 'id' in cols
    for i, row in enumerate(rows, 1):
        row['_id'] = row['id'] if has_id else str(i)
    if a.n > len(rows):
        print(f'sample.py: --n {a.n} is more than the {len(rows)} rows; taking them all', file=sys.stderr)
    picked, alloc = sample(rows, a.n, a.strata, a.seed)
    os.makedirs(a.out, exist_ok=True)
    width = len(str(len(picked)))
    for i, row in enumerate(picked, 1):
        row['_sheet'] = f'S{i:0{width}d}'
    with open(os.path.join(a.out, 'sheet.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['id', 'text'])
        for row in picked:
            w.writerow([row['_sheet'], row[text]])
    flagged = [row['_sheet'] for row in picked if CUE.search(row[text])]
    with open(os.path.join(a.out, 'key.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['id', 'source_id', a.strata, 'cue'] + grades)
        for row in picked:
            w.writerow([row['_sheet'], row['_id'], row[a.strata], 'yes' if row['_sheet'] in flagged else '']
                       + [row[c] for c in grades])
    if flagged:
        print(f'sample.py: text names a grade or a prior ruling, edit before grading: {", ".join(flagged)}',
              file=sys.stderr)
    total = len(rows)
    for k in sorted(alloc):
        n = sum(r[a.strata] == k for r in rows)
        print(f'{k or "(blank)"}: {alloc[k]} of {n} (exact share {len(picked) * n / total:.2f})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
