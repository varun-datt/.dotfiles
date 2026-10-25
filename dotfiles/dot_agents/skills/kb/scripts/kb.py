#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Search the wiki, work knowledge and product repos named in a sources file, through one contract.

Usage:
    kb.py search QUERY [--source NAME ...] [--mode auto|fused|regex|lex|sem|hybrid] [--limit N] [--json]
    kb.py index [--source NAME ...]     build or refresh ck's index of each folder (default: every source)
    kb.py sources

Sources come from $KB_SOURCES, else ~/.config/kb/sources.json:
    {"sources": [{"name": "wiki", "root": "~/sandbox/wiki"}, {"name": "my-service", "root": "~/src/my-service"}]}
A source may add "paths": ["docs", "notes"] to search only those parts of its root.
Without --source, search covers only the sources whose root holds the current folder, so content
from one space does not leak into another; outside every source, name the ones to search.
ck keeps one index per folder (the root, or each folder in paths) under $KB_INDEX_DIR, else
~/.cache/kb/ck, and writes nothing into the folder. A folder without an index yet, and a file listed
in paths, are searched by regex instead.

Each hit is {source, path, line, end, title, snippet, score, engines}; path is relative to the source root.
Modes:
    auto    by the query's shape: a regex goes to regex; up to three words to regex and lex; a
            longer message to sem (the default)
    regex   ripgrep, case-insensitive; a query that is not a valid regex is searched as fixed text
    lex     ck's BM25        sem  ck's embeddings        hybrid  ck's regex plus embeddings
    fused   regex and sem merged by reciprocal rank
Without ck, every mode that needs it falls back to regex. ck is found through $KB_CK, else on PATH.
Results merge across engines and sources by reciprocal rank, k=60.
"""
import argparse, glob, json, os, re, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

RRF_K = 60
MODES = ("auto", "fused", "regex", "lex", "sem", "hybrid")
SKIP = ("!.git/", "!.ck/", "!node_modules/")
REGEX_SHAPE = re.compile(r"\||\\[bdswBDSW.]|\.\*|\.\+|^\^|\$$")
INDEX_MARKER = "root_path"  # ck 0.8.1 records the indexed folder in this file of a relocated index


def load_sources(path=None):
    path = path or os.environ.get("KB_SOURCES") or os.path.expanduser("~/.config/kb/sources.json")
    with open(path) as f:
        data = json.load(f)
    return [{"name": s["name"], "root": os.path.realpath(os.path.expanduser(s["root"])), "paths": s.get("paths") or ["."]}
            for s in data["sources"]]


def ck_binary():
    return os.environ.get("KB_CK") or shutil.which("ck")


def index_base():
    return os.path.realpath(os.path.expanduser(os.environ.get("KB_INDEX_DIR") or "~/.cache/kb/ck"))


def ck_cmd(ck, opts, folder, query=None):
    """Run ck on exactly one folder: given several, ck indexes their common parent."""
    base = index_base()
    os.makedirs(base, exist_ok=True)
    cmd = [ck, "--hidden", "--no-ckignore", *opts, "--", *([] if query is None else [query]), folder]
    return subprocess.run(cmd, cwd=folder, env={**os.environ, "CK_INDEX_DIR": base}, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL)


def index_of(folder):
    """The folder's own ck index, or None; ck names it <basename>-<hash> under the base."""
    for d in glob.glob(os.path.join(glob.escape(index_base()), glob.escape(os.path.basename(folder)) + "-*")):
        try:
            with open(os.path.join(d, INDEX_MARKER)) as f:
                if f.read().strip() == folder:
                    return d
        except OSError:
            continue
    return None


def folders_and_files(src):
    dirs, files = [], []
    for p in src.get("paths") or ["."]:
        full = os.path.realpath(os.path.join(src["root"], p))
        (dirs if os.path.isdir(full) else files).append(full)
    return dirs, files


