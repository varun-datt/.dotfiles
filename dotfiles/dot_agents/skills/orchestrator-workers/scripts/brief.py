#!/usr/bin/env python3
"""Refuse a worker prompt that is not ready to launch.

Usage:
    python3 brief.py check <prompt.md> [<prompt.md> ...]

Fails (exit 2) when a prompt still holds a {{PLACEHOLDER}} outside an HTML comment or inline code,
or when a worker prompt (one built on preamble-worker.md) lacks a filled REUSE CHECK or ALLOWED
DEPENDENCIES line. REUSE CHECK names what was surveyed for reuse, or why none is needed; a bare
"none" is refused. ALLOWED DEPENDENCIES may be "none".

A worker brief (a worker prompt that is not a fix round) also fails when a numbered MUST line,
with any lines it wraps onto, has no "SHALL", or when its RISK, CASES THE ORCHESTRATOR KNOWS or
FACTS TO VERIFY line is missing or empty; each may say "none" with a reason, not "none" alone.
A worker brief whose TIME BUDGET is over 45 minutes gets a warning, and the exit code is unchanged.
"""
import re
import sys

WORKER = "You are a worker session"
FIX = "THIS IS A FIX ROUND"
REVIEWER = "You are a read-only reviewer"
EMPTY = {"", "none", "n/a", "na", "-", "tbd", "todo"}
BRIEF_FIELDS = ("RISK", "CASES THE ORCHESTRATOR KNOWS", "FACTS TO VERIFY")
HEADING = re.compile(r"^(?!WHEN\b|SHALL\b)[A-Z][A-Z ]{3,}(?=$|[:(])")
NUMBERED = re.compile(r"^\s*(\d+)[.)]\s")
SPLIT_MINUTES = 45


def is_worker_brief(text):
    return WORKER in text and FIX not in text and REVIEWER not in text


def brief_lines(text):
    return re.sub(r"<!--.*?-->", lambda m: "\n" * m.group().count("\n"), text, flags=re.S).split("\n")


def must_items(lines):
    items, inside = [], False
    for n, line in enumerate(lines, 1):
        if HEADING.match(line):
            inside = line.startswith("MUST")
            continue
        if not inside or not line.strip():
            continue
        m = NUMBERED.match(line)
        if m:
            items.append([m.group(1), n, line])
        elif items:
            items[-1][2] += " " + line
    return items


def brief_problems(text):
    lines = brief_lines(text)
    found = [f"line {n}: MUST {num} has no SHALL: write it as \"WHEN <event or state>, <part> SHALL <response>\""
             for num, n, body in must_items(lines) if not re.search(r"\bSHALL\b", body)]
    for field in BRIEF_FIELDS:
        hit = next(((n, line) for n, line in enumerate(lines, 1) if re.match(rf"{field}:", line)), None)
        if hit is None:
            found.append(f"no {field} line")
        elif hit[1][len(field) + 1:].strip().rstrip(".").lower() in EMPTY:
            found.append(f"line {hit[0]}: {field} is empty: name it, or say \"none\" and why")
    return found


def warnings(text):
    if not is_worker_brief(text):
        return []
    m = re.search(r"^TIME BUDGET:\s*(\d+)", "\n".join(brief_lines(text)), re.M)
    if m and int(m.group(1)) > SPLIT_MINUTES:
        return [f"TIME BUDGET of {m.group(1)} minutes is over {SPLIT_MINUTES}: split an item expected over {SPLIT_MINUTES} minutes into two (SKILL.md, Start)"]
    return []


def problems(text):
    visible = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    visible = re.sub(r"`[^`\n]*`", "", visible)
    found = [f"unfilled placeholder {m}" for m in sorted(set(re.findall(r"\{\{[^{}\n]+\}\}", visible)))]
    if WORKER in text:
        for field, bare_ok in (("REUSE CHECK", False), ("ALLOWED DEPENDENCIES", True)):
            m = re.search(rf"^{field}:[ \t]*(.*)$", visible, flags=re.M)
            value = m.group(1).strip().rstrip(".").lower() if m else None
            if value is None:
                found.append(f"no {field} line")
            elif value == "" or (value in EMPTY and not (bare_ok and value == "none")):
                found.append(f"{field} is empty: name it, or say why none is needed")
    if is_worker_brief(text):
        found += brief_problems(text)
    return found


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) < 2 or args[0] != "check":
        print(__doc__.strip(), file=sys.stderr)
        return 2
    failed = False
    for path in args[1:]:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        found = problems(text)
        for w in warnings(text):
            print(f"{path}: warning: {w}", file=sys.stderr)
        for p in found:
            print(f"{path}: {p}", file=sys.stderr)
        failed = failed or bool(found)
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
