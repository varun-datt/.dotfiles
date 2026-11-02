import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from resume import last_launch, resume_argv  # noqa: E402

LAUNCH = ['copilot', '-C', '/w', '-n', 'ow-x', '--model', 'm', '-p']


class ResumeTest(unittest.TestCase):
    def test_new_session_becomes_resume_and_gains_a_cap(self):
        argv = resume_argv(LAUNCH, 'x', 300, 'go on')
        self.assertEqual(['copilot', '-C', '/w', '-r', 'ow-x', '--model', 'm',
                          '--max-ai-credits', '300', '-p', 'go on'], argv)

    def test_an_existing_cap_is_replaced(self):
        argv = resume_argv(LAUNCH[:-1] + ['--max-ai-credits', '1200', '-p'], 'x', 250, 'p')
        self.assertEqual('250', argv[argv.index('--max-ai-credits') + 1])
        self.assertEqual(1, argv.count('--max-ai-credits'))

    def test_the_item_s_last_launch_is_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            routes = pathlib.Path(tmp) / 'routes.jsonl'
            rows = [{'event': 'launch', 'round': 'x', 'argv': ['a']},
                    {'event': 'pick', 'round': 'x'},
                    {'event': 'launch', 'round': 'y', 'argv': ['b']},
                    {'event': 'launch', 'round': 'x', 'argv': ['c']}]
            routes.write_text('\n'.join(json.dumps(r) for r in rows) + '\n')
            self.assertEqual(['c'], last_launch(routes, 'x')['argv'])


if __name__ == '__main__':
    unittest.main()
