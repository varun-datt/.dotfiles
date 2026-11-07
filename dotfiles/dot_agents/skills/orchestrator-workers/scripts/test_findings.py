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
        self.assertEqual((b1['class'] or '')[:33], 'unprotected transaction lifecycle')
        self.assertEqual((b1['file'], b1['line']), ('src/store/db.ts', 288))
        self.assertTrue(b1['blocking'])
        self.assertEqual(b1['title'], 'Restore can abort start-up')

    def test_emphasis_around_tags_and_no_location(self):
        b2 = {f['n']: f for f in findings.parse(RUBRIC)}['2']
        self.assertEqual((b2['cause'], b2['grade'], b2['file'], b2['line']), ('ADJ', 'Blocker', None, None))
        self.assertEqual((b2['class'] or '')[:29], 'reuse of a failed transaction')

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
        self.assertEqual(self.by['2']['suppressions'], [])

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
        self.assertEqual(r['suppressions'], [])

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

1. **INFERRED, not fixed — [runner.py:85](tools/runner.py#L85): Queue guard remains bypassable.** Timeout and redirect wrapped launches evade executable detection.

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


class OlderFormsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.run = Run(os.path.join(tmp.name, 'run-f'))

    def test_this_round_and_fix_round_briefs_and_known_limit_items(self):
        write(self.run, 'a-fix1.prompt.md', 'TASK\n1. a must\n\nTHIS ROUND\nFix all.\n\n1. `x.py` about 3: guard fails.\n2. Rename: do NOT build it. Record it as a known limit.\n')
        write(self.run, 'b-fix1.prompt.md', 'Fix round 1 for b. Fix 1.\n1. BLOCKING — `y.py:4`: a leak.\n')
        a, b = findings.brief(self.run.dir, 'a-fix1'), findings.brief(self.run.dir, 'b-fix1')
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertEqual((len(a['accepted']), len(a['recorded'])), (1, 1))
        self.assertTrue(a['accepted'][0].startswith('1. `x.py`'))
        self.assertEqual((len(b['accepted']), b['recorded']), (1, []))

    def test_original_task_marker_quoted_in_prose_does_not_cut_the_brief(self):
        write(self.run, 'c-fix1.prompt.md', 'The brief is after "==== ORIGINAL TASK ====".\n\nACCEPTED, fix these:\n1. one\n\n'
              '==== ORIGINAL TASK ====\nACCEPTED, fix these:\n1. from the task\n2. also\n')
        b = findings.brief(self.run.dir, 'c-fix1')
        self.assertIsNotNone(b)
        self.assertEqual(b['accepted'], ['1. one'])

    def test_fix_round_of_a_research_run_still_rules(self):
        self.assertTrue(findings.is_fix({'kind': 'research', 'name': 'dr1-fix1'}))
        self.assertFalse(findings.is_fix({'kind': 'research', 'name': 'dr1-review'}))

    def test_severity_table_takes_blocking_from_the_verdict(self):
        table = ('**1 blocking**\n\n| # | Severity | File | Vulnerability |\n|---|---|---|---|\n'
                 '| 1 | HIGH | a.ts:3 | key and folder disagree |\n| 2 | MEDIUM | b.ts:9 | hover leaks |\n')
        self.run.round('s', at=T0)
        self.run.round('s-review', at=T0 + 10, report=table)
        by = {r['properties']['n']: r['properties'] for r in findings.record(self.run.dir)[0]}
        self.assertEqual((by['1']['blocking'], by['1'].get('blockingFrom'), by['2']['blocking']), (True, 'verdict', False))

    def test_details_list_merges_into_its_row_and_follow_up_options_are_not_findings(self):
        text = ('**1 blocking**\n\n| # | Severity | Issue |\n|---|---|---|\n| 1 | HIGH | key mismatch in a.ts:3 |\n\n'
                '1. **Key mismatch**: details here.\n\n1. Fix highest severity issues\n2. Fix all issues\n3. Commit a summary of findings\n')
        fs = findings.parse(text)
        self.assertEqual([f['n'] for f in fs], ['1'])
        self.assertIn('details here', fs[0]['text'])

    def test_f_numbered_items_keep_their_label(self):
        self.assertEqual([f['n'] for f in findings.parse('2 blocking\n\nF1. Blocking: a.py:1 x. cause: ADJ\nF2. Blocking: b.py:2 y. cause: EDGE\n')],
                         ['F1', 'F2'])


class FixRoundTwoTest(unittest.TestCase):
    """Findings of the r1 fix round, one test (or a few) per finding."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.run = Run(os.path.join(tmp.name, 'run-x'))

    def by(self, **kw):
        res = findings.record(self.run.dir, **kw)
        self.unparsed = res[3]
        return {(r['properties']['round'], r['properties']['n']): r for r in res[0]}

    # finding 1
    def test_numbered_heading_with_its_body_after_a_blank_line(self):
        fs = findings.parse('1 blocking\n\n### 1. Saved notes vanish on close\n\nThe store drops the write in src/a.py:3. cause: ADJ\n')
        self.assertEqual([(f['n'], f['cause'], f['file'], f['title']) for f in fs],
                         [('1', 'ADJ', 'src/a.py', 'Saved notes vanish on close')])

    def test_details_after_a_blank_line_stay_with_their_finding(self):
        fs = findings.parse('1 blocking\n\n1. [Major] Saved notes vanish in src/a.py:3\n\nClass: lost write. cause: ADJ\n')
        self.assertEqual([(f['n'], f['cause'], f['class'], f['grade']) for f in fs], [('1', 'ADJ', 'lost write', 'Major')])

    def test_c1_m1_and_1_b1_labels(self):
        text = ('1 blocking\n\n**Findings.**\n\n1 (B1). **partly fixed — VERIFIED:** src/a.py:3 still loses one case.\n\n'
                'c2. not fixed — src/b.py:4 drops it.\n\n**New minor.**\n\nM1. [Minor] REL L2/I3 FAIL: slow refresh erases the list\n')
        fs = {f['n']: f for f in findings.parse(text, rereview=True)}
        self.assertEqual(sorted(fs), ['c1', 'c2', 'm1'])
        self.assertEqual((fs['c1']['ref'], fs['c1']['verdict'], fs['c1']['status']), ('1', 'partly', 'updated'))
        self.assertEqual((fs['c2']['verdict'], fs['c2']['status']), ('not fixed', 'unchanged'))
        self.assertEqual((fs['m1']['section'], fs['m1']['cause'], fs['m1']['blocking']), ('minor', 'FAIL', False))

    def test_bullets_under_a_blocking_heading_are_findings_but_detail_bullets_are_not(self):
        fs = findings.parse('**Verdict: request changes**\n\n**Blocking**\n- **VERIFIED** — a.py:3: the zone stays hidden.\n'
                            '- **VERIFIED** — b.py:4: zones drop selections.\n\n**Non-blocking**\n- c.py:5: label is vague.\n')
        self.assertEqual([(f['n'], f['file'], f['section']) for f in fs], [('1', 'a.py', 'blocking'), ('2', 'b.py', 'blocking')])
        fs = findings.parse('1 blocking\n\n**Blocking**\n1. [Major] a.py:3 the zone stays hidden.\n- reveal the next line too\n')
        self.assertEqual([f['n'] for f in fs], ['1'])

    def test_unconsumed_finding_like_block_is_named(self):
        self.run.round('job', at=T0)
        self.run.round('job-review', at=T0 + 10, report='2 blocking\n\n1. [Major] a.py:1 x breaks. cause: ADJ\n\nSome prose.\n\n'
                                                     '- **New blocker: items stay running** in b.py:2\n')
        self.by()
        whys = [(u['line'], u['why']) for u in self.unparsed]
        self.assertTrue(any(line == 7 and 'New blocker' in why for line, why in whys), whys)
        self.assertTrue(any('only 1 blocking' in why for _, why in whys), whys)

    # finding 2
    def test_fix_report_same_kind_list_and_jsonl_only_critique_are_recorded(self):
        self.run.round('job', at=T0)
        self.run.round('job-review', at=T0 + 10, report=REVIEW)
        self.run.round('job-fix1', at=T0 + 20)
        append(self.run, 'job-fix1', message('Fixed 1.\n\n**Same kind, not fixed:**\n- `a.py:3` keeps only the first error.\n'
                                             '- `b.py:9`: the skip reason is lost.\n\n## Checks\n1. ran\n'))
        self.run.round('doc-critique', at=T0 + 30)
        append(self.run, 'doc-critique', message('1 blocking\n\n## Blocking\n\n1. [Major] The cited rate is wrong in notes.md:4\n'))
        by = self.by()
        fix = [(k[1], r['properties']['roundKind'], r['properties']['origin']) for k, r in by.items() if k[0] == 'job-fix1']
        self.assertEqual(fix, [('s1', 'fix', 'same-kind'), ('s2', 'fix', 'same-kind')])
        self.assertEqual(by[('job-fix1', 's1')]['locations'][0]['physicalLocation']['artifactLocation']['uri'], 'a.py')
        self.assertEqual(by[('doc-critique', '1')]['properties']['roundKind'], 'critique')
        heading = findings.same_kind('## Same kind, not fixed\n\n- `c.py:1` drops it too.\n\n## Checks\n1. ran\n')
        self.assertEqual([x['text'] for x in heading], ['`c.py:1` drops it too.'])

    # finding 2: a review of a fix, named rv-<item>-fix1, stays a review
    def test_review_round_named_after_its_fix_is_still_a_review(self):
        self.run.round('job', at=T0)
        self.run.round('rv-job-fix1', at=T0 + 10, report='1 blocking\n\n1. **Blocking** — a.py:3: the guard is skipped. cause: BOUND\n')
        by = self.by()
        self.assertEqual(by[('rv-job-fix1', 'c1')]['properties']['roundKind'], 'rereview')

    # finding 3
    def test_explicit_b1_b2_rulings_win_over_text(self):
        self.run.round('job', at=T0)
        self.run.round('job-review', at=T0 + 10, report='2 blocking\n\nB1. [Major] REL L2/I2 FAIL: retry loop spins on a missing lock in a.py:3\n'
                                                     'Class: unbounded retry.\n\nB2. [Major] REL L2/I2 FAIL: retry loop spins on a missing socket in b.py:4\n'
                                                     'Class: unbounded retry.\n')
        self.run.round('job-fix1', at=T0 + 20)
        write(self.run, 'job-fix1.prompt.md', 'FIX THESE, one at a time:\n1. B2: the retry loop spins on a missing socket and lock.\n\n'
                                              'NOT TO CHANGE (rejected by the orchestrator): B1, the retry loop on a missing lock, is by design.\n')
        by = self.by()
        self.assertEqual(by[('job-review', '1')]['properties']['ruling'], 'rejected')
        self.assertEqual(by[('job-review', '2')]['properties']['ruling'], 'accepted')

    def test_text_match_that_fits_two_findings_is_left_unruled_and_reported(self):
        self.run.round('job', at=T0)
        self.run.round('job-review', at=T0 + 10, report='2 blocking\n\n1. Blocking: the retry loop spins forever. cause: FAIL\n'
                                                     '2. Blocking: the retry loop spins forever. cause: FAIL\n')
        self.run.round('job-fix1', at=T0 + 20)
        write(self.run, 'job-fix1.prompt.md', 'ACCEPTED:\n1. The retry loop spins forever.\n')
        by = self.by()
        self.assertEqual([by[('job-review', n)]['properties']['ruling'] for n in ('1', '2')], [None, None])
        self.assertTrue(any(u.get('kind') == 'ambiguous' for u in self.unparsed), self.unparsed)

    # finding 4
    def test_brief_sections_parsed_item_by_item(self):
        write(self.run, 'a-fix1.prompt.md', 'ACCEPTED, fix these:\n1. one thing\n\n2. two thing\n\n3. three thing\n\n'
                                            'REJECTED: the cache is by design; the log line is pre-existing, sent to debt.\n')
        b = findings.brief(self.run.dir, 'a-fix1')
        self.assertEqual(len(b['accepted']), 3)
        self.assertEqual(b['rejected'], ['the cache is by design', 'the log line is pre-existing, sent to debt.'])
        self.assertEqual([findings.reason_of(x) for x in b['rejected']], ['wrong', 'out-of-scope'])

    def test_current_fix_brief_form(self):
        write(self.run, 'b-fix1.prompt.md', 'THIS ROUND REPLACES the preamble.\n\nFIX THESE, one at a time:\n'
                                            '1. First. Where: `a.py` about 3. Done when: x.\n2. Second. Where: `b.py`.\n\n'
                                            'For each finding:\n1. Write one test.\n2. Fix the code.\n\n'
                                            'NOT TO CHANGE (decided by the orchestrator; on the debt list): unittest discovery (finding B4); '
                                            'odd names (finding B5). The pre-existing failure belongs to another task.\n\n'
                                            'REUSE CHECK: not needed.\n')
        b = findings.brief(self.run.dir, 'b-fix1')
        self.assertEqual([x[:9] for x in b['accepted']], ['1. First.', '2. Second'])
        self.assertEqual(len(b['rejected']), 3)
        self.assertEqual([findings.refs(x) for x in b['rejected']], [['4'], ['5'], []])

    def test_real_fix_briefs_of_the_p1_run(self):
        real = os.path.expanduser('~/.local/state/orchestrator-workers/amc-2026-11-02-p1')
        if not os.path.isfile(os.path.join(real, 'p1a-fix1.body.md')):
            self.skipTest('the p1 run folder is not on this machine')
        p1a, r3 = findings.brief(real, 'p1a-fix1'), findings.brief(real, 'r3-fix1')
        self.assertEqual((len(p1a['accepted']), len(p1a['rejected'])), (5, 3))
        self.assertEqual((len(r3['accepted']), len(r3['rejected'])), (8, 4))

    # finding 5
    def test_rereview_rejection_is_not_an_acceptance_and_a_bare_link_is_not_a_ruling(self):
        self.run.round('job', at=T0)
        self.run.round('job-review', at=T0 + 10, report=REVIEW)
        self.run.round('job-fix1', at=T0 + 20)
        self.run.round('job-rereview', at=T0 + 30, report='1 blocking\n\n**Findings.**\n\n'
                                                       'B1. Rejected — not a defect: the queue guard sees quoted wrapper commands in src/guard.py:10.\n\n'
                                                       '2. Merge totals double count a resumed round, src/merge.py:20.\n')
        by = self.by()
        p1, p2 = by[('job-review', '1')]['properties'], by[('job-review', '2')]['properties']
        self.assertEqual((p1['ruling'], p1['rulingSource'], p1['rulingReason']), ('rejected', 'rereview', 'wrong'))
        self.assertEqual(by[('job-rereview', 'c1')]['partialFingerprints'], by[('job-review', '1')]['partialFingerprints'])
        self.assertEqual(by[('job-rereview', 'c2')]['partialFingerprints'], by[('job-review', '2')]['partialFingerprints'])
        self.assertIsNone(p2['ruling'])

    # finding 6
    def test_b_labels_in_a_rereview_findings_section_are_carried_not_introduced(self):
        self.run.round('job', at=T0)
        self.run.round('job-review', at=T0 + 10, report='2 blocking\n\nB1. [Major] SEC L2/I1 ADJ: edit approvals skip the recheck in acp.ts:553\n\n'
                                                     'B2. [Major] REL L2/I2 FAIL: the source map is stale in knowledge.ts:240\n\n'
                                                     'B3. [Major] COR L2/I2 EDGE: folder aliases compare as text in acp.ts:117\n')
        self.run.round('job-fix1', at=T0 + 20)
        self.run.round('job-rereview', at=T0 + 30, report='1 blocking\n\n**Findings.**\n\n'
                                                       'B1. **Partly fixed — VERIFIED.** At acp.ts:560 a diff-only edit still bypasses it.\n\n'
                                                       'B2. **Fixed — VERIFIED.** knowledge.ts:240 invalidates the map.\n\n'
                                                       'B3. **Fixed — VERIFIED.** acp.ts:117 compares canonical paths.\n\n'
                                                       '**Pre-existing.**\n\nVERIFIED COR L1/I2 PRE: the base retries three times in tasks.ts:13\n\n'
                                                       '**New harm.**\n\nB1. [Major] REL L2/I2 FAIL: the new retry never ends in lock.py:12\n')
        by = self.by()
        for n, state in (('1', 'updated'), ('2', 'absent'), ('3', 'absent')):
            c = by[('job-rereview', 'c' + n)]
            self.assertEqual(c['partialFingerprints'], by[('job-review', n)]['partialFingerprints'])
            self.assertEqual((c['baselineState'], c['properties']['introducedBy']), (state, None))
        pre = by[('job-rereview', 'p1')]
        self.assertEqual((pre['baselineState'], pre['properties']['introducedBy']), ('new', None))
        self.assertEqual(by[('job-rereview', '1')]['properties']['introducedBy'], 'job-fix1')

    # finding 7
    def test_changing_a_line_number_in_the_raw_report_keeps_the_fingerprint(self):
        a = findings.parse(RUBRIC)[0]
        b = findings.parse(RUBRIC.replace('db.ts:288](src/store/db.ts#L288)', 'db.ts:301](src/store/db.ts#L301)'))[0]
        self.assertEqual(b['line'], 301)
        self.assertEqual(a['class'], 'unprotected transaction lifecycle')
        self.assertEqual(findings.defect_fp('x', a), findings.defect_fp('x', b))

    # finding 8
    def test_fixed_status_word_decides_even_when_the_explanation_says_remains_or_still(self):
        fs = {f['n']: f for f in findings.parse('Blocking: none\n\n**Findings.**\n\n'
                                                '4. **Fixed — VERIFIED.** a.py:3; the old branch remains but is unreachable.\n'
                                                '5. Fixed: b.py:4 still logs the value, which is harmless.\n', rereview=True)}
        self.assertEqual([fs[n]['status'] for n in ('c4', 'c5')], ['absent', 'absent'])

    # finding 9
    def test_every_result_carries_suppressions_when_one_does_and_the_checker_enforces_it(self):
        self.run.round('job', at=T0)
        self.run.round('job-review', at=T0 + 1000, report=REVIEW)
        self.run.round('job-fix1', at=T0 + 2000)
        write(self.run, 'job-fix1.prompt.md', BRIEF)
        results = findings.record(self.run.dir)[0]
        self.assertEqual(sarif_errors(findings.sarif_log(results)), [])
        self.assertTrue(all('suppressions' in r for r in results))
        old = [dict(r) for r in results]
        for r in old:
            if r['suppressions'] == []:
                del r['suppressions']
        self.assertIn('suppressions on some results of the run only', ' '.join(sarif_errors(findings.sarif_log(old))))

    # finding 10
    def test_paths_are_kept_as_written(self):
        for text, want in (('see .gitignore:3', '.gitignore'), ('see Makefile:12', 'Makefile'),
                           ('see /abs/src/a.py:5', '/abs/src/a.py'), ('see ../src/a.py:7', '../src/a.py')):
            self.assertEqual(findings.first_location(text)[0], want, text)

    def test_table_row_message_is_its_title_cell(self):
        self.assertEqual([f['title'] for f in findings.parse(TABLE)],
                         ['Task links reach prompts unfenced', 'Fixtures mask the newline check'])

    def test_tags_inside_full_emphasis_are_read(self):
        f = findings.parse('1 blocking\n\n1. [Major] **REL L2/I2** **FAIL**: retry spins in a.py:3. **class: unbounded retry**\n')[0]
        self.assertEqual((f['area'], f['cause'], f['class']), ('REL', 'FAIL', 'unbounded retry'))


class FixRoundThreeTest(unittest.TestCase):
    """The prose fallback's leftovers from the first fix round's re-check, one test each."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.run = Run(os.path.join(tmp.name, 'run-y'))

    def by(self):
        return {(r['properties']['round'], r['properties']['n']): r for r in findings.record(self.run.dir)[0]}

    def test_fix_report_known_limits_are_recorded_beside_same_kind(self):
        self.run.round('job', at=T0)
        self.run.round('job-review', at=T0 + 10, report=REVIEW)
        self.run.round('job-fix1', at=T0 + 20)
        append(self.run, 'job-fix1', message('1. Fixed 1 in src/guard.py:10.\n\n**Same kind, not fixed:**\n- `a.py:3` keeps one.\n\n'
                                             '6. Known limits:\n- `b.py:9`: a moved file loses its ruling.\n- Retries are not bounded.\n'
                                             '7. Drafts: none.\n'))
        fix = {k[1]: r['properties'] for k, r in self.by().items() if k[0] == 'job-fix1'}
        self.assertEqual(sorted(fix), ['l1', 'l2', 's1'])
        self.assertEqual((fix['l1']['origin'], fix['l1']['blocking'], fix['s1']['origin']), ('known-limit', False, 'same-kind'))

    def test_bare_number_in_a_rejected_list_rules_that_finding(self):
        self.run.round('job', at=T0)
        self.run.round('job-review', at=T0 + 10, report=REVIEW)
        self.run.round('job-fix1', at=T0 + 20)
        write(self.run, 'job-fix1.prompt.md', 'ACCEPTED, fix these:\n1. B1: the guard.\n\nREJECTED: 2 (by design); 5, out of scope.\n')
        by = self.by()
        self.assertEqual((by[('job-review', '2')]['properties']['ruling'], by[('job-review', '2')]['properties']['rulingReason']),
                         ('rejected', 'wrong'))
        self.assertEqual(by[('job-review', '5')]['properties']['ruling'], 'rejected')
        self.assertEqual(findings.refs('2 (by design)'), ['2'])
        self.assertEqual(findings.refs('3 retries are fine'), [])

    def test_status_less_entry_under_findings_is_carried_not_introduced(self):
        self.run.round('job', at=T0)
        self.run.round('job-review', at=T0 + 10, report='1 blocking\n\nB1. [Major] SEC L2/I1 ADJ: edit approvals skip the recheck in acp.ts:553\n')
        self.run.round('job-fix1', at=T0 + 20)
        self.run.round('job-rereview', at=T0 + 30, report='1 blocking\n\n**Findings.**\n\n'
                                                       'B1. acp.ts:560 a diff-only edit still bypasses the recheck.\n')
        by = self.by()
        self.assertNotIn(('job-rereview', '1'), by)
        c = by[('job-rereview', 'c1')]
        self.assertEqual(c['partialFingerprints'], by[('job-review', '1')]['partialFingerprints'])
        self.assertIsNone(c['properties']['introducedBy'])

    def test_minor_table_row_and_a_following_tagged_minor_get_different_ids(self):
        fs = findings.parse('Blocking: none\n\n**Minor.**\n\n| # | Finding |\n|---|---|\n| 1 | the label is vague in a.py:3 |\n\n'
                            'VERIFIED COR L3/I3 EDGE: an empty list renders a blank row in b.py:4; class: empty input\n')
        self.assertEqual([f['n'] for f in fs], ['m1', 'm2'])


LEVEL, KIND = findings.SARIF_LEVEL, findings.SARIF_KIND
sarif_errors = findings.sarif_errors


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

    def test_since_with_findings_is_refused_and_a_bad_date_is_refused_either_way(self):
        p = self.cli(self.run.dir, '--findings', '--since', '2026-01-01', code=2)
        self.assertIn('--since is refused', p.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.run.dir, 'findings.jsonl')))
        p = self.cli(self.run.dir, '--findings', '--since', 'yesterday-ish', code=2)
        self.assertIn('not an ISO date', p.stderr)
        self.cli(self.run.dir, '--since', 'yesterday-ish', code=2)

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


