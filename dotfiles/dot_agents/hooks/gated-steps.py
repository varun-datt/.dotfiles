#!/usr/bin/env python3
# preToolUse hook: refuses a terminal command that commits, merges or pushes after a step whose failure it cannot see.
import json
import re
import shlex
import sys

TERMINAL = re.compile(r"terminal|bash|shell|run_?command|powershell", re.I)
GATE = re.compile(r"(?:^|(?<=[\s;&|(]))(?:\S*/)?git(?:\s+-[Cc]\s+\S+)*\s+(commit|merge|push)\b")
HARMLESS = {"cd", "pushd", "popd", "clear", "true"}
OPS = {"&&", "||", ";", "|", "&", "|&", ";;", "\n"}


def tokens(text):
    lex = shlex.shlex(text.replace("\n", " ; "), posix=True, punctuation_chars=";&|")
    lex.whitespace_split = True
    return list(lex)


def problem(command):
    m = GATE.search(command)
    if not m:
        return None
    prefix = command[:m.start()]
    if not prefix.strip():
        return None
    if "pipefail" in prefix:
        return None
    try:
        toks = tokens(prefix)
    except ValueError:
        return "it could not be read safely"
    words, last_op, firsts, start = [], None, [], True
    for t in toks:
        if t in OPS:
            last_op = t
            words.append(t)
            start = True
        else:
            if start:
                firsts.append(t)
            start = False
    if last_op is None:
        return None
    if "|" in words or "|&" in words:
        return "a pipe before it hides the earlier step's exit code"
    if last_op == "&&":
        return None
    if all(f in HARMLESS for f in firsts):
        return None
    return f"it follows '{last_op}', so it runs even when the step before it fails"


def decide(event):
    name = event.get("toolName") or event.get("tool_name") or ""
    if not TERMINAL.search(name):
        return {}
    args = event.get("toolArgs", event.get("tool_input", {}))
    if isinstance(args, str):
        args = json.loads(args)
    command = (args.get("command") or "") if isinstance(args, dict) else ""
    why = problem(command)
    if not why:
        return {}
    gate = GATE.search(command).group(1)
    reason = (f"Gated step: git {gate} is chained so that {why}. Run the step it depends on as its own command, "
              f"read its exit code, then run git {gate} (user memory: never chain a gated step with ; or after a pipe).")
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
