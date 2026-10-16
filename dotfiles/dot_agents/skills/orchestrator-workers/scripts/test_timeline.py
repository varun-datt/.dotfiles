import json, os, re, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TIMELINE = os.path.join(HERE, 'timeline.py')
STATE = os.path.join(HERE, 'state.py')
MINE = os.path.join(HERE, 'mine.py')


def round_file(run, name, start, minutes, nano=None, ended=True):
    events = [{'type': 'user.message', 'data': {'content': 'go', 'responsesReasoning': {'model': 'm1', 'effort': 'high'}},
               'timestamp': f'{start}:00.000Z'}]
    if nano is not None:
        events.append({'type': 'session.usage_checkpoint', 'data': {'totalNanoAiu': nano}, 'timestamp': f'{start}:30.000Z'})
    if ended:
        events.append({'type': 'result', 'exitCode': 0, 'sessionId': 's-' + name, 'timestamp': f'{start}:59.000Z'})
    with open(os.path.join(run, name + '.jsonl'), 'w') as f:
        f.write(''.join(json.dumps(e) + '\n' for e in events))
    import datetime
    t = datetime.datetime.fromisoformat(start + ':00+00:00')
    with open(os.path.join(run, name + '.start'), 'w') as f:
        f.write(str(int(t.timestamp())))


class TimelineTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name
        self.archive = os.path.join(self.tmp, 'archive')
        os.makedirs(self.archive)
        self.env = {k: v for k, v in os.environ.items() if k not in ('OW_RUN_DIR', 'OW_PREFIX', 'OW_REGISTRY')}
        self.env.update(OW_REGISTRY=os.path.join(self.tmp, 'registry.jsonl'), PYTHONDONTWRITEBYTECODE='1', TZ='UTC')
        self.repo = os.path.join(self.tmp, 'repo')
        git = ['git', '-c', 'user.name=t', '-c', 'user.email=t@example.invalid', '-C', self.repo]
        subprocess.run(['git', 'init', '-q', '-b', 'main', self.repo], check=True)
        subprocess.run(git + ['commit', '-q', '--allow-empty', '-m', 'root'], check=True)
        subprocess.run(git + ['checkout', '-q', '-b', 'ow/alpha'], check=True)
        subprocess.run(git + ['commit', '-q', '--allow-empty', '-m', 'work'], check=True)
        subprocess.run(git + ['checkout', '-q', 'main'], check=True)
        subprocess.run(git + ['merge', '-q', '--no-ff', '-m', "Merge branch 'ow/alpha'", 'ow/alpha'], check=True)

    def run_cli(self, script, *args, code=0):
        p = subprocess.run([sys.executable, script, *args], capture_output=True, text=True, env=self.env)
        self.assertEqual(p.returncode, code, p.stdout + p.stderr)
        return p

    def make_run(self, name, title, archive=True, rounds=()):
        run = os.path.join(self.tmp, name)
        args = ['--run', run, 'init', '--title', title, '--repo', self.repo]
        if archive:
            args += ['--archive', self.archive]
        self.run_cli(STATE, *args)
        for r in rounds:
            round_file(run, *r)
        return run

    def two_runs(self):
        a = self.make_run('run-a', 'First run', rounds=[('alpha', '2026-10-01T10:00', 20, 5e11),
                                                         ('alpha-review', '2026-10-01T11:00', 5, 2e11)])
        b = self.make_run('run-b', 'Second run', rounds=[('beta', '2026-10-02T09:00', 10, 3e11),
                                                          ('gamma', '2026-10-02T12:00', 10, None)])
        return a, b

    def data(self, text):
        return json.loads(re.search(r'var D=(\{.*?\});\n', text).group(1).replace('<\\/', '</'))

    def test_export_refuses_without_an_archive_folder(self):
        run = self.make_run('run-x', 'No archive', archive=False, rounds=[('alpha', '2026-10-01T10:00', 5, 1e11)])
        p = self.run_cli(TIMELINE, '--run', run, '--export', code=2)
        self.assertEqual(len(p.stderr.strip().splitlines()), 1)
        self.assertIn('init --archive', p.stderr)
        self.assertEqual(os.listdir(self.archive), [])

    def test_export_joins_every_run_naming_the_same_archive(self):
        a, b = self.two_runs()
        self.make_run('run-other', 'Elsewhere', archive=False, rounds=[('delta', '2026-10-02T09:00', 5, 1e11)])
        p = self.run_cli(TIMELINE, '--run', a, '--export')
        self.assertEqual(len(p.stdout.strip().splitlines()), 2)
        self.assertEqual(sorted(os.listdir(self.archive)), ['spend-by-day.md', 'timeline.html'])
        with open(os.path.join(self.archive, 'timeline.html'), encoding='utf-8') as f:
            d = self.data(f.read())
        self.assertEqual(d['items'], ['alpha', 'beta', 'gamma'])
        self.assertEqual(d['runs'], 2)
        self.assertEqual({r['run'] for r in d['rounds']}, {'First run', 'Second run'})
        self.assertEqual([m['item'] for m in d['merges']], ['alpha'])
        self.assertEqual(d['creditTotal'], 1000.0)
        self.assertEqual(d['unknownTotal'], 1)

    def test_spend_rows_come_from_mine_and_unknown_is_never_zero(self):
        a, b = self.two_runs()
        self.run_cli(TIMELINE, '--run', b, '--export')
        with open(os.path.join(self.archive, 'spend-by-day.md'), encoding='utf-8') as f:
            rows = [line.split(' | ') for line in f if re.match(r'\| \d{4}-', line)]
        self.assertEqual([r[0] for r in rows], ['| 2026-10-02', '| 2026-10-01'])
        mined = {}
        for run in (a, b):
            for d in json.loads(self.run_cli(MINE, run, '--json').stdout)['days']:
                mined[d['day']] = d
        for r in rows:
            d = mined[r[0][2:]]
            self.assertTrue(r[1].startswith(f"{d['credits']:,.1f}"), r)
            self.assertTrue(r[2].startswith(f"${d['credits'] / 100:,.2f}"), r)
            self.assertEqual(int(r[3]), d['rounds'])
        self.assertIn('unknown (1 round)', rows[0][1])
        self.assertIn('build 300.0 + unknown (1 round)', rows[0][4])
        self.assertIn('build 500.0; review 200.0', rows[1][4])

    def test_a_day_with_only_unknown_credits_says_unknown(self):
        run = self.make_run('run-u', 'Unknown', rounds=[('alpha', '2026-10-03T10:00', 5, None)])
        self.run_cli(TIMELINE, '--run', run, '--export')
        with open(os.path.join(self.archive, 'spend-by-day.md'), encoding='utf-8') as f:
            row = next(line for line in f if line.startswith('| 2026-10-03'))
        self.assertEqual(row.split(' | ')[1:3], ['unknown', 'unknown'])

    def test_second_export_is_identical_and_touches_nothing_else(self):
        a, _ = self.two_runs()
        keep = os.path.join(self.archive, 'notes.md')
        with open(keep, 'w') as f:
            f.write('mine\n')
        self.run_cli(TIMELINE, '--run', a, '--export')
        first = self.snapshot()
        self.run_cli(TIMELINE, '--run', a, '--export')
        second = self.snapshot()
        self.assertEqual(first, second)
        self.assertEqual(second['notes.md'], b'mine\n')

    def snapshot(self):
        out = {}
        for n in os.listdir(self.archive):
            with open(os.path.join(self.archive, n), 'rb') as f:
                out[n] = f.read()
        return out

    def page(self):
        a, _ = self.two_runs()
        out = os.path.join(self.tmp, 'one.html')
        self.run_cli(TIMELINE, '--run', a, '--out', out)
        with open(out, encoding='utf-8') as f:
            return f.read()

    def test_theme_listener_takes_any_type_and_ignores_malformed(self):
        text = self.page()
        listener = re.search(r'window\.addEventListener\("message",function\(e\)\{(.*?)\n\}\);', text, re.S).group(1)
        self.assertNotIn('.type', listener)
        guard = listener.split('return;')[0]
        self.assertIn('typeof d!=="object"', guard)
        self.assertIn('d.theme!=="light"&&d.theme!=="dark"', guard)
        self.assertIn('prefers-color-scheme: dark', text)

    def test_page_loads_nothing_from_the_network_and_names_one_run(self):
        text = self.page()
        self.assertNotRegex(text, r'https?://')
        self.assertNotRegex(text, r'<(script|link|img)[^>]+(src|href)=')
        d = self.data(text)
        self.assertEqual(d['items'], ['alpha'])
        self.assertIn('UTC', d['zone'])
        self.assertIn('UTC', text.split('<p class="sub">')[1].split('</p>')[0])

    def test_sleep_unknown_off_macos_is_never_none(self):
        sys.path.insert(0, HERE)
        import timeline
        from unittest import mock
        with mock.patch.object(timeline.sys, 'platform', 'linux'):
            self.assertIsNone(timeline.sleep_gaps(None, None))
        self.assertIn('Machine sleep is unknown', self.page())


if __name__ == '__main__':
    unittest.main()
