#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Search the wiki, work knowledge and product repos named in a sources file, through one contract.

Usage:
    kb.py search QUERY [--source NAME ...] [--mode auto|fused|regex|lex|sem|hybrid] [--kind KIND ...] [--limit N] [--json]
    kb.py index [--source NAME ...]     build or refresh ck's index of each folder (default: every source)
    kb.py sources [--json]              name and root per line; --json gives the sources file's shape, each source resolved

Sources come from $KB_SOURCES, else ~/.config/kb/sources.json:
    {"sources": [{"name": "wiki", "root": "~/sandbox/wiki"}, {"name": "my-service", "root": "~/src/my-service"}]}
A source may add "paths": ["docs", "notes"] to search only those parts of its root, and
"exclude": ["tests/fixtures"] to skip folders under its root, and "kinds": {"exports/*": "data"} to set
the kind of the files whose root-relative path matches a glob (* crosses folders; the first match wins).
Without --source, search covers only the sources whose root holds the current folder, so content
from one space does not leak into another; outside every source, name the ones to search.
ck keeps one index per folder (the root, or each folder in paths) under $KB_INDEX_DIR, else
~/.cache/kb/ck, and writes nothing into the folder. A folder without an index yet, and a file listed
in paths, are searched by regex instead.

Each hit is {source, path, line, end, title, snippet, score, engines, kind}; path is relative to the source root.
kind is one of note, code, test, data: the source's "kinds" glob that matches first, else
    note    .md .markdown .mdx .rst .adoc .txt .org .html .htm, and README, LICENSE, CHANGELOG,
            CONTRIBUTING, NOTICE, AUTHORS without an extension
    test    any other file under a test, tests, __tests__, spec or specs folder, or named test_*,
            *_test.*, *.test.*, *.spec.*, *Test.*, *Tests.* or conftest.py
    data    .json .jsonl .ndjson .yaml .yml .toml .csv .tsv .xml .ini .cfg .conf .properties .lock,
            images, media, archives and databases, and a name that starts with a dot and has no other extension
    code    everything else, a file with no extension included (Makefile, Dockerfile, scripts)
--kind (repeat, or comma-separate) keeps only those kinds, before any cut: each engine ranks deep enough to hold
the limit in those kinds (ck is asked for four times as many until it does or runs out), the hits fuse at their
unfiltered ranks, and the other kinds drop after fusion, so the kept hits keep their unfiltered order; a hit found
only below the unfiltered pool scores 0 and comes after them.
Modes:
    auto    by the query's shape: a regex goes to regex; up to three words to regex and lex; a
            longer message to sem (the default)
    regex   ripgrep, case-insensitive; a query that is not a valid regex is searched as fixed text
    lex     ck's BM25        sem  ck's embeddings        hybrid  ck's regex plus embeddings
    fused   regex and sem merged by reciprocal rank