class FixCheckTest(unittest.TestCase):
    """findings.py fixcheck: every finding of the fix brief is fixed with a test that exists, or listed."""
    BRIEF = ('THIS IS A FIX ROUND for a.\n\nFIX THESE, one at a time:\n3. Lost rows. Where: `a.py` 4. Done when: kept.\n'
             '4. Vacuous check. Where: `b.py` 2. Done when: fails.\n5. Late event. Where: `c.py` 9. Done when: ignored.\n\n'
             'WHY NOW:\n3 HARM: rows lost\n')

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.wt = os.path.join(tmp.name, 'wt')
        os.makedirs(os.path.join(self.wt, 'tests'))
        with open(os.path.join(self.wt, 'tests', 'test_a.py'), 'w') as f:
            f.write('SCRIPT = 1\n\n\nclass StoreTest:\n    def test_rows_survive(self): pass\n    def test_check_fails(self): pass\n'
                    '    def helper(self): pass\n\n\ndef test_late_event_ignored(): pass\n')
        with open(os.path.join(self.wt, 'store.py'), 'w') as f:
            f.write('def record(): pass\n')
        with open(os.path.join(self.wt, 'tests', 'test_broken.py'), 'w') as f:
            f.write('def test_x(:\n')
        with open(os.path.join(self.wt, 'tests', 'pan.test.ts'), 'w') as f:
            f.write("describe('pan', () => {\n  it(\"keeps the view's edge\", () => {});\n  test.skip(`zooms`, () => {});\n});\n"
                    "test('alone', () => {});\n")

    def check(self, report):
        return findings.fix_check(self.BRIEF, report, self.wt)

    def test_all_fixed_with_tests_that_exist_is_exit_0(self):
        report = ('Done.\n\n- 3: fixed, tests/test_a.py::StoreTest.test_rows_survive\n'
                  '-  **4**:  fixed,  `tests/test_a.py::StoreTest.test_check_fails`.\n'
                  '**- 5: fixed, tests/test_a.py::test_late_event_ignored**\n')
        self.assertEqual(self.check(report), ([], 0))

    def test_left_unmentioned_and_missing_tests_are_listed_with_exit_1(self):
        report = ('- 3: left, the restart path needs a design.\n'
                  '- 4: fixed, tests/test_a.py::StoreTest.test_no_such_test\n'
                  '- 9: fixed, tests/test_a.py::StoreTest.test_rows_survive\n')
        lines, rc = self.check(report)
        self.assertEqual(rc, 1)
        self.assertEqual(lines, ['- 3: left, the restart path needs a design',
                                 '- 4: fixed, but no test StoreTest.test_no_such_test in tests/test_a.py: no class StoreTest '
                                 'with that method',
                                 "- 5: not mentioned on a `- 5: fixed|left` line of the fixer's report"])
        lines, _ = self.check('- 3: fixed, tests/test_gone.py::test_rows_survive\n- 4: fixed, test_check_fails\n'
                              '- 5: fixed, tests/test_a.py::test_late_event_ignored\n')
        self.assertEqual(lines, ['- 3: fixed, but no test file tests/test_gone.py in the worktree',
                                 "- 4: fixed, but 'test_check_fails' names no <test file>::<test name>"])

    def test_a_name_that_is_not_a_test_is_refused(self):
        refused = {'store.py::record': 'store.py is not a test file',
                   'tests/test_a.py::NoSuchTest.test_rows_survive': 'no class NoSuchTest with that method',
                   'tests/test_a.py::NonexistentClass.SCRIPT': 'no class NonexistentClass with that method',
                   'tests/test_a.py::SCRIPT': 'no module-level test SCRIPT in tests/test_a.py',
                   'tests/test_a.py::StoreTest.helper': 'StoreTest.helper in tests/test_a.py is not a test: its name',
                   'tests/test_a.py::test_rows_survive': 'no module-level test test_rows_survive',
                   'tests/test_broken.py::test_x': 'tests/test_broken.py does not parse (',
                   'tests/pan.test.ts::pan > rotates': "no test titled 'rotates' in tests/pan.test.ts after the parts",
                   'tests/pan.test.ts::alone > pan': "no test titled 'pan' in tests/pan.test.ts after the parts"}
        for spec, want in refused.items():
            self.assertIn(want, findings.test_found(self.wt, spec), spec)
        for spec in ('tests/test_a.py::StoreTest.test_rows_survive', 'tests/test_a.py::test_late_event_ignored',
                     "tests/pan.test.ts::pan > keeps the view's edge", 'tests/pan.test.ts::pan > zooms',
                     'tests/pan.test.ts::alone'):
            self.assertEqual(findings.test_found(self.wt, spec), '', spec)

    def test_the_real_report_before_the_line_form_lists_every_finding_as_not_mentioned(self):
        fx = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', 'findings')
        run = tempfile.mkdtemp(dir=self.wt)
        with open(os.path.join(fx, 'mf-fix1.report.md'), encoding='utf-8') as f:
            report = f.read()
        with open(os.path.join(run, 'mf-fix1-resume1.jsonl'), 'w', encoding='utf-8') as f:
            f.write(json.dumps(message(report)) + '\n' + json.dumps({'type': 'result', 'exitCode': 0}) + '\n')
        with open(os.path.join(run, 'queue.json'), 'w', encoding='utf-8') as f:
            json.dump({'items': [{'id': 'mf', 'worktree': self.wt, 'pipeline': [
                {'name': 'fix', 'brief': os.path.join(fx, 'mf-fix1.body.md'), 'report': 'mf-fix1-resume1'}]}]}, f)
        p = subprocess.run([sys.executable, '-B', SCRIPT.replace('mine.py', 'findings.py'), 'fixcheck', 'mf', '--run-dir',
                            run], capture_output=True, text=True, stdin=subprocess.DEVNULL)
        self.assertEqual(p.returncode, 1, p.stderr)
        self.assertEqual(p.stdout.splitlines(), [f"- {n}: not mentioned on a `- {n}: fixed|left` line of the fixer's report"
                                                  for n in ('1', '2')])
        p = subprocess.run([sys.executable, '-B', SCRIPT.replace('mine.py', 'findings.py'), 'fixcheck', 'nope',
                            '--run-dir', run], capture_output=True, text=True, stdin=subprocess.DEVNULL)
        self.assertEqual(p.returncode, 2)
        self.assertIn('no worktree for nope', p.stderr)


