#!/usr/bin/env python3
# preToolUse hook: refuses a question to the owner that breaks the user rules "Deciding whether to ask" and "Asking me to decide".
import json
import os
import re

ASK = re.compile(r"ask.?questions?|ask_?user", re.I)
REASONS = ("hard to undo", "changes a lot for the owner", "changes the owner's process",
           "needs the owner's judgement", "a fact about the owner's work")
OPENING = re.compile(r"^\s*Ask now:\s*(?P<reason>[^.\n]+?)\s*\.\s*Kind:\s*(?P<kind>[^.\n]+)", re.I)
BUILT = re.compile(r"\b(?:approve|accept|keep)\b[^.\n]{0,30}\bas (?:built|is)\b|\balready built\b", re.I)
BATCH = re.compile(r"\bbatch \d+ of \d+\b", re.I)
TABLE = re.compile(r"^\s*\|.*\|\s*$\n^\s*\|[\s:|-]*-[\s:|-]*\|\s*$", re.M)
STREAK = 5
LOG = os.path.expanduser("~/.local/state/agent-hooks/question-answers.jsonl")


def log_path():
    return os.environ.get("QUESTION_LOG", LOG)


def norm(text):
    return " ".join(re.findall(r"[a-z0-9']+", text.lower()))


def opening(question):
    m = OPENING.search(question.get("message") or question.get("question") or "")
    if not m or norm(m.group("reason")) not in REASONS:
        return None
    return norm(m.group("reason")), norm(m.group("kind"))


def answered(kind):
    try:
        with open(log_path()) as f:
            rows = [json.loads(line) for line in f if line.strip()]
    except OSError:
        return []
    return [r.get("took_recommended") for r in rows if r.get("kind") == kind]


def problems(questions):
    found = []
    if len(questions) > 1 and not any(BATCH.search(q.get("message") or "") for q in questions):
        found.append("several questions with no batch N of M in a message (label each batch)")
    for q in questions:
        name = q.get("header") or q.get("question") or "a question"
        sorted_as = opening(q)
        if sorted_as is None:
            found.append(f"{name} does not open its message with Ask now: <reason>. Kind: <kind>. where the reason is one of: "
                         + "; ".join(REASONS) + ". A choice with none of these reasons is Review later: decide it, build it, "
                         "and list it in the final report as not approved, grouped by feature")
            continue
        reason, kind = sorted_as
        if reason != "a fact about the owner's work" and not TABLE.search(q.get("message") or ""):
            found.append(f"{name} has no table of what is being decided in its message")
        for option in q.get("options") or []:
            if BUILT.search(f"{option.get('label', '')} {option.get('description', '')}"):
                found.append(f"{name} asks to approve finished work ({option.get('label', '')}): that is Review later, "
                             "listed in the final report, not asked")
                break
        recent = answered(kind)[-STREAK:]
        if len(recent) == STREAK and all(recent):
            found.append(f"{name}: the owner took the recommendation the last {STREAK} times a question of kind {kind} was "
                         "asked. Stop asking it: record its answer as a skill default or a ruling, decide it, and list it "
                         "in the final report as not approved")
    return found


def decide(event):
    name = event.get("toolName") or event.get("tool_name") or ""
    if not ASK.search(name):
        return {}
    args = event.get("toolArgs", event.get("tool_input", {}))
    if isinstance(args, str):
        args = json.loads(args)
    found = problems(args.get("questions") or [])
    if not found:
        return {}
    reason = "Question rules: " + " | ".join(found)
    reason = reason[:1500]
    return {"permissionDecision": "deny", "permissionDecisionReason": reason,
            "hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}
