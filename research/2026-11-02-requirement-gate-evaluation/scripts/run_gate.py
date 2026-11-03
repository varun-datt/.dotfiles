#!/usr/bin/env python3
"""Run the unmerged requirement gate on past AMC items, one item at a time.

Usage: run_gate.py <phase> [key ...]
  phase f2p   : the INFERRED map, --mutants none (head runs and FAIL_TO_PASS on base)
  phase strict: the strict map, --mutants none (consistency check of the derived strict result)
  phase p2p   : PASS_TO_PASS lines only, --mutants stryker (cost and mutant checks)
  phase cost  : every Vitest test of the map declared PASS_TO_PASS, --mutants stryker (cost only)
  phase cost-static: as cost, with Stryker's --ignoreStatic
A key is <run>__<item>; no key runs every item with a map file and no result for the phase.
"""
import json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
ITEMS = os.path.join(OUT, "items")
AMC = os.path.expanduser("~/sandbox/personal/agent-mission-control")
GATE = os.path.expanduser("~/worktrees/chezmoi/r3/dotfiles/dot_agents/skills/orchestrator-workers/scripts/reqgate.py")
SWEEP = os.path.expanduser("~/.agents/skills/orchestrator-workers/scripts/sweep.py")
STRYKER_CONFIG = os.path.join(HERE, "stryker.eval.json")
CAP = 1200


def key(i):
    return f"{i['run']}__{i['item']}"


def vitest_runner(t):
    return t.get("runner", "vitest") == "vitest"


def map_lines(m, phase):
    lines = []
    for e in m["map"]:
        tests = e.get("tests") or []
        if phase == "strict":
            tests = [t for t in tests if t.get("strict")]
        if phase in ("p2p",):
            tests = [t for t in tests if t["kind"] == "PASS_TO_PASS" and vitest_runner(t)]
        if phase.startswith("cost"):
            tests = [dict(t, kind="PASS_TO_PASS") for t in tests if vitest_runner(t)]
        if tests:
            lines += [f"- MUST {e['must']}: {t['file']}::{t['name']} [{t['kind']}]" for t in tests]
        elif phase in ("f2p", "strict"):
            lines.append(f"- MUST {e['must']}: none ({e.get('none') or 'no test cites it'})")
    return lines


def worktrees():
    out = subprocess.run(["git", "-C", AMC, "worktree", "list", "--porcelain"], capture_output=True, text=True).stdout
    return [ln.split(" ", 1)[1] for ln in out.splitlines() if ln.startswith("worktree ") and "reqgate-" in ln]


def run(item, m, phase):
    k = key(item)
    lines = map_lines(m, phase)
    if phase not in ("f2p", "strict") and not lines:
        return None
    report = os.path.join(ITEMS, f"{k}.report.{phase}.md")
    with open(report, "w") as f:
        f.write("## REQUIREMENTS MAP\n\n" + "\n".join(lines) + "\n")
    out = os.path.join(ITEMS, f"{k}.gate.{phase}.json")
    cmd = [sys.executable, "-B", GATE, "check", "--repo", AMC, "--base", item["base"], "--head", item["head"],
           "--brief", os.path.expanduser(item["brief"]), "--report", report, "--warn", "--json", out, "--timeout", "180"]
    if phase in ("f2p", "strict"):
        cmd += ["--mutants", "none"]
    else:
        stryker = f"npx --no-install stryker run {STRYKER_CONFIG}" + (" --ignoreStatic" if phase == "cost-static" else "")
        cmd += ["--mutants", "stryker", "--stryker-timeout", str(CAP), "--stryker-cmd", stryker]
    load = subprocess.run([sys.executable, "-B", SWEEP, "load", "--wait", "10"], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    before = set(worktrees())
    started = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    wall = round((time.time() - started) / 60, 2)
    left = [w for w in worktrees() if w not in before]
    # Another gate run (a Stryker phase) may be live; remove leftovers only when no other gate runs.
    others = subprocess.run(["ps", "-axo", "command"], capture_output=True, text=True).stdout.count("reqgate.py check")
    if not others:
        for w in left:
            subprocess.run(["git", "-C", AMC, "worktree", "remove", "--force", w], capture_output=True)
    log = {"id": k, "phase": phase, "exit": p.returncode, "wall_min": wall, "load_exit": load.returncode,
           "stderr": p.stderr[-2000:], "stdout_tail": p.stdout[-3000:], "leftover_worktrees": left,
           "leftover_removed": not others,
           "head": item["head"], "base": item["base"], "cmd": " ".join(cmd[2:]).replace(os.path.expanduser("~"), "~")}
    with open(os.path.join(ITEMS, f"{k}.run.{phase}.json"), "w") as f:
        json.dump(log, f, indent=1)
    return log


def main():
    phase, keys = sys.argv[1], sys.argv[2:]
    items = {key(i): i for i in json.load(open(os.path.join(OUT, "items.json")))}
    todo = keys or sorted(k for k in items if os.path.exists(os.path.join(ITEMS, f"{k}.map.json"))
                          and not os.path.exists(os.path.join(ITEMS, f"{k}.run.{phase}.json")))
    for k in todo:
        mp = os.path.join(ITEMS, f"{k}.map.json")
        if not os.path.exists(mp):
            print(f"{k}: no map", file=sys.stderr)
            continue
        log = run(items[k], json.load(open(mp)), phase)
        if log:
            print(k, phase, "exit", log["exit"], "min", log["wall_min"], "leftover", len(log["leftover_worktrees"]), log["stderr"][-200:].strip())


if __name__ == "__main__":
    main()