def title_of(abs_path):
    name = os.path.basename(abs_path)
    if not abs_path.endswith(".md"):
        return name
    try:
        with open(abs_path, errors="ignore") as f:
            head = f.read(4000)
    except OSError:
        return name
    m = re.search(r"^title:\s*[\"']?(.+?)[\"']?\s*$", head, re.M) or re.search(r"^#\s+(.+)$", head, re.M)
    return m.group(1).strip() if m else name


def run_rg(query, root, limit, paths=(".",)):
    base = ["rg", "--json", "-i", "--hidden", *sum((["-g", g] for g in SKIP), [])]
    out = subprocess.run([*base, "-e", query, *paths], cwd=root, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if out.returncode == 2 and "regex parse error" in out.stderr:
        out = subprocess.run([*base, "-F", "-e", query, *paths], cwd=root, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    files = {}
    for line in out.stdout.splitlines():
        r = json.loads(line)
        if r.get("type") != "match":
            continue
        d = r["data"]
        rel = os.path.normpath(d["path"]["text"])
        hit = files.setdefault(rel, {"path": rel, "line": d["line_number"], "end": d["line_number"],
                                     "snippet": d["lines"].get("text", "").strip()[:240], "count": 0})
        hit["count"] += 1
    ranked = sorted(files.values(), key=lambda h: (-h["count"], h["path"]))[:limit]
    return [{**h, "score": float(h.pop("count"))} for h in ranked]


def run_ck(mode, query, root, folder, limit, ck):
    out = ck_cmd(ck, [f"--{mode}", "--jsonl", "--topk", str(limit * 3), "--threshold", "0"], folder, query)
    seen, hits = set(), []
    for line in out.stdout.splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        rel = os.path.relpath(os.path.realpath(os.path.join(folder, r["path"])), root)
        if rel in seen:
            continue
        seen.add(rel)
        span = r.get("span") or {}
        hits.append({"path": rel, "line": span.get("line_start"), "end": span.get("line_end"),
                     "snippet": " ".join((r.get("snippet") or "").split())[:240], "score": float(r.get("score") or 0)})
    return hits[:limit]


def fuse(rankings):
    """Merge ranked lists of hits by reciprocal rank; the first list's line and snippet win."""
    merged = {}
    for engine, hits in rankings:
        for rank, h in enumerate(hits, 1):
            key = (h["source"], h["path"])
            m = merged.setdefault(key, {**h, "score": 0.0, "engines": []})
            m["score"] += 1 / (RRF_K + rank)
            if engine not in m["engines"]:
                m["engines"].append(engine)
    return sorted(merged.values(), key=lambda h: -h["score"])


def looks_like_regex(query):
    words = query.split()
    if len(words) > 6:
        return False
    return bool(REGEX_SHAPE.search(query)) or (len(words) == 1 and bool(re.search(r"[\[\](){}]", query)))


def engines_for(query, mode, ck):
    if mode == "auto":
        if looks_like_regex(query):
            wanted = ["regex"]
        elif len(query.split()) <= 3:
            wanted = ["regex", "lex"]
        else:
            wanted = ["sem"]
    else:
        wanted = {"fused": ["regex", "sem"]}.get(mode, [mode])
    return wanted if ck else ["regex"]


def plan(query, sources, mode, ck):
    """Jobs of (source, engine, folder): ck once per indexed folder, regex once per source. When ck
    cannot cover a source (a listed file, or a folder not indexed yet), regex runs over it too."""
    engines = engines_for(query, mode, ck)
    jobs, unindexed = [], []
    for src in sources:
        dirs, files = folders_and_files(src)
        ready = [d for d in dirs if index_of(d)] if engines != ["regex"] else []
        missing = [d for d in dirs if d not in ready] if engines != ["regex"] else []
        unindexed += [os.path.join(src["name"], os.path.relpath(d, src["root"])) for d in missing]
        for engine in engines:
            jobs += [(src, engine, None)] if engine == "regex" else [(src, engine, d) for d in ready]
        if "regex" not in engines and (missing or files):
            jobs.append((src, "regex", None))
    return jobs, unindexed


def search(query, sources, mode="auto", limit=10):
    if mode not in MODES:
        raise ValueError(f"mode is one of {', '.join(MODES)}")
    ck = ck_binary()
    jobs, _ = plan(query, sources, mode, ck)

    def one(job):
        src, engine, folder = job
        found = run_rg(query, src["root"], limit, src.get("paths") or ["."]) if engine == "regex" else run_ck(engine, query, src["root"], folder, limit, ck)
        return (src["name"], engine), [{**h, "source": src["name"]} for h in found]

    with ThreadPoolExecutor(max_workers=max(1, min(8, len(jobs)))) as pool:
        per_job = list(pool.map(one, jobs))
    merged = {}
    for key, found in per_job:
        merged.setdefault(key, []).extend(found)
    rankings = [(engine, sorted(found, key=lambda h: -h["score"])[:limit]) for (_, engine), found in merged.items()]
    hits = fuse(rankings)[:limit]
    for h in hits:
        h["title"] = title_of(os.path.join(next(s["root"] for s in sources if s["name"] == h["source"]), h["path"]))
    return [{k: h.get(k) for k in ("source", "path", "line", "end", "title", "snippet", "score", "engines")} for h in hits]


def index(sources, ck, out):
    failed = 0
    for src in sources:
        for folder in folders_and_files(src)[0]:
            t0 = time.monotonic()
            r = ck_cmd(ck, ["--index"], folder)
            ok = r.returncode == 0 and index_of(folder) is not None
            failed += not ok
            state = "indexed" if ok else "FAILED " + " ".join(r.stderr.split())[-200:]
            print(f"{src['name']}\t{os.path.relpath(folder, src['root'])}\t{state}\t{time.monotonic() - t0:.1f}s", file=out, flush=True)
    return 1 if failed else 0


def pick(sources, names, parser):
    if not names:
        return sources
    unknown = set(names) - {s["name"] for s in sources}
    if unknown:
        parser.error(f"unknown source: {', '.join(sorted(unknown))}")
    return [s for s in sources if s["name"] in names]


def holding(sources, folder):
    folder = os.path.realpath(folder)
    return [s for s in sources if os.path.commonpath([folder, s["root"]]) == s["root"]]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--source", action="append", help="a source name; repeat for more; default: the sources holding the current folder")
    s.add_argument("--mode", default="auto", choices=MODES)
    s.add_argument("--limit", type=int, default=10)
    s.add_argument("--json", action="store_true")
    s.add_argument("--sources-file")
    ix = sub.add_parser("index")
    ix.add_argument("--source", action="append", help="a source name; repeat for more; default all")
    ix.add_argument("--sources-file")
    sub.add_parser("sources").add_argument("--sources-file")
    a = p.parse_args(argv)
    sources = load_sources(a.sources_file)
    if a.cmd == "sources":
        for src in sources:
            print(f"{src['name']}\t{src['root']}")
        return 0
    if a.cmd == "index":
        ck = ck_binary()
        if not ck:
            p.exit(1, "kb: ck not found, so there is nothing to index\n")
        return index(pick(sources, a.source, p), ck, sys.stdout)
    if a.source:
        sources = pick(sources, a.source, p)
    else:
        names = ", ".join(s["name"] for s in sources)
        sources = holding(sources, os.getcwd())
        if not sources:
            p.exit(2, f"kb: the current folder is in none of the sources; name the ones to search with --source ({names})\n")
    if a.mode != "regex" and not ck_binary():
        print("kb: ck not found, so only regex runs", file=sys.stderr)
    unindexed = plan(a.query, sources, a.mode, ck_binary())[1]
    if unindexed:
        print(f"kb: searched by regex only, until `kb.py index` covers them: {', '.join(unindexed)}", file=sys.stderr)
    hits = search(a.query, sources, a.mode, a.limit)
    if a.json:
        print(json.dumps(hits, indent=1))
    else:
        for h in hits:
            print(f"{h['source']}:{h['path']}:{h['line']}  {h['title']} — {h['snippet'][:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
