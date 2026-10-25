#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Block a commit that adds an employer identifier or a secret to a repository that must not hold one.

Usage:
    guard.py [--staged] [--config PATH]      check the staged changes (what a pre-commit hook runs)
    guard.py --files FILE...                 check whole files instead

The block lists live outside every repository, in $COMMIT_GUARD_CONFIG or
~/.config/commit-guard/config.json:
    {"pattern_files": ["~/.config/amc/redaction-patterns.json"],
     "name_files": [{"path": "~/work/workspace.repos", "column": 1}],
     "url_files": [{"path": "~/work/workspace.repos", "column": 2}],
     "allow": ["a word a list blocks by mistake"],
     "gitleaks": true}
pattern_files hold [pattern, replacement] pairs, matched as whole words. name_files and url_files are
whitespace-separated columns; a name blocks itself, a URL blocks its host and organisation path.
Findings name the file, the line and the list, never the matched text, so a transcript stays clean.
"""
import argparse, json, os, re, shutil, subprocess, sys
from urllib.parse import urlparse

DEFAULT_CONFIG = "~/.config/commit-guard/config.json"


def expand(p):
    return os.path.expanduser(os.path.expandvars(p))


def column_values(spec):
    with open(expand(spec["path"])) as f:
        rows = [l.split() for l in f if l.strip() and not l.lstrip().startswith("#")]
    return [r[spec.get("column", 1) - 1] for r in rows if len(r) >= spec.get("column", 1)]


def org_paths(url):
    """dev.azure.com/org, github.com/org or org.visualstudio.com, from https or ssh remotes."""
    if url.startswith("git@") or re.match(r"^[\w.-]+@[\w.-]+:", url):
        host, _, rest = url.split("@", 1)[1].partition(":")
        parts = [p for p in re.sub(r"^v3/", "", rest).split("/") if p]
    else:
        u = urlparse(url)
        host, parts = u.hostname or "", [p for p in u.path.split("/") if p]
    out = set()
    if host.endswith(".visualstudio.com"):
        out.add(host)
    elif parts:
        out.add(f"{host.removeprefix('ssh.')}/{parts[0]}")
    return out


def matchers(cfg):
    allow = {a.lower() for a in cfg.get("allow", [])}
    rules = []
    for pf in cfg.get("pattern_files", []):
        with open(expand(pf)) as f:
            for pair in json.load(f):
                pat = pair[0] if isinstance(pair, list) else pair
                rules.append(("redaction pattern", re.compile(rf"\b(?:{pat})\b", re.I)))
    for spec in cfg.get("name_files", []):
        for name in column_values(spec):
            if name.lower() not in allow:
                rules.append(("repository name", re.compile(rf"(?<![\w-]){re.escape(name)}(?![\w-])", re.I)))
    for spec in cfg.get("url_files", []):
        for path in sorted({p for url in column_values(spec) for p in org_paths(url)}):
            if path.lower() not in allow:
                rules.append(("organisation URL", re.compile(re.escape(path), re.I)))
    return rules


def staged_lines():
    diff = subprocess.run(["git", "diff", "--cached", "-U0", "--no-color", "--diff-filter=ACMR"], capture_output=True,
                          text=True, check=True, stdin=subprocess.DEVNULL).stdout
    path, line = "?", 0
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            path = raw[6:] if raw.startswith("+++ b/") else raw[4:]
        elif raw.startswith("@@"):
            line = int(re.search(r"\+(\d+)", raw).group(1))
        elif raw.startswith("+"):
            yield path, line, raw[1:]
            line += 1


def file_lines(files):
    for p in files:
        with open(p, errors="ignore") as f:
            for i, text in enumerate(f, 1):
                yield p, i, text


def findings(lines, rules):
    for path, line, text in lines:
        for kind, rx in rules:
            if rx.search(text) or rx.search(path):
                yield path, line, kind
                break


def gitleaks():
    exe = shutil.which("gitleaks")
    cmd = [exe] if exe else None
    if not cmd and shutil.which("mise"):
        v = subprocess.run(["mise", "ls", "--installed", "gitleaks"], capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout.split()
        cmd = ["mise", "x", f"gitleaks@{v[1]}", "--", "gitleaks"] if len(v) >= 2 else None
    if not cmd:
        return "gitleaks is not installed (mise use -g gitleaks)"
    r = subprocess.run([*cmd, "git", "--staged", "--redact", "--no-banner", "--log-level", "warn"], capture_output=True, text=True,
                       stdin=subprocess.DEVNULL)
    return None if r.returncode == 0 else "gitleaks found a secret in the staged changes (run it with --verbose to see where)"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--staged", action="store_true")
    p.add_argument("--files", nargs="+")
    p.add_argument("--config", default=os.environ.get("COMMIT_GUARD_CONFIG", DEFAULT_CONFIG))
    a = p.parse_args(argv)
    try:
        with open(expand(a.config)) as f:
            cfg = json.load(f)
        rules = matchers(cfg)
    except (OSError, ValueError, IndexError) as e:
        print(f"commit-guard: cannot read its block lists ({e}); refusing the commit. Config: {a.config}", file=sys.stderr)
        return 2
    found = list(findings(file_lines(a.files) if a.files else staged_lines(), rules))
    for path, line, kind in found:
        print(f"commit-guard: {path}:{line} matches a {kind}", file=sys.stderr)
    problem = None if a.files or not cfg.get("gitleaks", True) else gitleaks()
    if problem:
        print(f"commit-guard: {problem}", file=sys.stderr)
    if found:
        print("commit-guard: work identifiers belong in the work knowledge repository, not here; "
              "a false positive goes in the config's allow list.", file=sys.stderr)
    return 1 if found or problem else 0


if __name__ == "__main__":
    sys.exit(main())
