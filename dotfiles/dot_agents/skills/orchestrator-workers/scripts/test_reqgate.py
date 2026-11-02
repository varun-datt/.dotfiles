import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import reqgate  # noqa: E402
from reqgate import main, parse_map  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures", "reqgate")
VITEST = f"{sys.executable} -B {os.path.join(FIXTURES, 'fake_vitest.py')}"
STRYKER = f"{sys.executable} -B {os.path.join(FIXTURES, 'fake_stryker.py')}"

BRIEF = """You are a worker session for a made-up project.

TASK: example

MUST (each is checked by the reviewer)
{musts}

ACCEPTANCE
- tests
"""

CALC_BASE = "def add(a, b):\n    return a + b\n\n\ndef clamp(x):\n    return x\n"
CALC_HEAD = CALC_BASE.replace("return x\n", "return max(0, x)\n") + "\n\ndef double(x):\n    return 2 * x\n"
TEST_BASE = """import unittest
import calc


class CalcTest(unittest.TestCase):
    def test_add(self):
        self.assertEqual(3, calc.add(1, 2))
"""
TEST_HEAD = TEST_BASE + """
    def test_clamp_negative(self):
        self.assertEqual(0, calc.clamp(-1))

    def test_clamp_positive(self):
        self.assertEqual(2, calc.clamp(2))

    def test_double(self):
        self.assertEqual(4, calc.double(2))


class OtherTest(unittest.TestCase):
    def test_add(self):
        self.assertEqual(2, calc.add(1, 1))

    def test_broken(self):
        self.assertEqual(5, calc.add(1, 1))
"""
FMT_TEST = """import unittest
import fmt


class FmtTest(unittest.TestCase):
    def test_label(self):
        self.assertEqual("#1", fmt.label(1))
"""
SLOW_TEST = """import time
import unittest
import calc


class SlowTest(unittest.TestCase):
    def test_waits(self):
        if not hasattr(calc, "double"):
            time.sleep(60)
        self.assertEqual(2, calc.double(1))
"""
TS_BASE = "// calc\nexport const add = (a: number, b: number) =>\n  a + b;\nexport const zero = 0;\n"
TS_HEAD = TS_BASE.replace("  a + b;", "  a + b + zero;")


def git(repo, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-C", repo, *args],
                          check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout


def make_repo(root, base, head):
    """A repo whose main is `base` and whose branch ow/x adds `head` on top; returns (repo, base sha)."""
    repo = os.path.join(root, "repo")
    subprocess.run(["git", "init", "-q", "-b", "main", repo], check=True)
    for files in (base, head):
        for path, text in files.items():
            full = os.path.join(repo, path)
            if text is None:
                os.remove(full)
                continue
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(text)
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "step")
        if files is base:
            sha = git(repo, "rev-parse", "HEAD").strip()
            git(repo, "checkout", "-q", "-b", "ow/x")
    git(repo, "checkout", "-q", "main")
    return repo, sha


