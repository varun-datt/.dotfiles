#!/usr/bin/env python3
"""Run the Stryker phases one item at a time, smallest change first, until a deadline.

Usage: stryker_queue.py <deadline HH:MM> [static-count]
Each item gets one Stryker run: phase p2p when its map has a Vitest PASS_TO_PASS line, else phase cost.
The first <static-count> items (default 3) that finish under 8 minutes also get phase cost-static.
"""
import datetime, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
ITEMS = os.path.join(OUT, "items")
AMC = os.path.expanduser("~/sandbox/personal/agent-mission-control")
sys.path.insert(0, HERE)
import run_gate  # noqa: E402


def src_lines(i):
    out = subprocess.run(["git", "-C", AMC, "diff", "--numstat", i["base"], i["head"], "--", "src"],
                         capture_output=True, text=True).stdout
    return sum(int(a) for a, _, p in (ln.split("\t") for ln in out.splitlines()) if a.isdigit()
               and p.endswith((".ts", ".tsx", ".js", ".mjs")))


def main():
    deadline = datetime.datetime.combine(datetime.date.today(), datetime.time.fromisoformat(sys.argv[1]))
    static_left = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    items = [i for i in json.load(open(os.path.join(OUT, "items.json"))) if i["set"] in ("finding", "control") and i.get("base") and i.get("head")]
    sizes = {}
    for i in items:
        sizes[run_gate.key(i)] = src_lines(i)
    json.dump(sizes, open(os.path.join(OUT, "src_added_lines.json"), "w"), indent=1, sort_keys=True)
    while datetime.datetime.now() < deadline:
        ran, waiting = one_pass(items, sizes, deadline, static_left)
        static_left = ran[1]
        if not ran[0]:
            if not waiting:
                break
            time.sleep(60)


def one_pass(items, sizes, deadline, static_left):
    runs, waiting = 0, 0
    for i in sorted(items, key=lambda i: sizes[run_gate.key(i)]):
        k = run_gate.key(i)
        mp = os.path.join(ITEMS, f"{k}.map.json")
        if not os.path.exists(mp):
            waiting += 1
            continue
        if any(os.path.exists(os.path.join(ITEMS, f"{k}.run.{ph}.json")) for ph in ("p2p", "cost")):
            continue
        if datetime.datetime.now() > deadline:
            print("deadline reached before", k)
            break
        m = json.load(open(mp))
        phase = "p2p" if run_gate.map_lines(m, "p2p") else "cost"
        log = run_gate.run(i, m, phase)
        runs += 1
        if not log:
            continue
        print(k, phase, "exit", log["exit"], "min", log["wall_min"], "src+", sizes[k], flush=True)
        if static_left and log["wall_min"] < 8 and datetime.datetime.now() < deadline:
            s = run_gate.run(i, m, "cost-static")
            if s:
                static_left -= 1
                print(k, "cost-static exit", s["exit"], "min", s["wall_min"], flush=True)
    return (runs, static_left), waiting


if __name__ == "__main__":
    main()
