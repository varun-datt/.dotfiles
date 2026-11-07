import contextlib
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from unittest import mock

import remove_merged

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, 'remove_merged.py')
OLD_COLUMNS = ['repo', 'branch', 'last_commit', 'worktree', 'untracked_items_archived']


def git(cwd, *args, binary=False):
    r = subprocess.run(['git', '-C', cwd, *args], capture_output=True, text=not binary, stdin=subprocess.DEVNULL)
    if r.returncode:
        raise AssertionError(f'git {args}: {r.stderr}')
    return r.stdout


class RemoveMergedBase(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix='ow rm '))
        self.addCleanup(self.cleanup)
        self.repo = os.path.join(self.tmp, 'repo')
        self.wts = os.path.join(self.tmp, 'wts')
        self.archive = os.path.join(self.tmp, 'archive')
        self.run_dir = os.path.join(self.tmp, 'run')
        os.makedirs(self.repo)
        os.makedirs(self.run_dir)
        git(self.repo, 'init', '-q', '-b', 'main')
        git(self.repo, 'config', 'user.email', 't@example.com')
        git(self.repo, 'config', 'user.name', 't')
        self.write(self.repo, 'a.txt', 'a\n')
        self.write(self.repo, 'x.sh', 'echo x\n')
        self.write(self.repo, 'gone.txt', 'gone\n')
        self.write(self.repo, 'bin.dat', bytes(range(256)))
        self.write(self.repo, '.gitignore', 'ignored/\n')
        git(self.repo, 'add', '.')
        git(self.repo, 'commit', '-qm', 'base')
        self.procs = []

    def cleanup(self):
        for p in self.procs:
            try:
                os.kill(p, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        for d, dirs, files in os.walk(self.tmp):
            for n in dirs + files:
                try:
                    os.chmod(os.path.join(d, n), 0o755, follow_symlinks=False)
                except (OSError, NotImplementedError):
                    pass
        os.chmod(self.tmp, 0o755)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, root, rel, data):
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb' if isinstance(data, bytes) else 'w') as f:
            f.write(data)
        return path

    def item(self, name='it', merged=True, commit=True, branch=None):
        branch = branch or f'ow/{name}'
        wt = os.path.join(self.wts, name)
        git(self.repo, 'worktree', 'add', '-q', '-b', branch, wt, 'main')
        if commit:
            self.write(wt, f'{name}.txt', f'{name}\n')
            git(wt, 'add', '.')
            git(wt, 'commit', '-qm', f'item {name}')
        if merged and commit:
            git(self.repo, 'merge', '-q', '--no-ff', branch, '-m', f'merge {name}')
        return wt

    def call(self, *extra, branch='ow/it', archive=True):
        argv = ['--repo', self.repo, '--branch', branch, '--run-dir', self.run_dir, *extra]
        if archive:
            argv += ['--archive', self.archive]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = remove_merged.main(argv)
        return code, out.getvalue(), err.getvalue()

    def call_json(self, *extra, **kw):
        code, out, err = self.call('--json', *extra, **kw)
        self.assertEqual(out.count('\n'), 1, out)
        return code, json.loads(out)

    def registered(self):
        return [f.split(' ', 1)[1] for f in git(self.repo, 'worktree', 'list', '--porcelain', '-z').split('\0')
                if f.startswith('worktree ')]

    def branches(self):
        return git(self.repo, 'for-each-ref', '--format=%(refname) %(objectname)', 'refs/heads/')

    def tree(self, root):
        found = []
        for d, dirs, files in os.walk(root):
            for n in sorted(dirs + files):
                p = os.path.join(d, n)
                st = os.lstat(p)
                found.append((os.path.relpath(p, root), st.st_mode, st.st_size, st.st_mtime_ns))
        return sorted(found)

    def state(self):
        return self.registered(), self.branches(), self.tree(self.archive), self.tree(self.wts)

    def tip(self, branch='ow/it'):
        return git(self.repo, 'rev-parse', branch).strip()

    def index_rows(self):
        with open(os.path.join(self.archive, 'index.tsv'), encoding='utf-8') as f:
            return [line.split('\t') for line in f.read().split('\n') if line]

    def orphan(self, cwd):
        p = subprocess.run(['sh', '-c', 'sleep 300 >/dev/null 2>&1 & echo $!'], cwd=cwd, capture_output=True,
                           text=True, stdin=subprocess.DEVNULL)
        pid = int(p.stdout.strip())
        self.procs.append(pid)
        deadline = time.time() + 10
        while time.time() < deadline and remove_merged.sweep.processes().get(pid, (0,))[0] != 1:
            time.sleep(0.1)
        self.assertEqual(remove_merged.sweep.processes()[pid][0], 1, 'the test process did not become an orphan')
        return pid


