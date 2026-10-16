import json, os, subprocess, sys, tempfile, time, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import state  # noqa: E402

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'state.py')


class StateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run_dir = os.path.join(self.tmp.name, 'run')
        self.reg = os.path.join(self.tmp.name, 'reg', 'registry.jsonl')
        self.env = {**os.environ, 'OW_RUN_DIR': self.run_dir, 'OW_REGISTRY': self.reg, 'OW_PREFIX': 'ow-'}

    def cli(self, *args, ok=True):
        p = subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, env=self.env)
        if ok:
            self.assertEqual(p.returncode, 0, p.stderr)
        else:
            self.assertNotEqual(p.returncode, 0, p.stdout)
        return p

    def doc(self):
        with open(os.path.join(self.run_dir, 'orchestrator.json'), encoding='utf-8') as f:
            return json.load(f)

    def registry(self):
        with open(self.reg, encoding='utf-8') as f:
            return [json.loads(line) for line in f if line.strip()]

    def test_every_command_prints_exactly_one_line(self):
        runs = [
            ('init', '--title', 'Docs build', '--client', 'cli', '--session-id', 'abcdef12-3456'),
            ('item', 'docs', '--kind', 'build', '--gate', 'npm  test', '--gate', 'make lint', '--title', 'Docs\nbuild'),
            ('queue', 'docs-2', '--after', 'docs', '--title', 'Second'),
            ('ask', 'Q-7', '--kind', 'decision', '--item', 'docs', '--question', 'Which\nscope?', '--option', 'per user', '--option', 'per repo', '--recommend', 'B', '--blocks', 'docs'),
            ('answered', 'Q-7', 'B', 'per repo'),
            ('queue', 'docs-2', '--remove'),
            ('init',),
        ]
        for args in runs:
            out = self.cli(*args).stdout
            self.assertEqual(len(out.splitlines()), 1, (args, out))
            self.assertTrue(out.endswith('\n'), args)

    def test_errors_are_one_line_on_stderr_and_nonzero(self):
        self.cli('init')
        for args in [('answered', 'nope', 'x'), ('ask', 'Q-1', '--kind', 'decision', '--question', 'q', '--recommend', 'C'), ('item', '../escape')]:
            p = self.cli(*args, ok=False)
            self.assertEqual(p.stdout, '')
            self.assertEqual(len(p.stderr.splitlines()), 1, (args, p.stderr))

    def test_init_creates_the_file_and_registers_once(self):
        self.cli('init', '--title', 'Docs build', '--session-id', 'abcdef12-3456')
        self.assertIn('registered', self.cli('init', '--title', 'Docs build').stdout)
        self.assertIn('already registered', self.cli('init').stdout)
        os.makedirs(os.path.join(self.tmp.name, 'link'), exist_ok=True)
        alias = os.path.join(self.tmp.name, 'link', 'run')
        os.symlink(self.run_dir, alias)
        self.cli('--run', alias, 'init')
        reg = self.registry()
        self.assertEqual(len(reg), 1)
        self.assertEqual(reg[0], {'dir': os.path.realpath(self.run_dir), 'prefix': 'ow-', 'title': 'Docs build', 'sessionId': 'abcdef12-3456'})
        d = self.doc()
        self.assertEqual(d['schema'], 1)
        self.assertEqual(d['orchestrator']['title'], 'Docs build')
        self.assertEqual((d['items'], d['queue'], d['asks'], d['risks']), ({}, [], [], []))

    def test_init_without_archive_stores_none_and_with_archive_an_absolute_existing_folder(self):
        self.cli('init', '--title', 'T')
        self.assertIsNone(self.doc()['orchestrator']['archive'])
        self.assertIn('--archive', self.cli('init', '--archive', os.path.join(self.tmp.name, 'missing'), ok=False).stderr)
        os.makedirs(os.path.join(self.tmp.name, 'arch'))
        p = subprocess.run([sys.executable, SCRIPT, 'init', '--archive', 'arch'], capture_output=True, text=True, env=self.env, cwd=self.tmp.name)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.doc()['orchestrator']['archive'], os.path.join(os.path.realpath(self.tmp.name), 'arch'))

    def test_setting_archive_on_a_registered_run_keeps_its_records_and_prefix(self):
        self.env['OW_PREFIX'] = 'proj-'
        self.cli('init', '--title', 'T', '--repo', '/r')
        self.cli('item', 'a', '--kind', 'build')
        self.cli('queue', 'b')
        self.cli('ask', 'q1', '--kind', 'decision', '--question', 'Which?')
        del self.env['OW_PREFIX']
        os.makedirs(os.path.join(self.tmp.name, 'arch'))
        self.assertIn('was already registered', self.cli('init', '--archive', os.path.join(self.tmp.name, 'arch')).stdout)
        d = self.doc()
        self.assertEqual(list(d['items']), ['a'])
        self.assertEqual([q['item'] for q in d['queue']], ['b'])
        self.assertEqual([x['id'] for x in d['asks']], ['q1'])
        self.assertEqual((d['orchestrator']['title'], d['orchestrator']['repo'], d['orchestrator']['prefix']), ('T', '/r', 'proj-'))
        self.assertTrue(d['orchestrator']['archive'].endswith('arch'))
        self.assertEqual(len(self.registry()), 1)

    def test_init_keeps_other_registry_lines_including_bad_ones(self):
        os.makedirs(os.path.dirname(self.reg))
        with open(self.reg, 'w', encoding='utf-8') as f:
            f.write('{"dir": "/elsewhere", "prefix": "x-", "title": null, "sessionId": null}\nnot json')
        self.cli('init')
        with open(self.reg, encoding='utf-8') as f:
            lines = f.read().splitlines()
        self.assertEqual(lines[:2], ['{"dir": "/elsewhere", "prefix": "x-", "title": null, "sessionId": null}', 'not json'])
        self.assertEqual(json.loads(lines[2])['dir'], os.path.realpath(self.run_dir))
        self.assertEqual(len(lines), 3)

    def test_init_refuses_a_symlinked_registry_and_a_bad_prefix(self):
        os.makedirs(os.path.dirname(self.reg))
        real = os.path.join(self.tmp.name, 'real.jsonl')
        open(real, 'w').close()
        os.symlink(real, self.reg)
        self.assertIn('not a regular file', self.cli('init', ok=False).stderr)
        self.env['OW_PREFIX'] = 'bad prefix'
        self.assertIn('OW_PREFIX', self.cli('init', ok=False).stderr)

    def test_writes_are_atomic_and_leave_no_temporary_file(self):
        self.cli('init')
        before = self.doc()
        with mock.patch.object(state.os, 'replace', side_effect=OSError('disk gone')), mock.patch('sys.stderr'):
            self.assertEqual(state.main(['--run', self.run_dir, 'item', 'docs', '--kind', 'build']), 1)
        self.assertEqual(self.doc(), before)
        left = [n for n in os.listdir(self.run_dir) if n.endswith('.tmp')]
        self.assertEqual(left, [])

    def test_writes_fsync_then_rename(self):
        self.cli('init')
        calls = []
        real_fsync, real_replace = os.fsync, os.replace
        with mock.patch.object(state.os, 'fsync', side_effect=lambda fd: (calls.append('fsync'), real_fsync(fd))[1]), \
             mock.patch.object(state.os, 'replace', side_effect=lambda a, b: (calls.append('replace'), real_replace(a, b))[1]):
            with mock.patch('sys.stdout'):
                state.main(['--run', self.run_dir, 'item', 'docs', '--kind', 'build'])
        self.assertEqual(calls, ['fsync', 'replace', 'fsync'])

    def test_refuses_to_overwrite_a_file_it_cannot_read(self):
        self.cli('init')
        with open(os.path.join(self.run_dir, 'orchestrator.json'), 'w') as f:
            f.write('{broken')
        self.assertIn('could not be read', self.cli('item', 'docs', ok=False).stderr)
        with open(os.path.join(self.run_dir, 'orchestrator.json')) as f:
            self.assertEqual(f.read(), '{broken')

    def test_refuses_to_drop_a_record_list_of_the_wrong_type(self):
        self.cli('init')
        target = os.path.join(self.run_dir, 'orchestrator.json')
        with open(target, 'w') as f:
            f.write('{"schema": 1, "asks": {"Q-1": "kept"}}')
        self.assertIn('asks in the state file', self.cli('item', 'docs', ok=False).stderr)
        with open(target) as f:
            self.assertEqual(json.load(f)['asks'], {'Q-1': 'kept'})

    def test_commands_other_than_init_need_the_run_folder(self):
        self.assertIn('state.py init', self.cli('item', 'docs', ok=False).stderr)
        self.assertFalse(os.path.exists(self.run_dir))

    def test_item_upserts(self):
        self.cli('init')
        self.cli('item', 'docs', '--kind', 'research', '--gate', 'npm   run  check')
        self.cli('item', 'docs', '--title', 'Docs')
        self.assertEqual(self.doc()['items']['docs'], {'kind': 'research', 'gates': ['npm run check'], 'title': 'Docs'})

    def test_queue_adds_replaces_in_place_and_removes(self):
        self.cli('init')
        self.cli('queue', 'a', '--title', 'A')
        self.cli('queue', 'b', '--after', 'a')
        self.cli('queue', 'a', '--after', 'x')
        self.assertEqual(self.doc()['queue'], [{'item': 'a', 'title': 'A', 'after': ['x']}, {'item': 'b', 'title': None, 'after': ['a']}])
        self.assertIn('removed', self.cli('queue', 'a', '--remove').stdout)
        self.assertEqual([q['item'] for q in self.doc()['queue']], ['b'])

    def test_ask_then_answered_leaves_the_open_list(self):
        self.cli('init')
        self.cli('ask', 'Q-7', '--kind', 'decision', '--question', 'Scope?', '--option', 'per user', '--option', 'per repo', '--recommend', 'B', '--blocks', 'docs', '--context', 'https://example.org/q7')
        self.cli('ask', 'S-2', '--kind', 'sign-in', '--question', 'Sign in to the registry')
        ask = self.doc()['asks'][0]
        self.assertEqual(ask['options'], [{'key': 'A', 'text': 'per user'}, {'key': 'B', 'text': 'per repo'}])
        self.assertEqual((ask['recommendation'], ask['blocks'], ask['answeredAt']), ('B', ['docs'], None))
        out = self.cli('answered', 'Q-7', 'B').stdout
        self.assertIn('1 open', out)
        asks = {a['id']: a for a in self.doc()['asks']}
        self.assertEqual(asks['Q-7']['answer'], 'B')
        self.assertTrue(asks['Q-7']['answeredAt'])
        self.assertIsNone(asks['S-2']['answeredAt'])

    def test_reasking_an_open_ask_updates_it_and_keeps_asked_at(self):
        self.cli('init')
        self.cli('ask', 'Q-1', '--kind', 'steering', '--question', 'First')
        d = self.doc()
        first = d['asks'][0]['askedAt'] = '2020-01-02T03:04:05Z'
        with open(os.path.join(self.run_dir, 'orchestrator.json'), 'w', encoding='utf-8') as f:
            json.dump(d, f)
        self.assertIn('updated', self.cli('ask', 'Q-1', '--kind', 'steering', '--question', 'Second').stdout)
        asks = self.doc()['asks']
        self.assertEqual(len(asks), 1)
        self.assertEqual((asks[0]['question'], asks[0]['askedAt']), ('Second', first))

    def test_reasking_an_answered_ask_is_refused(self):
        self.cli('init')
        self.cli('ask', 'Q-1', '--kind', 'blocker', '--question', 'Stuck')
        self.cli('answered', 'Q-1', 'unblocked')
        self.assertIn('new id', self.cli('ask', 'Q-1', '--kind', 'blocker', '--question', 'Again', ok=False).stderr)

    def markers(self):
        with open(os.path.join(self.run_dir, 'markers.jsonl'), encoding='utf-8') as f:
            return [json.loads(line) for line in f]

    def test_marker_appends_one_line_and_leaves_the_state_file_alone(self):
        self.cli('init')
        with open(os.path.join(self.run_dir, 'orchestrator.json'), 'rb') as f:
            before = f.read()
        out = self.cli('marker', 'merges  to\nthe mid-tier model', '--scope', 'merges', '--at', '2026-10-13T18:00:00+02:00').stdout
        self.assertEqual(out, "marker 'merges to the mid-tier model': merges at 2026-10-13T16:00:00Z; 1 marker(s)\n")
        out = self.cli('marker', 'keep-warm polls').stdout
        self.assertEqual(len(out.splitlines()), 1)
        self.assertIn(': all at ', out)
        m = self.markers()
        self.assertEqual(m[0], {'at': '2026-10-13T16:00:00Z', 'label': 'merges to the mid-tier model', 'scope': 'merges'})
        self.assertEqual((m[1]['label'], m[1]['scope']), ('keep-warm polls', 'all'))
        with open(os.path.join(self.run_dir, 'orchestrator.json'), 'rb') as f:
            self.assertEqual(f.read(), before)

    def test_marker_refusals_are_one_line(self):
        for args in [('marker', 'x'), ('--run', self.run_dir, 'marker', ' ')]:
            p = self.cli(*args, ok=False)
            self.assertEqual((p.stdout, len(p.stderr.splitlines())), ('', 1))
        os.makedirs(self.run_dir)
        self.assertIn('not an ISO', self.cli('marker', 'x', '--at', 'yesterday', ok=False).stderr)
        self.assertIn('invalid choice', self.cli('marker', 'x', '--scope', 'some', ok=False).stderr)
        self.assertFalse(os.path.exists(os.path.join(self.run_dir, 'markers.jsonl')))

    def test_marker_writes_are_atomic_and_locked(self):
        os.makedirs(self.run_dir)
        with open(os.path.join(self.run_dir, 'markers.jsonl'), 'w', encoding='utf-8') as f:
            f.write('{"at": "2026-10-12T00:00:00Z", "label": "old", "scope": "all"}')
        with mock.patch.object(state.os, 'replace', side_effect=OSError('disk gone')), mock.patch('sys.stderr'):
            self.assertEqual(state.main(['--run', self.run_dir, 'marker', 'lost']), 1)
        self.assertEqual([m['label'] for m in self.markers()], ['old'])
        target = os.path.join(self.run_dir, 'markers.jsonl')
        procs = []
        self.addCleanup(lambda: [p.kill() for p in procs if p.poll() is None])
        with state.locked(target):
            procs += [subprocess.Popen([sys.executable, SCRIPT, 'marker', f'm{i}'], env=self.env, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True) for i in range(8)]
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                done = [p.args[-1] for p in procs if p.poll() is not None]
                self.assertEqual(done, [], 'a marker was written while another writer held the lock')
                time.sleep(0.05)
        outs = []
        for p in procs:
            try:
                outs.append(p.communicate(timeout=30))
            except subprocess.TimeoutExpired:
                self.fail(f'{p.args[-1]} hung for 30 s after the lock was released')
        self.assertEqual([p.returncode for p in procs], [0] * 8, outs)
        self.assertEqual(sorted(m['label'] for m in self.markers()), ['m%d' % i for i in range(8)] + ['old'])
        self.assertEqual([n for n in os.listdir(self.run_dir) if n.endswith('.tmp')], [])

    def test_init_keeps_existing_records(self):
        self.cli('init', '--title', 'One')
        self.cli('ask', 'Q-1', '--kind', 'decision', '--question', 'q')
        self.cli('init', '--client', 'vscode')
        d = self.doc()
        self.assertEqual((d['orchestrator']['title'], d['orchestrator']['client'], len(d['asks'])), ('One', 'vscode', 1))


if __name__ == '__main__':
    unittest.main()
