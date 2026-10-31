import json, os, random, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import route

CFG = route.load_config()
SONNET, OPUS, GPT = 'claude-sonnet-5.5', 'claude-opus-5.5', 'gpt-6.1-sol'


def grades(risk=2, amb=2, breadth=2, ver=2, nov=2):
    return {'risk': risk, 'ambiguity': amb, 'breadth': breadth, 'verification': ver, 'novelty': nov}


def stub(category, **g):
    def call(text, kind, cfg):
        return {'source': 'stub', 'category': category,
                'grades': {k: {'grade': v, 'quote': ''} for k, v in grades(**g).items()}}
    return call


def failing(text, kind, cfg):
    raise RuntimeError('no copilot')


def history(rounds=(), caps=None):
    return {'rounds': list(rounds), 'caps': caps or {}}


def rnd(model, ok, category='change-existing', tier='easy', kind='build', item='x'):
    return {'kind': kind, 'category': category, 'tier': tier, 'model': model, 'ok': ok, 'item': item}


BRIEF = 'TASK: Tidy the colour of a diff view (branch `ow/x`)\n\nMUST\n1. Change one colour.\n'


class Pick(unittest.TestCase):
    def pick(self, kind='small', text=BRIEF, hist=None, call=None, **kw):
        kw.setdefault('seed', 1)
        return route.pick('x', kind, text, hist or history(), CFG, call=call or stub('change-existing'), **kw)

    def test_new_feature_has_no_floor_and_follows_a_good_cheap_record(self):
        hist = history([rnd(SONNET, True, 'new-feature', 'easy', item=str(i)) for i in range(10)])
        rec = self.pick('build', hist=hist, call=stub('new-feature'))
        self.assertIsNone(rec['floor'])
        self.assertEqual(rec['choice']['model'], SONNET)

    def test_sessions_ts_floor_but_not_when_out_of_scope(self):
        rec = self.pick(text=BRIEF + 'Change turn handling in src/host/sessions.ts.\n')
        self.assertEqual(rec['choice']['model'], OPUS)
        self.assertEqual(rec['floor'], 'owner-2026-10-29-sessions-ts')
        rec = self.pick(text=BRIEF + 'Files another session is changing, do not edit: src/host/sessions.ts\n')
        self.assertNotEqual(rec['floor'], 'owner-2026-10-29-sessions-ts')

    def test_risk_area_gets_strongest_high_and_review_max_other_family(self):
        text = BRIEF + 'It stores the sign-in token in the session.\n'
        rec = self.pick(text=text)
        self.assertEqual((rec['choice']['model'], rec['choice']['effort'], rec['floor']), (OPUS, 'high', 'risk-area'))
        rec = self.pick('review', text=text, author=OPUS, call=stub('review'))
        self.assertEqual((rec['choice']['model'], rec['choice']['effort']), (GPT, 'max'))

    def test_risk_in_the_diff_counts(self):
        rec = self.pick(diff='+ fs.rmSync(dir); // deletion of the data files\n')
        self.assertEqual(rec['floor'], 'risk-area')

    def test_review_uses_another_family_even_without_risk(self):
        for author, want in ((OPUS, GPT), (GPT, OPUS), (SONNET, GPT)):
            for seed in range(20):
                rec = self.pick('review', call=stub('review'), author=author, seed=seed)
                self.assertNotEqual(route.family(rec['choice']['model'], CFG), route.family(author, CFG))
                self.assertNotEqual(rec['choice']['model'], 'auto')

    def test_never_auto(self):
        for seed in range(30):
            for kind in ('build', 'fix', 'small', 'research', 'merge'):
                rec = self.pick(kind, seed=seed)
                self.assertIn(rec['choice']['model'], (SONNET, OPUS, GPT))

    def test_fallback_when_classifier_fails_is_logged_and_still_picks(self):
        rec = self.pick(call=failing)
        self.assertEqual(rec['classifier']['source'], 'fallback')
        self.assertIn('no copilot', rec['classifier']['fallback_reason'])
        self.assertIn(rec['choice']['model'], (SONNET, OPUS))
        self.assertEqual(rec['static'], {'model': SONNET, 'effort': 'medium'})

    def test_bad_json_and_bad_category_fall_back(self):
        for raw in ('not json', '{"category":"nope","grades":{}}'):
            def call(t, k, c, raw=raw):
                return route.parse_classifier(raw, t, k, c)
            self.assertEqual(self.pick(call=call)['classifier']['source'], 'fallback')

    def test_parse_checks_quote_against_brief(self):
        raw = json.dumps({'category': 'change-existing', 'grades': {
            k: {'grade': 2, 'quote': 'Change one colour'} for k in route.GRADES}})
        out = route.parse_classifier(raw, BRIEF, 'small', CFG)
        self.assertTrue(out['grades']['risk']['quote_found'])

    def test_static_table_beside_choice(self):
        for kind, want in (('fix', (SONNET, 'medium')), ('research', (SONNET, 'medium')), ('build', (OPUS, 'high'))):
            rec = self.pick(kind, call=stub('review-fix' if kind == 'fix' else 'docs-research' if kind == 'research' else 'new-feature'))
            self.assertEqual((rec['static']['model'], rec['static']['effort']), want)

    def test_effort_rule_is_the_prior_and_quality_lifts_it_without_outcomes(self):
        rec = self.pick(call=stub('change-existing', amb=2, ver=2))
        self.assertEqual(rec['rule_effort'], 'medium')
        efforts = {self.pick(call=stub('change-existing', amb=2, ver=2), seed=s)['choice']['effort'] for s in range(20)}
        self.assertEqual(efforts, {'high'})
        self.assertEqual(self.pick(call=stub('change-existing', amb=3, ver=2))['choice']['effort'], 'high')
        self.assertEqual(self.pick(call=stub('change-existing', amb=2, ver=4))['choice']['effort'], 'high')
        good = [dict(rnd(SONNET, True, item=str(i)), effort='medium') for i in range(12)]
        efforts = {self.pick(hist=history(good), seed=s, call=stub('change-existing'))['choice']['effort'] for s in range(20)}
        self.assertEqual(efforts, {'medium'})

    def test_effort_learned_from_outcomes_shares_the_kind(self):
        bad = [dict(rnd(SONNET, False, 'docs-research', 'hard', item=str(i)), effort='medium') for i in range(10)]
        a_bad = route.arm_posterior(bad, 'effort', 'medium', 'build', 'change-existing', 'easy', [3, 1], CFG)
        a_none = route.arm_posterior([], 'effort', 'medium', 'build', 'change-existing', 'easy', [3, 1], CFG)
        self.assertLess(a_bad[0] / (a_bad[0] + a_bad[1]), a_none[0] / (a_none[0] + a_none[1]))
        self.assertEqual((a_bad[2], a_bad[3]), (0, 10))

    def test_floor_effort_wins_over_learned_effort(self):
        good = [dict(rnd(SONNET, True, item=str(i)), effort='medium') for i in range(12)]
        rec = self.pick(hist=history(good), text=BRIEF + 'It stores the sign-in token.\n')
        self.assertEqual(rec['choice']['effort'], 'high')

    def test_quality_rule_picks_stronger_model_with_few_cell_outcomes(self):
        hist = history([rnd(SONNET, True, 'change-existing', 'hard', item=str(i)) for i in range(5)])
        picks = {self.pick(hist=hist, seed=s)['choice']['model'] for s in range(20)}
        self.assertEqual(picks, {OPUS})

    def test_quality_rule_off_only_when_spend_runs_ahead(self):
        hist = history([rnd(SONNET, i < 4, item=str(i)) for i in range(5)])
        on = self.pick(hist=hist, call=stub('change-existing', amb=3), budget_left=0.6, run_fraction=0.4)
        self.assertTrue(on['quality_rule'])
        off = self.pick(hist=hist, call=stub('change-existing', amb=3), budget_left=0.1, run_fraction=0.2)
        self.assertFalse(off['quality_rule'])
        self.assertIn('quality rule off', off['reason'])

    def test_context_default_without_signals_and_considered_with_them(self):
        rec = self.pick()
        self.assertEqual((rec['choice']['context'], rec['context_scores']), ('default', []))
        text = BRIEF + 'Read the full log and search across the whole repository.\n'
        rec = self.pick(text=text)
        self.assertEqual(len(rec['context_scores']), 2)
        self.assertIn(rec['choice']['context'], ('default', 'long_context'))
        good = [dict(rnd(SONNET, True, item=str(i)), context='long_context') for i in range(12)]
        bad = [dict(rnd(SONNET, False, item='b' + str(i)), context='default') for i in range(12)]
        picks = {self.pick(text=text, hist=history(good + bad), seed=s)['choice']['context'] for s in range(20)}
        self.assertEqual(picks, {'long_context'})

    def test_seed_makes_picks_repeatable(self):
        hist = history([rnd(SONNET, i % 2 == 0, item=str(i)) for i in range(6)])
        a = self.pick(hist=hist, seed=7)
        b = self.pick(hist=hist, seed=7)
        self.assertEqual((a['scores'], a['choice']), (b['scores'], b['choice']))

    def test_cap_comes_from_mined_caps_else_default(self):
        rec = self.pick('fix', call=stub('review-fix'), hist=history(caps={('fix', SONNET): 1234, ('fix', OPUS): 1234}))
        self.assertEqual(rec['choice']['cap'], 1234)
        self.assertEqual(self.pick('fix', call=stub('review-fix'))['choice']['cap'], CFG['default_cap'])

    def test_resume_keeps_the_model(self):
        rec = self.pick('resume', call=stub('resume'), resumed_model=OPUS)
        self.assertEqual((rec['choice']['model'], rec['choice']['effort']), (OPUS, 'high'))

    def test_bad_record_pushes_to_the_stronger_model(self):
        hist = history([rnd(SONNET, False, item=str(i)) for i in range(8)])
        picks = {self.pick(hist=hist, seed=s)['choice']['model'] for s in range(30)}
        self.assertEqual(picks, {OPUS})


