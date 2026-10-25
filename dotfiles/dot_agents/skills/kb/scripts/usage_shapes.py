#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Measure how search is used today, as counts and shares only, to keep the mock cases realistic.

Usage:
    usage_shapes.py [--sources-file PATH] [--json OUT]

Reads, read-only: VS Code Copilot Chat transcripts (agents' search calls and the files they read
next), Copilot CLI event logs, VS Code's search-box history, and the Copilot session store (the
person's messages to agents). A folder belongs to the kb source whose root contains it. No query
text is printed or written; references/refreshing-cases.md says what to do with the numbers.
"""
import argparse, glob, json, os, re, sqlite3, statistics, sys
from collections import defaultdict
from urllib.parse import unquote, urlparse

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kb  # noqa: E402

HOME = os.path.expanduser("~")
CODE = f"{HOME}/Library/Application Support/Code/User"
WS = f"{CODE}/workspaceStorage"
STORE = f"{CODE}/globalStorage/github.copilot-chat/session-store.db"
SEARCH_CMD = re.compile(r"(?:^|[;&|(]\s*)(?:/usr/bin/)?(rg|grep|git grep|find|fd|ck|qmd|kb)\b(.*?)(?=$|[;&|])", re.M)
FLAGS = ("regex", "identifier", "path_or_glob", "guid", "number", "error_like", "acronym", "natural_language")


def shape(q, regex):
    words = q.split()
    return {
        "words": len(words), "regex": bool(regex), "alternatives": q.count("|") + 1 if regex else 1,
        "identifier": bool(re.search(r"\b[a-z]+[A-Z]\w*\b|\b[a-z0-9]+_[a-z0-9_]+\b|\b[A-Z][a-z]+[A-Z]\w*\b", q)),
        "path_or_glob": bool(re.search(r"[\w-]+/[\w./-]+|\*\.\w+|\*\*", q)),
        "guid": bool(re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-", q, re.I)), "number": bool(re.search(r"\b\d{3,}\b", q)),
        "error_like": bool(re.search(r"error|exception|fail|denied|timeout", q, re.I)),
        "acronym": bool(re.search(r"\b[A-Z]{2,6}\d?\b", q)),
        "natural_language": len(words) >= 4 and not regex and not re.search(r"[|\\^$()\[\]{}]", q),
    }


def summarise(rows):
    out = {"n": len(rows), "median_words": statistics.median(r["words"] for r in rows),
           "median_alternatives": statistics.median(r["alternatives"] for r in rows)}
    out.update({f"share_{k}": round(sum(r[k] for r in rows) / len(rows), 2) for k in FLAGS})
    if "then_read" in rows[0]:
        out["share_followed_by_a_read"] = round(sum(r["then_read"] for r in rows) / len(rows), 2)
    return out


def space_finder(sources):
    roots = sorted(((s["root"], s["name"]) for s in sources), key=lambda x: -len(x[0]))
    return lambda folder: next((name for root, name in roots if folder and os.path.realpath(folder).startswith(root)), "other")


def folder_of(ws_dir):
    try:
        w = json.load(open(os.path.join(ws_dir, "workspace.json")))
        return unquote(urlparse(w.get("folder") or w.get("workspace") or "").path)
    except (OSError, ValueError):
        return ""


def agent_searches(space_of):
    rows = defaultdict(list)
    for f in glob.glob(f"{WS}/*/GitHub.copilot-chat/transcripts/*.jsonl"):
        space = space_of(folder_of(f.split("/GitHub.copilot-chat/")[0]))
        calls = []
        for line in open(f, errors="ignore"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("type") == "tool.execution_start":
                d = r.get("data") or {}
                calls.append((d.get("toolName"), d.get("arguments") or {}))
        for i, (name, args) in enumerate(calls):
            read = any(n == "read_file" for n, _ in calls[i + 1:i + 4])
            if name in ("grep_search", "semantic_search", "file_search") and isinstance(args.get("query"), str):
                rows[(space, name)].append({**shape(args["query"], args.get("isRegexp", name == "file_search")), "then_read": read})
            elif name == "run_in_terminal" and isinstance(args.get("command"), str):
                for m in SEARCH_CMD.finditer(args["command"]):
                    quoted = re.findall(r"'([^']+)'|\"([^\"]+)\"", m.group(2))
                    text = next((a or b for a, b in quoted), m.group(2).strip())
                    rows[(space, f"terminal {m.group(1)}")].append({**shape(text, True), "then_read": read})
    for f in glob.glob(f"{HOME}/.copilot/session-state/*/events.jsonl"):
        for line in open(f, errors="ignore"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            d = (r.get("data") or {}) if r.get("type") == "tool.execution_start" else {}
            name, args = d.get("toolName"), d.get("arguments") or {}
            if name in ("grep", "glob") and isinstance(args.get("pattern"), str):
                rows[("cli", name)].append(shape(args["pattern"], True))
            elif name == "bash" and isinstance(args.get("command"), str):
                for m in SEARCH_CMD.finditer(args["command"]):
                    rows[("cli", f"terminal {m.group(1)}")].append(shape(m.group(2).strip(), True))
    return rows


def search_box(space_of):
    rows = defaultdict(list)
    for db in glob.glob(f"{WS}/*/state.vscdb"):
        space = space_of(folder_of(os.path.dirname(db)))
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            for (v,) in con.execute("SELECT value FROM ItemTable WHERE key = 'workbench.search.history'"):
                hist = json.loads(v)
                for q in hist.get("search", []) if isinstance(hist, dict) else []:
                    if isinstance(q, str) and q.strip():
                        rows[(space, "editor search box")].append(shape(q, False))
            con.close()
        except sqlite3.Error:
            continue
    return rows


def requests():
    if not os.path.exists(STORE):
        return {}
    con = sqlite3.connect(f"file:{STORE}?mode=ro", uri=True)
    msgs = [m for (m,) in con.execute("SELECT user_message FROM turns WHERE user_message IS NOT NULL")
            if m and not m.lstrip().startswith("[Terminal") and len(m) >= 25]
    con.close()
    if len(msgs) < 4:
        return {}
    words = [len(m.split()) for m in msgs]
    q = statistics.quantiles(words, n=20)
    share = lambda pat: round(sum(bool(re.search(pat, m, re.M)) for m in msgs) / len(msgs), 2)
    return {"n": len(msgs), "words_p25": q[4], "words_median": q[9], "words_p75": q[14], "words_p90": q[17],
            "share_names_a_file": share(r"[\w-]+/[\w./-]+|\w+\.(md|ts|py|cs|java|json|yaml)\b"),
            "share_question_mark": share(r"\?"), "share_list": share(r"^\s*(\d+[.)]|[-*])\s")}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--sources-file")
    p.add_argument("--json")
    a = p.parse_args(argv)
    try:
        space_of = space_finder(kb.load_sources(a.sources_file))
    except OSError:
        space_of = lambda folder: "other"  # noqa: E731
    out = {"agent searches": agent_searches(space_of), "person, search box": search_box(space_of)}
    out = {k: {f"{s} / {t}": summarise(r) for (s, t), r in sorted(v.items(), key=lambda kv: -len(kv[1])) if r} for k, v in out.items()}
    out["person, messages to agents"] = requests()
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)
    for label, groups in out.items():
        print(f"\n{label}")
        if label == "person, messages to agents":
            print(f"  {groups}")
            continue
        for k, v in list(groups.items())[:16]:
            if v["n"] >= 5:
                print(f"  {k:36} n={v['n']:5} words~{v['median_words']:<4} alts~{v['median_alternatives']:<4} "
                      + " ".join(f"{f[:5]} {v[f'share_{f}']}" for f in FLAGS) + f" read-after {v.get('share_followed_by_a_read', '-')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
