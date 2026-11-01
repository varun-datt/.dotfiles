import os
import re
import shutil
import subprocess
import tempfile
import unittest

import brief
import mine

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
D1 = 'Blocker and Major block (I1 at L1–L2; I2 at L1–L2; I3 at L1). Minor goes to debt'
CAUSES = ('MUST', 'SPEC', 'ADJ', 'ORDER', 'FAIL', 'BOUND', 'EDGE', 'PLAT', 'DESIGN', 'READ', 'REUSE', 'UIQ', 'CONV',
          'TEST', 'PRE')


def read(*parts):
    with open(os.path.join(SKILL, *parts), encoding='utf-8') as f:
        return f.read()


def visible(text):
    return re.sub(r'<!--.*?-->', '', text, flags=re.S)


def numbered(text, start, end):
    return re.findall(r'^\d+\. .*$', text.split(start, 1)[1].split(end, 1)[0], flags=re.M)


REVIEW_CHECKS = [
    '1. Each MUST in the task, and each owner ruling it cites: met, partly met or not met, with file:line.',
    "2. The author's impact map and case table: what reads or writes the changed code that the map misses; cases that "
    'apply but are missing; rows whose test could not fail; facts marked VERIFIED without a source.',
    '3. Data: what the owner could lose, overwrite or see misattributed, including when Stop, close, reload, restart or '
    'a failing source lands mid-step.',
    '4. Security and privacy: outside text reaching a model, a command or HTML unfenced; secrets or private content in '
    'logs, cards, prompts or files; path escape; argument lists built from unvalidated input. '
    '{{PROJECT_SECURITY_SECTIONS}}',
    '5. Reliability: ordering, late events, retries, double actions, timeouts with no deadline.',
    "6. The owner's experience: a flow that breaks or misleads, focus taken while typing, contrast below WCAG AA, "
    'attention drawn to a normal state.',
    '7. Performance, compatibility and paid spend, at the owner\'s real data sizes and settings.',
    '8. The checks: do the new tests fail when the behaviour is removed? Is each mutation control killed by a failing '
    'assertion, not merely invalid (a crash, compile error or timeout)? Could a timing assumption flake on a loaded '
    'machine? Does an existing test now fail?',
    "9. Claims in the author's report that the diff does not support.",
    '10. Gaps against the acceptance rows the task names.',
    '11. Reuse: code that builds what already exists: a dependency in the manifest (read it; never judge what is '
    "installed from a worktree's `node_modules`), a decision the task cites, an installed skill or an in-repo helper. "
    'Name it with file:line.',
]
REVIEW_REPORT = [
    '1. The verdict as the first line: `Blocking: none`, or `N blocking` where N counts Blockers and Majors.',
    '2. **Blocking.** For each Blocker or Major: `B1. [Major] AREA L1/I2 CAUSE: title`, then `Class:` and every member '
    'of the class you found, its scenario, file:line, the reason for each grade, VERIFIED or INFERRED with the command '
    'or test that would confirm it, and a fix in one line that covers the whole class.',
    '3. **Check.** Possible Majors with no concrete scenario yet: one line each, with what would confirm them.',
    '4. **Minor.** One line each: `AREA Lx/Ix CAUSE: what, file:line; class: ...`.',
    '5. **Pre-existing.** One line each.',
    "6. **Corrections** to the author's report: one line each.",
    '7. `Nits: N` as one line; do not list them.',
    '8. **Not checked**, and why.',
]
REREVIEW_CHECKS = [
    '1. Each finding: fixed, partly fixed or not fixed, with file:line. A finding is fixed when its failure scenario '
    'can no longer happen; say how you know.',
    "2. The class: the fix must cover the finding's whole class, not only the member the review named. List each member "
    'the fix report names and the test that covers it; a member with no test, or one in the code that the report leaves '
    'out, is not fixed. A fix that covers some members of a class is "partly fixed", and the finding stays open.',
    '3. New problems the fix diff introduces, graded with the rubric. Look hardest at: {{NEARBY_RISKS_TO_CHECK}}. A fix '
    'that trades one race or loss for another is a new Major.',
    "4. Do the fix's tests fail when the fix is removed? Does an existing test now fail or flake?",
    '5. Claims in the fix report that the diff does not support.',
]
REREVIEW_REPORT = [
    '1. The verdict as the first line: `Blocking: none`, or `N blocking`.',
    '2. **Findings.** One line each: number, fixed / partly / not fixed, file:line, how you know, and each class member '
    'with its test or "no test".',
    '3. **New blocking.** For each Blocker or Major the fix introduced: `B1. [Major] AREA L1/I2 CAUSE: title`, its '
    'class, its scenario, file:line, the reason for each grade, VERIFIED or INFERRED with what would confirm it, and a '
    'fix in one line.',
    '4. **New minor.** One line each.',
    '5. **Corrections** to the fix report: one line each.',
    '6. **Outside scope**: one line each. Then `Nits: N`.',
]


