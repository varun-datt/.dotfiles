#!/usr/bin/env python3
"""Find an agent session's full log on disk and condense it into chunks a reader can cover.

  session_log.py find [--session ID] [--cwd DIR]
  session_log.py digest [--session ID] [--cwd DIR] [--out DIR] [--chunk-chars N] [--no-reasoning]
  session_log.py coverage --out DIR --ledger FILE
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

ERROR = re.compile(
    r"exit[ =:]+[1-9]|exit code [1-9]|\bfail(ed|ure|s)?\b|\berrors?\b|✘|traceback"
    r"|no such file|not found|denied|refused|timed out",
    re.I,
)
NOT_ERROR = re.compile(r"\b0 (failed|failures|errors?)\b", re.I)
SHELL_TOOLS = {"run_in_terminal", "get_terminal_output", "send_to_terminal", "bash", "shell", "powershell"}
ASK_TOOLS = {"vscode_askQuestions", "ask_user"}
SUBAGENT_TOOLS = {"runSubagent", "execution_subagent"}
KEY_ARGS = ("command", "filePath", "path", "file_path", "query", "pattern", "description", "url")


def vscode_roots():
    env = os.environ.get("DISTILL_VSCODE_STORAGE")
    if env:
        return [Path(p) for p in env.split(os.pathsep)]
    home, apps = Path.home(), ("Code", "Code - Insiders")
    return [home / "Library/Application Support" / a / "User/workspaceStorage" for a in apps] + [
        home / ".config" / a / "User/workspaceStorage" for a in apps
    ]


def copilot_state():
    return Path(os.environ.get("DISTILL_COPILOT_HOME") or Path.home() / ".copilot") / "session-state"


def same_dir(a, b):
    return a is not None and Path(a).resolve() == Path(b).resolve()


def vscode_folder(workspace):
    try:
        folder = json.loads((workspace / "workspace.json").read_text()).get("folder", "")
    except (OSError, ValueError):
        return None
    return unquote(urlparse(folder).path) if folder.startswith("file:") else None


def cli_cwd(session_dir):
    try:
        for line in (session_dir / "workspace.yaml").read_text().splitlines():
            if line.startswith("cwd:"):
                return line.split(":", 1)[1].strip().strip("'\"")
    except OSError:
        pass
    return None


def find_logs(session=None, cwd=None):
    found = []
    for root in vscode_roots():
        if not root.is_dir():
            continue
        for workspace in root.iterdir():
            transcripts = workspace / "GitHub.copilot-chat" / "transcripts"
            if not transcripts.is_dir():
                continue
            if session:
                found += [("vscode", p) for p in [transcripts / f"{session}.jsonl"] if p.is_file()]
            elif cwd is None or same_dir(vscode_folder(workspace), cwd):
                found += [("vscode", p) for p in transcripts.glob("*.jsonl")]
    state = copilot_state()
    if state.is_dir():
        for folder in state.iterdir():
            log = folder / "events.jsonl"
            if not log.is_file() or (session and folder.name != session):
                continue
            if session or cwd is None or same_dir(cli_cwd(folder), cwd):
                found.append(("copilot-cli", log))
    return sorted(found, key=lambda f: f[1].stat().st_mtime, reverse=True)


def session_id(surface, path):
    return path.stem if surface == "vscode" else path.parent.name


def read_jsonl(path, keep=None):
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.strip() or (keep and not keep(line)):
                continue
            try:
                yield json.loads(line)
            except ValueError:
                continue


def when(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, timezone.utc)
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def one_line(text, limit=300):
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def clip(text, limit):
    text = str(text).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def canonical(args):
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            return args
    return json.dumps(args, sort_keys=True, ensure_ascii=False)


def tool_line(name, args):
    if not isinstance(args, dict):
        return f"{name} {one_line(json.dumps(args, ensure_ascii=False))}"
    if name == "read_file" and "filePath" in args:
        return f"{name} {args['filePath']}:{args.get('startLine', '')}-{args.get('endLine', '')}"
    if name == "multi_replace_string_in_file":
        edits = [r for r in args.get("replacements", []) if isinstance(r, dict)]
        files = sorted({r.get("filePath", "?") for r in edits})
        return f"{name} {len(edits)} edits: {', '.join(files)}"
    if name == "memory":
        return f"{name} {args.get('command', '')} {args.get('path', '')}".rstrip()
    if name in ASK_TOOLS and isinstance(args.get("questions"), list):
        asked = [q.get("question", "") for q in args["questions"] if isinstance(q, dict)]
        return f"{name} {one_line(' | '.join(asked), 1000)}"
    for key in KEY_ARGS:
        if args.get(key):
            return f"{name} {one_line(args[key], 400)}"
    return f"{name} {one_line(json.dumps(args, ensure_ascii=False))}"


def result_text(result):
    if result is None or isinstance(result, str):
        return result
    if isinstance(result, dict):
        return result.get("content") or result.get("detailedContent") or json.dumps(result, ensure_ascii=False)
    return json.dumps(result, ensure_ascii=False)


def output_note(name, text):
    if not text:
        return None
    if name in ASK_TOOLS:
        return one_line(text, 2000)
    if name not in SHELL_TOOLS:
        return None
    lines = [one_line(l, 200) for l in text.splitlines() if ERROR.search(NOT_ERROR.sub("", l))]
    return " | ".join(lines[:6]) if lines else None


class DebugLog:
    """Tool outputs and subagent replies VS Code keeps beside a transcript, for as long as it keeps them."""

    TOLERANCE_MS = 5000

    def __init__(self, folder):
        self.folder, self.spans, self.first = folder, {}, None
        main = folder / "main.jsonl"
        if not main.is_file():
            return
        for o in read_jsonl(main, keep=lambda line: '"tool_call"' in line):
            if o.get("type") != "tool_call" or not isinstance(o.get("ts"), (int, float)):
                continue
            attrs = o.get("attrs") or {}
            self.spans.setdefault(o.get("name"), []).append([o["ts"], canonical(attrs.get("args")), attrs.get("result")])
            self.first = o["ts"] if self.first is None else min(self.first, o["ts"])

    def take(self, name, args, at):
        if not at:
            return None
        target = at.timestamp() * 1000
        near = [s for s in self.spans.get(name, []) if abs(s[0] - target) <= self.TOLERANCE_MS]
        if not near:
            return None
        # The debug log cuts long arguments, so an exact match is preferred but not required.
        exact = [s for s in near if s[1] == canonical(args)]
        best = min(exact or near, key=lambda s: abs(s[0] - target))
        self.spans[name].remove(best)
        return result_text(best[2])

    def reply(self, call_id):
        for path in self.folder.glob(f"*-{call_id}.jsonl") if call_id else []:
            last = None
            for o in read_jsonl(path, keep=lambda line: "agent_response" in line):
                if o.get("type") == "agent_response":
                    last = (o.get("attrs") or {}).get("response")
            if last:
                return clip(message_text(last), 4000)
        return None


def message_text(value):
    if isinstance(value, str) and value.lstrip().startswith("["):
        try:
            value = json.loads(value)
        except ValueError:
            return value
    if isinstance(value, list):
        parts = [p for m in value if isinstance(m, dict) for p in m.get("parts", []) if isinstance(p, dict)]
        texts = [p.get("content") for p in parts if p.get("type") == "text" and isinstance(p.get("content"), str)]
        if texts:
            return "\n".join(texts)
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def chat_store_results(transcript):
    """Tool results VS Code's chat-session store keeps for every finished request, by call id."""
    folder = transcript.parent.parent.parent / "chatSessions"
    results = {}

    def add(result):
        calls = ((result or {}).get("metadata") or {}).get("toolCallResults") or {}
        for key, value in calls.items() if isinstance(calls, dict) else []:
            parts = value.get("content") if isinstance(value, dict) else None
            texts = [p.get("value") if isinstance(p.get("value"), str) else json.dumps(p.get("value"), ensure_ascii=False)
                     for p in parts or [] if isinstance(p, dict) and "value" in p]
            results[key.split("__")[0]] = "\n".join(texts)

    whole = folder / f"{transcript.stem}.json"
    if whole.is_file():
        try:
            for request in json.loads(whole.read_text()).get("requests", []):
                add(request.get("result"))
        except (OSError, ValueError, AttributeError):
            pass
    log = folder / f"{transcript.stem}.jsonl"
    if log.is_file():
        for o in read_jsonl(log):
            kind, key, value = o.get("kind"), o.get("k"), o.get("v")
            if kind == 0 and isinstance(value, dict):
                for request in value.get("requests", []):
                    add(request.get("result"))
            elif kind == 1 and isinstance(key, list) and key[-1:] == ["result"] and isinstance(value, dict):
                add(value)
            elif kind == 2 and key == ["requests"] and isinstance(value, list):
                for request in value:
                    add(request.get("result") if isinstance(request, dict) else None)
    return results