class ArchiveAndRemoveTest(RemoveMergedBase):
    def dirty(self, wt):
        self.write(wt, 'a.txt', 'a\nstaged\n')
        git(wt, 'add', 'a.txt')
        self.write(wt, 'a.txt', 'a\nstaged\nunstaged\n')
        os.remove(os.path.join(wt, 'gone.txt'))
        os.chmod(os.path.join(wt, 'x.sh'), 0o755)
        self.write(wt, 'bin.dat', bytes(reversed(range(256))))
        self.write(wt, 'new.bin', b'\x00\x01\xff' * 50)
        git(wt, 'add', 'new.bin')
        self.write(wt, 'notes with spaces.md', 'notes\n')
        self.write(wt, os.path.join('scratch dir', 'deep', 'f.txt'), 'deep\n')
        self.write(wt, os.path.join('ignored', 'big.log'), 'ignored\n')
        os.symlink('a.txt', os.path.join(wt, 'link to a'))

    def test_a_worktree_with_uncommitted_files_is_archived_then_removed(self):
        wt = self.item()
        self.dirty(wt)
        tip = self.tip()
        status = git(wt, 'status', '--porcelain=v1', binary=True)
        code, out, err = self.call()
        self.assertEqual(code, 0, out + err)
        dest = os.path.join(self.archive, 'repo', 'it')
        self.assertIn(f'archived {dest} (3 untracked items, ', out)
        self.assertIn(f'worktree removed {wt}', out)
        self.assertIn(f'branch deleted ow/it {tip[:10]}', out)
        self.assertFalse(os.path.exists(wt))
        self.assertNotIn(wt, self.registered())
        self.assertNotIn('refs/heads/ow/it ', self.branches())
        with open(os.path.join(dest, 'status.txt'), 'rb') as f:
            self.assertEqual(f.read(), status)
        for rel, want in (('notes with spaces.md', b'notes\n'), ('scratch dir/deep/f.txt', b'deep\n')):
            with open(os.path.join(dest, rel), 'rb') as f:
                self.assertEqual(f.read(), want)
        self.assertEqual(os.readlink(os.path.join(dest, 'link to a')), 'a.txt')
        self.assertFalse(os.path.exists(os.path.join(dest, 'ignored')))
        check = os.path.join(self.tmp, 'check')
        git(self.repo, 'worktree', 'add', '-q', '--detach', check, tip)
        git(check, 'apply', '--binary', '--index', os.path.join(dest, 'uncommitted.patch'))
        with open(os.path.join(check, 'a.txt')) as f:
            self.assertEqual(f.read(), 'a\nstaged\nunstaged\n')
        self.assertFalse(os.path.exists(os.path.join(check, 'gone.txt')))
        self.assertTrue(os.access(os.path.join(check, 'x.sh'), os.X_OK))
        with open(os.path.join(check, 'bin.dat'), 'rb') as f:
            self.assertEqual(f.read(), bytes(reversed(range(256))))
        with open(os.path.join(check, 'new.bin'), 'rb') as f:
            self.assertEqual(f.read(), b'\x00\x01\xff' * 50)
        rows = self.index_rows()
        self.assertEqual(rows[0][:5], OLD_COLUMNS)
        self.assertEqual(rows[0][5:], ['archived_at', 'archive_dir', 'run_dir', 'bytes', 'branch_outcome'])
        self.assertEqual(len(rows), 2)
        row = dict(zip(rows[0], rows[1]))
        self.assertEqual((row['repo'], row['branch'], row['last_commit'], row['worktree'], row['archive_dir'],
                          row['run_dir'], row['branch_outcome'], row['untracked_items_archived']),
                         ('repo', 'ow/it', tip, wt, dest, self.run_dir, 'deleted', '3'))
        self.assertGreater(int(row['bytes']), 256)

    def test_a_run_folder_with_no_reviews_is_archived_and_removed_as_usual(self):
        wt = self.item()
        self.write(wt, 'left.txt', 'left\n')
        self.assertEqual([n for n in os.listdir(self.run_dir) if n.startswith('it-review')], [])
        code, out, err = self.call()
        self.assertEqual(code, 0, out + err)
        self.assertTrue(os.path.isfile(os.path.join(self.archive, 'repo', 'it', 'left.txt')))
        self.assertFalse(os.path.exists(wt))
        self.assertNotIn('refs/heads/ow/it ', self.branches())

    def test_a_clean_worktree_keeps_only_its_status(self):
        wt = self.item()
        code, out, err = self.call()
        self.assertEqual(code, 0, out + err)
        dest = os.path.join(self.archive, 'repo', 'it')
        self.assertEqual(os.listdir(dest), ['status.txt'])
        self.assertEqual(os.path.getsize(os.path.join(dest, 'status.txt')), 0)
        self.assertFalse(os.path.exists(wt))

    def test_a_worktree_already_gone_clears_only_its_registration_and_deletes_the_branch(self):
        wt = self.item()
        other = self.item('other')
        shutil.rmtree(wt)
        shutil.rmtree(other)
        code, out, err = self.call()
        self.assertEqual(code, 0, out + err)
        self.assertIn(f'worktree already_gone {wt}', out)
        self.assertNotIn('archived', out)
        self.assertFalse(os.path.exists(os.path.join(self.archive, 'repo')))
        self.assertNotIn(wt, self.registered())
        self.assertIn(other, self.registered(), 'a prune would have cleared every missing worktree')
        self.assertNotIn('refs/heads/ow/it ', self.branches())
        self.assertEqual(self.index_rows()[1][6], '')

    def test_a_branch_with_no_worktree_is_deleted_and_nothing_archived(self):
        wt = self.item()
        git(self.repo, 'worktree', 'remove', '--force', wt)
        code, out, err = self.call()
        self.assertEqual(code, 0, out + err)
        self.assertIn('worktree none -', out)
        self.assertIn('branch deleted ow/it', out)
        self.assertNotIn('refs/heads/ow/it ', self.branches())
        self.assertFalse(os.path.exists(os.path.join(self.archive, 'repo')))
        self.assertEqual(len(self.index_rows()), 2)

    def test_a_branch_at_a_commit_of_main_counts_as_merged(self):
        wt = self.item(commit=False)
        code, out, err = self.call()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(out.splitlines()[-1], f'branch deleted ow/it {self.tip("main")[:10]}')
        self.assertFalse(os.path.exists(wt))

    def test_a_nested_worktree_is_removed_first_and_a_nested_repository_skips_its_heavy_folders(self):
        wt = self.item()
        nested = os.path.join(wt, '.gates', 'mainnow')
        git(self.repo, 'worktree', 'add', '-q', '--detach', nested, 'main')
        self.write(nested, os.path.join('node_modules', 'pkg', 'index.js'), 'x\n')
        repo2 = os.path.join(wt, 'vendor repo')
        os.makedirs(repo2)
        git(repo2, 'init', '-q')
        self.write(repo2, 'kept.txt', 'kept\n')
        self.write(repo2, os.path.join('node_modules', 'm.js'), 'm\n')
        self.write(repo2, os.path.join('.vitest', 'cache'), 'c\n')
        code, out, err = self.call()
        self.assertEqual(code, 0, out + err)
        self.assertIn(f'removed nested worktree {nested}', out)
        for skipped in ('vendor repo/.git', 'vendor repo/node_modules', 'vendor repo/.vitest', '.gates/mainnow/.git',
                        '.gates/mainnow/node_modules'):
            self.assertIn(f'skipped {skipped}\n', out)
        dest = os.path.join(self.archive, 'repo', 'it')
        self.assertTrue(os.path.isfile(os.path.join(dest, 'vendor repo', 'kept.txt')))
        self.assertTrue(os.path.isfile(os.path.join(dest, '.gates', 'mainnow', 'a.txt')))
        for gone in ('vendor repo/.git', 'vendor repo/node_modules', 'vendor repo/.vitest', '.gates/mainnow/.git',
                     '.gates/mainnow/node_modules'):
            self.assertFalse(os.path.lexists(os.path.join(dest, gone)), gone)
        self.assertNotIn(nested, self.registered())
        self.assertFalse(os.path.exists(wt))

    def test_an_orphan_left_in_the_worktree_is_stopped_and_named(self):
        wt = self.item()
        pid = self.orphan(os.path.join(wt))
        code, out, err = self.call()
        self.assertEqual(code, 0, out + err)
        self.assertRegex(out, rf'(?m)^stopped {pid} \S*sleep cwd=')
        self.assertFalse(remove_merged.sweep.alive(pid))
        self.assertFalse(os.path.exists(wt))


