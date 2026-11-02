import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
SCRIPTS = pathlib.Path(__file__).resolve().parent

from resume import last_launch, resume_argv  # noqa: E402

LAUNCH = ['copilot', '-C', '/w', '-n', 'ow-x', '--model', 'm', '-p']


class ResumeTest(unittest.TestCase):
    def test_new_session_becomes_resume_with_no_visible_cap(self):
        argv = resume_argv(LAUNCH, 'x', 'go on')
        self.assertEqual(['copilot', '-C', '/w', '-r', 'ow-x', '--model', 'm', '-p', 'go on'], argv)

    def test_an_old_launch_s_visible_cap_is_removed(self):
        argv = resume_argv(LAUNCH[:-1] + ['--max-ai-credits', '1200', '-p'], 'x', 'p')
        self.assertNotIn('--max-ai-credits', argv)
        self.assertNotIn('1200', argv)
        self.assertEqual(['-p', 'p'], argv[-2:])

    def test_the_item_s_last_launch_is_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            routes = pathlib.Path(tmp) / 'routes.jsonl'
            rows = [{'event': 'launch', 'round': 'x', 'argv': ['a']},
                    {'event': 'pick', 'round': 'x'},
                    {'event': 'launch', 'round': 'y', 'argv': ['b']},
                    {'event': 'launch', 'round': 'x', 'argv': ['c']}]
            routes.write_text('\n'.join(json.dumps(r) for r in rows) + '\n')
            self.assertEqual(['c'], last_launch(routes, 'x')['argv'])


UNDER_CAFFEINATE = ['bash', '-c', 'exec -a caffeinate /bin/bash -c "\\"\\$@\\"; exit \\$?" inner "$@"', 'outer']


class CaffeinateTest(unittest.TestCase):
    def resume(self, argv, under=()):
        with tempfile.TemporaryDirectory() as tmp:
            run = pathlib.Path(tmp)
            (run / 'routes.jsonl').write_text(json.dumps({'event': 'launch', 'round': 'x', 'argv': argv}) + '\n')
            (run / 'x-r1.prompt.md').write_text('go on; caffeinate was killed last time\n')
            env = {**os.environ, 'OW_RUN_DIR': tmp, 'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1'}
            p = subprocess.run([*under, sys.executable, '-B', str(SCRIPTS / 'resume.py'), 'x', 'x-r1', 'none', '5'],
                               capture_output=True, text=True, env=env, timeout=60, stdin=subprocess.DEVNULL)
            return p, (run / 'x-r1.start').exists()

    def test_a_launch_argv_that_runs_caffeinate_is_refused_before_anything_starts(self):
        p, started = self.resume(['caffeinate', '-i'] + LAUNCH)
        self.assertEqual(p.returncode, 2, p.stderr)
        self.assertIn('resume.py: refused: this command runs caffeinate', p.stderr)
        self.assertFalse(started)

    def test_resume_started_by_a_caffeinate_process_is_refused(self):
        p, started = self.resume(LAUNCH, under=UNDER_CAFFEINATE)
        self.assertEqual(p.returncode, 2, p.stderr)
        self.assertIn('resume.py: refused: this launcher runs under caffeinate (pid ', p.stderr)
        self.assertFalse(started)

    def test_a_plain_launch_is_not_refused(self):
        p, started = self.resume(LAUNCH)
        self.assertNotIn('caffeinate', p.stderr)
        self.assertTrue(started)


if __name__ == '__main__':
    unittest.main()
