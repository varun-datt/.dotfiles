import csv, io, os, subprocess, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agreement  # noqa: E402
from test_findings import REVIEW, BRIEF, write  # noqa: E402
from test_mine import Run, T0  # noqa: E402

HEAD = ['run', 'round', 'round_kind', 'n', 'block_reviewer', 'ruling', 'ruling_source']


class AgreementTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name
        self.run = Run(os.path.join(tmp.name, 'run-g'))
        self.run.round('job', at=T0)
        self.run.round('job-review', at=T0 + 1000, report=REVIEW)
        self.run.round('job-fix1', at=T0 + 2000)
        write(self.run, 'job-fix1.prompt.md', BRIEF)

    def rows(self, *rows):
        return [dict(zip(HEAD, r)) for r in rows]

    def test_only_in_run_rulings_of_blocking_rows_are_compared_and_the_rest_listed_apart(self):
        rows = self.rows(('run-g', 'job-review', 'review', '1', 'yes', 'accepted', 'fix-brief'),
                         ('run-g', 'job-review', 'review', '3', 'yes', 'accepted', 'fix-brief'),
                         ('run-g', 'job-review', 'review', '9', 'yes', 'accepted', 'rulings.jsonl'),
                         ('run-g', 'job-review', 'review', '2', 'yes', 'rejected', 'plan'),
                         ('run-g', 'job-review', 'review', '5', 'yes', 'accepted', 'prior-csv'),
                         ('run-g', 'job-review', 'review', '4', 'no', 'rejected', 'fix-brief'),
                         ('other', 'job-review', 'review', '1', 'yes', 'rejected', 'fix-brief'))
        s = agreement.compare(rows, [self.run.dir])['run-g']
        self.assertEqual((s['compared'], s['agree'], s['missing']), (3, 1, [('job-review', '9')]))
        self.assertEqual(s['differ'], [(('job-review', '3'), 'accepted', 'rejected')])
        self.assertEqual(dict(s['apart']), {'plan': 1, 'prior-csv': 1})

    def test_cli_prints_the_share_against_the_bar_per_run_folder(self):
        path = os.path.join(self.tmp, 'f.csv')
        with open(path, 'w', encoding='utf-8', newline='') as f:
            w = csv.writer(f)
            w.writerow(HEAD)
            w.writerow(('run-g', 'job-review', 'review', '1', 'yes', 'accepted', 'fix-brief'))
            w.writerow(('run-g', 'job-review', 'review', '3', 'yes', 'rejected', 'fix-brief'))
        p = subprocess.run([sys.executable, '-B', agreement.__file__, path, self.run.dir], capture_output=True, text=True,
                           stdin=subprocess.DEVNULL, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('run-g: 2/2 agree (100.0%), 0 not in the record, 0 ruled differently; meets 90%; apart: none',
                      p.stdout)
        p = subprocess.run([sys.executable, '-B', agreement.__file__, '--help'], capture_output=True, text=True,
                           stdin=subprocess.DEVNULL, timeout=60)
        self.assertEqual(p.returncode, 0)


if __name__ == '__main__':
    unittest.main()