class GateCase(unittest.TestCase):
    base_files, head_files = {}, {}

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = cls._tmp.name
        cls.repo, cls.base = make_repo(cls.root, cls.base_files, cls.head_files)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def setUp(self):
        self.scratch = tempfile.mkdtemp(prefix="scratch-", dir=self.root)
        self.saved_tempdir, tempfile.tempdir = tempfile.tempdir, self.scratch
        self.log = os.path.join(self.root, "fake.log")
        os.environ["REQGATE_FAKE_LOG"] = self.log
        self.addCleanup(os.environ.pop, "REQGATE_FAKE_LOG", None)
        with contextlib.suppress(FileNotFoundError):
            os.remove(self.log)

    def tearDown(self):
        tempfile.tempdir = self.saved_tempdir

    def gate(self, musts, map_lines, *extra, code=None):
        brief = os.path.join(self.root, "brief.md")
        report = os.path.join(self.root, "report.md")
        out = os.path.join(self.root, "out.json")
        with contextlib.suppress(FileNotFoundError):
            os.remove(out)
        with open(brief, "w", encoding="utf-8") as f:
            f.write(BRIEF.format(musts="\n".join(f"{i}. WHEN a thing happens, the part SHALL do {i}." for i in musts)))
        with open(report, "w", encoding="utf-8") as f:
            f.write("9. REQUIREMENTS MAP\n" + "\n".join(map_lines) + "\n")
        args = ["check", "--repo", self.repo, "--base", self.base, "--head", "ow/x", "--brief", brief,
                "--report", report, "--json", out, "--vitest-cmd", VITEST, "--stryker-cmd", STRYKER, "--timeout", "20", *extra]
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            got = main(args)
        if code is not None:
            self.assertEqual(code, got, printed.getvalue())
        with open(out, encoding="utf-8") as f:
            result = json.load(f)
        result["printed"], result["code"] = printed.getvalue(), got
        self.assertEqual([], os.listdir(self.scratch), "temporary worktrees left behind")
        self.assertEqual(1, git(self.repo, "worktree", "list").count("\n"), "worktree not removed")
        self.assertEqual("", git(self.repo, "status", "--porcelain"), "the repository's checkout was touched")
        return result

    def row(self, result, kind, test):
        return next(r for r in result[kind] if r["test"] == test)

    def logged(self, prog):
        with open(self.log, encoding="utf-8") as f:
            return [x.split(" ", 1)[1].split("\x1f") for x in f.read().splitlines() if x.startswith(prog + " ")]


