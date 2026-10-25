#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Search the wiki, work knowledge and product repos named in a sources file, through one contract.

Usage:
    kb.py search QUERY [--source NAME ...] [--mode auto|fused|regex|lex|sem|hybrid] [--limit N] [--json]
    kb.py sources

Sources come from $KB_SOURCES, else ~/.config/kb/sources.json:
    {"sources": [{"name": "wiki", "root": "~/sandbox/wiki"}, {"name": "my-service", "root": "~/src/my-service"}]}
A source may add "paths": ["docs", "notes"] to search only those parts of its root; ck then keeps
one index inside each of them.

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
import argparse, json, os, re, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

RRF_K = 60
MODES = ("auto", "fused", "regex", "lex", "sem", "hybrid")
SKIP = ("!.git/", "!.ck/", "!node_modules/")
REGEX_SHAPE = re.compile(r"\||\\[bdswBDSW.]|\.\*|\.\+|^\^|\$$")


def load_sources(path=None):
    path = path or os.environ.get("KB_SOURCES") or os.path.expanduser("~/.config/kb/sources.json")
    with open(path) as f:
        data = json.load(f)
    return [{"name": s["name"], "root": os.path.realpath(os.path.expanduser(s["root"])), "paths": s.get("paths") or ["."]}
            for s in data["sources"]]


def ck_binary():
    return os.environ.get("KB_CK") or shutil.which("ck")


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


def run_ck(mode, query, root, limit, ck, paths=(".",)):
    cmd = [ck, f"--{mode}", "--jsonl", "--topk", str(limit * 3), "--threshold", "0", "--hidden", query, *paths]
    out = subprocess.run(cmd, cwd=root, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    seen, hits = set(), []
    for line in out.stdout.splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        rel = os.path.relpath(os.path.realpath(r["path"]), root)
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


def search(query, sources, mode="auto", limit=10):
    if mode not in MODES:
        raise ValueError(f"mode is one of {', '.join(MODES)}")
    ck = ck_binary()
    engines = engines_for(query, mode, ck)
    jobs = [(src, engine) for src in sources for engine in engines]

    def one(job):
        src, engine = job
        paths = src.get("paths") or ["."]
        found = run_rg(query, src["root"], limit, paths) if engine == "regex" else run_ck(engine, query, src["root"], limit, ck, paths)
        return engine, [{**h, "source": src["name"]} for h in found]

    with ThreadPoolExecutor(max_workers=max(1, min(8, len(jobs)))) as pool:
        rankings = list(pool.map(one, jobs))
    hits = fuse(rankings)[:limit]
    for h in hits:
        h["title"] = title_of(os.path.join(next(s["root"] for s in sources if s["name"] == h["source"]), h["path"]))
    return [{k: h.get(k) for k in ("source", "path", "line", "end", "title", "snippet", "score", "engines")} for h in hits]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--source", action="append", help="a source name; repeat for more; default all")
    s.add_argument("--mode", default="auto", choices=MODES)
    s.add_argument("--limit", type=int, default=10)
    s.add_argument("--json", action="store_true")
    s.add_argument("--sources-file")
    sub.add_parser("sources").add_argument("--sources-file")
    a = p.parse_args(argv)
    sources = load_sources(a.sources_file)
    if a.cmd == "sources":
        for src in sources:
            print(f"{src['name']}\t{src['root']}")
        return 0
    if a.source:
        unknown = set(a.source) - {s["name"] for s in sources}
        if unknown:
            p.error(f"unknown source: {', '.join(sorted(unknown))}")
        sources = [s for s in sources if s["name"] in a.source]
    if a.mode != "regex" and not ck_binary():
        print("kb: ck not found, so only regex runs", file=sys.stderr)
    hits = search(a.query, sources, a.mode, a.limit)
    if a.json:
        print(json.dumps(hits, indent=1))
    else:
        for h in hits:
            print(f"{h['source']}:{h['path']}:{h['line']}  {h['title']} — {h['snippet'][:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
