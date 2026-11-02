import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

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
ODD_TEST = """import os
import unittest


class OddTest(unittest.TestCase):
    def tearDown(self):
        if self._testMethodName == "test_assert_and_teardown":
            raise RuntimeError("teardown broke")

    def test_assert_and_teardown(self):
        self.assertEqual(1, 2)

    def test_subtest_error(self):
        for i in (1, 2):
            with self.subTest(i=i):
                self.assertEqual(1, 1)
                if i == 2:
                    raise KeyError("sub")

    @unittest.expectedFailure
    def test_unexpected_success(self):
        pass

    def test_exits(self):
        os._exit(3)
"""
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
                  "pkg/test_fmt.py": FMT_TEST, "pkg/test_slow.py": SLOW_TEST, "pkg/test_odd.py": ODD_TEST}

    def test_every_unittest_error_and_failure_of_the_test_is_kept(self):
        r = self.gate([1, 2, 3, 4], ["- MUST 1: pkg/test_odd.py::OddTest.test_assert_and_teardown [PASS_TO_PASS]",
                                     "- MUST 2: pkg/test_odd.py::OddTest.test_subtest_error [PASS_TO_PASS]",
                                     "- MUST 3: pkg/test_odd.py::OddTest.test_unexpected_success [PASS_TO_PASS]",
                                     "- MUST 4: pkg/test_odd.py::OddTest.test_exits [PASS_TO_PASS]"], code=1)
        reasons = [x["reason"] for x in r["PASS_TO_PASS"]]
        self.assertTrue(reasons[0].startswith("error at head"), reasons[0])
        self.assertIn("RuntimeError: teardown broke", reasons[0])
        self.assertIn("AssertionError: 1 != 2", reasons[0])
        self.assertTrue(reasons[1].startswith("error at head") and "KeyError: 'sub'" in reasons[1] and "(i=2)" in reasons[1], reasons[1])
        self.assertTrue(reasons[2].startswith("unexpected success at head"), reasons[2])
        self.assertTrue(reasons[3].startswith("error at head: the test process exited 3 without a result"), reasons[3])

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
        self.assertIn("pkg/test_gone.py is not tracked at head", self.row(r, "FAIL_TO_PASS", "pkg/test_gone.py::GoneTest.test_x")["reason"])
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

    def test_report_whose_only_map_is_fenced_fails_as_no_map(self):
        r = self.gate([1], ["```", "- MUST 1: pkg/test_calc.py::CalcTest.test_clamp_negative [FAIL_TO_PASS]", "```"], code=1)
        self.assertIn("no REQUIREMENTS MAP", r["problems"][0])
        self.assertEqual([], r["FAIL_TO_PASS"])

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

    def test_named_project_runs_only_that_project(self):
        self.gate([1, 2], ["- MUST 1: src/calc.test.ts::|unit| src/calc.test.ts > calc > adds [PASS_TO_PASS]",
                           "- MUST 2: src/calc.test.ts::calc > formats [PASS_TO_PASS]"], "--mutants", "none", code=0)
        named, plain = self.logged("vitest")
        self.assertEqual("unit", named[named.index("--project") + 1])
        self.assertNotIn("--project", plain)


def vitest_file(path, *tests, status="passed", message=""):
    return {"name": path, "status": status, "message": message,
            "assertionResults": [{"ancestorTitles": ["calc"], "title": t, "status": s, "failureMessages": m}
                                 for t, s, m in tests]}


