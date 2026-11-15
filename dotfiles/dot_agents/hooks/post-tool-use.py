#!/usr/bin/env python3
# postToolUse hook: logs, for each answered question to the owner, its kind and whether the owner took the recommendation.
import importlib.util
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("question_rules", os.path.join(HERE, "question-rules.py"))
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)


def find_answers(value):
    if isinstance(value, dict):
        if isinstance(value.get("answers"), dict):
            return value["answers"]
        for v in value.values():
            found = find_answers(v)
            if found is not None:
                return found
    elif isinstance(value, list):
        for v in value:
            found = find_answers(v)
            if found is not None:
                return found
    elif isinstance(value, str) and '"answers"' in value:
        try:
            return find_answers(json.loads(value[value.index("{"):value.rindex("}") + 1]))
        except ValueError:
            return None
    return None


def rows(event):
    name = event.get("toolName") or event.get("tool_name") or ""
    if not rules.ASK.search(name):
        return []
    args = event.get("toolArgs", event.get("tool_input", {}))
    if isinstance(args, str):
        args = json.loads(args)
    answers = find_answers({k: v for k, v in event.items() if k not in ("toolArgs", "tool_input")})
    if answers is None:
        return []
    out = []
    for q in args.get("questions") or []:
        sorted_as = rules.opening(q)
        answer = answers.get(q.get("header"))
        if sorted_as is None or not isinstance(answer, dict) or answer.get("skipped"):
            continue
        recommended = [o.get("label") for o in q.get("options") or [] if o.get("recommended")]
        took = bool(recommended) and answer.get("selected") == recommended and not answer.get("freeText")
        out.append({"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "reason": sorted_as[0], "kind": sorted_as[1],
                    "header": q.get("header"), "took_recommended": took})
    return out


def main():
    try:
        found = rows(json.load(sys.stdin))
        if found:
            path = rules.log_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a") as f:
                for row in found:
                    f.write(json.dumps(row) + "\n")
    except Exception:
        pass
    sys.stdout.write("{}")


if __name__ == "__main__":
    main()
