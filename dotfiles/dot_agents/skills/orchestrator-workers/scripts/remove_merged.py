#!/usr/bin/env python3
"""Archive what a merged item's worktree holds uncommitted, then remove the worktree and its merged branch.

  remove_merged.py --repo REPO --branch BRANCH [--main NAME] [--run-dir RUN] [--archive DIR] [--dry-run] [--json]

Each run's merge script calls it once main has moved. The branch counts as merged when its tip is an ancestor of
main (git merge-base --is-ancestor), a branch with no commits of its own included. In order, it finds the branch's
worktree, notes the tip, and, when the worktree's folder exists, archives into <archive>/<repo>/<item>/ (<repo> the
folder name of the main worktree, <item> that of the item's; <item>-<tip, 10 characters>[-N] when taken, never
overwritten): status.txt (git status --porcelain=v1), uncommitted.patch (git diff --binary HEAD, only when not
empty) and every untracked path git does not ignore, under the same relative path, symlinks as symlinks; inside an
untracked nested repository or worktree, .git, node_modules and .vitest are skipped and named. It then stops orphans
whose working folder is inside the worktree (sweep.py), removes the worktrees registered inside it, then the
worktree (git worktree remove --force; for a folder already deleted this clears only its registration), deletes
the branch only if it still points at the noted tip (git update-ref -d <ref> <tip>) and no worktree holds it, and
appends one line to <archive>/index.tsv under a lock (tabs, newlines and backslashes in a field escaped as \\t, \\n,
\\r, \\\\).

Outcomes follow worktrunk's `wt remove`. branch: deleted, retained_unmerged, retained_checked_out, retained_raced,
retained_failed, not_attempted. worktree: removed, already_gone (folder deleted by hand, registration cleared),
none (the branch has no worktree), not_attempted, retained_locked, retained_in_use (a live process that is not an
orphan works inside it), retained_failed (a failed archive is deleted and nothing is removed).
Exit 0: the worktree is gone and the branch deleted. Exit 1: something was kept, for the owner's list, not a
failed merge; nothing is archived or removed unless the worktree outcome says so. Exit 2: usage error (no such
branch, the branch is main, it is checked out in the main worktree), nothing changed.
--dry-run prints what would be archived, stopped, removed and deleted, changes nothing, and exits as a real run
would. --json prints one object instead of the lines.
"""
import argparse, datetime, fcntl, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sweep  # noqa: E402

ARCHIVE = os.path.join('~', '.local', 'state', 'orchestrator-workers', '_archive', 'worktrees')
SKIP = ('.git', 'node_modules', '.vitest')
OWN = ('status.txt', 'uncommitted.patch')
COLUMNS = ('repo', 'branch', 'last_commit', 'worktree', 'untracked_items_archived', 'archived_at', 'archive_dir',
           'run_dir', 'bytes', 'branch_outcome')


class Usage(Exception):
    pass


class Failed(Exception):
    pass


def git(cwd, *args, binary=False):
    kw = {} if binary else {'text': True, 'encoding': 'utf-8', 'errors': 'surrogateescape'}
    return subprocess.run(['git', '-C', cwd, *args], capture_output=True, stdin=subprocess.DEVNULL, **kw)


def out(cwd, *args, binary=False):
    r = git(cwd, *args, binary=binary)
    if r.returncode:
        err = r.stderr.decode('utf-8', 'replace') if binary else r.stderr
        raise Failed(f"git {' '.join(args)}: {err.strip()}")
    return r.stdout


def rev(cwd, ref):
    r = git(cwd, 'rev-parse', '--verify', '--quiet', ref + '^{commit}')
    return r.stdout.strip() if r.returncode == 0 else None


def worktrees(repo):
    items, cur = [], {}
    for field in out(repo, 'worktree', 'list', '--porcelain', '-z').split('\0'):
        if not field:
            if cur:
                items.append(cur)
            cur = {}
            continue
        key, _, value = field.partition(' ')
        cur[key] = value or True
    return items


def real(path):
    return os.path.realpath(path)


def inside(path, root):
    return (path.rstrip('/') + '/').startswith(root.rstrip('/') + '/')


def escape(value):
    return str(value).replace('\\', '\\\\').replace('\t', '\\t').replace('\n', '\\n').replace('\r', '\\r')


def find_skips(src, top):
    found = []
    for d, dirs, files in os.walk(src):
        for n in sorted(set(dirs + files) & set(SKIP)):
            found.append(os.path.relpath(os.path.join(d, n), top))
        dirs[:] = [n for n in dirs if n not in SKIP]
    return found


