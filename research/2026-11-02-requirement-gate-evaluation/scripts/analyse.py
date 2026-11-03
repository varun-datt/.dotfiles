#!/usr/bin/env python3
"""Turn gate results into the evaluation's tables: per finding (Q1), controls (Q2), cost (Q3), new modules (Q4).

Reads items.json, items/<key>.map.json, items/<key>.gate.f2p.json and, where present, items/<key>.gate.p2p.json
(the PASS_TO_PASS verdicts with Stryker) and the .run.<phase>.json logs. Writes results.json and tables.md.

Rule variants: map (the INFERRED map), strict (only tests whose title or comments cite the MUST; a MUST with none
becomes a `none` line), and each again under SWE-bench's rule, where any non-pass on the base is a valid
FAIL_TO_PASS (swebench/harness/grading.py test_failed), against the gate's assertion-only rule (D4).
"""
import json, os, re, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
ITEMS = os.path.join(OUT, "items")

GENUINE = {"F2P passes on base", "P2P no killed mutant", "fails at head"}
ABSENT = {"F2P load on base (new module)", "F2P error on base (missing export)", "F2P error on base (other non-assertion)"}
NOT_GATE = {"unsupported runner (playwright)", "unsupported runner (live)", "map error", "environment"}
SIZES = json.load(open(os.path.join(OUT, "src_added_lines.json"))) if os.path.exists(os.path.join(OUT, "src_added_lines.json")) else {}
VARIANTS = (("map", {}), ("strict", {"strict": True}), ("map_swe", {"swe": True}), ("strict_swe", {"strict": True, "swe": True}))


def load(path):
    return json.load(open(path)) if os.path.exists(path) else None


def key(i):
    return f"{i['run']}__{i['item']}"


def classify(g, runner, base_status=None):
    """One test line's outcome in the gate's own words, sorted into kinds."""
    s, r = g["status"], g["reason"]
    if runner != "vitest":
        return f"unsupported runner ({runner})"
    if r.startswith(("missing at head", "ambiguous at head")):
        return "map error"
    if " at head" in r and not r.startswith(("passes on base", "fails on base")):
        if re.search(r"Cannot find (module|package)|ERR_MODULE_NOT_FOUND|Startup Error|No test files? found", r):
            return "environment"
        return "fails at head"
    if s == "pass":
        return "pass"
    if r.startswith("passes on base"):
        return "F2P passes on base"
    if r.startswith("load on base"):
        return "F2P load on base (new module)"
    if r.startswith(("error on base", "timeout on base")):
        if re.search(r"is not a (function|constructor)|does not provide an export|is not defined", r):
            return "F2P error on base (missing export)"
        return "F2P error on base (other non-assertion)"
    if r.startswith(("missing on base", "skipped on base", "ambiguous on base")):
        return "map error"
    if r.startswith("attribution unavailable"):
        return "P2P attribution unavailable"
    if r.startswith("killed none"):
        return "P2P no killed mutant"
    if r.startswith("Stryker timed out"):
        return "Stryker timed out"
    if r.startswith("Stryker failed"):
        return "Stryker failed"
    if r.startswith("covers no changed line"):
        return "P2P covers no changed line"
    if s == "not checked":
        return "P2P not checked"
    return "other: " + r[:60]


def test_kinds(m, gate, p2p, strict=False, swe=False):
    """{(must, test): kind} under one rule variant, plus the MUSTs left with no test (`none`)."""
    meta = {}
    for e in m["map"]:
        for t in e.get("tests") or []:
            meta[(str(e["must"]), f"{t['file']}::{t['name']}")] = (t.get("runner", "vitest"), bool(t.get("strict")))
    p2p_by = {(str(g["must"]), g["test"]): g for g in (p2p or {}).get("PASS_TO_PASS", [])}
    kinds = {}
    for kind in ("FAIL_TO_PASS", "PASS_TO_PASS"):
        for g in gate.get(kind, []):
            k = (str(g["must"]), g["test"])
            runner, is_strict = meta.get(k, ("vitest", False))
            if strict and not is_strict:
                continue
            if kind == "PASS_TO_PASS" and k in p2p_by and g["status"] in ("not checked", "pass"):
                g = p2p_by[k] if g["status"] == "not checked" else g
            c = classify(g, runner)
            if swe and c in ABSENT:
                c = "pass"
            kinds[k] = c
    musts = [str(e["must"]) for e in m["map"]]
    none = [n for n in musts if not any(k[0] == n for k in kinds)]
    return kinds, none


