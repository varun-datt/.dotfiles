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
45 minutes gets a warning, and the exit code is unchanged. So does each number of 3 or more digits, percentage
or "N of M" count in the GOAL, CASES THE ORCHESTRATOR KNOWS or FACTS TO VERIFY section of a worker or fix-round
brief with no source on the same line or bullet: a command in backticks (a number alone in backticks is not one), a
file:line, a commit id, a URL or a dated owner ruling. Years, dates, times, versions such as 10.1.1 or v1.105, and
numbers inside paths or URLs are not claims; a rate such as 994/s is.

A fix round (kind "fix") fails unless it lists numbered findings under a FIX THESE line and, under a WHY NOW line,
gives each finding one line "N HARM: <what the owner loses if it merges>" or "N DEPENDS: <the planned item that
builds on it>" (owner, 2026-11-02: a fix round must earn its place; other findings go to the tech-debt list).

Any prompt naming a commit it relies on ("fixed in <commit>", "after <commit>", either with "commit" before the id,
or a "RELIES ON: <commit> ..." line; an id is 7 to 40 hex characters, all digits or all letters included)
fails unless the commit is an ancestor of HEAD of --repo (the worktree), or of main in the current folder's
repository when --repo is not given.

With --repo, each open row of DIR/docs/tech-debt.md on a path the prompt names (a backticked token, or a
word inside a fenced block, that is an existing file or folder relative to DIR) whose TD-<n> id the
prompt does not mention gets a warning with the line `debt.py for-files` prints; the exit code is unchanged.
DIR itself (`.` or its absolute path) is not a named path, and a path outside DIR is ignored. Options may
come before, between or after the prompt files.

The kind comes from --kind, else from the prompt's first line outside comments and code blocks:
the reviewer, research or worker preamble's opening. A worker prompt with a line that starts
"THIS IS A FIX ROUND" before its first "TASK:" line is a fix round. Anything else is "other".
"""
import argparse
import json
import os
import re
import subprocess
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


def hot_spot_problem(lines):
    """The router's strongest-model rule reads RISK: host-state, so a brief naming the file must say yes or none."""
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "routes.json"),
                  encoding="utf-8") as f:
            floor = next((x for x in json.load(f)["floors"] if "text" in x["when"]), None)
    except (OSError, ValueError, KeyError):
        return None
    if not floor:
        return None
    start = next((i for i, line in enumerate(lines) if line.startswith("TASK:")), 0)
    named = next((n for n, line in enumerate(lines, 1) if n > start and re.search(floor["when"]["text"], line)), None)
    risk = next((line for line in lines if line.startswith("RISK:")), "")
    if named and not re.search(r"\bhost-state\b", risk):
        return (f"line {named} names {floor['when']['text'].replace(chr(92), '')}: say on the RISK line "
                f"\"host-state (what changes)\" or \"host-state none (why)\", so the router can pick the model")
    return None


def brief_problems(text):
    lines = brief_lines(text)
    found = [f"line {n}: MUST {num} has no SHALL: write it as \"WHEN <event or state>, <part> SHALL <response>\""
             for num, n, body in must_items(lines) if not re.search(r"\bSHALL\b", body)]
    found += [p for p in (field_problem(outside_fences(lines), f, "name it, or say \"none\" and why") for f in BRIEF_FIELDS) if p]
    found += [p for p in (hot_spot_problem(lines),) if p]
    return found


WHY_NOW = "WHY NOW"
WHY_LINE = re.compile(r"^\s*(\d+)[.)]?\s+(HARM|DEPENDS):(.*)$")
WHY_HOW = ("write `N HARM: <what the owner loses if it merges>` or `N DEPENDS: <the planned item (id) that builds on "
           "it>`; a finding that meets neither goes to the tech-debt list (owner, 2026-11-02)")


