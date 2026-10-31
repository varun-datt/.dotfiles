import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import brief  # noqa: E402

SKILL = Path(__file__).resolve().parent.parent
AGENTS = SKILL.parent.parent
TESTING = AGENTS / "skills" / "software-testing"
PREAMBLE = SKILL / "assets" / "preamble-worker.md"
BODY = SKILL / "assets" / "task-body.md"
PLACEHOLDER = re.compile(r"\{\{([^{}|\n]+)(?:\|[^{}\n]*)?\}\}")
DEPLOYED = re.compile(r"~/\.agents/(skills/[^`\s)]+)")
LINK = re.compile(r"\]\(([^)\s]+)\)")
CHANGED = [SKILL / "SKILL.md", PREAMBLE, TESTING / "SKILL.md", *sorted((TESTING / "references").glob("*.md"))]


def fill(text):
    return PLACEHOLDER.sub(lambda m: f"WHEN sample {m.group(1).lower()} arrives, the sample part SHALL answer", text)


def visible(text):
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


class PreambleTest(unittest.TestCase):
    def test_the_filled_preamble_and_task_body_pass_the_brief_check(self):
        prompt = fill(PREAMBLE.read_text()) + fill(BODY.read_text())
        self.assertEqual(brief.problems(prompt), [])

    def test_the_unfilled_preamble_and_task_body_are_refused(self):
        found = brief.problems(PREAMBLE.read_text() + BODY.read_text())
        self.assertIn("unfilled placeholder {{GATES}}", found)
        self.assertIn("unfilled placeholder {{READ_FIRST}}", found)

    def test_the_preamble_keeps_every_placeholder_but_the_self_review_step(self):
        names = set(PLACEHOLDER.findall(visible(PREAMBLE.read_text())))
        self.assertEqual(names, {
            "PROJECT", "PROJECT_DIR", "READ_FIRST", "ORCHESTRATOR_OWNED_FILES", "OWNER_INSTANCE",
            "EXTRA_DIRS_OR_NONE", "PORTS", "INSTALL_STEP", "SHELL_TRAPS_OR_DELETE", "GATES",
            "RECORD_DRAFTS", "STANDING_OWNER_RULES"})

    def test_the_preamble_keeps_the_hard_rules(self):
        text = PREAMBLE.read_text()
        for rule in ("Never `git push`", "git commit --only <paths>", "Never `git add -A`",
                     "git show --stat --format='' HEAD", "Never bypass a commit hook", "${VAR:+set}",
                     "in the FOREGROUND", "`read_bash` `delay` at 240 or less", "`pgrep -x yes | wc -l` = 0",
                     "Comments: only a WHY", "ALLOWED DEPENDENCIES line names it", "Never truncate output",
                     "Mark every claim VERIFIED", "Your LAST message is the report", ".gates/<gate>.log"):
            self.assertIn(rule, text)

    def test_the_method_comes_before_the_hard_rules(self):
        text = PREAMBLE.read_text()
        steps = [text.index(f"\n{n}. {word}") for n, word in enumerate(("MAP", "CASES", "FACTS", "BUILD", "PROVE", "CHECK"), 1)]
        self.assertEqual(steps, sorted(steps))
        self.assertLess(steps[-1], text.index("HARD RULES"))

    def test_the_preamble_names_testing_references_by_deployed_paths_that_exist(self):
        text = visible(PREAMBLE.read_text())
        paths = DEPLOYED.findall(text)
        self.assertIn("skills/software-testing/references/case-lists.md", paths)
        for p in paths:
            self.assertTrue((AGENTS / p).is_file(), p)
        self.assertEqual(re.findall(r"(?<![/\w])references/[\w-]+\.md", text), [])

    def test_every_relative_link_in_the_changed_files_resolves(self):
        for f in CHANGED:
            for target in LINK.findall(f.read_text()):
                if re.match(r"[a-z]+:", target) or target.startswith("#"):
                    continue
                self.assertTrue((f.parent / target.split("#")[0]).exists(), f"{f.name}: {target}")

    def test_the_testing_skill_links_every_reference(self):
        links = set(LINK.findall((TESTING / "SKILL.md").read_text()))
        for name in ("case-lists", "event-orders", "flaky-tests", "mutation-checks"):
            self.assertIn(f"references/{name}.md", links)

    def test_no_file_in_the_skill_mentions_the_self_review_step(self):
        gone = "SELF_REVIEW" + "_STEP"
        hits = [str(p) for p in SKILL.rglob("*") if p.is_file() and gone in p.read_text(errors="replace")]
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
