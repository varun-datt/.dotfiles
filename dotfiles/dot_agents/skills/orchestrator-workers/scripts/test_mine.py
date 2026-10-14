import contextlib, io, json, os, shutil, subprocess, sys, tempfile, time, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mine, result, status  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, 'fixtures', 'capped-round.jsonl')
SCRIPT = os.path.join(HERE, 'mine.py')
T0 = 1_791_900_000


def stamp(epoch):
    return time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime(epoch))


def events(model='claude-opus-5.5', effort='high', credits=None, premium=None, session=None, at=T0, minutes=10,
           ended=True, compact=True):
    """The events of one round; credits and premium are the session's running totals, as the CLI writes them."""
    ev = [{'type': 'session.tools_updated', 'data': {'model': model}, 'timestamp': stamp(at)},
          {'type': 'user.message', 'data': {'content': 'go', 'responsesReasoning': {'model': model, 'effort': effort}},
           'timestamp': stamp(at)},
          {'type': 'assistant.reasoning_delta', 'data': {'deltaContent': '"timestamp":"2001-01-01T00:00:00Z"'},
           'timestamp': stamp(at + 30)}]
    if credits is not None:
        ev.append({'type': 'session.usage_checkpoint', 'data': {'totalNanoAiu': int(credits * 1e9), 'totalPremiumRequests': premium},
                   'timestamp': stamp(at + minutes * 60 - 1)})
    if ended:
        ev.append({'type': 'result', 'timestamp': stamp(at + minutes * 60), 'exitCode': 0,
                   **({'sessionId': session} if session else {})})
    sep = (',', ':') if compact else (', ', ': ')
    return ''.join(json.dumps(e, separators=sep) + '\n' for e in ev)


class Run:
    def __init__(self, folder):
        self.dir = folder
        os.makedirs(folder, exist_ok=True)

    def round(self, name, at=T0, report=None, start=True, **kw):
        with open(os.path.join(self.dir, name + '.jsonl'), 'w', encoding='utf-8') as f:
            f.write(events(at=at, **kw))
        if start:
            with open(os.path.join(self.dir, name + '.start'), 'w') as f:
                f.write(f'{at}\n')
        if report is not None:
            with open(os.path.join(self.dir, name + '.txt'), 'w', encoding='utf-8') as f:
                f.write(report)

    def rounds(self):
        return {r['name']: r for r in mine.load_rounds(self.dir)}


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name
        self.run = Run(os.path.join(self.tmp, 'run'))

    def cli(self, *args, ok=True):
        env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
        p = subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(p.returncode == 0, ok, p.stderr)
        return p


