import io, json, os, re, sys, tempfile, threading, time, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runqueue as q  # noqa: E402

ANCESTOR = q.caffeinated_ancestor

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

    def test_add_queues_any_command_text_because_text_is_not_checked_for_caffeinate(self):
        run = f'python3 -B {S}/route.py run a --kind build --brief b --worktree w'
        texts = [f"{run} --override 'reason=Do not use caffeinate -i'", f"echo '$(caffeinate -i)'",
                 f'CAFFEINATE_BIN=/usr/bin/caffeinate {run}', f"env -S 'caffeinate -i {run}'",
                 f"zsh -c 'exec -a name caffeinate -i {run}'", f'caffeinate -i {run}']
        for n, cmd in enumerate(texts):
            self.assertEqual(self.cli('add', f'ok{n}', '--cmd', cmd, '--unrouted-reason', 'owner probe'), 0, cmd)
        self.assertEqual(len(self.items()), len(texts))

    def test_each_form_is_decided_at_launch_by_the_ancestor_check(self):
        fakebin = os.path.join(self.tmp.name, 'bin')
        os.makedirs(fakebin)
        # A binary named caffeinate is killed here within a second, so the stand-in is bash with argv[0] caffeinate.
        with open(os.path.join(fakebin, 'caffeinate'), 'w') as f:
            f.write('#!/bin/bash\nwhile [ "${1#-}" != "$1" ]; do shift; done\n'
                    'exec -a caffeinate /bin/bash -c \'"$@"; exit $?\' caffeinate "$@"\n')
        os.chmod(os.path.join(fakebin, 'caffeinate'), 0o755)
        check = os.path.join(self.tmp.name, 'check.py')
        with open(check, 'w') as f:
            f.write(f'import sys\nsys.path.insert(0, {S!r})\nimport runqueue\nr = runqueue.caffeinate_refusal()\n'
                    'print(r or "launched")\nsys.exit(2 if r else 0)\n')
        brief = os.path.join(self.tmp.name, 'b.md')
        with open(brief, 'w') as f:
            f.write('Do not use caffeinate -i.\n')
        chk = f'python3 -B {check}'
        forms = {'literal': (f"{chk} --override 'reason=Do not use caffeinate -i'", 0),
                 'quoted': (f"{chk} '$(caffeinate -i)'", 0),
                 'assign': (f'CAFFEINATE_BIN=/usr/bin/caffeinate {chk}', 0),
                 'envs': (f"env -S 'caffeinate -i {chk}'", 2),
                 'execa': (f"zsh -c 'exec -a name caffeinate -i {chk}'", 2),
                 'route': (f"env -S 'caffeinate -i python3 -B {S}/route.py run a --kind build --brief {brief} "
                           f"--worktree {self.tmp.name}'", 2)}
        for name, (cmd, _) in forms.items():
            self.assertEqual(self.cli('add', name, '--cmd', cmd, '--unrouted-reason', 'owner probe'), 0, cmd)
        with mock.patch.dict(os.environ, {'PATH': f"{fakebin}:{os.environ['PATH']}"}):
            t = self.start()
            self.assertTrue(wait_until(lambda: all(it['end'] is not None for it in self.items().values()), 60),
                            self.items())
        self.finish(t, list(forms))
        for name, (cmd, rc) in forms.items():
            with open(os.path.join(self.rd, f'{name}.runner.log')) as f:
                log = f.read()
            self.assertEqual(self.items()[name]['exit'], rc, f'{name}: {log}')
            if rc:
                self.assertIn('runs under caffeinate (pid ', log, name)
            else:
                self.assertIn('launched', log, name)

    def test_a_renamed_caffeinate_is_seen_by_its_executable_name(self):
        parent = os.getppid()
        table = f'{parent} 1 bash\n{parent} 1 name\n'
        self.assertIsNone(ANCESTOR(lambda: table))
        table = f'{parent} 1 caffeinate\n{parent} 1 name\n'
        self.assertEqual(ANCESTOR(lambda: table), f'{parent} caffeinate')

    def test_the_process_table_holds_the_executable_name_and_argv0(self):
        import subprocess
        code = f'import os, sys; sys.path.insert(0, {S!r}); import runqueue; print(runqueue.processes()[os.getppid()][1])'
        p = subprocess.run(['zsh', '-c', f'exec -a name /bin/bash -c "{sys.executable} -B -c \\"{code}\\"; exit \\$?"'],
                           capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(sorted(eval(p.stdout)), ['bash', 'name'])

    def test_add_and_run_refuse_when_started_by_a_caffeinate_process(self):
        table = f'{os.getppid()} 1 /usr/bin/caffeinate\n'
        with mock.patch.object(q, 'caffeinated_ancestor', lambda ps=None: ANCESTOR(lambda: table)):
            for args in (('add', 'a', '--cmd', 'true'), ('run',)):
                err = io.StringIO()
                with mock.patch('sys.stderr', err):
                    self.assertEqual(self.cli(*args), 2, args)
                self.assertIn(f'runs under caffeinate (pid {os.getppid()} /usr/bin/caffeinate)', err.getvalue())
        self.assertEqual(self.items(), {})
        self.assertEqual(self.cli('add', 'a', '--cmd', 'true'), 0)

    def test_an_ancestor_further_up_counts_and_a_caffeinate_child_does_not(self):
        me, parent = os.getpid(), os.getppid()
        up = f'{me} {parent} python3\n{parent} 4242 /bin/zsh\n4242 1 caffeinate\n'
        self.assertEqual(ANCESTOR(lambda: up), '4242 caffeinate')
        down = f'{parent} 1 /bin/zsh\n{me} {parent} python3\n5151 {me} /usr/bin/caffeinate\n'
        self.assertIsNone(ANCESTOR(lambda: down))
        loop = f'{parent} 4242 /bin/zsh\n4242 {parent} /bin/zsh\n'
        self.assertIsNone(ANCESTOR(lambda: loop))

    def test_an_unreadable_process_table_warns_and_does_not_refuse(self):
        def broken():
            raise OSError('no ps here')
        err = io.StringIO()
        with mock.patch('sys.stderr', err):
            self.assertIsNone(q.caffeinate_refusal(ps=broken))
        self.assertIn('not checked', err.getvalue())

    def test_a_real_caffeinate_named_parent_is_seen_through_ps(self):
        import subprocess
        under = ['bash', '-c', 'exec -a caffeinate /bin/bash -c "\\"\\$@\\"; exit \\$?" inner "$@"', 'outer']
        p = subprocess.run(under + [sys.executable, '-B', os.path.join(S, 'runqueue.py'), 'add', 'a', '--cmd', 'true',
                                    '--run-dir', self.rd], capture_output=True, text=True, timeout=60,
                           stdin=subprocess.DEVNULL)
        self.assertEqual(p.returncode, 2, p.stderr)
        self.assertIn('runs under caffeinate (pid ', p.stderr)
        self.assertEqual(self.items(), {})


FAKE_ROUTE = r'''import json, os, subprocess, sys, time
time.sleep(float(os.environ.get('OW_FAKE_DELAY', '0')))
a = sys.argv[1:]
rnd, kind = a[1], a[a.index('--kind') + 1]
wt, rd = a[a.index('--worktree') + 1], a[a.index('--run') + 1]
def opt(n, d):
    p = os.path.join(rd, f'{rnd}.{n}')
    return open(p).read().strip() if os.path.exists(p) else d
with open(os.path.join(rd, 'calls.log'), 'a') as f:
    f.write(f"{rnd} {kind} {time.time()} {' '.join(a)}\n")
head = subprocess.run(['git', '-C', wt, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout
open(os.path.join(rd, rnd + '.base'), 'w').write(head)
time.sleep(float(opt('sleep', '0')))
while os.path.exists(os.path.join(rd, rnd + '.hold')):
    time.sleep(0.02)
if kind in ('build', 'fix') and not os.path.exists(os.path.join(rd, rnd + '.nocommit')):
    open(os.path.join(wt, rnd + '.txt'), 'w').write(f'{rnd} {time.time()}')
    subprocess.run(['git', '-C', wt, 'add', rnd + '.txt'])
    subprocess.run(['git', '-C', wt, '-c', 'core.hooksPath=/dev/null', '-c', 'user.name=t', '-c',
                    'user.email=t@example.invalid', 'commit', '-qm', f'feat: {rnd}'])
with open(os.path.join(rd, rnd + '.jsonl'), 'w') as f:
    f.write(json.dumps({'type': 'assistant.message', 'data': {'content': f'REPORT of {rnd}'}}) + '\n')
    f.write(json.dumps({'type': 'result', 'exitCode': 0}) + '\n')
with open(os.path.join(rd, 'calls.log'), 'a') as f:
    f.write(f"{rnd} end {time.time()}\n")
sys.exit(int(opt('fake-exit', '0')))
'''
FAKE_REVIEW = r'''#!/usr/bin/env bash
name="$1"; wt="$2"; rd="$OW_RUN_DIR"
sleep "${OW_FAKE_DELAY:-0}"
echo "$name review $(python3 -c 'import time; print(time.time())') $*" >> "$rd/calls.log"
[ -f "$rd/$name.md" ] || exit 2
cp "$wt/REVIEW-DIFF.patch" "$rd/$name.seen-diff"
[ -f "$rd/$name.sleep" ] && sleep "$(cat "$rd/$name.sleep")"
while [ -f "$rd/$name.hold" ]; do sleep 0.02; done
echo "$name end $(python3 -c 'import time; print(time.time())')" >> "$rd/calls.log"
[ -f "$rd/$name.fake-exit" ] && exit "$(cat "$rd/$name.fake-exit")"
exit 0
'''
FIX_BODY = '''THIS IS A FIX ROUND in a fresh session, for item {id}.

FIX THESE, one at a time:
1. Lost rows on restart. Where: `store.py` about 40. What goes wrong: a restart drops a row. Done when: a restarted store keeps every row.
2. A check that cannot fail. Where: `test_store.py` about 12. What goes wrong: it passes vacuously. Done when: the check fails with the fix removed. Cases: one, two.

For each finding:
1. Write one test that fails.
'''
FULL = 'build,review,suspend:rulings,fix,recheck,suspend:merge'


class PipelineTest(unittest.TestCase):
    cli, items, start = QueueTest.cli, QueueTest.items, QueueTest.start

    def setUp(self):
        QueueTest.setUp(self)
        os.makedirs(self.rd)
        fakes = os.path.join(self.tmp.name, 'fakes')
        os.makedirs(fakes)
        route, review = os.path.join(fakes, 'route.py'), os.path.join(fakes, 'review.sh')
        with open(route, 'w') as f:
            f.write(FAKE_ROUTE)
        with open(review, 'w') as f:
            f.write(FAKE_REVIEW)
        for name, value in (('ROUTE', route), ('REVIEW', review)):
            p = mock.patch.object(q, name, value)
            p.start()
            self.addCleanup(p.stop)

    def worktree(self, i):
        wt = os.path.join(self.tmp.name, 'wt', i)
        os.makedirs(wt)
        git = ['git', '-C', wt, '-c', 'core.hooksPath=/dev/null', '-c', 'user.name=t', '-c', 'user.email=t@example.invalid']
        import subprocess
        subprocess.run(['git', 'init', '-q', '-b', f'ow/{i}', wt], check=True)
        with open(os.path.join(wt, 'README'), 'w') as f:
            f.write('x\n')
        subprocess.run(git + ['add', 'README'], check=True)
        subprocess.run(git + ['commit', '-qm', 'init'], check=True)
        body = f'TASK: item {i}\nRISK: processes (a runner that relaunches wastes credits), checks (a wrong base)\n'
        self.write(f'{i}.body.md', body)
        self.write(f'{i}.prompt.md', 'PREAMBLE for the worker\n' + body)
        return wt

    def write(self, name, text):
        with open(os.path.join(self.rd, name), 'w') as f:
            f.write(text)

    def read(self, name):
        with open(os.path.join(self.rd, name)) as f:
            return f.read()

    def add(self, i, pipeline=FULL, *extra):
        return self.cli('add', i, '--pipeline', pipeline, '--worktree', self.worktree(i), *extra)

    def calls(self):
        try:
            return [ln.split() for ln in self.read('calls.log').splitlines()]
        except FileNotFoundError:
            return []

    def launched(self):
        return [c[0] for c in self.calls() if c[1] != 'end']

    def step(self, i):
        it = self.items()[i]
        s = q.current(it)
        return (s['name'] if s else None), q.state(it, self.items())

    def at(self, i, name, st='suspended'):
        self.assertTrue(wait_until(lambda: self.step(i) == (name, st)), (self.step(i), self.calls()))

    def stop(self, t, ev):
        ev.set()
        t.join(5)
        self.assertFalse(t.is_alive())

    def test_full_pipeline_runs_each_step_through_the_launchers_and_waits_at_each_suspend(self):
        self.assertEqual(self.add('a'), 0)
        t = self.start()
        self.at('a', 'suspend:rulings')
        self.assertEqual(self.launched(), ['a', 'a-review'])
        self.assertIn('--kind build', ' '.join(self.calls()[0]))
        self.assertIn(os.path.join(self.rd, 'a.prompt.md'), self.calls()[0])
        prompt = self.read('a-review.md')
        self.assertIn('TASK: item a', prompt)
        self.assertIn('- Processes: what starts', prompt)
        self.assertIn('- The checks themselves:', prompt)
        self.assertNotIn('Trust boundaries', prompt)
        self.assertEqual(re.findall(r'\{\{[^}]+\}\}', prompt), ['{{RUBRIC}}'])
        self.assertIn('+++ b/a.txt', self.read('a-review.seen-diff'))
        with open(os.path.join(self.items()['a']['worktree'], 'REVIEW-REPORT.md')) as f:
            self.assertEqual(f.read().strip(), 'REPORT of a')
        time.sleep(0.3)
        self.assertEqual(self.launched(), ['a', 'a-review'])
        self.write('a-fix1.body.md', FIX_BODY.format(id='a'))
        self.write('a.rulings.done', 'fix 1 and 2\n')
        self.at('a', 'suspend:merge')
        self.assertEqual(self.launched(), ['a', 'a-review', 'a-fix1', 'a-rereview'])
        self.assertEqual(self.read('a-fix1.prompt.md'), 'PREAMBLE for the worker\n' + FIX_BODY.format(id='a'))
        self.assertIn('--kind fix', ' '.join(self.calls()[4]))
        recheck = self.read('a-rereview.md')
        self.assertIn('1. Lost rows on restart. Where: `store.py` about 40. Done when: a restarted store keeps every row.', recheck)
        self.assertIn('2. A check that cannot fail. Where: `test_store.py` about 12. Done when: the check fails with the fix removed.', recheck)
        self.assertNotIn('{{', recheck)
        self.assertIn('feat: a-fix1', recheck)
        seen = self.read('a-rereview.seen-diff')
        self.assertIn('+++ b/a-fix1.txt', seen)
        self.assertNotIn('+++ b/a.txt', seen)
        self.write('a.merge.done', '')
        t.join(5)
        self.assertFalse(t.is_alive())
        self.assertTrue(self.items()['a']['done'])
        self.assertEqual(len(self.launched()), 4)

    def test_a_failed_build_stops_the_pipeline_until_retried(self):
        self.add('a')
        self.write('a.fake-exit', '1')
        t = self.start()
        self.at('a', 'build', 'failed 1')
        time.sleep(0.3)
        self.assertEqual(self.launched(), ['a'])
        with mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            self.cli('status')
        self.assertRegex(out.getvalue(), r'^a  build \(1/6\)  failed 1, waits on the chat  \d+m$')
        self.assertEqual(q.waiting_on_chat(list(self.items().values()), 0), ['a build failed 1'])
        os.remove(os.path.join(self.rd, 'a.fake-exit'))
        self.assertEqual(self.cli('retry', 'a'), 0)
        self.at('a', 'suspend:rulings')
        self.assertEqual(self.launched(), ['a', 'a', 'a-review'])
        self.assertNotEqual(self.read('a.base').strip(), self.items()['a']['pipeline'][0]['head'])
        self.assertIn('--- /dev/null\n+++ b/a.txt', self.read('a-review.seen-diff'))
        self.write('a.rulings.done', 'none')
        self.write('a.merge.done', '')
        t.join(5)

    def test_a_capped_timed_out_or_errored_review_stops_the_pipeline(self):
        for code in ('3', '124', '4'):
            self.add(f'r{code}')
            self.write(f'r{code}-review.fake-exit', code)
        t = self.start()
        for code in ('3', '124', '4'):
            self.at(f'r{code}', 'review', f'failed {code}')
        time.sleep(0.3)
        self.assertEqual(sorted(self.launched()), sorted(['r3', 'r3-review', 'r124', 'r124-review', 'r4', 'r4-review']))
        for code in ('3', '124', '4'):
            self.cli('done', f'r{code}')
        t.join(5)

    def test_rulings_none_skips_the_fix_and_the_recheck(self):
        self.add('a')
        t = self.start()
        self.at('a', 'suspend:rulings')
        self.write('a.rulings.done', 'None. Nothing blocks.\n')
        self.at('a', 'suspend:merge')
        self.assertEqual(self.launched(), ['a', 'a-review'])
        self.assertEqual([s['name'] for s in self.items()['a']['pipeline'] if s.get('skipped')], ['fix', 'recheck'])
        self.write('a.merge.done', '')
        t.join(5)
        self.assertTrue(self.items()['a']['done'])

    def test_reviews_do_not_take_a_slot_so_two_items_interleave(self):
        self.add('a')
        self.add('b')
        self.write('a-review.hold', '')
        t = self.start(slots=1)
        self.assertTrue(wait_until(lambda: 'b' in self.launched()), self.calls())
        self.assertEqual(self.step('a'), ('review', 'running'))
        self.assertNotIn(['a-review', 'end'], [c[:2] for c in self.calls()])
        when = {(c[0], c[1] == 'end'): float(c[2]) for c in self.calls()}
        self.assertGreaterEqual(when[('b', False)], when[('a', True)])
        os.remove(os.path.join(self.rd, 'a-review.hold'))
        self.at('a', 'suspend:rulings')
        self.at('b', 'suspend:rulings')
        for i in ('a', 'b'):
            self.write(f'{i}.rulings.done', 'none')
            self.write(f'{i}.merge.done', '')
        t.join(5)

    def test_a_restarted_runner_never_relaunches_a_step_that_started(self):
        self.add('a')
        self.write('a.sleep', '0.8')
        ev = threading.Event()
        t = self.start(stop=ev)
        self.at('a', 'build', 'running')
        self.stop(t, ev)
        ev2 = threading.Event()
        t = self.start(stop=ev2)
        self.at('a', 'suspend:rulings')
        self.stop(t, ev2)
        self.assertEqual(self.launched(), ['a', 'a-review'])
        t = self.start()
        time.sleep(0.3)
        self.write('a.rulings.done', 'none')
        self.write('a.merge.done', '')
        t.join(5)
        self.assertEqual(self.launched(), ['a', 'a-review'])

    def test_a_round_launched_just_before_a_crash_is_found_running_and_never_relaunched(self):
        import subprocess
        self.add('a')
        self.write('a.hold', '')
        real = subprocess.Popen

        class Crash(BaseException):
            pass

        def popen(args, *a, **kw):
            p = real(args, *a, **kw)
            if args[:3] == ['/bin/sh', '-c', q.WRAP]:
                raise Crash
            return p
        with mock.patch.object(q.subprocess, 'Popen', popen), mock.patch('threading.excepthook'):
            t = self.start()
            t.join(5)
        self.assertFalse(t.is_alive())
        s = self.items()['a']['pipeline'][0]
        self.assertIsNotNone(s['start'])
        self.assertIsNone(s['pid'])
        self.assertTrue(wait_until(lambda: 'a' in self.launched()), self.calls())
        if os.path.exists(os.path.join(self.rd, 'a.queue-pid')):
            os.remove(os.path.join(self.rd, 'a.queue-pid'))
        ev = threading.Event()
        t = self.start(stop=ev)
        self.assertTrue(wait_until(lambda: self.items()['a']['pipeline'][0]['pid'] is not None), self.items())
        self.assertEqual(self.step('a'), ('build', 'running'))
        self.stop(t, ev)
        qd = q.load(self.rd)
        qd['items'][0]['pipeline'][0].update(end=time.time(), exit=None, pid=None)
        q.save(self.rd, qd)
        self.assertEqual(self.step('a'), ('build', 'failed ?'))
        with mock.patch('sys.stderr', new_callable=io.StringIO) as err:
            self.assertEqual(self.cli('retry', 'a'), 2)
            self.assertEqual(self.cli('retry', 'a', '--passed'), 2)
        self.assertIn('a may still run', err.getvalue())
        os.remove(os.path.join(self.rd, 'a.hold'))
        self.assertTrue(wait_until(lambda: os.path.exists(os.path.join(self.rd, 'a.queue-exit'))))
        self.assertTrue(wait_until(lambda: q.round_pid(self.rd, 'a') is None))
        self.assertEqual(self.cli('retry', 'a', '--passed'), 0)
        t = self.start()
        self.at('a', 'suspend:rulings')
        self.assertEqual(self.launched(), ['a', 'a-review'])
        self.cli('done', 'a')
        t.join(5)

    def test_a_ready_fix_takes_a_freed_slot_before_any_new_build(self):
        self.add('a')
        ev = threading.Event()
        t = self.start(slots=1, stop=ev)
        self.at('a', 'suspend:rulings')
        self.stop(t, ev)
        self.add('b', FULL, '--priority', '9')
        self.write('a-fix1.body.md', FIX_BODY.format(id='a'))
        self.write('a.rulings.done', 'fix 1 and 2\n')
        once = threading.Event()
        once.set()
        q.run(self.rd, slots=1, poll=0.05, idle_alert=0, stop=once)
        self.assertEqual(self.step('a'), ('fix', 'running'))
        self.assertEqual(self.step('b'), ('build', 'ready'))
        t = self.start(slots=1)
        self.at('a', 'suspend:merge')
        self.at('b', 'suspend:rulings')
        for i in ('a', 'b'):
            self.cli('done', i)
        t.join(5)

    def test_a_step_gone_without_an_exit_code_waits_on_the_chat(self):
        self.add('a')
        qd = q.load(self.rd)
        import subprocess
        p = subprocess.Popen(['true'])
        p.wait()
        qd['items'][0]['pipeline'][0].update(start=time.time(), pid=p.pid)
        q.save(self.rd, qd)
        t = self.start()
        self.at('a', 'build', 'failed ?')
        time.sleep(0.2)
        self.assertEqual(self.launched(), [])
        self.cli('done', 'a')
        t.join(5)

    def test_a_review_with_no_usable_base_or_an_empty_diff_is_never_launched(self):
        self.add('nobase', 'review,suspend:merge')
        self.add('badbase', 'review,suspend:merge')
        self.write('badbase.base', '0123456789abcdef0123456789abcdef01234567\n')
        self.add('empty')
        self.write('empty.nocommit', '')
        t = self.start()
        self.at('nobase', 'review', 'failed 2')
        self.at('badbase', 'review', 'failed 2')
        self.at('empty', 'review', 'failed 2')
        self.assertIn('no nobase.reviewbase or nobase.base', q.current(self.items()['nobase'])['reason'])
        self.assertIn('empty diff', q.current(self.items()['empty'])['reason'])
        self.assertEqual(self.launched(), ['empty'])
        with mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            self.cli('status')
        self.assertIn('empty  review (2/6)  failed 2, waits on the chat: empty diff', out.getvalue())
        for i in ('nobase', 'badbase', 'empty'):
            self.cli('done', i)
        t.join(5)

    def test_add_refuses_a_malformed_pipeline_or_a_stale_done_file(self):
        wt = self.worktree('x')
        self.write('s.merge.done', '')
        cases = [('x', 'build,review', wt), ('x', 'build,deploy,suspend:merge', wt), ('x', 'build,build,suspend:m', wt),
                 ('x', 'recheck,fix,suspend:m', wt), ('x', FULL, os.path.join(self.tmp.name, 'nowhere')),
                 ('s', FULL, wt)]
        for i, pipe, w in cases:
            with mock.patch('sys.stderr'):
                self.assertEqual(self.cli('add', i, '--pipeline', pipe, '--worktree', w), 2, pipe)
        with mock.patch('sys.stderr'), self.assertRaises(SystemExit):
            self.cli('add', 'x', '--pipeline', FULL, '--worktree', wt, '--cmd', 'true')
        self.assertEqual(self.items(), {})

    def test_status_names_the_step_and_what_it_waits_on(self):
        self.add('a')
        self.write('a.hold', '')
        t = self.start()
        self.at('a', 'build', 'running')
        with mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            self.cli('status')
        self.assertRegex(out.getvalue(), r'^a  build \(1/6\)  running a  \d+m$')
        os.remove(os.path.join(self.rd, 'a.hold'))
        self.at('a', 'suspend:rulings')
        with mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            self.cli('status')
        self.assertRegex(out.getvalue(), r'^a  suspend:rulings \(3/6\)  waits on the chat: a.rulings.done  \d+m$')
        self.cli('done', 'a')
        t.join(5)

    def test_wait_returns_once_per_new_point_that_needs_the_chat(self):
        self.add('a')
        t = self.start()
        with mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            self.assertEqual(q.wait(self.rd, 0.2, 0, 0.02), 0)
        self.assertEqual(out.getvalue(), 'a suspend:rulings: write a.rulings.done\n')
        with mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            self.assertEqual(q.wait(self.rd, 0.005, 0, 0.02), 1)
        self.assertNotIn('rulings', out.getvalue())
        self.write('a.rulings.done', 'none')
        with mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            self.assertEqual(self.cli('wait', '--max-min', '0.2', '--settle', '0', '--poll', '0.02'), 0)
        self.assertEqual(out.getvalue(), 'a suspend:merge: write a.merge.done\n')
        self.write('a.merge.done', '')
        t.join(5)

    def test_idle_alert_names_a_suspended_item(self):
        self.add('a')
        old = time.time() - 3600
        os.utime(os.path.join(self.rd, 'heartbeat'), (old, old))
        t = self.start(idle_alert=0.001)
        self.assertTrue(wait_until(lambda: self.notes))
        self.assertIn('a suspend:rulings: write a.rulings.done', self.notes[0])
        self.cli('done', 'a')
        t.join(5)

    def test_review_and_recheck_read_the_briefs_the_item_was_launched_with(self):
        briefs = os.path.join(self.tmp.name, 'briefs')
        os.makedirs(briefs)
        custom = os.path.join(briefs, 'custom.prompt.md')
        with open(custom, 'w') as f:
            f.write('PREAMBLE\nTASK: the custom task\nRISK: paid calls\n')
        self.add('a', FULL, '--brief', custom)
        self.write('a.body.md', 'TASK: a stale task\nRISK: trust boundaries\n')
        os.remove(os.path.join(self.rd, 'a.prompt.md'))
        self.add('b', FULL, '--brief', custom)
        for name in ('b.body.md', 'b.prompt.md'):
            os.remove(os.path.join(self.rd, name))
        t = self.start()
        for i in ('a', 'b'):
            self.at(i, 'suspend:rulings')
            prompt = self.read(f'{i}-review.md')
            self.assertIn('TASK: the custom task', prompt)
            self.assertNotIn('stale', prompt)
            self.assertIn('- Paid calls:', prompt)
            self.assertNotIn('Trust boundaries', prompt)
        self.write('a-fix1.prompt.md', 'PREAMBLE\n' + FIX_BODY.format(id='a'))
        self.write('a-fix1.body.md', 'FIX THESE, one at a time:\n1. A stale finding. Where: `old.py` about 1. Done when: never.\n')
        self.write('a.rulings.done', 'fix 1 and 2\n')
        self.at('a', 'suspend:merge')
        recheck = self.read('a-rereview.md')
        self.assertIn('1. Lost rows on restart.', recheck)
        self.assertNotIn('stale', recheck)
        for i in ('a', 'b'):
            self.cli('done', i)
        t.join(5)

    def test_a_resumed_build_or_fix_hands_its_report_to_the_next_step(self):
        self.add('a')
        self.add('b')
        for rnd in ('a', 'a-fix1', 'b'):
            self.write(f'{rnd}.fake-exit', '3')
        t = self.start()
        for i in ('a', 'b'):
            self.at(i, 'build', 'failed 3')
        self.write('a-resume1.jsonl', report_log('REPORT of a-resume1'))
        self.write('b-resume2.jsonl', report_log('REPORT of b-resume2'))
        self.write('b-resume1.jsonl', report_log('REPORT of b-resume1'))
        with mock.patch('sys.stderr'):
            self.assertEqual(self.cli('retry', 'b', '--passed', '--report', 'b-resume9'), 2)
        self.assertEqual(self.cli('retry', 'a', '--passed'), 0)
        self.assertEqual(self.cli('retry', 'b', '--passed', '--report', 'b-resume2'), 0)
        for i in ('a', 'b'):
            self.at(i, 'suspend:rulings')
            with open(os.path.join(self.items()[i]['worktree'], 'REVIEW-REPORT.md')) as f:
                self.assertEqual(f.read().strip(), f'REPORT of {i}-resume' + ('1' if i == 'a' else '2'))
        self.write('a-fix1.body.md', FIX_BODY.format(id='a'))
        self.write('a.rulings.done', 'fix 1 and 2\n')
        self.at('a', 'fix', 'failed 3')
        self.write('a-fix1-resume1.jsonl', report_log('REPORT of a-fix1-resume1'))
        self.assertEqual(self.cli('retry', 'a', '--passed'), 0)
        self.at('a', 'suspend:merge')
        with open(os.path.join(self.items()['a']['worktree'], 'REVIEW-REPORT.md')) as f:
            self.assertEqual(f.read().strip(), 'REPORT of a-fix1-resume1')
        for i in ('a', 'b'):
            self.cli('done', i)
        t.join(5)


def report_log(text):
    return (json.dumps({'type': 'assistant.message', 'data': {'content': text}}) + '\n'
            + json.dumps({'type': 'result', 'exitCode': 0}) + '\n')


class ReviewPrepTest(unittest.TestCase):
    write, read = PipelineTest.write, PipelineTest.read

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.rd = os.path.join(self.tmp.name, 'run')
        os.makedirs(self.rd)
        self.wt = os.path.join(self.tmp.name, 'wt')
        self.git('init', '-q', '-b', 'ow/a', self.wt, at=None)
        self.commit('README')

    def git(self, *args, at=''):
        import subprocess
        pre = ['git'] + (['-C', self.wt] if at is not None else [])
        return subprocess.run(pre + ['-c', 'core.hooksPath=/dev/null', '-c', 'user.name=t', '-c',
                                     'user.email=t@example.invalid', *args],
                              check=True, capture_output=True, text=True).stdout.strip()

    def commit(self, name):
        with open(os.path.join(self.wt, name), 'w') as f:
            f.write(f'{name} {time.time()}\n')
        self.git('add', name)
        self.git('commit', '-qm', f'feat: {name}')
        return self.git('rev-parse', 'HEAD')

    def built(self, task):
        self.write('a.base', self.git('rev-parse', 'HEAD'))
        self.commit('a.txt')
        self.write('a.prompt.md', 'PREAMBLE\n' + task)
        self.write('a.jsonl', report_log('REPORT of a'))
        return q.reviewprep.review(self.rd, 'a', self.wt)

    def test_inserted_text_is_never_read_as_a_placeholder(self):
        for quoted in ('{{TASK}}', '{{GATES_RUN}}', '{{WORD_LIMIT|900}}'):
            with self.subTest(quoted=quoted):
                task = f'TASK: quote {quoted} in the docs\nRISK: none\n'
                prompt = self.read(os.path.basename(self.built(task)))
                self.assertIn(task.strip(), prompt)
                self.assertEqual(prompt.count('Under 900 words.'), 1)

    def test_findings_after_blank_lines_reach_the_recheck(self):
        self.write('a-fix1.base', self.git('rev-parse', 'HEAD'))
        self.commit('a-fix1.txt')
        self.write('a-fix1.jsonl', report_log('REPORT of a-fix1'))
        self.write('a-fix1.prompt.md', (
            'THIS IS A FIX ROUND.\n\nFIX THESE, one at a time:\n\n'
            '1. First. Where: `one.py` about 1. Done when: one holds.\n\n'
            '2. Second. Where: `two.py` about 2.\n   Done when: two holds.\n\n'
            '3. Third. Where: `three.py` about 3. Done when: three holds.\n\n'
            'NOT TO CHANGE (decided): 4. Not a finding.\n\nREUSE CHECK: not needed.\n'))
        recheck = self.read(os.path.basename(q.reviewprep.recheck(self.rd, 'a', self.wt)))
        self.assertIn('1. First. Where: `one.py` about 1. Done when: one holds.', recheck)
        self.assertIn('2. Second. Where: `two.py` about 2. Done when: two holds.', recheck)
        self.assertIn('3. Third. Where: `three.py` about 3. Done when: three holds.', recheck)
        self.assertNotIn('Not a finding', recheck)
        with open(os.path.join(S, '..', 'assets', 'fix.md')) as f:
            fix = f.read()
        self.assertEqual([n for n, *_ in q.reviewprep.findings(fix.replace('{{MORE_FINDINGS}}', '\n2. B. Where: x. Done when: y.'))],
                         ['1', '2'])


if __name__ == '__main__':
    unittest.main()