def message_events(at, data, reasoning):
    events = []
    if reasoning and (data.get("reasoningText") or "").strip():
        events.append((at, "THINKING", data["reasoningText"]))
    if (data.get("content") or "").strip():
        events.append((at, "AGENT", data["content"]))
    return events


def vscode_events(path, reasoning=True):
    debug = DebugLog(path.parent.parent / "debug-logs" / path.stem)
    store = chat_store_results(path)
    events, names, calls, joined = [], {}, 0, 0
    for o in read_jsonl(path):
        kind, data, at = o.get("type"), o.get("data") or {}, when(o.get("timestamp"))
        if kind == "user.message":
            events.append((at, "USER", data.get("content") or ""))
        elif kind == "assistant.message":
            events += message_events(at, data, reasoning)
        elif kind == "tool.execution_start":
            name, args, call = data.get("toolName", "?"), data.get("arguments"), data.get("toolCallId")
            names[call], calls = name, calls + 1
            events.append((at, "TOOL", tool_line(name, args)))
            logged = debug.take(name, args, at)
            result = store.get(call) or logged
            joined += result is not None
            note = (debug.reply(call) if name in SUBAGENT_TOOLS else None) or output_note(name, result)
            if note:
                events.append((at, "OUTPUT", note))
        elif kind == "tool.execution_complete" and data.get("success") is False:
            events.append((at, "FAILED", names.get(data.get("toolCallId"), "?")))
    first = when(debug.first)
    return events, {"calls": calls, "outputs_joined": joined, "outputs_from": first.isoformat() if first else None}