def processes_in(root):
    """(orphans, live) whose working folder is inside root; a descendant of such an orphan is the orphan's."""
    procs, dirs = sweep.processes(), sweep.cwds()
    orphans = [x for x in sweep.leftovers(root, procs, dirs) if x[2] and inside(x[2], root)]
    left = {pid for pid, _, _ in orphans}
    live = []
    for pid, cwd in sorted(dirs.items()):
        if pid == os.getpid() or pid not in procs or pid in left or not inside(cwd, root):
            continue
        p, seen = procs[pid][0], set()
        while p in procs and p not in left and p > 1 and p not in seen:
            seen.add(p)
            p = procs[p][0]
        if p not in left:
            live.append((pid, procs[pid][1]))
    return orphans, live


def stop_orphans(root):
    stopped = []
    for _ in range(3):  # stopping a parent orphans its children, so look again
        found, _ = processes_in(root)
        if not found:
            break
        sweep.stop([pid for pid, _, _ in found])
        stopped += found
    return stopped


def pick_dest(base, item, tip, dry):
    for name in [item, f'{item}-{tip[:10]}'] + [f'{item}-{tip[:10]}-{n}' for n in range(2, 100)]:
        dest = os.path.join(base, name)
        if dry:
            if not os.path.lexists(dest):
                return dest
            continue
        os.makedirs(base, exist_ok=True)
        try:
            os.mkdir(dest)
            return dest
        except FileExistsError:
            continue
    raise Failed(f'every archive name for {item} under {base} is taken')


def archive(path, dest_base, item, tip, dry, res):
    top = out(path, 'rev-parse', '--show-toplevel').strip()
    if real(top) != real(path):
        raise Failed(f'{path} is not a git worktree any more (git finds {top})')
    rels = [r for r in out(path, 'ls-files', '--others', '--exclude-standard', '-z').split('\0') if r]
    res['untracked_items'] = len(rels)
    clash = [r for r in rels if r.rstrip('/') in OWN]
    if clash:
        raise Failed(f'untracked {", ".join(clash)} would collide with the archive\'s own file')
    for rel in rels:
        if rel.endswith('/'):
            res['skipped'] += find_skips(os.path.join(path, rel.rstrip('/')), path)
    if dry:
        res['archive_dir'] = pick_dest(dest_base, item, tip, True)
        return
    status = out(path, 'status', '--porcelain=v1', binary=True)
    patch = out(path, 'diff', '--binary', 'HEAD', binary=True)
    dest = pick_dest(dest_base, item, tip, False)
    res['archive_dir'] = dest
    with open(os.path.join(dest, 'status.txt'), 'xb') as f:
        f.write(status)
    if patch:
        with open(os.path.join(dest, 'uncommitted.patch'), 'xb') as f:
            f.write(patch)
    for rel in rels:
        src, dst = os.path.join(path, rel.rstrip('/')), os.path.join(dest, rel.rstrip('/'))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.lexists(dst):
            raise Failed(f'{rel} is already in the archive')
        if os.path.islink(src):
            os.symlink(os.readlink(src), dst)
        elif os.path.isdir(src):
            shutil.copytree(src, dst, symlinks=True, ignore=shutil.ignore_patterns(*SKIP))
        else:
            shutil.copy2(src, dst)
    total = 0
    for d, dirs, files in os.walk(dest):
        for n in files + [x for x in dirs if os.path.islink(os.path.join(d, x))]:
            total += os.lstat(os.path.join(d, n)).st_size
    res['bytes'] = total


