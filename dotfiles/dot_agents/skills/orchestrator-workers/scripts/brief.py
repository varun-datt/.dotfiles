#!/usr/bin/env python3
"""Refuse a worker prompt that is not ready to launch.

Usage:
    python3 brief.py check [--kind build|fix|review|research|other] [--repo DIR] <prompt.md> [<prompt.md> ...]

Fails (exit 2) when a prompt still holds a {{PLACEHOLDER}} outside an HTML comment or inline code,
or when a worker prompt (one built on preamble-worker.md) lacks a filled REUSE CHECK or ALLOWED
DEPENDENCIES line. REUSE CHECK names what was surveyed for reuse, or why none is needed; a bare
"none" is refused. ALLOWED DEPENDENCIES may be "none".

A worker brief (kind "build") also fails when a top-level numbered MUST item, with the lines under
it, has no "SHALL", or when its RISK, CASES THE ORCHESTRATOR KNOWS or FACTS TO VERIFY line is
missing or empty; each may say "none" with a reason, not "none" alone. A bare "none" in backticks,
bold, italics or with trailing punctuation counts as alone. A worker brief whose TIME BUDGET is over
45 minutes gets a warning, and the exit code is unchanged.

With --repo, each open row of DIR/docs/tech-debt.md on a path the prompt names (a backticked token, or a
word inside a fenced block, that is an existing file or folder relative to DIR) whose TD-<n> id the
prompt does not mention gets a warning with the line `debt.py for-files` prints; the exit code is unchanged.

The kind comes from --kind, else from the prompt's first line outside comments and code blocks:
the reviewer, research or worker preamble's opening. A worker prompt with a line that starts
"THIS IS A FIX ROUND" before its first "TASK:" line is a fix round. Anything else is "other".
"""
import os
import re
import sys

WORKER = "You are a worker session"
FIX = "THIS IS A FIX ROUND"
REVIEWER = "You are a read-only reviewer"
RESEARCH = "You are a research worker"
KINDS = ("build", "fix", "review", "research", "other")
EMPTY = {"", "none", "n/a", "na", "-", "tbd", "todo"}
BRIEF_FIELDS = ("RISK", "CASES THE ORCHESTRATOR KNOWS", "FACTS TO VERIFY")
HEADING = re.compile(r"^(?!WHEN\b|SHALL\b)[A-Z][A-Z ]{3,}(?=$|[:(])")
TOP_NUMBERED = re.compile(r"^(\d+)[.)]\s")
FENCE = re.compile(r"^\s*(```|~~~)")
SPLIT_MINUTES = 45


def brief_lines(text):
    return re.sub(r"<!--.*?-->", lambda m: "\n" * m.group().count("\n"), text, flags=re.S).split("\n")


def outside_fences(lines):
    fenced = False
    for n, line in enumerate(lines, 1):
        if FENCE.match(line):
            fenced = not fenced
        elif not fenced:
            yield n, line


def prompt_kind(text):
    lines = list(outside_fences(brief_lines(text)))
    first = next((line for _, line in lines if line.strip()), "")
    if first.startswith(REVIEWER):
        return "review"
    if first.startswith(RESEARCH):
        return "research"
    if not first.startswith(WORKER):
        return "other"
    for _, line in lines:
        if line.startswith("TASK:"):
            break
        if line.startswith(FIX):
            return "fix"
    return "build"


def must_items(lines):
    items, inside = [], False
    for n, line in outside_fences(lines):
        if HEADING.match(line):
            inside = line.startswith("MUST")
            continue
        if not inside or not line.strip():
            continue
        m = TOP_NUMBERED.match(line)
        if m:
            items.append([m.group(1), n, line])
        elif items:
            items[-1][2] += " " + line
    return items


def bare(value):
    return re.sub(r"[`*_]", "", value).strip(" \t.,;:!-–—").lower()


def field_problem(numbered, field, hint, bare_none_ok=False):
    numbered = list(numbered)
    hit = next(((n, line) for n, line in numbered if line.startswith(field + ":")), None)
    if hit is None:
        near = next((n for n, line in numbered if re.search(rf"\b{field}\W*:", line)), None)
        return f"no {field} line" + (f": line {near} names it, but the field must start its own line" if near else "")
    value = bare(hit[1][len(field) + 1:])
    if value in EMPTY and not (bare_none_ok and value == "none"):
        return f"line {hit[0]}: {field} is empty: {hint}"
    return None