def cli_events(path, reasoning=True):
    events, names, calls = [], {}, 0
    for o in read_jsonl(path):
        kind, data, at = o.get("type", ""), o.get("data") or {}, when(o.get("timestamp"))
        if kind == "user.message":
            events.append((at, "USER", data.get("content") or ""))
        elif kind == "assistant.message":
            events += message_events(at, data, reasoning)
        elif kind == "tool.execution_start":
            name = data.get("toolName", "?")
            names[data.get("toolCallId")], calls = name, calls + 1
            events.append((at, "TOOL", tool_line(name, data.get("arguments"))))
        elif kind == "tool.execution_complete":
            name, text = names.get(data.get("toolCallId"), "?"), result_text(data.get("result"))
            if data.get("success") is False:
                error = data.get("error")
                message = error.get("message") if isinstance(error, dict) else error
                events.append((at, "FAILED", f"{name}: {one_line(message or text or '', 400)}"))
            elif note := output_note(name, text):
                events.append((at, "OUTPUT", note))
        elif kind.startswith("session.compaction") or kind == "session.truncation":
            events.append((at, "NOTE", kind))
    return events, {"calls": calls, "outputs_joined": calls, "outputs_from": None}


def local(at, fmt):
    return at.astimezone().strftime(fmt) if at else "?"


def render(events):
    blocks, day = [], None
    for at, kind, text in events:
        if at and at.astimezone().date() != day:
            day = at.astimezone().date()
            blocks.append((at, f"--- {day.isoformat()} ---"))
        stamp = local(at, "%H:%M:%S")
        if kind == "OUTPUT":
            blocks.append((at, f"{stamp}   ↳ {text}"))
        elif kind in ("USER", "AGENT", "THINKING"):
            blocks.append((at, f"{stamp} {kind}\n{text.strip()}\n"))
        else:
            blocks.append((at, f"{stamp} {kind} {text}"))
    return blocks


def split(blocks, size):
    chunks, current, length = [], [], 0
    for block in blocks:
        if current and length + len(block[1]) > size:
            chunks.append(current)
            current, length = [], 0
        current.append(block)
        length += len(block[1]) + 1
    return chunks + [current] if current else chunks


