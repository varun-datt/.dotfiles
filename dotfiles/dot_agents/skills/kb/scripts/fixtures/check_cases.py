"""Validate fixtures/cases.json against fixtures/corpus/. Prints OK and counts, or the problems found."""
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "corpus"
SPACES = {"wiki", "work", "product"}
CALLERS = {"palette", "agent", "request"}
SOURCES = {"wiki", "work", "route-planner", "dock-scheduler"}
KEYS = {"id", "space", "caller", "class", "q", "scope", "expect", "note", "mustNot"}
BANNED = re.compile(r"patient|cardiac|device serial|medical|hospital|clinic|health", re.I)
HOST = re.compile(r"[a-z][a-z0-9+.-]*://([^/\s\"'<>`)]+)", re.I)
BARE = re.compile(r"\b((?:[a-z0-9-]+\.)+(?:com|org|io|internal))\b", re.I)
ALLOWED_HOST = re.compile(r"(?:^|\.)example\.(?:com|internal)$", re.I)

problems = []
data = json.loads((HERE / "cases.json").read_text())
if set(data) != {"version", "about", "classes", "queries"}:
    problems.append(f"top-level keys: {sorted(data)}")
classes = data["classes"]
ids = Counter(q["id"] for q in data["queries"])
problems += [f"duplicate id {i}" for i, n in ids.items() if n > 1]

anchors = 0
for q in data["queries"]:
    qid = q["id"]
    if set(q) - KEYS:
        problems.append(f"{qid}: unknown keys {sorted(set(q) - KEYS)}")
    if q["class"] not in classes:
        problems.append(f"{qid}: class {q['class']!r} not in classes")
    if q["space"] not in SPACES:
        problems.append(f"{qid}: space {q['space']!r}")
    if q["caller"] not in CALLERS:
        problems.append(f"{qid}: caller {q['caller']!r}")
    if not q["scope"] or set(q["scope"]) - SOURCES:
        problems.append(f"{qid}: scope {q['scope']}")
    if not q["expect"]:
        problems.append(f"{qid}: no expect")
    for e in q["expect"]:
        f = CORPUS / e["path"]
        if not f.is_file():
            problems.append(f"{qid}: missing {e['path']}")
            continue
        if e["path"].split("/")[0 if not e["path"].startswith("product/") else 1] not in q["scope"]:
            problems.append(f"{qid}: {e['path']} is outside scope {q['scope']}")
        if "anchor" in e:
            anchors += 1
            try:
                rx = re.compile(e["anchor"])
            except re.error as err:
                problems.append(f"{qid}: anchor does not compile: {err}")
                continue
            hits = sum(1 for line in f.read_text().splitlines() if rx.search(line))
            if hits != 1:
                problems.append(f"{qid}: anchor {e['anchor']!r} matches {hits} lines in {e['path']}")
    for m in q.get("mustNot", []):
        if not (CORPUS / m).is_file():
            problems.append(f"{qid}: mustNot path missing {m}")
    if q["caller"] == "agent":
        try:
            re.compile(q["q"])
        except re.error as err:
            problems.append(f"{qid}: agent regex does not compile: {err}")

files = sorted(p for p in CORPUS.rglob("*") if p.is_file())
for p in files + [HERE / "cases.json"]:
    for n, line in enumerate(p.read_text().splitlines(), 1):
        rel = p.relative_to(HERE)
        if BANNED.search(line):
            problems.append(f"banned word: {rel}:{n}")
        for h in HOST.findall(line) + BARE.findall(line):
            if not ALLOWED_HOST.search(h.split(":")[0]):
                problems.append(f"host not allowed: {rel}:{n}: {h}")

if problems:
    print("FAIL")
    print("\n".join(problems))
    sys.exit(1)

qs = data["queries"]
print(f"OK: {len(qs)} cases, {anchors} anchors ({len({q['id'] for q in qs if any('anchor' in e for e in q['expect'])})} cases with one), "
      f"{sum(1 for q in qs if 'mustNot' in q)} with mustNot, {len(files)} corpus files, 0 banned-word hits, only example.com/example.internal hosts")
print("space x caller:", dict(sorted(Counter((q["space"], q["caller"]) for q in qs).items())))
print("caller x class:", dict(sorted(Counter((q["caller"], q["class"]) for q in qs).items())))