def append_index(index, row):
    with open(index, 'a', encoding='utf-8', errors='surrogateescape') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            if os.fstat(f.fileno()).st_size == 0:
                f.write('\t'.join(COLUMNS) + '\n')
            f.write('\t'.join(escape(v) for v in row) + '\n')
            f.flush()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def remove(a, res):
    repo = os.path.abspath(os.path.expanduser(a.repo))
    if not os.path.isdir(repo) or git(repo, 'rev-parse', '--git-dir').returncode:
        raise Usage(f'no git repository at {repo}')
    if a.run_dir is not None:
        if not os.path.isdir(os.path.expanduser(a.run_dir)):
            raise Usage(f'no run folder at {a.run_dir}')
        res['run_dir'] = os.path.abspath(os.path.expanduser(a.run_dir))
    branch = a.branch.removeprefix('refs/heads/')
    ref = 'refs/heads/' + branch
    wts = worktrees(repo)
    main_wt = wts[0]['worktree']
    repo_name = os.path.basename(main_wt.rstrip('/'))
    res['repo'] = repo_name
    if branch == a.main.removeprefix('refs/heads/'):
        raise Usage(f'{branch} is the main branch')
    tip = rev(main_wt, ref)
    if not tip:
        raise Usage(f'no branch {branch}')
    main_tip = rev(main_wt, 'refs/heads/' + a.main.removeprefix('refs/heads/'))
    if not main_tip:
        raise Usage(f'no branch {a.main}')
    res['tip'] = tip
    held = [w for w in wts if w.get('branch') == ref]
    if any(real(w['worktree']) == real(main_wt) for w in held):
        raise Usage(f'{branch} is checked out in the main worktree {main_wt}')
    wt = next((w for w in held if os.path.basename(w['worktree'].rstrip('/')) == branch.rsplit('/', 1)[-1]),
              held[0] if held else None)
    path = wt['worktree'] if wt else None
    res['path'] = path
    anc = git(main_wt, 'merge-base', '--is-ancestor', tip, main_tip).returncode
    if anc == 1:
        res['branch_outcome'] = 'retained_unmerged'
        return
    if anc:
        raise Failed(f'git merge-base --is-ancestor {tip} {main_tip} exited {anc}')
    archive_root = os.path.abspath(os.path.expanduser(a.archive))
    nested, exists, root = [], False, None
    if path is not None:
        root = real(path)
        nested = [w for w in wts[1:] if w is not wt and inside(real(w['worktree']), root)]
        nested.sort(key=lambda w: -len(real(w['worktree'])))
        res['nested'] = [w['worktree'] for w in nested]
        locked = [w['worktree'] for w in [wt] + nested if 'locked' in w]
        if locked:
            res['worktree_outcome'] = 'retained_locked'
            res['locked'] = locked
            return
        exists = os.path.isdir(path)
        if exists:
            orphans, live = processes_in(root)
            res['in_use'] = [{'pid': p, 'command': c} for p, c in live]
            if live:
                res['worktree_outcome'] = 'retained_in_use'
                return
            res['stopped'] = [{'pid': p, 'command': c, 'cwd': d} for p, c, d in orphans]
    if not a.dry_run:
        try:
            os.makedirs(archive_root, exist_ok=True)
            open(os.path.join(archive_root, 'index.tsv'), 'a').close()
        except OSError as e:
            res['worktree_outcome' if path is not None else 'branch_outcome'] = 'retained_failed'
            res['error'] = f'archive folder not writable: {e}'
            return
    res['index'] = os.path.join(archive_root, 'index.tsv')
    if path is None:
        res['worktree_outcome'] = 'none'
    else:
        if exists:
            try:
                archive(path, os.path.join(archive_root, repo_name), os.path.basename(path.rstrip('/')), tip,
                        a.dry_run, res)
            except (Failed, OSError, shutil.Error) as e:
                res['worktree_outcome'] = 'retained_failed'
                res['error'] = f'archive failed: {e}'
                dest = res.pop('archive_dir', None)
                if dest and not a.dry_run:
                    shutil.rmtree(dest, ignore_errors=True)
                    res['error'] += '; the partial archive was deleted' if not os.path.lexists(dest) else \
                        f'; the partial archive is left at {dest}'
                res['archive_dir'] = None
                return
            if not a.dry_run:
                res['stopped'] = [{'pid': p, 'command': c, 'cwd': d} for p, c, d in stop_orphans(root)]
        if not a.dry_run:
            try:
                remove_worktrees(main_wt, nested, path)
            except Failed as e:
                res['worktree_outcome'] = 'retained_failed'
                res['error'] = str(e)
                return
        res['worktree_outcome'] = 'removed' if exists else 'already_gone'
    if a.dry_run:
        others = [w['worktree'] for w in held if w is not wt and w not in nested]
    else:
        others = [w['worktree'] for w in worktrees(main_wt) if w.get('branch') == ref]
    if others:
        res['branch_outcome'] = 'retained_checked_out'
        res['checked_out'] = others
        return
    if a.dry_run:
        res['branch_outcome'] = 'deleted'
        return
    r = git(main_wt, 'update-ref', '-d', ref, tip)
    if r.returncode == 0:
        res['branch_outcome'] = 'deleted'
        return
    now = rev(main_wt, ref)
    res['branch_outcome'] = 'retained_raced' if now and now != tip else 'retained_failed'
    res['error'] = f'git update-ref -d {ref} {tip}: {r.stderr.strip()}'


def remove_worktrees(main_wt, nested, path):
    for w in nested + [{'worktree': path}]:
        r = git(main_wt, 'worktree', 'remove', '--force', w['worktree'])
        if r.returncode:
            raise Failed(f"git worktree remove --force {w['worktree']}: {r.stderr.strip()}")


