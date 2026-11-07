import os, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))


class AgeProgramTest(unittest.TestCase):
    """Runs age.py as a program, so this module loads, and its test fails on an assertion, where age.py is missing."""

    def test_a_line_a_build_commit_only_added_is_new(self):
        with tempfile.TemporaryDirectory() as tmp:
            wt = os.path.join(tmp, 'wt')

            def git(*args):
                return subprocess.run(['git', '-C', wt, '-c', 'core.hooksPath=/dev/null', '-c', 'user.name=t', '-c',
                                       'user.email=t@example.invalid', *args], check=True, capture_output=True,
                                      text=True, stdin=subprocess.DEVNULL).stdout.strip()
            subprocess.run(['git', 'init', '-q', '-b', 'ow/a', wt], check=True, stdin=subprocess.DEVNULL)
            with open(os.path.join(wt, 'f.py'), 'w') as f:
                f.write('a = 1\n')
            git('add', 'f.py')
            git('commit', '-qm', 'base')
            base = git('rev-parse', 'HEAD')
            with open(os.path.join(wt, 'f.py'), 'a') as f:
                f.write('b = 2\n')
            git('commit', '-qam', 'build')
            build = git('rev-parse', 'HEAD')
            p = subprocess.run([sys.executable, '-B', os.path.join(HERE, 'age.py'), wt, base, 'f.py', '2'],
                               capture_output=True, text=True, cwd=tmp, stdin=subprocess.DEVNULL)
            self.assertEqual(p.stdout.split()[:2], ['New', build], p.stderr)
            self.assertEqual(p.returncode, 0, p.stderr)


if __name__ == '__main__':
    unittest.main()
