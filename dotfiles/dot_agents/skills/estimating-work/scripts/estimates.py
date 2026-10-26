#!/usr/bin/env python3
"""Log agent work items, estimate from their history, and forecast a window by Monte Carlo."""

import argparse
import json
import math
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

MIN_HISTORY = 5
METHODS = ("history", "rounds", "judged")
MINUTES_PER_ROUND = 3.0
# Stop-hook refusals in a row with no new log record before the guard lets the turn end anyway.
GUARD_LIMIT = 3


def log_path():
    return Path(os.environ.get("ESTIMATES_LOG") or Path.home() / ".agents" / "state" / "estimates.jsonl")


def run_path():
    return Path(os.environ.get("ESTIMATES_RUN") or Path.home() / ".agents" / "state" / "active-run.json")


def now():
    return datetime.now(timezone.utc).astimezone()


def append(record):
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")


def read():
    path = log_path()
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def completed(records):
    items, starts = [], {}
    for r in records:
        if r["event"] == "done":
            items.append(r)
        elif r["event"] == "start":
            starts[r["id"]] = r
        elif r["event"] == "end" and r["id"] in starts:
            s = starts.pop(r["id"])
            minutes = (datetime.fromisoformat(r["at"]) - datetime.fromisoformat(s["at"])).total_seconds() / 60
            items.append({**s, "event": "done", "actual": round(minutes, 1), "at": r["at"]})
    return items


def percentile(values, p):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)]


def recent(items, days):
    cutoff = now() - timedelta(days=days)
    return [i for i in items if datetime.fromisoformat(i["at"]) >= cutoff]


def velocities(items, method):
    return [i["estimate"] / i["actual"] for i in items if i["actual"] > 0 and i.get("method", "judged") == method]


def kind_estimate(items, kind):
    actuals = [i["actual"] for i in items if i["kind"] == kind]
    if len(actuals) < MIN_HISTORY:
        return {"kind": kind, "n": len(actuals), "guess": True}
    return {"kind": kind, "n": len(actuals), "p50": percentile(actuals, 50), "p90": percentile(actuals, 90), "guess": False}


def rounds_estimate(rounds, risk):
    return {"rounds": rounds, "risk": risk, "estimate": round(rounds * risk * MINUTES_PER_ROUND, 1), "method": "rounds"}


def forecast(plan, window, items, runs=1000, seed=None):
    rng = random.Random(seed)
    actuals = {}
    for i in items:
        actuals.setdefault(i["kind"], []).append(i["actual"])
    pools = {m: velocities(items, m) for m in METHODS}
    totals, fits = [], []
    for _ in range(runs):
        elapsed, fitted = 0.0, 0
        for item in plan:
            kind_actuals = actuals.get(item["kind"], [])
            pool = pools[item["method"]]
            if item["method"] == "history" and len(kind_actuals) >= MIN_HISTORY:
                elapsed += rng.choice(kind_actuals)
            else:
                elapsed += item["estimate"] / rng.choice(pool if len(pool) >= MIN_HISTORY else [1.0])
            if elapsed <= window:
                fitted += 1
        totals.append(elapsed)
        fits.append(fitted)
    return {
        "items": len(plan),
        "history": len(items),
        "total_p50": round(percentile(totals, 50), 1),
        "total_p90": round(percentile(totals, 90), 1),
        "fit_p50": percentile(fits, 50),
        "fit_p10": percentile(fits, 10),
        "chance_all_fit": round(sum(t <= window for t in totals) / runs, 2),
    }


def report(items):
    if not items:
        return {"n": 0}
    est = sum(i["estimate"] for i in items)
    act = sum(i["actual"] for i in items)
    within = sum(abs(i["actual"] - i["estimate"]) <= 0.25 * i["actual"] for i in items)
    by_kind = {}
    for i in items:
        by_kind[i["kind"]] = round(by_kind.get(i["kind"], 0) + i["actual"], 1)
    features = sum(i["actual"] for i in items if i["kind"] == "feature" or i.get("serves"))
    return {
        "n": len(items),
        "estimated": round(est, 1),
        "actual": round(act, 1),
        "estimate_over_actual": round(est / act, 2) if act else None,
        "within_25_percent": within,
        "features_with_enablers_share": round(features / act, 2) if act else None,
        "minutes_by_kind": {k: {"minutes": v, "share": round(v / act, 2) if act else None} for k, v in sorted(by_kind.items(), key=lambda kv: -kv[1])},
    }