class PythonGateTest(GateCase):
    base_files = {"pkg/calc.py": CALC_BASE, "pkg/test_calc.py": TEST_BASE, "README.md": "x\n"}
    head_files = {"pkg/calc.py": CALC_HEAD, "pkg/test_calc.py": TEST_HEAD, "pkg/fmt.py": "def label(x):\n    return f'#{x}'\n",
                  "pkg/test_fmt.py": FMT_TEST, "pkg/test_slow.py": SLOW_TEST}

    def test_correct_branch_passes(self):
        r = self.gate([1, 2], ["- MUST 1: pkg/test_calc.py::CalcTest.test_clamp_negative [FAIL_TO_PASS]",
                               "- MUST 2: pkg/test_calc.py::CalcTest.test_add [PASS_TO_PASS]"], code=0)
        self.assertEqual("pass", self.row(r, "FAIL_TO_PASS", "pkg/test_calc.py::CalcTest.test_clamp_negative")["status"])
        p2p = self.row(r, "PASS_TO_PASS", "pkg/test_calc.py::CalcTest.test_add")
        self.assertEqual(("not checked", "not checked: no mutant runner"), (p2p["status"], p2p["reason"]))
        self.assertEqual({"passed", "musts", "problems", "none", "FAIL_TO_PASS", "PASS_TO_PASS", "mutants_run", "minutes"},
                         set(r) - {"printed", "code"})
        self.assertIn("PASS: 2 MUSTs", r["printed"])

    def test_new_test_that_passes_on_base_fails_the_gate(self):
        r = self.gate([1], ["- MUST 1: pkg/test_calc.py::CalcTest.test_clamp_positive [FAIL_TO_PASS]"], code=1)
        row = self.row(r, "FAIL_TO_PASS", "pkg/test_calc.py::CalcTest.test_clamp_positive")
        self.assertEqual("fail", row["status"])
        self.assertIn("passes on base", row["reason"])

    def test_new_test_that_fails_on_base_only_by_import_fails_the_gate(self):
        r = self.gate([1], ["- MUST 1: pkg/test_fmt.py::FmtTest.test_label [FAIL_TO_PASS]"], code=1)
        row = self.row(r, "FAIL_TO_PASS", "pkg/test_fmt.py::FmtTest.test_label")
        self.assertEqual("fail", row["status"])
        self.assertTrue(row["reason"].startswith("load on base"), row["reason"])

    def test_new_test_that_raises_a_non_assertion_on_base_fails_the_gate(self):
        r = self.gate([1], ["- MUST 1: pkg/test_calc.py::CalcTest.test_double [FAIL_TO_PASS]"], code=1)
        self.assertTrue(self.row(r, "FAIL_TO_PASS", "pkg/test_calc.py::CalcTest.test_double")["reason"].startswith("error on base"))

    def test_timeout_on_base_fails_the_gate_and_cleans_up(self):
        r = self.gate([1], ["- MUST 1: pkg/test_slow.py::SlowTest.test_waits [FAIL_TO_PASS]"], "--timeout", "3", code=1)
        self.assertTrue(self.row(r, "FAIL_TO_PASS", "pkg/test_slow.py::SlowTest.test_waits")["reason"].startswith("timeout on base"))

    def test_unmapped_must_fails_the_gate(self):
        r = self.gate([1, 2], ["- MUST 1: pkg/test_calc.py::CalcTest.test_clamp_negative [FAIL_TO_PASS]"], code=1)
        self.assertEqual(["MUST 2 has no line in the REQUIREMENTS MAP"], r["problems"])

    def test_map_line_with_no_test_fails_the_gate(self):
        r = self.gate([1], ["- MUST 1: pkg/test_calc.py [FAIL_TO_PASS]"], code=1)
        self.assertEqual(2, len(r["problems"]))
        self.assertIn("cannot read map line for MUST 1", r["problems"][0])

    def test_missing_test_file_or_name_fails_the_gate(self):
        r = self.gate([1, 2], ["- MUST 1: pkg/test_gone.py::GoneTest.test_x [FAIL_TO_PASS]",
                               "- MUST 2: pkg/test_calc.py::CalcTest.test_nope [PASS_TO_PASS]"], code=1)
        self.assertTrue(self.row(r, "FAIL_TO_PASS", "pkg/test_gone.py::GoneTest.test_x")["reason"].startswith("missing at head"))
        self.assertTrue(self.row(r, "PASS_TO_PASS", "pkg/test_calc.py::CalcTest.test_nope")["reason"].startswith("missing at head"))

    def test_test_failing_at_head_fails_the_gate(self):
        r = self.gate([1], ["- MUST 1: pkg/test_calc.py::OtherTest.test_broken [FAIL_TO_PASS]"], "--runner", "unittest", code=1)
        reason = r["FAIL_TO_PASS"][0]["reason"]
        self.assertTrue(reason.startswith("failed at head") and "AssertionError: 5 != 2" in reason, reason)

    def test_ambiguous_method_name_fails_the_gate(self):
        r = self.gate([1], ["- MUST 1: pkg/test_calc.py::test_add [PASS_TO_PASS]"], code=1)
        self.assertTrue(self.row(r, "PASS_TO_PASS", "pkg/test_calc.py::test_add")["reason"].startswith("ambiguous at head"))

    def test_none_line_is_counted_not_failed(self):
        r = self.gate([1, 2], ["- MUST 1: pkg/test_calc.py::CalcTest.test_clamp_negative [FAIL_TO_PASS]",
                               "- MUST 2: none (a prompt change, read by the reviewer)"], code=0)
        self.assertEqual([{"must": "2", "why": "a prompt change, read by the reviewer"}], r["none"])
        self.assertIn("1 none (the owner decides whether none should fail)", r["printed"])

    def test_must_mapped_twice_checks_both_lines(self):
        r = self.gate([1], ["- MUST 1: pkg/test_calc.py::CalcTest.test_clamp_negative [FAIL_TO_PASS]",
                            "- MUST 1: pkg/test_calc.py::CalcTest.test_clamp_positive [FAIL_TO_PASS]"], code=1)
        self.assertEqual(["pass", "fail"], [x["status"] for x in r["FAIL_TO_PASS"]])

    def test_line_naming_a_must_the_brief_lacks_fails(self):
        r = self.gate([1], ["- MUST 1: pkg/test_calc.py::CalcTest.test_clamp_negative [FAIL_TO_PASS]",
                            "- MUST 7: pkg/test_calc.py::CalcTest.test_add [PASS_TO_PASS]"], code=1)
        self.assertIn("MUST 7 is not in the brief", r["problems"][0])
        self.assertEqual([], r["PASS_TO_PASS"])

    def test_report_with_no_map_fails(self):
        r = self.gate([1], ["nothing here"], code=1)
        self.assertIn("no REQUIREMENTS MAP", r["problems"][0])

    def test_warn_reports_the_same_and_exits_zero(self):
        r = self.gate([1], ["- MUST 1: pkg/test_calc.py::CalcTest.test_clamp_positive [FAIL_TO_PASS]"], "--warn", code=0)
        self.assertFalse(r["passed"])
        self.assertIn("FAIL:", r["printed"])

    def test_usage_and_setup_errors_exit_two(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(2, main(["check", "--repo", self.repo]))
            self.assertEqual(2, main(["check", "--repo", self.repo, "--base", "no-such-ref", "--head", "ow/x",
                                      "--brief", os.devnull, "--report", os.devnull]))


class VitestGateTest(GateCase):
    base_files = {"src/calc.ts": TS_BASE, "src/calc.test.ts": "// calc tests\n", "FAKE_VITEST": "vitest-base.json\n",
                  "FAKE_STRYKER": "mutation.json\n", "stryker.config.json": "{}\n", "package.json": "{}\n"}
    head_files = {"src/calc.ts": TS_HEAD, "src/calc.test.ts": "// calc tests, more\n", "FAKE_VITEST": "vitest-head.json\n"}

    def test_vitest_assertion_on_base_passes_and_keeps_test_kills_a_mutant(self):
        r = self.gate([1, 2], ["- MUST 1: src/calc.test.ts::calc > adds [FAIL_TO_PASS]",
                               "- MUST 2: src/calc.test.ts::|unit| src/calc.test.ts > calc > adds [PASS_TO_PASS]"], code=0)
        p2p = r["PASS_TO_PASS"][0]
        self.assertEqual(("pass", {"covered": 2, "killed": 1, "survived": 1}), (p2p["status"], p2p["mutants"]))
        self.assertEqual(4, r["mutants_run"])
        stryker = self.logged("stryker")
        self.assertEqual(1, len(stryker))
        args = stryker[0]
        self.assertEqual("src/calc.ts:3-3", args[args.index("--mutate") + 1])
        self.assertIn("--disableBail", args)

    def test_keeps_test_that_survives_every_mutant_fails_the_gate(self):
        r = self.gate([1], ["- MUST 1: src/calc.test.ts::calc > keeps zero [PASS_TO_PASS]"], code=1)
        row = r["PASS_TO_PASS"][0]
        self.assertEqual(("fail", {"covered": 3, "killed": 0, "survived": 3}), (row["status"], row["mutants"]))
        self.assertIn("survived all 3", row["reason"])

    def test_keeps_test_covering_no_changed_line_is_reported(self):
        r = self.gate([1], ["- MUST 1: src/calc.test.ts::calc > formats [PASS_TO_PASS]"], code=0)
        self.assertEqual(("not checked", "covers no changed line"), (r["PASS_TO_PASS"][0]["status"], r["PASS_TO_PASS"][0]["reason"]))

    def test_vitest_non_assertion_and_pass_on_base_fail(self):
        r = self.gate([1, 2], ["- MUST 1: src/calc.test.ts::calc > throws [FAIL_TO_PASS]",
                               "- MUST 2: src/calc.test.ts::calc > formats [FAIL_TO_PASS]"], code=1)
        reason = self.row(r, "FAIL_TO_PASS", "src/calc.test.ts::calc > throws")["reason"]
        self.assertTrue(reason.startswith("error on base, not an assertion: TypeError"), reason)
        self.assertIn("passes on base", self.row(r, "FAIL_TO_PASS", "src/calc.test.ts::calc > formats")["reason"])

    def test_vitest_name_matching_two_tests_is_ambiguous(self):
        r = self.gate([1], ["- MUST 1: src/calc.test.ts::calc > twice [PASS_TO_PASS]"], code=1)
        self.assertTrue(r["PASS_TO_PASS"][0]["reason"].startswith("ambiguous at head"))

    def test_test_name_with_colons_quotes_and_brackets(self):
        r = self.gate([1], ['- MUST 1: src/calc.test.ts::calc > parse ["a"] > reads a::b [PASS_TO_PASS]'], code=0)
        self.assertEqual('src/calc.test.ts::calc > parse ["a"] > reads a::b', r["PASS_TO_PASS"][0]["test"])
        args = self.logged("vitest")[0]
        self.assertEqual('calc(?: > | )parse \\["a"\\](?: > | )reads a::b', args[args.index("-t") + 1])

    def test_missing_vitest_test_fails(self):
        r = self.gate([1], ["- MUST 1: src/calc.test.ts::calc > nope [PASS_TO_PASS]"], code=1)
        self.assertTrue(r["PASS_TO_PASS"][0]["reason"].startswith("missing at head"))


class VitestLoadOnBaseTest(GateCase):
    base_files = {"src/calc.test.ts": "// none\n", "FAKE_VITEST": "vitest-load.json\n"}
    head_files = {"src/calc.test.ts": "// calc tests\n", "src/format.ts": "export {}\n", "FAKE_VITEST": "vitest-head.json\n"}

    def test_vitest_file_that_fails_to_load_on_base_fails_the_gate(self):
        r = self.gate([1], ["- MUST 1: src/calc.test.ts::calc > adds [FAIL_TO_PASS]"], code=1)
        reason = r["FAIL_TO_PASS"][0]["reason"]
        self.assertTrue(reason.startswith("load on base, not an assertion: Failed to load url ./format"), reason)


class StrykerErrorTest(GateCase):
    base_files = {"src/calc.ts": TS_BASE, "src/calc.test.ts": "// t\n", "FAKE_VITEST": "vitest-head.json\n",
                  "FAKE_STRYKER": "error\n", "stryker.config.mjs": "export default {}\n"}
    head_files = {"src/calc.ts": TS_HEAD}

    def test_stryker_error_fails_the_gate_with_its_message(self):
        r = self.gate([1], ["- MUST 1: src/calc.test.ts::calc > adds [PASS_TO_PASS]"], code=1)
        self.assertIn("ConfigError: no test runner", r["PASS_TO_PASS"][0]["reason"])


class NoSourceChangeTest(GateCase):
    base_files = {"src/calc.ts": TS_BASE, "src/calc.test.ts": "// t\n", "FAKE_VITEST": "vitest-head.json\n",
                  "FAKE_STRYKER": "mutation.json\n", "stryker.config.json": "{}\n"}
    head_files = {"src/calc.test.ts": "// t2\n", "README.md": "docs\n"}

    def test_change_with_no_source_lines_runs_no_mutants(self):
        r = self.gate([1], ["- MUST 1: src/calc.test.ts::calc > adds [PASS_TO_PASS]"], code=0)
        self.assertEqual("no changed source lines: no mutants run", r["PASS_TO_PASS"][0]["reason"])
        self.assertEqual(0, r["mutants_run"])
        self.assertEqual([], self.logged("stryker"))


class ParseMapTest(unittest.TestCase):
    def test_forms(self):
        entries, problems, found = parse_map(
            "- MUST 1: a/b.test.ts::x > y [\"z\"] :: w [FAIL_TO_PASS]\n- MUST 2: none (docs only)\n"
            "- MUST 3: a.py::T.t\n- MUST <n>: <test file>::<name> [PASS_TO_PASS]\n")
        self.assertTrue(found)
        self.assertEqual(("a/b.test.ts", 'x > y ["z"] :: w', "FAIL_TO_PASS"),
                         (entries[0]["file"], entries[0]["name"], entries[0]["kind"]))
        self.assertEqual("docs only", entries[1]["none"])
        self.assertEqual(1, len(problems))
        self.assertFalse(parse_map("REQUIREMENTS MAP\n(none)\n")[2])

    def test_help_exits_zero(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, main(["--help"]))
            self.assertEqual(0, main(["check", "--help"]))


if __name__ == "__main__":
    unittest.main()