def choose(args):
    logs = find_logs(args.session, None if args.session else (args.cwd or os.getcwd()))
    return logs


def cmd_find(args):
    logs = choose(args)
    for surface, path in logs[:10]:
        stat = path.stat()
        print(f"{datetime.fromtimestamp(stat.st_mtime):%Y-%m-%d %H:%M}  {surface:11} {stat.st_size / 1e6:6.1f} MB  {path}")
    if not logs:
        print("no session log found; pass --session ID, or --cwd for the session's folder")
        return 1
    if len(logs) > 10:
        print(f"... and {len(logs) - 10} older")
    return 0


def cmd_digest(args):
    logs = choose(args)
    if not logs:
        print("no session log found; distill from the context window and say so in the report")
        return 1
    surface, path = logs[0]
    sid = session_id(surface, path)
    events, meta = (vscode_events if surface == "vscode" else cli_events)(path, not args.no_reasoning)
    out = Path(args.out) if args.out else Path.home() / ".cache" / "distill" / sid
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("chunk-*.md"):
        old.unlink()
    chunks = split(render(events), args.chunk_chars)
    index = {"source": str(path), "surface": surface, "session": sid, **meta, "chunks": []}
    for number, chunk in enumerate(chunks, 1):
        cid, times = f"chunk-{number:02d}", [at for at, _ in chunk if at]
        start, end = (times[0], times[-1]) if times else (None, None)
        text = "\n".join(block for _, block in chunk)
        header = f"# {cid} of {len(chunks):02d}: {surface} session {sid}, {local(start, '%Y-%m-%d %H:%M')} to {local(end, '%Y-%m-%d %H:%M')}\n\n"
        (out / f"{cid}.md").write_text(header + text + "\n", encoding="utf-8")
        index["chunks"].append({"id": cid, "file": str(out / f"{cid}.md"), "chars": len(text)})
    (out / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    counts = {}
    for _, kind, _ in events:
        counts[kind] = counts.get(kind, 0) + 1
    times = [at for at, _, _ in events if at]
    total = sum(c["chars"] for c in index["chunks"])
    print(f"source: {surface} {path} ({path.stat().st_size / 1e6:.1f} MB)")
    if len(logs) > 1 and not args.session:
        print(f"chose the newest of {len(logs)} logs for this folder; pass --session to choose another")
    if times:
        print(f"period: {local(times[0], '%Y-%m-%d %H:%M')} to {local(times[-1], '%Y-%m-%d %H:%M')}")
    print("events: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    if surface == "vscode":
        since = local(when(meta["outputs_from"]), "%Y-%m-%d %H:%M") if meta["outputs_from"] else "nowhere"
        print(f"tool outputs: {meta['outputs_joined']} of {meta['calls']} calls still on disk "
              f"(chat store: finished requests; debug log: from {since})")
    print(f"chunks: {len(chunks)} in {out}, {total} characters (about {total // 4000}k tokens)")
    return 0


def cmd_coverage(args):
    index = json.loads((Path(args.out) / "index.json").read_text())
    sections = {}
    current = None
    for line in Path(args.ledger).read_text().splitlines():
        heading = re.match(r"^#+\s*(chunk-\d+)\b", line)
        if heading:
            current = heading.group(1)
            sections[current] = ""
        elif current:
            sections[current] += line.strip()
    missing = [c["id"] for c in index["chunks"] if not sections.get(c["id"])]
    if missing:
        print("not covered (no heading, or nothing under it; write `none` for a chunk with no candidates): " + ", ".join(missing))
        return 1
    print(f"all {len(index['chunks'])} chunks covered")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("find", "digest"):
        p = sub.add_parser(name)
        p.add_argument("--session", help="the session id; in VS Code, the last folder of its debug-log path")
        p.add_argument("--cwd", help="the session's folder (default: the current folder)")
        if name == "digest":
            p.add_argument("--out", help="default: ~/.cache/distill/<session>")
            p.add_argument("--chunk-chars", type=int, default=100_000)
            p.add_argument("--no-reasoning", action="store_true")
    p = sub.add_parser("coverage")
    p.add_argument("--out", required=True)
    p.add_argument("--ledger", required=True)
    args = parser.parse_args(argv)
    return {"find": cmd_find, "digest": cmd_digest, "coverage": cmd_coverage}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
