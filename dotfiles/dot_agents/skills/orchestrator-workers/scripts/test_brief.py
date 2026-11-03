import contextlib
import io
import os
import re
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import brief  # noqa: E402

PREAMBLE = "<!-- fill every {{PLACEHOLDER}} -->\nYou are a worker session for amc.\n"
MUST = "MUST (each is checked by the reviewer)\n1. WHEN the diagram is dragged, the view SHALL pan with it.\n"
FIELDS = ("RISK: UI\nCASES THE ORCHESTRATOR KNOWS: none, a new view with no earlier findings\n"
          "FACTS TO VERIFY: none, the library is already in use\n")


def worker(reuse="REUSE CHECK: surveyed @panzoom/panzoom and svg-pan-zoom; using @panzoom/panzoom",
           deps="ALLOWED DEPENDENCIES: @panzoom/panzoom", must=MUST, fields=FIELDS, budget="TIME BUDGET: 30 minutes.\n"):
    return (PREAMBLE + "TASK: diagram pan and zoom\n\n" + must + "\n" + fields
            + "\n".join(x for x in (reuse, deps) if x) + "\nOUT OF SCOPE: none.\n" + budget)


def check(text):
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "x.prompt.md")
        Path(path).write_text(text)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = brief.main(["check", path])
        return code, err.getvalue()