Without ck, every mode that needs it falls back to regex. ck is found through $KB_CK, else on PATH.
Each engine retrieves up to 50 candidates (more when --limit asks for more), whatever the limit.
Results merge across engines and sources by reciprocal rank, k=60; then a hit whose title (front-matter
title, first heading, else file name) holds half or more of the query's content words scores x1.2; the
limit cuts that ranking last.
"""
import argparse, fnmatch, glob, json, os, re, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

RRF_K = 60
TITLE_BOOST = 1.2
# Each engine's candidates, whatever the limit, so the boost and fusion rank the same pool and the limit cuts last.
POOL = 50
STOP = frozenset("a an the of for to in on and or is are was do does did how what which why when where who can "
                 "should we our it this that with by from at be as not i you very".split())
WORD = re.compile(r"[^\W_]+")
MODES = ("auto", "fused", "regex", "lex", "sem", "hybrid")
SKIP = ("!.git/", "!.ck/", "!node_modules/")
REGEX_SHAPE = re.compile(r"\||\\[bdswBDSW.]|\.\*|\.\+|^\^|\$$")
INDEX_MARKER = "root_path"  # ck 0.8.1 records the indexed folder in this file of a relocated index
# ck 0.8.1's default .ckignore, plus *.jsonl; passed as --exclude because --no-ckignore drops the file
CK_EXCLUDES = ("*.png", "*.jpg", "*.jpeg", "*.gif", "*.bmp", "*.svg", "*.ico", "*.webp", "*.tiff", "*.mp4", "*.avi",
               "*.mov", "*.mkv", "*.wmv", "*.flv", "*.webm", "*.mp3", "*.wav", "*.flac", "*.aac", "*.ogg", "*.m4a",
               "*.exe", "*.dll", "*.so", "*.dylib", "*.a", "*.lib", "*.obj", "*.o", "*.zip", "*.tar", "*.tar.gz",
               "*.tgz", "*.rar", "*.7z", "*.bz2", "*.gz", "*.db", "*.sqlite", "*.sqlite3", "*.parquet", "*.arrow",
               "*.json", "*.yaml", "*.yml", "*.jsonl")
FIELDS = ("source", "path", "line", "end", "title", "snippet", "score", "engines", "kind")
KINDS = ("note", "code", "test", "data")
NOTE_EXT = frozenset(".md .markdown .mdx .rst .adoc .txt .org .html .htm".split())
NOTE_NAMES = frozenset("README LICENSE CHANGELOG CONTRIBUTING NOTICE AUTHORS".split())
DATA_EXT = frozenset(".json .jsonl .ndjson .yaml .yml .toml .csv .tsv .xml .ini .cfg .conf .properties .lock .png .jpg "
                     ".jpeg .gif .bmp .svg .ico .webp .tiff .pdf .mp4 .avi .mov .mkv .webm .mp3 .wav .flac .ogg .m4a "
                     ".zip .tar .gz .tgz .bz2 .7z .rar .db .sqlite .sqlite3 .parquet .arrow".split())
TEST_DIRS = frozenset("test tests __tests__ spec specs".split())
TEST_NAMES = ("test_*", "*_test.*", "*.test.*", "*.spec.*", "*Test.*", "*Tests.*", "conftest.py")


def kind_of(path, overrides=()):
    """note, code, test or data for a root-relative path; overrides are (glob, kind) pairs, the first match wins."""
    for pattern, kind in overrides.items() if isinstance(overrides, dict) else overrides:
        if fnmatch.fnmatchcase(path, pattern):
            return kind
    parts = path.replace(os.sep, "/").split("/")
    name = parts[-1]
    ext = os.path.splitext(name)[1].lower()
    if ext in NOTE_EXT or (not ext and name.upper() in NOTE_NAMES):
        return "note"
    if TEST_DIRS.intersection(parts[:-1]) or any(fnmatch.fnmatchcase(name, t) for t in TEST_NAMES):
        return "test"
    if ext in DATA_EXT or (not ext and name.startswith(".")):
        return "data"
    return "code"


def kind_overrides(kinds, where):
    if not isinstance(kinds, dict):
        raise SystemExit(f"kb: {where}: kinds is an object of path glob to kind")
    bad = {p: k for p, k in kinds.items() if k not in KINDS}
    if bad:
        raise SystemExit(f"kb: {where}: unknown kind {', '.join(f'{k!r} for {p!r}' for p, k in bad.items())}; use one of {', '.join(KINDS)}")
    return list(kinds.items())


def load_sources(path=None):
    path = path or os.environ.get("KB_SOURCES") or os.path.expanduser("~/.config/kb/sources.json")
    with open(path) as f:
        data = json.load(f)
    return [{"name": s["name"], "root": os.path.realpath(os.path.expanduser(s["root"])), "paths": s.get("paths") or ["."],
             "exclude": [os.path.normpath(e).strip("/") for e in s.get("exclude") or []],
             "kinds": kind_overrides(s.get("kinds") or {}, f"{path}: source {s['name']}")}
            for s in data["sources"]]


def ck_binary():
    return os.environ.get("KB_CK") or shutil.which("ck")


def index_base():
    return os.path.realpath(os.path.expanduser(os.environ.get("KB_INDEX_DIR") or "~/.cache/kb/ck"))


def ck_cmd(ck, opts, folder, query=None, exclude=()):
    """Run ck on exactly one folder: given several, ck indexes their common parent."""
    base = index_base()
    os.makedirs(base, exist_ok=True)
    cmd = [ck, "--hidden", "--no-ckignore", *sum((["--exclude", p] for p in (*CK_EXCLUDES, *exclude)), []), *opts, "--",
           *([] if query is None else [query]), folder]
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


def ck_excludes(exclude, root, folder):
    """The root-relative excluded folders that lie inside folder, anchored there, as ck matches them."""
    rels = (os.path.relpath(os.path.join(root, e), folder) for e in exclude)
    return ["/" + r for r in rels if r != os.curdir and not r.startswith(os.pardir)]


def under(path, folders):
    return any(path == f or path.startswith(f + os.sep) for f in folders)


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


def title_matches(query, title):
    """Half or more of the query's content words (over two letters, not stop words) are in the title; a
    trailing s is dropped when the plural is not."""
    terms = [w for w in WORD.findall(query.lower()) if len(w) > 2 and w not in STOP]
    words = set(WORD.findall((title or "").lower()))
    return bool(terms) and 2 * sum(w in words or w.rstrip("s") in words for w in terms) >= len(terms)


def run_rg(query, root, limit, paths=(".",), exclude=(), keep=None):
    base = ["rg", "--json", "-i", "--hidden", *sum((["-g", g] for g in (*SKIP, *(f"!/{e}" for e in exclude))), [])]
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
    ranked = through(sorted(files.values(), key=lambda h: (-h["count"], h["path"])), limit, keep)
    return [{**h, "score": float(h.pop("count"))} for h in ranked]


def through(ranked, limit, keep=None):
    """The top limit hits; with keep, the unfiltered ranking down to the hit where limit of them pass keep."""
    if not keep:
        return ranked[:limit]
    kept = 0
    for n, h in enumerate(ranked, 1):
        kept += bool(keep(h["path"]))
        if kept >= limit:
            return ranked[:max(n, limit)]
    return ranked


def run_ck(mode, query, root, folder, limit, ck, exclude=(), keep=None):
    """ck's top chunks as one hit per file; with keep, ck is asked for more until limit files pass keep or ck runs out,
    and the hits that fail keep stay in, so their ranks are those of the unfiltered search."""
    topk = limit * 3
    while True:
        out = ck_cmd(ck, [f"--{mode}", "--jsonl", "--topk", str(topk), "--threshold", "0"], folder, query,
                     ck_excludes(exclude, root, folder))
        seen, hits, rows = set(), [], 0
        for line in out.stdout.splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            rows += 1
            rel = os.path.relpath(os.path.realpath(os.path.join(folder, r["path"])), root)
            # ck's --exclude keeps files out of an index; one built before the exclude still returns them.
            if rel in seen or under(rel, exclude):
                continue
            seen.add(rel)
            span = r.get("span") or {}
            hits.append({"path": rel, "line": span.get("line_start"), "end": span.get("line_end"),
                         "snippet": " ".join((r.get("snippet") or "").split())[:240], "score": float(r.get("score") or 0)})
        if not keep or sum(bool(keep(h["path"])) for h in hits) >= limit or rows < topk:
            return through(hits, limit, keep)
        topk *= 4


def fuse(rankings, depth=None):
    """Merge ranked lists of hits by reciprocal rank; the first list's line and snippet win. A rank below depth adds to
    deep, not score, so a list ranked deeper for a filter gives the hits above depth the scores of the unfiltered search."""
    merged = {}
    for engine, hits in rankings:
        for rank, h in enumerate(hits, 1):
            key = (h["source"], h["path"])
            m = merged.setdefault(key, {**h, "score": 0.0, "deep": 0.0, "engines": []})
            m["score" if depth is None or rank <= depth else "deep"] += 1 / (RRF_K + rank)
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


def search(query, sources, mode="auto", limit=10, kinds=None):
    if mode not in MODES:
        raise ValueError(f"mode is one of {', '.join(MODES)}")
    if kinds and set(kinds) - set(KINDS):
        raise ValueError(f"kind is one of {', '.join(KINDS)}")
    ck = ck_binary()
    jobs, _ = plan(query, sources, mode, ck)
    depth = max(limit, POOL)
    overrides = {}
    for s in sources:
        overrides.setdefault(s["name"], s.get("kinds") or ())
    keeper = lambda name: (lambda path: kind_of(path, overrides[name]) in kinds) if kinds else None  # noqa: E731

    def one(job):
        src, engine, folder = job
        keep = keeper(src["name"])
        if engine == "regex":
            found = run_rg(query, src["root"], depth, src.get("paths") or ["."], src.get("exclude") or [], keep=keep)
        else:
            found = run_ck(engine, query, src["root"], folder, depth, ck, src.get("exclude") or [], keep=keep)
        return (src["name"], engine), [{**h, "source": src["name"]} for h in found]

    with ThreadPoolExecutor(max_workers=max(1, min(8, len(jobs)))) as pool:
        per_job = list(pool.map(one, jobs))
    merged = {}
    for (_, engine), found in per_job:
        best = merged.setdefault(engine, {})
        for h in found:
            key = (h["source"], h["path"])
            if key not in best or h["score"] > best[key]["score"]:
                best[key] = h
    rankings = [(engine, sorted(best.values(), key=lambda h: -h["score"])[:None if kinds else depth])
                for engine, best in merged.items()]
    roots = {}
    for s in sources:
        roots.setdefault(s["name"], s["root"])
    fused = []
    for h in fuse(rankings, depth):
        h["kind"] = kind_of(h["path"], overrides[h["source"]])
        if kinds and h["kind"] not in kinds:
            continue
        h["title"] = title_of(os.path.join(roots[h["source"]], h["path"]))
        if title_matches(query, h["title"]):
            h["score"] *= TITLE_BOOST
            h["deep"] *= TITLE_BOOST
        fused.append(h)
    hits = sorted(fused, key=lambda h: (-h["score"], 0 if h["score"] else -h["deep"]))[:limit]
    return [{k: h.get(k) for k in FIELDS} for h in hits]


def index(sources, ck, out):
    failed = 0
    for src in sources:
        for folder in folders_and_files(src)[0]:
            t0 = time.monotonic()
            r = ck_cmd(ck, ["--index"], folder, exclude=ck_excludes(src.get("exclude") or [], src["root"], folder))
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
    s.add_argument("--kind", action="append", metavar="KIND",
                   help=f"keep only these kinds ({', '.join(KINDS)}); repeat or comma-separate; applied before --limit")
    s.add_argument("--limit", type=int, default=10)
    s.add_argument("--json", action="store_true")
    s.add_argument("--sources-file")
    ix = sub.add_parser("index")
    ix.add_argument("--source", action="append", help="a source name; repeat for more; default all")
    ix.add_argument("--sources-file")
    so = sub.add_parser("sources")
    so.add_argument("--sources-file")
    so.add_argument("--json", action="store_true", help="print the sources file's shape, each source resolved")
    a = p.parse_args(argv)
    kinds = [k.strip() for v in getattr(a, "kind", None) or [] for k in v.split(",")]
    unknown_kinds = [k for k in kinds if k not in KINDS]
    if unknown_kinds:
        p.error(f"unknown kind: {', '.join(map(repr, unknown_kinds))}; use one of {', '.join(KINDS)}")
    sources = load_sources(a.sources_file)
    if a.cmd == "sources":
        if a.json:
            print(json.dumps({"sources": [{**s, "kinds": dict(s["kinds"])} for s in sources]}))
            return 0
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
    hits = search(a.query, sources, a.mode, a.limit, kinds or None)
    if a.json:
        print(json.dumps(hits, indent=1))
    else:
        for h in hits:
            print(f"{h['source']}:{h['path']}:{h['line']}  {h['title']} — {h['snippet'][:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
