#!/usr/bin/env python3
"""Refuse a worker prompt that is not ready to launch.

Usage:
    python3 brief.py check <prompt.md> [<prompt.md> ...]

Fails (exit 2) when a prompt still holds a {{PLACEHOLDER}} outside an HTML comment or inline code,
or when a worker prompt (one built on preamble-worker.md) lacks a filled REUSE CHECK or ALLOWED
DEPENDENCIES line. REUSE CHECK names what was surveyed for reuse, or why none is needed; a bare
"none" is refused. ALLOWED DEPENDENCIES may be "none".
"""
import re
import sys

WORKER = "You are a worker session"
EMPTY = {"", "none", "n/a", "na", "-", "tbd", "todo"}


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
    return found


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) < 2 or args[0] != "check":
        print(__doc__.strip(), file=sys.stderr)
        return 2
    failed = False
    for path in args[1:]:
        with open(path, encoding="utf-8") as f:
            found = problems(f.read())
        for p in found:
            print(f"{path}: {p}", file=sys.stderr)
        failed = failed or bool(found)
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