class DecumulateTest(Base):
    def test_a_resumed_session_is_split_into_rounds(self):
        self.run.round('x', credits=100, premium=15, session='A')
        self.run.round('x-fix1', at=T0 + 3600, credits=250, premium=30, session='A')
        self.run.round('x-fix2-resume1', at=T0 + 7200, credits=420.5, premium=45, session='A')
        rs = self.run.rounds()
        self.assertEqual([(rs[n]['kind'], rs[n]['item'], rs[n]['credits'], rs[n]['premium']) for n in ('x', 'x-fix1', 'x-fix2-resume1')],
                         [('build', 'x', 100, 15), ('fix', 'x', 150, 15), ('resume', 'x', 170.5, 15)])

    def test_a_round_without_a_session_id_joins_its_item_session(self):
        self.run.round('x', credits=100, premium=15, session='A')
        self.run.round('x-fix1', at=T0 + 3600, credits=180, premium=30, ended=False)
        self.run.round('x-resume1', at=T0 + 7200, credits=300, premium=45, session='A')
        rs = self.run.rounds()
        self.assertEqual((rs['x-fix1']['credits'], rs['x-resume1']['credits']), (80, 120))

    def test_reviews_are_their_own_sessions(self):
        self.run.round('x', credits=100, premium=15, session='A')
        self.run.round('x-review', at=T0 + 1000, model='gpt-6-astra', credits=50, premium=1, session='B')
        self.run.round('x-fix1', at=T0 + 2000, credits=260, premium=30, session='A')
        self.run.round('x-rereview', at=T0 + 3000, model='gpt-6-astra', credits=30, premium=1)
        self.run.round('y-review', at=T0 + 4000, model='gpt-6-astra', credits=40, premium=1)
        rs = self.run.rounds()
        self.assertEqual({n: rs[n]['credits'] for n in rs}, {'x': 100, 'x-review': 50, 'x-fix1': 160, 'x-rereview': 30, 'y-review': 40})
        self.assertEqual(rs['x-review']['model'], 'gpt-6-astra')

    def test_a_fall_in_the_running_total_starts_again(self):
        self.run.round('x', credits=500, premium=15)
        self.run.round('x-resume1', at=T0 + 3600, credits=120, premium=15)
        self.assertEqual(self.run.rounds()['x-resume1']['credits'], 120)

    def test_a_session_that_starts_mid_item_is_partial_and_left_out_of_caps(self):
        with open(os.path.join(self.run.dir, 'x.start'), 'w') as f:
            f.write(f'{T0 - 3600}\n')
        self.run.round('x-merge2', credits=900, premium=75, session='A')
        self.run.round('x-merge3', at=T0 + 3600, credits=1000, premium=90, session='A')
        rs = self.run.rounds()
        self.assertTrue(rs['x-merge2']['partial'])
        self.assertFalse(rs['x-merge3']['partial'])
        self.assertEqual([(c['kind'], c['n']) for c in mine.caps(list(rs.values()))], [('merge', 1)])

    def test_a_fresh_merge_session_is_whole_and_trains_its_cap(self):
        for i in range(5):
            self.run.round(f'm{i}-catchup', at=T0 + i, credits=400 + i, premium=15, session=f'S{i}')
        self.run.round('m9-merge1', at=T0 + 9, credits=500, premium=15, session='S9')
        rs = self.run.rounds()
        self.assertEqual([n for n, r in rs.items() if r['partial']], [])
        got = {(c['kind'], c['n'], c['from']) for c in mine.caps(list(rs.values()))}
        self.assertEqual(got, {('catchup', 5, '3 x median'), ('merge', 1, 'floor (n < 5)')})

    def test_an_unknown_suffix_inside_a_session_is_other(self):
        self.run.round('x', credits=100, premium=15, session='A')
        self.run.round('x-report2', at=T0 + 3600, credits=110, premium=30, session='A')
        r = self.run.rounds()['x-report2']
        self.assertEqual((r['kind'], r['item'], r['credits']), ('other', 'x', 10))

    def test_model_effort_and_wall_time(self):
        self.run.round('x', model='claude-sonnet-5.5', effort='medium', credits=10, premium=1, minutes=42, compact=False)
        r = self.run.rounds()['x']
        self.assertEqual((r['model'], r['effort'], round(r['wall_min'], 3)), ('claude-sonnet-5.5', 'medium', 42.0))

    def test_names_split_into_item_and_kind(self):
        cases = {'a': ('a', 'build'), 'a-fix1': ('a', 'fix'), 'a-review2': ('a', 'review'), 'a-rereview': ('a', 'rereview'),
                 'a-1-fix3-resume1': ('a-1', 'resume'), 'a-catchup': ('a', 'catchup'), 'a-merge2': ('a', 'merge'),
                 'docs-research': ('docs', 'research'), 'review': ('review', 'build')}
        self.assertEqual({n: mine.split_name(n) for n in cases}, cases)