def why_now_problems(text):
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    import reviewprep
    lines = brief_lines(text)
    numbers = [num for num, *_ in reviewprep.findings("\n".join(lines))]
    if not numbers:
        return ["no numbered findings under a FIX THESE line: a fix round fixes named findings"]
    body = list(outside_fences(lines))
    start = next((i for i, (_, line) in enumerate(body) if line.startswith(WHY_NOW)), None)
    if start is None:
        return [f"no WHY NOW section: for each finding, {WHY_HOW}"]
    found, given = [], set()
    for n, line in body[start + 1:]:
        m = WHY_LINE.match(line)
        if not m:
            if line.strip() and not line[0].isspace() and (HEADING.match(line) or line.rstrip().endswith(":")):
                break
            continue
        num = m.group(1)
        given.add(num)
        if num not in numbers:
            found.append(f"line {n}: WHY NOW {num} names no finding {num} under FIX THESE")
        elif bare(m.group(3)) in EMPTY:
            found.append(f"line {n}: WHY NOW {num} is empty: {WHY_HOW}")
    found += [f"finding {num} has no WHY NOW line: {WHY_HOW}" for num in numbers if num not in given]
    return found


def warnings(text, kind=None):
    kind = kind or prompt_kind(text)
    if kind not in ("build", "fix"):
        return []
    found = number_warnings(text)
    m = re.search(r"^TIME BUDGET:\s*(\d+)", "\n".join(brief_lines(text)), re.M)
    if kind == "build" and m and int(m.group(1)) > SPLIT_MINUTES:
        found.insert(0, f"TIME BUDGET of {m.group(1)} minutes is over {SPLIT_MINUTES}: split an item expected over {SPLIT_MINUTES} minutes into two (SKILL.md, Start)")
    return found


CLAIM_SECTIONS = ("GOAL", "CASES THE ORCHESTRATOR KNOWS", "FACTS TO VERIFY")
BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")
FILE_LINE = r"(?<![\w./~-])(?=[\w./~-]*[A-Za-z])[\w./~-]+:\d+(?:-\d+)?"
COMMIT = r"\b(?=[0-9a-fA-F]*\d)(?=[0-9a-fA-F]*[a-fA-F])[0-9a-fA-F]{7,40}\b"
DATE = r"\b\d{4}-\d{2}-\d{2}\b"
SOURCE = re.compile("|".join((r"`(?![\d.,%\s]*`)[^`\n]+`", FILE_LINE, COMMIT, r"https?://\S+",
                              rf"\b(?:owner|ruled|ruling)\b[^\n]{{0,40}}?{DATE}", rf"{DATE}[^\n]{{0,15}}?\bowner\b")), re.I)
NOT_A_CLAIM = re.compile("|".join((r"https?://\S+", FILE_LINE, r"(?<!\S)(?![(\[\"'`]?\d[\d.,]*/)\S*/\S*", COMMIT, DATE,
                                   r"\b\d{1,2}:\d{2}\b", r"\bv\d+(?:\.\d+)*\b", r"\b\d+(?:\.\d+){2,}\b")))
CLAIM = re.compile(r"\b\d+(?:\.\d+)?\s?%|\b\d+ of \d+\b|\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b|\b\d{3,}(?:\.\d+)?\b")
YEAR = re.compile(r"^(?:19|20)\d{2}$")


def claim_units(text):
    """(line, section, text) for each line or bullet, with its indented continuation lines, in the claim sections."""
    units, section = [], None
    for n, line in outside_fences(brief_lines(text)):
        if HEADING.match(line):
            section = next((s for s in CLAIM_SECTIONS if line == s or line.startswith((s + ":", s + " ", s + "("))), None)
        if section is None or not line.strip():
            continue
        if units and units[-1][1] == section and line[:1].isspace() and not BULLET.match(line):
            units[-1][2] += " " + line.strip()
        else:
            units.append([n, section, line])
    return units


def number_warnings(text):
    found = []
    for n, section, unit in claim_units(text):
        if SOURCE.search(unit):
            continue
        masked = NOT_A_CLAIM.sub(lambda m: " " * len(m.group()), unit)
        for c in dict.fromkeys(m.group() for m in CLAIM.finditer(masked) if not YEAR.match(m.group())):
            found.append(f"line {n}: {section}: \"{c}\" has no source beside it: name the command (in backticks) whose "
                         "output gave it, or a file:line, commit, URL or dated owner ruling (task-body.md)")
    return found