class BriefTest(unittest.TestCase):
    def test_a_filled_worker_prompt_passes(self):
        self.assertEqual(brief.problems(worker()), [])

    def test_naming_the_turn_state_file_needs_a_host_state_answer(self):
        names = FIELDS.replace("none, a new view", "`validSpecial` in `src/host/sessions.ts`; a new view")
        found = brief.problems(worker(fields=names))
        self.assertEqual(len(found), 1)
        self.assertIn("host-state none (why)", found[0])
        for risk in ("RISK: UI, host-state none (no change to how sessions send)", "RISK: host-state (late events)"):
            self.assertEqual(brief.problems(worker(fields=names.replace("RISK: UI", risk))), [], risk)
        self.assertEqual(brief.problems("Turn state lives in `src/host/sessions.ts`.\n" + worker()), [])

    def test_an_unfilled_placeholder_fails_outside_comments_and_inline_code(self):
        self.assertEqual(brief.problems(worker() + "YOUR RESOURCES: ports {{PORTS}}\n"), ["unfilled placeholder {{PORTS}}"])
        self.assertEqual(brief.problems(worker() + "Placeholders look like `{{NAME}}`.\n"), [])

    def test_a_worker_prompt_needs_both_fields(self):
        self.assertEqual(brief.problems(worker(reuse=None)), ["no REUSE CHECK line"])
        self.assertEqual(brief.problems(worker(deps=None)), ["no ALLOWED DEPENDENCIES line"])

    def test_a_bare_none_is_refused_for_reuse_but_not_for_dependencies(self):
        self.assertEqual(len(brief.problems(worker(reuse="REUSE CHECK: none"))), 1)
        self.assertEqual(len(brief.problems(worker(reuse="REUSE CHECK:"))), 1)
        self.assertEqual(brief.problems(worker(reuse="REUSE CHECK: not needed, a one-line fix", deps="ALLOWED DEPENDENCIES: none")), [])

    def test_a_fix_round_prompt_needs_no_reuse_fields(self):
        self.assertEqual(brief.problems("The review of your branch is in. Fix the findings below.\n"), [])

    def test_check_exits_2_on_a_problem_and_0_when_ready(self):
        with tempfile.TemporaryDirectory() as d:
            good, bad = os.path.join(d, "good.prompt.md"), os.path.join(d, "bad.prompt.md")
            Path(good).write_text(worker())
            Path(bad).write_text(worker(reuse=None))
            self.assertEqual(brief.main(["check", good]), 0)
            self.assertEqual(brief.main(["check", good, bad]), 2)

    def test_a_brief_without_risk_fails(self):
        self.assertEqual(brief.problems(worker(fields=FIELDS.replace("RISK: UI\n", ""))), ["no RISK line"])

    def test_each_brief_field_is_required(self):
        for field in ("RISK", "CASES THE ORCHESTRATOR KNOWS", "FACTS TO VERIFY"):
            kept = "".join(x for x in FIELDS.splitlines(True) if not x.startswith(field + ":"))
            self.assertEqual(brief.problems(worker(fields=kept)), [f"no {field} line"])

    def test_a_must_without_shall_fails_naming_its_line(self):
        found = brief.problems(worker(must="MUST\n1. WHEN dragged, the view pans.\n2. WHEN zoomed, the view SHALL scale.\n"))
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0].startswith("line 6: MUST 1 has no SHALL"), found[0])

    def test_shall_not_and_parenthesised_numbers_pass(self):
        self.assertEqual(brief.problems(worker(must="MUST\n1) WHEN read-only, the view SHALL NOT save.\n")), [])
        self.assertEqual(len(brief.problems(worker(must="MUST\n1) WHEN read-only, the view does not save.\n"))), 1)

    def test_a_wrapped_must_with_shall_on_its_second_line_passes(self):
        self.assertEqual(brief.problems(worker(must="MUST\n1. WHEN the diagram is dragged past its edge,\n   the view SHALL stop at the edge.\n")), [])
        self.assertEqual(brief.problems(worker(must="MUST\n1. WHEN the diagram is dragged past its edge, the view\nSHALL (once) stop at the edge.\n")), [])

    def test_numbered_lines_outside_must_are_not_musts(self):
        self.assertEqual(brief.problems(worker() + "ACCEPTANCE\n1. A test drags the diagram.\n"), [])

    def test_none_with_a_reason_passes_and_none_alone_fails(self):
        self.assertEqual(brief.problems(worker()), [])
        for bare in ("none", "None.", "", "n/a"):
            found = brief.problems(worker(fields=FIELDS.replace("none, the library is already in use", bare)))
            self.assertEqual(len(found), 1, bare)
            self.assertIn("FACTS TO VERIFY is empty", found[0])
            self.assertRegex(found[0], r"^line \d+: ")

    def test_a_fix_prompt_composed_from_the_preamble_still_passes(self):
        fix = PREAMBLE + "THIS IS A FIX ROUND in a fresh session.\nORIGINAL BRIEF\nTASK: x\nMUST\n1. Pan.\n" \
            + "REUSE CHECK: not needed, a fix\nALLOWED DEPENDENCIES: none\nTIME BUDGET: 90\n"
        self.assertEqual(brief.problems(fix), [])
        self.assertEqual(brief.warnings(fix), [])

    def test_a_review_prompt_quoting_a_worker_brief_is_not_held_to_brief_rules(self):
        review = "You are a read-only reviewer.\nTASK\n" + worker(fields="")
        self.assertEqual(brief.problems(review), [])

    def test_a_time_budget_over_45_warns_and_keeps_exit_0(self):
        code, err = check(worker(budget="TIME BUDGET: 60 minutes.\n"))
        self.assertEqual(code, 0)
        self.assertIn("warning: TIME BUDGET of 60 minutes is over 45", err)
        self.assertEqual(check(worker(budget="TIME BUDGET: 45 minutes.\n")), (0, ""))
        code, err = check(worker(budget="TIME BUDGET: 46 minutes.\n"))
        self.assertEqual(code, 0)
        self.assertIn("warning: TIME BUDGET of 46 minutes is over 45", err)
        code, err = check(worker(fields="", budget="TIME BUDGET: 60 minutes.\n"))
        self.assertEqual(code, 2)
        self.assertIn("warning: TIME BUDGET", err)

    def test_the_task_body_filled_with_sample_values_passes(self):
        body = (Path(__file__).parent.parent / "assets" / "task-body.md").read_text()
        filled = re.sub(r"\{\{[^{}\n]+\}\}", "sample value", body).replace("2. sample value", "2. WHEN zoomed, the view SHALL scale")
        self.assertEqual(brief.problems(PREAMBLE + filled), [])
        self.assertEqual(brief.problems(PREAMBLE + filled.replace("RISK: ", "")), ["no RISK line"])

    def test_text_under_the_musts_that_is_not_a_top_level_item_is_not_a_must(self):
        for extra in ("   1. Old records still load.\n", "  - 2. Old records still load.\n", "\t3) Old records load.\n",
                      "```\n2. WHEN x, y does z\nMUST\n3. no shall\n```\n", "~~~\n2. no shall\n~~~\n",
                      "> 2. WHEN x, y does z\n", "> MUST\n> 1. no shall\n", "Write each `MUST` as one sentence.\n"):
            self.assertEqual(brief.problems(worker(must=MUST + extra)), [], extra)
        self.assertEqual(len(brief.problems(worker(must=MUST + "```\nx\n```\n2. no shall\n"))), 1)

    def test_a_fenced_example_of_a_field_is_not_the_field(self):
        fenced = "```\nRISK: UI\n```\n"
        self.assertEqual(brief.problems(worker(fields=fenced + FIELDS.replace("RISK: UI\n", ""))), ["no RISK line"])

    def test_kind_comes_from_the_leading_declaration_not_a_quote(self):
        quoted = worker(fields="") + "Quote from a fix: THIS IS A FIX ROUND\n> THIS IS A FIX ROUND\n"
        self.assertEqual(brief.prompt_kind(quoted), "build")
        self.assertEqual(len(brief.problems(quoted)), 3)
        for marker in ("You are a read-only reviewer", "`THIS IS A FIX ROUND`", "<!-- THIS IS A FIX ROUND -->",
                       "```\nTHIS IS A FIX ROUND\n```"):
            self.assertEqual(brief.prompt_kind(worker() + marker + "\n"), "build", marker)
        late_fix = worker() + "THIS IS A FIX ROUND\n"
        self.assertEqual(brief.prompt_kind(late_fix), "build")
        research = "You are a research worker for amc. A worker prompt opens with \"You are a worker session\".\n" \
            "MUST\n1. no shall\nREUSE CHECK: x\nALLOWED DEPENDENCIES: none\n"
        self.assertEqual(brief.prompt_kind(research), "research")
        self.assertEqual(brief.problems(research), [])
        self.assertEqual(brief.prompt_kind("```\nYou are a read-only reviewer\n```\n" + worker()), "build")
        self.assertEqual(brief.prompt_kind("Note: You are a worker session\n" + worker()), "other")

    def test_an_explicit_kind_overrides_detection(self):
        self.assertEqual(len(brief.problems(worker(fields=""), kind="fix")), 0)
        self.assertEqual(len(brief.problems(worker(fields=""), kind="build")), 3)
        code, err = check(worker(fields=""))
        self.assertEqual(code, 2)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.prompt.md")
            Path(path).write_text(worker(fields="", budget="TIME BUDGET: 90\n"))
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(brief.main(["check", "--kind", "fix", path]), 0)
                self.assertEqual(brief.main(["check", "--kind", "bogus", path]), 2)
            self.assertNotIn("warning", err.getvalue())

    def test_each_shipped_template_filled_as_skill_md_says_passes_with_its_kind(self):
        assets = Path(__file__).parent.parent / "assets"

        def fill(name):
            text = re.sub(r"\{\{[^{}\n]+\}\}", "sample value", (assets / name).read_text())
            return text.replace("2. sample value", "2. WHEN zoomed, the view SHALL scale")
        build = fill("preamble-worker.md") + fill("task-body.md")
        original = re.sub(r"\{\{[^{}\n]+\}\}", "sample value", (assets / "task-body.md").read_text())
        fix = fill("preamble-worker.md") + fill("fix.md").replace("ORIGINAL BRIEF\nsample value", "ORIGINAL BRIEF\n" + original)
        review = fill("review.md").replace("==== THE AUTHOR'S TASK ====\nsample value", "==== THE AUTHOR'S TASK ====\n" + build)
        cases = {"build": build, "fix": fix, "review": review, "research": fill("preamble-research.md") + fill("task-body.md"),
                 "rereview": fill("rereview.md"), "resume": fill("resume.md"), "critique": fill("critique-research.md")}
        kinds = {"rereview": "review", "resume": "other", "critique": "other"}
        self.assertEqual(sorted(p.name for p in assets.glob("*.md")),
                         ["critique-research.md", "fix.md", "preamble-research.md", "preamble-worker.md", "rereview.md",
                          "resume.md", "review.md", "task-body.md"])
        for name, text in cases.items():
            self.assertEqual(brief.prompt_kind(text), kinds.get(name, name), name)
            self.assertEqual(brief.problems(text), [], name)
            self.assertEqual(brief.warnings(text), [], name)

    def test_a_decorated_bare_none_is_refused_per_field(self):
        values = ("`none`", "**none**", "*None*", "_none_", "none,", "none.", "none -", "NONE;", "`n/a`.")
        for field in ("RISK", "CASES THE ORCHESTRATOR KNOWS", "FACTS TO VERIFY", "REUSE CHECK"):
            for value in values:
                fields = re.sub(rf"^{field}:.*$", f"{field}: {value}", FIELDS + "REUSE CHECK: x\n", flags=re.M)
                found = brief.problems(worker(fields=fields, reuse=None))
                self.assertEqual(len(found), 1, (field, value))
                self.assertRegex(found[0], rf"^line \d+: {field} is empty", (field, value))
            for value in ("none: a new view", "none, because the view is new", "`none` - the view is new"):
                fields = re.sub(rf"^{field}:.*$", f"{field}: {value}", FIELDS + "REUSE CHECK: x\n", flags=re.M)
                self.assertEqual(brief.problems(worker(fields=fields, reuse=None)), [], (field, value))

    def test_allowed_dependencies_may_be_a_decorated_none_but_not_empty(self):
        for value in ("none", "`none`", "None."):
            self.assertEqual(brief.problems(worker(deps=f"ALLOWED DEPENDENCIES: {value}")), [], value)
        found = brief.problems(worker(deps="ALLOWED DEPENDENCIES: `n/a`"))
        self.assertEqual(len(found), 1)
        self.assertRegex(found[0], r"^line \d+: ALLOWED DEPENDENCIES is empty")

    def test_a_missing_field_names_the_line_that_mentions_it(self):
        found = brief.problems(worker(fields=FIELDS.replace("RISK: UI", "- **RISK:** UI")))
        self.assertEqual(found, ["no RISK line: line 8 names it, but the field must start its own line"])


