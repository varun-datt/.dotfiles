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
EDITORS = {"sed", "gsed", "perl"}
IN_PLACE = re.compile(r"^-[A-Za-z]*i|^--in-place")
CHECKS = {"tsc", "oxlint", "eslint", "vitest", "playwright", "stryker"}
NPM_CHECKS = re.compile(r"^(?:check|lint|typecheck|test\S*|e2e|mutate)$")
WRAPPERS = {"npx", "queue.zsh", "time", "timeout"}
CUTTERS = {"head", "tail"}
REDIRECT = re.compile(r"\d?>&\d")


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


def base(word):
    return word.rsplit("/", 1)[-1]


def commands(text):
    out, cur = [], []
    for t in tokens(REDIRECT.sub(" ", text)):
        if t in OPS:
            out.append((cur, t))
            cur = []
        else:
            cur.append(t)
    out.append((cur, None))
    return out


def is_check(words):
    while words and (re.match(r"^[A-Za-z_]\w*=", words[0]) or base(words[0]) in WRAPPERS
                     or (words[0].isdigit() and len(words) > 1)):
        words = words[1:]
    if not words:
        return False
    exe = base(words[0])
    if exe in CHECKS:
        return True
    return exe in {"npm", "pnpm", "yarn"} and len(words) > 2 and words[1] == "run" and bool(NPM_CHECKS.match(words[2]))


def other_problem(command):
    try:
        cmds = commands(command)
    except ValueError:
        return None
    for i, (words, op) in enumerate(cmds):
        plain = [w for w in words if not re.match(r"^[A-Za-z_]\w*=", w)]
        if plain and base(plain[0]) in EDITORS and any(IN_PLACE.match(w) for w in plain[1:]):
            return (f"{base(plain[0])} edits a file in place from the terminal. Edit files with the edit tools "
                    "(user rule: never edit a file by running terminal commands). To prove a test can fail, follow the "
                    "software-testing skill's references/mutation-checks.md: patch at runtime or edit a temporary copy.")
        if op in ("|", "|&") and i + 1 < len(cmds) and cmds[i + 1][0] and base(cmds[i + 1][0][0]) in CUTTERS \
                and is_check(words):
            return (f"a check's output is cut with {base(cmds[i + 1][0][0])}, which can hide its failures and "
                    "its exit code. Send the output to a file and read that file's summary lines.")
    return None


def deny(reason):
    return {"permissionDecision": "deny", "permissionDecisionReason": reason,
            "hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def decide(event):
    name = event.get("toolName") or event.get("tool_name") or ""
    if not TERMINAL.search(name):
        return {}
    args = event.get("toolArgs", event.get("tool_input", {}))
    if isinstance(args, str):
        args = json.loads(args)
    command = (args.get("command") or "") if isinstance(args, dict) else ""
    other = other_problem(command)
    if other:
        return deny(other)
    why = problem(command)
    if not why:
        return {}
    gate = GATE.search(command).group(1)
    return deny(f"Gated step: git {gate} is chained so that {why}. Run the step it depends on as its own command, "
                f"read its exit code, then run git {gate} (user memory: never chain a gated step with ; or after a pipe).")


def main():
    try:
        out = decide(json.load(sys.stdin))
    except Exception:
        out = {}
    sys.stdout.write(json.dumps(out))


if __name__ == "__main__":
    main()
