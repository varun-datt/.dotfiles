import csv, io, contextlib, json, os, subprocess, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kappa, mine, rule, sample  # noqa: E402
from test_mine import Run, T0  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def quiet(fn, *a):
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()) as out:
        code = fn(*a)
    return code, out.getvalue()


class Tmp(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.tmp = t.name
        self.run = Run(os.path.join(self.tmp, 'run'))

    def rows(self):
        with open(os.path.join(self.run.dir, 'rulings.jsonl'), encoding='utf-8') as f:
            return [json.loads(x) for x in f]


class RuleTest(Tmp):
    def add(self, round_='a-review', grade='Major', ruled='Minor', reason='why'):
        return quiet(rule.main, ['add', self.run.dir, round_, '1', '--grade', grade, '--ruled', ruled,
                                 '--by', 'orch', '--reason', reason, '--area', 'COR'])[0]

    def test_first_and_second_add_append(self):
        self.run.round('a-review')
        self.assertEqual(self.add(), 0)
        self.assertEqual(self.add(ruled='rejected', reason='say "no"\nsecond line'), 0)
        rows = self.rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual({k: v for k, v in rows[0].items() if k != 'at'},
                         {'round': 'a-review', 'n': 1, 'grade': 'Major', 'ruled': 'Minor', 'by': 'orch',
                          'reason': 'why', 'area': 'COR'})
        self.assertEqual(rows[1]['reason'], 'say "no"\nsecond line')
        self.assertTrue(rows[0]['at'])

    def test_refusals_write_nothing(self):
        self.run.round('a-review')
        self.assertNotEqual(self.add(round_='b-review'), 0)
        self.assertNotEqual(self.add(reason='  '), 0)
        self.assertFalse(os.path.exists(os.path.join(self.run.dir, 'rulings.jsonl')))

    def test_path_separator_refused(self):
        self.run.round('a-review')
        self.assertNotEqual(self.add(round_='../run/a-review'), 0)
        with self.assertRaises(SystemExit):
            quiet(rule.main, ['add', self.run.dir, 'a-review', '1', '--grade', 'Huge', '--ruled', 'Minor',
                              '--by', 'o', '--reason', 'r'])
        with self.assertRaises(SystemExit):
            quiet(rule.main, ['add', self.run.dir, 'a-review', '1', '--grade', 'Major', '--ruled', 'maybe',
                              '--by', 'o', '--reason', 'r'])
        self.assertFalse(os.path.exists(os.path.join(self.run.dir, 'rulings.jsonl')))


def ruling(f, round_, grade, ruled, area='COR'):
    f.write(json.dumps({'round': round_, 'n': 1, 'grade': grade, 'ruled': ruled, 'by': 'o', 'reason': 'r',
                        'area': area}) + '\n')


class RulingsTest(Tmp):
    def test_kinds_rereview_and_orphan(self):
        self.run.round('a', credits=10, session='s1')
        self.run.round('a-review', at=T0 + 700, model='gpt-x', credits=5, session='r1')
        self.run.round('rv-b', at=T0 + 900, model='gpt-x', credits=5, session='r2')
        self.run.round('a-rereview', at=T0 + 1200, model='gpt-x', credits=5, session='r3')
        with open(os.path.join(self.run.dir, 'rulings.jsonl'), 'w') as f:
            ruling(f, 'a-review', 'Major', 'Major')
            ruling(f, 'rv-b', 'Major', 'Minor')
            ruling(f, 'a-rereview', 'Minor', 'Blocker', area='SEC')
            ruling(f, 'gone-review', 'Major', 'rejected')
        rs = mine.load_rounds(self.run.dir)
        g = mine.rulings(mine.read_rulings(self.run.dir), rs)
        self.assertEqual(g['model']['gpt-x'], {'accepted': 1, 'demoted': 1, 'promoted': 1})
        self.assertEqual(g['area']['SEC'], {'promoted': 1})
        self.assertEqual([o['round'] for o in g['orphans']], ['gone-review'])
        self.assertEqual(g['odd'], [])
        text = mine.rulings_text(self.run.dir, mine.read_rulings(self.run.dir), rs)
        self.assertIn('orphan: gone-review', text)
        self.assertIn('accepted 1 (33%)', text)

    def test_rejected_and_not_reproduced(self):
        self.assertEqual(mine.ruling_kind({'grade': 'Major', 'ruled': 'rejected'}), 'rejected')
        self.assertEqual(mine.ruling_kind({'grade': 'Major', 'ruled': 'not-reproduced'}), 'not-reproduced')

    def test_no_rulings_file(self):
        self.run.round('a-review')
        code, out = quiet(mine.main, [self.run.dir, '--rulings'])
        self.assertEqual(code, 0)
        self.assertIn('no rulings', out)


class QualityTest(Tmp):
    def test_first_reviews_clean_rates_and_causes(self):
        r = self.run
        r.round('a', credits=60, session='sa')
        r.round('a-review', at=T0 + 700, credits=20, session='ra',
                report='2 blocking\n| x | blocking | ADJ | other caller | f:1 | fix |\ncause: EDGE\n')
        r.round('a-fix', at=T0 + 1400, credits=80, session='sa')
        r.round('rv-a', at=T0 + 2100, credits=10, session='ra2', report='Blocking: none\n')
        r.round('b', at=T0 + 3000, credits=50, session='sb')
        r.round('b-review', at=T0 + 3700, credits=10, session='rb', report='Blocking: none\n')
        r.round('c', at=T0 + 4000, credits=50, session='sc')
        r.round('c-review', at=T0 + 4700, credits=10, session='rc', report='looks fine to me\n')
        with open(os.path.join(r.dir, 'rulings.jsonl'), 'w') as f:
            ruling(f, 'a-review', 'Major', 'Minor')
            ruling(f, 'a-review', 'Major', 'rejected')
        rs = mine.load_rounds(r.dir)
        mine.add_costs(rs, mine.load_prices(r.dir))
        q = mine.quality(r.dir, rs, mine.read_rulings(r.dir))
        firsts = {f['item']: f for f in q['first_reviews']}
        self.assertEqual(q['n'], 3)
        self.assertEqual(firsts['a']['round'], 'a-review')
        self.assertEqual(firsts['c']['verdict'], 'no verdict')
        self.assertEqual((q['clean_reviewer'], q['no_verdict']), (1, 1))
        self.assertEqual(firsts['a']['ruled_blocking'], 0)
        self.assertEqual((q['clean_orchestrator'], q['unruled']), (2, 1))
        self.assertEqual(q['blockers_per_review'], 0.0)
        self.assertEqual((q['fix_rounds_per_item'], q['looped_items']), (1.0, 1))
        self.assertEqual(round(q['review_fix_share'], 3), round(70 / 230, 3))
        self.assertEqual(dict(q['causes']), {'ADJ': 1, 'EDGE': 1, 'untagged': 3})
        self.assertEqual(dict(q['classes']), {'other caller': 1})
        self.assertIn('first reviews: 3', mine.quality_text(q))

    def test_accepted_file_and_fix_brief(self):
        r = self.run
        r.round('a', credits=10, session='sa')
        r.round('a-review', at=T0 + 700, credits=5, session='ra', report='1 blocking\n')
        r.round('b', at=T0 + 800, credits=10, session='sb')
        r.round('b-review', at=T0 + 1500, credits=5, session='rb', report='2 blocking\n')
        r.round('b-fix', at=T0 + 2200, credits=5, session='sb')
        with open(os.path.join(r.dir, 'a.accepted'), 'w') as f:
            f.write('none\n')
        with open(os.path.join(r.dir, 'b-fix.md'), 'w') as f:
            f.write('Fix.\nACCEPTED, fix these:\n- one\n- two\n\nOther.\n')
        firsts = {f['item']: f for f in mine.quality(r.dir, mine.load_rounds(r.dir), None)['first_reviews']}
        self.assertEqual((firsts['a']['ruled_blocking'], firsts['a']['ruled_source']), (0, 'accepted'))
        self.assertEqual((firsts['b']['ruled_blocking'], firsts['b']['ruled_source']), (2, 'fix brief'))


class SampleTest(Tmp):
    def write(self, rows):
        path = os.path.join(self.tmp, 'f.csv')
        with open(path, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['area', 'finding', 'severity_today', 'accepted'])
            w.writerows(rows)
        return path

    def go(self, path, n, seed=7, out='o'):
        out = os.path.join(self.tmp, out)
        code, text = quiet(sample.main, [path, '--n', str(n), '--strata', 'area', '--seed', str(seed), '--out', out])
        self.assertEqual(code, 0)
        with open(os.path.join(out, 'sheet.csv'), newline='') as f:
            sheet = list(csv.DictReader(f))
        with open(os.path.join(out, 'key.csv'), newline='') as f:
            key = list(csv.DictReader(f))
        return sheet, key, out

    def test_strata_blind_and_key(self):
        rows = [['SEC', f'leak, "quoted"\nline {i}', 'Major', 'yes'] for i in range(10)]
        rows += [['UX', f'ux {i}', 'Minor', 'no'] for i in range(5)] + [['DOC', 'only one', 'Nit', 'no']]
        sheet, key, _ = self.go(self.write(rows), 8)
        self.assertEqual(len(sheet), 8)
        self.assertEqual(list(sheet[0]), ['id', 'text'])
        self.assertEqual([s['id'] for s in sheet], [f'S{i}' for i in range(1, 9)])
        self.assertTrue(any('\n' in s['text'] and '"' in s['text'] for s in sheet))
        self.assertTrue(all(k['source_id'].isdigit() for k in key))
        counts = {a: sum(k['area'] == a for k in key) for a in ('SEC', 'UX', 'DOC')}
        for a, total in (('SEC', 10), ('UX', 5), ('DOC', 1)):
            self.assertLessEqual(abs(counts[a] - 8 * total / 16), 1, counts)
        self.assertEqual([k['id'] for k in key], [s['id'] for s in sheet])
        self.assertTrue(all(k['severity_today'] for k in key))

    def test_n_larger_and_same_seed(self):
        path = self.write([['A', f'x{i}', 'Major', 'y'] for i in range(3)] + [['B', 'y', 'Minor', 'n']])
        sheet, _, _ = self.go(path, 40)
        self.assertEqual(len(sheet), 4)
        _, _, o1 = self.go(path, 2, seed=5, out='o1')
        _, _, o2 = self.go(path, 2, seed=5, out='o2')
        with open(os.path.join(o1, 'sheet.csv')) as f1, open(os.path.join(o2, 'sheet.csv')) as f2:
            self.assertEqual(f1.read(), f2.read())

    def test_allocate_within_one(self):
        for counts in ({'a': 48, 'b': 39, 'c': 1, 'd': 2}, {'x': 1, 'y': 1, 'z': 1}):
            alloc = sample.allocate(counts, 2 if len(counts) == 3 else 40)
            n = sum(alloc.values())
            for k, c in counts.items():
                self.assertLess(abs(alloc[k] - n * c / sum(counts.values())), 1)


class KappaTest(Tmp):
    def sheet(self, name, grades):
        path = os.path.join(self.tmp, name)
        with open(path, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['id', 'g'])
            w.writerows(grades)
        return path

    def test_hand_computed(self):
        # po = 0.7, pe = 0.6*0.5 + 0.4*0.5 = 0.5, kappa = 0.4
        a = ['Y'] * 6 + ['N'] * 4
        b = ['Y'] * 4 + ['N'] * 2 + ['Y'] + ['N'] * 3
        po, k = kappa.kappa(list(zip(a, b)))
        self.assertAlmostEqual(po, 0.7)
        self.assertAlmostEqual(k, 0.4)

    def test_identical_undefined_and_only_one(self):
        self.assertEqual(kappa.kappa([('a', 'a'), ('b', 'b')]), (1.0, 1.0))
        self.assertEqual(kappa.kappa([('a', 'a'), ('a', 'a')]), (1.0, None))
        sa = self.sheet('a.csv', [['1', 'Major'], ['2', 'Major'], ['3', 'Minor']])
        sb = self.sheet('b.csv', [['1', 'Major'], ['2', 'Major'], ['4', 'Nit']])
        code, out = quiet(kappa.main, [sa, sb, '--column', 'g'])
        self.assertEqual(code, 0)
        self.assertIn('kappa: undefined', out)
        self.assertIn('rows graded in both: 2', out)
        self.assertIn(f'only in {sa}: 3', out)
        self.assertIn(f'only in {sb}: 4', out)


class FixRoundTest(Tmp):
    def test_round_names_map_to_item_and_kind(self):
        cases = {'p4': ('p4', 'build'), 'p4-review': ('p4', 'review'), 'p4-review2': ('p4', 'review'),
                 'p4-fix1': ('p4', 'fix'), 'p4-rereview': ('p4', 'rereview'), 'p4-r2': ('p4', 'resume'),
                 'merge-p4': ('p4', 'merge'), 'rv-p4': ('p4', 'review'), 'rv-p7-fix1': ('p7', 'rereview'),
                 'rv-t7-fix3': ('t7', 'rereview'), 'rr-p4': ('p4', 'rereview'), 'f29-fix1': ('f29', 'fix'),
                 'dr2-r2': ('dr2', 'resume'), 'p4-rx': ('p4-rx', 'build')}
        self.assertEqual({n: mine.split_name(n) for n in cases}, cases)

    def test_rulings_on_rv_fix_round_are_counted(self):
        self.run.round('rv-a-fix1', model='gpt-x', session='r')
        with open(os.path.join(self.run.dir, 'rulings.jsonl'), 'w') as f:
            ruling(f, 'rv-a-fix1', 'Major', 'Major')
        g = mine.rulings(mine.read_rulings(self.run.dir), mine.load_rounds(self.run.dir))
        self.assertEqual((g['odd'], g['model'].get('gpt-x')), ([], {'accepted': 1}))

    def test_first_review_has_a_verdict_and_follows_the_build(self):
        r = self.run
        r.round('p', credits=10, session='sp')
        r.round('p-review', at=T0 + 700, credits=5, session='r1')
        r.round('p-review2', at=T0 + 1400, credits=5, session='r2', report='Blocking: none\n')
        r.round('a-fix1', at=T0 + 2000, credits=5, session='sa')
        r.round('a-review2', at=T0 + 2700, credits=5, session='ra', report='Blocking: none\n')
        q = mine.quality(r.dir, mine.load_rounds(r.dir), None)
        self.assertEqual([(f['item'], f['round']) for f in q['first_reviews']], [('p', 'p-review2')])
        self.assertEqual((q['clean_reviewer'], q['unknown_provenance']), (1, ['a-review2']))
        self.assertIn('unknown provenance: a-review2', mine.quality_text(q))

    def test_review_after_fix_is_not_first(self):
        r = self.run
        r.round('b', credits=10, session='sb')
        r.round('b-review', at=T0 + 700, credits=5, session='r1')
        r.round('b-fix1', at=T0 + 1400, credits=5, session='sb')
        r.round('b-review2', at=T0 + 2100, credits=5, session='r2', report='Blocking: none\n')
        firsts = mine.quality(r.dir, mine.load_rounds(r.dir), None)['first_reviews']
        self.assertEqual([(f['round'], f['verdict']) for f in firsts], [('b-review', 'no verdict')])

    def write_rulings(self, *rows):
        with open(os.path.join(self.run.dir, 'rulings.jsonl'), 'w') as f:
            for round_, n, grade, ruled in rows:
                f.write(json.dumps({'round': round_, 'n': n, 'grade': grade, 'ruled': ruled, 'area': 'COR'}) + '\n')

    def test_measures_use_accepted_blockers_and_looped_items(self):
        r = self.run
        r.round('a', credits=10, session='sa')
        r.round('a-review', at=T0 + 700, credits=5, session='ra', report='1 blocking\n')
        r.round('a-fix1', at=T0 + 1400, credits=5, session='sa')
        r.round('b', at=T0 + 2000, credits=10, session='sb')
        r.round('b-review', at=T0 + 2700, credits=5, session='rb', report='1 blocking\n')
        self.write_rulings(('a-review', 1, 'Major', 'Minor'), ('b-review', 1, 'Major', 'Major'))
        q = mine.quality(r.dir, mine.load_rounds(r.dir), mine.read_rulings(r.dir))
        self.assertEqual((q['clean_orchestrator'], q['blockers_per_review']), (1, 0.5))
        self.assertEqual((q['fix_rounds_per_item'], q['looped_items']), (1.0, 1))
        text = mine.quality_text(q)
        self.assertIn('accepted by the orchestrator: 0.5', text)
        self.assertIn('fix rounds per looped item: 1.0 (1 looped)', text)

    def test_latest_ruling_replaces_earlier(self):
        r = self.run
        r.round('a', credits=10, session='sa')
        r.round('a-review', at=T0 + 700, model='gpt-x', credits=5, session='ra', report='1 blocking\n')
        self.write_rulings(('a-review', 1, 'Major', 'Major'), ('a-review', 1, 'Major', 'Minor'),
                           ('a-review', 2, 'Major', 'rejected'))
        rows, rs = mine.read_rulings(r.dir), mine.load_rounds(r.dir)
        self.assertEqual(len(rows), 3)
        g = mine.rulings(rows, rs)
        self.assertEqual((g['total'], g['lines'], g['model']['gpt-x']), (2, 3, {'demoted': 1, 'rejected': 1}))
        self.assertEqual(mine.quality(r.dir, rs, rows)['first_reviews'][0]['ruled_blocking'], 0)

    def test_malformed_rulings_line_is_reported(self):
        with open(os.path.join(self.run.dir, 'rulings.jsonl'), 'w') as f:
            f.write('{"round": "a-review", "n": 1, "gra\n')
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(mine.read_rulings(self.run.dir), [])
        self.assertIn('line 1 is not a ruling', err.getvalue())

    def test_sheet_is_blind_and_cues_flagged(self):
        path = os.path.join(self.tmp, 'f.csv')
        with open(path, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['id', 'area', 'finding', 'severity_today'])
            w.writerows([['F1', 'A', 'repeat of rejected finding', 'Nit'], ['F2', 'A', 'cache grows', 'Major']])
        out = os.path.join(self.tmp, 'o')
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sample.main([path, '--n', '2', '--strata', 'area', '--seed', '3', '--out', out]), 0)
        with open(os.path.join(out, 'sheet.csv'), newline='') as f:
            sheet = list(csv.reader(f))
        with open(os.path.join(out, 'key.csv'), newline='') as f:
            key = {k['id']: k for k in csv.DictReader(f)}
        self.assertEqual(sheet[0], ['id', 'text'])
        self.assertFalse({c for row in sheet for c in row} & {'F1', 'F2', 'A', 'Nit', 'Major'})
        cue = next(i for i, k in key.items() if k['source_id'] == 'F1')
        self.assertEqual((key[cue]['cue'], key[cue]['severity_today']), ('yes', 'Nit'))
        self.assertIn(cue, err.getvalue())

    def test_seed_controls_selection(self):
        path = os.path.join(self.tmp, 'f.csv')
        with open(path, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['area', 'finding'])
            w.writerows([['A', f'x{i}'] for i in range(30)])
        texts = set()
        for seed in range(4):
            out = os.path.join(self.tmp, f's{seed}')
            quiet(sample.main, [path, '--n', '5', '--strata', 'area', '--seed', str(seed), '--out', out])
            with open(os.path.join(out, 'sheet.csv'), newline='') as f:
                texts.add(tuple(row['text'] for row in csv.DictReader(f)))
        self.assertEqual(len(texts), 4)

    def sheet(self, name, rows):
        path = os.path.join(self.tmp, name)
        with open(path, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['id', 'g'])
            w.writerows(rows)
        return path

    def test_kappa_cli_prints_agreement(self):
        a = ['Y'] * 6 + ['N'] * 4
        b = ['Y'] * 4 + ['N'] * 2 + ['Y'] + ['N'] * 3
        sa = self.sheet('a.csv', [[str(i), g] for i, g in enumerate(a)])
        sb = self.sheet('b.csv', [[str(i), g] for i, g in enumerate(b)])
        code, out = quiet(kappa.main, [sa, sb, '--column', 'g'])
        self.assertEqual(code, 0)
        self.assertIn('agreement: 70.0%', out)
        self.assertIn('kappa: 0.400', out)

    def test_kappa_refuses_duplicate_and_empty_ids(self):
        good = self.sheet('g.csv', [['1', 'Y']])
        for name, rows, needle in (('d.csv', [['1', 'Y'], ['1', 'N']], "'1' appears more than once"),
                                   ('e.csv', [['1', 'Y'], ['', 'N']], "line 3 has an empty 'id'")):
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                code = kappa.main([good, self.sheet(name, rows), '--column', 'g'])
            self.assertEqual(code, 2)
            self.assertIn(needle, err.getvalue())


class HelpTest(unittest.TestCase):
    def test_help_exits_zero(self):
        for script in ('rule.py', 'sample.py', 'kappa.py', 'mine.py'):
            p = subprocess.run([sys.executable, '-B', os.path.join(HERE, script), '--help'], capture_output=True,
                               text=True, timeout=60, stdin=subprocess.DEVNULL)
            self.assertEqual(p.returncode, 0, script)


if __name__ == '__main__':
    unittest.main()
