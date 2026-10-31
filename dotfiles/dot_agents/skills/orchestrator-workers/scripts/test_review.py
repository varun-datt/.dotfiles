import os
import re
import shutil
import subprocess
import tempfile
import unittest

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


class PromptTextTest(unittest.TestCase):
    def test_the_rubric_holds_the_grades_and_the_d1_matrix(self):
        r = read('references', 'rubric.md')
        for word in ('Blocker', 'Major', 'Minor', 'Nit', 'L1 ', 'L2 ', 'L3 ', 'I1 ', 'I2 ', 'I3 '):
            self.assertIn(word, r)
        rows = {m.group(1): [c.strip() for c in m.group(2).split('|')]
                for m in re.finditer(r'^\| \*\*(I\d) [a-z]+\*\* \|(.*)\|$', r, flags=re.M)}
        blocking = {(i, f'L{n + 1}') for i, cells in rows.items() for n, c in enumerate(cells) if c in ('Blocker', 'Major')}
        self.assertEqual(blocking, {('I1', 'L1'), ('I1', 'L2'), ('I2', 'L1'), ('I2', 'L2'), ('I3', 'L1')})

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

    def test_the_rereview_checks_every_member_of_the_class(self):
        t = visible(read('assets', 'rereview.md'))
        for part in ('You are a read-only reviewer', '{{RUBRIC}}', '`Blocking: none`', '{{CLASS_1}}', 'whole class',
                     'partly fixed'):
            self.assertIn(part, t)
        self.assertRegex(t, r'member .*has no test|member with no test')


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

    def test_a_prompt_named_like_its_filled_copy_is_not_overwritten(self):
        p = self.review('{{RUBRIC}}\n', prompt_path=os.path.join(self.run_dir, '.', 'x-review.filled.md'))
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('would be overwritten', p.stderr)
        self.assertFalse(os.path.exists(self.args))


if __name__ == '__main__':
    unittest.main()