def claims(text):
    return [re.search(r'"([^"]+)" has no source', w).group(1) for w in brief.number_warnings(text)]


class NumberSourceTest(unittest.TestCase):
    def test_an_unsourced_number_in_goal_cases_or_facts_warns_and_the_exit_code_is_unchanged(self):
        goal = ("GOAL\nFix rounds cost 6,569 credits, 54% of the run, and 3 of 14 items failed.\n\n" + MUST + "\n"
                "RISK: UI\nCASES THE ORCHESTRATOR KNOWS: the router lost 994 credits\n"
                "FACTS TO VERIFY: 120 ms per call\n")
        text = worker(must=goal, fields="")
        self.assertEqual(claims(text), ["6,569", "54%", "3 of 14", "994", "120"])
        self.assertTrue(all(w.startswith("line ") for w in brief.number_warnings(text)))
        sections = [w.split(": ")[1] for w in brief.number_warnings(text)]
        self.assertEqual(sections, ["GOAL"] * 3 + ["CASES THE ORCHESTRATOR KNOWS", "FACTS TO VERIFY"])
        self.assertEqual(brief.problems(text), [])
        code, err = check(text)
        self.assertEqual(code, 0, err)
        self.assertEqual(err.count("warning: line "), 5, err)

    def test_a_source_on_the_same_line_or_bullet_settles_it(self):
        sourced = ["Fix rounds cost 6,569 credits (`python3 mine.py run --quality`).",
                   "The guard misses 3 of 14 forms (runqueue.py:74).", "54% of reviews were clean, per 69d558a.",
                   "Median 994 ms (https://example.com/bench).", "Fix rounds cost 6,569 credits (owner, 2026-11-02).",
                   "- 994 credits went to fixes\n  as `mine.py run --quality` shows"]
        for line in sourced:
            self.assertEqual(claims(worker(must="GOAL\n" + line + "\n\n" + MUST)), [], line)
        self.assertEqual(claims(worker(must="GOAL\n- 994 credits went to fixes\n- as `mine.py run --quality` shows\n\n"
                                            + MUST)), ["994"])

    def test_paths_versions_years_dates_and_small_numbers_are_not_claims(self):
        for line in ("Read research/2026-10-30-build-quality/case-lists.md and docs/v2/page-404.md.",
                     "The CLI is 1.0.105 and Electron 10.1.1.", "Since 2026, first seen 2026-10-30 at 14:05.",
                     "Use the 12 cases and 45 minutes.", "The lesson is in references/lessons.md about 72.",
                     "Port `4173` and `git log -n 200`."):
            self.assertEqual(claims(worker(must="GOAL\n" + line + "\n\n" + MUST)), [], line)

    def test_numbers_outside_the_three_sections_and_in_other_kinds_are_not_checked(self):
        text = worker(must=MUST + "2. WHEN 994 rows load, the view SHALL stay under 120 ms.\n")
        self.assertEqual(brief.number_warnings(text), [])
        review = "You are a read-only reviewer.\nGOAL\n994 credits.\nTASK: x\n"
        self.assertEqual(brief.warnings(review), [])

    def test_a_number_alone_in_backticks_is_a_claim(self):
        self.assertEqual(claims(worker(must="GOAL\nCosts `994` credits.\n\n" + MUST)), ["994"])

    def test_a_rate_is_a_claim(self):
        self.assertEqual(claims(worker(must="GOAL\nRate is 994/s.\n\n" + MUST)), ["994"])

    def test_an_unsourced_goal_in_a_fix_round_brief_warns(self):
        fix = "You are a worker session.\nTHIS IS A FIX ROUND\nGOAL\n994 credits.\nTASK: x\nTIME BUDGET: 90 minutes.\n"
        found = brief.warnings(fix)
        self.assertEqual(len(found), 1, found)
        self.assertIn('"994" has no source', found[0])

    def test_a_one_word_command_in_backticks_is_a_source(self):
        self.assertEqual(claims(worker(must="GOAL\n994 tests passed (`pytest`).\n\n" + MUST)), [])

    def test_a_file_line_without_an_extension_is_a_source(self):
        self.assertEqual(claims(worker(must="GOAL\n994 tests (Makefile:120).\n\n" + MUST)), [])

    def test_a_version_with_one_dot_and_a_v_is_not_a_claim(self):
        self.assertEqual(claims(worker(must="GOAL\nThe CLI is v1.105 now.\n\n" + MUST)), [])

    def test_the_task_body_says_where_every_number_comes_from(self):
        body = (Path(__file__).parent.parent / "assets" / "task-body.md").read_text()
        self.assertIn("Every number in a brief", body)
        self.assertIn("comes from a command's output,\nnamed beside it", body)


class ReliesOnTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "repo")
        git = ["git", "-C", self.repo, "-c", "user.name=t", "-c", "user.email=t@example.com"]

        def run(*args):
            return subprocess.run(list(args), check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout.strip()
        run("git", "init", "-q", "-b", "main", self.repo)
        run(*git, "commit", "-q", "--allow-empty", "-m", "base")
        self.base = run(*git, "rev-parse", "HEAD")
        run(*git, "switch", "-q", "-c", "side")
        run(*git, "commit", "-q", "--allow-empty", "-m", "side fix")
        self.side = run(*git, "rev-parse", "HEAD")
        run(*git, "switch", "-q", "main")
        run(*git, "commit", "-q", "--allow-empty", "-m", "main fix")
        self.fixed = run(*git, "rev-parse", "HEAD")
        self.wt = os.path.join(self.tmp, "wt")
        run(*git, "worktree", "add", "-q", "-b", "item", self.wt, self.side)

    def found(self, line, repo=None, cwd=None):
        old = os.getcwd()
        os.chdir(cwd or self.repo)
        try:
            return brief.problems(worker() + line + "\n", repo=repo)
        finally:
            os.chdir(old)

    def test_an_ancestor_passes_in_every_form(self):
        for line in (f"RELIES ON: {self.fixed[:7]} the import fix", f"The crash was fixed in {self.fixed}.",
                     f"Build after `{self.base}` landed.", f"Fixed in commit {self.fixed[:7]}.",
                     f"RELIES ON: {self.base[:7]} and {self.fixed[:8]}"):
            self.assertEqual(self.found(line), [], line)

    def test_which_words_name_a_commit(self):
        named = brief.relied_on(worker() + "Fixed in commit 1234567. Build after `a1b2c3d4`.\nRELIES ON: 7654321 abcdef0\n"
                                "Run after 1234568 rows; fixed in deadbeefcafe; after 2026-11-02; after the fix.\n")
        self.assertEqual([c for _, c in named], ["1234567", "a1b2c3d4", "7654321", "abcdef0", "1234568", "deadbeefcafe"])

    def assert_checked(self, line, cid):
        found = self.found(line)
        self.assertEqual(len(found), 1, (line, found))
        self.assertRegex(found[0], rf"^line \d+: relies on {cid}, which the repository at .* does not know")

    def test_fixed_in_an_all_digit_id_is_checked(self):
        self.assert_checked("It was fixed in 1234567.", "1234567")

    def test_after_an_all_digit_id_in_backticks_is_checked(self):
        self.assert_checked("Build after `1234567` lands.", "1234567")

    def test_fixed_in_an_all_letter_id_is_checked(self):
        self.assert_checked("It was fixed in deadbeef.", "deadbeef")

    def test_after_an_all_letter_id_in_backticks_is_checked(self):
        self.assert_checked("Build after `deadbeef` lands.", "deadbeef")

    def test_relies_on_all_digit_and_all_letter_ids_are_checked(self):
        found = self.found("RELIES ON: 1234567 deadbeef")
        self.assertEqual([re.search(r"relies on (\w+), which the repository .* does not know", f).group(1)
                          for f in found], ["1234567", "deadbeef"])

    def test_commit_before_an_all_digit_or_all_letter_id_is_checked(self):
        self.assert_checked("Fixed in commit 1234567.", "1234567")
        self.assert_checked("Build after commit `deadbeef`.", "deadbeef")

    def test_a_commit_on_another_branch_is_refused(self):
        found = self.found(f"RELIES ON: {self.side[:7]} the side fix")
        self.assertEqual(len(found), 1, found)
        self.assertRegex(found[0], rf"^line \d+: relies on {self.side[:7]}, which is not in main of ")
        self.assertEqual(self.found(f"It was fixed in {self.side}."), [found[0].replace(self.side[:7], self.side)])

    def test_an_unknown_id_is_refused(self):
        found = self.found("RELIES ON: 1234abcd5678 the missing fix")
        self.assertEqual(len(found), 1, found)
        self.assertIn("relies on 1234abcd5678, which the repository at", found[0])
        self.assertIn("does not know", found[0])

    def test_no_such_line_passes_and_runs_no_git(self):
        with unittest.mock.patch.object(brief.subprocess, "run", side_effect=AssertionError("git ran")):
            self.assertEqual(self.found("Build after the merge; fixed in time; after decade."), [])

    def test_repo_means_the_worktree_s_head_not_main(self):
        self.assertEqual(self.found(f"RELIES ON: {self.side[:7]}", repo=self.wt), [])
        found = self.found(f"RELIES ON: {self.fixed[:7]}", repo=self.wt)
        self.assertEqual(len(found), 1, found)
        self.assertIn("which is not in HEAD of", found[0])
        code, err = check(worker() + f"RELIES ON: {self.side[:7]}\n")
        self.assertEqual(code, 2)

    def test_no_repository_to_read_is_refused_with_how_to_fix(self):
        empty = os.path.join(self.tmp, "plain")
        os.makedirs(empty)
        found = self.found(f"RELIES ON: {self.fixed[:7]}", cwd=empty)
        self.assertEqual(len(found), 1, found)
        self.assertIn("cannot be read: pass --repo <worktree>", found[0])

    def test_the_task_body_offers_an_optional_relies_on_line(self):
        body = (Path(__file__).parent.parent / "assets" / "task-body.md").read_text()
        self.assertRegex(body, r"\nRELIES ON: \{\{[A-Z_]*OR_DELETE_THE_LINE\}\}")


REGISTER = """# Tech debt

| Id | Date | Area | Grade | File | Scenario | Source | Minutes | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TD-1 | 2026-10-01 | host | Minor | src/host/history.ts | history scenario | r1 | 5 | open |
| TD-2 | 2026-10-01 | host | Minor | src/hostile.ts | sibling scenario | r1 | 5 | open |
| TD-3 | 2026-10-01 | host | Minor | src/host/history.ts | closed scenario | r1 | 5 | closed 2026-10-02: done |
| TD-4 | 2026-10-01 | ui | Major | src/ui/file-view.tsx | view scenario | r1 | 10 | open |
| TD-10 | 2026-10-01 | gone | Minor | src/missing.ts | missing scenario | r1 | 5 | open |
"""


class DebtTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = self.tmp.name
        for f in ("src/host/history.ts", "src/hostile.ts", "src/ui/file-view.tsx"):
            os.makedirs(os.path.join(self.repo, os.path.dirname(f)), exist_ok=True)
            Path(self.repo, f).write_text("x\n")
        os.makedirs(os.path.join(self.repo, "docs"))
        Path(self.repo, "docs", "tech-debt.md").write_text(REGISTER)

    def run_check(self, text, repo=True):
        path = os.path.join(self.repo, "x.prompt.md")
        Path(path).write_text(text)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = brief.main(["check", "--repo", self.repo, path] if repo else ["check", path])
        return code, err.getvalue()

    def ids(self, extra, base=None):
        code, err = self.run_check((base or worker()) + extra)
        return code, re.findall(r"warning: (TD-\d+) is open", err)

    def test_an_open_row_on_a_named_file_warns_once_with_its_paste_line_and_exit_0(self):
        code, err = self.run_check(worker() + "Change `./src/host/history.ts` and `src/host/history.ts:12`.\n")
        self.assertEqual(code, 0)
        self.assertEqual(re.findall(r"warning: (TD-\d+) is open on (\S+),", err), [("TD-1", "src/host/history.ts")])
        self.assertIn("- TD-1 (Minor, host, about 5 min) `src/host/history.ts`: history scenario", err)

    def test_a_named_folder_with_or_without_slash_covers_files_under_it_but_not_a_sibling_prefix(self):
        self.assertEqual(self.ids("Work in `src/host`.\n"), (0, ["TD-1"]))
        self.assertEqual(self.ids("Work in `src/host/`.\n"), (0, ["TD-1"]))
        self.assertEqual(self.ids("Work in `src/`.\n"), (0, ["TD-1", "TD-2", "TD-4", "TD-10"]))

    def test_no_register_closed_rows_missing_paths_and_non_path_tokens_give_no_warning(self):
        self.assertEqual(self.ids("Run `git status`, `--repo`, `TD-3`, `.`, `..`, `/etc`, `src/missing.ts`.\n"), (0, []))
        Path(self.repo, "docs", "tech-debt.md").write_text(REGISTER.replace("| open |", "| closed 2026-10-02: x |"))
        self.assertEqual(self.ids("Change `src/host/history.ts`.\n"), (0, []))
        os.remove(os.path.join(self.repo, "docs", "tech-debt.md"))
        self.assertEqual(self.ids("Change `src/host/history.ts`.\n"), (0, []))

    def test_a_brief_that_names_the_id_gets_no_warning_but_a_longer_id_does_not_count(self):
        self.assertEqual(self.ids("Change `src/host/history.ts`.\nTECH DEBT: TD-1, fixed here.\n"), (0, []))
        self.assertEqual(self.ids("Change `src/host/history.ts`.\nTECH DEBT: TD-10 only.\n"), (0, ["TD-1"]))

    def test_a_file_inside_a_fenced_block_counts(self):
        self.assertEqual(self.ids("```\nsrc/ui/file-view.tsx\n```\n"), (0, ["TD-4"]))

    def test_the_warning_never_changes_the_exit_code(self):
        self.assertEqual(self.ids("`src/ui/file-view.tsx`\n", base=worker(reuse=None)), (2, ["TD-4"]))
        self.assertEqual(self.run_check(worker() + "`src/ui/file-view.tsx`\n", repo=False), (0, ""))
        Path(self.repo, "docs", "tech-debt.md").write_text(REGISTER + "| broken |\n")
        code, err = self.run_check(worker() + "`src/ui/file-view.tsx`\n")
        self.assertEqual(code, 0)
        self.assertIn("could not be read", err)

    def test_repo_must_name_a_folder(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(brief.main(["check", "--repo", os.path.join(self.repo, "nope"), "x.md"]), 2)
            self.assertEqual(brief.main(["check", "--repo"]), 2)

    def cli(self, *args, cwd=None):
        script = str(Path(__file__).parent / "brief.py")
        return subprocess.run([sys.executable, "-B", script, *args], cwd=cwd or self.repo,
                              capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)

    def test_options_parse_before_between_and_after_the_prompt_files(self):
        good, bad = os.path.join(self.repo, "good.md"), os.path.join(self.repo, "bad.md")
        Path(good).write_text(worker() + "`src/ui/file-view.tsx`\n")
        Path(bad).write_text(worker(reuse=None))
        orders = [["--repo", self.repo, good], [good, "--repo", self.repo], [f"--repo={self.repo}", good],
                  ["--kind", "build", good, "--repo", self.repo], [good, "--repo", self.repo, "--kind", "build"]]
        for order in orders:
            r = self.cli("check", *order)
            self.assertEqual((r.returncode, re.findall(r"warning: (TD-\d+)", r.stderr)), (0, ["TD-4"]), order)
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(brief.main(["check", *order]), 0, order)
            self.assertEqual(re.findall(r"warning: (TD-\d+)", err.getvalue()), ["TD-4"], order)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(brief.main(["check", good, "--repo", self.repo, bad]), 2)
        self.assertIn("bad.md: no REUSE CHECK line", err.getvalue())
        for order in ([good, "--repo", self.repo, bad], [good, bad, "--repo", self.repo], ["--repo", self.repo, good, bad]):
            r = self.cli("check", *order)
            self.assertEqual(r.returncode, 2, order)
            self.assertIn("bad.md: no REUSE CHECK line", r.stderr, order)
            self.assertEqual(re.findall(r"warning: (TD-\d+)", r.stderr), ["TD-4"], order)
        self.assertEqual(self.cli("check", good, "--kind", "fix").returncode, 0)
        for usage in (["check", good, "--kind", "bogus"], ["check", good, "--repo"], ["check", good, "--repo", "nope"],
                      ["check", "--repo", self.repo], ["check"], [], ["list", good]):
            self.assertEqual(self.cli(*usage).returncode, 2, usage)

    def test_a_backticked_area_does_not_replace_the_file_in_the_warning(self):
        Path(self.repo, "docs", "tech-debt.md").write_text(REGISTER.replace("| ui |", "| `ui` |"))
        code, err = self.run_check(worker() + "Change `src/ui/file-view.tsx`.\n")
        self.assertEqual(re.findall(r"warning: (TD-\d+) is open on (\S+),", err), [("TD-4", "src/ui/file-view.tsx")])

    def test_a_line_suffix_alone_still_names_the_file(self):
        self.assertEqual(self.ids("Change `src/ui/file-view.tsx:12`.\n"), (0, ["TD-4"]))
        self.assertEqual(self.ids("Change `src/ui/file-view.tsx:12-14`.\n"), (0, ["TD-4"]))

    def test_a_path_that_escapes_the_repo_is_not_named_even_when_it_exists(self):
        outside = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(outside))
        Path(outside, "x.ts").write_text("x\n")
        rel = os.path.relpath(os.path.join(outside, "x.ts"), self.repo)
        self.assertTrue(rel.startswith(".." + os.sep) and os.path.exists(os.path.join(self.repo, rel)))
        text = f"Change `{rel}`, `{os.path.join(outside, 'x.ts')}` and `src/hostile.ts`.\n"
        self.assertEqual(brief.named_paths(text, self.repo), ["src/hostile.ts"])

    def test_the_repository_root_itself_is_not_matched(self):
        self.assertEqual(self.ids(f"Worktree `{self.repo}`, `.`, `./`.\n"), (0, []))

    def test_without_repo_the_current_folders_register_is_not_read(self):
        path = os.path.join(self.repo, "x.prompt.md")
        Path(path).write_text(worker() + "Change `src/ui/file-view.tsx`.\n")
        r = self.cli("check", path, cwd=self.repo)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        here = os.getcwd()
        os.chdir(self.repo)
        self.addCleanup(os.chdir, here)
        self.assertEqual(self.run_check(worker() + "Change `src/ui/file-view.tsx`.\n", repo=False), (0, ""))


if __name__ == "__main__":
    unittest.main()
