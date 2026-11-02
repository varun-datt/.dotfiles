import contextlib
import datetime as dt
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vault_validator import VaultValidator, main  # noqa: E402

RULES = {
    "note_roots": ["notes"],
    "required_fields": ["title", "type"],
    "types": ["note", "decision"],
    "type_fields": {"decision": ["date"]},
    "dated_types": ["decision"],
}


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class EngineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def findings(self, **overrides):
        rules = {**RULES, **overrides}
        return VaultValidator(self.root, rules=rules, today=dt.date(2026, 10, 24)).run()

    def errors(self, **overrides):
        return {(f.rule, f.path) for f in self.findings(**overrides) if f.severity == "error"}

    def test_checks_without_rules_do_not_run(self) -> None:
        write(self.root / "notes/plain.md", "---\ntitle: Plain\ntype: note\n---\n\nText\n")
        self.assertEqual([], self.findings())

    def test_required_fields_and_types_come_from_the_rules(self) -> None:
        write(self.root / "notes/odd.md", "---\ntitle: Odd\ntype: recipe\n---\n")
        write(self.root / "notes/bare.md", "---\ntype: note\n---\n")
        self.assertEqual(
            {("FRONTMATTER_TYPE", "notes/odd.md"), ("FRONTMATTER_REQUIRED", "notes/bare.md")},
            self.errors(),
        )

    def test_month_dates_need_the_rule_and_still_name_the_file(self) -> None:
        write(self.root / "notes/2024-11-old-call.md", "---\ntitle: Old\ntype: decision\ndate: 2024-11\n---\n")
        write(self.root / "notes/misnamed.md", "---\ntitle: Misnamed\ntype: decision\ndate: 2024-11\n---\n")
        self.assertEqual(
            {("FRONTMATTER_DATE", "notes/2024-11-old-call.md"), ("FRONTMATTER_DATE", "notes/misnamed.md")},
            self.errors(),
        )
        self.assertEqual({("DATED_FILENAME", "notes/misnamed.md")}, self.errors(dated_month_ok=True))

    def test_a_summary_older_than_a_note_it_links_is_a_warning(self) -> None:
        summary = "---\ntitle: Hub\ntype: moc\nupdated: 2026-10-01\n---\n\n[[fresh]] [[close]] [[notes/old]]\n"
        write(self.root / "notes/hub.md", summary)
        write(self.root / "notes/fresh.md", "---\ntitle: Fresh\ntype: note\nupdated: 2026-10-20\n---\n")
        write(self.root / "notes/close.md", "---\ntitle: Close\ntype: note\nupdated: 2026-10-05\n---\n")
        write(self.root / "notes/old.md", "---\ntitle: Old\ntype: note\nupdated: 2026-09-01\n---\n")
        rules = {"types": ["note", "moc"], "summaries": {"types": ["moc"], "grace_days": 7}}
        stale = [f for f in self.findings(**rules) if f.rule == "SUMMARY_STALE"]
        self.assertEqual([("warning", "notes/hub.md")], [(f.severity, f.path) for f in stale])
        self.assertIn("1 note(s)", stale[0].message)
        self.assertIn("notes/fresh.md", stale[0].message)
        self.assertEqual([], [f for f in self.findings(types=["note", "moc"]) if f.rule == "SUMMARY_STALE"])

    def test_baseline_downgrades_only_the_listed_finding(self) -> None:
        write(self.root / "notes/a.md", "---\ntype: note\n---\n")
        write(self.root / "notes/b.md", "---\ntype: note\n---\n")
        baseline = self.root / "baseline.json"
        baseline.write_text(json.dumps([{"rule": "FRONTMATTER_REQUIRED", "path": "notes/a.md", "subject": ""}]))
        found = VaultValidator(self.root, rules=RULES, baseline_path=baseline).run()
        self.assertEqual(
            {("notes/a.md", "warning"), ("notes/b.md", "error")},
            {(f.path, f.severity) for f in found if f.rule == "FRONTMATTER_REQUIRED"},
        )

    def test_command_needs_a_rules_file(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(2, main(["--root", str(self.root)]))
        self.assertIn("no rules file", err.getvalue())
        write(self.root / "vault-validator.json", json.dumps(RULES))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(0, main(["--root", str(self.root)]))
        self.assertIn("0 error(s)", out.getvalue())


if __name__ == "__main__":
    unittest.main()