class PromptTextTest(unittest.TestCase):
    def test_the_rubric_holds_the_grades_and_the_d1_matrix(self):
        r = read('references', 'rubric.md')
        for word in ('Blocker', 'Major', 'Minor', 'Nit', 'L1 ', 'L2 ', 'L3 ', 'I1 ', 'I2 ', 'I3 '):
            self.assertIn(word, r)
        self.assertIn('\n| | L1 normal | L2 plausible | L3 contrived |\n', r)
        rows = {m.group(1): [c.strip() for c in m.group(2).split('|')]
                for m in re.finditer(r'^\| \*\*(I\d) [a-z]+\*\* \|(.*)\|$', r, flags=re.M)}
        self.assertEqual(rows, {'I1': ['Blocker', 'Blocker', 'Minor, tagged SEC or DATA for the owner'],
                                'I2': ['Major', 'Major', 'Minor'], 'I3': ['Major', 'Minor', 'Minor'],
                                'I4': ['Minor', 'Nit', 'Nit']})
        blocking = {(i, f'L{n + 1}') for i, cells in rows.items() for n, c in enumerate(cells) if c in ('Blocker', 'Major')}
        self.assertEqual(blocking, {('I1', 'L1'), ('I1', 'L2'), ('I2', 'L1'), ('I2', 'L2'), ('I3', 'L1')})
        for row in ('| Blocker, Major | Blocks: one fix round | Fix brief; re-review checks the fix |',
                    '| Minor | Does not block | One line on the repository\'s tech-debt list |',
                    '| Nit | Does not block | Counted in one line, never listed |',
                    '| Pre-existing | Does not block | Tech-debt list if it would be Major, else dropped |',
                    '| Correction | Does not block | The orchestrator fixes the record |'):
            self.assertIn('\n' + row + '\n', r)

    def test_skill_md_states_the_same_rule_and_points_at_the_rubric(self):
        lifecycle = read('SKILL.md').split('## Lifecycle', 1)[1].split('\n## ', 1)[0]
        self.assertIn(D1, ' '.join(lifecycle.split()))
        self.assertIn('references/rubric.md', lifecycle)
        self.assertIn('docs/tech-debt.md', lifecycle)

    def test_the_review_prompt_holds_every_required_part_once(self):
        t = visible(read('assets', 'review.md'))
        for part in ('You are a read-only reviewer', '{{TASK}}', '{{RUBRIC}}', '`Blocking: none`', '`N blocking`',
                     'impact map and case table', '**Minor.** One line each', '`Nits: N`', 'Tag every finding',
                     '{{RISK_CHECKS_OR_DELETE}}', '{{PRIOR_RULINGS|none}}', 'acceptance rows'):
            self.assertEqual(t.count(part), 1, part)
        for cause in CAUSES:
            self.assertEqual(len(re.findall(rf'\b{cause} \(', t)), 1, cause)
        self.assertLess(t.index('The verdict as the first line'), t.index('**Blocking.**'))
        self.assertEqual(numbered(t, 'CHECK, in this order', '{{RISK_CHECKS_OR_DELETE}}'), REVIEW_CHECKS)
        self.assertEqual(numbered(t, 'REPORT, in this order', 'Mark every claim'), REVIEW_REPORT)
        self.assertIn('\nBlocking rule ({{BLOCKING_RULE_SOURCE}}): Blocker and Major block; nothing else does.\n', t)

    def test_the_rereview_checks_every_member_of_the_class(self):
        t = visible(read('assets', 'rereview.md'))
        for part in ('You are a read-only reviewer', '{{RUBRIC}}', '`Blocking: none`', '{{CLASS_1}}', 'whole class',
                     'partly fixed'):
            self.assertIn(part, t)
        self.assertRegex(t, r'member .*has no test|member with no test')
        self.assertEqual(numbered(t, '\nCHECK\n', 'Out of scope'), REREVIEW_CHECKS)
        self.assertEqual(numbered(t, 'REPORT, in this order', 'Mark every claim'), REREVIEW_REPORT)
        self.assertIn('\nBlocking rule ({{BLOCKING_RULE_SOURCE}}): a Blocker or Major that is still open, or that the '
                      'fix introduced, blocks; nothing else does.\n', t)