class Cells(unittest.TestCase):
    def test_widening_cell_then_category_then_kind(self):
        rs = [rnd(SONNET, True, 'change-existing', 'easy', item='a'),
              rnd(SONNET, True, 'change-existing', 'easy', item='b'),
              rnd(SONNET, False, 'change-existing', 'hard', item='c'),
              rnd(SONNET, True, 'docs-research', 'easy', item='d')]
        a, b, n, level = route.posterior(SONNET, 'build', 'change-existing', 'easy', rs, CFG)
        self.assertEqual((level, n), ('category', 3))
        a, b, n, level = route.posterior(SONNET, 'build', 'docs-research', 'easy', rs, CFG)
        self.assertEqual((level, n), ('kind', 4))
        rs += [rnd(SONNET, True, 'change-existing', 'easy', item=x) for x in 'efg']
        self.assertEqual(route.posterior(SONNET, 'build', 'change-existing', 'easy', rs, CFG)[3], 'cell')

    def test_small_maps_to_build_rounds(self):
        rs = [rnd(SONNET, True, item=str(i)) for i in range(3)]
        self.assertEqual(route.posterior(SONNET, 'small', 'change-existing', 'easy', rs, CFG)[3], 'cell')


class Budget(unittest.TestCase):
    def test_target_falls_when_spend_runs_ahead(self):
        base = route.target_for('medium', None, None, CFG)
        on_pace = route.target_for('medium', 0.6, 0.4, CFG)
        ahead = route.target_for('medium', 0.2, 0.4, CFG)
        self.assertEqual(base, on_pace)
        self.assertLess(ahead, base)
        self.assertGreaterEqual(route.target_for('medium', 0.0, 0.0, CFG), CFG['budget']['min_target'])

    def test_lower_target_picks_the_cheaper_model_more_often(self):
        hist = history([rnd(SONNET, i < 3, item=str(i)) for i in range(5)])
        def share(**kw):
            return sum(route.pick('x', 'small', BRIEF, hist, CFG, call=stub('change-existing', amb=3), seed=s, **kw)
                       ['choice']['model'] == SONNET for s in range(300))
        self.assertGreater(share(budget_left=0.1, run_fraction=0.2), share())

    def test_budget_never_lowers_a_floor(self):
        rec = self.pick_floor()
        self.assertEqual(rec['choice']['model'], OPUS)

    def pick_floor(self):
        return route.pick('x', 'build', BRIEF + 'Change turn handling in src/host/sessions.ts.\n', history(), CFG,
                          call=stub('new-feature'), seed=1, budget_left=0.0, run_fraction=0.0)


