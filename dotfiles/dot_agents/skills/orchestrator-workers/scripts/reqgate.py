#!/usr/bin/env python3
"""The requirement gate: check each MUST in a brief has a named test that can fail.

Usage:
    python3 -B reqgate.py check --repo DIR --base SHA --head REF --brief prompt.md --report report.md
        [--runner vitest|unittest] [--mutants auto|stryker|none] [--json out.json] [--warn] [--timeout S]

The brief's numbered MUSTs come from brief.py's must_items(); the report's REQUIREMENTS MAP, the lines
under a heading or numbered item named REQUIREMENTS MAP (fenced and `>`-quoted lines are ignored), holds
one line per test:
    - MUST <n>: <test file>::<test name> [FAIL_TO_PASS|PASS_TO_PASS]
    - MUST <n>: none (<why>)
FAIL_TO_PASS and PASS_TO_PASS are SWE-bench's two test lists: a test for new behaviour, which fails
before the change and passes after, and a test guarding behaviour the base already had.

Fails when a MUST has no line, a line names a MUST the brief lacks or cannot be read, the report
has no map, a mapped test path is absolute, escapes the repository, is a symlink or is not tracked at
head (checked before anything runs), or a named test is missing, ambiguous or does not pass at head. A
FAIL_TO_PASS test is
run on the base commit with only the branch's test files applied and must fail there on an
assertion (for Vitest: chai's AssertionError, a `.rejects`/`.resolves` failure, or an expect.assertions
count); failing to load, import, compile or collect shows only that the code is absent, and
fails the gate. Extension to SWE-bench: when the head tree has a Stryker config, a PASS_TO_PASS
test must kill at least one Stryker mutant on the changed source lines it covers; without a mutant
runner it is reported "not checked: no mutant runner". When the Stryker report cannot tell which
mutants the test covers (no testFiles, no test of that name, or mutants with no coveredBy) the test
fails as "attribution unavailable". A measured "covers no changed line", or "no covering test" when
Stryker's dry run ran no test at all, is reported first in the table and fails only when no other test
of the same MUST covers a changed line. A Stryker run stopped at --stryker-timeout
keeps the mutants its event-recorder reporter wrote so far, marked partial; a kill seen there passes.
Mutant counts use only Stryker's MutantStatus names; killedByThisTest is a separate count. A `none` line is reported first and counted, and
is not a failure on its own. Playwright tests (importing @playwright/test) and live tests (*.live.test.*)
are reported "not checked: no runner" and do not fail. Every test runs in a temporary detached worktree, removed afterwards.

Exit 0 when every check passes, 1 when any fails, 2 on a usage or setup error, an internal error or a
worktree it could not remove; 128+N when stopped by signal N (SIGINT, SIGTERM), after killing its child
processes and removing its worktrees. --warn reports the same and exits 0. The Vitest and Stryker
commands can be replaced with --vitest-cmd and
--stryker-cmd (defaults "npx --no-install vitest" and "npx --no-install stryker run").
"""
import argparse
import ast
import contextlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brief import brief_lines, must_items  # noqa: E402

KINDS = ("FAIL_TO_PASS", "PASS_TO_PASS")
MAP_LINE = re.compile(r"^\s*[-*]\s*MUST\s+(\d+)\s*:\s*(.*?)\s*$")
TEST_REF = re.compile(r"^(?P<file>[^\s:][^:]*?)::(?P<name>.+?)\s+\[(?P<kind>FAIL_TO_PASS|PASS_TO_PASS)\]$")
NONE_REF = re.compile(r"^none\s*\((?P<why>.*)\)$", re.S)
MAP_HEADING = re.compile(r"^\s{0,3}(?:#{1,6}\s+)?(?:\*\*)?(?:\d+[.)]\s*)?(?:\*\*)?requirements map\b", re.I)
SECTION = re.compile(r"^(?:\s{0,3}#{1,6}\s|\d+[.)]\s|\*\*[^*]+\*\*:?\s*$)")
FENCE = re.compile(r"^\s{0,3}(?:```|~~~)")
QUOTE = re.compile(r"^\s*>")
JS_SUFFIXES = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts")
TEST_DIRS = {"test", "tests", "__tests__", "fixtures", "__fixtures__", "__snapshots__"}
TEST_NAME = re.compile(r"(^test_.*\.py$|_test\.py$|\.(test|spec)\.[cm]?[jt]sx?$)")
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.M)
STRYKER_REPORT = os.path.join("reports", "mutation", "mutation.json")
STRYKER_EVENTS = os.path.join("reports", "mutation", "events")
DETAIL_LINES = 3