class VerdictTest(unittest.TestCase):
    def test_new_format_messages_give_the_same_verdict(self):
        cases = {
            'Blocking: none\n\n**Check.**\n- none\n\n**Minor.**\n- COR L3/I2 EDGE: x, a.py:3; class: y\n\nNits: 2': 'Blocking: none',
            '2 blocking\n\n**Blocking.**\n\nB1. [Major] COR L1/I2 MUST: a\nClass: b\n\nB2. [Blocker] DATA L2/I1 ORDER: c\n\nNits: 0': '2 blocking',
            '# Review of p3\n\n2 blocking\n\n**Blocking.**\n\nB1. [Major] REL L2/I2 FAIL: a': '2 blocking',
            '## Verdict\n\n**Blocking: none**\n\nNits: 4': 'Blocking: none',
            '1 blocking\n\n**Findings.**\n1. partly fixed, a.py:9; members: x has a test, y no test': '1 blocking',
        }
        for msg, want in cases.items():
            self.assertEqual(mine.verdict_line(msg), want, msg)


class ReviewShTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='ow review ')
        self.addCleanup(shutil.rmtree, self.tmp)
        self.run_dir, self.wt, bin_dir = (os.path.join(self.tmp, n) for n in ('run dir', 'wt', 'bin'))
        for d in (self.run_dir, self.wt, bin_dir):
            os.makedirs(d)
        self.args = os.path.join(self.tmp, 'args')
        fake = os.path.join(bin_dir, 'copilot')
        with open(fake, 'w') as f:
            f.write('#!/bin/sh\nprintf "%s\\0" "$@" > "' + self.args + '"\n'
                    'printf \'%s\\n\' \'{"type":"assistant.message","data":{"content":"Blocking: none"}}\'\n'
                    'printf \'%s\\n\' \'{"type":"result","exitCode":0}\'\n')
        os.chmod(fake, 0o755)
        self.env = {**os.environ, 'PATH': bin_dir + os.pathsep + os.environ['PATH'], 'OW_RUN_DIR': self.run_dir,
                    'PYTHONDONTWRITEBYTECODE': '1', 'HOME': self.tmp}

    def review(self, prompt_text, script=os.path.join(HERE, 'review.sh'), prompt_path=None):
        prompt_path = prompt_path or os.path.join(self.tmp, 'my prompts', 'x review.md')
        os.makedirs(os.path.dirname(prompt_path), exist_ok=True)
        with open(prompt_path, 'w', encoding='utf-8') as f:
            f.write(prompt_text)
        p = subprocess.run(['bash', script, '--author-model', 'gpt-6.1-sol', '--load-wait', '0', '--no-classifier',
                            'x-review', self.wt, prompt_path],
                           capture_output=True, text=True, env=self.env, timeout=60, stdin=subprocess.DEVNULL)
        with open(prompt_path, encoding='utf-8') as f:
            self.assertEqual(f.read(), prompt_text, 'the original prompt was modified')
        return p

    def launched_prompt(self):
        with open(self.args, encoding='utf-8') as f:
            return f.read().split('\0')[-2]

    def test_rubric_is_filled_into_a_copy_and_launched(self):
        text = '<!-- {{RUBRIC}} is filled -->\nYou are a read-only reviewer.\n==== RUBRIC ====\n{{RUBRIC}}\n==== END ====\nTag & go \\1 /x/'
        p = self.review(text)
        self.assertEqual(p.returncode, 0, p.stderr)
        filled = os.path.join(self.run_dir, 'x-review.filled.md')
        with open(filled, encoding='utf-8') as f:
            body = f.read()
        rubric = read('references', 'rubric.md').rstrip('\n')
        self.assertEqual(body, text.replace('\n{{RUBRIC}}\n', '\n' + rubric + '\n'))
        self.assertIn('<!-- {{RUBRIC}} is filled -->', body)
        self.assertTrue(self.launched_prompt().startswith(body))
        with open(os.path.join(self.run_dir, 'x-review.txt')) as f:
            self.assertEqual(f.read(), 'Blocking: none\n')

    def test_a_prompt_without_rubric_launches_unchanged(self):
        text = 'You are a read-only reviewer. Check `{{NOT_A_FIELD}}` and <!-- {{NOTE}} -->.\n'
        p = self.review(text)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.run_dir, 'x-review.filled.md')))
        self.assertTrue(self.launched_prompt().startswith(text))

    def test_another_unfilled_placeholder_is_refused_and_nothing_launches(self):
        for text in ('{{RUBRIC}}\n{{TASK}}\n', 'no rubric here {{FINDING_1}}\n'):
            p = self.review(text)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn('unfilled placeholders', p.stderr)
            self.assertFalse(os.path.exists(self.args), text)
            self.assertFalse(os.path.exists(os.path.join(self.run_dir, 'x-review.jsonl')))

    def test_a_missing_rubric_is_refused_and_nothing_launches(self):
        scripts = os.path.join(self.tmp, 'copy', 'scripts')
        os.makedirs(scripts)
        shutil.copy(os.path.join(HERE, 'review.sh'), scripts)
        p = self.review('{{RUBRIC}}\n', script=os.path.join(scripts, 'review.sh'))
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('no rubric at', p.stderr)
        self.assertFalse(os.path.exists(self.args))

    def filled(self):
        with open(os.path.join(self.run_dir, 'x-review.filled.md'), encoding='utf-8') as f:
            return f.read()

    def test_quoted_placeholder_examples_are_left_as_written(self):
        rubric = read('references', 'rubric.md').rstrip('\n')
        examples = ('Say `{{RUBRIC}} {{TASK}}` here.', '| slot | `{{RUBRIC}}` | `{{TASK}}` |',
                    'Spans: `` `{{RUBRIC}}` `` and `{{TASK}}`.', '> quoted: `{{RUBRIC}}` and `{{TASK}}`',
                    '> {{RUBRIC}} `{{TASK}}`'.replace('{{RUBRIC}}', '`{{RUBRIC}}`'),
                    '```\nuse `{{RUBRIC}}` and `{{TASK}}`\n```', '````md\n```\n`{{RUBRIC}}` `{{TASK}}`\n```\n````',
                    '~~~\n`{{RUBRIC}}` `{{TASK}}`\n~~~', '<!-- ```\n-->\n`{{RUBRIC}}`')
        for ex in examples:
            self.assertEqual(brief.problems(ex), [], ex)
            for head, tail in (('You are a read-only reviewer.\n' + ex + '\n==== RUBRIC ====\n', '\n==== END ====\n'),
                               ('==== RUBRIC ====\n', '\n' + ex + '\n')):
                p = self.review(head + '{{RUBRIC}}' + tail)
                self.assertEqual(p.returncode, 0, ex + p.stderr)
                self.assertEqual(self.filled(), head + rubric + tail, ex)
            if os.path.exists(self.args):
                os.remove(self.args)
            p = self.review(ex + '\n')
            self.assertEqual(p.returncode, 0, ex + p.stderr)
            self.assertTrue(self.launched_prompt().startswith(ex + '\n'), ex)

    def test_a_bare_placeholder_in_a_fence_or_quote_is_left_and_refused_as_brief_py_would(self):
        for ex in ('```\n{{RUBRIC}}\n```', '````\n```\n{{RUBRIC}}\n````', '```\n~~~\n{{RUBRIC}}\n```',
                   '```\n``` x\n{{RUBRIC}}\n```', '> {{RUBRIC}}', '  > {{TASK}}', '```\nunclosed\n{{RUBRIC}}'):
            self.assertNotEqual(brief.problems(ex + '\n'), [], ex)
            if os.path.exists(self.args):
                os.remove(self.args)
            p = self.review('==== RUBRIC ====\n{{RUBRIC}}\n' + ex + '\n')
            self.assertNotEqual(p.returncode, 0, ex)
            self.assertIn('unfilled placeholders: {{', p.stderr, ex)
            self.assertFalse(os.path.exists(self.args), ex)

    def test_a_bare_slot_outside_fences_and_code_is_filled(self):
        rubric = read('references', 'rubric.md').rstrip('\n')
        for head, tail in (('````\n```\n````\n', '\n'), ('    ```\n', '\n'), ('```a`b\n', '\n'),
                           ('   ~~~ md\n`x`\n   ~~~\n', '\n'), ('x ` ', ' y\n'), ('<!-- ```\n-->\n', '\n'),
                           ('`a` ', ' `{{TASK}}`\n'), ('', ' and {{RUBRIC}} twice\n'), ('`` ', ' ``\n'),
                           ('`a` `', '\n')):
            p = self.review(head + '{{RUBRIC}}' + tail)
            self.assertEqual(p.returncode, 0, head + p.stderr)
            self.assertEqual(self.filled(), head + rubric + tail.replace('{{RUBRIC}}', rubric), head)

    def test_the_rubric_holds_nothing_that_could_shift_code_spans_or_placeholders(self):
        r = read('references', 'rubric.md')
        self.assertNotIn('`', r)
        self.assertNotIn('{{', r)
        self.assertNotIn('<!--', r)

    def test_a_prompt_named_like_its_filled_copy_is_not_overwritten(self):
        p = self.review('{{RUBRIC}}\n', prompt_path=os.path.join(self.run_dir, '.', 'x-review.filled.md'))
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('would be overwritten', p.stderr)
        self.assertFalse(os.path.exists(self.args))


if __name__ == '__main__':
    unittest.main()