class BlockTest(unittest.TestCase):
    """Reviewers' structured findings blocks."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.run = Run(os.path.join(tmp.name, 'run-k'))

    def record(self):
        res = findings.record(self.run.dir)
        self.unparsed, self.counts = res[3], res[2]
        return {(r['properties']['round'], r['properties']['n']): r for r in res[0]}

    @staticmethod
    def block(results):
        return '\n```json\n' + json.dumps(results, indent=1) + '\n```\n'

    FIRST = [{'ruleId': 'ADJ', 'level': 'error', 'message': {'text': 'Saved notes vanish on close'},
              'locations': [{'physicalLocation': {'artifactLocation': {'uri': 'src/a.py'}, 'region': {'startLine': 3}}}],
              'properties': {'n': 'B1', 'grade': 'Major', 'area': 'DATA', 'likelihood': 'L1', 'impact': 'I2',
                             'class': 'lost write'}},
             {'ruleId': 'EDGE', 'level': 'error', 'message': {'text': 'Empty list crashes the page'},
              'properties': {'n': 'B2', 'grade': 'Major', 'area': 'COR', 'likelihood': 'L2', 'impact': 'I2', 'class': None}},
             {'ruleId': 'TEST', 'level': 'warning', 'message': {'text': 'The guard test cannot fail'},
              'properties': {'n': 'M1', 'grade': 'Minor', 'area': 'VERIF', 'likelihood': 'L2', 'impact': 'I3',
                             'class': 'vacuous test'}}]

    def test_a_valid_block_builds_every_row_and_the_prose_is_not_read(self):
        prose = '2 blocking\n\n**Blocking.**\n\nB1. [Major] DATA L1/I2 FIX: prose title that must not be used in z.py:9\n'
        self.run.round('job', at=T0)
        self.run.round('job-review', at=T0 + 10, report=prose + self.block(self.FIRST))
        by = self.record()
        self.assertEqual(sorted(k[1] for k in by), ['1', '2', 'm1'])
        b1 = by[('job-review', '1')]
        self.assertEqual((b1['ruleId'], b1['message']['text'], b1['properties']['class'], b1['properties']['blocking']),
                         ('ADJ', 'Saved notes vanish on close', 'lost write', True))
        self.assertEqual(b1['locations'][0]['physicalLocation']['region']['startLine'], 3)
        self.assertEqual((by[('job-review', 'm1')]['properties']['blocking'], by[('job-review', 'm1')]['level']),
                         (False, 'warning'))
        self.assertEqual((self.counts['blocks'], self.unparsed), (1, []))
        self.assertEqual(findings.sarif_errors(findings.sarif_log([r for r in by.values()])), [])

    def test_a_block_missing_a_required_field_is_named_and_the_prose_is_read(self):
        bad = [dict(self.FIRST[0], properties={k: v for k, v in self.FIRST[0]['properties'].items() if k != 'grade'})]
        prose = '1 blocking\n\n**Blocking.**\n\nB1. [Major] DATA L1/I2 ADJ: Prose finding in z.py:9\nClass: prose class.\n'
        self.run.round('job', at=T0)
        self.run.round('job-review', at=T0 + 10, report=prose + self.block(bad))
        by = self.record()
        self.assertEqual(by[('job-review', '1')]['message']['text'], 'Prose finding in z.py:9')
        whys = [u['why'] for u in self.unparsed if u.get('kind') == 'block']
        self.assertEqual(len(whys), 1, self.unparsed)
        self.assertIn('result 1 (B1): properties.grade missing', whys[0])
        self.assertIn('the prose was read instead', whys[0])
        self.assertEqual(self.counts['blocks'], 0)
        out = findings.write(self.run.dir)[0]
        self.assertIn('findings block: job-review.txt line', out)

    def test_a_block_that_is_not_json_is_named(self):
        self.run.round('job', at=T0)
        self.run.round('job-review', at=T0 + 10, report='Blocking: none\n\n```json\n[{"level": \n```\n')
        self.record()
        self.assertTrue(any(u.get('kind') == 'block' and 'not JSON' in u['why'] for u in self.unparsed), self.unparsed)

    def test_a_rereview_block_links_by_the_named_numbers_not_by_text(self):
        self.run.round('job', at=T0)
        self.run.round('job-review', at=T0 + 10, report='2 blocking\n' + self.block(self.FIRST))
        self.run.round('job-fix1', at=T0 + 20)
        # Text that would match the other finding: the named number must win.
        re_block = [{'level': 'error', 'message': {'text': 'Empty list crashes the page'},
                     'properties': {'n': '1', 'grade': 'Major', 'area': 'DATA', 'likelihood': 'L1', 'impact': 'I2',
                                    'class': 'lost write', 'earlierN': 1, 'rereviewVerdict': 'partly'}},
                    {'level': 'note', 'message': {'text': 'Saved notes vanish on close'},
                     'properties': {'n': '2', 'grade': 'Major', 'area': None, 'likelihood': None, 'impact': None,
                                    'class': None, 'earlierN': 'B2', 'rereviewVerdict': 'fixed'}},
                    {'ruleId': 'FAIL', 'level': 'error', 'message': {'text': 'Retry never ends'},
                     'properties': {'n': 'B1', 'grade': 'Major', 'area': 'REL', 'likelihood': 'L2', 'impact': 'I2',
                                    'class': 'unbounded retry', 'introducedByFix': True}}]
        self.run.round('job-rereview', at=T0 + 30, report='2 blocking\n\nprose\n' + self.block(re_block))
        by = self.record()
        fp = lambda k: by[k]['partialFingerprints'][findings.FP_KEY]  # noqa: E731
        self.assertEqual(fp(('job-rereview', 'c1')), fp(('job-review', '1')))
        self.assertEqual(fp(('job-rereview', 'c2')), fp(('job-review', '2')))
        self.assertEqual([by[('job-rereview', c)]['baselineState'] for c in ('c1', 'c2')], ['updated', 'absent'])
        new = by[('job-rereview', '1')]
        self.assertEqual((new['baselineState'], new['properties']['introducedBy']), ('new', 'job-fix1'))
        self.assertEqual(self.counts['blocks'], 2)

    def test_a_rereview_block_naming_an_unknown_finding_falls_back_to_prose(self):
        self.run.round('job', at=T0)
        self.run.round('job-review', at=T0 + 10, report='1 blocking\n' + self.block(self.FIRST[:1]))
        self.run.round('job-fix1', at=T0 + 20)
        re_block = [{'level': 'error', 'message': {'text': 'x'},
                     'properties': {'n': '1', 'grade': 'Major', 'earlierN': 7, 'rereviewVerdict': 'not fixed'}}]
        self.run.round('job-rereview', at=T0 + 30, report='Blocking: none\n' + self.block(re_block))
        self.record()
        self.assertTrue(any(u.get('kind') == 'block' and 'earlierN 7' in u['why'] for u in self.unparsed), self.unparsed)

    WHY = {'age': 'New', 'phaseInjected': 'brief', 'phaseShouldHaveCaught': 'brief-cases', 'qualifier': 'Missing',
           'missing': 'the brief named one case of two',
           'evidence': {'age': 'git blame: abc1234', 'phaseInjected': 'brief line 12: "not named"',
                        'phaseShouldHaveCaught': 'not named', 'qualifier': 'unknown', 'missing': 'unknown'}}

    def why_block(self, *props, asked=True):
        results = [dict(self.FIRST[i], properties=dict(self.FIRST[i]['properties'], **p)) for i, p in enumerate(props)]
        if asked:
            write(self.run, 'job-review.filled.md', 'ask for `phaseShouldHaveCaught`\n')
        self.run.round('job', at=T0)
        self.run.round('job-review', at=T0 + 10, report='2 blocking\n' + self.block(results))
        return self.record()

    def test_why_it_got_in_is_stored_with_a_major_and_unknown_is_accepted(self):
        unknown = {k: 'unknown' for k in self.WHY if k != 'evidence'}
        by = self.why_block(self.WHY, dict(unknown, evidence={k: 'unknown' for k in unknown}))
        self.assertEqual({k: by[('job-review', '1')]['properties'][k] for k in self.WHY}, self.WHY)
        self.assertEqual(by[('job-review', '2')]['properties']['age'], 'unknown')
        self.assertEqual((self.counts['blocks'], self.unparsed), (1, []))

    def test_a_major_without_the_fields_is_stored_and_flagged_a_minor_is_not(self):
        by = self.why_block({}, self.WHY, {})
        self.assertNotIn('age', by[('job-review', '1')]['properties'])
        self.assertEqual(self.counts['blocks'], 1)
        notes = [u['why'] for u in self.unparsed if u.get('kind') == 'why']
        self.assertEqual(notes, ['1 (Major) has no age, phaseInjected, phaseShouldHaveCaught, qualifier, missing, evidence'])
        self.assertEqual(self.counts['unparsed'], 0)
        out = findings.write(self.run.dir)[0]
        self.assertIn('  why it got in: job-review: 1 (Major) has no age, phaseInjected', out)

    def test_a_review_whose_prompt_did_not_ask_is_not_flagged(self):
        by = self.why_block({}, asked=False)
        self.assertNotIn('ageProposed', by[('job-review', '1')]['properties'])
        self.assertEqual(self.unparsed, [])

    def test_with_no_prompt_kept_a_major_carrying_some_why_fields_is_flagged(self):
        self.why_block({'age': 'unknown'}, self.WHY, {'age': 'New'}, asked=False)
        notes = [u['why'] for u in self.unparsed if u.get('kind') == 'why']
        self.assertEqual(notes, ['1 (Major) has no phaseInjected, phaseShouldHaveCaught, qualifier, missing, evidence'])

    def test_a_why_value_outside_its_list_or_evidence_not_an_object_is_a_validation_problem(self):
        for bad, want in (({'age': 'Old'}, "age 'Old'"), ({'phaseInjected': 'Build'}, "phaseInjected 'Build'"),
                          ({'phaseShouldHaveCaught': 'reviewer'}, "phaseShouldHaveCaught 'reviewer'"),
                          ({'qualifier': 'missing'}, "qualifier 'missing'"), ({'evidence': 'a quote'}, 'evidence is not an object'),
                          ({'missing': 3}, 'missing 3 is not text')):
            with self.subTest(bad=bad):
                self.setUp()
                self.why_block(dict(self.WHY, **bad))
                whys = [u['why'] for u in self.unparsed if u.get('kind') == 'block']
                self.assertEqual(len(whys), 1, self.unparsed)
                self.assertIn(f'result 1 (B1): {want}', whys[0])
                self.assertEqual(self.counts['blocks'], 0)

    def test_the_real_review_before_these_fields_records_as_before(self):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', 'findings', 'mf-review.report.md'),
                  encoding='utf-8') as f:
            report = f.read()
        self.run.round('mf', at=T0)
        self.run.round('mf-review', at=T0 + 10, report=report)
        by = self.record()
        self.assertEqual(sorted((k[1], r['properties']['grade'], r['properties']['blocking']) for k, r in by.items()),
                         [('1', 'Major', True), ('2', 'Major', True), ('3', 'Major', True), ('4', 'Major', True),
                          ('5', 'Major', True), ('p1', None, False), ('x1', None, False), ('x2', None, False)])
        for r in by.values():
            self.assertFalse(set(r['properties']) & (set(findings.WHY_FIELDS) | {'ageProposed', 'ageDisagrees'}))
        # The block is rejected for its "Pre-existing" grade, so the prose, kept whole in the fixture, is read.
        self.assertEqual([(u.get('kind'), u['why'][:60]) for u in self.unparsed],
                         [('block', "findings block not read (result 6 (P1): grade 'Pre-existing'")])
        self.assertEqual(self.counts['blocks'], 0)


if __name__ == '__main__':
    unittest.main()