def brief_problems(text):
    lines = brief_lines(text)
    found = [f"line {n}: MUST {num} has no SHALL: write it as \"WHEN <event or state>, <part> SHALL <response>\""
             for num, n, body in must_items(lines) if not re.search(r"\bSHALL\b", body)]
    found += [p for p in (field_problem(outside_fences(lines), f, "name it, or say \"none\" and why") for f in BRIEF_FIELDS) if p]
    return found


def warnings(text, kind=None):
    if (kind or prompt_kind(text)) != "build":
        return []
    m = re.search(r"^TIME BUDGET:\s*(\d+)", "\n".join(brief_lines(text)), re.M)
    if m and int(m.group(1)) > SPLIT_MINUTES:
        return [f"TIME BUDGET of {m.group(1)} minutes is over {SPLIT_MINUTES}: split an item expected over {SPLIT_MINUTES} minutes into two (SKILL.md, Start)"]
    return []


TICKED = re.compile(r"`([^`\n]+)`")
LINE_SUFFIX = re.compile(r":\d+(?:-\d+)?$")


def named_paths(text, repo):
    lines = brief_lines(text)
    tokens = [t for line in lines for t in TICKED.findall(line)]
    inside = {n for n, _ in outside_fences(lines)}
    tokens += [w.strip("\"'(),;") for n, line in enumerate(lines, 1)
               if n not in inside and not FENCE.match(line) for w in line.split()]
    found = set()
    for t in tokens:
        t = LINE_SUFFIX.sub("", t.strip())
        if not t:
            continue
        if os.path.isabs(t):
            t = os.path.relpath(t, repo)
        norm = os.path.normpath(t)
        if norm == "." or norm == ".." or norm.startswith(".." + os.sep) or not os.path.exists(os.path.join(repo, norm)):
            continue
        found.add(norm)
    return sorted(found)


def debt_warnings(text, repo):
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    import argparse
    import debt
    paths = named_paths(text, repo)
    if not paths:
        return []
    try:
        rows = debt.cmd_for_files(argparse.Namespace(repo=repo, paths=paths))
    except (debt.Refused, OSError, ValueError) as e:
        return [f"{debt.REGISTER} could not be read, so its open rows were not checked: {debt.one_line(e)}"]
    visible = "\n".join(brief_lines(text))
    out = []
    for row in rows.splitlines():
        m = re.match(r"- (TD-\d+) .*?`([^`]*)`", row)
        if m and not re.search(rf"\b{m.group(1)}(?!\d)", visible):
            out.append(f"{m.group(1)} is open on {m.group(2)}, which the brief names, and the brief does not name the row: "
                       f"paste it under the TECH DEBT line and fix it, or say why not: {row}")
    return out


def problems(text, kind=None):
    visible = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    visible = re.sub(r"`[^`\n]*`", "", visible)
    found = [f"unfilled placeholder {m}" for m in sorted(set(re.findall(r"\{\{[^{}\n]+\}\}", visible)))]
    kind = kind or prompt_kind(text)
    if WORKER in text or kind in ("build", "fix"):
        lines = list(enumerate(brief_lines(text), 1))
        found += [p for p in (field_problem(lines, "REUSE CHECK", "name it, or say why none is needed"),
                              field_problem(lines, "ALLOWED DEPENDENCIES", "name them, or say \"none\"", True)) if p]
    if kind == "build":
        found += brief_problems(text)
    return found


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    kind = repo = None
    while len(args) >= 2 and args[0] == "check" and args[1] in ("--kind", "--repo"):
        flag, value = args[1], args[2] if len(args) > 2 else None
        args = args[:1] + args[3:]
        if flag == "--kind":
            kind = value
            if kind not in KINDS:
                print(f"brief.py: --kind must be one of {', '.join(KINDS)}", file=sys.stderr)
                return 2
        elif value is None or not os.path.isdir(value):
            print("brief.py: --repo must name a folder", file=sys.stderr)
            return 2
        else:
            repo = os.path.abspath(value)
    if len(args) < 2 or args[0] != "check":
        print(__doc__.strip(), file=sys.stderr)
        return 2
    failed = False
    for path in args[1:]:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        found = problems(text, kind)
        for w in warnings(text, kind) + (debt_warnings(text, repo) if repo else []):
            print(f"{path}: warning: {w}", file=sys.stderr)
        for p in found:
            print(f"{path}: {p}", file=sys.stderr)
        failed = failed or bool(found)
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
