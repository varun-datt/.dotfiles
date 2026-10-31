#!/usr/bin/env python3
"""Record the orchestrator's ruling on one review finding as a line of <run>/rulings.jsonl.

Usage:
    python3 rule.py add RUN ROUND N --grade G --ruled R --by WHO --reason TEXT [--area AREA]

ROUND is a round name with a <run>/<ROUND>.jsonl; N is the finding's number in that review (B1 is 1).
G is the reviewer's grade (Blocker, Major, Minor, Nit); R is the orchestrator's ruling: a grade, rejected
or not-reproduced. AREA is the rubric's area code (SEC, COR, DATA ...); `mine.py RUN --rulings` counts by it.
Refuses, writing nothing, a missing round, a round name with a path separator, an empty reason or by.
"""
import argparse, datetime, json, os, sys

GRADES = ('Blocker', 'Major', 'Minor', 'Nit')
RULINGS = GRADES + ('rejected', 'not-reproduced')


def fail(msg):
    print(f'rule.py: {msg}', file=sys.stderr)
    return 2


def round_name_ok(name):
    return bool(name) and name not in ('.', '..') and not any(s and s in name for s in ('/', os.sep, os.altsep))


def add(a):
    run = os.path.abspath(os.path.expanduser(a.run))
    if not os.path.isdir(run):
        return fail(f'no run folder at {run}')
    name = a.round
    if not round_name_ok(name):
        return fail(f'round {name!r} is not a round name')
    if not os.path.isfile(os.path.join(run, name + '.jsonl')):
        return fail(f'no round {name!r}: {name}.jsonl is not in {run}')
    if a.n < 1:
        return fail('N must be 1 or more')
    reason, by = a.reason.strip(), a.by.strip()
    if not reason:
        return fail('--reason is empty')
    if not by:
        return fail('--by is empty')
    row = {'round': name, 'n': a.n, 'grade': a.grade, 'ruled': a.ruled, 'by': by, 'reason': reason,
           'area': (a.area or '').strip() or None,
           'at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')}
    with open(os.path.join(run, 'rulings.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Record the orchestrator's ruling on a review finding.")
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('add', help='append one ruling to <run>/rulings.jsonl')
    p.add_argument('run', help='run folder')
    p.add_argument('round', help='review round name (a <run>/<round>.jsonl)')
    p.add_argument('n', type=int, help="the finding's number in that review")
    p.add_argument('--grade', required=True, choices=GRADES, help="the reviewer's grade")
    p.add_argument('--ruled', required=True, choices=RULINGS, help="the orchestrator's ruling")
    p.add_argument('--by', required=True, help='who ruled')
    p.add_argument('--reason', required=True, help='why, in one line')
    p.add_argument('--area', help="the finding's rubric area (SEC, COR, DATA ...)")
    a = ap.parse_args(argv)
    return add(a)


if __name__ == '__main__':
    sys.exit(main())
