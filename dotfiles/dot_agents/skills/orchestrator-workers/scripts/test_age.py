import json, os, subprocess, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import age  # noqa: E402
import findings  # noqa: E402
from test_mine import Run, T0  # noqa: E402


class Repo:
    def __init__(self, folder):
        self.wt = folder
        self.git('init', '-q', '-b', 'ow/a', folder, at=None)

    def git(self, *args, at=''):
        pre = ['git'] + (['-C', self.wt] if at is not None else [])
        return subprocess.run(pre + ['-c', 'core.hooksPath=/dev/null', '-c', 'user.name=t', '-c',
                                     'user.email=t@example.invalid', *args],
                              check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout.strip()

    def commit(self, name, text, msg):
        with open(os.path.join(self.wt, name), 'w') as f:
            f.write(text)
        self.git('add', name)
        self.git('commit', '-qm', msg)
        return self.git('rev-parse', 'HEAD')


class AgeTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.r = Repo(os.path.join(tmp.name, 'wt'))
        self.base = self.r.commit('f.py', 'a = 1\nb = 2\nc = 3\nd = 4\n', 'base')
        self.build = self.r.commit('f.py', 'a = 1\n  b = 2\nc = 30\nd = 4\ne = 5\n', 'build')
        self.r.commit('gone.py', 'x\n', 'build: a file deleted later')
        self.r.git('rm', '-q', 'gone.py')
        self.r.git('commit', '-qm', 'build: delete')
        self.start = self.r.git('rev-parse', 'HEAD')
        self.fix = self.r.commit('f.py', 'a = 1\n  b = 2\nc = 30\nd = 40\ne = 5\n', 'fix')

    def age(self, path, line):
        return age.propose(self.r.wt, self.base, path, line, self.start)

    def test_each_age_from_blame_and_the_build_and_fix_labels(self):
        self.assertEqual(self.age('f.py', 1)['age'], 'Base')
        self.assertEqual(self.age('f.py', 1)['commit'], self.base)
        new = self.age('f.py', 5)
        self.assertEqual((new['age'], new['commit']), ('New', self.build))
        self.assertIn('only added lines', new['reason'])
        self.assertEqual(self.age('f.py', 3)['age'], 'Rewritten')
        self.assertEqual((self.age('f.py', 4)['age'], self.age('f.py', 4)['commit']), ('ReFixed', self.fix))

    def test_a_whitespace_only_change_keeps_the_line_s_age_because_blame_runs_with_w(self):
        self.assertEqual(self.age('f.py', 2)['age'], 'Base')

    def test_a_file_renamed_on_the_branch_is_followed(self):
        self.r.git('mv', 'f.py', 'g.py')
        self.r.git('commit', '-qm', 'build: rename')
        self.assertEqual(self.age('g.py', 1)['age'], 'Base')
        self.assertEqual(self.age('g.py', 3)['age'], 'Rewritten')

    def test_what_cannot_be_decided_is_unknown_with_the_reason(self):
        for path, line, want in (('f.py', 99, 'git blame failed: fatal: file f.py has only 5 lines'),
                                 ('gone.py', 1, 'gone.py is not in HEAD'), ('f.py', 0, 'out of range')):
            r = self.age(path, line)
            self.assertEqual(r['age'], 'unknown', (path, line))
            self.assertIn(want, r['reason'])
        with open(os.path.join(self.r.wt, 'f.py'), 'a') as f:
            f.write('f = 6\n')
        self.assertIn('uncommitted change', self.age('f.py', 1)['reason'])
        self.r.git('checkout', '-q', 'f.py')
        r = age.propose(self.r.wt, '0123456789abcdef0123456789abcdef01234567', 'f.py', 1)
        self.assertEqual(r['age'], 'unknown')
        self.assertIn('branch history could not be read', r['reason'])

    def test_a_line_from_main_merged_in_after_the_base_is_unknown(self):
        self.r.git('checkout', '-q', '-b', 'main', self.base)
        self.r.commit('m.py', 'from main\n', 'main work')
        self.r.git('checkout', '-q', 'ow/a')
        self.r.git('merge', '-q', '--no-ff', '-m', 'merge main', 'main')
        r = self.age('m.py', 1)
        self.assertEqual(r['age'], 'unknown')
        self.assertIn('came in through a merge (merged)', r['reason'])

    def test_the_cli_prints_the_age_commit_and_reason(self):
        p = subprocess.run([sys.executable, '-B', age.__file__, self.r.wt, self.base, 'f.py', '5', '--fix-start',
                            self.start], capture_output=True, text=True, stdin=subprocess.DEVNULL)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(p.stdout.startswith(f'New {self.build} build commit '), p.stdout)


class RecordAgeTest(unittest.TestCase):
    """findings.py keeps blame's proposal next to the reviewer's age and flags a disagreement."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.r = Repo(os.path.join(tmp.name, 'wt'))
        self.base = self.r.commit('f.py', 'a\n', 'base')
        self.r.commit('f.py', 'a\nb\n', 'build')
        self.run = Run(os.path.join(tmp.name, 'run-a'))
        with open(os.path.join(self.run.dir, 'queue.json'), 'w') as f:
            json.dump({'items': [{'id': 'job', 'worktree': self.r.wt,
                                  'pipeline': [{'name': 'build', 'head': self.base}]}]}, f)
        with open(os.path.join(self.run.dir, 'job-review.filled.md'), 'w') as f:
            f.write('... `phaseShouldHaveCaught` ...\n')

    def result(self, n, grade='Major', line=2, **why):
        props = {'n': n, 'grade': grade, 'area': 'COR', 'likelihood': 'L1', 'impact': 'I2', 'class': 'k', **why}
        return {'ruleId': 'EDGE', 'level': 'error' if grade != 'Minor' else 'warning', 'message': {'text': f'finding {n}'},
                'locations': [{'physicalLocation': {'artifactLocation': {'uri': 'f.py'}, 'region': {'startLine': line}}}],
                'properties': props}

    def record(self, results):
        self.run.round('job', at=T0)
        self.run.round('job-review', at=T0 + 10, report='1 blocking\n\n```json\n' + json.dumps(results) + '\n```\n')
        res = findings.record(self.run.dir)
        return {r['properties']['n']: r['properties'] for r in res[0]}, res[3]

    def test_agree_disagree_and_missing(self):
        full = dict(phaseInjected='build', phaseShouldHaveCaught='test', qualifier='Missing', missing='a test',
                    evidence={'age': 'unknown'})
        by, notes = self.record([self.result('B1', age='New', **full), self.result('B2', age='Base', **full),
                                 self.result('B3')])
        self.assertEqual((by['1']['ageProposed'], by['1']['ageDisagrees']), ('New', False))
        self.assertEqual((by['2']['ageProposed'], by['2']['ageDisagrees']), ('New', True))
        self.assertEqual((by['3']['ageProposed'], by['3']['ageDisagrees']), ('New', None))
        self.assertEqual([n['why'] for n in notes if n['kind'] == 'age'],
                         [f"2: the reviewer says Base, git blame proposes New ({by['2']['ageProposedReason']})"])
        out = findings.write(self.run.dir)[0]
        self.assertIn('  age disagrees: job-review: 2: the reviewer says Base, git blame proposes New', out)

    def test_no_worktree_recorded_gives_unknown_with_the_reason(self):
        os.remove(os.path.join(self.run.dir, 'queue.json'))
        by, _ = self.record([self.result('B1', age='New')])
        self.assertEqual((by['1']['ageProposed'], by['1']['ageDisagrees']), ('unknown', None))
        self.assertIn('no worktree for job', by['1']['ageProposedReason'])


if __name__ == '__main__':
    unittest.main()