class KeepTest(RemoveMergedBase):
    def assert_unchanged(self, before, code, out, outcome, want_code=1):
        self.assertEqual(code, want_code, out)
        after = self.state()
        self.assertEqual((after[0], after[1], after[3]), (before[0], before[1], before[3]))
        self.assertIn(outcome, out)

    def test_a_branch_that_did_not_merge_is_kept(self):
        wt = self.item(merged=False)
        self.write(wt, 'left.txt', 'left\n')
        before = self.state()
        code, out, err = self.call()
        self.assert_unchanged(before, code, out, f'branch retained_unmerged ow/it {self.tip()[:10]}: not in main')
        self.assertIn('worktree not_attempted', out)
        self.assertFalse(os.path.exists(self.archive))

    def test_a_locked_worktree_is_kept(self):
        wt = self.item()
        git(self.repo, 'worktree', 'lock', wt)
        before = self.state()
        code, out, err = self.call()
        self.assert_unchanged(before, code, out, f'worktree retained_locked {wt}')
        self.assertIn('branch not_attempted', out)

    def test_a_locked_nested_worktree_keeps_the_item(self):
        wt = self.item()
        nested = os.path.join(wt, 'inner')
        git(self.repo, 'worktree', 'add', '-q', '--detach', nested, 'main')
        git(self.repo, 'worktree', 'lock', nested)
        before = self.state()
        code, out, err = self.call()
        self.assert_unchanged(before, code, out, f'worktree retained_locked {wt}: locked {nested}')

    def test_a_worktree_a_live_process_uses_is_kept_and_the_process_named(self):
        wt = self.item()
        p = subprocess.Popen(['sleep', '300'], cwd=os.path.join(wt), stdin=subprocess.DEVNULL)
        self.procs.append(p.pid)
        self.addCleanup(lambda: (p.kill(), p.wait()))
        before = self.state()
        code, out, err = self.call()
        self.assert_unchanged(before, code, out, f'worktree retained_in_use {wt}: in use by {p.pid} ')
        self.assertRegex(out, rf'in use by {p.pid} \S*sleep')
        self.assertIsNone(p.poll())

    def test_an_archive_that_fails_part_way_removes_nothing_and_deletes_the_partial_archive(self):
        wt = self.item()
        self.write(wt, 'a first.txt', 'first\n')
        secret = self.write(wt, 'z unreadable.txt', 'no\n')
        os.chmod(secret, 0)
        before = self.state()
        code, out, err = self.call()
        self.assert_unchanged(before, code, out, f'worktree retained_failed {wt}: archive failed: ')
        self.assertIn('; the partial archive was deleted', out)
        self.assertIn('branch not_attempted', out)
        self.assertEqual(os.listdir(os.path.join(self.archive, 'repo')), [])
        with open(os.path.join(self.archive, 'index.tsv')) as f:
            self.assertEqual(f.read(), '')

    def test_an_archive_folder_that_cannot_be_written_removes_nothing(self):
        wt = self.item()
        self.write(wt, 'left.txt', 'left\n')
        os.makedirs(self.archive)
        os.chmod(self.archive, 0o555)
        before = self.state()
        code, out, err = self.call()
        self.assert_unchanged(before, code, out, f'worktree retained_failed {wt}: archive folder not writable')

    def test_a_branch_that_moves_after_its_tip_is_noted_is_kept(self):
        wt = self.item()
        tip = self.tip()
        moved = git(self.repo, 'commit-tree', '-p', tip, '-m', 'late', f'{tip}^{{tree}}').strip()
        real_remove = remove_merged.remove_worktrees

        def remove_then_move(*args):
            real_remove(*args)
            git(self.repo, 'update-ref', 'refs/heads/ow/it', moved)

        with mock.patch.object(remove_merged, 'remove_worktrees', remove_then_move):
            code, out, err = self.call()
        self.assertEqual(code, 1, out)
        self.assertIn(f'worktree removed {wt}', out)
        self.assertIn(f'branch retained_raced ow/it {tip[:10]}: ', out)
        self.assertEqual(self.tip(), moved)
        self.assertEqual(self.index_rows()[1][9], 'retained_raced')

    def test_a_branch_checked_out_in_another_worktree_is_kept(self):
        wt = self.item()
        other = os.path.join(self.tmp, 'second')
        git(self.repo, 'worktree', 'add', '-q', '--force', other, 'ow/it')
        code, out, err = self.call()
        self.assertEqual(code, 1, out)
        self.assertIn(f'worktree removed {wt}', out)
        self.assertIn(f'branch retained_checked_out ow/it {self.tip()[:10]}: checked out in {other}', out)
        self.assertTrue(os.path.isdir(other))
        self.assertIn('refs/heads/ow/it ', self.branches())

    def test_usage_errors_exit_2_and_change_nothing(self):
        self.item()
        before = self.state()
        for branch, want in (('ow/none', 'no branch ow/none'), ('main', 'main is the main branch')):
            code, out, err = self.call(branch=branch)
            self.assertEqual(code, 2, err)
            self.assertIn(want, err)
            self.assertEqual(self.state(), before)
        git(self.repo, 'branch', 'ow/here', 'main')
        git(self.repo, 'checkout', '-q', 'ow/here')
        before = self.state()
        code, out, err = self.call(branch='ow/here')
        self.assertEqual(code, 2, err)
        self.assertIn('ow/here is checked out in the main worktree', err)
        self.assertEqual(self.state(), before)
        self.assertFalse(os.path.exists(self.archive))