RELIES = re.compile(r"(?i:\bfixed in|\bafter)\s+(?:(?i:commit)\s+)?`?([0-9a-fA-F]{7,40})\b`?")
HEX = re.compile(r"\b[0-9a-fA-F]{7,40}\b")


def relied_on(text):
    named = []
    for n, line in outside_fences(brief_lines(text)):
        ids = HEX.findall(line[len("RELIES ON:"):]) if line.startswith("RELIES ON:") else RELIES.findall(line)
        named += [(n, c) for c in ids if (n, c) not in named]
    return named


def relies_problems(text, repo=None):
    """A brief that names a commit it relies on is refused unless that commit is in the worktree's HEAD (--repo), or
    in main of the current folder's repository when no worktree is given."""
    named = relied_on(text)
    if not named:
        return []
    where, ref = (repo, "HEAD") if repo else (os.getcwd(), "main")

    def git(*args):
        return subprocess.run(["git", "-C", where, *args], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if git("rev-parse", "--verify", "--quiet", ref + "^{commit}").returncode:
        return [f"line {n}: relies on {c}, but {ref} of {where} cannot be read: pass --repo <worktree>" for n, c in named]
    found = []
    for n, c in named:
        if git("rev-parse", "--verify", "--quiet", c + "^{commit}").returncode:
            found.append(f"line {n}: relies on {c}, which the repository at {where} does not know: commit the fix "
                         "first, or correct the id")
        elif git("merge-base", "--is-ancestor", c, ref).returncode:
            found.append(f"line {n}: relies on {c}, which is not in {ref} of {where}: merge the fix into it first")
    return found


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
    import debt
    paths = named_paths(text, repo)
    if not paths:
        return []
    try:
        rows = debt.rows_for_files(repo, paths)
    except (debt.Refused, OSError, ValueError) as e:
        return [f"{debt.REGISTER} could not be read, so its open rows were not checked: {debt.one_line(e)}"]
    visible = "\n".join(brief_lines(text))
    return [f"{r['Id']} is open on {r['File']}, which the brief names, and the brief does not name the row: "
            f"paste it under the TECH DEBT line and fix it, or say why not: {debt.for_files_line(repo, r)}"
            for r in rows if not re.search(rf"\b{r['Id']}(?!\d)", visible)]


def problems(text, kind=None, repo=None):
    visible = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    visible = re.sub(r"`[^`\n]*`", "", visible)
    found = [f"unfilled placeholder {m}" for m in sorted(set(re.findall(r"\{\{[^{}\n]+\}\}", visible)))]
    found += relies_problems(text, repo)
    kind = kind or prompt_kind(text)
    if WORKER in text or kind in ("build", "fix"):
        lines = list(enumerate(brief_lines(text), 1))
        found += [p for p in (field_problem(lines, "REUSE CHECK", "name it, or say why none is needed"),
                              field_problem(lines, "ALLOWED DEPENDENCIES", "name them, or say \"none\"", True)) if p]
    if kind == "build":
        found += brief_problems(text)
    if kind == "fix":
        found += why_now_problems(text)
    return found


def folder(value):
    if not os.path.isdir(value):
        raise argparse.ArgumentTypeError("--repo must name a folder")
    return os.path.abspath(value)


def parser():
    ap = argparse.ArgumentParser(prog="brief.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("check",))
    ap.add_argument("--kind", choices=KINDS)
    ap.add_argument("--repo", type=folder)
    ap.add_argument("prompts", nargs="+", metavar="prompt.md")
    return ap


def main(argv=None):
    try:
        args = parser().parse_intermixed_args(argv)
    except SystemExit as e:
        return e.code
    kind, repo = args.kind, args.repo
    failed = False
    for path in args.prompts:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        found = problems(text, kind, repo)
        for w in warnings(text, kind) + (debt_warnings(text, repo) if repo else []):
            print(f"{path}: warning: {w}", file=sys.stderr)
        for p in found:
            print(f"{path}: {p}", file=sys.stderr)
        failed = failed or bool(found)
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
