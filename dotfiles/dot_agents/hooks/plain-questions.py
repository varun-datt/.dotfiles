#!/usr/bin/env python3
# preToolUse hook: refuses a question to the owner whose text holds code formatting, command names or option flags.
import json
import re
import sys

ASK = re.compile(r"ask.?questions?|ask_?user", re.I)
FOUND = [
    ("code formatting", re.compile(r"`[^`\n]+`")),
    ("an option flag", re.compile(r"(?<![\w-])--[a-z][\w-]*")),
    ("a script name", re.compile(r"\b[\w.-]+\.(?:py|zsh|sh|mjs|cjs)\b")),
    ("a command", re.compile(r"\b(?:npm|npx|pnpm|yarn)\s+[a-z][\w:-]*|\bgit\s+(?:merge|commit|push|pull|rebase|reset|"
                             r"checkout|switch|stash|log|diff|status|worktree)\b|\b(?:gh|az|chezmoi)\s+[a-z]")),
]


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings(v)


def decide(event):
    name = event.get("toolName") or event.get("tool_name") or ""
    if not ASK.search(name):
        return {}
    args = event.get("toolArgs", event.get("tool_input", {}))
    if isinstance(args, str):
        args = json.loads(args)
    hits = []
    for text in strings(args):
        for kind, pattern in FOUND:
            for m in pattern.finditer(text):
                hits.append(f"{kind} ({m.group(0)})")
    if not hits:
        return {}
    shown = "; ".join(dict.fromkeys(hits))[:600]
    reason = ("Plain words: this question holds " + shown + ". Rewrite it without code formatting, command names "
              "or option flags: say in plain words what each option does for the owner (user rule: asking me to decide).")
    return {"permissionDecision": "deny", "permissionDecisionReason": reason,
            "hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def main():
    try:
        out = decide(json.load(sys.stdin))
    except Exception:
        out = {}
    sys.stdout.write(json.dumps(out))


if __name__ == "__main__":
    main()
