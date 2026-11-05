#!/usr/bin/env python3
"""Check and safely rewrite a workspace state file (~/.agents/state/<workspace>/state.md).

  state.py check FILE...                 warn on size, dated diary lines and an old template; exit 1 if any
  state.py hash FILE                     print the token to pass to write
  state.py write FILE --expect TOKEN     replace FILE with stdin, refused if FILE changed since TOKEN;
                                         committed when it lies in ~/.agents/state and that is a git repo
"""

import argparse
import fcntl
import hashlib
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

STATE_ROOT = Path(os.path.realpath(Path.home() / ".agents" / "state"))
LIMIT = 25 * 1024
SCHEMA = "agent-state/v2"
DATE = r"20\d\d-\d\d-\d\d"
DATED_HEADING = re.compile(rf"^#+ .*\b{DATE}\b")
DATED_ITEM = re.compile(rf"^\s*[-*] (\[[xX]\] )?[*_(\[]*{DATE}\b")


def token(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def findings(path):
    data = path.read_bytes()
    out = []
    if len(data) > LIMIT:
        out.append(f"{len(data) / 1024:.1f} KB, over the {LIMIT // 1024} KB limit: move finished topics to their homes and delete them")
    lines = data.decode("utf-8", "replace").splitlines()
    if f"schema: {SCHEMA}" not in lines[:10]:
        out.append(f"not on the current template ({SCHEMA}): ~/.agents/state/TEMPLATE.md")
    dated = [n for n, line in enumerate(lines, 1) if DATED_HEADING.match(line) or DATED_ITEM.match(line)]
    if dated:
        shown = ", ".join(map(str, dated[:5])) + (" ..." if len(dated) > 5 else "")
        out.append(f"{len(dated)} dated diary lines (lines {shown}): keep current state, not a log")
    return out


def check(files):
    bad = False
    for f in files:
        path = Path(f)
        if not path.is_file():
            print(f"{f}: missing", file=sys.stderr)
            bad = True
            continue
        for msg in findings(path):
            print(f"{f}: {msg}", file=sys.stderr)
            bad = True
    return 1 if bad else 0


def record(path):
    if STATE_ROOT not in path.parents or not (STATE_ROOT / ".git").exists():
        return
    rel = str(path.relative_to(STATE_ROOT))
    git = ["git", "-C", str(STATE_ROOT)]
    done = subprocess.run(git + ["add", "--", rel], capture_output=True, text=True)
    if done.returncode == 0:
        if subprocess.run(git + ["diff", "--cached", "--quiet", "--", rel]).returncode == 0:
            return
        msg = f"state: {path.parent.name}"
        done = subprocess.run(git + ["commit", "-q", "--only", "-m", msg, "--", rel], capture_output=True, text=True)
    if done.returncode != 0:
        print(f"{path}: written but not committed: {done.stderr.strip()}", file=sys.stderr)


def write(file, expect, content):
    path = Path(os.path.realpath(file))
    if not content.strip():
        print(f"{file}: refused, the new content is empty", file=sys.stderr)
        return 2
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        if token(path) != expect:
            print(f"{file}: refused, it changed since it was read; read it again and redo the edit", file=sys.stderr)
            return 3
        mode = path.stat().st_mode & 0o777
        tmp = tempfile.NamedTemporaryFile("wb", dir=path.parent, prefix=".state-", delete=False)
        try:
            with tmp:
                tmp.write(content.encode("utf-8"))
            os.chmod(tmp.name, mode)
            os.replace(tmp.name, path)
        except BaseException:
            os.unlink(tmp.name)
            raise
        record(path)
    finally:
        os.close(fd)
    for msg in findings(path):
        print(f"{file}: {msg}", file=sys.stderr)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check").add_argument("files", nargs="+")
    sub.add_parser("hash").add_argument("file")
    w = sub.add_parser("write")
    w.add_argument("file")
    w.add_argument("--expect", required=True)
    args = parser.parse_args(argv)
    if args.cmd == "check":
        return check(args.files)
    if args.cmd == "hash":
        print(token(Path(args.file)))
        return 0
    return write(args.file, args.expect, sys.stdin.read())


if __name__ == "__main__":
    sys.exit(main())