def finding_verdict(f, mf, kinds, none):
    """caught / MUST flagged / none only / flagged, not for this / miss, with the kinds behind it."""
    musts = [str(n) for n in (mf.get("musts") or [])]
    tests = set(mf.get("tests") or [])
    own = [c for (n, t), c in kinds.items() if t in tests]
    near = [c for (n, t), c in kinds.items() if n in musts and t not in tests]
    if any(c in GENUINE for c in own):
        return "caught", sorted({c for c in own if c != "pass"})
    if any(n in none for n in musts) and not tests:
        return "none only", ["none"]
    if any(c in GENUINE for c in near):
        return "MUST flagged", sorted({c for c in near if c in GENUINE})
    bad = sorted({c for c in own + near if c not in ("pass", "P2P not checked", "P2P covers no changed line")})
    if any(n in none for n in musts):
        return "none only", ["none"] + bad
    if bad:
        return "flagged, not for this", bad
    if not musts and not tests:
        return "miss (no MUST)", []
    return "miss", sorted({c for c in own + near})


def gate_fails(kinds, problems, as_run=False):
    """Whether the gate fails the item; as_run keeps Playwright, live and environment failures, as the gate does."""
    skip = {"pass", "P2P not checked", "P2P covers no changed line", "map error"} | (set() if as_run else NOT_GATE)
    real = [c for c in kinds.values() if c not in skip]
    return bool(real) or bool(problems), sorted(set(real))


def cost_row(k):
    for phase in ("p2p", "cost"):
        run = load(os.path.join(ITEMS, f"{k}.run.{phase}.json"))
        gate = load(os.path.join(ITEMS, f"{k}.gate.{phase}.json"))
        if run:
            row = {"phase": phase, "wall_min": run["wall_min"], "exit": run["exit"]}
            if gate:
                row.update(mutants_run=gate.get("mutants_run"), statuses=gate.get("mutant_statuses"),
                           generated=sum((gate.get("mutant_statuses") or {}).values()),
                           p2p=sorted({classify(g, "vitest") for g in gate.get("PASS_TO_PASS", [])}) if phase == "p2p" else [],
                           gate_min=gate.get("minutes"),
                           stryker_error=next((g["reason"] for g in gate.get("PASS_TO_PASS", []) if "Stryker" in g["reason"]), None))
            else:
                row["error"] = (run.get("stderr") or "")[-300:]
            st = load(os.path.join(ITEMS, f"{k}.run.cost-static.json"))
            sg = load(os.path.join(ITEMS, f"{k}.gate.cost-static.json"))
            if st and sg:
                row["static_off"] = {"wall_min": st["wall_min"], "mutants_run": sg.get("mutants_run"),
                                     "generated": sum((sg.get("mutant_statuses") or {}).values()),
                                     "statuses": sg.get("mutant_statuses")}
            return row
    return None


def fmt_statuses(s):
    return ", ".join(f"{k} {v}" for k, v in sorted((s or {}).items(), key=lambda kv: -kv[1])) or "-"