class ArchiveIndexTest(RemoveMergedBase):
    def test_an_item_folder_already_archived_is_never_overwritten(self):
        base = os.path.join(self.archive, 'repo')
        self.write(base, os.path.join('it', 'old.txt'), 'old\n')
        wt = self.item()
        self.write(wt, 'new.txt', 'new\n')
        tip = self.tip()
        code, out, err = self.call()
        self.assertEqual(code, 0, out + err)
        with open(os.path.join(base, 'it', 'old.txt')) as f:
            self.assertEqual(f.read(), 'old\n')
        self.assertFalse(os.path.exists(os.path.join(base, 'it', 'new.txt')))
        self.assertTrue(os.path.isfile(os.path.join(base, f'it-{tip[:10]}', 'new.txt')))
        git(self.repo, 'branch', '-f', 'ow/it', tip)
        git(self.repo, 'worktree', 'add', '-q', wt, 'ow/it')
        code, out, err = self.call()
        self.assertEqual(code, 0, out + err)
        self.assertTrue(os.path.isfile(os.path.join(base, f'it-{tip[:10]}-2', 'status.txt')))
        self.assertEqual(len(self.index_rows()), 3)

    def test_two_merges_share_one_index_with_one_header(self):
        self.item('one')
        self.item('two')
        self.assertEqual(self.call(branch='ow/one')[0], 0)
        self.assertEqual(self.call(branch='ow/two')[0], 0)
        rows = self.index_rows()
        self.assertEqual([r[1] for r in rows], ['branch', 'ow/one', 'ow/two'])
        self.assertTrue(all(len(r) == 10 for r in rows))

    def test_concurrent_appends_do_not_interleave(self):
        index = os.path.join(self.tmp, 'index.tsv')
        code = textwrap.dedent(f'''
            import sys; sys.path.insert(0, {HERE!r})
            import remove_merged
            for n in range(300):
                remove_merged.append_index({index!r}, [sys.argv[1]] * 9 + ['x' * 3000])
        ''')
        ps = [subprocess.Popen([sys.executable, '-B', '-c', code, tag], stdin=subprocess.DEVNULL) for tag in 'ab']
        self.assertEqual([p.wait(timeout=60) for p in ps], [0, 0])
        with open(index) as f:
            lines = f.read().split('\n')
        self.assertEqual(lines[0], '\t'.join(remove_merged.COLUMNS))
        self.assertEqual(lines[-1], '')
        body = lines[1:-1]
        self.assertEqual(len(body), 600)
        for line in body:
            self.assertIn(line, ('\t'.join(['a'] * 9 + ['x' * 3000]), '\t'.join(['b'] * 9 + ['x' * 3000])))

    def test_a_tab_or_newline_in_a_path_is_escaped_in_the_index(self):
        name = 'it\tx\ny'
        wt = os.path.join(self.wts, name)
        git(self.repo, 'worktree', 'add', '-q', '-b', 'ow/it', wt, 'main')
        self.write(wt, 'f.txt', 'f\n')
        code, out, err = self.call()
        self.assertEqual(code, 0, out + err)
        rows = self.index_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[1]), 10)
        self.assertEqual(rows[1][3], wt.replace('\t', '\\t').replace('\n', '\\n'))
        self.assertTrue(os.path.isfile(os.path.join(self.archive, 'repo', name, 'f.txt')))

    def test_json_prints_one_object_with_worktrunk_field_names(self):
        wt = self.item()
        code, res = self.call_json()
        self.assertEqual(code, 0)
        self.assertEqual((res['branch'], res['path'], res['branch_outcome'], res['worktree_outcome'],
                          res['archive_dir']),
                         ('ow/it', wt, 'deleted', 'removed', os.path.join(self.archive, 'repo', 'it')))