class VitestOutcomeTest(unittest.TestCase):
    path = "src/calc.test.ts"

    def outcome(self, *files, code=0, err=""):
        tree = tempfile.gettempdir()
        report = {"testResults": [dict(f, name=os.path.join(tree, f["name"])) for f in files]}
        return reqgate.vitest_outcome(report, tree, self.path, ["calc", "adds"], code, err)

    def test_one_project_passes(self):
        self.assertEqual(("passed", ""), self.outcome(vitest_file(self.path, ("adds", "passed", []))))

    def test_same_test_in_two_projects_is_ambiguous(self):
        status, detail = self.outcome(vitest_file(self.path, ("adds", "passed", [])), vitest_file(self.path, ("adds", "passed", [])))
        self.assertEqual("ambiguous", status)
        self.assertIn("across 2 projects", detail)

    def test_suite_failure_with_a_passing_test_is_an_error(self):
        status, detail = self.outcome(vitest_file(self.path, ("adds", "passed", []), status="failed",
                                                  message="Error: afterAll hook broke"), code=1)
        self.assertEqual(("error", "the suite failed: Error: afterAll hook broke"), (status, detail))

    def test_suite_failure_with_an_assertion_is_not_an_assertion(self):
        status, _ = self.outcome(vitest_file(self.path, ("adds", "failed", ["AssertionError: expected 1 to be 2"]),
                                             status="failed", message="Error: beforeAll broke"), code=1)
        self.assertEqual("error", status)

    def test_assertion_with_a_second_error_is_an_error_and_keeps_both(self):
        status, detail = self.outcome(vitest_file(self.path, ("adds", "failed", ["AssertionError: expected 1 to be 2\n  at x",
                                                                                 "TypeError: cleanup broke\n  at y"]), status="failed"), code=1)
        self.assertEqual(("error", "AssertionError: expected 1 to be 2 | TypeError: cleanup broke"), (status, detail))

    def test_non_zero_exit_with_no_result_is_an_error(self):
        status, detail = self.outcome(vitest_file(self.path, ("other", "passed", [])), code=1, err="Error: config broke")
        self.assertEqual("error", status)
        self.assertIn("Vitest exited 1: Error: config broke", detail)
        self.assertEqual("error", self.outcome(code=1, err="boom")[0])

    def test_non_zero_exit_with_only_passing_results_is_an_error(self):
        status, detail = self.outcome(vitest_file(self.path, ("adds", "passed", [])), code=1, err="Unhandled Rejection")
        self.assertEqual("error", status)
        self.assertIn("Unhandled Rejection", detail)


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


class PathGateTest(GateCase):
    base_files = {"pkg/calc.py": CALC_BASE, "pkg/test_calc.py": TEST_BASE}
    head_files = {"pkg/calc.py": CALC_HEAD, "pkg/test_calc.py": TEST_HEAD}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        outside = os.path.join(cls.root, "test_outside.py")
        with open(outside, "w", encoding="utf-8") as f:
            f.write(TEST_HEAD)
        git(cls.repo, "checkout", "-q", "ow/x")
        os.symlink(outside, os.path.join(cls.repo, "pkg", "test_link.py"))
        git(cls.repo, "add", "pkg/test_link.py")
        git(cls.repo, "commit", "-q", "-m", "link")
        git(cls.repo, "checkout", "-q", "main")
        os.makedirs(os.path.join(cls.repo, ".git", "info"), exist_ok=True)
        with open(os.path.join(cls.repo, ".git", "info", "exclude"), "a", encoding="utf-8") as f:
            f.write("pkg/test_untracked.py\n")
        with open(os.path.join(cls.repo, "pkg", "test_untracked.py"), "w", encoding="utf-8") as f:
            f.write(TEST_HEAD)

    def test_paths_outside_the_head_tree_fail_before_anything_runs(self):
        outside = os.path.join(self.root, "test_outside.py")
        lines = {f"{outside}::CalcTest.test_clamp_negative": "is absolute",
                 "../test_outside.py::CalcTest.test_clamp_negative": "escapes the repository",
                 "pkg/../../test_outside.py::CalcTest.test_clamp_negative": "escapes the repository",
                 "pkg/test_link.py::CalcTest.test_clamp_negative": "is a symlink",
                 "pkg/test_untracked.py::CalcTest.test_clamp_negative": "is not tracked at head"}
        ran = []
        with unittest.mock.patch.dict(reqgate.RUNNERS, unittest=lambda *a, **k: ran.append(a) or ("passed", "")):
            r = self.gate([1], [f"- MUST 1: {t} [FAIL_TO_PASS]" for t in lines], code=1)
        self.assertEqual([], ran)
        for test, why in lines.items():
            row = self.row(r, "FAIL_TO_PASS", test)
            self.assertEqual("fail", row["status"])
            self.assertIn(why, row["reason"])


