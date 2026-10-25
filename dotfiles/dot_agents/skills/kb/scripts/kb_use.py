#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Measure whether agents use kb, per request, by app and by kb source.

Usage:
    kb_use.py [--since YYYY-MM-DD] [--json OUT] [--sources-file PATH]

For each message a person sent, and each helper agent's task: did kb run, did it run before any
other tool, and did the agent then open a file kb had returned. Reads, read-only: VS Code Copilot
Chat debug logs (main agent and helpers, with tool results), Copilot CLI and SDK session logs, and
AMC's database, to tell AMC's sessions from the CLI's. Prints counts and shares only, no text.
"""
import argparse, datetime as dt, glob, json, os, re, sqlite3, sys
from collections import defaultdict
from urllib.parse import unquote, urlparse

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kb  # noqa: E402

HOME = os.path.expanduser("~")
WS = f"{HOME}/Library/Application Support/Code/User/workspaceStorage"
CLI = f"{HOME}/.copilot/session-state"
AMC_DB = os.path.join(os.environ.get("AMC_HOME", f"{HOME}/Library/Application Support/amc"), "amc.db")
KB_COMMAND = re.compile(r"\bkb(?:\.py)?\s+search\b")
KB_TOOL = re.compile(r"(?:^|_)kb(?:_|$)|knowledge_search")
SHELL_ARG = {"run_in_terminal": "command", "bash": "command", "shell": "command"}
READ_ARG = {"read_file": "filePath", "view": "path", "read": "path", "str_replace_editor": "path"}
IGNORED = {"manage_todo_list", "memory", "vscode_askQuestions", "tool_search", "report_intent", "think", "update_todo"}
PATH = re.compile(r"(?:[\w.@-]+/)*[\w@-][\w.@-]*\.[A-Za-z]\w{0,5}\b")


def parse_args_text(text):
    try:
        v = json.loads(text) if isinstance(text, str) else text
        return v if isinstance(v, dict) else {}
    except ValueError:
        return {}


def is_kb(name, args):
    if KB_TOOL.search(name or ""):
        return True
    command = args.get(SHELL_ARG.get(name, ""), "")
    return isinstance(command, str) and bool(KB_COMMAND.search(command))


def opened_paths(name, args):
    if name in READ_ARG and isinstance(args.get(READ_ARG[name]), str):
        return [args[READ_ARG[name]]]
    command = args.get(SHELL_ARG.get(name, ""), "")
    if isinstance(command, str) and re.search(r"\b(cat|sed|head|tail|less|bat|nl)\b", command):
        return PATH.findall(command)
    return []


def score(calls):
    """calls: [(name, args, result_text or None)] in order. Returns the request's facts."""
    calls = [c for c in calls if c[0] not in IGNORED]
    kb_at = [i for i, (n, a, _) in enumerate(calls) if is_kb(n, a)]
    out = {"kb_ran": bool(kb_at), "kb_first": bool(calls) and bool(kb_at) and kb_at[0] == 0,
           "results_seen": False, "opened_kb_file": False}
    returned = set()
    for i, (name, args, result) in enumerate(calls):
        if i in kb_at and isinstance(result, str):
            out["results_seen"] = True
            returned |= {p for p in PATH.findall(result) if "/" in p or p.endswith(".md")}
        elif returned and any(p.endswith(r) or r.endswith(p) for p in opened_paths(name, args) for r in returned):
            out["opened_kb_file"] = True
    return out


def folder_of(ws_dir):
    try:
        with open(os.path.join(ws_dir, "workspace.json")) as f:
            w = json.load(f)
        return unquote(urlparse(w.get("folder") or w.get("workspace") or "").path)
    except (OSError, ValueError):
        return ""


def stamp(v):
    if isinstance(v, (int, float)):
        return dt.datetime.fromtimestamp(v / 1000 if v > 1e11 else v, dt.timezone.utc)
    try:
        return dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None