class DryRunTest(RemoveMergedBase):
    def dry(self, want_code, wt_line, br_line, **kw):
        before = self.state()
        code, out, err = self.call('--dry-run', **kw)
        self.assertEqual(code, want_code, out + err)
        self.assertEqual(self.state(), before)
        lines = out.splitlines()
        self.assertTrue(lines and all(x.startswith('dry run: ') for x in lines), out)
        self.assertIn(f'dry run: worktree {wt_line}', out)
        self.assertIn(f'dry run: branch {br_line}', out)
        return out

    def test_dry_run_changes_nothing_on_each_outcome(self):
        wt = self.item()
        self.write(wt, 'left.txt', 'left\n')
        repo2 = os.path.join(wt, 'nest')
        os.makedirs(repo2)
        git(repo2, 'init', '-q')
        pid = self.orphan(wt)
        out = self.dry(0, f'removed {wt}', 'deleted ow/it')
        self.assertIn(f"dry run: archived {os.path.join(self.archive, 'repo', 'it')} (2 untracked items)", out)
        self.assertIn('dry run: skipped nest/.git', out)
        self.assertRegex(out, rf'dry run: stopped {pid} \S*sleep')
        self.assertTrue(remove_merged.sweep.alive(pid))
        os.kill(pid, signal.SIGKILL)
        other = os.path.join(self.tmp, 'second')
        git(self.repo, 'worktree', 'add', '-q', '--force', other, 'ow/it')
        self.dry(1, f'removed {wt}', 'retained_checked_out ow/it')
        git(self.repo, 'worktree', 'remove', '--force', other)
        git(self.repo, 'worktree', 'lock', wt)
        self.dry(1, f'retained_locked {wt}', 'not_attempted ow/it')
        git(self.repo, 'worktree', 'unlock', wt)
        p = subprocess.Popen(['sleep', '300'], cwd=wt, stdin=subprocess.DEVNULL)
        self.procs.append(p.pid)
        self.dry(1, f'retained_in_use {wt}', 'not_attempted ow/it')
        p.kill()
        p.wait()
        secret = self.write(wt, 'z.txt', 'z\n')
        os.chmod(secret, 0)
        self.dry(0, f'removed {wt}', 'deleted ow/it')
        os.chmod(secret, 0o644)
        shutil.rmtree(wt)
        self.dry(0, f'already_gone {wt}', 'deleted ow/it')
        git(self.repo, 'worktree', 'prune')
        self.dry(0, 'none -', 'deleted ow/it')
        self.item('late', merged=False)
        self.dry(1, 'not_attempted', 'retained_unmerged ow/late', branch='ow/late')

    def test_the_cli_defaults_the_archive_under_home_and_help_exits_0(self):
        self.item()
        env = {**os.environ, 'HOME': self.tmp, 'PYTHONDONTWRITEBYTECODE': '1'}
        p = subprocess.run([sys.executable, '-B', SCRIPT, '--help'], capture_output=True, text=True, env=env,
                           stdin=subprocess.DEVNULL)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('--dry-run', p.stdout)
        p = subprocess.run([sys.executable, '-B', SCRIPT, '--repo', self.repo, '--branch', 'ow/it', '--dry-run',
                            '--json'], capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
        self.assertEqual(p.returncode, 0, p.stderr)
        res = json.loads(p.stdout)
        self.assertEqual(res['archive_dir'], os.path.join(self.tmp, '.local', 'state', 'orchestrator-workers',
                                                          '_archive', 'worktrees', 'repo', 'it'))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, '.local')))
        p = subprocess.run([sys.executable, '-B', SCRIPT, '--repo', self.repo, '--branch', 'main'],
                           capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
        self.assertEqual(p.returncode, 2)
        self.assertIn('nothing changed', p.stderr)


if __name__ == '__main__':
    unittest.main()
