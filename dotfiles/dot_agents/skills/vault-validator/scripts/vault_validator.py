#!/usr/bin/env python3
"""Dependency-light validation for a Markdown notes repository.

The checks are generic; each repository owns its rules in a JSON file (default
`vault-validator.json` at its root). A check whose rules section is absent does not run.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
FILENAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
WIKILINK_RE = re.compile(r"!?\[\[([^\]\n]+)\]\]")
TASK_RE = re.compile(r"^\s*[-*]\s+\[[ xX]\]\s+(.+)$", re.MULTILINE)
DATE_ANCHOR_RE = re.compile(r"(?:📅|⏳|🛫)\s*\d{4}-\d{2}-\d{2}")
DEFAULT_RULES_FILE = "vault-validator.json"


@dataclass(frozen=True)
class Finding:
    severity: str
    rule: str
    path: str
    message: str
    line: int | None = None
    subject: str = ""

    def display(self) -> str:
        location = self.path + (f":{self.line}" if self.line else "")
        return f"{self.severity.upper():7} {self.rule:32} {location} — {self.message}"


@dataclass
class ParsedMarkdown:
    path: Path
    relative: str
    text: str
    body: str
    frontmatter: dict[str, Any]
    key_lines: dict[str, int]
    errors: list[tuple[int, str]]


def scalar(value: str) -> Any:
    value = value.strip()
    if not value or value in {"null", "~"}:
        return None
    if value in {"true", "false"}:
        return value == "true"
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [scalar(part) for part in inner.split(",")]
    return value


def parse_frontmatter(text: str) -> tuple[dict[str, Any], dict[str, int], str, list[tuple[int, str]]]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, {}, text, [(1, "missing opening frontmatter delimiter")]
    try:
        end = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration:
        return {}, {}, text, [(1, "missing closing frontmatter delimiter")]

    data: dict[str, Any] = {}
    key_lines: dict[str, int] = {}
    errors: list[tuple[int, str]] = []
    index = 1
    while index < end:
        raw = lines[index]
        if not raw.strip() or raw.lstrip().startswith("#"):
            index += 1
            continue
        match = re.match(r"^([A-Za-z0-9_-]+):(?:\s*(.*))?$", raw)
        if not match:
            errors.append((index + 1, "unsupported or malformed frontmatter line"))
            index += 1
            continue
        key, raw_value = match.group(1), match.group(2) or ""
        if key in data:
            errors.append((index + 1, f"duplicate frontmatter key '{key}'"))
        key_lines[key] = index + 1
        if raw_value in {"|", ">"}:
            continuation: list[str] = []
            index += 1
            while index < end and (lines[index].startswith((" ", "\t")) or not lines[index].strip()):
                continuation.append(lines[index].strip())
                index += 1
            data[key] = "\n".join(continuation).strip()
            continue
        if raw_value == "":
            items: list[Any] = []
            cursor = index + 1
            while cursor < end:
                item = re.match(r"^\s+-\s+(.+)$", lines[cursor])
                if not item:
                    break
                items.append(scalar(item.group(1)))
                cursor += 1
            if items:
                data[key] = items
                index = cursor
                continue
        data[key] = scalar(raw_value)
        index += 1
    body = "\n".join(lines[end + 1 :])
    return data, key_lines, body, errors


def read_markdown(path: Path, root: Path) -> ParsedMarkdown:
    text = path.read_text(encoding="utf-8")
    frontmatter, key_lines, body, errors = parse_frontmatter(text)
    return ParsedMarkdown(
        path=path,
        relative=path.relative_to(root).as_posix(),
        text=text,
        body=body,
        frontmatter=frontmatter,
        key_lines=key_lines,
        errors=errors,
    )


def valid_date(value: Any) -> bool:
    if not isinstance(value, str) or not DATE_RE.fullmatch(value):
        return False
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def valid_month(value: Any) -> bool:
    return isinstance(value, str) and bool(MONTH_RE.fullmatch(value))


def meaningful(value: Any) -> bool:
    return value is not None and value != "" and value != []


def load_rules(path: Path) -> dict[str, Any]:
    rules = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rules, dict):
        raise ValueError(f"{path}: rules must be a JSON object")
    return rules


class VaultValidator:
    def __init__(
        self,
        root: Path,
        *,
        rules: dict[str, Any],
        today: dt.date | None = None,
        baseline_path: Path | None = None,
    ) -> None:
        self.root = root.resolve()
        self.rules = rules
        self.today = today or dt.date.today()
        self.findings: list[Finding] = []
        self.notes: list[ParsedMarkdown] = []
        default_baseline = rules.get("baseline")
        self.baseline_path = baseline_path or (self.root / default_baseline if default_baseline else None)
        self.used_baseline: set[int] = set()
        self.baseline = self._load_baseline()

    def _load_baseline(self) -> list[dict[str, str]]:
        if not self.baseline_path or not self.baseline_path.exists():
            return []
        try:
            value = json.loads(self.baseline_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            self.add("error", "BASELINE_INVALID", self._relative(self.baseline_path), str(exc))
            return []
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            self.add(
                "error",
                "BASELINE_INVALID",
                self._relative(self.baseline_path),
                "baseline must be a JSON list of matching objects",
            )
            return []
        return value

    def _relative(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.root).as_posix()
        except ValueError:
            return path.as_posix()

    def add(
        self,
        severity: str,
        rule: str,
        path: str,
        message: str,
        line: int | None = None,
        subject: str = "",
    ) -> None:
        if severity == "error":
            for index, entry in enumerate(self.baseline):
                if (
                    entry.get("rule") == rule
                    and entry.get("path") == path
                    and entry.get("subject") == subject
                ):
                    self.used_baseline.add(index)
                    severity = "warning"
                    message += " (accepted migration debt)"
                    break
        self.findings.append(Finding(severity, rule, path, message, line, subject))

    def run(self) -> list[Finding]:
        self._collect_notes()
        self._validate_notes()
        self._validate_wikilinks()
        self._validate_tasks_and_retention()
        self._validate_workflows()
        self._validate_bootstrap()
        self._validate_plugins()
        self._validate_operator_docs()
        self._validate_tend_state()
        self._validate_baseline_usage()
        return sorted(
            self.findings,
            key=lambda item: (item.severity != "error", item.path, item.line or 0, item.rule),
        )

    def _collect_notes(self) -> None:
        skip = {name.lower() for name in self.rules.get("skip_names", ["readme.md"])}
        for directory in self.rules.get("note_roots", []):
            base = self.root / directory
            if not base.exists():
                continue
            for path in sorted(base.rglob("*.md")):
                if path.name.lower() in skip:
                    continue
                self.notes.append(read_markdown(path, self.root))

    def _validate_notes(self) -> None:
        rules = self.rules
        contexts = set(rules.get("contexts", []))
        mixed = rules.get("mixed_context")
        mixed_re = re.compile(mixed["path_pattern"]) if mixed else None
        note_types = set(rules.get("types", []))
        statuses = rules.get("statuses", {})
        type_fields = rules.get("type_fields", {})
        for note in self.notes:
            if not FILENAME_RE.fullmatch(note.path.name):
                self.add(
                    "error",
                    "FILENAME",
                    note.relative,
                    "note filename must be lowercase kebab-case",
                )
            for line, message in note.errors:
                self.add("error", "FRONTMATTER_PARSE", note.relative, message, line)
            if note.errors and not note.frontmatter:
                continue
            fm = note.frontmatter
            for field in rules.get("required_fields", []):
                if field not in fm:
                    self.add(
                        "error",
                        "FRONTMATTER_REQUIRED",
                        note.relative,
                        f"missing required field '{field}'",
                    )
            context = fm.get("context")
            mixed_ok = mixed_re is not None and context == mixed["value"] and mixed_re.fullmatch(note.relative)
            if contexts and context not in contexts and not mixed_ok:
                allowed = " or ".join(sorted(contexts))
                extra = f"; {mixed['value']} is allowed only on {mixed['where']}" if mixed else ""
                self.add(
                    "error",
                    "FRONTMATTER_CONTEXT",
                    note.relative,
                    f"context must be {allowed}{extra}",
                    note.key_lines.get("context"),
                )
            note_type = fm.get("type")
            if note_types and note_type not in note_types:
                self.add(
                    "error",
                    "FRONTMATTER_TYPE",
                    note.relative,
                    f"type must be one of {sorted(note_types)}",
                    note.key_lines.get("type"),
                )
            expected_statuses = set(statuses.get(str(note_type), statuses.get("default", [])))
            if expected_statuses and "status" in fm and fm.get("status") not in expected_statuses:
                self.add(
                    "error",
                    "FRONTMATTER_STATUS",
                    note.relative,
                    f"status must be one of {sorted(expected_statuses)}",
                    note.key_lines.get("status"),
                )
            if "tags" in rules.get("required_fields", []) and not isinstance(fm.get("tags"), list):
                self.add(
                    "error",
                    "FRONTMATTER_TAGS",
                    note.relative,
                    "tags must be a YAML list",
                    note.key_lines.get("tags"),
                )
            for field in rules.get("date_fields", []):
                if field in fm and not valid_date(fm.get(field)):
                    self.add(
                        "error",
                        "FRONTMATTER_DATE",
                        note.relative,
                        f"{field} must be a valid YYYY-MM-DD date",
                        note.key_lines.get(field),
                    )
            for field in type_fields.get(str(note_type), ()):
                if field not in fm:
                    self.add(
                        "error",
                        "TYPE_FIELD",
                        note.relative,
                        f"{note_type} notes require '{field}'",
                    )
            if note_type == "project" and "project" in note_types:
                self._validate_project(note)
            elif note_type == "read-later" and "read_later" in rules:
                self._validate_read_later(note)
            elif note_type == "place" and "place" in note_types:
                self._validate_place(note)
            elif note_type in rules.get("dated_types", []):
                self._validate_dated(note)
            self._warn_inbox(note)

    def _validate_dated(self, note: ParsedMarkdown) -> None:
        value = note.frontmatter.get("date")
        month_ok = self.rules.get("dated_month_ok", False)
        valid = valid_date(value) or (month_ok and valid_month(value))
        if "date" in note.frontmatter and not valid:
            wanted = "YYYY-MM-DD or YYYY-MM" if month_ok else "YYYY-MM-DD"
            self.add(
                "error",
                "FRONTMATTER_DATE",
                note.relative,
                f"date must be a valid {wanted} date",
                note.key_lines.get("date"),
            )
        elif valid and not Path(note.relative).name.startswith(f"{value}-"):
            self.add(
                "error",
                "DATED_FILENAME",
                note.relative,
                "dated notes are named after their date: YYYY-MM-DD-slug.md (or YYYY-MM-slug.md)",
            )

    def _validate_project(self, note: ParsedMarkdown) -> None:
        fm = note.frontmatter
        blank = [field for field in ("goal", "due") if field in fm and not meaningful(fm[field])]
        open_tasks = any(match.group(1).strip() for match in TASK_RE.finditer(note.body))
        if blank or not open_tasks:
            details = []
            if blank:
                details.append(f"blank {', '.join(blank)}")
            if not open_tasks:
                details.append("no task content")
            self.add(
                "warning",
                "PROJECT_SHELL",
                note.relative,
                "project shell: " + "; ".join(details),
            )
        due = fm.get("due")
        if meaningful(due) and not valid_date(due):
            self.add(
                "error",
                "PROJECT_DUE",
                note.relative,
                "project due must be blank or a valid YYYY-MM-DD date",
                note.key_lines.get("due"),
            )

    def _validate_read_later(self, note: ParsedMarkdown) -> None:
        fm = note.frontmatter
        settings = self.rules["read_later"]
        priorities = set(settings.get("priorities", []))
        if priorities and fm.get("priority") not in priorities:
            self.add(
                "error",
                "READ_LATER_PRIORITY",
                note.relative,
                f"priority must be one of {sorted(priorities)}",
                note.key_lines.get("priority"),
            )
        added = fm.get("added")
        if "added" in fm and not valid_date(added):
            self.add(
                "error",
                "READ_LATER_ADDED",
                note.relative,
                "added must be a valid YYYY-MM-DD date",
                note.key_lines.get("added"),
            )
        stale_days = settings.get("stale_days")
        if stale_days is not None and fm.get("status") == "queued" and valid_date(added):
            age = (self.today - dt.date.fromisoformat(added)).days
            if age > stale_days:
                self.add(
                    "warning",
                    "READ_LATER_STALE",
                    note.relative,
                    f"queued read-later item is {age} days old",
                )

    def _validate_place(self, note: ParsedMarkdown) -> None:
        fm = note.frontmatter
        location = fm.get("location")
        if "location" in fm and (
            not isinstance(location, list)
            or len(location) != 2
            or not all(re.fullmatch(r"-?\d+(?:\.\d+)?", str(item)) for item in location)
        ):
            self.add(
                "error",
                "PLACE_LOCATION",
                note.relative,
                "location must contain numeric [latitude, longitude]",
                note.key_lines.get("location"),
            )
        visited = fm.get("visited")
        if meaningful(visited) and not valid_date(visited):
            self.add(
                "error",
                "PLACE_VISITED",
                note.relative,
                "visited must be blank or a valid YYYY-MM-DD date",
                note.key_lines.get("visited"),
            )

    def _warn_inbox(self, note: ParsedMarkdown) -> None:
        inbox = self.rules.get("inbox")
        if not inbox:
            return
        if not note.relative.startswith(inbox["folder"]) or any(
            part in note.relative for part in inbox.get("skip", [])
        ):
            return
        created = note.frontmatter.get("created")
        if valid_date(created):
            age = (self.today - dt.date.fromisoformat(created)).days
            if age > inbox["max_age_days"]:
                self.add("warning", "INBOX_AGE", note.relative, f"inbox note is {age} days old")
        max_kib, max_lines = inbox["max_kib"], inbox["max_lines"]
        if note.path.stat().st_size > max_kib * 1024 or len(note.body.splitlines()) > max_lines:
            self.add(
                "warning",
                "INBOX_SIZE",
                note.relative,
                f"inbox note exceeds {max_kib} KiB or {max_lines} body lines",
            )

    def _validate_wikilinks(self) -> None:
        if not self.rules.get("wikilinks", True):
            return
        markdown_paths = [note.path for note in self.notes]
        markdown_paths.extend(
            path for path in self.root.rglob("README.md") if ".git" not in path.parts
        )
        attachments_dir = self.root / self.rules.get("attachments", "attachments")
        attachments = [
            path
            for path in attachments_dir.rglob("*")
            if path.is_file()
        ] if attachments_dir.exists() else []
        candidates = markdown_paths + attachments
        for note in self.notes:
            visible = self._mask_non_rendered_wikilinks(note.text)
            for match in WIKILINK_RE.finditer(visible):
                raw = match.group(1).strip()
                target = raw.split("|", 1)[0].split("#", 1)[0].strip()
                if not target:
                    continue
                line = visible.count("\n", 0, match.start()) + 1
                if not self._resolve_link(target, note.path, candidates):
                    self.add(
                        "error",
                        "WIKILINK_BROKEN",
                        note.relative,
                        f"cannot resolve Obsidian wikilink '[[{raw}]]'",
                        line,
                        raw,
                    )

    @staticmethod
    def _mask_non_rendered_wikilinks(text: str) -> str:
        def mask(match: re.Match[str]) -> str:
            return re.sub(r"[^\n]", " ", match.group(0))

        text = re.sub(r"<!--.*?-->", mask, text, flags=re.DOTALL)
        return re.sub(r"(?<!`)`[^`\n]+`(?!`)", mask, text)

    def _resolve_link(self, target: str, source: Path, candidates: Iterable[Path]) -> bool:
        normalized = target.lstrip("/").replace("\\", "/")
        has_suffix = PurePosixPath(normalized).suffix != ""
        if "/" in normalized:
            possibilities = [source.parent / normalized, self.root / normalized]
            if not has_suffix:
                possibilities.extend(
                    [source.parent / f"{normalized}.md", self.root / f"{normalized}.md"]
                )
            return any(path.is_file() for path in possibilities)

        target_name = normalized if has_suffix else f"{normalized}.md"
        matches = [path for path in candidates if path.name.casefold() == target_name.casefold()]
        if not matches:
            return False
        if len(matches) == 1:
            return True
        source_parts = source.parent.relative_to(self.root).parts

        def rank(path: Path) -> tuple[int, int]:
            parts = path.parent.relative_to(self.root).parts
            shared = 0
            for left, right in zip(source_parts, parts):
                if left != right:
                    break
                shared += 1
            return shared, -len(path.relative_to(self.root).parts)

        ranked = sorted((rank(path), path) for path in matches)
        return len(ranked) == 1 or ranked[-1][0] != ranked[-2][0]

    def _validate_tasks_and_retention(self) -> None:
        retention = self.rules.get("retention_tags")
        for note in self.notes:
            for match in TASK_RE.finditer(note.body):
                task = match.group(1).strip()
                if "🔁" in task and not DATE_ANCHOR_RE.search(task):
                    line = note.text.count("\n", 0, note.text.find(match.group(0))) + 1
                    self.add(
                        "error",
                        "RECURRING_DATE_ANCHOR",
                        note.relative,
                        "recurring task needs a due, scheduled, or start date anchor",
                        line,
                        task,
                    )
            if not retention:
                continue
            tags = {str(tag).lstrip("#").casefold() for tag in note.frontmatter.get("tags", [])} \
                if isinstance(note.frontmatter.get("tags"), list) else set()
            has_retrieval = (
                re.search(r"^#{1,6}\s+.*flashcards?", note.body, flags=re.IGNORECASE | re.MULTILINE)
                or re.search(r"\bQuestion::\S", note.body)
                or re.search(r"==[^=\n]+==", note.body)
            )
            if has_retrieval and not (set(retention) & tags):
                self.add(
                    "warning",
                    "RETENTION_TAG",
                    note.relative,
                    f"retrieval material should carry a {' or '.join(retention)} frontmatter tag",
                )

    def _validate_workflows(self) -> None:
        skills = self.rules.get("skills")
        if not skills:
            return
        skill_root = self.root / skills.get("root", ".agents/skills")
        for skill_name in skills.get("required", []):
            skill = skill_root / skill_name / "SKILL.md"
            if not skill.is_file():
                self.add(
                    "error",
                    "WORKFLOW_SKILL_MISSING",
                    self._relative(skill),
                    f"missing canonical '{skill_name}' skill",
                )
        if skill_root.exists():
            for skill in sorted(skill_root.glob("*/SKILL.md")):
                parsed = read_markdown(skill, self.root)
                directory_name = skill.parent.name
                if parsed.frontmatter.get("name") != directory_name:
                    self.add(
                        "error",
                        "SKILL_NAME",
                        parsed.relative,
                        "skill name must match its directory",
                        parsed.key_lines.get("name"),
                    )
                if not meaningful(parsed.frontmatter.get("description")):
                    self.add(
                        "error",
                        "SKILL_DESCRIPTION",
                        parsed.relative,
                        "skill requires a non-empty description",
                        parsed.key_lines.get("description"),
                    )
        for skill_name, reference in skills.get("references", {}).items():
            skill_file = skill_root / skill_name / "SKILL.md"
            reference_file = skill_root / skill_name / reference
            if not skill_file.is_file():
                continue
            rule = f"{skill_name.upper().replace('-', '_')}_{Path(reference).stem.upper()}"
            if not reference_file.is_file():
                self.add(
                    "error",
                    f"{rule}_MISSING",
                    self._relative(reference_file),
                    f"{skill_name} skill requires its {reference} reference",
                )
            elif f"[{reference}]({reference})" not in skill_file.read_text(encoding="utf-8"):
                self.add(
                    "error",
                    f"{rule}_LINK",
                    self._relative(skill_file),
                    f"{skill_name} skill must link {reference}",
                )

    def _validate_bootstrap(self) -> None:
        for relative in self.rules.get("required_files", []):
            if not (self.root / relative).is_file():
                self.add("error", "BOOTSTRAP_MISSING", relative, "required bootstrap file is missing")

    def _validate_plugins(self) -> None:
        if not self.rules.get("obsidian_plugins"):
            return
        declaration = self.root / ".obsidian" / "community-plugins.json"
        if not declaration.is_file():
            self.add(
                "error",
                "PLUGIN_DECLARATION",
                self._relative(declaration),
                "community plugin declaration is missing",
            )
            return
        try:
            declared_value = json.loads(declaration.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self.add("error", "PLUGIN_DECLARATION", self._relative(declaration), str(exc))
            return
        if not isinstance(declared_value, list) or not all(isinstance(item, str) for item in declared_value):
            self.add(
                "error",
                "PLUGIN_DECLARATION",
                self._relative(declaration),
                "community-plugins.json must be a list of plugin IDs",
            )
            return
        declared = set(declared_value)
        installed: set[str] = set()
        plugin_root = self.root / ".obsidian" / "plugins"
        for manifest in sorted(plugin_root.glob("*/manifest.json")):
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                self.add("error", "PLUGIN_MANIFEST", self._relative(manifest), str(exc))
                continue
            plugin_id = data.get("id")
            if not isinstance(plugin_id, str) or not plugin_id:
                self.add(
                    "error",
                    "PLUGIN_MANIFEST",
                    self._relative(manifest),
                    "manifest requires an id",
                )
                continue
            if plugin_id != manifest.parent.name:
                self.add(
                    "error",
                    "PLUGIN_MANIFEST",
                    self._relative(manifest),
                    f"manifest id '{plugin_id}' does not match directory '{manifest.parent.name}'",
                )
            installed.add(plugin_id)
        for plugin_id in sorted(declared - installed):
            self.add(
                "error",
                "PLUGIN_ENABLED_NOT_INSTALLED",
                ".obsidian/community-plugins.json",
                f"enabled plugin has no installed manifest: {plugin_id}",
                subject=plugin_id,
            )

    def _validate_operator_docs(self) -> None:
        settings = self.rules.get("operator_guide")
        if not settings:
            return
        guide = self.root / settings["path"]
        diagram_dir = guide.parent / settings.get("diagram_folder", "diagram")
        if not guide.is_file():
            self.add(
                "warning",
                "DOCS_DEFERRED",
                self._relative(guide),
                "operator guide and diagram checks are deferred until the documentation phase",
            )
            return
        parsed = read_markdown(guide, self.root)
        lowered = parsed.body.casefold()
        for section in settings.get("sections", []):
            if section not in lowered:
                self.add(
                    "error",
                    "OPERATOR_GUIDE_SECTION",
                    parsed.relative,
                    f"operator guide is missing expected coverage: {section}",
                )
        for name in settings.get("diagrams", []):
            asset = diagram_dir / name
            if not asset.is_file():
                self.add(
                    "error",
                    "DIAGRAM_MISSING",
                    self._relative(asset),
                    "required operator-guide diagram asset is missing",
                )
            expected_embed = f"![[{settings.get('diagram_folder', 'diagram')}/{name}]]"
            if expected_embed not in parsed.body:
                self.add(
                    "error",
                    "DIAGRAM_EMBED",
                    parsed.relative,
                    f"operator guide must embed {expected_embed}",
                )

    def _validate_tend_state(self) -> None:
        marker = self.rules.get("tend_state")
        if not marker:
            return
        state_path = self.root / marker
        if not state_path.is_file():
            self.add(
                "error",
                "TEND_STATE",
                self._relative(state_path),
                "durable tend run marker is missing",
            )
            return
        data: dict[str, Any] = {}
        for number, raw in enumerate(state_path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            match = re.match(r"^([a-z_]+):\s*(.*)$", raw)
            if not match:
                self.add("error", "TEND_STATE", self._relative(state_path), "malformed marker", number)
                continue
            data[match.group(1)] = scalar(match.group(2))
        if data.get("version") != "1":
            self.add(
                "error",
                "TEND_STATE",
                self._relative(state_path),
                "marker version must be 1",
            )
        last_run, scope = data.get("last_run"), data.get("scope")
        if not meaningful(last_run) and not meaningful(scope):
            self.add(
                "warning",
                "TEND_NEVER_RUN",
                self._relative(state_path),
                "no completed tend run has been recorded yet",
            )
            return
        if not meaningful(last_run) or not meaningful(scope):
            self.add(
                "error",
                "TEND_STATE",
                self._relative(state_path),
                "last_run and scope must either both be blank or both be set",
            )
            return
        if not isinstance(last_run, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", last_run
        ):
            self.add(
                "error",
                "TEND_STATE",
                self._relative(state_path),
                "last_run must be an ISO-8601 UTC timestamp ending in Z",
            )

    def _validate_baseline_usage(self) -> None:
        for index, entry in enumerate(self.baseline):
            if index in self.used_baseline:
                continue
            self.add(
                "warning",
                "BASELINE_STALE",
                entry.get("path", self._relative(self.baseline_path)),
                f"migration baseline entry no longer matches: {entry.get('rule', 'unknown')}",
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root (default: current folder)")
    parser.add_argument("--rules", type=Path, help=f"rules file (default: <root>/{DEFAULT_RULES_FILE})")
    parser.add_argument("--today", type=dt.date.fromisoformat, help="override today for repeatable checks")
    parser.add_argument("--baseline", type=Path, help="accepted migration-debt baseline (default: the rules' baseline)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    rules_path = args.rules or root / DEFAULT_RULES_FILE
    if not rules_path.is_absolute():
        rules_path = root / rules_path
    if not rules_path.is_file():
        print(f"vault-validator: no rules file at {rules_path}", file=sys.stderr)
        return 2
    baseline = args.baseline
    if baseline and not baseline.is_absolute():
        baseline = root / baseline
    validator = VaultValidator(root, rules=load_rules(rules_path), today=args.today, baseline_path=baseline)
    findings = validator.run()
    for finding in findings:
        print(finding.display())
    errors = sum(item.severity == "error" for item in findings)
    warnings = sum(item.severity == "warning" for item in findings)
    print(f"\nVault validation: {errors} error(s), {warnings} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
