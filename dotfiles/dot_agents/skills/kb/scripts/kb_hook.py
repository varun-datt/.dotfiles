#!/usr/bin/env python3
"""Hook for Copilot CLI, the Copilot app and VS Code: tells every agent, and every helper agent it
starts, to look things up with kb. With KB_HOOK_HITS=1 it also hands over kb's top hits for the
person's message: appended to the message (userPromptTransformed), or after the agent's first
search (postToolUse). The hits part is an experiment and is off unless that variable is set.

Usage, from a hook file in ~/.copilot/hooks/:  kb_hook.py EVENT
    sessionStart, subagentStart   add the note
    userPromptTransformed         (KB_HOOK_HITS=1) append kb's hits to the model-facing message
    userPromptSubmitted           (KB_HOOK_HITS=1) remember the message for postToolUse
    postToolUse                   (KB_HOOK_HITS=1) after the first search since the message, add kb's hits
Reads the event's JSON on stdin and answers in the caller's shape: VS Code's Local harness sends
hook_event_name and reads hookSpecificOutput; the Copilot harness reads top-level fields. Any
failure prints {} and exits 0, so the hook never stops the agent. $KB_HOOK_LOG, if set, gets one
line per call: the event, the input's field names and what was added, never the text.
"""
import json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(os.environ.get("KB_HOOK_STATE", os.path.expanduser("~/.cache/kb/hook")))
NOTE = ("Knowledge search: to look up notes, decisions, runbooks or code by meaning, run "
        "`python3 ~/.agents/skills/kb/scripts/kb.py search \"<question>\"` before grepping folders by hand. "
        "It searches the space you are working in; name another with --source (`kb.py sources` lists them).")
SEARCH_TOOLS = {"grep", "rg", "glob", "grep_search", "file_search", "semantic_search"}
SHELL_TOOLS = {"bash", "run_in_terminal"}
SEARCH_COMMAND = re.compile(r"(?:^|[;&|(]\s*)(?:rg|grep|git grep|find|fd)\b")
MAX_CHARS = 1500


def kb_hits(query, cwd):
    """Top 3 hits as text, or "" when kb finds nothing, fails, or the folder is in no source."""
    words = query.split()
    if len(words) <= 3 or query.lstrip().startswith("/"):
        return ""
    try:
        run = subprocess.run([sys.executable, "-B", os.path.join(HERE, "kb.py"), "search", query, "--json"],
                             cwd=cwd or None, capture_output=True, text=True, timeout=float(os.environ.get("KB_HOOK_TIMEOUT", "4")))
        hits = json.loads(run.stdout)[:3] if run.returncode == 0 else []
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return ""
    if not hits:
        return ""
    lines = ["Knowledge search (kb) ran on this message; leads to read, not answers:"]
    lines += [f"- {h['source']}:{h['path']}:{h['line']} {h.get('title', '')} — {h.get('snippet', '')[:160]}" for h in hits]
    return "\n".join(lines)[:MAX_CHARS]


def is_search(data):
    name = data.get("toolName") or data.get("tool_name") or ""
    if name in SEARCH_TOOLS or name.lower() in ("grep", "glob"):
        return True
    args = data.get("toolArgs") or data.get("tool_input") or {}
    command = args.get("command", "") if isinstance(args, dict) else ""
    return name in SHELL_TOOLS | {"Bash"} and bool(SEARCH_COMMAND.search(command))


def state_path(data):
    sid = re.sub(r"[^\w.-]", "_", str(data.get("sessionId") or data.get("session_id") or "default"))
    return os.path.join(STATE, f"{sid}.json")


def answer(event, data):
    hits_on = os.environ.get("KB_HOOK_HITS") == "1"
    if event in ("sessionstart", "subagentstart"):
        return {"additionalContext": NOTE}, "note"
    if not hits_on:
        return {}, ""
    cwd = data.get("cwd") or ""
    if event == "userprompttransformed":
        hits = kb_hits(data.get("prompt") or "", cwd)
        content = data.get("transformedPrompt")
        if hits and isinstance(content, str) and content:
            if os.path.exists(state_path(data)):
                os.remove(state_path(data))
            return {"modifiedTransformedPrompt": f"{content}\n\n{hits}"}, "hits"
        return {}, ""
    if event in ("userpromptsubmitted", "userpromptsubmit"):
        os.makedirs(STATE, exist_ok=True)
        with open(state_path(data), "w") as f:
            json.dump({"prompt": data.get("prompt") or "", "cwd": cwd}, f)
        return {}, "remembered"
    if event == "posttooluse" and is_search(data) and os.path.exists(state_path(data)):
        with open(state_path(data)) as f:
            saved = json.load(f)
        os.remove(state_path(data))
        hits = kb_hits(saved.get("prompt", ""), saved.get("cwd") or cwd)
        return ({"additionalContext": hits}, "hits") if hits else ({}, "")
    return {}, ""


def shape(event, data, out):
    """VS Code's Local harness reads hookSpecificOutput; the Copilot harness reads top-level fields."""
    if "hook_event_name" in data and "additionalContext" in out:
        return {"hookSpecificOutput": {"hookEventName": data["hook_event_name"], "additionalContext": out["additionalContext"]}}
    return out


def main(argv):
    event = (argv[1] if len(argv) > 1 else "").lower()
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        out, added = answer(event, data if isinstance(data, dict) else {})
        out = shape(event, data, out)
    except Exception:  # a hook must never stop the agent
        data, out, added = {}, {}, "error"
    if os.environ.get("KB_HOOK_LOG"):
        with open(os.environ["KB_HOOK_LOG"], "a") as log:
            log.write(json.dumps({"at": time.strftime("%H:%M:%S"), "event": event, "fields": sorted(data), "added": added}) + "\n")
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
