import contextlib
import io
import os
import re
import sys
import tempfile
import unittest
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
                 "rereview": fill("rereview.md"), "resume": fill("resume.md")}
        kinds = {"rereview": "review", "resume": "other"}
        self.assertEqual(sorted(p.name for p in assets.glob("*.md")),
                         ["fix.md", "preamble-research.md", "preamble-worker.md", "rereview.md", "resume.md", "review.md", "task-body.md"])
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


if __name__ == "__main__":
    unittest.main()