def vscode_requests():
    for log in glob.glob(f"{WS}/*/GitHub.copilot-chat/debug-logs/*/*.jsonl"):
        folder = folder_of(log.split("/GitHub.copilot-chat/")[0])
        helper = not log.endswith("/main.jsonl")
        spans = []
        for line in open(log, errors="ignore"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("type") in ("user_message", "tool_call"):
                spans.append(r)
        spans.sort(key=lambda r: r.get("ts") or 0)
        current = None
        for r in spans:
            if r["type"] == "user_message" and not helper or current is None:
                if current:
                    yield current
                current = {"app": "vscode helper" if helper else "vscode", "folder": folder, "at": stamp(r.get("ts")), "calls": []}
            if r["type"] == "tool_call":
                a = r.get("attrs") or {}
                current["calls"].append((str(r.get("name", "")).split()[-1] if r.get("name") else "",
                                         parse_args_text(a.get("args")), a.get("result")))
        if current:
            yield current


def amc_sessions():
    try:
        con = sqlite3.connect(f"file:{AMC_DB}?mode=ro&immutable=1", uri=True)
        ids = {v for (v,) in con.execute("SELECT vendor_session_id FROM sessions WHERE vendor_session_id IS NOT NULL")}
        con.close()
        return ids
    except sqlite3.Error:
        return set()


def cli_requests():
    amc = amc_sessions()
    for log in glob.glob(f"{CLI}/*/events.jsonl"):
        sid = os.path.basename(os.path.dirname(log))
        app, folder, current, results, pending = ("amc" if sid in amc else "cli"), "", None, {}, []
        for line in open(log, errors="ignore"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            t, d = r.get("type"), r.get("data") or {}
            if t == "session.start":
                folder = (d.get("context") or {}).get("cwd", "")
            elif t == "user.message":
                if current:
                    yield current
                current = {"app": app, "folder": folder, "at": stamp(r.get("timestamp")), "calls": []}
            elif t == "tool.execution_start" and current:
                call = [d.get("toolName", ""), parse_args_text(d.get("arguments") or {}), None]
                current["calls"].append(call)
                results[d.get("toolCallId")] = call
            elif t == "tool.execution_complete" and d.get("toolCallId") in results:
                res = d.get("result")
                results[d["toolCallId"]][2] = res if isinstance(res, str) else json.dumps(res)
        if current:
            yield current


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--since", help="only requests on or after this date (YYYY-MM-DD)")
    p.add_argument("--sources-file")
    p.add_argument("--json")
    a = p.parse_args(argv)
    since = dt.datetime.fromisoformat(a.since).replace(tzinfo=dt.timezone.utc) if a.since else None
    try:
        sources = kb.load_sources(a.sources_file)
    except OSError:
        sources = []
    roots = sorted(((os.path.realpath(os.path.expanduser(s["root"])), s["name"]) for s in sources), key=lambda x: -len(x[0]))
    space_of = lambda folder: next((n for r, n in roots if folder and os.path.realpath(folder).startswith(r)), "other")  # noqa: E731

    groups = defaultdict(lambda: defaultdict(int))
    for req in (*vscode_requests(), *cli_requests()):
        if since and (req["at"] is None or req["at"] < since):
            continue
        facts = score([tuple(c) for c in req["calls"]])
        g = groups[(req["app"], space_of(req["folder"]))]
        g["requests"] += 1
        g["with_tools"] += bool(req["calls"])
        for k, v in facts.items():
            g[k] += v
    rows = [{"app": app, "space": space, **g} for (app, space), g in sorted(groups.items(), key=lambda kv: -kv[1]["requests"])]
    total = defaultdict(int)
    for r in rows:
        for k, v in r.items():
            if isinstance(v, int):
                total[k] += v
    rows.append({"app": "all", "space": "all", **total})
    if a.json:
        with open(a.json, "w") as f:
            json.dump({"measured_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                       "since": a.since, "rows": rows}, f, indent=1)
    print(f"{'app':14} {'space':34} {'requests':>8} {'tools':>6} {'kb ran':>7} {'kb 1st':>7} {'seen':>5} {'opened':>7}")
    for r in rows:
        print(f"{r['app']:14} {r['space'][:34]:34} {r['requests']:8} {r['with_tools']:6} {r['kb_ran']:7} "
              f"{r['kb_first']:7} {r['results_seen']:5} {r['opened_kb_file']:7}")
    print("kb ran / kb 1st: requests where kb ran at all / before any other tool. seen: requests whose kb"
          " results are in the log. opened: the agent then opened a file kb returned.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
