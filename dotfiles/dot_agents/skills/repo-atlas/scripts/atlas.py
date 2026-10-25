#!/usr/bin/env python3
"""repo-atlas: keep a short, refreshable index of the git repositories under one folder.

  atlas.py refresh PARENT [--repos A,B] [--dry-run]
      git fetch every repo in parallel; pull --ff-only only when the tree is clean and on the
      default branch. Prints one JSON line per repo: before, after, and what was done.
  atlas.py facts PARENT --out DIR [--repos A,B]
      collect stable facts per repo into DIR/repos.json and DIR/repos.md (llms.txt shape).
      An entry is rebuilt only when the repo's structure fingerprint changed; hand-kept fields
      (area, pointers) are never overwritten.

Repos are the folders directly under PARENT that hold `.git` (a folder or a file).
Nothing here names any organisation; every path is an argument.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

MANIFESTS = (
    "package.json", "pnpm-workspace.yaml", "pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle",
    "go.mod", "Cargo.toml", "pyproject.toml", "requirements.txt", "setup.py", "Gemfile", "composer.json",
    "Dockerfile", "docker-compose.yml", "azure-pipelines.yml", "Makefile", "global.json", "Directory.Build.props",
    "catalog-info.yaml", "mkdocs.yml",
)
LANGUAGE = (
    ("*.sln", ".NET"), ("*.csproj", ".NET"), ("pom.xml", "Java (Maven)"), ("build.gradle", "Java/Kotlin (Gradle)"),
    ("build.gradle.kts", "Kotlin (Gradle)"), ("package.json", "JavaScript/TypeScript"), ("go.mod", "Go"),
    ("Cargo.toml", "Rust"), ("pyproject.toml", "Python"), ("requirements.txt", "Python"), ("setup.py", "Python"),
)
HAND_KEPT = ("area", "summary", "pointers")
FACTS_VERSION = "3"
ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never", "GIT_OPTIONAL_LOCKS": "0"}


def git(repo: Path, *args: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), "-c", "core.fsmonitor=false", *args], capture_output=True,
                          text=True, stdin=subprocess.DEVNULL, env=ENV, timeout=timeout)


def out(repo: Path, *args: str) -> str:
    r = git(repo, *args)
    return r.stdout.strip() if r.returncode == 0 else ""


def repos(parent: Path, names: str | None) -> list[Path]:
    found = sorted(p for p in parent.iterdir() if p.is_dir() and (p / ".git").exists())
    if names:
        wanted = [n.strip() for n in names.split(",") if n.strip()]
        missing = [n for n in wanted if not (parent / n / ".git").exists()]
        if missing:
            raise SystemExit(f"repo-atlas: not repositories under {parent}: {', '.join(missing)}")
        return [parent / n for n in wanted]
    return found


def default_branch(repo: Path) -> str:
    head = out(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if head:
        return head.split("/", 1)[1]
    for name in ("main", "master", "develop"):
        if git(repo, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{name}").returncode == 0:
            return name
    return ""


def refresh_one(repo: Path, dry_run: bool) -> dict:
    row = {"repo": repo.name, "branch": out(repo, "branch", "--show-current"), "before": out(repo, "rev-parse", "--short", "HEAD")}
    row["default"] = default_branch(repo)
    dirty = bool(out(repo, "status", "--porcelain", "--untracked-files=no"))
    if dry_run:
        row["action"] = "dry-run"
    else:
        f = git(repo, "fetch", "--quiet", "--prune", "origin", timeout=180)
        if f.returncode:
            row.update(action="fetch-failed", error=f.stderr.strip().splitlines()[-1:] or [""])
            return row
        row["default"] = default_branch(repo)
        if dirty:
            row["action"] = "fetched; not pulled: uncommitted changes"
        elif not row["branch"] or row["branch"] != row["default"]:
            row["action"] = f"fetched; not pulled: on {row['branch'] or 'a detached HEAD'}, default is {row['default'] or 'unknown'}"
        else:
            p = git(repo, "pull", "--quiet", "--ff-only", timeout=180)
            row["action"] = "pulled" if p.returncode == 0 else "fetched; pull refused: " + (p.stderr.strip().splitlines() or [""])[-1]
    row["after"] = out(repo, "rev-parse", "--short", "HEAD")
    if row["action"] == "pulled" and row["after"] == row["before"]:
        row["action"] = "up to date"
    row["behind"] = out(repo, "rev-list", "--count", f"HEAD..origin/{row['default']}") if row["default"] else ""
    return row


def cmd_refresh(args: argparse.Namespace) -> int:
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        rows = list(pool.map(lambda r: refresh_one(r, args.dry_run), repos(args.parent, args.repos)))
    for row in rows:
        print(json.dumps(row))
    return 1 if any(r["action"] == "fetch-failed" for r in rows) else 0


def catalog(text: str) -> dict:
    """The handful of Backstage fields, read without a YAML library: first document only."""
    fields, section, key = {}, "", ""
    wanted = {("metadata", "name"), ("metadata", "description"), ("spec", "type"), ("spec", "lifecycle"),
              ("spec", "owner"), ("spec", "system")}
    for line in text.split("\n---")[0].splitlines():
        top = re.match(r"^(\w+):\s*$", line)
        if top:
            section, key = top.group(1), ""
            continue
        m = re.match(r"^  (\w+):\s*(.*?)\s*$", line)
        if m:
            key = m.group(1) if (section, m.group(1)) in wanted else ""
            if key:
                fields[key] = m.group(2).strip("'\"")
        elif key and re.match(r"^    \S", line):
            fields[key] = (fields[key] + " " + line.strip()).strip()
        else:
            key = ""
    names = [n.strip() for n in fields.get("description", "").split(",") if n.strip()]
    if len(names) > 1 and all(re.fullmatch(r"[a-z0-9][a-z0-9._-]*", n) for n in names):
        fields["components"] = names
        del fields["description"]
    return fields


def readme_purpose(repo: Path) -> str:
    for name in ("README.md", "readme.md", "README.MD", "README"):
        p = repo / name
        if p.is_file():
            text = p.read_text(encoding="utf-8", errors="replace")
            text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
            for block in re.split(r"\n\s*\n", text):
                block = block.strip()
                first = block.splitlines()[0].rstrip() if block else ""
                if block and not block.startswith(("#", "[!", "![", "<", "|", "```", "---", "[![", "TODO", ">")) \
                        and not first.endswith(":"):
                    text = re.sub(r"\s+", " ", block)
                    end = re.search(r"(?<=[.!?])\s", text[60:])
                    return (text[:60 + end.start()] if end else text)[:300]
    return ""


def fingerprint(repo: Path, tops: list[str], manifests: list[str]) -> str:
    h = hashlib.sha256((FACTS_VERSION + "\n" + "\n".join(tops)).encode())
    for m in manifests:
        h.update(out(repo, "rev-parse", f"HEAD:{m}").encode())
    return h.hexdigest()[:16]


def facts(repo: Path) -> dict:
    tracked = out(repo, "ls-tree", "--name-only", "HEAD").splitlines()
    tops = sorted(t for t in tracked if (repo / t).is_dir())
    manifests = sorted(t for t in tracked if t in MANIFESTS or t.endswith((".sln", ".csproj")))
    shallow = [t for t in out(repo, "ls-tree", "-r", "--name-only", "HEAD").splitlines() if t.count("/") <= 2]
    language = sorted({lang for pattern, lang in LANGUAGE for t in shallow if Path(t).match(pattern)})
    remote = re.sub(r"//[^/@]+@", "//", out(repo, "remote", "get-url", "origin"))
    cat = repo / "catalog-info.yaml"
    entry = {
        "name": repo.name,
        "path": repo.name,
        "remote": remote,
        "commit": out(repo, "rev-parse", "--short", "HEAD"),
        "commit_date": out(repo, "log", "-1", "--format=%cs"),
        "purpose": readme_purpose(repo),
        "catalog": catalog(cat.read_text(encoding="utf-8", errors="replace")) if "catalog-info.yaml" in tracked else {},
        "language": language,
        "manifests": manifests,
        "top_folders": tops,
        "agents_md": "AGENTS.md" in tracked,
        "fingerprint": fingerprint(repo, tops, manifests),
    }
    return entry


def render(entries: list[dict], parent: Path) -> str:
    lines = [f"# Repositories under {parent.name}", "",
             f"> {len(entries)} repositories. Facts are collected by script; `area` and `pointers` are kept by hand. "
             "If nothing here matches, search all repos.", ""]
    by_area: dict[str, list[dict]] = {}
    for e in entries:
        by_area.setdefault(e.get("area") or "Unsorted", []).append(e)
    for area in sorted(by_area):
        lines += [f"## {area}", ""]
        for e in by_area[area]:
            what = e.get("summary") or e["purpose"] or e["catalog"].get("description") or "no summary yet"
            extra = ", ".join(x for x in [", ".join(e["language"]), e["catalog"].get("type", ""),
                                           "has AGENTS.md" if e["agents_md"] else ""] if x)
            lines.append(f"- [{e['name']}]({e['path']}/): {what}" + (f" ({extra})" if extra else ""))
            for pointer in e.get("pointers", []):
                lines.append(f"  - {pointer}")
        lines.append("")
    return "\n".join(lines)


def cmd_facts(args: argparse.Namespace) -> int:
    args.out.mkdir(parents=True, exist_ok=True)
    store = args.out / "repos.json"
    old = {e["name"]: e for e in json.loads(store.read_text())["repos"]} if store.exists() else {}
    entries, rebuilt = [], []
    for repo in repos(args.parent, args.repos):
        new = facts(repo)
        prev = old.pop(repo.name, None)
        if prev and prev.get("fingerprint") == new["fingerprint"]:
            prev.update(commit=new["commit"], commit_date=new["commit_date"])
            entries.append(prev)
            continue
        for key in HAND_KEPT:
            if prev and key in prev:
                new[key] = prev[key]
        if prev:
            new["structure_changed_since"] = prev.get("commit", "")
        entries.append(new)
        rebuilt.append(repo.name)
    entries += old.values() if args.repos else []
    entries.sort(key=lambda e: e["name"])
    store.write_text(json.dumps({"generated": dt.date.today().isoformat(), "parent": args.parent.name,
                                 "repos": entries}, indent=1) + "\n")
    (args.out / "repos.md").write_text(render(entries, args.parent))
    print(json.dumps({"repos": len(entries), "rebuilt": rebuilt, "out": str(args.out)}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("refresh")
    r.add_argument("parent", type=Path)
    r.add_argument("--repos")
    r.add_argument("--jobs", type=int, default=8)
    r.add_argument("--dry-run", action="store_true")
    f = sub.add_parser("facts")
    f.add_argument("parent", type=Path)
    f.add_argument("--out", type=Path, required=True)
    f.add_argument("--repos")
    args = parser.parse_args(argv)
    args.parent = args.parent.expanduser().resolve()
    return cmd_refresh(args) if args.command == "refresh" else cmd_facts(args)


if __name__ == "__main__":
    sys.exit(main())