class SetupError(Exception):
    pass


class NoCoveringTest(Exception):
    pass


class Stopped(BaseException):
    pass


CLEANUP_ERRORS = []


def on_signal(signum, _frame):
    signal.signal(signum, signal.SIG_IGN)
    raise Stopped(signum)


def git_status(repo, *args):
    p = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return p.returncode, p.stderr.strip()


def git(repo, *args, check=True):
    p = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if check and p.returncode:
        raise SetupError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout


def last_lines(text, n=DETAIL_LINES):
    lines = [x for x in (text or "").strip().splitlines() if x.strip()]
    return " | ".join(lines[-n:])


def map_lines(text):
    """(line number, line) under a REQUIREMENTS MAP heading or numbered item, outside fences and quotes."""
    inside = fenced = False
    for n, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            fenced = not fenced
            continue
        if fenced or QUOTE.match(line):
            continue
        if SECTION.match(line) or MAP_HEADING.match(line):
            inside = bool(MAP_HEADING.match(line))
            if inside:
                continue
        if inside:
            yield n, line


def parse_map(text):
    """Return (entries, problems, found); an entry is a dict with must and either file/name/kind or none."""
    entries, problems = [], []
    for n, line in map_lines(text):
        m = MAP_LINE.match(line)
        if not m:
            continue
        must, rest = m.group(1), m.group(2)
        t, z = TEST_REF.match(rest), NONE_REF.match(rest)
        if t:
            entries.append({"must": must, "file": t["file"].strip(), "name": t["name"].strip(), "kind": t["kind"], "line": n})
        elif z:
            entries.append({"must": must, "none": z["why"].strip(), "line": n})
        else:
            problems.append(f"report line {n}: cannot read map line for MUST {must}: "
                            "write '- MUST <n>: <test file>::<test name> [FAIL_TO_PASS|PASS_TO_PASS]' or '- MUST <n>: none (<why>)'")
    return entries, problems, bool(entries or problems)


def is_test_path(path):
    parts = path.replace("\\", "/").split("/")
    return bool(TEST_NAME.search(parts[-1])) or any(p in TEST_DIRS for p in parts[:-1])


def path_problem(repo, head, path):
    """Why a mapped test path cannot be trusted, or None: it must be a relative regular file tracked at head."""
    if os.path.isabs(path) or path.startswith("~"):
        return f"{path} is absolute: name a path inside the repository"
    norm = os.path.normpath(path)
    if norm == ".." or norm.startswith("../"):
        return f"{path} escapes the repository"
    out = git(repo, "ls-tree", head, "--", norm).split()
    if not out:
        return f"{path} is not tracked at head"
    if out[0] == "120000":
        return f"{path} is a symlink: name the file it points to"
    if out[1] != "blob":
        return f"{path} is not a file"
    return None


def changed_files(repo, base, head):
    """(status, path) for each file the branch changed, renames as their new path."""
    out = git(repo, "diff", "--name-status", "--no-renames", base, head)
    return [(line.split("\t")[0][0], line.split("\t")[-1]) for line in out.splitlines() if line.strip()]


def changed_ranges(repo, base, head, files):
    """{path: [(start, end)]} of lines added or changed at head, from git diff --unified=0."""
    ranges = {}
    for path in files:
        out = git(repo, "diff", "--unified=0", "--no-color", base, head, "--", path)
        for m in HUNK.finditer(out):
            start, count = int(m.group(1)), int(m.group(2) or 1)
            if count:
                ranges.setdefault(path, []).append((start, start + count - 1))
    return ranges


@contextlib.contextmanager
def worktree(repo, ref, node_modules=None):
    tmp = tempfile.mkdtemp(prefix="reqgate-")
    tree = os.path.join(tmp, "tree")
    try:
        git(repo, "worktree", "add", "--detach", "--quiet", tree, ref)
        if node_modules and not os.path.exists(os.path.join(tree, "node_modules")):
            os.symlink(node_modules, os.path.join(tree, "node_modules"))
        yield tree
    finally:
        link = os.path.join(tree, "node_modules")
        if os.path.islink(link):
            os.unlink(link)
        code, err = git_status(repo, "worktree", "remove", "--force", tree)
        if code and os.path.exists(tree):
            CLEANUP_ERRORS.append(f"git worktree remove {tree}: {err}")
        shutil.rmtree(tmp, ignore_errors=True)
        code, err = git_status(repo, "worktree", "prune")
        if code:
            CLEANUP_ERRORS.append(f"git worktree prune: {err}")
        if os.path.exists(tmp):
            CLEANUP_ERRORS.append(f"{tmp} still exists")


