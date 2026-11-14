import importlib.util
import os
import unittest

spec = importlib.util.spec_from_file_location("gated_steps", os.path.join(os.path.dirname(__file__), "gated-steps.py"))
gated = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gated)

HOME = os.path.expanduser("~")


def refused(command, cwd=None):
    event = {"toolName": "run_in_terminal", "toolArgs": {"command": command}}
    if cwd:
        event["cwd"] = cwd
    return gated.decide(event).get("permissionDecision") == "deny"


class PathlessDotfilesCommitTest(unittest.TestCase):
    def test_refuses_a_dotfiles_commit_that_lists_no_files(self):
        self.assertTrue(refused("cd ~/.local/share/chezmoi && git commit -m 'x'"))
        self.assertTrue(refused("/usr/bin/git -C ~/.local/share/chezmoi commit -am x"))
        self.assertTrue(refused("git commit -m x --", cwd=os.path.join(HOME, ".local/share/chezmoi/dotfiles")))
        self.assertTrue(refused("cd $HOME/.local/share/chezmoi && git commit --amend --no-edit"))

    def test_lets_a_dotfiles_commit_that_lists_its_files_through(self):
        self.assertFalse(refused("cd ~/.local/share/chezmoi && /usr/bin/git commit -m x -- dotfiles/a.py"))
        self.assertFalse(refused("git -C ~/.local/share/chezmoi commit -m x -- a b"))

    def test_lets_a_pathless_commit_elsewhere_through(self):
        self.assertFalse(refused("cd ~/worktrees/amc/features && git commit -m x"))
        self.assertFalse(refused("git commit -m x", cwd="/tmp"))
        self.assertFalse(refused("git commit -m x"))
        self.assertFalse(refused("cd ~/.local/share/chezmoi && cd /tmp && git commit -m x"))


if __name__ == "__main__":
    unittest.main()