def main():
    every = json.load(open(os.path.join(OUT, "items.json")))
    items = [i for i in every if i["set"] in ("finding", "control") and i.get("base") and i.get("head") and i.get("repo") == "amc"]
    dropped = [{"id": key(i), "repo": i.get("repo"), "findings": [f"{f['round']} #{f['n']} ({f['focus']})" for f in i.get("findings", [])],
                "why": "; ".join(i.get("problems") or []) or ("not an AMC item: its commits are not in the AMC repository" if i.get("repo") != "amc" else "")}
               for i in every if i["set"] == "finding" and i not in items]
    results, findings, controls, costs, newmod = [], [], [], [], []
    for i in items:
        k = key(i)
        m, gate = load(os.path.join(ITEMS, f"{k}.map.json")), load(os.path.join(ITEMS, f"{k}.gate.f2p.json"))
        res = {"id": k, "set": i["set"], "gated": bool(m and gate)}
        results.append(res)
        c = cost_row(k)
        if c:
            costs.append((k, i["set"], c))
        if not (m and gate):
            for f in i.get("findings", []):
                findings.append({"id": k, "f": f, "verdicts": {v: ("not run", []) for v, _ in VARIANTS}})
            continue
        p2p = load(os.path.join(ITEMS, f"{k}.gate.p2p.json"))
        res["p2p_checked"] = bool(p2p)
        mfs = {(x["round"], str(x["n"])): x for x in m.get("findings", [])}
        per = {}
        for v, kw in VARIANTS:
            kinds, none = test_kinds(m, gate, p2p, **kw)
            fails, why = gate_fails(kinds, gate.get("problems"))
            per[v] = {"fails": fails, "why": why, "none": none, "fails_as_run": gate_fails(kinds, gate.get("problems"), True)[0],
                      "kinds": {f"{n}|{t}": c for (n, t), c in kinds.items()}}
        res["variants"] = per
        for f in i.get("findings", []):
            mf = mfs.get((f["round"], str(f["n"])), {})
            vs = {}
            for v, kw in VARIANTS:
                kinds, none = test_kinds(m, gate, p2p, **kw)
                vs[v] = finding_verdict(f, mf, kinds, none)
            findings.append({"id": k, "f": f, "mf": mf, "verdicts": vs})
        if i["set"] == "control":
            controls.append((k, per, p2p is not None))
        f2p = gate.get("FAIL_TO_PASS", [])
        newmod.append({"id": k, "set": i["set"], "f2p": len(f2p),
                       "load": sum(1 for g in f2p if g["reason"].startswith("load on base")),
                       "error": sum(1 for g in f2p if g["reason"].startswith(("error on base", "timeout on base"))),
                       "error_export": sum(1 for g in f2p if classify(g, "vitest") == "F2P error on base (missing export)"),
                       "passes": sum(1 for g in f2p if g["reason"].startswith("passes on base")),
                       "fails_ok": sum(1 for g in f2p if g["status"] == "pass"),
                       "new_sources": len(i.get("new_sources", [])),
                       "fails_map": per["map"]["fails"], "fails_swe": per["map_swe"]["fails"]})
    json.dump({"items": results, "findings": [{"id": x["id"], "round": x["f"]["round"], "n": x["f"]["n"],
                                                "focus": x["f"]["focus"], "cause": x["f"]["cause"],
                                                "graded": x["f"]["test_would_catch"],
                                                "verdicts": x["verdicts"]} for x in findings],
               "dropped": dropped, "costs": [{"id": k, "set": s, **c} for k, s, c in costs], "new_modules": newmod},
              open(os.path.join(OUT, "results.json"), "w"), indent=1)
    write_tables(findings, controls, costs, newmod, dropped)


