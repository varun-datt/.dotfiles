import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from merge_check import findings, main  # noqa: E402


class MergeCheckTest(unittest.TestCase):
    def test_patterns_match_on_word_boundaries_only(self):
        self.assertEqual(['pattern#0=1'], findings('see acme here, not acmerock', ['acme']))

    def test_literal_escapes_are_found(self):
        self.assertEqual(['escapes=1'], findings('a \\u2014 dash', []))

    def test_pairs_and_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'p.json').write_text(json.dumps([['acme', 'ORG']]))
            (root / 'clean.md').write_text('nothing here')
            (root / 'dirty.md').write_text('acme')
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(0, main(['--patterns', str(root / 'p.json'), str(root / 'clean.md')]))
                self.assertEqual(1, main(['--patterns', str(root / 'p.json'), str(root / 'dirty.md')]))
            self.assertNotIn('acme', out.getvalue().replace(str(root), ''))


if __name__ == '__main__':
    unittest.main()