class VerdictTest(Base):
    def test_verdicts(self):
        header = 'events=10 models=[] result_exit=0\npremium_requests=1 ai_credits=5.0\n' + '-' * 20 + '\n'
        self.run.round('a-review', report=header + '**Blocking: none — INFERRED from static review.**\n', credits=1, premium=1)
        self.run.round('b-review', report=header + '**2 blocking — INFERRED.**\n\n| x | non-blocking |\n', credits=1, premium=1)
        self.run.round('c-review', credits=1, premium=1)
        self.run.round('d-rereview', report=header + '| f.md:4 | marked **non-blocking** |\n1 blocking\n', credits=1, premium=1)
        self.run.round('e-review', report=header + 'The fix is fine.\n', credits=1, premium=1)
        self.run.round('f-rereview', report=header + 'The review found 2 blocking issues; both are fixed.\nBlocking: none\n', credits=1, premium=1)
        rs = self.run.rounds()
        self.assertEqual({n: (rs[n]['verdict'], rs[n]['blocking']) for n in rs},
                         {'a-review': ('none', 0), 'b-review': ('2 blocking', 2), 'c-review': ('missing', None),
                          'd-rereview': ('1 blocking', 1), 'e-review': ('no verdict', None), 'f-rereview': ('none', 0)})

    def test_a_capped_review_is_incomplete_not_none(self):
        self.run.round('x', credits=100, premium=15, session='A')
        self.run.round('x-review', at=T0 + 1000, report='Blocking: none\n', credits=40, premium=1)
        warn = {'type': 'session.warning', 'data': {'message': 'Session limit reached (40/30 AI credits used).'}}
        with open(os.path.join(self.run.dir, 'x-review.jsonl'), 'a', encoding='utf-8') as f:
            f.write(json.dumps(warn) + '\n')
        r = self.run.rounds()['x-review']
        self.assertEqual((r['capped'], r['verdict'], r['blocking'], r['raw_verdict']), (True, 'incomplete', None, 'none'))
        it = mine.items(mine.load_rounds(self.run.dir))[0]
        self.assertEqual((it['blocking'], it['verdicts'][-1]['verdict']), (None, 'incomplete'))
        self.assertIn('-> incomplete', self.cli(self.run.dir).stdout)

    def test_item_summary(self):
        self.run.round('x', credits=100, premium=15, session='A')
        self.run.round('x-review', at=T0 + 1000, report='**3 blocking**\n', credits=50, premium=1)
        self.run.round('x-fix1', at=T0 + 2000, credits=300, premium=30, session='A')
        self.run.round('x-rereview', at=T0 + 3000, report='Blocking: none\n', credits=20, premium=1)
        it = mine.items(mine.load_rounds(self.run.dir))[0]
        self.assertEqual((it['item'], it['rounds'], it['credits'], it['fix_rounds'], it['blocking'], it['merged']),
                         ('x', 4, 370, 1, 3, None))
        self.assertEqual([v['verdict'] for v in it['verdicts']], ['3 blocking', 'none'])


def fake(kind, model, credits, i=0, partial=False):
    return {'kind': kind, 'model': model, 'credits': credits, 'partial': partial, 'start': T0 + i}


class CapsTest(unittest.TestCase):
    def test_floor_below_five_rounds(self):
        rs = [fake('fix', 'm', c, i) for i, c in enumerate([100, 200, 300, 400])]
        self.assertEqual(mine.caps(rs, floor=2500), [{'kind': 'fix', 'model': 'm', 'n': 4, 'median': 250, 'cap': 2500,
                                                      'from': 'floor (n < 5)'}])

    def test_three_times_the_median_from_five_rounds(self):
        rs = [fake('fix', 'm', c, i) for i, c in enumerate([500, 100, 300, 200, 400])]
        c = mine.caps(rs)[0]
        self.assertEqual((c['n'], c['median'], c['cap'], c['from']), (5, 300, 900, '3 x median'))

    def test_only_the_last_twenty_rounds_count(self):
        rs = [fake('review', 'm', 10_000, i) for i in range(20)] + [fake('review', 'm', 100, 100 + i) for i in range(20)]
        c = mine.caps(rs)[0]
        self.assertEqual((c['n'], c['median'], c['cap']), (20, 100, 300))

    def test_per_kind_and_model_and_never_below_the_cli_minimum(self):
        rs = [fake('review', 'a', 5, i) for i in range(5)] + [fake('review', 'b', 50, i) for i in range(5)]
        rs += [fake('fix', 'a', 1, i, partial=True) for i in range(5)] + [fake('other', 'a', 1, i) for i in range(5)]
        self.assertEqual([(c['kind'], c['model'], c['cap']) for c in mine.caps(rs)], [('review', 'a', 30), ('review', 'b', 150)])


