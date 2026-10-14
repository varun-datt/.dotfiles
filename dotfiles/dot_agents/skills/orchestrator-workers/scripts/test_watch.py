import io, json, os, subprocess, sys, tempfile, time, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import status, watch  # noqa: E402

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'watch.py')


def row(name, st='running', elapsed=10.0, idle=1.0, budget=90):
    return {'name': name, 'state': st, 'elapsed': elapsed, 'idle': idle, 'doing': 'thinking (model call)',
            'premium': None, 'aiu': None, 'budget': budget}


class Clock:
    def __init__(self):
        self.t = 1_000_000.0
        self.sleeps = 0

    def time(self):
        return self.t

    def sleep(self, s):
        self.sleeps += 1
        self.t += s

    def strftime(self, fmt):
        return time.strftime(fmt)


class Out(io.StringIO):
    def __init__(self):
        super().__init__()
        self.flushed_at = []

    def flush(self):
        self.flushed_at.append(len(self.getvalue()))
        super().flush()


class WatchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run_dir = os.path.join(self.tmp.name, 'run')
        self.reg = os.path.join(self.tmp.name, 'registry.jsonl')
        for p in (mock.patch.object(status, 'RUN', self.run_dir), mock.patch.object(status, 'STALL_MIN', 20.0),
                  mock.patch.dict(os.environ, {'OW_REGISTRY': self.reg})):
            p.start()
            self.addCleanup(p.stop)

    def register(self, folder=None):
        with open(self.reg, 'a', encoding='utf-8') as f:
            f.write('not json\n' + json.dumps({'dir': folder or self.run_dir, 'prefix': 'ow-', 'title': None, 'sessionId': None}) + '\n')

    def watch(self, rows, *args):
        """Run watch.main with `rows` (a list, or a function of the call number) and a fake clock."""
        calls = []

        def fake_rows():
            calls.append(1)
            return rows(len(calls)) if callable(rows) else rows
        out, clock = Out(), Clock()
        with mock.patch.object(status, 'rows', fake_rows), mock.patch.object(watch, 'time', clock), \
             mock.patch('sys.stdout', out):
            code = watch.main(list(args))
        self.assertFalse(os.path.exists(os.path.join(self.run_dir, 'watch.pid')))
        return code, out, clock

    def lines(self, rows, *args):
        return self.watch(rows, *args)[1].getvalue().splitlines()

    def test_registered_heartbeat_prints_exactly_one_line(self):
        self.register()
        out = self.lines([row('a'), row('b'), row('c', 'done')], '2')
        self.assertEqual(out, ['HEARTBEAT: 2 awake minutes; running=2 stalled=0 died=0'])

    def test_registered_alert_prints_one_line_naming_the_worker(self):
        self.register()
        out = self.lines([row('a'), row('dead', 'DIED (no result)')])
        self.assertEqual(out, ['ALERT: a worker stalled or died: dead DIED; running=1 stalled=0 died=1'])

    def test_registered_over_budget_prints_one_line_naming_the_worker(self):
        self.register()
        out = self.lines([row('slow', elapsed=95, budget=90), row('b')])
        self.assertEqual(out, ['ALERT: over time budget: slow 95m/90m; running=2 stalled=0 died=0'])

    def test_registered_capped_prints_one_line_with_credits_against_the_cap(self):
        self.register()
        capped = {**row('cap', 'CAPPED'), 'cap': {'used': 32.5, 'cap': 30.0, 'capped': True}}
        out = self.lines([row('a'), capped])
        self.assertEqual(out, ['ALERT: a worker hit its credit cap: cap CAPPED 32.5/30; running=1 stalled=0 died=0 capped=1'])

    def test_capped_alerts_like_a_death_and_a_death_names_both(self):
        capped = {**row('cap', 'CAPPED'), 'cap': {'used': 31.0, 'cap': 30.0, 'capped': True}}
        out = self.lines([row('a', 'done'), capped])
        self.assertEqual(out[0], 'ALERT: a worker hit its credit cap')
        self.register()
        out = self.lines([row('dead', 'DIED (no result)'), capped])
        self.assertEqual(out, ['ALERT: a worker stalled or died: dead DIED, cap CAPPED 31/30; running=0 stalled=0 died=1 capped=1'])

    def test_registry_matches_through_a_symlink(self):
        os.makedirs(self.run_dir)
        alias = os.path.join(self.tmp.name, 'alias')
        os.symlink(self.run_dir, alias)
        self.register(alias)
        self.assertEqual(len(self.lines([row('a', 'done')])), 1)

    def test_unregistered_prints_the_reason_then_the_table(self):
        self.register(os.path.join(self.tmp.name, 'another-run'))
        out = self.lines([row('alpha'), row('dead', 'DIED (no result)')])
        self.assertEqual(out[0], 'ALERT: a worker stalled or died')
        self.assertRegex(out[1], r'running=1 stalled=0 died=1 errored=0 done=0')
        self.assertEqual(len(out), 4)
        self.assertTrue(out[2].startswith('alpha ') and out[3].startswith('dead '), out)

    def test_missing_registry_prints_the_table(self):
        out = self.lines([row('alpha', 'done')])
        self.assertEqual(out[0], 'IDLE: no worker running')
        self.assertIn('running=0', out[1])

    def test_tables_flag_restores_the_table_for_a_registered_run(self):
        self.register()
        out = self.lines([row('alpha'), row('beta')], '1', '--tables')
        self.assertEqual(out[0], 'HEARTBEAT: 1 awake minutes')
        self.assertIn('running=2', out[1])
        self.assertEqual([x.split()[0] for x in out[2:]], ['alpha', 'beta'])

    def test_conditions_unchanged(self):
        stalled = [row('stuck', 'STALLED', idle=30), row('b')]
        cases = [
            ('died', [row('a'), row('dead', 'DIED (no result)')], 'ALERT: a worker stalled or died', 0),
            ('stalled', stalled, 'ALERT: a worker stalled or died', 20),
            ('over', [row('slow', elapsed=95, budget=90)], 'ALERT: over time budget: slow 95m/90m', 0),
            ('idle', [row('a', 'done'), row('b', 'ERRORED'), row('c', 'superseded')], 'IDLE: no worker running', 0),
            ('heartbeat', [row('a')], 'HEARTBEAT: 3 awake minutes', 3),
        ]
        for registered in (False, True):
            if registered:
                self.register()
            for label, rows, reason, sleeps in cases:
                with self.subTest(label=label, registered=registered):
                    if os.path.exists(os.path.join(self.run_dir, 'over-alerted.txt')):
                        os.remove(os.path.join(self.run_dir, 'over-alerted.txt'))
                    _, out, clock = self.watch(rows, '3' if label == 'heartbeat' else '60')
                    first = out.getvalue().splitlines()[0]
                    self.assertTrue(first == reason or first.startswith(reason + ':') or first.startswith(reason + ';'), first)
                    self.assertEqual(clock.sleeps, sleeps)

    def test_a_stall_waits_for_the_stall_minutes_after_wake(self):
        self.register()
        _, out, clock = self.watch([row('stuck', 'STALLED', idle=30)], '60')
        self.assertEqual(clock.sleeps, 20)
        self.assertEqual(out.getvalue(), 'ALERT: a worker stalled or died: stuck STALLED; running=0 stalled=1 died=0\n')

    def test_over_budget_alerts_once_per_worker(self):
        self.register()
        rows = [row('slow', elapsed=95, budget=90)]
        self.assertTrue(self.lines(rows, '2')[0].startswith('ALERT: over time budget: slow'))
        self.assertTrue(self.lines(rows, '2')[0].startswith('HEARTBEAT'))

    def test_quiet_without_progress(self):
        self.register()
        _, out, clock = self.watch([row('a')], '5')
        self.assertEqual(clock.sleeps, 5)
        self.assertEqual(len(out.getvalue().splitlines()), 1)

    def test_progress_prints_one_flushed_line_per_tick(self):
        self.register()
        _, out, clock = self.watch(lambda n: [row('a'), row('b', 'STALLED', idle=3)], '4', '--progress')
        lines = out.getvalue().splitlines()
        self.assertEqual(clock.sleeps, 4)
        self.assertEqual(len(lines), 5)
        for i, line in enumerate(lines[:4]):
            self.assertRegex(line, r'^\d\d:\d\d watching: running=1 stalled=1 died=0; heartbeat in %dm$' % (4 - i))
        self.assertEqual(lines[4], 'HEARTBEAT: 4 awake minutes; running=1 stalled=1 died=0')
        ends = [len('\n'.join(lines[:i + 1])) + 1 for i in range(4)]
        for end in ends:
            self.assertIn(end, out.flushed_at)

    def test_progress_line_is_printed_before_each_sleep(self):
        self.register()
        seen = []
        out, clock = Out(), Clock()

        def sleep(s):
            seen.append(len(out.getvalue().splitlines()))
            clock.t += s
        clock.sleep = sleep
        with mock.patch.object(status, 'rows', lambda: [row('a')]), mock.patch.object(watch, 'time', clock), \
             mock.patch('sys.stdout', out):
            watch.main(['3', '--progress'])
        self.assertEqual(seen, [1, 2, 3])