def kinds_table(items):
    lines = ["| Kind | Items | P50 (min) | P90 (min) |", "| --- | --- | --- | --- |"]
    for kind in sorted({i["kind"] for i in items}):
        actuals = [i["actual"] for i in items if i["kind"] == kind]
        lines.append(f"| {kind} | {len(actuals)} | {percentile(actuals, 50):g} | {percentile(actuals, 90):g} |")
    return "\n".join(lines)


def until_time(text, at):
    """An ISO time, or a clock time HH:MM taken as its next occurrence after `at`."""
    if ":" in text and len(text) <= 5:
        hour, minute = (int(part) for part in text.split(":"))
        moment = at.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return moment if moment > at else moment + timedelta(days=1)
    return datetime.fromisoformat(text)


def load_run():
    path = run_path()
    return json.loads(path.read_text()) if path.exists() else None


def save_run(run):
    path = run_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run, indent=1))


def guard_decision(run, records, at):
    """The reason the agent must keep working, or None to let the turn end; also returns the run to save."""
    if not run or run.get("blocked") or at >= datetime.fromisoformat(run["until"]):
        return None, run
    finished = {r["id"] for r in records if r["event"] in ("end", "done")}
    left = [i for i in run.get("planned") or [] if i not in finished]
    if run.get("planned") and not left:
        return None, run
    progressed = run.get("seen") != len(records)
    blocks = 1 if progressed else run.get("blocks", 0) + 1
    if blocks > GUARD_LIMIT:
        return None, {**run, "blocks": 0, "seen": len(records)}
    stop = datetime.fromisoformat(run["until"]).strftime("%H:%M")
    what = f"{len(left)} planned items are not done (next: {left[0]})" if left else "items may remain"
    reason = (
        f"Run {run['run']} is armed until {stop} and {what}. Do not end the turn: put any question that blocks "
        "nothing in the session memory for the final report, and take the next item. Only if something blocks "
        "every remaining item, run `estimates.py block --reason \"...\"` first; at the wrap-up, `estimates.py disarm`."
    )
    return reason, {**run, "blocks": blocks, "seen": len(records)}