def run_cmd(cmd, cwd, timeout):
    """Run in its own process group so a timeout, signal or error stops every child; returns (code, out, err) or None on timeout."""
    try:
        p = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, start_new_session=True)
    except OSError as e:
        raise SetupError(f"cannot run {cmd[0]}: {e.strerror or e}")
    try:
        out, err = p.communicate(timeout=timeout)
        return p.returncode, out, err
    except BaseException as e:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(p.pid, signal.SIGKILL)
        p.communicate()
        if isinstance(e, subprocess.TimeoutExpired):
            return None
        raise


# A test outcome: passed, failed (an assertion), error (another exception), load (could not load,
# import, compile or collect), missing, ambiguous, skipped, timeout.

UNITTEST_HELPER = r"""
import json, sys, unittest
mod, name, out = sys.argv[1:4]
def last(tb):
    lines = [x for x in (tb or "").strip().splitlines() if x.strip()]
    return lines[-1].strip() if lines else ""
def done(status, detail=""):
    with open(out, "w") as f:
        json.dump({"status": status, "detail": detail}, f)
    sys.exit(0)
loader = unittest.TestLoader()
try:
    suite = loader.loadTestsFromName(mod + "." + name)
except BaseException as e:
    done("load", f"{type(e).__name__}: {e}")
if loader.errors:
    done("load", loader.errors[0])
def flat(s):
    for t in s:
        yield from (flat(t) if isinstance(t, unittest.TestSuite) else (t,))
tests = list(flat(suite)) if isinstance(suite, unittest.TestSuite) else [suite]
if any(type(t).__name__ == "_FailedTest" for t in tests):
    done("load", "unittest could not load the test")
result = unittest.TestResult()
suite.run(result)
if result.errors and any(type(t).__name__ == "_ErrorHolder" for t, _ in result.errors):
    done("load", " | ".join(last(tb) for _, tb in result.errors))
found = ([("error", t, tb) for t, tb in result.errors] + [("failure", t, tb) for t, tb in result.failures]
         + [("unexpected success", t, "") for t in result.unexpectedSuccesses]
         + [("expected failure", t, tb) for t, tb in result.expectedFailures])
detail = " | ".join(f"{k} in {t.id()[len(mod) + 1:]}: {last(tb)}".rstrip(": ") for k, t, tb in found)
if result.errors:
    done("error", detail)
if result.failures:
    done("failed", detail)
if result.unexpectedSuccesses:
    done("unexpected success", detail)
if result.expectedFailures:
    done("expected failure", detail)
if result.testsRun == 0:
    done("missing", "no test ran")
if result.skipped and len(result.skipped) == result.testsRun:
    done("skipped", result.skipped[0][1])
done("passed")
"""