class WatchCliTest(unittest.TestCase):
    def test_end_to_end_one_line_when_registered_and_table_when_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = os.path.join(tmp, 'run')
            os.makedirs(run)
            with open(os.path.join(run, 'job.start'), 'w') as f:
                f.write(str(int(time.time()) - 120))
            with open(os.path.join(run, 'job.jsonl'), 'w') as f:
                f.write(json.dumps({'type': 'model.call_finished'}) + '\n' + json.dumps({'type': 'result', 'exitCode': 0}) + '\n')
            reg = os.path.join(tmp, 'registry.jsonl')
            env = {**os.environ, 'OW_RUN_DIR': run, 'OW_REGISTRY': reg, 'OW_PREFIX': 'owtest-nomatch-', 'PYTHONDONTWRITEBYTECODE': '1'}

            def cli(*args):
                p = subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, env=env, timeout=60)
                self.assertEqual((p.returncode, p.stderr), (0, ''))
                return p.stdout.splitlines()
            out = cli()
            self.assertEqual(out[0], 'IDLE: no worker running')
            self.assertIn('done=1', out[1])
            with open(reg, 'w') as f:
                f.write(json.dumps({'dir': run}) + '\n')
            self.assertEqual(cli(), ['IDLE: no worker running; running=0 stalled=0 died=0'])
            self.assertEqual(len(cli('--tables')), 2)
            self.assertFalse(os.path.exists(os.path.join(run, 'watch.pid')))


if __name__ == '__main__':
    unittest.main()
