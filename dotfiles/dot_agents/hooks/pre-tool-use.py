#!/usr/bin/env python3
# preToolUse hook: runs the plain-questions, gated-steps and npx-no-install checks in one process.
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), os.path.join(HERE, f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECKS = [load(name) for name in ("plain-questions", "question-rules", "gated-steps", "npx-no-install")]


def decide(event):
    rewrite = {}
    for check in CHECKS:
        try:
            out = check.decide(event)
        except Exception:
            out = {}
        if out.get("permissionDecision") == "deny":
            return out
        rewrite = rewrite or out
    return rewrite


def main():
    try:
        out = decide(json.load(sys.stdin))
    except Exception:
        out = {}
    sys.stdout.write(json.dumps(out))


if __name__ == "__main__":
    main()
