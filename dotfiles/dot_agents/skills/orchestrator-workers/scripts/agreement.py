#!/usr/bin/env python3
"""How far the findings record (findings.py) agrees with a hand-made findings CSV on the rulings of blocking findings.

Usage:
    python3 agreement.py CSV RUN [RUN ...] [--bar 0.9]

Only blocking rows (block_reviewer yes) whose ruling the CSV took from inside the run folder are compared (owner,
2026-11-02, 4a): ruling_source rulings.jsonl, fix-brief, fix-report or rereview. Rows ruled from PLAN.md, another
run's discuss.md, the prior CSV or nothing are counted apart, by source. A row agrees when the record holds the same
(round, n) with the same ruling (not-reproduced counts as rejected). Reads the run folders only; writes nothing.
Prints one line per run folder with its agreement against the bar.
"""
import argparse, collections, csv, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import findings

IN_RUN = ('rulings.jsonl', 'fix-brief', 'fix-report', 'rereview')
SAME = {'not-reproduced': 'rejected', 'not-ruled': None, 'unknown': None, '': None}


def compare(rows, run_dirs):
    """{run: {'compared', 'agree', 'apart': Counter, 'missing': [...], 'differ': [...]}} for each run folder named."""
    by_run = {os.path.basename(os.path.abspath(d).rstrip(os.sep)): d for d in run_dirs}
    out = {}
    for run, d in by_run.items():
        rec = {(r['properties']['round'], str(r['properties']['n'])): r['properties']['ruling']
               for r in findings.record(d)[0]}
        s = out[run] = {'compared': 0, 'agree': 0, 'apart': collections.Counter(), 'missing': [], 'differ': []}
        for row in rows:
            if row['run'] != run or row.get('block_reviewer') != 'yes':
                continue
            if row.get('ruling_source') not in IN_RUN:
                s['apart'][row.get('ruling_source') or 'none'] += 1
                continue
            s['compared'] += 1
            key = (row['round'], row['n'])
            if key not in rec and (row['round'], 'c' + row['n']) in rec and row.get('round_kind') == 'rereview':
                # The CSV numbers a re-review's carried findings as the reviewer did; the record labels them cN.
                key = (row['round'], 'c' + row['n'])
            want = SAME.get(row['ruling'], row['ruling'])
            if key not in rec:
                s['missing'].append(key)
            elif rec[key] == want:
                s['agree'] += 1
            else:
                s['differ'].append((key, want, rec[key]))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('csv')
    ap.add_argument('runs', nargs='+', metavar='RUN')
    ap.add_argument('--bar', type=float, default=0.9)
    ap.add_argument('-v', '--verbose', action='store_true', help='list each missing or differing row')
    a = ap.parse_args(argv)
    with open(a.csv, encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f))
    for run, s in compare(rows, a.runs).items():
        share = s['agree'] / s['compared'] if s['compared'] else None
        verdict = 'no in-run rulings' if share is None else ('meets' if share >= a.bar else 'below') + f' {a.bar:.0%}'
        apart = ', '.join(f'{k} {v}' for k, v in sorted(s['apart'].items())) or 'none'
        print(f"{run}: {s['agree']}/{s['compared']} agree" + (f' ({share:.1%})' if share is not None else '')
              + f", {len(s['missing'])} not in the record, {len(s['differ'])} ruled differently; {verdict}; "
              f"apart: {apart}")
        if a.verbose:
            for key in s['missing']:
                print(f'  missing {key[0]} {key[1]}')
            for key, want, got in s['differ']:
                print(f'  differs {key[0]} {key[1]}: csv {want}, record {got}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
