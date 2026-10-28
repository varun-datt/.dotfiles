import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import brief  # noqa: E402

PREAMBLE = "<!-- fill every {{PLACEHOLDER}} -->\nYou are a worker session for amc.\n"


def worker(reuse="REUSE CHECK: surveyed @panzoom/panzoom and svg-pan-zoom; using @panzoom/panzoom",
           deps="ALLOWED DEPENDENCIES: @panzoom/panzoom"):
    return PREAMBLE + "TASK: diagram pan and zoom\n" + "\n".join(x for x in (reuse, deps) if x) + "\nOUT OF SCOPE: none.\n"


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


if __name__ == "__main__":
    unittest.main()