class CliTest(Base):
    def test_caps_prints_cap_median_and_n(self):
        for i in range(6):
            self.run.round(f'i{i}-review', at=T0 + i, model='gpt-6-astra', credits=100 + i * 10, premium=1)
        out = self.cli(self.run.dir, '--caps', '--floor', '2000').stdout.splitlines()
        self.assertEqual(out, ['review    gpt-6-astra            --max-ai-credits 375    3 x median: median 125, n=6',
                               'any other kind or model: --max-ai-credits 2000 floor (n < 5)'])

    def test_since_json_and_summary(self):
        day = 86400
        self.run.round('old', credits=100, premium=15)
        self.run.round('new', at=T0 + 3 * day, credits=40, premium=15)
        since = time.strftime('%Y-%m-%d', time.localtime(T0 + 2 * day))
        doc = json.loads(self.cli(self.run.dir, '--json', '--since', since).stdout)
        self.assertEqual([r['name'] for r in doc['rounds']], ['new'])
        self.assertEqual(doc['rounds'][0]['credits'], 40)
        text = self.cli(self.run.dir).stdout
        self.assertIn('2 rounds, 140 credits, 30 premium requests, 0 capped, 0 with unknown credits', text)
        self.assertEqual(self.cli(os.path.join(self.tmp, 'nope'), ok=False).stdout, '')

    def test_markers_are_measured_before_and_after(self):
        for i, c in enumerate([800, 900, 1000]):
            self.run.round(f'a{i}', at=T0 + i, credits=10, premium=15)
            self.run.round(f'a{i}-merge', at=T0 + 100 + i, credits=10 + c, premium=30)
        for i, c in enumerate([400, 500]):
            self.run.round(f'b{i}', at=T0 + 600 + i, credits=10, premium=15)
            self.run.round(f'b{i}-merge', at=T0 + 1000 + i, credits=10 + c, premium=30)
        self.run.round('c-review', at=T0 + 1500, credits=99, premium=1)
        with open(os.path.join(self.run.dir, 'markers.jsonl'), 'w') as f:
            f.write(json.dumps({'at': stamp(T0 + 500), 'label': 'cheaper merges', 'scope': 'merges'}) + '\nnot json\n')
        m = mine.measure(mine.load_markers(self.run.dir), mine.load_rounds(self.run.dir))
        self.assertEqual(len(m), 1)
        self.assertEqual(m[0]['kinds'], [{'kind': 'merge', 'before_n': 3, 'before_median': 900, 'after_n': 2, 'after_median': 450}])
        self.assertEqual(m[0]['saving'], 900)
        self.assertIn("'cheaper merges' [merges]: saving 900; merge 900 (3) -> 450 (2)", self.cli(self.run.dir).stdout)

    def test_merged_from_git_log(self):
        repo = os.path.join(self.tmp, 'repo')
        env = {**os.environ, 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_AUTHOR_NAME': 't',
               'GIT_AUTHOR_EMAIL': 't@example.invalid', 'GIT_COMMITTER_NAME': 't', 'GIT_COMMITTER_EMAIL': 't@example.invalid'}

        def git(*a):
            return subprocess.run(['git', '-C', repo, *a], check=True, capture_output=True, text=True, env=env).stdout
        os.makedirs(repo)
        git('init', '-q', '-b', 'main')
        git('commit', '-q', '--allow-empty', '-m', 'root')
        for branch in ('ow/x', 'ow/x-2'):
            git('checkout', '-q', '-b', branch, 'main')
            git('commit', '-q', '--allow-empty', '-m', 'work on ' + branch)
        git('checkout', '-q', 'main')
        git('merge', '-q', '--no-ff', '-m', "Merge branch 'ow/x-2'", 'ow/x-2')
        git('checkout', '-q', 'ow/x')
        git('merge', '-q', '--no-ff', '-m', "Merge branch 'main' into ow/x", 'main')
        self.assertEqual(git('log', '--merges', '--format=%s', 'ow/x').splitlines(),
                         ["Merge branch 'main' into ow/x", "Merge branch 'ow/x-2'"])
        git('checkout', '-q', 'main')
        with mock.patch.dict(os.environ, env):
            rows = mine.merges(repo)
        self.assertEqual((mine.merged_at('x', rows), mine.merged_at('x-2', rows) is not None), (None, True))
        git('merge', '-q', '--no-ff', '-m', 'Merge ow/x: the item', 'ow/x')
        with mock.patch.dict(os.environ, env):
            rows = mine.merges(repo)
        self.assertEqual([s for _, s in rows], ["Merge branch 'ow/x-2'", 'Merge ow/x: the item'])
        self.assertIsNotNone(mine.merged_at('x', rows))
        self.run.round('x', credits=1, premium=1)
        self.run.round('z', credits=1, premium=1)
        out = self.cli(self.run.dir, '--repo', repo).stdout
        self.assertRegex(out, r'\n  x +1 +1 fix 0 blocking - -> - merged \d{4}-\d\d-\d\d\n')
        self.assertRegex(out, r'\n  z +1 +1 fix 0 blocking - -> - not merged')


