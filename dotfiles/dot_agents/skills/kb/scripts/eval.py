#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Score search engines on the mock cases, for every space and caller, and guard a baseline.

Usage:
    eval.py [--engine kb:fused --engine kb:regex ...] [--by class] [--json OUT] [--compare RUN]
    eval.py --check                 exit 1 when the default engine falls below the baseline in any cell
    eval.py --write-baseline        record the engines just run as the baseline

Each cell reports hit@5, hit@1, hit@3 and latency. Given several engines, each after the first is paired
with the first, case by case by reciprocal rank, in a two-sided sign test over the cases that differ;
--compare RUN pairs each engine with the same engine in RUN, a run saved earlier with --json.

Engines:
    kb:<mode>     this skill's kb.py in that mode (fused, regex, lex, sem, hybrid)
    cmd:<command> any other tool that speaks kb's contract: run as `<command> QUERY SOURCE[,SOURCE]`
                  with KB_SOURCES set, printing a JSON list of {source, path, line, end, ...}
The corpus is copied to a temporary folder, which also holds its indexes, so nothing is written into
the fixtures or ~/.cache.
"""
import argparse, io, json, math, os, re, shlex, shutil, statistics, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")
BASELINE = os.path.join(HERE, "baseline.json")
sys.path.insert(0, HERE)
import kb  # noqa: E402


def corpus_sources(corpus):
    """Each top-level folder is a source, except product/, whose repos are one source each."""
    out = {}
    for name in sorted(os.listdir(corpus)):
        full = os.path.join(corpus, name)
        if not os.path.isdir(full):
            continue
        if name == "product":
            for repo in sorted(os.listdir(full)):
                out[repo] = f"product/{repo}"
        else:
            out[name] = name
    return out


def anchor_line(path, anchor):
    with open(path, errors="ignore") as f:
        found = [i for i, l in enumerate(f.read().split("\n"), 1) if re.search(anchor, l)]
    return found[0] if len(found) == 1 else None


def engine_runner(spec, sources_file, sources):
    kind, _, arg = spec.partition(":")
    if kind == "kb":
        return lambda q, scope: kb.search(q, [s for s in sources if s["name"] in scope], arg, 10)
    if kind == "cmd":
        env = {**os.environ, "KB_SOURCES": sources_file}
        return lambda q, scope: json.loads(subprocess.run([*shlex.split(arg), q, ",".join(scope)], env=env, capture_output=True,
                                                          text=True, stdin=subprocess.DEVNULL, check=True).stdout)
    raise SystemExit(f"unknown engine {spec}: use kb:<mode> or cmd:<command>")


def score_case(case, hits, prefix, corpus):
    shown = [f"{prefix[h['source']]}/{h['path']}" for h in hits]
    rank = next((i + 1 for i, p in enumerate(shown) if any(p == e["path"] for e in case["expect"])), None)
    anchored = None
    if rank:
        hit, want = hits[rank - 1], next(e for e in case["expect"] if e["path"] == shown[rank - 1])
        if want.get("anchor"):
            at = anchor_line(os.path.join(corpus, want["path"]), want["anchor"])
            anchored = bool(at and hit.get("line") and hit["line"] <= at <= (hit.get("end") or hit["line"]))
    above = shown[: (rank or len(shown) + 1) - 1]
    violated = any(m in p for m in case.get("mustNot", []) for p in above)
    return {"rank": rank, "anchored": anchored, "mustNot_violated": violated}


def cell_summary(rows):
    n = len(rows)
    anchors = [r["anchored"] for r in rows if r["anchored"] is not None]
    return {"n": n, "hit1": sum(r["rank"] == 1 for r in rows), "hit3": sum(bool(r["rank"]) and r["rank"] <= 3 for r in rows),
            "hit5": sum(bool(r["rank"]) and r["rank"] <= 5 for r in rows),
            "mrr": round(sum(1 / r["rank"] for r in rows if r["rank"]) / n, 2) if n else 0,
            "anchor_ok": f"{sum(anchors)}/{len(anchors)}" if anchors else "-",
            "mustNot": sum(r["mustNot_violated"] for r in rows),
            "p50_ms": round(statistics.median(r["ms"] for r in rows)) if n else 0}


def group(rows, by):
    cells = {}
    for r in rows:
        cells.setdefault(f"{r['space']}/{r['caller']}" if by == "cell" else f"{r['caller']}/{r['class']}", []).append(r)
    return {"cells": {k: cell_summary(v) for k, v in sorted(cells.items())}, "all": cell_summary(rows),
            "misses": [r["id"] for r in rows if not r["rank"] or r["rank"] > 5]}


def run(engines):
    with open(os.path.join(FIXTURES, "cases.json")) as f:
        cases = json.load(f)["queries"]
    tmp = tempfile.mkdtemp(prefix="kb-eval-")
    saved_index_dir = os.environ.get("KB_INDEX_DIR")
    os.environ["KB_INDEX_DIR"] = os.path.join(tmp, "ck-index")
    try:
        corpus = os.path.join(tmp, "corpus")
        shutil.copytree(os.path.join(FIXTURES, "corpus"), corpus)
        prefix = corpus_sources(corpus)
        sources = [{"name": n, "root": os.path.realpath(os.path.join(corpus, p))} for n, p in prefix.items()]
        sources_file = os.path.join(tmp, "sources.json")
        with open(sources_file, "w") as f:
            json.dump({"sources": sources}, f)
        ck = kb.ck_binary()
        if ck and any(e.startswith("kb:") and e != "kb:regex" for e in engines):
            kb.index(sources, ck, io.StringIO())
        results = {}
        for spec in engines:
            go = engine_runner(spec, sources_file, sources)
            rows = []
            for c in cases:
                t0 = time.perf_counter()
                hits = go(c["q"], c["scope"])
                rows.append({**score_case(c, hits, prefix, os.path.realpath(os.path.join(FIXTURES, "corpus"))),
                             "ms": (time.perf_counter() - t0) * 1000, "space": c["space"], "caller": c["caller"],
                             "class": c["class"], "id": c["id"]})
            results[spec] = rows
        return results
    finally:
        if saved_index_dir is None:
            os.environ.pop("KB_INDEX_DIR", None)
        else:
            os.environ["KB_INDEX_DIR"] = saved_index_dir
        shutil.rmtree(tmp, ignore_errors=True)


def print_table(results):
    keys = sorted({k for r in results.values() for k in r["cells"]})
    engines = list(results)
    print("| cell | n | " + " | ".join(f"{e} hit@5" for e in engines) + " |")
    print("| --- | --- | " + " | ".join("---" for _ in engines) + " |")
    for k in keys + ["ALL"]:
        cells = [results[e]["all"] if k == "ALL" else results[e]["cells"].get(k, {}) for e in engines]
        print(f"| {k} | {cells[0].get('n', 0)} | " + " | ".join(f"{c.get('hit5', '-')} (top1 {c.get('hit1', '-')}, top3 {c.get('hit3', '-')}, "
                                                               f"{c.get('p50_ms', '-')} ms)" for c in cells) + " |")
    for e in engines:
        a = results[e]["all"]
        print(f"{e}: MRR {a['mrr']}, anchors {a['anchor_ok']}, mustNot violations {a['mustNot']}")


def ranks_of(rows):
    ranks = {}
    for r in rows:
        if r["id"] in ranks:
            raise SystemExit(f"case id {r['id']} appears twice, so runs cannot be paired")
        ranks[r["id"]] = r["rank"]
    return ranks


def sign_test(wins, losses):
    """Two-sided exact binomial sign test over the cases that differ; ties are dropped before it."""
    n, k = wins + losses, min(wins, losses)
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def paired(base, new):
    """Case by case by reciprocal rank, over the case ids both runs scored; a miss counts as 0."""
    rr = lambda rank: 1 / rank if rank else 0.0  # noqa: E731
    both = [i for i in new if i in base]
    wins = sum(rr(new[i]) > rr(base[i]) for i in both)
    losses = sum(rr(new[i]) < rr(base[i]) for i in both)
    return {"wins": wins, "losses": losses, "ties": len(both) - wins - losses, "p": sign_test(wins, losses),
            "only_base": sorted(i for i in base if i not in new), "only_new": sorted(i for i in new if i not in base)}


def print_paired(new_name, base_name, r):
    if r["wins"] + r["losses"] == 0:
        print(f"paired, {new_name} against {base_name}: no case differs ({r['ties']} tied), so the sign test has nothing to weigh: p = 1")
    else:
        print(f"paired, {new_name} against {base_name}: {r['wins']} better, {r['losses']} worse, {r['ties']} tied and dropped; "
              f"two-sided sign test p = {r['p']:.4g}")
    for side, ids in ((base_name, r["only_base"]), (new_name, r["only_new"])):
        if ids:
            print(f"  {len(ids)} case(s) only in {side}, not paired: {', '.join(ids)}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--engine", action="append")
    p.add_argument("--by", choices=["cell", "class"], default="cell")
    p.add_argument("--json")
    p.add_argument("--compare", metavar="RUN", help="a run saved with --json: pair each engine in both, case by case, with a sign test")
    p.add_argument("--check", action="store_true")
    p.add_argument("--write-baseline", action="store_true")
    a = p.parse_args(argv)
    earlier = None
    if a.compare:
        with open(a.compare) as f:
            earlier = json.load(f)
        if not isinstance(earlier, dict) or not all(isinstance(r, dict) and "ranks" in r for r in earlier.values()):
            raise SystemExit(f"{a.compare} has no per-case ranks: save the run with this eval.py's --json")
    base = None
    if os.path.exists(BASELINE):
        with open(BASELINE) as f:
            base = json.load(f)
    engines = a.engine or ([base["default"]] if a.check and base else [f"kb:{m}" for m in kb.MODES])
    if not kb.ck_binary():
        engines = [e for e in engines if not e.startswith("kb:") or e == "kb:regex"] or ["kb:regex"]
        print("ck not found: only regex runs", file=sys.stderr)
    rows = run(engines)
    results = {e: {**group(r, "cell"), "ranks": ranks_of(r)} for e, r in rows.items()}
    print_table(results)
    if a.by == "class":
        print()
        print_table({e: group(r, "class") for e, r in rows.items()})
    for e in engines[1:]:
        print_paired(e, engines[0], paired(results[engines[0]]["ranks"], results[e]["ranks"]))
    if earlier is not None:
        for e in engines:
            if e in earlier:
                print_paired(e, f"{e} in {a.compare}", paired(earlier[e]["ranks"], results[e]["ranks"]))
            else:
                print(f"paired: {e} is not in {a.compare}, so it is not compared")
    if a.json:
        with open(a.json, "w") as f:
            json.dump(results, f, indent=1)
    if a.write_baseline:
        out = base or {"default": "kb:auto", "engines": {}}
        for e, r in results.items():
            out["engines"][e] = {k: {"hit5": v["hit5"], "hit1": v["hit1"]} for k, v in r["cells"].items()}
        out["recorded"] = time.strftime("%Y-%m-%d")
        with open(BASELINE, "w") as f:
            json.dump(out, f, indent=1)
        print(f"baseline written for {', '.join(results)}")
    if a.check:
        if not base:
            raise SystemExit("no baseline.json yet: run with --write-baseline first")
        want = base["engines"][engines[0]]
        got = results[engines[0]]["cells"]
        drops = [f"{k}: hit@5 {got[k]['hit5']} < {v['hit5']}" for k, v in want.items() if got.get(k, {}).get("hit5", 0) < v["hit5"]]
        print("baseline: " + ("; ".join(drops) if drops else f"{engines[0]} holds every cell"))
        return 1 if drops else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