def lines(res):
    pre = 'dry run: ' if res['dry_run'] else ''
    tip = (res.get('tip') or '')[:10]
    if res.get('archive_dir') and res['worktree_outcome'] in ('removed', 'retained_failed', 'already_gone'):
        yield f"{pre}archived {res['archive_dir']} ({res['untracked_items']} untracked items" + \
            (f", {res['bytes']} bytes)" if res.get('bytes') is not None else ')')
    for s in res['skipped']:
        yield f'{pre}skipped {s}'
    for p in res['stopped']:
        yield f"{pre}stopped {p['pid']} {p['command']} cwd={p['cwd']}"
    if res['worktree_outcome'] in ('removed', 'already_gone'):
        for n in res['nested']:
            yield f'{pre}removed nested worktree {n}'
    wt = f"worktree {res['worktree_outcome']} {res.get('path') or '-'}"
    if res['worktree_outcome'] == 'retained_in_use':
        wt += ': in use by ' + ', '.join(f"{p['pid']} {p['command']}" for p in res['in_use'])
    elif res['worktree_outcome'] == 'retained_locked':
        wt += ': locked ' + ', '.join(res['locked'])
    elif res['worktree_outcome'] == 'retained_failed' and res.get('error'):
        wt += ': ' + res['error']
    yield pre + wt
    br = f"branch {res['branch_outcome']} {res['branch']} {tip}".rstrip()
    if res['branch_outcome'] == 'retained_unmerged':
        br += f": not in {res['main']}"
    elif res['branch_outcome'] == 'retained_checked_out':
        br += ': checked out in ' + ', '.join(res['checked_out'])
    elif res['branch_outcome'] in ('retained_raced', 'retained_failed') and res.get('error'):
        br += ': ' + res['error']
    yield pre + br
    if res.get('index_error'):
        yield f"index not written: {res['index_error']}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--repo', required=True, help='the repository, or any of its worktrees')
    ap.add_argument('--branch', required=True, help='the merged item branch, for example ow/<item>')
    ap.add_argument('--main', default='main', help='the branch it must be in (default main)')
    ap.add_argument('--run-dir', help='the run folder, recorded in the index')
    ap.add_argument('--archive', default=ARCHIVE, help=f'archive folder (default {ARCHIVE})')
    ap.add_argument('--dry-run', action='store_true', help='print what would happen and change nothing')
    ap.add_argument('--json', action='store_true', help='print one JSON object instead of lines')
    a = ap.parse_args(argv)
    res = {'repo': None, 'branch': a.branch.removeprefix('refs/heads/'), 'main': a.main, 'path': None, 'tip': None,
           'branch_outcome': 'not_attempted', 'worktree_outcome': 'not_attempted', 'archive_dir': None,
           'untracked_items': 0, 'bytes': None, 'skipped': [], 'stopped': [], 'in_use': [], 'nested': [],
           'run_dir': None, 'dry_run': a.dry_run}
    try:
        remove(a, res)
    except Usage as e:
        res['error'] = str(e)
        if a.json:
            print(json.dumps({**res, 'exit': 2}))
        print(f'remove_merged.py: {e}; nothing changed', file=sys.stderr)
        return 2
    except Failed as e:
        res['error'] = str(e)
        if res['worktree_outcome'] == 'not_attempted' and res['branch_outcome'] == 'not_attempted':
            res['branch_outcome'] = 'retained_failed'
    changed = res['worktree_outcome'] in ('removed', 'already_gone') or res['branch_outcome'] == 'deleted' or \
        (res['archive_dir'] and res['worktree_outcome'] == 'retained_failed')
    if changed and not a.dry_run and res.get('index'):
        try:
            append_index(res['index'], [res['repo'], res['branch'], res['tip'], res['path'] or '',
                                        res['untracked_items'] if res['archive_dir'] else 0,
                                        datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
                                        res['archive_dir'] or '', res['run_dir'] or '',
                                        res['bytes'] if res['bytes'] is not None else 0, res['branch_outcome']])
        except OSError as e:
            res['index_error'] = str(e)
    ok = res['worktree_outcome'] in ('removed', 'already_gone', 'none') and res['branch_outcome'] == 'deleted' \
        and not res.get('index_error')
    code = 0 if ok else 1
    if a.json:
        print(json.dumps({**res, 'exit': code}))
    else:
        for line in lines(res):
            print(line)
    return code


if __name__ == '__main__':
    sys.exit(main())
