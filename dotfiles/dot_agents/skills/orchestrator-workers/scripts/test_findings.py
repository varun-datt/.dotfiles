import json, os, subprocess, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import findings  # noqa: E402
from test_mine import Run, T0, append, message, SCRIPT  # noqa: E402

RUBRIC = """2 blocking

**Blocking.**

B1. [Major] REL L2/I2 FAIL: Restore can abort start-up  
Class: unprotected transaction lifecycle. The second rollback in [db.ts:288](src/store/db.ts#L288) throws; see also src/other.ts:9.  
Fix: guard it.

B2. [Blocker] *DATA L1/I1 **ADJ***: Saved notes vanish on close  
class: reuse of a failed transaction. No location given.

**Minor.**

VERIFIED COR L3/I2 BOUND: [Lexical containment](src/projects.ts#L14) accepts a symlink; class: unresolved containment.

**Pre-existing.**

VERIFIED COR L1/I2 PRE: The base defaults to three tries in src/tasks.ts:13; class: missing prerequisite.

**Corrections**

VERIFIED REPORT READ; class: coverage overstatement. The route test calls a manager.
"""

NUMBERED = """1 blocking

1. **Blocking** — `src/queue.py:35`: wrapped launch commands escape the guard. cause: **BOUND**
2. Non-blocking — src/route.py:501: a re-pick redraws. cause: SPEC
"""

TABLE = """**1 blocking**

| # | Severity | Finding | Cause | Class | Where |
|---|---|---|---|---|---|
| 1 | Blocking | Task links reach prompts unfenced | ADJ | unfenced outside text | src/tasks.ts:69 |
| 2 | Non-blocking | Fixtures mask the newline check | TEST | masking fixture | tests/fence.test.ts:125 |
"""


def write(run, name, text):
    with open(os.path.join(run.dir, name), 'w', encoding='utf-8') as f:
        f.write(text)


class FormatTest(unittest.TestCase):
    def test_rubric_lines_with_class_minor_pre_and_corrections(self):
        fs = {f['n']: f for f in findings.parse(RUBRIC)}
        self.assertEqual(list(fs), ['1', '2', 'm1', 'p1', 'x1'])
        b1 = fs['1']
        self.assertEqual((b1['cause'], b1['area'], b1['likelihood'], b1['impact'], b1['grade']),
                         ('FAIL', 'REL', 'L2', 'I2', 'Major'))
        self.assertTrue(b1['class'].startswith('unprotected transaction lifecycle'), b1['class'])
        self.assertEqual((b1['file'], b1['line']), ('src/store/db.ts', 288))
        self.assertTrue(b1['blocking'])
        self.assertEqual(b1['title'], 'Restore can abort start-up')

    def test_emphasis_around_tags_and_no_location(self):
        b2 = {f['n']: f for f in findings.parse(RUBRIC)}['2']
        self.assertEqual((b2['cause'], b2['grade'], b2['file'], b2['line']), ('ADJ', 'Blocker', None, None))
        self.assertTrue(b2['class'].startswith('reuse of a failed transaction'), b2['class'])

    def test_minor_and_pre_existing_do_not_block(self):
        fs = {f['n']: f for f in findings.parse(RUBRIC)}
        self.assertEqual((fs['m1']['grade'], fs['m1']['blocking'], fs['m1']['cause']), ('Minor', False, 'BOUND'))
        self.assertEqual((fs['p1']['blocking'], fs['p1']['cause'], fs['p1']['file']), (False, 'PRE', 'src/tasks.ts'))

    def test_numbered_list_with_cause(self):
        fs = findings.parse(NUMBERED)
        self.assertEqual([(f['n'], f['cause'], f['file'], f['line'], f['blocking']) for f in fs],
                         [('1', 'BOUND', 'src/queue.py', 35, True), ('2', 'SPEC', 'src/route.py', 501, False)])

    def test_table_with_cause_column(self):
        fs = findings.parse(TABLE)
        self.assertEqual([(f['n'], f['cause'], f['class'], f['file'], f['line'], f['blocking']) for f in fs],
                         [('1', 'ADJ', 'unfenced outside text', 'src/tasks.ts', 69, True),
                          ('2', 'TEST', 'masking fixture', 'tests/fence.test.ts', 125, False)])

    def test_first_of_two_paths_is_kept(self):
        f = findings.parse('1 blocking\n\n1. Blocking: a.py:3 and b.py:4 disagree. cause: ADJ\n')[0]
        self.assertEqual((f['file'], f['line']), ('a.py', 3))

    def test_clean_review_has_no_findings(self):
        self.assertEqual(findings.parse('Blocking: none\n\nVERIFIED: read every file.\n'), [])