def write_tables(findings, controls, costs, newmod, dropped):
    L = ["## Dropped finding items\n", "<!-- table:dropped -->", "| item | findings | why |", "| --- | --- | --- |"]
    L += [f"| {d['id']} | {len(d['findings'])}: {', '.join(d['findings'])} | {d['why']} |" for d in dropped]
    L.append("<!-- /table -->\n")
    L.append("## Q1 per finding\n")
    L.append("<!-- table:q1rows -->")
    L.append("| item | finding | focus/cause | graded | map | strict | map, SWE rule | kinds (map) |")
    L.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for x in sorted(findings, key=lambda x: (x["f"]["focus"], x["id"], x["f"]["round"], str(x["f"]["n"]))):
        f, v = x["f"], x["verdicts"]
        L.append(f"| {x['id'].split('__')[1]} ({x['id'][4:14]}) | {f['round']} #{f['n']} | {f['focus']}/{f['cause']} | "
                 f"{(f['test_would_catch'] or '-') if f['focus'] == 'requirement' else ('TEST' if f['cause'] == 'TEST' else 'other')} | {v['map'][0]} | {v['strict'][0]} | {v['map_swe'][0]} | {'; '.join(v['map'][1]) or '-'} |")
    L.append("<!-- /table -->")
    for focus, graded_key, label in (("requirement", "yes", "45 requirement-only"), ("test", None, "30 TEST")):
        sub = [x for x in findings if x["f"]["focus"] == focus]
        L.append(f"\n**{label}** ({len(sub)} in scope):\n")
        L.append(f"<!-- table:q1{focus} -->")
        L.append("| verdict | map | strict | map, SWE | strict, SWE |")
        L.append("| --- | --- | --- | --- | --- |")
        for verdict in ("caught", "MUST flagged", "none only", "flagged, not for this", "miss", "miss (no MUST)", "not run"):
            row = [sum(1 for x in sub if x["verdicts"][v][0] == verdict) for v, _ in VARIANTS]
            if any(row):
                L.append(f"| {verdict} | " + " | ".join(map(str, row)) + " |")
        grade = (lambda x: x["f"]["test_would_catch"] or "-") if focus == "requirement" else \
            (lambda x: "cause TEST (a test that cannot fail)" if x["f"]["cause"] == "TEST" else "other cause")
        L.append("\nCrossed with the graded column (map rule):\n")
        L.append(f"| {'graded would catch' if focus == 'requirement' else 'graded cause'} | n | caught | MUST flagged | other |")
        L.append("| --- | --- | --- | --- | --- |")
        for g in sorted({grade(x) for x in sub}):
            s2 = [x for x in sub if grade(x) == g]
            a = sum(1 for x in s2 if x["verdicts"]["map"][0] == "caught")
            b = sum(1 for x in s2 if x["verdicts"]["map"][0] == "MUST flagged")
            L.append(f"| {g} | {len(s2)} | {a} | {b} | {len(s2) - a - b} |")
        L.append("<!-- /table -->")
    L.append("\n## Q2 controls\n")
    L.append("<!-- table:q2 -->")
    L.append("| control | Stryker checked | as run (Playwright counted) | map: fails? | kinds | strict: fails? | map, SWE: fails? | kinds (SWE) |")
    L.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for k, per, checked in controls:
        L.append(f"| {k.split('__')[1]} | {'yes' if checked else 'no'} | {'FAIL' if per['map']['fails_as_run'] else 'pass'} | {'FAIL' if per['map']['fails'] else 'pass'} | {'; '.join(per['map']['why']) or '-'} | "
                 f"{'FAIL' if per['strict']['fails'] else 'pass'} | {'FAIL' if per['map_swe']['fails'] else 'pass'} | {'; '.join(per['map_swe']['why']) or '-'} |")
    L.append("\nFalse alarms by kind (count of controls with at least one, map rule; SWE rule):\n")
    L.append("| kind | map | strict | map, SWE | strict, SWE |")
    L.append("| --- | --- | --- | --- | --- |")
    allk = sorted({c for _, per, _ in controls for v in per.values() for c in v["why"]})
    for c in allk:
        L.append(f"| {c} | " + " | ".join(str(sum(1 for _, per, _ in controls if c in per[v]["why"])) for v, _ in VARIANTS) + " |")
    L.append("| none line (reported, not a failure) | " + " | ".join(str(sum(1 for _, per, _ in controls if per[v]["none"])) for v, _ in VARIANTS) + " |")
    L.append("| **controls failed** | " + " | ".join(str(sum(1 for _, per, _ in controls if per[v]["fails"])) for v, _ in VARIANTS) + f" |\n\nAs run, Playwright counted: {sum(1 for _, per, _ in controls if per['map']['fails_as_run'])} of {len(controls)} fail.")
    L.append("<!-- /table -->")
    L.append("\n## Q3 cost\n")
    L.append("<!-- table:q3 -->")
    L.append("| item | set | src lines added | phase | wall min | mutants generated | mutants run | Stryker statuses | gate's PASS_TO_PASS verdicts | ignoreStatic: wall min | ignoreStatic: generated / run |")
    L.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for k, s, c in sorted(costs, key=lambda x: x[2]["wall_min"]):
        st = c.get("static_off") or {}
        err = f" ({c['stryker_error'][:40]})" if c.get("stryker_error", "") and "Stryker" in c["stryker_error"][:20] else ""
        L.append(f"| {k.split('__')[1]} | {s} | {SIZES.get(k, '-')} | {c['phase']} | {c['wall_min']}{err} | {c.get('generated', '-')} | {c.get('mutants_run', '-')} | "
                 f"{fmt_statuses(c.get('statuses'))} | {'; '.join(c.get('p2p') or []) or '-'} | {st.get('wall_min', '-')} | "
                 f"{str(st.get('generated', '-')) + ' / ' + str(st.get('mutants_run', '-')) if st else '-'} |")
    walls = [c["wall_min"] for _, _, c in costs]
    if walls:
        L.append(f"\nmedian {round(statistics.median(walls), 2)} min, largest {max(walls)} min over {len(walls)} items.")
    have = {k for k, _, _ in costs}
    novitest, unreached = [], []
    for r in newmod:
        if r["id"] in have:
            continue
        m = load(os.path.join(ITEMS, f"{r['id']}.map.json"))
        vit = any(t.get("runner", "vitest") == "vitest" for e in m["map"] for t in e.get("tests") or [])
        run, name = r["id"].split("__")
        (unreached if vit else novitest).append(f"{name} ({run[-5:]})" if name == "insights-history" else name)
    if novitest:
        L.append(f"\nNo Vitest test in the map, so no Stryker run: {', '.join(sorted(novitest))}.")
    if unreached:
        L.append(f"\nNot reached inside the time budget (larger changes): {', '.join(sorted(unreached))}.")
    L.append("<!-- /table -->")
    L.append("\n## Q4 new modules and absent code\n")
    L.append("<!-- table:q4 -->")
    L.append("| item | set | FAIL_TO_PASS | fail on assertion | load on base (new module) | error on base: missing export | error on base: other | passes on base | new source files | gate fails (D4) | gate fails (SWE) |")
    L.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in newmod:
        L.append(f"| {r['id'].split('__')[1]} | {r['set']} | {r['f2p']} | {r['fails_ok']} | {r['load']} | {r['error_export']} | {r['error'] - r['error_export']} | {r['passes']} | {r['new_sources']} | "
                 f"{'FAIL' if r['fails_map'] else 'pass'} | {'FAIL' if r['fails_swe'] else 'pass'} |")
    L.append("<!-- /table -->")
    L += summary(findings, controls, costs, newmod)
    open(os.path.join(OUT, "tables.md"), "w").write("\n".join(L) + "\n")


