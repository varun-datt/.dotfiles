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
        for field in brief.BRIEF_FIELDS:
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
        code, err = check(worker(fields="", budget="TIME BUDGET: 60 minutes.\n"))
        self.assertEqual(code, 2)
        self.assertIn("warning: TIME BUDGET", err)

    def test_the_task_body_filled_with_sample_values_passes(self):
        body = (Path(__file__).parent.parent / "assets" / "task-body.md").read_text()
        filled = re.sub(r"\{\{[^{}\n]+\}\}", "sample value", body).replace("2. sample value", "2. WHEN zoomed, the view SHALL scale")
        self.assertEqual(brief.problems(PREAMBLE + filled), [])
        self.assertEqual(brief.problems(PREAMBLE + filled.replace("RISK: ", "")), ["no RISK line"])


if __name__ == "__main__":
    unittest.main()
