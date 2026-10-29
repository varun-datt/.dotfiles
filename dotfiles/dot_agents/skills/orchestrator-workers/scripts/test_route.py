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

    def test_new_feature_floor_wins_over_a_good_cheap_record(self):
        hist = history([rnd(SONNET, True, 'new-feature', 'easy', item=str(i)) for i in range(10)])
        rec = self.pick('build', hist=hist, call=stub('new-feature'))
        self.assertEqual((rec['choice']['model'], rec['choice']['effort']), (OPUS, 'high'))
        self.assertEqual(rec['floor'], 'owner-2026-10-29-new-features')

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

    def test_effort_from_ambiguity_and_verification(self):
        self.assertEqual(self.pick(call=stub('change-existing', amb=2, ver=2))['choice']['effort'], 'medium')
        self.assertEqual(self.pick(call=stub('change-existing', amb=3, ver=2))['choice']['effort'], 'high')
        self.assertEqual(self.pick(call=stub('change-existing', amb=2, ver=4))['choice']['effort'], 'high')

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
        return route.pick('x', 'build', BRIEF, history(), CFG, call=stub('new-feature'), seed=1,
                          budget_left=0.0, run_fraction=0.0)


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
            self.assertEqual(len(lines), 1)
            self.assertIn('ran claude-opus-5.5/high, 900 credits, ok', lines[0])
            self.assertIn('same as table', lines[0])


class Outcome(unittest.TestCase):
    def test_success_needs_no_cap_no_blocking_and_at_most_one_fix(self):
        base = {'kind': 'build', 'capped': False, 'error': False, 'exit': 0}
        self.assertTrue(route.round_ok(base, {'blocking': 0, 'fix_rounds': 1}))
        self.assertFalse(route.round_ok(dict(base, capped=True), {}))
        self.assertFalse(route.round_ok(base, {'blocking': 2, 'fix_rounds': 0}))
        self.assertFalse(route.round_ok(base, {'blocking': 0, 'fix_rounds': 2}))


if __name__ == '__main__':
    unittest.main()