def guard():
    """The Stop hook: prints a block decision while an armed run has work left; fails open on any error."""
    try:
        reason, run = guard_decision(load_run(), read(), now())
        if run is not None:
            save_run(run)
    except Exception as error:  # noqa: BLE001 - a broken guard must never trap the agent
        return {"systemMessage": f"Run guard: not checked ({error})"}
    if reason is None:
        return None
    return {"decision": "block", "reason": reason, "hookSpecificOutput": {"hookEventName": "Stop", "decision": "block", "reason": reason}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("start", help="stamp the start of an item")
    p.add_argument("--id", required=True)
    p.add_argument("--kind", required=True)
    p.add_argument("--estimate", type=float, required=True, help="minutes")
    p.add_argument("--method", required=True, choices=METHODS, help="how the estimate was made")
    p.add_argument("--serves", default="", help="id of the planned feature this enabler makes possible or faster")
    p.add_argument("--run", default="")
    p = sub.add_parser("end", help="stamp the end of an item")
    p.add_argument("--id", required=True)
    p = sub.add_parser("add", help="record a finished item whose actual is already known")
    p.add_argument("--id", required=True)
    p.add_argument("--kind", required=True)
    p.add_argument("--estimate", type=float, required=True)
    p.add_argument("--actual", type=float, required=True)
    p.add_argument("--method", required=True, choices=METHODS)
    p.add_argument("--serves", default="")
    p.add_argument("--at", default=None, help="ISO time it ended; default now")
    p.add_argument("--run", default="")
    p = sub.add_parser("estimate", help="P50 and P90 for a kind from the log, or minutes for a count of rounds")
    p.add_argument("--kind")
    p.add_argument("--rounds", type=int, help="think-write-run-verify cycles the item needs")
    p.add_argument("--risk", type=float, default=1.0, help="1.0 known ground to 2.0 many unknowns")
    p.add_argument("--days", type=int, default=180)
    p = sub.add_parser("forecast", help="Monte Carlo forecast of a plan against a window")
    p.add_argument("--plan", required=True, help="JSON list of {id, kind, estimate, method}")
    p.add_argument("--window", type=float, required=True, help="minutes until the stop time")
    p.add_argument("--runs", type=int, default=1000)
    p.add_argument("--days", type=int, default=180)
    p.add_argument("--seed", type=int, default=None)
    p = sub.add_parser("report", help="estimate against actual for one run, or all")
    p.add_argument("--run", default=None)
    p = sub.add_parser("kinds", help="markdown table of measured pace per kind")
    p.add_argument("--days", type=int, default=180)
    p = sub.add_parser("arm", help="start the run guard: a Stop hook keeps the agent working until the stop time")
    p.add_argument("--run", required=True)
    p.add_argument("--until", required=True, help="stop time, HH:MM (its next occurrence) or ISO")
    p.add_argument("--plan", default=None, help="plan JSON; the guard lets the turn end once every item in it is done")
    p = sub.add_parser("block", help="a blocker stops every remaining item: let the turn end until the next start")
    p.add_argument("--reason", required=True)
    sub.add_parser("disarm", help="end the run guard at the wrap-up")
    sub.add_parser("guard", help="the Stop hook's check; reads the hook's JSON on stdin")
    args = parser.parse_args(argv)

    if args.command == "start":
        append({"event": "start", "id": args.id, "kind": args.kind, "estimate": args.estimate, "method": args.method, "serves": args.serves, "run": args.run, "at": now().isoformat()})
        run = load_run()
        if run and run.get("blocked"):
            save_run({k: v for k, v in run.items() if k not in ("blocked", "blockedAt")})
    elif args.command == "end":
        append({"event": "end", "id": args.id, "at": now().isoformat()})
        done = [i for i in completed(read()) if i["id"] == args.id]
        if not done:
            print(f"no open start for {args.id}", file=sys.stderr)
            return 1
        print(json.dumps({k: done[-1][k] for k in ("id", "kind", "estimate", "actual")}))
    elif args.command == "add":
        append({"event": "done", "id": args.id, "kind": args.kind, "estimate": args.estimate, "actual": args.actual, "method": args.method, "serves": args.serves, "run": args.run, "at": args.at or now().isoformat()})
    elif args.command == "estimate":
        if args.rounds is not None:
            print(json.dumps(rounds_estimate(args.rounds, args.risk)))
        elif args.kind:
            print(json.dumps(kind_estimate(recent(completed(read()), args.days), args.kind)))
        else:
            print("give --kind or --rounds", file=sys.stderr)
            return 2
    elif args.command == "forecast":
        plan = json.loads(Path(args.plan).read_text())
        if any(item.get("method") not in METHODS for item in plan):
            print(f"every plan item needs a method: {', '.join(METHODS)}", file=sys.stderr)
            return 2
        print(json.dumps(forecast(plan, args.window, recent(completed(read()), args.days), args.runs, args.seed)))
    elif args.command == "report":
        items = [i for i in completed(read()) if args.run is None or i.get("run") == args.run]
        print(json.dumps(report(items), indent=2))
    elif args.command == "kinds":
        print(kinds_table(recent(completed(read()), args.days)))
    elif args.command == "arm":
        at = now()
        planned = [item["id"] for item in json.loads(Path(args.plan).read_text())] if args.plan else None
        save_run({"run": args.run, "until": until_time(args.until, at).isoformat(), "planned": planned, "armedAt": at.isoformat()})
        print(json.dumps(load_run()))
    elif args.command == "block":
        run = load_run()
        if not run:
            print("no armed run", file=sys.stderr)
            return 1
        save_run({**run, "blocked": args.reason, "blockedAt": now().isoformat()})
    elif args.command == "disarm":
        run_path().unlink(missing_ok=True)
    elif args.command == "guard":
        output = guard()
        if output:
            print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
