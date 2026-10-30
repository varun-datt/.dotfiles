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
                 'docs-research': ('docs', 'research'), 'review': ('review', 'build'),
                 'rv-a-b': ('a-b', 'review'), 'rr-a': ('a', 'rereview'), 'pm-a': ('a', 'review'), 'rv-': ('rv-', 'build')}
        self.assertEqual({n: mine.split_name(n) for n in cases}, cases)

    def test_active_minutes_leave_out_gaps_over_ten_minutes(self):
        self.run.round('x', minutes=60)
        self.run.round('y', minutes=9, at=T0 + 10000)
        rs = self.run.rounds()
        self.assertEqual((round(rs['x']['wall_min']), round(rs['x']['active_min'], 1)), (60, 0.5))
        self.assertEqual(round(rs['y']['active_min']), 9)


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
                         {'a-review': ('none', 0), 'b-review': ('2 blocking', 2), 'c-review': ('no verdict', None),
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


PRICES = {'big': {'inputPrice': 400, 'outputPrice': 2000, 'cacheReadPrice': 20, 'cacheWritePrice': 500},
          'small': {'inputPrice': 200, 'outputPrice': 1000, 'cacheReadPrice': 10, 'cacheWritePrice': 250}}


def metric_round(run, name, at, model, cum, calls, gaps=(), session='s'):
    """A round whose usage checkpoint carries running token totals; gaps are seconds between model calls."""
    ev, t = [{'type': 'user.message', 'data': {'responsesReasoning': {'model': model, 'effort': 'medium'}},
              'timestamp': stamp(at)}], at
    for g in (0, *gaps):
        t += g
        ev.append({'type': 'model.call_start', 'data': {'model': model}, 'timestamp': stamp(t)})
    usage = {'inputTokens': cum[0] + cum[2] + cum[3], 'outputTokens': cum[1], 'cacheReadTokens': cum[2],
             'cacheWriteTokens': cum[3], 'reasoningTokens': 0}
    snap = {'modelMetrics': {model: {'usage': usage, 'requests': {'count': calls}}}}
    price = PRICES[model]
    credits = sum(n * price[k] for n, k in zip(cum, ('inputPrice', 'outputPrice', 'cacheReadPrice', 'cacheWritePrice'))) / 1e6
    ev.append({'type': 'session.usage_checkpoint', 'data': {'totalNanoAiu': int(credits * 1e9), 'accountingSnapshot': snap},
               'timestamp': stamp(t + 1)})
    ev.append({'type': 'result', 'exitCode': 0, 'sessionId': session, 'timestamp': stamp(t + 2)})
    with open(os.path.join(run.dir, name + '.jsonl'), 'w') as f:
        f.write(''.join(json.dumps(e) + '\n' for e in ev))
    with open(os.path.join(run.dir, name + '.start'), 'w') as f:
        f.write(f'{at}\n')


class MetricsTest(Base):
    def test_usage_is_decumulated_with_calls_and_cold_calls(self):
        metric_round(self.run, 'a', T0, 'big', (10, 20, 1000, 100), 3, gaps=(10, 400))
        metric_round(self.run, 'a-fix1', T0 + 1000, 'big', (15, 50, 3000, 150), 5, gaps=(20,))
        rs = self.run.rounds()
        self.assertEqual((rs['a']['usage']['calls'], rs['a']['cold_calls']), (3, 1))
        self.assertEqual(rs['a-fix1']['usage'], {'input': 5, 'output': 30, 'cache_read': 2000, 'cache_write': 50,
                                                 'reasoning': 0, 'calls': 2})
        self.assertEqual(rs['a-fix1']['cold_calls'], 0)

    def test_prices_split_credits_by_class(self):
        metric_round(self.run, 'a', T0, 'big', (1_000_000, 500_000, 2_000_000, 100_000), 1)
        rs = mine.load_rounds(self.run.dir)
        mine.add_costs(rs, PRICES)
        self.assertEqual(rs[0]['priced'], {'input': 400, 'output': 1000, 'cache_read': 40, 'cache_write': 50})

    def test_prices_file_default_and_override(self):
        self.assertEqual(mine.load_prices(self.run.dir)['claude-opus-5.5']['inputPrice'], 400)
        custom = os.path.join(self.tmp, 'p.json')
        with open(custom, 'w') as f:
            json.dump({'x': {'inputPrice': 1}}, f)
        self.assertEqual(mine.load_prices(self.run.dir, custom), {'x': {'inputPrice': 1}})

    def test_history_rounds_widen_the_caps_window(self):
        old = Run(os.path.join(self.tmp, 'old'))
        for i in range(5):
            old.round(f'i{i}-fix1', at=T0 + i, credits=100, premium=1)
        self.run.round('n-fix1', at=T0 + 9999, credits=100, premium=1)
        out = self.cli(self.run.dir, '--caps', '--history', old.dir).stdout
        self.assertIn('3 x median: median 100, n=6', out)

    def test_derived_cap_uses_the_price_ratio(self):
        rs = []
        for i in range(5):
            r = fake('fix', 'big', 400, i)
            r['usage'] = {'input': 0, 'output': 0, 'cache_read': 1_000_000, 'cache_write': 0}
            rs.append(r)
        rs.append(fake('fix', 'small', 10, 9))
        c = {x['model']: x for x in mine.caps(rs, prices=PRICES)}
        self.assertEqual((c['small']['cap'], c['small']['from']), (600, 'derived from big by price (x0.50)'))
        self.assertEqual(mine.caps(rs)[1]['from'], 'floor (n < 5)')
        self.assertEqual(mine.caps([r for r in rs if r['model'] == 'small'], prices=PRICES)[0]['cap'], 3000)

    def write_chat(self):
        d = os.path.join(self.tmp, 'chat')
        os.makedirs(d)
        with open(os.path.join(d, 'main.jsonl'), 'w') as f:
            for i, o in ((1_000_000, 100_000), (500_000, 0)):
                f.write(json.dumps({'type': 'llm_request', 'attrs': {'model': 'big', 'inputTokens': i, 'cachedTokens': 400_000,
                                                                      'outputTokens': o}}) + '\n')
            f.write('not json\n{"type":"other"}\n')
        return d

    def test_chat_is_priced_as_an_upper_bound(self):
        chat = mine.chat_spend(self.write_chat(), PRICES)
        self.assertEqual((chat['credits'], chat['upper_bound'], chat['models'][0]['calls']), (566.0, True, 2))

    def test_budget_counts_rounds_and_chat_and_how_many_more_fit(self):
        for i in range(5):
            self.run.round(f'i{i}-fix1', at=T0 + i, model='small', credits=100, premium=1)
        p = os.path.join(self.tmp, 'p.json')
        with open(p, 'w') as f:
            json.dump(PRICES, f)
        out = self.cli(self.run.dir, '--caps', '--prices', p, '--chat', self.write_chat(), '--budget', '10000').stdout
        self.assertIn('spend: 1,066 of 10,000 credits (rounds 500 + chat 566 (upper bound)), 8,934 left', out)
        self.assertIn('fix small 89', out)

    def test_cap_evidence_counts_rounds_over_each_candidate(self):
        rs = [fake('fix', 'm', c, i) for i, c in enumerate([100] * 8 + [250, 500])]
        ev = mine.cap_evidence(rs)
        self.assertEqual((ev['rounds'], ev['hit']), (10, {'2x': 2, '3x': 1, '4x': 1, 'p90x1.2': 1}))

    def test_json_and_text_carry_the_usage(self):
        metric_round(self.run, 'a', T0, 'big', (10, 20, 1000, 100), 3, gaps=(400, 5))
        j = json.loads(self.cli(self.run.dir, '--json').stdout)
        self.assertEqual(j['usage'][0]['cold_calls'], 1)
        self.assertEqual(j['rounds'][0]['usage']['calls'], 3)
        self.assertIn('usage by kind and model', self.cli(self.run.dir).stdout)


def append(run, name, *evs):
    with open(os.path.join(run.dir, name + '.jsonl'), 'a', encoding='utf-8') as f:
        f.writelines(json.dumps(e) + '\n' for e in evs)


def message(text, sub=False):
    return {'type': 'assistant.message', 'data': {'content': text, **({'parentToolCallId': 't9'} if sub else {})}}


def tool(cur, limit=200000, sub=False):
    return {'type': 'tool.execution_complete',
            'data': {'toolTelemetry': {'metrics': {'context_current_tokens': cur, 'context_token_limit': limit}},
                     **({'parentToolCallId': 't9'} if sub else {})}}


class LogVerdictTest(Base):
    def test_the_verdict_comes_from_the_last_message_when_no_txt_exists(self):
        for name, msgs in {'a-review': ['Looking.', '**Blocking: none** - INFERRED.\n\ndetails'],
                           'b-review': ['Blocking: none', '## Verdict\n2 blocking\n\n| f | non-blocking |'],
                           'c-review': ['Reading the diff.', 'The diff looks fine.'],
                           'd-review': ['**Verdict: no blocking findings** in the branch.'],
                           'e-review': ['**Verdict: request changes**\n\n**Blocking**\n- one\n  more on one\n- two\n\n'
                                        '**Non-blocking**\n- three']}.items():
            self.run.round(name, credits=1, premium=1)
            append(self.run, name, *[message(m) for m in msgs], message('Blocking: none', sub=True))
        rs = self.run.rounds()
        self.assertEqual({n: (r['verdict'], r['blocking'], r['verdict_source']) for n, r in rs.items()},
                         {'a-review': ('none', 0, 'log'), 'b-review': ('2 blocking', 2, 'log'),
                          'c-review': ('no verdict', None, 'log'), 'd-review': ('none', 0, 'log'),
                          'e-review': ('2 blocking', 2, 'log')})

    def test_a_txt_wins_over_the_log_and_a_review_with_neither_has_no_verdict(self):
        self.run.round('a-review', report='3 blocking\n', credits=1, premium=1)
        append(self.run, 'a-review', message('Blocking: none'))
        self.run.round('b-review', credits=1, premium=1)
        rs = self.run.rounds()
        self.assertEqual((rs['a-review']['verdict'], rs['a-review']['blocking'], rs['a-review']['verdict_source']),
                         ('3 blocking', 3, 'txt'))
        self.assertEqual((rs['b-review']['verdict'], rs['b-review']['blocking'], rs['b-review']['verdict_source']),
                         ('no verdict', None, None))
        self.assertEqual(mine.items(list(rs.values()))[0]['verdicts'][0]['source'], 'txt')

    def test_review_sh_writes_the_verdict_line_for_mine(self):
        bin_dir, wt = os.path.join(self.tmp, 'bin'), os.path.join(self.tmp, 'wt')
        os.makedirs(bin_dir)
        os.makedirs(wt)
        args_file = os.path.join(self.tmp, 'args')
        fake = os.path.join(bin_dir, 'copilot')
        with open(fake, 'w') as f:
            f.write('#!/bin/sh\nprintf "%s\\n" "$@" > ' + args_file + '\n'
                    'printf \'%s\\n\' \'{"type":"assistant.message","data":{"content":"Checked.\\n**1 blocking**: x"}}\'\n'
                    'printf \'%s\\n\' \'{"type":"result","exitCode":0}\'\n')
        os.chmod(fake, 0o755)
        with open(os.path.join(self.run.dir, 'x-review.md'), 'w') as f:
            f.write('review it\n')
        env = {**os.environ, 'PATH': bin_dir + os.pathsep + os.environ['PATH'], 'OW_RUN_DIR': self.run.dir,
               'PYTHONDONTWRITEBYTECODE': '1', 'HOME': self.tmp}
        p = subprocess.run(['bash', os.path.join(HERE, 'review.sh'), '--effort', 'max', 'x-review', wt],
                           capture_output=True, text=True, env=env, timeout=60, stdin=subprocess.DEVNULL)
        self.assertEqual(p.returncode, 0, p.stderr)
        with open(os.path.join(self.run.dir, 'x-review.txt')) as f:
            self.assertEqual(f.read(), '1 blocking\n')
        with open(args_file) as f:
            argv = f.read().split('\n')
        self.assertEqual(argv[argv.index('--reasoning-effort') + 1], 'max')
        r = self.run.rounds()['x-review']
        self.assertEqual((r['blocking'], r['verdict_source']), (1, 'txt'))


class CompactionTest(Base):
    def test_a_context_drop_reads_as_one_compaction(self):
        self.run.round('x', credits=10, premium=1)
        append(self.run, 'x', tool(50000), tool(120000), tool(165000), tool(40000), tool(60000), tool(150000, sub=True),
               tool(10000, sub=True))
        self.run.round('y', at=T0 + 100, credits=10, premium=1)
        append(self.run, 'y', tool(100000), tool(40000), tool(140000), tool(130000))
        rs = self.run.rounds()
        self.assertEqual((rs['x']['compactions'], rs['x']['peak_context'], rs['y']['compactions']), (1, 165000, 0))
        u = {(k['kind'], k['model']): k for k in mine.usage_by_kind(list(rs.values()))}
        self.assertEqual((u[('build', 'claude-opus-5.5')]['compactions'], u[('build', 'claude-opus-5.5')]['compacted_rounds']), (1, 1))
        out = self.cli(self.run.dir).stdout
        self.assertIn('compactions per round: x 1 (peak 165k)', out)
        self.assertIn('  build     claude-opus-5.5           1    1 of 2', out)


def decision(item, kind, at, model='claude-opus-5.5', effort='high', **extra):
    return {'event': 'pick', 'at': stamp(at), 'item': item, 'kind': kind,
            'choice': {'model': model, 'effort': effort, 'context': 'default', 'cap': 100}, **extra}


class AuditTest(Base):
    def write(self, *ds):
        with open(os.path.join(self.run.dir, 'routes.jsonl'), 'w', encoding='utf-8') as f:
            f.writelines(json.dumps(d) + '\n' for d in ds)

    def test_routed_overridden_unrouted_and_a_mismatch(self):
        self.run.round('a', credits=10, premium=1)
        self.run.round('a-review1', at=T0 + 1000, model='gpt-6.1-sol', effort='max', credits=5, premium=1)
        self.run.round('a-fix1', at=T0 + 2000, model='claude-sonnet-5.5', effort='medium', credits=20, premium=2)
        self.run.round('b', at=T0 + 3000, model='claude-sonnet-5.5', effort='high', credits=10, premium=1)
        self.write(decision('a', 'build', T0 - 30),
                   decision('a-review1', 'review', T0 + 990, model='gpt-6.1-sol', effort='high',
                            override={'model': 'gpt-6.1-sol', 'effort': 'max', 'reason': 'risk area'}),
                   decision('a-fix1', 'fix', T0 + 1990, model='claude-sonnet-5.5', effort='high'),
                   decision('c', 'build', T0 + 5000))
        a = mine.audit(mine.load_rounds(self.run.dir), mine.read_decisions(self.run.dir))
        got = {x['name']: (x['status'], x['mismatch']) for x in a['rounds']}
        self.assertEqual(got, {'a': ('routed', []), 'a-review1': ('overridden', []), 'a-fix1': ('routed', ['effort']),
                               'b': ('unrouted', [])})
        self.assertEqual((a['counts'], a['mismatched'], [u['item'] for u in a['unused']]),
                         ({'routed': 2, 'overridden': 1, 'unrouted': 1}, 1, ['c']))
        out = self.cli(self.run.dir, '--audit').stdout
        self.assertIn('4 rounds, 2 routed, 1 overridden, 1 unrouted, 1 differ from their decision', out)
        self.assertIn('MISMATCH effort', out)
        self.assertRegex(out, r'unrouted\s+b\s')

    def test_a_decision_is_used_once_and_never_for_an_earlier_round(self):
        self.run.round('a', credits=10, premium=1)
        self.run.round('a-fix1', at=T0 + 1000, credits=20, premium=2)
        self.run.round('a-fix2', at=T0 + 2000, model='claude-sonnet-5.5', credits=30, premium=3)
        self.write(decision('a-fix', 'fix', T0 + 1500, model='claude-sonnet-5.5'))
        a = mine.audit(mine.load_rounds(self.run.dir), mine.read_decisions(self.run.dir))
        self.assertEqual({x['name']: x['status'] for x in a['rounds']},
                         {'a': 'unrouted', 'a-fix1': 'unrouted', 'a-fix2': 'routed'})

    def test_json_carries_the_audit(self):
        self.run.round('a', credits=10, premium=1)
        j = json.loads(self.cli(self.run.dir, '--json').stdout)
        self.assertEqual(j['audit']['counts'], {'routed': 0, 'overridden': 0, 'unrouted': 1})


STATE = os.path.expanduser('~/.local/state/orchestrator-workers')


@unittest.skipUnless(os.path.isdir(os.path.join(STATE, 'amc-2026-10-29')), 'no real run folders on this machine')
class RealFolderTest(unittest.TestCase):
    def test_every_reviewed_item_of_10_29_has_a_blocking_value(self):
        rounds = mine.load_rounds(os.path.join(STATE, 'amc-2026-10-29'))
        reviewed = {r['item'] for r in rounds if r['kind'] == 'review'}
        self.assertTrue(reviewed)
        self.assertEqual({i['item']: i['blocking'] for i in mine.items(rounds) if i['item'] in reviewed and i['blocking'] is None}, {})

    @unittest.skipUnless(os.path.isdir(os.path.join(STATE, 'amc-2026-10-30')), 'no 10-30 run folder')
    def test_10_30_reports_its_unrouted_rounds(self):
        run = os.path.join(STATE, 'amc-2026-10-30')
        rounds, decisions = mine.load_rounds(run), mine.read_decisions(run)
        a = mine.audit(rounds, decisions)
        decided = {mine.split_name(d.get('item', ''))[0] for d in decisions}
        self.assertEqual(a['counts']['unrouted'], sum(r['item'] not in decided for r in rounds))
        self.assertGreaterEqual(a['counts']['unrouted'], 83)
