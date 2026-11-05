import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))
import state  # noqa: E402

CURRENT = "---\nschema: agent-state/v2\nworkspace: /w\nupdated: 2026-11-05\n---\n\n# Current state\n\n## Waiting on the owner\n\n- [ ] Decide X ([Topic](#topic))\n\n## Topic\n\n- Status: works; settled on 2026-11-01 for the reason Y.\n"


def run(argv, stdin=""):
    err = io.StringIO()
    old = sys.stdin
    sys.stdin = io.StringIO(stdin)
    try:
        with redirect_stderr(err):
            rc = state.main(argv)
    finally:
        sys.stdin = old
    return rc, err.getvalue()


class StateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.file = self.dir / "state.md"
        self.file.write_text(CURRENT)

    def tearDown(self):
        self.tmp.cleanup()

    def test_current_file_passes(self):
        self.assertEqual(run(["check", str(self.file)]), (0, ""))

    def test_over_limit_warns(self):
        self.file.write_text(CURRENT + "- Status: x\n" * 3000)
        rc, err = run(["check", str(self.file)])
        self.assertEqual(rc, 1)
        self.assertIn("over the 25 KB limit", err)

    def test_old_template_warns(self):
        self.file.write_text(CURRENT.replace("agent-state/v2", "agent-state/v1"))
        rc, err = run(["check", str(self.file)])
        self.assertEqual(rc, 1)
        self.assertIn("not on the current template", err)

    def test_dated_diary_lines_warn(self):
        diary = "## 2026-10-09 — onboarding\n- 2026-10-06: did a thing\n- **2026-10-07** did another\n- [x] 2026-10-08 done\n"
        self.file.write_text(CURRENT + diary)
        rc, err = run(["check", str(self.file)])
        self.assertEqual(rc, 1)
        self.assertIn("4 dated diary lines (lines 16, 17, 18, 19)", err)

    def test_date_inside_a_line_is_not_diary(self):
        rc, err = run(["check", str(self.file)])
        self.assertNotIn("dated diary", err)

    def test_open_item_dated_for_the_dashboard_is_not_diary(self):
        self.file.write_text(CURRENT + "- [ ] 2026-11-20 renew the token\n")
        self.assertEqual(run(["check", str(self.file)]), (0, ""))

    def test_missing_file(self):
        rc, err = run(["check", str(self.dir / "nope.md")])
        self.assertEqual(rc, 1)
        self.assertIn("missing", err)

    def test_write_with_current_token_replaces(self):
        t = state.token(self.file)
        new = CURRENT.replace("Decide X", "Decide Z")
        self.assertEqual(run(["write", str(self.file), "--expect", t], new), (0, ""))
        self.assertEqual(self.file.read_text(), new)

    def test_write_refused_when_changed_since_read(self):
        t = state.token(self.file)
        self.file.write_text(CURRENT + "- Status: another session\n")
        rc, err = run(["write", str(self.file), "--expect", t], CURRENT)
        self.assertEqual(rc, 3)
        self.assertIn("changed since it was read", err)
        self.assertIn("another session", self.file.read_text())

    def test_write_refuses_empty_content(self):
        t = state.token(self.file)
        rc, err = run(["write", str(self.file), "--expect", t], "  \n")
        self.assertEqual(rc, 2)
        self.assertEqual(self.file.read_text(), CURRENT)

    def test_write_through_symlink_keeps_the_link(self):
        real = self.dir / "repo" / "state.md"
        real.parent.mkdir()
        real.write_text(CURRENT)
        link = self.dir / "link.md"
        link.symlink_to(real)
        new = CURRENT.replace("Decide X", "Decide Z")
        rc, _ = run(["write", str(link), "--expect", state.token(link)], new)
        self.assertEqual(rc, 0)
        self.assertTrue(link.is_symlink())
        self.assertEqual(real.read_text(), new)

    def test_write_keeps_mode_and_leaves_no_temp_file(self):
        os.chmod(self.file, 0o600)
        run(["write", str(self.file), "--expect", state.token(self.file)], CURRENT + "\n")
        self.assertEqual(self.file.stat().st_mode & 0o777, 0o600)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["state.md"])

    def test_write_reports_findings_after_writing(self):
        rc, err = run(["write", str(self.file), "--expect", state.token(self.file)], CURRENT + "- 2026-10-06 diary\n")
        self.assertEqual(rc, 0)
        self.assertIn("dated diary", err)

    def test_hash_prints_token(self):
        out = io.StringIO()
        old = sys.stdout
        sys.stdout = out
        try:
            state.main(["hash", str(self.file)])
        finally:
            sys.stdout = old
        self.assertEqual(out.getvalue().strip(), state.token(self.file))

    def git_root(self):
        root = Path(os.path.realpath(self.dir)) / "state"
        (root / "ws").mkdir(parents=True)
        git = ["git", "-C", str(root)]
        subprocess.run(git + ["init", "-q"], check=True)
        for key, value in (("user.name", "t"), ("user.email", "t@t"), ("commit.gpgsign", "false")):
            subprocess.run(git + ["config", key, value], check=True)
        f = root / "ws" / "state.md"
        f.write_text(CURRENT)
        return root, f

    def subjects(self, root):
        out = subprocess.run(["git", "-C", str(root), "log", "--format=%s"], capture_output=True, text=True).stdout
        return out.split()

    def test_write_commits_each_change_inside_a_git_state_root(self):
        root, f = self.git_root()
        new = CURRENT.replace("Decide X", "Decide Z")
        with mock.patch.object(state, "STATE_ROOT", root):
            self.assertEqual(run(["write", str(f), "--expect", state.token(f)], new), (0, ""))
            self.assertEqual(run(["write", str(f), "--expect", state.token(f)], new), (0, ""))
        self.assertEqual(self.subjects(root), ["state:", "ws"])

    def test_write_commits_only_the_state_file(self):
        root, f = self.git_root()
        other = root / "ws" / "notes.md"
        other.write_text("x")
        subprocess.run(["git", "-C", str(root), "add", "ws/notes.md"], check=True)
        with mock.patch.object(state, "STATE_ROOT", root):
            run(["write", str(f), "--expect", state.token(f)], CURRENT + "\n")
        files = subprocess.run(["git", "-C", str(root), "show", "--name-only", "--format="], capture_output=True, text=True).stdout.split()
        self.assertEqual(files, ["ws/state.md"])

    def test_write_outside_the_state_root_makes_no_commit(self):
        root, _ = self.git_root()
        with mock.patch.object(state, "STATE_ROOT", root):
            self.assertEqual(run(["write", str(self.file), "--expect", state.token(self.file)], CURRENT + "\n"), (0, ""))
        self.assertEqual(self.subjects(root), [])


if __name__ == "__main__":
    unittest.main()
