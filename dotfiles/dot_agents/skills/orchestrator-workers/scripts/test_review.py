import os
import re
import shutil
import subprocess
import tempfile
import unittest

import brief
import mine
import route

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
    '1. Each finding: fixed, partly fixed or not fixed, with file:line. Fixed means its scenario can no longer happen; '
    'say how you know.',
    "2. Each finding's test: does it check the finding's scenario, and would it fail with the fix removed? Read it; you "
    'need not run it.',
    '3. Harm the fix diff itself introduces: owner data lost or corrupted, a secret or private text leaking, an approval '
    'or confinement bypassed, or a flow that no longer completes, in normal use or at an unlucky moment (Stop, restart, '
    'reload, a failing source). Only lines this diff changes; nothing else counts here.',
]
REREVIEW_REPORT = [
    '1. The verdict as the first line: `Blocking: none`, or `N blocking` (findings not fixed or partly fixed, plus harm '
    'the fix introduced).',
    '2. **Findings.** One line each: number, fixed / partly / not fixed, file:line, how you know, and whether its test '
    'would fail without the fix.',
    '3. **New harm.** For each: `B1. [Major] AREA L1/I2 CAUSE: title`, its scenario, file:line, VERIFIED or INFERRED '
    'with what would confirm it, and a fix in one line.',
    '4. **Corrections** to the fix report: one line each.',
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

    def test_the_rereview_checks_only_the_named_fixes_and_pauses_for_the_owner(self):
        raw = read('assets', 'rereview.md')
        t = visible(raw)
        for part in ('You are a read-only reviewer', 'SHORT RE-REVIEW', '`Blocking: none`', '{{FIX_COMMITS}}',
                     '{{FINDING_1}}', 'partly fixed'):
            self.assertIn(part, t)
        self.assertIn("\nDo not look for other cases of each finding's kind, and do not review code the fix does not "
                      'touch', t)
        for hunt in ('whole class', '{{CLASS_1}}', '{{RUBRIC}}', 'member'):
            self.assertNotIn(hunt, t)
        self.assertEqual(numbered(t, '\nCHECK, nothing else:\n', '\nDo not look'), REREVIEW_CHECKS)
        self.assertEqual(numbered(t, 'REPORT, in this order', 'Mark every claim'), REREVIEW_REPORT)
        rule = ' '.join(raw.split('-->', 1)[0].split())
        self.assertIn('a finding it leaves open pauses the item for the owner (owner, 2026-10-31, confirmed 2026-11-02)',
                      rule)
        self.assertNotIn('one more fix round', rule)

    def test_no_skill_text_gives_a_finding_left_open_another_fix_round(self):
        texts = {p: read(*p.split('/')) for p in ['SKILL.md'] + [f'references/{n}' for n in
                                                                  sorted(os.listdir(os.path.join(SKILL, 'references')))
                                                                  if n.endswith('.md')]}
        for path, text in texts.items():
            flat = ' '.join(text.split())
            for said in ('one more fix round', 'another fix round', 'a second fix round', 'Fixes made after the re-review go'):
                self.assertNotIn(said, flat, path)
        lifecycle = ' '.join(read('SKILL.md').split('## Lifecycle', 1)[1].split('\n## ', 1)[0].split())
        self.assertIn('A finding the re-review leaves open pauses the item for the owner (owner, 2026-10-31, confirmed '
                      '2026-11-02)', lifecycle)

    def test_the_critique_asks_for_each_cited_standard_s_own_names(self):
        t = visible(read('assets', 'critique-research.md'))
        checks = numbered(t, 'CHECK, in this order:', '{{ITEM_CHECKS_OR_DELETE}}')
        standards = [c for c in checks if c.startswith('6. Standards')]
        self.assertEqual(len(standards), 1, checks)
        for part in ('field names, values and terms', 'invents its own name where the standard has one'):
            self.assertIn(part, standards[0])
        report = numbered(t, 'REPORT, nothing else:', 'Mark every claim')
        self.assertIn('**Invented names**', ' '.join(report))
        self.assertEqual([r.split('.', 1)[0] for r in report], [str(n) for n in range(1, len(report) + 1)])


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

    def review(self, prompt_text, script=os.path.join(HERE, 'review.sh'), prompt_path=None, extra=(), under=()):
        prompt_path = prompt_path or os.path.join(self.tmp, 'my prompts', 'x review.md')
        os.makedirs(os.path.dirname(prompt_path), exist_ok=True)
        with open(prompt_path, 'w', encoding='utf-8') as f:
            f.write(prompt_text)
        p = subprocess.run([*under, 'bash', script, '--author-model', 'gpt-6.1-sol', '--load-wait', '0', '--no-classifier',
                            *extra, 'x-review', self.wt, prompt_path],
                           capture_output=True, text=True, env=self.env, timeout=60, stdin=subprocess.DEVNULL)
        with open(prompt_path, encoding='utf-8') as f:
            self.assertEqual(f.read(), prompt_text, 'the original prompt was modified')
        return p

    def launched_prompt(self):
        with open(self.args, encoding='utf-8') as f:
            return f.read().split('\0')[-2]

    def add_dirs(self):
        with open(self.args, encoding='utf-8') as f:
            argv = f.read().split('\0')
        return [argv[i + 1] for i, a in enumerate(argv) if a == '--add-dir']

    def test_review_started_by_a_caffeinate_process_is_refused_and_nothing_launches(self):
        under = ['bash', '-c', 'exec -a caffeinate /bin/bash -c "\\"\\$@\\"; exit \\$?" inner "$@"', 'outer']
        p = self.review('You are a read-only reviewer. caffeinate was killed.\n', under=under)
        self.assertEqual(p.returncode, 2, p.stderr)
        self.assertIn('review.sh: refused: this launcher runs under caffeinate (pid ', p.stderr)
        self.assertEqual(p.stderr.count('\n'), 1, p.stderr)
        self.assertFalse(os.path.exists(self.args))
        self.assertEqual(os.listdir(self.run_dir), [])

    def test_a_research_critique_reads_the_run_folder_and_the_project(self):
        critique = '<!-- launch note -->\nYou are a read-only critic from a different model family.\n'
        project = os.path.join(self.tmp, 'project repo')
        os.makedirs(project)
        p = self.review(critique, extra=('--project', project))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.add_dirs(), [self.run_dir, project])
        self.assertNotIn('run folder only', p.stderr)
        p = self.review(critique)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.add_dirs(), [self.run_dir])
        self.assertIn('review.sh: no --project given, so the critic reads the run folder only', p.stderr)

    def test_a_code_review_gets_no_run_folder_and_a_bad_project_is_refused(self):
        p = self.review('You are a read-only reviewer.\n')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.add_dirs(), [])
        os.remove(self.args)
        p = self.review('You are a read-only critic.\n', extra=('--project', os.path.join(self.tmp, 'gone')))
        self.assertEqual(p.returncode, 2)
        self.assertIn('--project needs a folder', p.stderr)
        self.assertFalse(os.path.exists(self.args))

    def test_the_critique_template_launch_line_names_the_project(self):
        t = read('assets', 'critique-research.md')
        self.assertIn('--project <project repository>', t)
        reads = visible(t).split('WHAT TO READ', 1)[1].split('CHECK, in this order', 1)[0]
        line = next((x for x in reads.split('\n') if 'run folder' in x), '')
        for part in ('You can also read the run folder', 'the project repository', "check the note's claims",
                     'against them, read-only'):
            self.assertIn(part, line)

    def test_rubric_is_filled_into_a_copy_and_launched(self):
        text = '<!-- {{RUBRIC}} is filled -->\nYou are a read-only reviewer.\n==== RUBRIC ====\n{{RUBRIC}}\n==== END ====\nTag & go \\1 /x/'
        p = self.review(text)
        self.assertEqual(p.returncode, 0, p.stderr)
        filled = os.path.join(self.run_dir, 'x-review.filled.md')
        with open(filled, encoding='utf-8') as f:
            body = f.read()
        rubric = filled_rubric()
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
        rubric = filled_rubric()
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
        rubric = filled_rubric()
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

    def patch(self, *paths):
        with open(os.path.join(self.wt, 'REVIEW-DIFF.patch'), 'w', encoding='utf-8') as f:
            f.writelines(f'diff --git a/{p} b/{p}\n--- a/{p}\n+++ b/{p}\n@@ -1 +1 @@\n-a\n+b\n' for p in paths)

    def scope_line(self, extra=(), want_rc=0):
        p = self.review('==== RUBRIC ====\n{{RUBRIC}}\n==== END ====\n', extra=extra)
        self.assertEqual(p.returncode, want_rc, p.stderr)
        body = self.filled().split('==== END ====')[0].rstrip('\n')
        self.assertTrue(body.startswith('==== RUBRIC ====\n' + read('references', 'rubric.md').rstrip('\n') + '\n\nScope'))
        self.assertTrue(self.launched_prompt().startswith(self.filled()))
        return body.rsplit('\n', 1)[1], p.stderr

    def test_a_tool_diff_is_graded_at_scope_tool(self):
        self.patch(TOOL_A, TOOL_B)
        line, err = self.scope_line()
        self.assertEqual(line, 'Scope of this change: tool (every changed file is under dotfiles/dot_agents/skills/*/scripts/).'
                               ' Grade with the Scope rule in section 4.')
        self.assertNotIn('REVIEW-DIFF', err)

    def test_a_product_diff_is_graded_at_scope_product(self):
        self.patch('src/app.ts', 'dotfiles/dot_agents/skills/kb/SKILL.md', 'scripts/route.py')
        line, _ = self.scope_line()
        self.assertEqual(line, 'Scope of this change: product (some changed files are outside'
                               ' dotfiles/dot_agents/skills/*/scripts/). Grade with the Scope rule in section 4.')

    def test_a_mixed_diff_is_product_with_its_check_tool_files_listed_as_tool(self):
        self.patch('src/app.ts', TOOL_B, TOOL_A)
        line, _ = self.scope_line()
        self.assertEqual(line, 'Scope of this change: product (some changed files are outside'
                               ' dotfiles/dot_agents/skills/*/scripts/). Grade with the Scope rule in section 4.'
                               f' Graded as tool whatever the scope, being check tools: {TOOL_B}, {TOOL_A}.')

    def test_an_explicit_scope_wins_and_a_bad_one_is_refused(self):
        self.patch(TOOL_A)
        line, _ = self.scope_line(extra=('--scope', 'product'))
        self.assertEqual(line, 'Scope of this change: product (given by --scope). Grade with the Scope rule in section 4.'
                               f' Graded as tool whatever the scope, being check tools: {TOOL_A}.')
        self.patch('src/app.ts')
        line, _ = self.scope_line(extra=('--scope', 'tool'))
        self.assertEqual(line, 'Scope of this change: tool (given by --scope). Grade with the Scope rule in section 4.')
        os.remove(self.args)
        for bad in (('--scope', 'Tool'), ('--scope',)):
            p = self.review('{{RUBRIC}}\n', extra=bad)
            self.assertEqual(p.returncode, 2, bad)
            self.assertIn('review.sh: --scope takes product or tool', p.stderr)
            self.assertFalse(os.path.exists(self.args))

    def test_no_patch_is_graded_at_scope_product_and_said_on_stderr(self):
        line, err = self.scope_line()
        self.assertEqual(line, 'Scope of this change: product (no REVIEW-DIFF.patch in the worktree). Grade with the Scope rule'
                               ' in section 4.')
        self.assertIn('review.sh: no REVIEW-DIFF.patch in ', err)
        with open(os.path.join(self.wt, 'REVIEW-DIFF.patch'), 'w') as f:
            f.write('')
        line, err = self.scope_line()
        self.assertIn('product (REVIEW-DIFF.patch names no file)', line)
        self.assertNotIn('REVIEW-DIFF', err)

    def test_patch_paths_reads_renames_binaries_quoted_and_spaced_names(self):
        diff = ('diff --git a/old name.py b/old name.py\nindex 1..2 100644\nBinary files differ\n'
                'diff --git a/x.py b/y.py\nsimilarity index 90%\nrename from x.py\nrename to y.py\n'
                'diff --git "a/caf\\303\\251.py" "b/caf\\303\\251.py"\nold mode 100644\nnew mode 100755\n'
                'diff --git a/n.py b/n.py\nnew file mode 100644\n--- /dev/null\n+++ b/n.py\t\n')
        self.assertEqual(route.patch_paths(diff), ['caf\\303\\251.py', 'n.py', 'old name.py', 'x.py', 'y.py'])
        self.assertEqual(route.review_scope('diff --git a/x.py b/' + TOOL_A + '\nrename from x.py\nrename to ' + TOOL_A + '\n')[0],
                         'product')


TOOL_A = 'dotfiles/dot_agents/skills/orchestrator-workers/scripts/route.py'
TOOL_B = 'dotfiles/dot_agents/skills/kb/scripts/kb.py'


def filled_rubric():
    return (read('references', 'rubric.md').rstrip('\n') + '\n\nScope of this change: product (no REVIEW-DIFF.patch in the'
            ' worktree). Grade with the Scope rule in section 4.')


if __name__ == '__main__':
    unittest.main()
