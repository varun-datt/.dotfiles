#!/usr/bin/env python3
# preToolUse hook: an agent's npx fails at once on a package the project lacks, instead of prompting or installing it.
import json
import re
import sys

TERMINAL = re.compile(r"terminal|bash|shell|run_?command", re.I)
OPS = ("&&", "||", ";", "|", "(", "{", "\n", "&")
WRAPPER = re.compile(r"^(?:\S*/)?(?:queue\.zsh|timeout|gtimeout|time|nice|env|caffeinate)$"
                     r"|^[A-Za-z_]\w*=\S*$|^-\S+$|^\d+[smh]?$")
SETTING = "env npm_config_yes=false "


def npx_words(command):
    quote, i, n = None, 0, len(command)
    while i < n:
        c = command[i]
        if quote:
            if c == "\\" and quote == '"':
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "'\"":
            quote = c
        elif c == "\\":
            i += 2
            continue
        elif command.startswith("<<", i):
            return
        elif (command.startswith("npx", i) and (i == 0 or command[i - 1] in " \t\n;&|({")
              and (i + 3 == n or command[i + 3] in " \t\n")):
            yield i
        i += 1


def at_command_start(command, i):
    before = command[:i]
    cut = max((before.rfind(op) + len(op) for op in OPS if before.rfind(op) >= 0), default=0)
    return all(WRAPPER.match(w) for w in before[cut:].split())


def rewrite(command):
    if "npm_config_yes" in command:
        return command
    for i in sorted((i for i in npx_words(command) if at_command_start(command, i)), reverse=True):
        command = command[:i] + SETTING + command[i:]
    return command


def decide(event):
    name = event.get("toolName") or event.get("tool_name") or ""
    if not TERMINAL.search(name):
        return {}
    args = event.get("toolArgs", event.get("tool_input", {}))
    if isinstance(args, str):
        args = json.loads(args)
    if not isinstance(args, dict) or not isinstance(args.get("command"), str):
        return {}
    new = rewrite(args["command"])
    if new == args["command"]:
        return {}
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "permissionDecisionReason": "npx may not install a missing package",
                                   "updatedInput": {**args, "command": new}}}


def main():
    try:
        out = decide(json.load(sys.stdin))
    except Exception:
        out = {}
    sys.stdout.write(json.dumps(out))


if __name__ == "__main__":
    main()
