import os, subprocess, sys, tempfile, unittest
from unittest import mock

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_install_names as cin  # noqa: E402


class InstallNames(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        home = os.path.join(d, "home")
        os.makedirs(home)
        env = mock.patch.dict(os.environ, {"HOME": home, "XDG_CONFIG_HOME": os.path.join(d, "config")})
        env.start()
        self.addCleanup(env.stop)
        self.repo = os.path.join(d, "repo")
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        self.write(".chezmoiroot", "dotfiles\n")
        self.write("dotfiles/.chezmoiignore", ".x/skipped.py\n")
        self.git("add", ".")
        self.git("-c", "core.hooksPath=/dev/null", "-c", "user.email=t@t", "-c", "user.name=t",
                 "commit", "-q", "-m", "base")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text="x\n"):
        path = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)

    def git(self, *args):
        subprocess.run(["git", "-C", self.repo, *args], check=True, capture_output=True)

    def stage(self, *rels):
        for r in rels:
            self.write(r)
        self.git("add", *rels)
        return cin.check(self.repo)

    def test_own_names_pass_silently(self):
        self.assertEqual(self.stage("dotfiles/private_Library/private_Application Support/dot_tool.py",
                                    "dotfiles/dot_x/executable_run.sh", "dotfiles/dot_x/foo.py.tmpl",
                                    "dotfiles/dot_x/literal_remove_me.py", "dotfiles/dot_x/empty_keep"), ([], []))

    def test_action_prefix_blocks_with_the_fix(self):
        blocks, _ = self.stage("dotfiles/dot_x/remove_merged.py")
        self.assertEqual(len(blocks), 1)
        self.assertIn("dotfiles/dot_x/remove_merged.py", blocks[0])
        self.assertIn("deletes the target", blocks[0])
        self.assertIn("literal_remove_merged.py", blocks[0])

    def test_each_action_prefix_blocks(self):
        rels = [f"dotfiles/dot_x/{p}{p.strip('_')}.py" for p in ("run_", "create_", "modify_", "symlink_")]
        blocks, _ = self.stage(*rels)
        self.assertEqual(len(blocks), len(rels))

    def test_an_action_word_after_a_keeping_prefix_is_part_of_the_name(self):
        self.assertEqual(self.stage("dotfiles/dot_x/private_remove_me.py"), ([], []))

    def test_the_suggested_literal_rename_passes(self):
        self.assertEqual(self.stage("dotfiles/dot_x/literal_symlink_notes.md.tmpl"), ([], []))

    def test_scripts_folder_passes(self):
        self.assertEqual(self.stage("dotfiles/.chezmoiscripts/run_onchange_after_x.sh.tmpl"), ([], []))

    def test_allow_list_passes(self):
        self.write(cin.ALLOW, "# deliberate\ndotfiles/dot_config/create_config.yaml\n")
        self.assertEqual(self.stage("dotfiles/dot_config/create_config.yaml"), ([], []))

    def test_ignored_file_passes_with_a_note(self):
        blocks, notes = self.stage("dotfiles/dot_x/skipped.py")
        self.assertEqual(blocks, [])
        self.assertEqual(len(notes), 1)
        self.assertIn("will not install", notes[0])

    def test_changed_renamed_and_outside_files_are_not_checked(self):
        self.write("dotfiles/dot_x/remove_old.py")
        self.write("dotfiles/dot_x/remove_moved.py")
        self.git("add", ".")
        self.git("-c", "core.hooksPath=/dev/null", "-c", "user.email=t@t", "-c", "user.name=t",
                 "commit", "-q", "-m", "old")
        self.write("dotfiles/dot_x/remove_old.py", "changed\n")
        self.git("mv", "dotfiles/dot_x/remove_moved.py", "dotfiles/dot_x/remove_renamed.py")
        self.assertEqual(self.stage("dotfiles/dot_x/remove_old.py", "scripts/remove_tool.py"), ([], []))

    def test_breaking_the_name_comparison_fails_the_block_test(self):
        with mock.patch.object(cin, "same_name", lambda a, b: True):
            blocks, _ = self.stage("dotfiles/dot_x/remove_merged.py")
        self.assertEqual(blocks, [], "the block test would pass with the comparison broken")

    def test_hook_exit_code(self):
        self.stage("dotfiles/dot_x/remove_merged.py")
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "check_install_names.py")
        r = subprocess.run([sys.executable, "-B", script], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("remove_merged.py", r.stderr)

    def test_a_source_chezmoi_refuses_blocks_with_its_error(self):
        for r in ("dotfiles/dot_x/run_same.py", "dotfiles/dot_x/create_same.py"):
            self.write(r)
        self.git("add", ".")
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "check_install_names.py")
        r = subprocess.run([sys.executable, "-B", script], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("chezmoi --source", r.stderr)
        self.assertNotIn("Traceback", r.stderr)


if __name__ == "__main__":
    unittest.main()
