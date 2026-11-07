#!/usr/bin/env python3
"""Propose ODC v5.2's Age for one line of a reviewed branch, from git blame: a proposal the reviewer confirms.

Usage:
    python3 age.py <worktree> <base> <file> <line> [--fix-start COMMIT]
    python3 age.py --help

Prints `<Age> <commit or -> <reason>`, exit 0 (2 on a usage error). Age (ODC v5.2, section 4.2.4,
https://s3.us.cloud-object-storage.appdomain.cloud/res-files/70-ODC-5-2.pdf):
    Base       the line is at the base commit or before it (blame marks it boundary)
    ReFixed    a fix commit put it in (after --fix-start)
    Rewritten  a build commit put it in, in a hunk that replaced lines which trace back to the base
    New        a build commit put it in, in a hunk that only added lines or replaced lines the branch itself added
    unknown    anything else, with the reason: a line out of range, a file not in HEAD, a blame that fails, an
               uncommitted change to the file, or a commit brought in by a merge (main merged in after the base)
Blame runs as `git blame --porcelain -w -L <line>,<line> <base>..HEAD -- <file>`: -w gives a whitespace-only change
to the commit before it; a whole-file rename is followed without -M or -C, which are not used. A file HEAD does not
have at that path (deleted, or the name before a rename) is unknown; give the path HEAD has. Whether replaced lines
trace back to the base is found by blaming each line the hunk removed in the commit's parent, a line whose commit is
the base or its ancestor (`git merge-base --is-ancestor`) being from the base, and again for each line that came from
an earlier branch commit (`git log -L` would give the same chain as patches to
parse). Labels come from reviewprep.py's
labelled_commits. Blame only proposes: SZZ-style linking was right about half the time (recall and precision 0.40 to
0.60, https://arxiv.org/html/2308.05060v2; research/2026-11-06-why-a-major-got-in.md in the dotfiles repository).
"""
import argparse, json, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reviewprep  # noqa: E402

AGES = ('Base', 'New', 'Rewritten', 'ReFixed', 'unknown')
HUNK = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', re.M)


def git(wt, *args):
    return subprocess.run(['git', '-C', wt, *args], capture_output=True, text=True, stdin=subprocess.DEVNULL)


def unknown(reason, commit=None):
    return {'age': 'unknown', 'commit': commit, 'reason': reason}


def tracked(wt, path):
    """(the path HEAD has, '') for the file, `./` and `a/../` resolved; (None, why) when HEAD has no file there."""
    norm = os.path.normpath(path).replace(os.sep, '/')
    if norm.startswith('../') or norm in ('.', '..') or os.path.isabs(norm):
        return None, f'{path} is not inside the worktree'
    if not git(wt, 'cat-file', '-e', f'HEAD:{norm}').returncode:
        return norm, ''
    return None, f'{path} is not in HEAD (deleted, renamed away or never committed); give the path HEAD has'


def blame_one(wt, rng, path, line):
    """(commit, line there, file name there, boundary) of one line, or None when blame fails."""
    p = git(wt, 'blame', '--porcelain', '-w', '-L', f'{line},{line}', rng, '--', path)
    head = p.stdout.splitlines()
    first = head[0].split() if not p.returncode and head else []
    if len(first) < 2:
        return None
    named = next((h[len('filename '):] for h in head if h.startswith('filename ')), path)
    return first[0], int(first[1]), named, 'boundary' in head


def hunk_of(wt, sha, path, line):
    """(old path, first removed line, removed count) of the hunk of commit `sha` that added line `line` of `path`."""
    d = git(wt, 'show', '-U0', '-w', '-M', '--format=', sha)
    if d.returncode:
        return None
    for sec in re.split(r'^diff --git ', d.stdout, flags=re.M):
        if not re.search(r'^\+\+\+ b/' + re.escape(path) + r'$', sec, re.M):
            continue
        old = re.search(r'^--- (?:a/(.*)|/dev/null)$', sec, re.M)
        for m in HUNK.finditer(sec):
            start, count = int(m.group(3)), int(m.group(4) or 1)
            if start <= line < start + count:
                return (old and old.group(1)) or path, int(m.group(1)), int(m.group(2) or 1)
    return None


def from_base(wt, base, sha, path, line, seen):
    """True when the lines commit `sha`'s hunk replaced to write line `line` of `path` trace back to the base."""
    if (sha, path, line) in seen:
        return False
    seen.add((sha, path, line))
    hunk = hunk_of(wt, sha, path, line)
    if not hunk or not hunk[2]:
        return False
    old_path, first, count = hunk
    for n in range(first, first + count):
        b = blame_one(wt, f'{sha}^', old_path, n)
        if not b:
            continue
        # A blame range base..<parent> is empty when the parent is the base, and git then blames HEAD instead.
        if not git(wt, 'merge-base', '--is-ancestor', b[0], base).returncode:
            return True
        if from_base(wt, base, b[0], b[2], b[1], seen):
            return True
    return False


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
    real, why = tracked(wt, path)
    if real is None:
        return unknown(why)
    note = '' if real == path else f' ({path} read as {real})'
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
    hunk = hunk_of(wt, sha, named, orig)
    if hunk is None:
        return unknown(f'line {orig} of {named} is not in a hunk of {sha[:12]}', sha)
    if from_base(wt, base, sha, named, orig, set()):
        return {'age': 'Rewritten', 'commit': sha,
                'reason': f'build commit {sha[:12]} replaced line(s) that trace back to the base{note}'}
    did = 'replaced only lines the branch added' if hunk[2] else 'only added lines'
    return {'age': 'New', 'commit': sha, 'reason': f'build commit {sha[:12]} {did} there{note}'}


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
