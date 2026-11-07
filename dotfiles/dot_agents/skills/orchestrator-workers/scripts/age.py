#!/usr/bin/env python3
"""Propose ODC v5.2's Age for one line of a reviewed branch, from git blame: a proposal the reviewer confirms.

Usage:
    python3 age.py <worktree> <base> <file> <line> [--fix-start COMMIT]
    python3 age.py --help

Prints `<Age> <commit or -> <reason>`, exit 0 (2 on a usage error). Age (ODC v5.2, section 4.2.4,
https://s3.us.cloud-object-storage.appdomain.cloud/res-files/70-ODC-5-2.pdf):
    Base       the line is at the base commit or before it (blame marks it boundary)
    ReFixed    a fix commit put it in (after --fix-start)
    Rewritten  a build commit put it in, in a hunk that replaced lines of its parent
    New        a build commit put it in, in a hunk that only added lines
    unknown    anything else, with the reason: a line out of range, a file not in HEAD, a blame that fails, an
               uncommitted change to the file, or a commit brought in by a merge (main merged in after the base)
Blame runs as `git blame --porcelain -w -L <line>,<line> <base>..HEAD -- <file>`: -w gives a whitespace-only change
to the commit before it; a whole-file rename is followed without -M or -C, which are not used. A file the worktree
does not have at that path is looked up as the one tracked file ending in /<file>. Labels come from reviewprep.py's
labelled_commits. Blame only proposes: SZZ-style linking was right about half the time (recall and precision 0.40 to
0.60, https://arxiv.org/html/2308.05060v2; research/2026-11-06-why-a-major-got-in.md in the dotfiles repository).
"""
import argparse, json, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reviewprep  # noqa: E402

AGES = ('Base', 'New', 'Rewritten', 'ReFixed', 'unknown')
HUNK = re.compile(r'^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', re.M)


def git(wt, *args):
    return subprocess.run(['git', '-C', wt, *args], capture_output=True, text=True, stdin=subprocess.DEVNULL)


def unknown(reason, commit=None):
    return {'age': 'unknown', 'commit': commit, 'reason': reason}


def tracked(wt, path):
    """(the path HEAD has, note) for the file; a path HEAD lacks is matched as the one tracked file ending in it."""
    if not git(wt, 'cat-file', '-e', f'HEAD:{path}').returncode:
        return path, ''
    hits = [f for f in git(wt, 'ls-files').stdout.splitlines() if f.endswith('/' + path.lstrip('./'))]
    if len(hits) == 1:
        return hits[0], f' ({path} read as {hits[0]})'
    return None, ''


def propose(wt, base, path, line, fix=None):
    """{'age', 'commit', 'reason'} for line `line` of `path` in the worktree, over base..HEAD."""
    try:
        line = int(line)
    except (TypeError, ValueError):
        return unknown(f'line {line!r} is not a number')
    if line < 1:
        return unknown(f'line {line} is out of range')
    try:
        labels = {sha: label for sha, _, label in reviewprep.labelled_commits(wt, base, fix)}
    except (reviewprep.PrepError, OSError) as e:
        return unknown(f'the branch history could not be read: {e}')
    real, note = tracked(wt, path)
    if real is None:
        return unknown(f'{path} is not in HEAD (deleted, renamed away or never committed)')
    if git(wt, 'status', '--porcelain', '--', real).stdout.strip():
        return unknown(f'{real} has an uncommitted change, so its line numbers may not be HEAD\'s')
    p = git(wt, 'blame', '--porcelain', '-w', '-L', f'{line},{line}', f'{base}..HEAD', '--', real)
    if p.returncode:
        return unknown(f"git blame failed: {(p.stderr.strip().splitlines() or ['no message'])[0]}")
    head = p.stdout.splitlines()
    first = head[0].split() if head else []
    if len(first) < 2:
        return unknown('git blame printed no line')
    sha, orig = first[0], int(first[1])
    named = next((h[len('filename '):] for h in head if h.startswith('filename ')), real)
    if 'boundary' in head or sha == base:
        return {'age': 'Base', 'commit': sha, 'reason': f'line {line} of {real} is from the base commit or before{note}'}
    label = labels.get(sha)
    if label is None:
        return unknown(f'blame gives {sha[:12]}, which is not between the base and HEAD', sha)
    if label in ('merge', 'merged'):
        return unknown(f'{sha[:12]} came in through a merge ({label}), not from this item\'s own work', sha)
    if label == 'fix':
        return {'age': 'ReFixed', 'commit': sha, 'reason': f'{sha[:12]} is a fix commit{note}'}
    d = git(wt, 'show', '-U0', '-w', '-M', '--format=', sha)
    if d.returncode:
        return unknown(f'git show {sha[:12]} failed', sha)
    section = next((s for s in re.split(r'^diff --git ', d.stdout, flags=re.M)
                    if re.search(r'^\+\+\+ b/' + re.escape(named) + r'$', s, re.M)), '')
    for m in HUNK.finditer(section):
        old, start, count = int(m.group(1) or 1), int(m.group(2)), int(m.group(3) or 1)
        if start <= orig < start + count:
            if old:
                return {'age': 'Rewritten', 'commit': sha,
                        'reason': f'build commit {sha[:12]} replaced {old} line(s) there{note}'}
            return {'age': 'New', 'commit': sha, 'reason': f'build commit {sha[:12]} only added lines there{note}'}
    return unknown(f'line {orig} of {named} is not in a hunk of {sha[:12]}', sha)


def context(run, item):
    """{'wt', 'base', 'fix'} of an item from its run folder (queue.json, <item>.reviewbase or .base,
    <item>-fix1.base), or {'reason'} when the worktree or base cannot be found."""
    try:
        with open(os.path.join(run, 'queue.json'), encoding='utf-8') as f:
            it = next((x for x in json.load(f).get('items', []) if x.get('id') == item), None)
    except (OSError, ValueError, AttributeError, TypeError):
        it = None
    wt = (it or {}).get('worktree')
    if not wt:
        return {'reason': f'queue.json in the run folder has no worktree for {item}'}
    if not os.path.isdir(wt):
        return {'reason': f'the worktree {wt} is gone'}
    build = next((s.get('head') for s in it.get('pipeline', []) if s.get('name') == 'build'), None)
    path = reviewprep.first(os.path.join(run, item + '.reviewbase'))
    base = (reviewprep.read(path).strip() if path else None) or build
    if not base:
        path = reviewprep.first(os.path.join(run, item + '.base'))
        base = reviewprep.read(path).strip() if path else None
    if not base:
        return {'reason': f'no base commit recorded for {item}'}
    return {'wt': wt, 'base': base, 'fix': reviewprep.fix_start(run, item)}


def propose_in(ctx, path, line):
    if 'reason' in ctx:
        return unknown(ctx['reason'])
    return propose(ctx['wt'], ctx['base'], path, line, ctx['fix'])


def main(argv=None):
    ap = argparse.ArgumentParser(description="Propose ODC's Age for one line of a branch from git blame.")
    ap.add_argument('worktree')
    ap.add_argument('base', help='the commit the reviewed diff starts from')
    ap.add_argument('file', help='path relative to the worktree')
    ap.add_argument('line', type=int)
    ap.add_argument('--fix-start', help='the commit the fix round started from; commits after it are fix')
    a = ap.parse_args(argv)
    r = propose(os.path.abspath(os.path.expanduser(a.worktree)), a.base, a.file, a.line, a.fix_start)
    print(r['age'], r['commit'] or '-', r['reason'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