def summary(findings, controls, costs, newmod):
    names = [v for v, _ in VARIANTS]
    L = ["\n## Summary\n", "<!-- table:summary -->",
         "| | assertion-only rule (D4), INFERRED map | D4, strict map | SWE-bench rule, INFERRED map | SWE-bench rule, strict map |",
         "| --- | --- | --- | --- | --- |"]
    def count(sub, pred):
        return [sum(1 for x in sub if pred(x["verdicts"][v][0])) for v in names]
    hit = lambda r: r in ("caught", "MUST flagged")
    for focus, label, graded, glabel in (("requirement", "Requirement-only findings caught or MUST flagged", lambda x: x["f"]["test_would_catch"] == "yes", "graded yes"),
                                         ("test", "TEST-focus findings caught or MUST flagged", lambda x: x["f"]["cause"] == "TEST", "cause TEST")):
        sub = [x for x in findings if x["f"]["focus"] == focus and x["verdicts"]["map"][0] != "not run"]
        g = [x for x in sub if graded(x)]
        a, b = count(sub, hit), count(g, hit)
        L.append(f"| {label} (of {len(sub)}; {glabel}: of {len(g)}) | " + " | ".join(f"{a[i]} ({b[i]})" for i in range(len(names))) + " |")
        c = count(sub, lambda r: r == "none only")
        L.append(f"| ... MUST had no test (`none`, reported, not failed) | " + " | ".join(map(str, c)) + " |")
        d = count(sub, lambda r: r == "flagged, not for this")
        L.append(f"| ... item failed only for another reason | " + " | ".join(map(str, d)) + " |")
    L.append(f"| Clean controls failed (of {len(controls)}) | " + " | ".join(str(sum(1 for _, per, _ in controls if per[v]["fails"])) for v in names) + " |")
    L.append(f"| Clean controls failed with Playwright counted, as the gate runs today | {sum(1 for _, per, _ in controls if per['map']['fails_as_run'])} | | {sum(1 for _, per, _ in controls if per['map_swe']['fails_as_run'])} | |")
    f2p = [load(os.path.join(ITEMS, f"{r['id']}.gate.f2p.json"))["minutes"] for r in newmod]
    walls = [c["wall_min"] for _, _, c in costs]
    gen = [c.get("generated") or 0 for _, _, c in costs]
    if f2p:
        L.append(f"| Minutes per change, base and head runs (median / largest, {len(f2p)} items) | {statistics.median(f2p)} / {max(f2p)} | same | same | same |")
    if walls:
        L.append(f"| Minutes per change with Stryker (median / largest, {len(walls)} items; partial, smallest first) | {round(statistics.median(walls), 2)} / {max(walls)} | same | same | same |")
        L.append(f"| Mutants generated per change (median / largest) | {statistics.median(gen)} / {max(gen)} | same | same | same |")
    L.append("<!-- /table -->")
    return L


if __name__ == "__main__":
    main()