REVIEW = """4 blocking

1. **Blocking** — src/guard.py:10: the queue guard misses quoted wrapper commands. cause: BOUND
2. **Blocking** — src/merge.py:20: merge totals double count a resumed round. cause: EDGE
3. **Blocking** — src/cache.py:30: cache entries survive a folder removal until restart. cause: ADJ
4. **Blocking** — src/clock.py:40: midnight crossing charges the whole turn to its start day. cause: ORDER
5. **Blocking** — src/theme.py:50: verdict colour contrast below four point five in the light theme. cause: UIQ
"""

BRIEF = """THIS IS A FIX ROUND.

ACCEPTED, fix these:
1. The queue guard misses quoted wrapper commands (`src/guard.py` about 10).
2. Merge totals double count a resumed round (`src/merge.py` about 20).
3. Midnight crossing charges the whole turn to its start day (`src/clock.py` about 40).

REJECTED, do not change: cache entries surviving a folder removal until restart are pre-existing; sent to the debt list.
"""

FIX_REPORT = """Finding 3: could not reproduce. A turn crossing midnight in src/clock.py:40 is split at the day boundary already.

Finding 1 fixed with a test.
"""


class RulingTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.run = Run(os.path.join(tmp.name, 'run-a'))
        self.run.round('job', at=T0)
        self.run.round('job-review', at=T0 + 1000, report=REVIEW)
        self.run.round('job-fix1', at=T0 + 2000)
        write(self.run, 'job-fix1.prompt.md', BRIEF)
        append(self.run, 'job-fix1', message(FIX_REPORT))
        write(self.run, 'rulings.jsonl', json.dumps({'round': 'job-review', 'n': 2, 'grade': 'Blocker', 'ruled': 'Major',
                                                     'by': 'o', 'reason': 'real but not harm', 'area': 'COR'}) + '\n')
        results, self.defects, self.counts, self.unparsed = findings.record(self.run.dir)
        self.by = {r['properties']['n']: r for r in results}

    def test_rulings_jsonl_blocker_to_major_is_accepted_and_outranks_the_brief(self):
        p = self.by['2']['properties']
        self.assertEqual((p['ruling'], p['rulingSource']), ('accepted', 'rulings.jsonl'))
        self.assertEqual([x['source'] for x in p['rulingOthers']], ['fix-brief-accepted'])
        self.assertNotIn('suppressions', self.by['2'])

    def test_brief_accepted_item_matched_by_text(self):
        p = self.by['1']['properties']
        self.assertEqual((p['ruling'], p['rulingSource']), ('accepted', 'fix-brief-accepted'))

    def test_rejected_item_sent_to_debt_is_rejected_out_of_scope_with_a_sarif_suppression(self):
        r = self.by['3']
        self.assertEqual((r['properties']['ruling'], r['properties']['rulingReason']), ('rejected', 'out-of-scope'))
        s = r['suppressions']
        self.assertEqual(len(s), 1)
        self.assertEqual((s[0]['kind'], s[0]['status']), ('external', 'accepted'))
        self.assertTrue(s[0]['justification'].startswith('out-of-scope: '))

    def test_accepted_brief_loses_to_nothing_but_could_not_reproduce_is_kept_as_a_lower_source(self):
        p = self.by['4']['properties']
        self.assertEqual((p['ruling'], p['rulingSource']), ('accepted', 'fix-brief-accepted'))
        self.assertEqual([(x['ruling'], x['reason'], x['source']) for x in p['rulingOthers']],
                         [('rejected', 'wrong', 'fix-report')])

    def test_unruled_blocking_finding_is_left_unruled(self):
        r = self.by['5']
        self.assertEqual((r['properties']['ruling'], r['properties']['blocking']), (None, True))
        self.assertNotIn('suppressions', r)

    def test_sarif_fields(self):
        r = self.by['1']
        self.assertEqual((r['ruleId'], r['level'], r['baselineState']), ('BOUND', 'note', 'new'))
        loc = r['locations'][0]['physicalLocation']
        self.assertEqual((loc['artifactLocation']['uri'], loc['region']['startLine']), ('src/guard.py', 10))
        self.assertIn(findings.FP_KEY, r['partialFingerprints'])