class CappedTest(Base):
    def setUp(self):
        super().setUp()
        shutil.copy(FIXTURE, os.path.join(self.run.dir, 'cap.jsonl'))
        with open(os.path.join(self.run.dir, 'cap.start'), 'w') as f:
            f.write(f'{int(time.time()) - 600}\n')
        for p in (mock.patch.object(status, 'RUN', self.run.dir), mock.patch.object(status, 'procs', lambda: set())):
            p.start()
            self.addCleanup(p.stop)

    def test_status_reads_capped_not_done(self):
        rows = status.rows()
        self.assertEqual([(r['name'], r['state']) for r in rows], [('cap', 'CAPPED')])
        self.assertEqual((rows[0]['cap']['used'], rows[0]['cap']['cap']), (32.5, 30))
        line = status.table(rows, only_active=True)
        self.assertIn('32.5/30cr', line)
        self.assertIn('CAPPED at 32.5/30 AI credits', line)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            status.main(['--all'])
        self.assertIn('done=0 capped=1', out.getvalue())

    def test_capped_while_the_process_runs(self):
        with mock.patch.object(status, 'procs', lambda: {'cap'}):
            self.assertEqual(status.rows()[0]['state'], 'CAPPED')

    def test_quoted_limit_text_in_tool_output_is_not_a_cap(self):
        with open(FIXTURE, encoding='utf-8') as f:
            kept = [line for line in f if 'Session limit reached' not in line or '"tool.' in line]
        with open(os.path.join(self.run.dir, 'cap.jsonl'), 'w', encoding='utf-8') as f:
            f.writelines(kept)
        rows = status.rows()
        self.assertEqual(rows[0]['state'], 'done')
        self.assertEqual(rows[0]['cap'], {'used': 27.9, 'cap': 30, 'capped': False})

    def test_only_session_info_and_warning_events_count(self):
        msg = {'message': 'Session limit reached (32.5/30 AI credits used).'}
        self.assertEqual(status.limit_event({'type': 'session.warning', 'data': msg}), (32.5, 30, True))
        for t in ('session.error', 'assistant.message', 'tool.execution_complete', None):
            self.assertIsNone(status.limit_event({'type': t, 'data': msg}), t)

    def test_an_extension_supersedes_the_capped_round(self):
        later = os.path.join(self.run.dir, 'cap-resume1')
        with open(later + '.start', 'w') as f:
            f.write(f'{int(time.time())}\n')
        os.utime(later + '.start', (time.time() + 5, time.time() + 5))
        with open(later + '.jsonl', 'w') as f:
            f.write(json.dumps({'type': 'model.call_start'}) + '\n')
        states = {r['name']: r['state'] for r in status.rows()}
        self.assertEqual(states['cap'], 'superseded')
        self.assertNotIn('done', states.values())

    def test_a_later_review_does_not_hide_an_unextended_cap(self):
        for i, name in enumerate(('cap-review', 'cap-rereview', 'cap-merge1', 'cap-fix1')):
            path = os.path.join(self.run.dir, name)
            with open(path + '.start', 'w') as f:
                f.write(f'{int(time.time())}\n')
            os.utime(path + '.start', (time.time() + 5 + i, time.time() + 5 + i))
            with open(path + '.jsonl', 'w') as f:
                f.write(json.dumps({'type': 'model.call_start'}) + '\n')
            want = 'superseded' if name == 'cap-fix1' else 'CAPPED'
            self.assertEqual({r['name']: r['state'] for r in status.rows()}['cap'], want, name)

    def test_result_prints_capped(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = result.main([os.path.join(self.run.dir, 'cap.jsonl'), '--no-report'])
        self.assertEqual(code, 3)
        self.assertIn(' result_exit=0\noutcome=CAPPED\n', out.getvalue())
        self.assertIn('\nCAPPED at 32.5/30 AI credits: not done', out.getvalue())
        self.run.round('ok', credits=1, premium=1)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(result.main([os.path.join(self.run.dir, 'ok.jsonl'), '--no-report']), 0)
        self.assertIn(' result_exit=0\noutcome=ended\n', out.getvalue())

    def test_mine_marks_the_round_capped(self):
        r = self.run.rounds()['cap']
        self.assertEqual((r['capped'], r['cap'], r['cap_used'], r['credits'], r['model'], r['effort']),
                         (True, 30, 32.5, 32.5, 'claude-opus-5.5', 'high'))


if __name__ == '__main__':
    unittest.main()