def unittest_names(source, name):
    """The Class.method names in a test file's source that `name` (Class.method or method) picks."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    found = [f"{c.name}.{f.name}" for c in tree.body if isinstance(c, ast.ClassDef)
             for f in c.body if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return [x for x in found if x == name or ("." not in name and x.split(".")[1] == name)]


def run_unittest(tree, path, name, timeout, **_):
    full = os.path.join(tree, path)
    if not os.path.isfile(full):
        return "missing", f"{path} does not exist"
    with open(full, encoding="utf-8", errors="replace") as f:
        names = unittest_names(f.read(), name)
    if names is not None:
        if not names:
            return "missing", f"no test {name} in {path}"
        if len(names) > 1:
            return "ambiguous", f"{name} matches {len(names)} tests: {', '.join(names)}"
        name = names[0]
    with tempfile.TemporaryDirectory(prefix="reqgate-out-") as tmp:
        out = os.path.join(tmp, "result.json")
        stem = os.path.splitext(os.path.basename(path))[0]
        got = run_cmd([sys.executable, "-B", "-c", UNITTEST_HELPER, stem, name, out], os.path.dirname(full), timeout)
        if got is None:
            return "timeout", f"no result after {timeout} s"
        if not os.path.exists(out):
            return "error", f"the test process exited {got[0]} without a result: " + (last_lines(got[2]) or "no output")
        with open(out, encoding="utf-8") as f:
            r = json.load(f)
    return r["status"], last_lines(r["detail"])


def split_project(name):
    """(project, rest) of a Vitest test name that may start with `|project|`."""
    m = re.match(r"^\|([^|]*)\|\s*(.*)$", name.strip(), re.S)
    return (m.group(1).strip(), m.group(2)) if m else (None, name)


def title_parts(name, path):
    """Split a Vitest test title (`describe > test`, optionally `|project| file > ...`) into its titles."""
    name = split_project(name)[1].strip()
    parts = [p for p in name.split(" > ")]
    if parts and parts[0].strip() in (path, os.path.basename(path)):
        parts = parts[1:]
    return parts


def js_escape(text):
    return re.sub(r"[\\^$.*+?()[\]{}|/]", lambda m: "\\" + m.group(), text)


def first_line(text):
    return next((x.strip() for x in (text or "").splitlines() if x.strip()), "")


ASYNC_EXPECT_FRAME = re.compile(r"^at \S*__VITEST_(?:REJECTS|RESOLVES)__ ")
VITEST_ASSERTION = re.compile(r"^(?:Error: )?(?:promise (?:resolved|rejected) .* instead of (?:rejecting|resolving)"
                              r"|expected number of assertions to be \d+, but got \d+|expected any number of assertion, but got none)$")


def vitest_assertion(message):
    """Whether one Vitest failure message (an error's stack, or its message) is an assertion.

    Chai's AssertionError names itself. A `.rejects` or `.resolves` failure, including any matcher chained
    after it, is rethrown with the stack of a plain Error made in Vitest's __VITEST_REJECTS__ or
    __VITEST_RESOLVES__ getter, so it is known by that first frame, or by its message when there is no
    stack; expect.assertions() and expect.hasAssertions() throw a plain Error with a fixed message."""
    lines = [x.strip() for x in (message or "").splitlines() if x.strip()]
    if not lines:
        return False
    if lines[0].startswith("AssertionError"):
        return True
    frame = next((x for x in lines[1:] if x.startswith("at ")), "")
    return bool(ASYNC_EXPECT_FRAME.match(frame) or VITEST_ASSERTION.match(lines[0]))


def vitest_outcome(report, tree, path, parts, code=0, err=""):
    """Read Vitest's JSON reporter output for one test file and title; code and err are Vitest's exit and stderr."""
    want = os.path.realpath(os.path.join(tree, path))
    results = report.get("testResults", [])
    files = [r for r in results if os.path.realpath(r.get("name", "")) == want]
    exited = f"Vitest exited {code}: " + (last_lines(err) or "no output")
    if not files:
        return ("error", exited + "; it did not report the file") if code else ("load", "Vitest did not report the file")
    hits, suite_errors = [], []
    for r in files:
        if not r.get("assertionResults") and r.get("status") == "failed":
            return "load", last_lines(r.get("message")) or "the file failed to load"
        hits += [a for a in r["assertionResults"]
                 if [t for t in a.get("ancestorTitles", []) if t and t != path] + [a.get("title")] == parts]
        if r.get("message"):
            suite_errors.append(first_line(r["message"]))
    if len(hits) > 1:
        where = f" across {len(files)} projects: start the name with |project|" if len(files) > 1 else ""
        return "ambiguous", f"{' > '.join(parts)} matches {len(hits)} tests{where}"
    if not hits:
        return ("error", f"{exited}; no result for {' > '.join(parts)}") if code else \
            ("missing", f"no test {' > '.join(parts)} in {path}")
    hit = hits[0]
    msgs = [m for m in hit.get("failureMessages") or [] if m]
    detail = " | ".join(first_line(m) for m in msgs + suite_errors)
    if suite_errors:
        return "error", f"the suite failed: {detail}"
    if hit.get("status") == "failed":
        # Vitest's expect throws chai's AssertionError; any other error class is not an assertion.
        return ("failed" if msgs and all(vitest_assertion(m) for m in msgs) else "error"), detail
    if hit.get("status") == "passed":
        explained = any(a.get("status") == "failed" for r in results for a in r.get("assertionResults", [])) or \
            any(r.get("status") == "failed" for r in results)
        if code and not explained:
            return "error", exited + "; the test passed"
        return "passed", ""
    return "skipped", f"status {hit.get('status')}"


def load_json(path, what):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except ValueError as e:
        raise SetupError(f"{what} is not valid JSON: {e}")


def split_cmd(cmd):
    try:
        return shlex.split(cmd)
    except ValueError as e:
        raise SetupError(f"cannot read the command {cmd!r}: {e}")


def run_vitest(tree, path, name, timeout, vitest_cmd="npx --no-install vitest", **_):
    if not os.path.isfile(os.path.join(tree, path)):
        return "missing", f"{path} does not exist"
    project = split_project(name)[0]
    parts = title_parts(name, path)
    pattern = "(?: > | )".join(js_escape(p) for p in parts)
    with tempfile.TemporaryDirectory(prefix="reqgate-out-") as tmp:
        out = os.path.join(tmp, "vitest.json")
        cmd = split_cmd(vitest_cmd) + ["run", path, "-t", pattern, "--reporter=json", f"--outputFile={out}"]
        if project:
            cmd += ["--project", project]
        got = run_cmd(cmd, tree, timeout)
        if got is None:
            return "timeout", f"no result after {timeout} s"
        if not os.path.exists(out):
            return "error", "Vitest wrote no JSON report: " + (last_lines(got[2]) or f"exit {got[0]}")
        report = load_json(out, "Vitest's report")
    return vitest_outcome(report, tree, path, parts, got[0], got[2])


RUNNERS = {"unittest": run_unittest, "vitest": run_vitest}


def pick_runner(path, forced):
    if forced:
        return forced
    if path.endswith(".py"):
        return "unittest"
    if path.endswith(JS_SUFFIXES):
        return "vitest"
    return None


def has_stryker(tree):
    return any(re.match(r"^\.?stryker\.conf(ig)?\.", f) for f in os.listdir(tree))


def partial_report(tree):
    """A report rebuilt from Stryker's event-recorder files, each written as its event happens; None before the dry run."""
    folder = os.path.join(tree, STRYKER_EVENTS)
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return None
    report, dry = {"files": {}, "testFiles": {}}, False
    for n in names:
        try:
            with open(os.path.join(folder, n), encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        if n.endswith("-onDryRunCompleted.json"):
            dry = True
            for t in data.get("result", {}).get("tests", []):
                report["testFiles"].setdefault(t.get("fileName") or "", {"tests": []})["tests"].append(
                    {"id": t.get("id"), "name": t.get("name")})
        elif n.endswith("-onMutantTested.json"):
            report["files"].setdefault(data.get("fileName") or "", {"mutants": []})["mutants"].append(data)
    return report if dry else None


def stryker_run(tree, ranges, timeout, stryker_cmd):
    """Run Stryker on the changed line ranges; returns the parsed mutation-testing-elements report.

    On a timeout the report is rebuilt from the events recorded so far and carries a "partial" note."""
    mutate = ",".join(f"{p}:{s}-{e}" for p, rs in sorted(ranges.items()) for s, e in rs)
    cmd = split_cmd(stryker_cmd) + ["--mutate", mutate, "--reporters", "json,event-recorder", "--disableBail"]
    got = run_cmd(cmd, tree, timeout)
    if got is None:
        report = partial_report(tree)
        if report is None:
            raise SetupError(f"Stryker timed out after {timeout:g} s before its dry run finished")
        report["partial"] = f"Stryker stopped at the {timeout:g} s limit"
        return report
    code, out, err = got
    report = os.path.join(tree, STRYKER_REPORT)
    if code and "No tests were executed" in out + err:
        raise NoCoveringTest("no covering test: Stryker's dry run ran no test on the changed lines")
    if code or not os.path.exists(report):
        raise SetupError(f"Stryker failed (exit {code}): " + (last_lines(err) or last_lines(out) or "no report"))
    return load_json(report, "Stryker's report")


def same_path(a, b):
    a, b = a.replace("\\", "/").lstrip("./"), b.replace("\\", "/").lstrip("./")
    return a == b or a.endswith("/" + b) or b.endswith("/" + a)


def test_ids(report, path, name):
    parts = title_parts(name, path)
    names = {" ".join(parts), " > ".join(parts)}
    return {t["id"] for f, tf in report.get("testFiles", {}).items() if same_path(f, path)
            for t in tf.get("tests", []) if t.get("name") in names}


STATUSES = ("Killed", "Survived", "Timeout", "NoCoverage", "CompileError", "RuntimeError", "Pending", "Ignored")
NOT_RUN = ("Ignored", "NoCoverage", "Pending")


def mutant_check(report, ranges, path, name):
    """(check, reason, counts) for one test from the mutants on changed lines it covers.

    counts["statuses"] counts those mutants by Stryker's MutantStatus; counts["killedByThisTest"] those
    Killed with this test in killedBy; counts["attempted"] all but Ignored."""
    counts = {"attempted": 0, "killedByThisTest": 0, "statuses": dict.fromkeys(STATUSES, 0)}
    if not report.get("testFiles"):
        return "fail", "attribution unavailable: the Stryker report has no testFiles", counts
    ids = test_ids(report, path, name)
    if not ids:
        return "fail", f"attribution unavailable: no test in the Stryker report's testFiles is named {name}", counts
    unknown = 0
    for f, result in report.get("files", {}).items():
        spans = next((rs for p, rs in ranges.items() if same_path(f, p)), None)
        if not spans:
            continue
        for m in result.get("mutants", []):
            line = m.get("location", {}).get("start", {}).get("line", 0)
            if not any(s <= line <= e for s, e in spans):
                continue
            status, by_kill = m.get("status"), ids & set(m.get("killedBy") or [])
            if by_kill or ids & set(m.get("coveredBy") or []):
                counts["attempted"] += status != "Ignored"
                counts["killedByThisTest"] += status == "Killed" and bool(by_kill)
                counts["statuses"][status] = counts["statuses"].get(status, 0) + 1
            elif m.get("coveredBy") is None and status not in ("NoCoverage", "Ignored"):
                unknown += 1
    seen = ", ".join(f"{k} {v}" for k, v in counts["statuses"].items() if v)
    if counts["killedByThisTest"]:
        return "pass", f"this test killed {counts['killedByThisTest']} of the {counts['attempted']} mutants it covers ({seen})", counts
    if unknown:
        return "fail", f"attribution unavailable: {unknown} mutants on changed lines carry no coveredBy data", counts
    if not counts["attempted"]:
        return "not checked", "covers no changed line", counts
    return "fail", f"killed none of the {counts['attempted']} mutants it covers on changed lines ({seen})", counts


def no_runner(repo, head, path):
    """"Playwright" or "live" for a test the gate has no runner for, else None."""
    if not path.endswith(JS_SUFFIXES):
        return None
    if re.search(r"\.live\.(test|spec)\.[cm]?[jt]sx?$", path):
        return "live"
    source = subprocess.run(["git", "-C", repo, "show", f"{head}:{path}"], capture_output=True, text=True,
                            stdin=subprocess.DEVNULL).stdout
    if re.search(r"""(?:from\s+|require\(\s*)['"]@playwright/test['"]""", source):
        return "Playwright"
    return None


def covers_change(e):
    """True when the test is measured to cover a changed line, False when measured not to, None when unknown."""
    if e.get("check") == "not checked" and (e["reason"] == "covers no changed line" or e["reason"].startswith("no covering test")):
        return False
    if e.get("mutants", {}).get("attempted"):
        return True
    # Only the source differs between the two trees, so failing on base on an assertion means it reached changed code.
    if e["kind"] == "FAIL_TO_PASS" and e.get("base") == "failed" and e.get("check") == "pass":
        return True
    return None


def check(args):
    started = time.monotonic()
    repo = os.path.abspath(args.repo)
    try:
        with open(args.brief, encoding="utf-8") as f:
            musts = [num for num, _, _ in must_items(brief_lines(f.read()))]
        with open(args.report, encoding="utf-8") as f:
            entries, problems, found = parse_map(f.read())
    except OSError as e:
        raise SetupError(str(e))
    if not musts:
        raise SetupError(f"{args.brief} has no numbered MUST items")
    base = git(repo, "rev-parse", "--verify", args.base + "^{commit}").strip()
    head = git(repo, "rev-parse", "--verify", args.head + "^{commit}").strip()
    if not found:
        problems.append("the report has no REQUIREMENTS MAP: add '- MUST <n>: <test file>::<test name> [FAIL_TO_PASS|PASS_TO_PASS]' lines")
    for e in entries:
        if e["must"] not in musts:
            problems.append(f"report line {e['line']}: MUST {e['must']} is not in the brief")
    unmapped = [n for n in musts if not any(e["must"] == n for e in entries)]
    problems += [f"MUST {n} has no line in the REQUIREMENTS MAP" for n in unmapped]
    tests = [e for e in entries if "file" in e and e["must"] in musts]
    nones = [e for e in entries if "none" in e and e["must"] in musts]
    for e in tests:
        why = path_problem(repo, head, e["file"])
        if why:
            e["check"], e["reason"] = "fail", why
    runnable = [e for e in tests if "check" not in e]
    changed = changed_files(repo, base, head)
    branch_tests = [p for s, p in changed if s != "D" and is_test_path(p)]
    sources = [p for s, p in changed if s != "D" and not is_test_path(p) and p.endswith(JS_SUFFIXES)]
    node_modules = os.path.join(repo, "node_modules") if os.path.isdir(os.path.join(repo, "node_modules")) else None
    opts = {"vitest_cmd": args.vitest_cmd}

    def run(tree, e):
        runner = pick_runner(e["file"], args.runner)
        if not runner:
            return "error", f"no runner for {e['file']}: pass --runner"
        return RUNNERS[runner](tree, e["file"], e["name"], args.timeout, **opts)

    for e in runnable:
        kind = no_runner(repo, head, e["file"])
        if kind:
            e["check"], e["reason"] = "not checked", f"not checked: no runner ({kind})"
    runnable = [e for e in runnable if "check" not in e]

    mutants_run, stryker_error, no_cover, statuses = 0, None, None, {}
    with worktree(repo, head, node_modules) as tree:
        for e in runnable:
            e["head"], e["head_detail"] = run(tree, e)
        keeps = [e for e in runnable if e["kind"] == "PASS_TO_PASS"]
        mode = args.mutants if args.mutants != "auto" else ("stryker" if has_stryker(tree) else "none")
        ranges = changed_ranges(repo, base, head, sources) if keeps and mode == "stryker" else {}
        report = None
        if keeps and mode == "stryker" and ranges:
            try:
                report = stryker_run(tree, ranges, args.stryker_timeout, args.stryker_cmd)
                for r in report.get("files", {}).values():
                    for m in r.get("mutants", []):
                        statuses[m.get("status")] = statuses.get(m.get("status"), 0) + 1
                mutants_run = sum(v for k, v in statuses.items() if k not in NOT_RUN)
            except NoCoveringTest as err:
                no_cover = str(err)
            except SetupError as err:
                stryker_error = str(err)
        for e in keeps:
            if mode != "stryker":
                e["check"], e["reason"] = "not checked", "not checked: no mutant runner"
            elif not ranges:
                e["check"], e["reason"] = "not checked", "no changed source lines: no mutants run"
            elif no_cover:
                e["check"], e["reason"] = "not checked", no_cover
            elif stryker_error:
                e["check"], e["reason"] = "fail", stryker_error
            else:
                e["check"], e["reason"], e["mutants"] = mutant_check(report, ranges, e["file"], e["name"])
                if report.get("partial"):
                    e["partial"] = True
                    if e["check"] == "fail" and e["reason"].startswith("killed none"):
                        e["reason"] = "no mutant killed by this test yet" + e["reason"][len("killed none"):]
                    e["reason"] = f"partial, {report['partial']}: {e['reason']}"
    news = [e for e in runnable if e["kind"] == "FAIL_TO_PASS"]
    if news:
        with worktree(repo, base, node_modules) as tree:
            for p in branch_tests:
                dest = os.path.join(tree, p)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                blob = subprocess.run(["git", "-C", repo, "show", f"{head}:{p}"], capture_output=True,
                                      stdin=subprocess.DEVNULL, check=True).stdout
                with open(dest, "wb") as f:
                    f.write(blob)
            for e in news:
                status, detail = run(tree, e)
                e["base"] = status
                if status == "failed":
                    e["check"], e["reason"] = "pass", "fails on base on an assertion"
                elif status == "passed":
                    e["check"], e["reason"] = "fail", "passes on base: it cannot catch the change"
                else:
                    e["check"], e["reason"] = "fail", f"{status} on base, not an assertion: {detail}".rstrip(": ")
    for e in runnable:
        if e["head"] != "passed":
            e["check"], e["reason"] = "fail", f"{e['head']} at head: {e['head_detail']}".rstrip(": ")
    for e in tests:
        e["covers"] = covers_change(e)
    for e in tests:
        if e["covers"] is False and e["check"] == "not checked" and not any(x["covers"] for x in tests if x["must"] == e["must"]):
            e["check"], e["reason"] = "fail", f"{e['reason']}; no other test of MUST {e['must']} covers a changed line"
    failed = bool(problems) or any(e["check"] == "fail" for e in tests)
    return {
        "passed": not failed,
        "musts": musts,
        "problems": problems,
        "none": [{"must": e["must"], "why": e["none"]} for e in nones],
        "FAIL_TO_PASS": [entry(e) for e in tests if e["kind"] == "FAIL_TO_PASS"],
        "PASS_TO_PASS": [entry(e) for e in tests if e["kind"] == "PASS_TO_PASS"],
        "unmapped": [{"must": n, "status": "fail", "reason": "no line in the REQUIREMENTS MAP"} for n in unmapped],
        "mutants_run": mutants_run,
        "mutants_partial": bool(report and report.get("partial")),
        "mutant_statuses": statuses,
        "minutes": round((time.monotonic() - started) / 60, 2),
    }


def entry(e):
    out = {"must": e["must"], "test": f"{e['file']}::{e['name']}", "status": e["check"], "reason": e["reason"]}
    if e.get("covers") is False:
        out["covers"] = False
    if "mutants" in e:
        out["mutants"] = e["mutants"]
    if e.get("partial"):
        out["partial"] = True
    return out


def mutant_text(counts):
    return f"; mutants attempted {counts['attempted']}, killed by this test {counts['killedByThisTest']}: " + ", ".join(
        f"{k} {v}" for k, v in counts["statuses"].items() if v or k in ("Killed", "Survived", "Timeout"))


def table(result):
    """One row per map line: none lines first, then PASS_TO_PASS tests that cover no changed line, then the rest by MUST."""
    rows = [(0, f"MUST {n['must']}", "none", "-", "none", n["why"]) for n in result["none"]]
    rows += [(1 if r.get("covers") is False else 2, f"MUST {r['must']}", kind, r["test"], r["status"],
              r["reason"] + (mutant_text(r["mutants"]) if "mutants" in r else ""))
             for kind in KINDS for r in result[kind]]
    rows += [(2, f"MUST {n['must']}", "unmapped", "-", n["status"], n["reason"]) for n in result["unmapped"]]
    rows.sort(key=lambda r: (r[0], int(r[1].split()[1])))
    lines = [" | ".join(r[1:]) for r in rows]
    lines += [f"problem: {p}" for p in result["problems"]]
    lines.append(f"{'PASS' if result['passed'] else 'FAIL'}: {len(result['musts'])} MUSTs, "
                 f"{sum(r['status'] == 'fail' for k in KINDS for r in result[k])} failing tests, "
                 f"{sum(r['status'] == 'not checked' for k in KINDS for r in result[k])} not checked, "
                 f"{len(result['problems'])} problems, {len(result['none'])} none (reported, not failed), "
                 f"{result['mutants_run']} mutants{' (partial)' if result.get('mutants_partial') else ''}, {result['minutes']} min")
    return "\n".join(lines)


def parser():
    ap = argparse.ArgumentParser(prog="reqgate.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="check a branch's REQUIREMENTS MAP against its brief")
    c.add_argument("--repo", required=True, help="the git repository (its checkout is never touched)")
    c.add_argument("--base", required=True, help="the branch's base commit")
    c.add_argument("--head", required=True, help="the branch or commit to check")
    c.add_argument("--brief", required=True, help="the worker prompt with the numbered MUSTs")
    c.add_argument("--report", required=True, help="the worker's report with the REQUIREMENTS MAP")
    c.add_argument("--runner", choices=sorted(RUNNERS), help="test runner; default: by the test file's suffix")
    c.add_argument("--mutants", choices=("auto", "stryker", "none"), default="auto",
                   help="mutant runner for PASS_TO_PASS tests; auto uses Stryker when the head tree has its config")
    c.add_argument("--json", help="write the result as JSON to this file")
    c.add_argument("--warn", action="store_true", help="report failures but exit 0")
    c.add_argument("--timeout", type=float, default=300, help="seconds per test run (default 300)")
    c.add_argument("--stryker-timeout", type=float, default=3600, help="seconds for the Stryker run (default 3600)")
    c.add_argument("--vitest-cmd", default="npx --no-install vitest")
    c.add_argument("--stryker-cmd", default="npx --no-install stryker run")
    return ap


def main(argv=None):
    try:
        args = parser().parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    CLEANUP_ERRORS.clear()
    saved = {s: signal.signal(s, on_signal) for s in (signal.SIGINT, signal.SIGTERM)}
    code = 2
    try:
        result = check(args)
        print(table(result))
        if args.json:
            with open(args.json, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
        code = 0 if result["passed"] or args.warn else 1
    except Stopped as e:
        print(f"reqgate: stopped by signal {e.args[0]}", file=sys.stderr)
        code = 128 + e.args[0]
    except (SetupError, subprocess.CalledProcessError) as e:
        print(f"reqgate: {e}", file=sys.stderr)
    except OSError as e:
        print(f"reqgate: {e.strerror or e}: {e.filename or ''}".rstrip(": "), file=sys.stderr)
    except Exception:
        print(f"reqgate: internal error, the gate's worktrees were removed:\n{traceback.format_exc()}", file=sys.stderr)
    finally:
        for s, h in saved.items():
            signal.signal(s, h)
    for err in CLEANUP_ERRORS:
        print(f"reqgate: could not clean up: {err}", file=sys.stderr)
    return 2 if CLEANUP_ERRORS and code < 2 else code


if __name__ == "__main__":
    sys.exit(main())