class Escalate(unittest.TestCase):
    def test_next_model_up_same_effort_and_logged(self):
        with tempfile.TemporaryDirectory() as run:
            rec = route.pick('x', 'small', BRIEF, history(), CFG, call=stub('change-existing'), seed=3)
            rec['choice'] = {'model': SONNET, 'effort': 'medium', 'cap': 100}
            route.log(run, rec)
            up = route.escalate('x', history(), CFG, run)
            route.log(run, up)
            self.assertEqual((up['choice']['model'], up['choice']['effort']), (OPUS, 'medium'))
            top = route.escalate('x', history(), CFG, run)
            self.assertTrue(top['top_of_pool'])
            self.assertEqual(top['choice']['model'], OPUS)
            self.assertEqual(len(route.read_decisions(run)), 2)

    def test_review_escalation_stays_in_other_family(self):
        with tempfile.TemporaryDirectory() as run:
            rec = route.pick('x', 'review', BRIEF, history(), CFG, author=GPT, call=stub('review'), seed=3)
            rec['choice'] = {'model': SONNET, 'effort': 'high', 'cap': 100}
            route.log(run, rec)
            up = route.escalate('x', history(), CFG, run)
            self.assertEqual(up['choice']['model'], OPUS)

    def test_unknown_item_raises(self):
        with tempfile.TemporaryDirectory() as run:
            with self.assertRaises(LookupError):
                route.escalate('nope', history(), CFG, run)


