import io, json, os, sys, tempfile, threading, time, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runqueue as q  # noqa: E402

S = os.path.dirname(os.path.abspath(q.__file__))


def wait_until(pred, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.02)
    return False


class QueueTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.rd = os.path.join(self.tmp.name, 'run')
        self.notes = []
        p = mock.patch.object(q, 'notify', self.notes.append)
        p.start()
        self.addCleanup(p.stop)

    def cli(self, *args):
        return q.main([*args, '--run-dir', self.rd])

    def items(self):
        return {it['id']: it for it in q.load(self.rd)['items']}

    def start(self, **kw):
        kw = {'slots': 3, 'poll': 0.05, 'idle_alert': 0, **kw}
        t = threading.Thread(target=q.run, args=(self.rd,), kwargs=kw, daemon=True)
        t.start()
        return t

    def finish(self, t, ids):
        self.assertTrue(wait_until(lambda: all(self.items()[i]['end'] is not None for i in ids)), self.items())
        for i in ids:
            self.cli('done', i)
        t.join(5)
        self.assertFalse(t.is_alive())

    def test_slots_respected_and_no_slot_items_do_not_count(self):
        for i in ('a', 'b', 'c'):
            self.cli('add', i, '--cmd', 'sleep 0.3')
        self.cli('add', 'r', '--cmd', 'sleep 0.3', '--no-slot')
        t = self.start(slots=1)
        self.finish(t, ['a', 'b', 'c', 'r'])
        it = self.items()
        self.assertLess(it['r']['start'], it['a']['end'])
        self.assertGreaterEqual(it['b']['start'], it['a']['end'])
        self.assertGreaterEqual(it['c']['start'], it['b']['end'])

    def test_after_waits_for_done_not_for_exit(self):
        self.cli('add', 'a', '--cmd', 'true')
        self.cli('add', 'b', '--cmd', 'true', '--after', 'a')
        t = self.start()
        self.assertTrue(wait_until(lambda: self.items()['a']['end'] is not None))
        time.sleep(0.2)
        self.assertIsNone(self.items()['b']['start'])
        self.assertEqual(q.state(self.items()['b'], self.items()), 'waiting')
        self.cli('done', 'a')
        self.finish(t, ['b'])
        self.assertGreater(self.items()['b']['start'], self.items()['a']['end'])

    def test_exit_codes_recorded_and_status_lines(self):
        self.cli('add', 'bad', '--cmd', 'sleep 0.2; exit 3')
        t = self.start()
        self.assertTrue(wait_until(lambda: self.items()['bad']['end'] is not None))
        self.assertEqual(self.items()['bad']['exit'], 3)
        with mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            self.cli('status')
        self.assertRegex(out.getvalue(), r'^bad  exited 3  \d+m$')
        self.finish(t, ['bad'])

    def test_concurrent_add_during_run_is_not_lost(self):
        self.cli('add', 'first', '--cmd', 'sleep 0.5')
        t = self.start(slots=20)
        adders = [threading.Thread(target=self.cli, args=('add', f'x{n}', '--cmd', 'true')) for n in range(15)]
        for a in adders:
            a.start()
        for a in adders:
            a.join()
        ids = ['first'] + [f'x{n}' for n in range(15)]
        self.assertEqual(set(self.items()), set(ids))
        self.finish(t, ids)

    def test_priority_then_insertion_order(self):
        log = os.path.join(self.tmp.name, 'order')
        for i, p in (('low', '0'), ('high', '5'), ('mid', '1'), ('mid2', '1')):
            self.cli('add', i, '--cmd', f'echo {i} >> {log}', '--priority', p)
        t = self.start(slots=1)
        self.finish(t, ['low', 'high', 'mid', 'mid2'])
        with open(log) as f:
            self.assertEqual(f.read().split(), ['high', 'mid', 'mid2', 'low'])

    def test_idle_chat_alerts_the_owner_once_and_quiet_while_active(self):
        self.cli('add', 'a', '--cmd', 'true')
        old = time.time() - 3600
        os.utime(os.path.join(self.rd, 'heartbeat'), (old, old))
        t = self.start(idle_alert=0.5)
        self.assertTrue(wait_until(lambda: self.notes))
        time.sleep(0.3)
        self.assertEqual(len(self.notes), 1)
        self.assertIn('a exited 0', self.notes[0])
        with open(os.path.join(self.rd, 'ALERT.log')) as f:
            self.assertIn(self.notes[0], f.read())
        self.cli('done', 'a')
        t.join(5)

        self.notes.clear()
        self.cli('add', 'b', '--cmd', 'true')
        t = self.start(idle_alert=0.5)
        self.finish(t, ['b'])
        self.assertEqual(self.notes, [])

    def test_idle_alert_is_not_repeated_while_the_same_items_wait(self):
        self.cli('add', 'a', '--cmd', 'true')
        old = time.time() - 3600
        os.utime(os.path.join(self.rd, 'heartbeat'), (old, old))
        t = self.start(idle_alert=0.001)
        self.assertTrue(wait_until(lambda: self.notes))
        time.sleep(0.5)
        self.assertEqual(len(self.notes), 1)
        self.cli('add', 'c', '--cmd', 'true')
        self.assertTrue(wait_until(lambda: len(self.notes) == 2))
        self.assertIn('c exited 0', self.notes[1])
        self.cli('done', 'a')
        self.cli('done', 'c')
        t.join(5)

    def test_add_rejects_duplicates_and_unknown_after(self):
        self.assertEqual(self.cli('add', 'a', '--cmd', 'true'), 0)
        with mock.patch('sys.stderr'):
            self.assertEqual(self.cli('add', 'a', '--cmd', 'true'), 2)
            self.assertEqual(self.cli('add', 'b', '--cmd', 'true', '--after', 'nope'), 2)
        with open(os.path.join(self.rd, 'queue.json')) as f:
            self.assertEqual([it['id'] for it in json.load(f)['items']], ['a'])

    def test_add_refuses_an_unrouted_copilot_command_unless_given_a_reason(self):
        with mock.patch('sys.stderr'):
            self.assertEqual(self.cli('add', 'a', '--cmd', 'copilot -p "do it" --model m'), 2)
        self.assertEqual(self.cli('add', 'a', '--cmd', 'copilot -p "do it"', '--unrouted-reason', 'owner probe'), 0)
        self.assertEqual(self.cli('add', 'b', '--cmd', f'python3 {S}/route.py run b --kind build --brief b.md --worktree w'), 0)
        self.assertEqual(self.cli('add', 'c', '--cmd', f'bash {S}/review.sh b-review w'), 0)
        with open(os.path.join(self.rd, 'queue.json')) as f:
            items = {it['id']: it for it in json.load(f)['items']}
        self.assertEqual(items['a']['unrouted_reason'], 'owner probe')
        self.assertNotIn('unrouted_reason', items['b'])

    def test_add_refuses_every_copilot_mention_unless_route_py_run_or_review_sh_is_the_program(self):
        launch = os.path.join(self.tmp.name, 'launch.zsh')
        with open(launch, 'w') as f:
            f.write('#!/bin/zsh\nMODEL=m\ntimeout 9000 copilot -C wt --model "$MODEL" -p "$(cat brief.md)"\necho done\n')
        plain = os.path.join(self.tmp.name, 'launch')
        with open(plain, 'w') as f:
            f.write('MODEL=m\ntimeout 9000 copilot -p x\n')
        tidy = os.path.join(self.tmp.name, 'tidy.sh')
        with open(tidy, 'w') as f:
            f.write('#!/bin/sh\necho tidy\n')
        refused = ['timeout --signal TERM 9000 copilot -p x', '>log copilot -p x', '"$(command -v copilot)" -p x',
                   f'bash {plain}', f'cd {self.tmp.name} && bash launch', 'c""opilot -p x', '`which copilot` -p x',
                   f'bash {S}/review.sh a w; copilot -p x', f'bash {S}/review.sh a w && copilot -p x',
                   f'nohup zsh -c "bash {S}/review.sh a w; copilot -p x" &', f'python3 {S}/route.py pick a; copilot -p x',
                   'python3 /x/route.py run a', f'bash {self.tmp.name}/gone.sh',
                   'zsh run1030/launch.zsh x',
                   'env A=1 copilot -p x', 'timeout 900 copilot -p x', 'nohup copilot -p x &', 'A=1 B=2 copilot -p x',
                   "zsh -c 'copilot -p x'", 'bash -c "cd /tmp && copilot -p x"', "sh -c 'copilot -p x'",
                   'true; copilot -p x', 'true && copilot -p x', 'false || copilot -p x', 'echo hi | copilot -p x',
                   'echo review.sh; copilot -p x', 'copilot -p "run review.sh then stop"',
                   f'nohup zsh -c "cd {self.tmp.name} && zsh launch.zsh x >log 2>&1" &', f'zsh {launch}',
                   'echo "$(copilot -p x)"', 'echo copilot']
        for n, cmd in enumerate(refused):
            with mock.patch('sys.stderr'):
                self.assertEqual(self.cli('add', f'r{n}', '--cmd', cmd), 2, cmd)
            self.assertEqual(self.cli('add', f'r{n}', '--cmd', cmd, '--unrouted-reason', 'owner probe'), 0, cmd)
        run = f'python3 -B {S}/route.py run a --kind build --brief b --worktree w'
        for n, cmd in enumerate([run, f'bash {S}/review.sh a-review w >a.log 2>&1', f'{S}/review.sh a-review w',
                                 f'nohup zsh -c "{run} >a.log 2>&1" &', f'nohup zsh -c "bash {S}/review.sh a-review w" &',
                                 f'timeout --signal TERM 9000 env A=1 {run}', f'sh {tidy}', 'sleep 1',
                                 f'cd /tmp && bash {S}/review.sh a-review w >a.log 2>&1']):
            self.assertEqual(self.cli('add', f'ok{n}', '--cmd', cmd), 0, cmd)
        items = self.items()
        self.assertEqual({items[f'r{n}']['unrouted_reason'] for n in range(len(refused))}, {'owner probe'})


if __name__ == '__main__':
    unittest.main()