class NotReproducedTest(unittest.TestCase):
    def test_could_not_reproduce_alone_rejects_as_wrong(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Run(os.path.join(tmp, 'run-b'))
            run.round('job', at=T0)
            run.round('job-review', at=T0 + 1000, report=REVIEW)
            run.round('job-fix1', at=T0 + 2000)
            append(run, 'job-fix1', message(FIX_REPORT))
            by = {r['properties']['n']: r for r in findings.record(run.dir)[0]}
        p = by['4']['properties']
        self.assertEqual((p['ruling'], p['rulingReason'], p['rulingSource']), ('rejected', 'wrong', 'fix-report'))
        self.assertEqual(by['4']['suppressions'][0]['justification'].split(':')[0], 'wrong')
        self.assertIsNone(by['1']['properties']['ruling'])


FIRST = """2 blocking

1. **VERIFIED, blocking — [runner.py:35](tools/runner.py#L35):** shell wrapped launches escape detection because quotes are excluded from token boundaries.

2. **VERIFIED, blocking — [route.py:546](tools/route.py#L546):** an author can receive a reviewer of its own family through an override; final choices are not family checked after overrides.

3. **INFERRED, nonblocking — [route.py:501](tools/route.py#L501):** launch clears the pending decision, so a same round re-pick redraws without fresh.

4. **VERIFIED, nonblocking — [route.py:666](tools/route.py#L666):** a reused pick decision lacks tool version and model id fields; only its later launch event receives them.
"""

RE = """2 blocking

1. **INFERRED — [runner.py:85](tools/runner.py#L85): Queue guard remains bypassable.** Timeout and redirect wrapped launches evade executable detection.

2. **INFERRED — [route.py:564](tools/route.py#L564): Reuse can lose a known author.** A reused pick forgets the saved author, so an override launches a same family reviewer.

3. **VERIFIED (read), nonblocking — [route.py:698](tools/route.py#L698): Identity fix is incomplete.** Reused escalation decisions still lack tool version and model id.

**New blocking.**

B1. [Major] REL L2/I2 FAIL: The new retry loop never ends when the lock file is missing  
Class: unbounded retry. [lock.py:12](tools/lock.py#L12).
"""


class CarryTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.run = Run(os.path.join(tmp.name, 'run-c'))
        self.run.round('launcher', at=T0)
        self.run.round('launcher-review', at=T0 + 1000, report=FIRST)
        self.run.round('launcher-fix1', at=T0 + 2000)
        self.run.round('launcher-rereview', at=T0 + 3000, report=RE)
        results, self.defects = findings.record(self.run.dir)[:2]
        self.by = {(r['properties']['round'], r['properties']['n']): r for r in results}

    def fp(self, rnd, n):
        return self.by[(rnd, n)]['partialFingerprints'][findings.FP_KEY]

    def test_c3_takes_the_defect_id_of_first_finding_4(self):
        self.assertEqual(self.fp('launcher-rereview', 'c3'), self.fp('launcher-review', '4'))
        self.assertEqual(self.by[('launcher-rereview', 'c3')]['baselineState'], 'updated')

    def test_same_fingerprint_in_one_review_kept_apart(self):
        ids = {self.fp('launcher-review', n) for n in ('2', '3', '4')}
        self.assertEqual(len(ids), 3)
        self.assertEqual(len({i.split('/')[0] for i in ids}), 1)

    def test_not_fixed_is_unchanged_and_carried_finding_is_ruled_accepted(self):
        self.assertEqual(self.fp('launcher-rereview', 'c1'), self.fp('launcher-review', '1'))
        self.assertEqual(self.by[('launcher-rereview', 'c1')]['baselineState'], 'unchanged')
        p = self.by[('launcher-review', '1')]['properties']
        self.assertEqual((p['ruling'], p['rulingSource']), ('accepted', 'rereview'))
        self.assertIsNone(self.by[('launcher-review', '3')]['properties']['ruling'])

    def test_fix_introduced_finding_is_new_and_names_the_fix_round(self):
        r = self.by[('launcher-rereview', '1')]
        self.assertEqual(r['baselineState'], 'new')
        self.assertEqual(r['properties']['introducedBy'], 'launcher-fix1')
        self.assertNotIn(r['partialFingerprints'][findings.FP_KEY], {d['defect_id'] for d in self.defects[:4]})

    def test_moved_file_keeps_the_defect_id(self):
        moved = RE.replace('runner.py:85](tools/runner.py#L85)', 'launch.py:85](tools/launch.py#L85)')
        with tempfile.TemporaryDirectory() as tmp:
            run = Run(os.path.join(tmp, 'run-d'))
            run.round('launcher', at=T0)
            run.round('launcher-review', at=T0 + 1000, report=FIRST)
            run.round('launcher-fix1', at=T0 + 2000)
            run.round('launcher-rereview', at=T0 + 3000, report=moved)
            by = {(r['properties']['round'], r['properties']['n']): r for r in findings.record(run.dir)[0]}
        self.assertEqual(by[('launcher-rereview', 'c1')]['partialFingerprints'],
                         by[('launcher-review', '1')]['partialFingerprints'])

    def test_line_number_is_not_in_the_fingerprint(self):
        f = findings.parse(FIRST)[0]
        moved = dict(f, line=999)
        self.assertEqual(findings.defect_fp('x', f), findings.defect_fp('x', moved))


REQUIRED_RESULT = {'message'}
LEVEL = {'none', 'note', 'warning', 'error'}
KIND = {'pass', 'open', 'informational', 'notApplicable', 'review', 'fail'}
SUPPRESSION_KIND = {'inSource', 'external'}
SUPPRESSION_STATUS = {'accepted', 'underReview', 'rejected'}


def sarif_errors(log):
    """Hand-coded from SARIF 2.1.0 sections 3.13-3.34: required properties and enum values used here."""
    errs = []
    if log.get('version') != '2.1.0' or not str(log.get('$schema', '')).startswith('https://docs.oasis-open.org/sarif/'):
        errs.append('log version or $schema')
    if not isinstance(log.get('runs'), list) or len(log['runs']) != 1:
        return errs + ['runs']
    run = log['runs'][0]
    driver = run.get('tool', {}).get('driver', {})
    if not driver.get('name'):
        errs.append('tool.driver.name')
    rule_ids = {r.get('id') for r in driver.get('rules', [])}
    for i, r in enumerate(run.get('results', [])):
        if not isinstance(r.get('message'), dict) or not r['message'].get('text'):
            errs.append(f'{i}: message.text')
        if 'level' in r and r['level'] not in LEVEL:
            errs.append(f'{i}: level')
        if 'kind' in r and r['kind'] not in KIND:
            errs.append(f'{i}: kind')
        if 'ruleId' in r and r['ruleId'] not in rule_ids:
            errs.append(f'{i}: ruleId not in rules')
        if r.get('baselineState', 'new') not in findings.BASELINE:
            errs.append(f'{i}: baselineState')
        for s in r.get('suppressions', []):
            if s.get('kind') not in SUPPRESSION_KIND or s.get('status', 'accepted') not in SUPPRESSION_STATUS:
                errs.append(f'{i}: suppression')
        for loc in r.get('locations', []):
            reg = loc.get('physicalLocation', {}).get('region')
            if reg is not None and (not isinstance(reg.get('startLine'), int) or reg['startLine'] < 1):
                errs.append(f'{i}: region.startLine')
        pf = r.get('partialFingerprints', {})
        if not all(isinstance(v, str) for v in pf.values()):
            errs.append(f'{i}: partialFingerprints values')
        if not isinstance(r.get('properties', {}), dict):
            errs.append(f'{i}: properties')
    return errs


class CliTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name
        self.run = Run(os.path.join(tmp.name, 'run-e'))

    def cli(self, *args, code=0):
        env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
        p = subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, env=env, timeout=60,
                           stdin=subprocess.DEVNULL)
        self.assertEqual(p.returncode, code, p.stderr)
        return p

    def read(self, folder, name):
        with open(os.path.join(folder, name), encoding='utf-8') as f:
            return f.read()

    def test_empty_run_folder_writes_empty_files(self):
        p = self.cli(self.run.dir, '--findings')
        self.assertIn('0 reviews, 0 findings, 0 defects, 0 reports not parsed', p.stdout)
        self.assertEqual((self.read(self.run.dir, 'findings.jsonl'), self.read(self.run.dir, 'defects.jsonl')), ('', ''))

    def test_run_with_no_reviews_and_a_clean_review(self):
        self.run.round('job', at=T0)
        p = self.cli(self.run.dir, '--findings')
        self.assertIn('0 reviews, 0 findings', p.stdout)
        self.run.round('job-review', at=T0 + 10, report='Blocking: none\n')
        p = self.cli(self.run.dir, '--findings')
        self.assertIn('1 reviews, 0 findings', p.stdout)

    def test_unparsable_report_is_counted_and_named(self):
        self.run.round('job', at=T0)
        self.run.round('job-review', at=T0 + 10, report='3 blocking\n\nAll of it is wrong, trust me.\n')
        p = self.cli(self.run.dir, '--findings')
        self.assertIn('1 reports not parsed', p.stdout)
        self.assertIn('not parsed: job-review.txt line 1', p.stdout)

    def test_two_runs_are_byte_identical_and_out_is_honoured(self):
        self.run.round('job', at=T0)
        self.run.round('job-review', at=T0 + 1000, report=REVIEW)
        self.run.round('job-fix1', at=T0 + 2000)
        write(self.run, 'job-fix1.prompt.md', BRIEF)
        a, b = os.path.join(self.tmp, 'a'), os.path.join(self.tmp, 'b')
        self.cli(self.run.dir, '--findings', '--sarif', '--out', a)
        self.cli(self.run.dir, '--findings', '--sarif', '--out', b)
        for name in ('findings.jsonl', 'defects.jsonl', 'findings.sarif'):
            self.assertEqual(self.read(a, name), self.read(b, name), name)
        self.assertFalse(os.path.exists(os.path.join(self.run.dir, 'findings.jsonl')))
        self.assertEqual(len(self.read(a, 'findings.jsonl').splitlines()), 5)

    def test_sarif_log_meets_the_spec_and_holds_the_same_results(self):
        self.run.round('launcher', at=T0)
        self.run.round('launcher-review', at=T0 + 1000, report=RUBRIC)
        self.cli(self.run.dir, '--findings', '--sarif')
        log = json.loads(self.read(self.run.dir, 'findings.sarif'))
        self.assertEqual(sarif_errors(log), [])
        lines = [json.loads(x) for x in self.read(self.run.dir, 'findings.jsonl').splitlines()]
        self.assertEqual(log['runs'][0]['results'], lines)
        self.assertEqual([r['id'] for r in log['runs'][0]['tool']['driver']['rules']], ['ADJ', 'BOUND', 'FAIL', 'PRE'])

    def test_sarif_checker_catches_a_bad_enum(self):
        bad = findings.sarif_log([{'message': {'text': 'x'}, 'baselineState': 'persisted', 'level': 'error'}])
        self.assertEqual(sarif_errors(bad), ['0: baselineState'])

    def test_sarif_needs_findings_and_help_lists_both(self):
        self.cli(self.run.dir, '--sarif', code=2)
        p = self.cli('--help')
        self.assertIn('--findings', p.stdout)
        self.assertIn('--sarif', p.stdout)


if __name__ == '__main__':
    unittest.main()