class Report(unittest.TestCase):
    def test_report_lines_show_choice_table_and_outcome(self):
        with tempfile.TemporaryDirectory() as run:
            rec = route.pick('x', 'small', BRIEF + 'sign-in token\n', history(), CFG, call=stub('change-existing'), seed=3)
            route.log(run, rec)
            rounds = [{'item': 'x', 'kind': 'build', 'model': OPUS, 'effort': 'high', 'credits': 900.0, 'capped': False,
                       'error': False, 'exit': 0, 'ended': True}]
            lines = route.report(run, rounds, [{'item': 'x', 'blocking': 0, 'fix_rounds': 0}])
            self.assertEqual(len(lines), 3)
            self.assertIn('ran claude-opus-5.5/high, 900 credits, ok', lines[0])
            self.assertIn('same as table', lines[0])
            self.assertIn('/default/cap', lines[0])
            self.assertTrue(any(ln.startswith('effort high') and '1 ok, 0 failed' in ln for ln in lines))


class EvalClassifier(unittest.TestCase):
    def test_scores_tier_against_outcomes_and_stops_at_credit_limit(self):
        with tempfile.TemporaryDirectory() as d:
            samples = []
            for i, ok in enumerate((True, False, True, False)):
                p = os.path.join(d, f'r{i}.prompt.md')
                with open(p, 'w') as f:
                    f.write(BRIEF + ('hard\n' if not ok else ''))
                samples.append((d, {'name': f'r{i}', 'kind': 'build'}, p, ok))

            def call(text, kind, cfg, model):
                hard = 'hard' in text if model == 'good' else False
                g = 5 if hard else 2
                return {'category': 'change-existing', 'credits': 1.0,
                        'grades': {k: {'grade': g, 'quote': ''} for k in route.GRADES}}
            rows, res, spent = route.eval_classifier(samples, ['good', 'flat'], CFG, 100, call)
            by = {r['model']: r for r in rows}
            self.assertEqual((by['good']['accuracy'], by['good']['balanced']), (1.0, 1.0))
            self.assertEqual(by['flat']['balanced'], 0.5)
            self.assertEqual(by['flat']['agreement'], 0.5)
            self.assertEqual(spent, 8.0)
            rows, res, spent = route.eval_classifier(samples, ['good', 'flat'], CFG, 5, call)
            self.assertEqual(spent, 4.0)

    def test_classifier_pool_in_config(self):
        self.assertIn(CFG['classifier']['model'], CFG['classifier']['pool'])
        self.assertNotIn('auto', CFG['classifier']['pool'])


