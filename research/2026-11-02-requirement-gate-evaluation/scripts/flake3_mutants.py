#!/usr/bin/env python3
"""Mutation check (software-testing mutation-checks.md) of flake-3's two hygiene guards, in memory.

Each mutant is one extra test-file text (or the root browser config) run through the guard's own regex and assertion, taken from
tests/unit/test-hygiene.test.ts at the reviewed head, in its own node process; `none` is the control. Nothing on disk changes.
A mutant the guard must catch passes the check when the guard's assertion fails; a mutant that is the reviewer's defect shows the
guard cannot see it when its assertion still passes.
"""
import json, os, re, subprocess

AMC = os.path.expanduser("~/sandbox/personal/agent-mission-control")
HEAD = "563999547f39cca7d883fe332470b81d43eb1142"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "flake3", "mutants.json")
src = subprocess.run(["git", "-C", AMC, "show", f"{HEAD}:tests/unit/test-hygiene.test.ts"], capture_output=True, text=True, check=True).stdout
SLEEP = re.search(r"^const SLEEP = (.+);$", src, re.M).group(1)
PORT = re.search(r"^const PORT = (.+);$", src, re.M).group(1)
config = subprocess.run(["git", "-C", AMC, "show", f"{HEAD}:playwright.config.ts"], capture_output=True, text=True, check=True).stdout

# (name, guard, file the text is added to, text, in the tests folder the guard scans, expected: "fails" = the guard must catch it)
MUTANTS = [
    ("none", "sleep", "tests/unit/x.test.ts", "await until(() => done);", True, "passes"),
    ("known sleep form", "sleep", "tests/unit/x.test.ts", "await new Promise((r) => setTimeout(r, 200));", True, "fails"),
    ("finding 2: sleep through an arrow", "sleep", "tests/unit/x.test.ts", "await new Promise((resolve) => setTimeout(() => resolve(undefined), 200));", True, "fails"),
    ("finding 2: promisified setTimeout", "sleep", "tests/unit/x.test.ts", "await setTimeoutP(200);", True, "fails"),
    ("finding 2: sleep named in a comment", "sleep", "tests/unit/x.test.ts", "// never call sleep(100) here", True, "passes"),
    ("none", "port", "tests/unit/x.test.ts", "listen(0)", True, "passes"),
    ("port in a test file", "port", "tests/unit/x.test.ts", "const port = 4399;", True, "fails"),
    ("finding 3: port in the browser config at head", "port", "playwright.config.ts", config, False, "fails"),
]
JS = r"""
const [guard, text, scanned] = [process.argv[1], process.argv[2], process.argv[3] === "1"];
const SLEEP = %s; const PORT = %s;
const sources = scanned ? [{file: "added", text}] : [];
let failed;
if (guard === "sleep") failed = sources.some((s) => [...s.text.matchAll(SLEEP)].length > 0);
else failed = sources.some((s) => PORT.test(s.text));
console.log(failed ? "assertion fails" : "assertion passes");
""" % (SLEEP, PORT)
rows = []
for name, guard, where, text, scanned, expect in MUTANTS:
    out = subprocess.run(["node", "-e", JS, guard, text, "1" if scanned else "0"], capture_output=True, text=True).stdout.strip()
    got = "fails" if out == "assertion fails" else "passes"
    rows.append({"mutant": name, "guard": guard, "added_to": where, "guard_assertion": got, "should": expect, "guard_sees_it": got == expect})
json.dump(rows, open(OUT, "w"), indent=1)
for r in rows:
    print(r["guard"], "|", r["mutant"], "|", r["guard_assertion"], "| should", r["should"], "|", "ok" if r["guard_sees_it"] else "GUARD MISSES IT")