class ParseMapTest(unittest.TestCase):
    def test_forms(self):
        entries, problems, found = parse_map(
            "## REQUIREMENTS MAP\n"
            "- MUST 1: a/b.test.ts::x > y [\"z\"] :: w [FAIL_TO_PASS]\n- MUST 2: none (docs only)\n"
            "- MUST 3: a.py::T.t\n- MUST <n>: <test file>::<name> [PASS_TO_PASS]\n")
        self.assertTrue(found)
        self.assertEqual(("a/b.test.ts", 'x > y ["z"] :: w', "FAIL_TO_PASS"),
                         (entries[0]["file"], entries[0]["name"], entries[0]["kind"]))
        self.assertEqual("docs only", entries[1]["none"])
        self.assertEqual(1, len(problems))
        self.assertFalse(parse_map("REQUIREMENTS MAP\n(none)\n")[2])

    def test_fenced_example_alone_is_no_map(self):
        text = ("9. REQUIREMENTS MAP\n```\n- MUST 1: a/test_x.py::XTest.test_y [FAIL_TO_PASS]\n```\n"
                "- MUST 2: a/test_x.py::XTest.test_z [PASS_TO_PASS]\n")
        self.assertEqual(["2"], [e["must"] for e in parse_map(text)[0]])
        self.assertEqual(([], [], False), parse_map("9. REQUIREMENTS MAP\n```\n- MUST 1: a/test_x.py::XTest.test_y [FAIL_TO_PASS]\n```\n"))

    def test_quoted_example_and_lines_outside_the_map_are_ignored(self):
        text = ("1. What changed\n- MUST 3: a/test_x.py::XTest.test_q [PASS_TO_PASS]\n"
                "9. REQUIREMENTS MAP\n> - MUST 1: a/test_x.py::XTest.test_y [FAIL_TO_PASS]\n"
                "- MUST 2: a/test_x.py::XTest.test_z [PASS_TO_PASS]\n## Notes\n- MUST 4: none (after the map)\n")
        entries, problems, found = parse_map(text)
        self.assertEqual((["2"], [], True), ([e["must"] for e in entries], problems, found))

    def test_help_exits_zero(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, main(["--help"]))
            self.assertEqual(0, main(["check", "--help"]))


class TemplateFormTest(unittest.TestCase):
    def test_the_preamble_asks_for_the_map_in_the_form_the_gate_reads(self):
        skill = os.path.dirname(HERE)
        with open(os.path.join(skill, "assets", "preamble-worker.md"), encoding="utf-8") as f:
            text = f.read()
        form = "`- MUST <n>: <test file path>::<test name> [FAIL_TO_PASS|PASS_TO_PASS]`"
        self.assertIn("REQUIREMENTS MAP", text)
        self.assertIn(form, text)
        self.assertIn("`- MUST <n>: none (<why>)`", text)
        for kind in ("FAIL_TO_PASS", "PASS_TO_PASS"):
            line = form.strip("`").replace("<n>", "3").replace("<test file path>", "a/test_x.py") \
                .replace("<test name>", "XTest.test_y").replace("FAIL_TO_PASS|PASS_TO_PASS", kind)
            entries, problems, _ = parse_map("REQUIREMENTS MAP\n" + line)
            self.assertEqual(([], "a/test_x.py", "XTest.test_y", kind),
                             (problems, entries[0]["file"], entries[0]["name"], entries[0]["kind"]))
        with open(os.path.join(skill, "SKILL.md"), encoding="utf-8") as f:
            skill_text = f.read()
        for phrase in ("reqgate.py check", "--warn", "phase 4", "what the author did not imagine"):
            self.assertIn(phrase, skill_text)


if __name__ == "__main__":
    unittest.main()
