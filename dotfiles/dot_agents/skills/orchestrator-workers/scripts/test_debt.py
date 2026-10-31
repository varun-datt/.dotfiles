import datetime, os, subprocess, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import debt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, 'debt.py')
FIXTURE = os.path.join(HERE, 'fixtures', 'debt-plan.md')
TODAY = datetime.date.today().isoformat()


class DebtTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = os.path.join(self.tmp.name, 'repo')
        os.makedirs(os.path.join(self.repo, 'src', 'host'))
        open(os.path.join(self.repo, 'src', 'host', 'a.ts'), 'w').close()
        self.reg = os.path.join(self.repo, 'docs', 'tech-debt.md')

    def cli(self, *args, ok=True):
        p = subprocess.run([sys.executable, '-B', SCRIPT, *args], capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if ok:
            self.assertEqual(p.returncode, 0, p.stderr)
        else:
            self.assertNotEqual(p.returncode, 0, p.stdout)
            self.assertEqual(p.stdout, '')
            self.assertEqual(len(p.stderr.splitlines()), 1, p.stderr)
        return p

    def add(self, file='src/host/a.ts', scenario='a stale cache shows old names', ok=True, grade='Minor', **kw):
        args = ['add', self.repo, '--area', kw.get('area', 'host-io'), '--grade', grade, '--file', file,
                '--scenario', scenario, '--source', kw.get('source', 'item-review'), '--minutes', str(kw.get('minutes', 10))]
        return self.cli(*args, ok=ok)

    def text(self):
        with open(self.reg, encoding='utf-8') as f:
            return f.read()

    def rows(self, *flags):
        return self.cli('list', self.repo, *flags).stdout.splitlines()

    # MUST 1
    def test_add_creates_docs_and_file_with_header(self):
        self.assertFalse(os.path.exists(os.path.join(self.repo, 'docs')))
        self.assertIn('added TD-1', self.add().stdout)
        text = self.text()
        self.assertTrue(text.startswith('# Tech debt\n'))
        self.assertIn('| Id | Date | Area | Grade | File | Scenario | Source | Minutes | Status |', text)
        self.assertIn(f'| TD-1 | {TODAY} | host-io | Minor | src/host/a.ts | a stale cache shows old names | item-review | 10 | open |', text)

    def test_two_adds_get_consecutive_ids(self):
        self.add()
        self.add(scenario='second one')
        self.assertEqual([r.split('|')[1].strip() for r in self.rows()], ['TD-1', 'TD-2'])

    def test_ids_are_never_reused_after_a_row_is_deleted_by_hand(self):
        self.add()
        self.add(scenario='second one')
        kept = [line for line in self.text().splitlines() if not line.startswith('| TD-2 ')]
        with open(self.reg, 'w', encoding='utf-8') as f:
            f.write('\n'.join(kept) + '\n')
        self.assertIn('added TD-3', self.add(scenario='third').stdout)
        self.assertEqual([r.split('|')[1].strip() for r in self.rows()], ['TD-1', 'TD-3'])

    def test_backticks_in_a_scenario_round_trip(self):
        self.add(scenario='a query that starts with `--` is read as an option')
        self.assertIn('`--` is read as an option', self.rows()[0])
        self.assertIn('`--` is read as an option', self.cli('for-files', self.repo, 'src').stdout)

    def test_bad_input_is_refused_and_leaves_the_file_unchanged(self):
        self.add()
        before = self.text()
        outside = os.path.join(self.tmp.name, 'outside.ts')
        for kw in [dict(scenario=''), dict(scenario='   '), dict(scenario='two\nlines'), dict(scenario='a | b'),
                   dict(file=outside), dict(file='../outside.ts'), dict(file='src/../../outside.ts'), dict(file='.'),
                   dict(file='src/a|b.ts')]:
            self.add(ok=False, **kw)
            self.assertEqual(self.text(), before, kw)
        for grade in ('Blocker', 'minor'):
            args = ['add', self.repo, '--area', 'a', '--grade', grade, '--file', 'a.ts', '--scenario', 's', '--source', 'r', '--minutes', '5']
            p = subprocess.run([sys.executable, '-B', SCRIPT, *args], capture_output=True, text=True, stdin=subprocess.DEVNULL)
            self.assertNotEqual(p.returncode, 0, grade)
            self.assertEqual(self.text(), before, grade)

    def test_a_path_that_climbs_and_comes_back_is_stored_normalised(self):
        self.add(file='./src/../src/host/a.ts')
        self.assertIn('| src/host/a.ts |', self.rows()[0])

    # MUST 2
    def test_list_open_all_and_close_round_trip(self):
        self.add()
        self.add(scenario='second one')
        self.add(scenario='third one')
        before = self.text().splitlines()
        self.assertIn('closed TD-2', self.cli('close', self.repo, 'TD-2', '--reason', "won't fix: rarely touched").stdout)
        after = self.text().splitlines()
        changed = [(b, a) for b, a in zip(before, after) if b != a]
        self.assertEqual(len(before), len(after))
        self.assertEqual(len(changed), 1, changed)
        self.assertTrue(changed[0][1].endswith(f"| closed {TODAY}: won't fix: rarely touched |"))
        self.assertEqual([r.split('|')[1].strip() for r in self.rows()], ['TD-1', 'TD-3'])
        self.assertEqual(self.rows('--open'), self.rows())
        self.assertEqual([r.split('|')[1].strip() for r in self.rows('--all')], ['TD-1', 'TD-2', 'TD-3'])

    def test_close_refuses_unknown_and_already_closed_ids(self):
        self.add()
        self.cli('close', self.repo, 'TD-1', '--reason', 'fixed in item x')
        before = self.text()
        for args in [('TD-1', '--reason', 'again'), ('TD-9', '--reason', 'x'), ('TD-1x', '--reason', 'x'), ('TD-1', '--reason', 'a|b')]:
            self.cli('close', self.repo, *args, ok=False)
            self.assertEqual(self.text(), before, args)

    def test_close_without_a_register_is_refused(self):
        self.cli('close', self.repo, 'TD-1', '--reason', 'x', ok=False)
        self.assertFalse(os.path.exists(self.reg))

    def test_hand_written_text_outside_the_table_is_kept(self):
        os.makedirs(os.path.dirname(self.reg))
        hand = ('# Our debt\n\nA note above, with a | pipe.\n\n'
                '| Id | Date | Area | Grade | File | Scenario | Source | Minutes | Status |\n'
                '| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n'
                '| TD-4 | 2026-01-01 | ui | Major | src/host/a.ts | old row | r1 | 5 | open |\n'
                '\n## Notes below\n\n- keep me\n')
        with open(self.reg, 'w', encoding='utf-8') as f:
            f.write(hand)
        self.assertIn('added TD-5', self.add().stdout)
        self.cli('close', self.repo, 'TD-4', '--reason', 'done')
        text = self.text()
        self.assertTrue(text.startswith('# Our debt\n\nA note above, with a | pipe.\n\n| Id |'))
        self.assertTrue(text.endswith('\n## Notes below\n\n- keep me\n'))
        self.assertIn('| TD-4 | 2026-01-01 | ui | Major | src/host/a.ts | old row | r1 | 5 | closed', text)

    def test_a_broken_row_is_refused_not_rewritten(self):
        os.makedirs(os.path.dirname(self.reg))
        hand = ('| Id | Date | Area | Grade | File | Scenario | Source | Minutes | Status |\n| --- |\n'
                '| TD-1 | 2026-01-01 | ui | Minor | a.ts | a | b | extra | 5 | open |\n')
        with open(self.reg, 'w', encoding='utf-8') as f:
            f.write(hand)
        self.add(ok=False)
        self.assertEqual(self.text(), hand)

    # MUST 3
    def test_for_files_matches_files_and_folders(self):
        self.add(file='src/host/a.ts', scenario='on a')
        self.add(file='src/hostile.ts', scenario='on hostile')
        self.add(file='docs/x.md', scenario='on docs')
        self.add(file='src/host/b.ts', scenario='closed one')
        self.cli('close', self.repo, 'TD-4', '--reason', 'fixed')
        ids = lambda *paths: [line.split()[1] for line in self.cli('for-files', self.repo, *paths).stdout.splitlines()]
        self.assertEqual(ids('./src/host/a.ts'), ['TD-1'])
        self.assertEqual(ids('src/host'), ['TD-1'])
        self.assertEqual(ids('src/host/'), ['TD-1'])
        self.assertEqual(ids('src'), ['TD-1', 'TD-2'])
        self.assertEqual(ids('src/host', 'docs/'), ['TD-1', 'TD-3'])
        self.assertEqual(ids(os.path.join(self.repo, 'src', 'host', 'a.ts')), ['TD-1'])
        line = self.cli('for-files', self.repo, 'src/host/a.ts').stdout
        self.assertTrue(line.startswith('- TD-1 (Minor, host-io, about 10 min) `src/host/a.ts`: on a'), line)

    def test_for_files_with_no_match_prints_nothing(self):
        self.assertEqual(self.cli('for-files', self.repo, 'src').stdout, '')
        self.add()
        self.assertEqual(self.cli('for-files', self.repo, 'lib', 'src/host/a.tsx').stdout, '')

    def test_for_files_flags_a_deleted_file(self):
        self.add(file='src/host/gone.ts')
        self.add(file='src/host/a.ts')
        lines = self.cli('for-files', self.repo, 'src/host').stdout.splitlines()
        self.assertIn('no longer exists', lines[0])
        self.assertNotIn('no longer exists', lines[1])

    # MUST 4
    def write_rows(self, *dates):
        os.makedirs(os.path.dirname(self.reg), exist_ok=True)
        rows = ''.join(f'| TD-{i} | {d} | ui | Minor | a.ts | s{i} | r | 5 | open |\n' for i, d in enumerate(dates, 1))
        with open(self.reg, 'w', encoding='utf-8') as f:
            f.write('| Id | Date | Area | Grade | File | Scenario | Source | Minutes | Status |\n| --- |\n' + rows)

    def runs(self, *lines):
        path = os.path.join(self.tmp.name, 'runs.txt')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')
        return path

    def test_stale_counts_runs_dated_after_the_row(self):
        self.write_rows('2026-01-01', '2026-01-03', '2026-01-04')
        runs = self.runs('2026-01-01 run-a', '2026-01-02 run-b', 'not a run line', '2026-01-03 run-c', '2026-01-04 run-d')
        out = self.cli('stale', self.repo, '--runs', runs).stdout.splitlines()
        self.assertEqual([line.split()[0] for line in out], ['TD-1'])
        self.assertIn('3 runs since 2026-01-01', out[0])
        self.assertEqual(self.cli('stale', self.repo, '--runs', runs, '--threshold', '1').stdout.split('\n')[1].split()[0], 'TD-2')

    def test_stale_skips_closed_rows_and_needs_a_readable_runs_file(self):
        self.write_rows('2026-01-01')
        self.cli('close', self.repo, 'TD-1', '--reason', 'x')
        runs = self.runs('2026-02-01', '2026-02-02', '2026-02-03')
        self.assertEqual(self.cli('stale', self.repo, '--runs', runs).stdout, '')
        self.cli('stale', self.repo, '--runs', os.path.join(self.tmp.name, 'none'), ok=False)

    # MUST 5
    def test_import_plan_dry_run_finds_each_passage_shape(self):
        out = self.cli('import-plan', FIXTURE, '--dry-run', '--counts').stdout.splitlines()
        self.assertEqual([(line.split()[1], line.split()[-2]) for line in out], [('1', '3'), ('2', '2'), ('3', '1'), ('4', '2'), ('5', '1'), ('?', '2')])
        rows = self.cli('import-plan', FIXTURE, '--dry-run').stdout.splitlines()
        gaps = [r.split(' | ', 4)[4] for r in rows]
        self.assertEqual(gaps[0], 'a widget renamed during a search keeps its old name')
        self.assertEqual(gaps[2], 'a query that starts with `--` is read as an option')
        self.assertEqual(gaps[3], 'a root set by hand with a trailing `/` or `/.` is still followed (fixed later in 1111111; reverted in 2222222)')
        self.assertEqual(gaps[4], 'a folder swapped for a link between the check and the read')
        self.assertEqual(gaps[6], 'an attachment is read whole with no binary check')
        self.assertEqual(gaps[7], 'a literal `>>>; <<<` in an attachment becomes `>>`')
        self.assertEqual(gaps[8], 'a thread on a deleted first line shows a stray number')
        self.assertTrue(all('area ? | grade ? | file ?' in r for r in rows))

    def test_import_plan_writes_nothing_and_needs_dry_run(self):
        before = sorted(os.listdir(os.path.dirname(FIXTURE)))
        self.cli('import-plan', FIXTURE, '--dry-run')
        self.assertEqual(sorted(os.listdir(os.path.dirname(FIXTURE))), before)
        subprocess.run([sys.executable, '-B', SCRIPT, 'import-plan', FIXTURE], capture_output=True, stdin=subprocess.DEVNULL, check=False)
        self.assertNotEqual(subprocess.run([sys.executable, '-B', SCRIPT, 'import-plan', FIXTURE], capture_output=True, stdin=subprocess.DEVNULL).returncode, 0)

    def test_import_plan_with_no_known_gaps_prints_nothing(self):
        plan = os.path.join(self.tmp.name, 'PLAN.md')
        with open(plan, 'w', encoding='utf-8') as f:
            f.write('# Plan\n\n1. An item with no gaps.\n2. Another, merged.\n')
        self.assertEqual(self.cli('import-plan', plan, '--dry-run').stdout, '')

    # MUST 6
    def test_the_dotfiles_register_parses(self):
        root = os.path.abspath(os.path.join(HERE, *(['..'] * 5)))
        with open(os.path.join(root, debt.REGISTER), encoding='utf-8') as f:
            debt.Register(f.read())

    def test_help_runs(self):
        self.assertIn('tech-debt', self.cli('--help').stdout)


if __name__ == '__main__':
    unittest.main()
