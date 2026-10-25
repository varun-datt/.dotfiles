import contextlib, io, json, os, subprocess, sys, tempfile, unittest

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guard  # noqa: E402

REPOS = ("route-planner\thttps://dev.azure.com/larkspur-freight/Platform/_git/route-planner\n"
         "dock-scheduler\tgit@ssh.dev.azure.com:v3/larkspur-freight/Platform/dock-scheduler\n"
         "billing-gateway\thttps://github.com/larkspur-oss/billing-gateway.git\n")


class Guard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        with open(os.path.join(d, "patterns.json"), "w") as f:
            json.dump([["Larkspur Freight", "the employer"]], f)
        with open(os.path.join(d, "workspace.repos"), "w") as f:
            f.write(REPOS)
        self.config = os.path.join(d, "config.json")
        self.write_config(allow=["billing-gateway"])
        self.repo = os.path.join(d, "repo")
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        self.cwd = os.getcwd()
        os.chdir(self.repo)

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def write_config(self, allow=()):
        d = self.tmp.name
        with open(self.config, "w") as f:
            json.dump({"pattern_files": [os.path.join(d, "patterns.json")],
                       "name_files": [{"path": os.path.join(d, "workspace.repos"), "column": 1}],
                       "url_files": [{"path": os.path.join(d, "workspace.repos"), "column": 2}],
                       "allow": list(allow), "gitleaks": False}, f)

    def stage(self, name, text):
        with open(name, "w") as f:
            f.write(text)
        subprocess.run(["git", "add", name], check=True)

    def check(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = guard.main(["--staged", "--config", self.config])
        return code, err.getvalue()

    def test_a_clean_note_passes(self):
        self.stage("note.md", "Exponential backoff with jitter spreads retries out.\n")
        self.assertEqual(self.check(), (0, ""))

    def test_a_repository_name_is_blocked_and_never_echoed(self):
        self.stage("note.md", "line one\nThe Route-Planner service retries twice.\n")
        code, err = self.check()
        self.assertEqual(code, 1)
        self.assertIn("note.md:2 matches a repository name", err)
        self.assertNotIn("route-planner", err.lower())

    def test_an_organisation_url_is_blocked_from_https_and_ssh_remotes(self):
        self.assertEqual(guard.org_paths("git@ssh.dev.azure.com:v3/larkspur-freight/Platform/dock-scheduler"), {"dev.azure.com/larkspur-freight"})
        self.stage("links.md", "See https://dev.azure.com/larkspur-freight/_boards for the board.\n")
        code, err = self.check()
        self.assertEqual(code, 1)
        self.assertIn("organisation URL", err)

    def test_a_redaction_pattern_is_blocked_as_a_whole_word_only(self):
        self.stage("a.md", "Notes from Larkspur Freight's planning day.\n")
        self.assertEqual(self.check()[0], 1)
        subprocess.run(["git", "rm", "-q", "--cached", "a.md"], check=True)
        self.stage("b.md", "Larkspur Freighters bloom in spring.\n")
        self.assertEqual(self.check()[0], 0)

    def test_the_allow_list_releases_a_false_positive(self):
        self.stage("note.md", "A billing-gateway is a common pattern.\n")
        self.assertEqual(self.check()[0], 0)
        self.write_config()
        self.assertEqual(self.check()[0], 1)

    def test_a_file_named_after_a_repository_is_blocked(self):
        self.stage("dock-scheduler.md", "nothing else here\n")
        self.assertEqual(self.check()[0], 1)

    def test_missing_block_lists_refuse_the_commit(self):
        self.stage("note.md", "fine\n")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(guard.main(["--staged", "--config", os.path.join(self.tmp.name, "absent.json")]), 2)


if __name__ == "__main__":
    unittest.main()