FAKE = r'''#!/usr/bin/env python3
import json, os, sys, time
a = sys.argv[1:]
if a == ['--version']:
    print('9.9.9-fake')
    sys.exit(0)
with open(os.environ['FAKE_ARGS'], 'w') as f:
    json.dump(a, f)
mode = os.environ.get('FAKE_MODE', 'ok')
if mode == 'sleep':
    time.sleep(60)
def ev(t, **kw):
    print(json.dumps({'type': t, 'timestamp': '2026-10-30T12:00:00.000Z', **kw}, separators=(',', ':')))
ev('user.message', data={'content': 'go', 'responsesReasoning': {'model': a[a.index('--model') + 1],
                                                                'effort': a[a.index('--reasoning-effort') + 1]}})
if mode == 'capped':
    ev('session.warning', data={'message': 'Session limit reached (40/30 AI credits used).'})
if mode == 'error':
    ev('session.error', data={'message': 'boom'})
ev('assistant.message', data={'content': 'Done.\nBlocking: none'})
ev('result', exitCode=0)
sys.exit(1 if mode == 'fail' else 0)
'''


class Launcher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(__import__('shutil').rmtree, self.tmp, True)
        self.run_dir, self.wt, b = (os.path.join(self.tmp, x) for x in ('run', 'wt', 'bin'))
        for d in (self.run_dir, self.wt, b, os.path.join(self.tmp, 'hist')):
            os.makedirs(d)
        with open(os.path.join(b, 'copilot'), 'w') as f:
            f.write(FAKE)
        os.chmod(os.path.join(b, 'copilot'), 0o755)
        git = ['git', '-C', self.wt, '-c', 'user.name=t', '-c', 'user.email=t@example.com']
        import subprocess
        self.sp = subprocess
        subprocess.run(['git', 'init', '-q', self.wt], check=True, stdin=subprocess.DEVNULL)
        subprocess.run(git + ['commit', '-q', '--allow-empty', '-m', 'base'], check=True, stdin=subprocess.DEVNULL)
        self.head = subprocess.run(['git', '-C', self.wt, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout
        self.args = os.path.join(self.tmp, 'args.json')
        self.env = {**os.environ, 'PATH': b + os.pathsep + os.environ['PATH'], 'HOME': self.tmp, 'FAKE_ARGS': self.args,
                    'PYTHONDONTWRITEBYTECODE': '1', 'OW_STATE_ROOT': os.path.join(self.tmp, 'hist')}
        self.env.pop('OW_RUN_DIR', None)
        self.brief = os.path.join(self.tmp, 'brief.md')
        with open(self.brief, 'w') as f:
            f.write(BRIEF + 'TIME BUDGET: 20\n')

    def launch(self, rnd='x', kind='small', *extra, mode='ok'):
        cmd = [sys.executable, '-B', os.path.join(HERE, 'route.py'), 'run', rnd, '--kind', kind, '--run', self.run_dir,
               '--brief', self.brief, '--worktree', self.wt, '--no-classifier', '--seed', '1', '--load-wait', '0', *extra]
        return self.sp.run(cmd, capture_output=True, text=True, env={**self.env, 'FAKE_MODE': mode}, timeout=120,
                           stdin=self.sp.DEVNULL)

    def decisions(self):
        return [d for d in route.read_decisions(self.run_dir) if d.get('event') not in ('launch', 'refuse')]

    def argv(self):
        with open(self.args) as f:
            return json.load(f)

    def audit(self):
        p = self.sp.run([sys.executable, '-B', os.path.join(HERE, 'mine.py'), self.run_dir, '--audit'],
                        capture_output=True, text=True, env=self.env, timeout=120, stdin=self.sp.DEVNULL)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def test_run_launches_exactly_the_logged_decision_and_audits_as_routed(self):
        p = self.launch()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        [d] = self.decisions()
        c, argv = d['choice'], self.argv()
        self.assertEqual((d['cli_version'], d['model_id']), ('9.9.9-fake', c['model']))
        for flag, val in (('--model', c['model']), ('--reasoning-effort', c['effort']), ('--context', c['context']),
                          ('--max-ai-credits', str(c['cap'])), ('-C', self.wt), ('--output-format', 'json')):
            self.assertEqual(argv[argv.index(flag) + 1], val)
        for flag in ('--no-ask-user', '--disable-builtin-mcps', 'shell(git push)'):
            self.assertIn(flag, argv)
        with open(self.brief) as f:
            self.assertEqual(argv[argv.index('-p') + 1], f.read())
        launch = [x for x in route.read_decisions(self.run_dir) if x.get('event') == 'launch']
        self.assertEqual(launch[0]['argv'], ['copilot'] + argv[:-1])
        with open(os.path.join(self.run_dir, 'x.base')) as f:
            self.assertEqual(f.read(), self.head)
        self.assertTrue(os.path.exists(os.path.join(self.run_dir, 'x.start')))
        with open(os.path.join(self.run_dir, 'budgets.json')) as f:
            self.assertEqual(json.load(f)['x'], 20)
        self.assertIn('1 routed, 0 overridden, 0 unrouted, 0 differ', self.audit())

    def test_override_logs_its_reason_cap_none_drops_the_cap_and_audits_as_overridden(self):
        p = self.launch('x', 'research', '--override', f'model={GPT},effort=max,cap=none,reason=owner rules research uncapped')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        [d] = self.decisions()
        self.assertEqual(d['override'], {'model': GPT, 'effort': 'max', 'cap': None, 'reason': 'owner rules research uncapped'})
        self.assertEqual((d['choice']['model'], d['choice']['effort'], d['choice']['cap']), (GPT, 'max', None))
        self.assertIn('routed_choice', d)
        argv = self.argv()
        self.assertEqual(argv[argv.index('--model') + 1], GPT)
        self.assertNotIn('--max-ai-credits', argv)
        self.assertIn('0 routed, 1 overridden, 0 unrouted, 0 differ', self.audit())

    def test_an_override_without_a_reason_is_refused_before_anything_is_logged(self):
        for spec in (f'model={GPT},effort=high', f'model={GPT},reason=', 'reason=just because', 'model=auto,reason=x',
                     'cap=0,reason=x'):
            p = self.launch('x', 'small', '--override', spec)
            self.assertEqual(p.returncode, 2, spec)
            self.assertIn('override refused', p.stderr)
        self.assertEqual(route.read_decisions(self.run_dir), [])
        self.assertFalse(os.path.exists(self.args))

    def test_review_reads_the_missing_author_model_from_the_round_log(self):
        with open(os.path.join(self.run_dir, 'x.jsonl'), 'w') as f:
            f.write(json.dumps({'type': 'user.message', 'data': {'responsesReasoning': {'model': OPUS, 'effort': 'high'}}},
                               separators=(',', ':')) + '\n')
        p = self.launch('x-review', 'review')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        [d] = self.decisions()
        self.assertEqual((d['inputs']['author_model'], d['inputs']['author_source']), (OPUS, 'log:x.jsonl'))
        self.assertNotEqual(route.family(d['choice']['model'], CFG), route.family(OPUS, CFG))
        self.assertIn('--deny-tool=url', self.argv())

    def test_a_failed_capped_errored_or_timed_out_round_exits_non_zero(self):
        for rnd, mode, extra, code in (('a', 'fail', (), 1), ('b', 'capped', (), 3), ('c', 'error', (), 4),
                                       ('d', 'sleep', ('--timeout', '2'), 124)):
            p = self.launch(rnd, 'small', *extra, mode=mode)
            self.assertEqual(p.returncode, code, (mode, p.stdout, p.stderr))

    def test_run_checks_the_brief_against_the_worktree_debt_register_and_still_launches(self):
        os.makedirs(os.path.join(self.wt, 'src'))
        os.makedirs(os.path.join(self.wt, 'docs'))
        with open(os.path.join(self.wt, 'src', 'a.ts'), 'w') as f:
            f.write('x\n')
        with open(os.path.join(self.wt, 'docs', 'tech-debt.md'), 'w') as f:
            f.write('| Id | Date | Area | Grade | File | Scenario | Source | Minutes | Status |\n'
                    '| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n'
                    '| TD-7 | 2026-10-01 | a | Minor | src/a.ts | made-up scenario | r1 | 5 | open |\n')
        with open(self.brief, 'a') as f:
            f.write('Change `src/a.ts`.\n')
        p = self.launch()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('warning: TD-7 is open on src/a.ts', p.stderr)
        self.assertTrue(os.path.exists(self.args))

    def test_add_dir_is_taken_any_number_of_times(self):
        p = self.launch('x', 'small', '--add-dir', '/tmp/one', '--add-dir', '/tmp/two')
        self.assertEqual(p.returncode, 0, p.stderr)
        argv = self.argv()
        self.assertEqual([argv[i + 1] for i, v in enumerate(argv) if v == '--add-dir'], ['/tmp/one', '/tmp/two'])

    def test_concurrent_writers_keep_shared_files_whole(self):
        import threading
        bad = []
        stop = threading.Event()

        def reader():
            path = os.path.join(self.run_dir, 'budgets.json')
            while not stop.is_set():
                try:
                    with open(path) as f:
                        json.load(f)
                except FileNotFoundError:
                    pass
                except ValueError as ex:
                    bad.append(ex)

        def writer(i):
            route.set_budget(self.run_dir, f'r{i}', 'build', f'TIME BUDGET: {i + 1}\n' + 'x' * 20000)
            route.log(self.run_dir, {'event': 'pick', 'item': f'r{i}', 'pad': 'y' * 20000})
        r = threading.Thread(target=reader)
        r.start()
        ws = [threading.Thread(target=writer, args=(i,)) for i in range(30)]
        for w in ws:
            w.start()
        for w in ws:
            w.join()
        stop.set()
        r.join()
        self.assertEqual(bad, [])
        with open(os.path.join(self.run_dir, 'budgets.json')) as f:
            self.assertEqual(json.load(f), {f'r{i}': i + 1 for i in range(30)})
        self.assertEqual(len(route.read_decisions(self.run_dir)), 30)
        self.assertEqual([f for f in os.listdir(self.run_dir) if f.startswith('.budgets')], [])

    def test_a_numeric_cap_override_is_logged_and_passed(self):
        p = self.launch('x', 'small', '--override', 'cap=77,reason=owner caps this one')
        self.assertEqual(p.returncode, 0, p.stderr)
        [d] = self.decisions()
        self.assertEqual((d['override'], d['choice']['cap']), ({'cap': 77, 'reason': 'owner caps this one'}, 77))
        argv = self.argv()
        self.assertEqual(argv[argv.index('--max-ai-credits') + 1], '77')

    def test_each_configured_mcp_server_is_disabled(self):
        os.makedirs(os.path.join(self.tmp, '.copilot'))
        with open(os.path.join(self.tmp, '.copilot', 'mcp-config.json'), 'w') as f:
            json.dump({'mcpServers': {'alpha': {}, 'beta': {}}}, f)
        self.assertEqual(self.launch().returncode, 0)
        argv = self.argv()
        self.assertEqual([argv[i + 1] for i, v in enumerate(argv) if v == '--disable-mcp-server'], ['alpha', 'beta'])

    def test_load_wait_and_leftovers_sweep_are_called(self):
        from unittest import mock
        calls = []
        args = ['run', 'x', '--kind', 'small', '--run', self.run_dir, '--brief', self.brief, '--worktree', self.wt,
                '--no-classifier', '--seed', '1', '--history-root', self.env['OW_STATE_ROOT']]
        with mock.patch.dict(os.environ, self.env, clear=True), \
                mock.patch.object(route, 'sweep', side_effect=lambda *a: calls.append(a) or 0), \
                mock.patch('sys.stdout'):
            self.assertEqual(route.main(args), 0)
        self.assertEqual(calls, [('load', '--wait', '15'), ('leftovers', self.wt, '--kill')])
        calls.clear()
        with mock.patch.dict(os.environ, self.env, clear=True), \
                mock.patch.object(route, 'sweep', side_effect=lambda *a: calls.append(a) or 1), \
                mock.patch('sys.stdout'), mock.patch('sys.stderr'):
            self.assertEqual(route.main(args[:1] + ['y'] + args[2:]), 12)
        self.assertEqual(calls, [('load', '--wait', '15')])

    def author_log(self, model):
        with open(os.path.join(self.run_dir, 'x.jsonl'), 'w') as f:
            f.write(json.dumps({'type': 'user.message', 'data': {'responsesReasoning': {'model': model, 'effort': 'high'}}},
                               separators=(',', ':')) + '\n')

    def refusals(self):
        return [d for d in route.read_decisions(self.run_dir) if d.get('event') == 'refuse']

    def test_a_same_family_review_override_is_refused_unless_it_is_the_422_fallback(self):
        self.author_log(OPUS)
        p = self.launch('x-review', 'review', '--override', f'model={OPUS},effort=max,reason=owner wants opus')
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertFalse(os.path.exists(self.args))
        self.assertEqual([(r['round'], r['model'], r['author_model']) for r in self.refusals()], [('x-review', OPUS, OPUS)])
        self.assertEqual(self.decisions(), [])
        p = self.launch('x-review', 'review', '--override', f'model={OPUS},effort=max,same_family=yes,reason=422 from gpt')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        [d] = [x for x in self.decisions() if x.get('event') == 'pick']
        self.assertTrue(d['override']['same_family'])
        self.assertEqual(self.argv()[self.argv().index('--model') + 1], OPUS)
        out = self.audit()
        self.assertIn('0 routed, 1 overridden', out)
        self.assertIn('"same_family": true', out)
        for spec in (f'model={OPUS},same_family=no,reason=x', 'same_family=yes,reason=x'):
            self.assertEqual(self.launch('x-review', 'review', '--override', spec).returncode, 2, spec)

    def test_a_reused_review_decision_keeps_its_saved_author_for_the_family_check(self):
        pick = [sys.executable, '-B', os.path.join(HERE, 'route.py'), 'pick', '--run', self.run_dir, '--item', 'x-review',
                '--kind', 'review', '--prompt', self.brief, '--no-classifier', '--seed', '1', '--author-model', OPUS]
        self.assertEqual(self.sp.run(pick, capture_output=True, env=self.env, stdin=self.sp.DEVNULL).returncode, 0)
        [d] = self.decisions()
        self.assertEqual((d['cli_version'], d['model_id'], d['inputs']['author_model']), ('9.9.9-fake', GPT, OPUS))
        p = self.launch('x-review', 'review', '--override', f'model={OPUS},effort=max,reason=owner wants opus')
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertFalse(os.path.exists(self.args))
        self.assertEqual([(r['model'], r['author_model']) for r in self.refusals()], [(OPUS, OPUS)])
        self.author_log(GPT)
        p = self.sp.run(pick[:-2], capture_output=True, text=True, env=self.env, stdin=self.sp.DEVNULL)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        p = self.launch('x-review', 'review', '--fresh')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(route.family(self.argv()[self.argv().index('--model') + 1], CFG), route.family(OPUS, CFG))

    def test_a_review_whose_author_is_unknown_is_refused_without_same_family_yes(self):
        p = self.launch('x-review', 'review')
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertFalse(os.path.exists(self.args))
        self.assertEqual([(r['author_model'], r['reason']) for r in self.refusals()],
                         [(None, 'review whose author model is unknown')])
        self.assertEqual(self.decisions(), [])
        p = self.launch('x-review', 'review', '--override', f'model={GPT},same_family=yes,reason=author log lost')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(self.argv()[self.argv().index('--model') + 1], GPT)
        import mine
        [d] = [x for x in mine.read_decisions(self.run_dir) if x.get('event') == 'pick']
        self.assertEqual((d['_launch']['cli_version'], d['_launch']['model_id']), ('9.9.9-fake', GPT))

    def test_rerunning_pick_or_run_reuses_an_unlaunched_decision_and_fresh_draws_again(self):
        pick = [sys.executable, '-B', os.path.join(HERE, 'route.py'), 'pick', '--run', self.run_dir, '--item', 'x',
                '--kind', 'small', '--prompt', self.brief, '--no-classifier']
        for _ in range(2):
            self.assertEqual(self.sp.run(pick, capture_output=True, env=self.env, stdin=self.sp.DEVNULL).returncode, 0)
        self.assertEqual(len(self.decisions()), 1)
        self.assertEqual(self.launch().returncode, 0)
        self.assertEqual(len(self.decisions()), 1)
        self.assertEqual(self.launch().returncode, 0)
        self.assertEqual(len(self.decisions()), 2)
        self.sp.run(pick, capture_output=True, env=self.env, stdin=self.sp.DEVNULL)
        self.sp.run(pick + ['--fresh'], capture_output=True, env=self.env, stdin=self.sp.DEVNULL)
        self.assertEqual(len(self.decisions()), 4)


class Outcome(unittest.TestCase):
    def test_success_needs_no_cap_no_blocking_and_at_most_one_fix(self):
        base = {'kind': 'build', 'capped': False, 'error': False, 'exit': 0}
        self.assertTrue(route.round_ok(base, {'blocking': 0, 'fix_rounds': 1}))
        self.assertFalse(route.round_ok(dict(base, capped=True), {}))
        self.assertFalse(route.round_ok(base, {'blocking': 2, 'fix_rounds': 0}))
        self.assertFalse(route.round_ok(base, {'blocking': 0, 'fix_rounds': 2}))


if __name__ == '__main__':
    unittest.main()
