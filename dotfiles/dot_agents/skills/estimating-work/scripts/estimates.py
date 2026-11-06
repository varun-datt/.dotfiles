#!/usr/bin/env python3
"""Log agent work items, estimate from their history, and forecast a window by Monte Carlo."""

import argparse
import json
import math
import os
import random
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

MIN_HISTORY = 5
METHODS = ("history", "rounds", "judged")
MINUTES_PER_ROUND = 3.0
# Stop-hook refusals in a row with no new log record before the guard lets the turn end anyway.
GUARD_LIMIT = 3
CREDITS_TIMEOUT = 20
GH_ENV = {"GH_PROMPT_DISABLED": "1", "GH_NO_UPDATE_NOTIFIER": "1", "NO_COLOR": "1"}
CLOSES = ("end", "drop", "done")
LEFT_OPEN_AFTER = timedelta(days=1)
REASON = re.compile(r"(start|end):(gh-missing|gh-exit-\d{1,3}|timeout|gh-error|bad-json|no-quota|no-figure|not-read|unknown)")


def log_path():
    return Path(os.environ.get("ESTIMATES_LOG") or Path.home() / ".agents" / "state" / "estimates.jsonl")


def run_path():
    return Path(os.environ.get("ESTIMATES_RUN") or Path.home() / ".agents" / "state" / "active-run.json")


def now():
    return datetime.now(timezone.utc).astimezone()


def parse_time(text):
    """An ISO time; one with no zone is taken as local time, so naive and aware records compare."""
    moment = datetime.fromisoformat(text)
    return moment if moment.tzinfo else moment.astimezone()


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


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def parse_credits(payload):
    """Credits used from `gh api /copilot_internal/user`, as (value, None) or (None, reason)."""
    snapshots = payload.get("quota_snapshots") if isinstance(payload, dict) else None
    premium = snapshots.get("premium_interactions") if isinstance(snapshots, dict) else None
    if not isinstance(premium, dict) or premium.get("has_quota") is False:
        return None, "no-quota"
    used = premium.get("credits_used")
    if is_number(used) and used >= 0:
        return used, None
    return None, "no-figure"


def read_credits():
    """The account's credits-used figure, as (value, None) or (None, reason code); never raises."""
    try:
        done = subprocess.run(["gh", "api", "/copilot_internal/user"], capture_output=True, timeout=CREDITS_TIMEOUT, env={**os.environ, **GH_ENV}, stdin=subprocess.DEVNULL)
    except FileNotFoundError:
        return None, "gh-missing"
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except Exception:  # noqa: BLE001 - a failed read must never stop a stamp
        return None, "gh-error"
    if done.returncode != 0:
        return None, f"gh-exit-{done.returncode}"
    try:
        payload = json.loads(done.stdout.decode("utf-8"))
    except ValueError:
        return None, "bad-json"
    return parse_credits(payload)


def credits_fields(prefix):
    value, reason = read_credits()
    return {f"credits_at_{prefix}": value} | ({"credits_unknown": f"{prefix}:{reason}"} if reason else {})


def open_start(records, item_id):
    start = None
    for r in records:
        if r.get("id") != item_id:
            continue
        if r["event"] == "start":
            start = r
        elif r["event"] in CLOSES:
            start = None
    return start


def known_reasons(text, fallback="unknown"):
    """The text when it is only reason codes, else the fallback, so no free text reaches the log or the report."""
    tokens = str(text).split()
    return " ".join(tokens) if tokens and all(REASON.fullmatch(t) for t in tokens) else fallback


def end_credits(start):
    fields = credits_fields("end")
    before, after = start.get("credits_at_start"), fields["credits_at_end"]
    if is_number(before) and is_number(after):
        return fields | {"credits_actual": round(after - before, 2)}
    started = start.get("credits_unknown")
    started = known_reasons(started, "start:unknown") if started else ("" if is_number(before) else "start:not-read")
    if started and not started.startswith("start:"):
        started = "start:unknown"
    reasons = [started, fields.get("credits_unknown", "")]
    return {"credits_at_end": after, "credits_actual": None, "credits_unknown": " ".join(r for r in reasons if r)}


def completed(records):
    items, starts = [], {}
    for r in records:
        if r["event"] == "done":
            items.append(r)
        elif r["event"] == "start":
            starts[r["id"]] = r
        elif r["event"] == "end" and r["id"] in starts:
            s = starts.pop(r["id"])
            minutes = (parse_time(r["at"]) - parse_time(s["at"])).total_seconds() / 60
            item = {k: v for k, v in s.items() if k != "credits_unknown"}
            item |= {"event": "done", "actual": round(minutes, 1), "started": s["at"], "at": r["at"]}
            item |= {k: r[k] for k in ("credits_actual", "credits_unknown") if k in r}
            items.append(item)
        elif r["event"] == "drop":
            if starts.pop(r["id"], None) is None:
                last = next((n for n in range(len(items) - 1, -1, -1) if items[n]["id"] == r["id"]), None)
                if last is not None:
                    del items[last]
    return prefer_imported(items)


def prefer_imported(items):
    """An id with an imported row counts once, as that row; the hand-logged row only lends its estimate and method."""
    imported = {i["id"] for i in items if i.get("imported")}
    hand = {}
    for i in items:
        if not i.get("imported") and i["id"] in imported:
            hand[i["id"]] = i
    out = []
    for i in items:
        if i.get("imported"):
            h = hand.get(i["id"])
            if h and is_number(h.get("estimate")):
                i = i | {"estimate": h["estimate"], "method": h.get("method", "judged")}
            out.append(i)
        elif i["id"] not in imported:
            out.append(i)
    return out


def percentile(values, p):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)]


def recent(items, days):
    cutoff = now() - timedelta(days=days)
    return [i for i in items if parse_time(i["at"]) >= cutoff]


def velocities(items, method):
    return [i["estimate"] / i["actual"] for i in items
            if i.get("estimate") and i["actual"] > 0 and i.get("method", "judged") == method]


def kind_estimate(items, kind):
    actuals = [i["actual"] for i in items if i["kind"] == kind]
    if len(actuals) < MIN_HISTORY:
        return {"kind": kind, "n": len(actuals), "guess": True}
    return {"kind": kind, "n": len(actuals), "p50": percentile(actuals, 50), "p90": percentile(actuals, 90), "guess": False}


def rounds_estimate(rounds, risk):
    return {"rounds": rounds, "risk": risk, "estimate": round(rounds * risk * MINUTES_PER_ROUND, 1), "method": "rounds"}


def check_after(plan):
    seen = set()
    for item in plan:
        for dep in item.get("after", []):
            if dep not in seen:
                known = any(other["id"] == dep for other in plan)
                raise ValueError(f"item {item['id']} waits for {dep}, " + ("which comes later in the plan" if known else "which is not in the plan"))
        seen.add(item["id"])


def schedule(plan, minutes, slots):
    """Greedy list scheduling: a free lane takes the first ready item in plan order; blocked items hold no lane."""
    lanes = {"slot": [0.0] * slots, "chat": [0.0]}
    finished = {}
    pending = list(range(len(plan)))
    t = 0.0
    while pending:
        started = True
        while started:
            started = False
            for i in pending:
                item = plan[i]
                if any(finished.get(d, float("inf")) > t for d in item.get("after", [])):
                    continue
                if item.get("slot") is False:
                    pool = None
                else:
                    pool = "slot" if slots == 1 or item["kind"].startswith("worker-") else "chat"
                lane = None
                if pool:
                    lane = next((n for n, free in enumerate(lanes[pool]) if free <= t), None)
                    if lane is None:
                        continue
                finished[item["id"]] = t + minutes[i]
                if pool:
                    lanes[pool][lane] = t + minutes[i]
                pending.remove(i)
                started = True
                break
        if pending:
            t = min(e for e in finished.values() if e > t)
    return finished


def forecast(plan, window, items, runs=1000, seed=None, slots=1):
    if slots < 1:
        raise ValueError("slots must be at least 1")
    check_after(plan)
    rng = random.Random(seed)
    actuals = {}
    for i in items:
        actuals.setdefault(i["kind"], []).append(i["actual"])
    pools = {m: velocities(items, m) for m in METHODS}
    totals, fits, sequentials = [], [], []
    for _ in range(runs):
        minutes_by_item = []
        for item in plan:
            kind_actuals = actuals.get(item["kind"], [])
            pool = pools[item["method"]]
            if item["method"] == "history" and len(kind_actuals) >= MIN_HISTORY:
                minutes = rng.choice(kind_actuals)
            else:
                minutes = item["estimate"] / rng.choice(pool if len(pool) >= MIN_HISTORY else [1.0])
            minutes_by_item.append(minutes)
        summed = sum(minutes_by_item)
        ends = list(schedule(plan, minutes_by_item, slots).values())
        totals.append(max(ends, default=0.0))
        fits.append(sum(e <= window for e in ends))
        sequentials.append(summed)
    return {
        "items": len(plan),
        "history": len(items),
        "slots": slots,
        "total_p50": round(percentile(totals, 50), 1),
        "total_p90": round(percentile(totals, 90), 1),
        "sequential_p50": round(percentile(sequentials, 50), 1),
        "fit_p50": percentile(fits, 50),
        "fit_p10": percentile(fits, 10),
        "chance_all_fit": round(sum(t <= window for t in totals) / runs, 2),
    }


def daily_counts(items, days, today, kinds=None):
    """Items finished per local calendar day over the last `days` full days before `today`, zero days
    included; the range starts no earlier than the first logged item, so days before the log are not zeros."""
    chosen = [i for i in items if (i["kind"] in kinds if kinds else not i.get("imported"))]
    if not chosen:
        return []
    first = min(parse_time(i["at"]).astimezone().date() for i in chosen)
    start = max(today - timedelta(days=days), first)
    counts = {start + timedelta(days=n): 0 for n in range((today - start).days)}
    for i in chosen:
        day = parse_time(i["at"]).astimezone().date()
        if day in counts:
            counts[day] += 1
    return [counts[d] for d in sorted(counts)]


def throughput(counts, items, runs=1000, seed=None):
    """Days to finish `items` more, by drawing past days' finished-item counts with replacement."""
    if not any(counts):
        raise ValueError("no finished items in the history window (today is not counted)")
    rng = random.Random(seed)
    needed = []
    for _ in range(runs):
        done = days = 0
        while done < items:
            done += rng.choice(counts)
            days += 1
        needed.append(days)
    return {
        "items": items,
        "history_days": len(counts),
        "zero_days": counts.count(0),
        "finished_in_history": sum(counts),
        "guess": len(counts) < MIN_HISTORY,
        "days_p50": percentile(needed, 50),
        "days_p85": percentile(needed, 85),
        "days_p95": percentile(needed, 95),
    }


def report(items, logged=None):
    if not items:
        return {"n": 0}
    judged = [i for i in items if is_number(i.get("estimate"))]
    est = sum(i["estimate"] for i in judged)
    act = sum(i["actual"] for i in items)
    within = sum(abs(i["actual"] - i["estimate"]) <= 0.25 * i["actual"] for i in judged)
    by_kind = {}
    for i in items:
        by_kind[i["kind"]] = round(by_kind.get(i["kind"], 0) + i["actual"], 1)
    features = sum(i["actual"] for i in items if i["kind"] == "feature" or i.get("serves"))
    return {
        "n": len(items),
        "estimated": round(est, 1),
        "actual": round(act, 1),
        "estimate_over_actual": round(est / sum(i["actual"] for i in judged), 2) if judged and sum(i["actual"] for i in judged) else None,
        "within_25_percent": within,
        "features_with_enablers_share": round(features / act, 2) if act else None,
        "minutes_by_kind": {k: {"minutes": v, "share": round(v / act, 2) if act else None} for k, v in sorted(by_kind.items(), key=lambda kv: -kv[1])},
        "credits": credits_report(items, logged),
    }


def running(records, at):
    """Items started and not yet ended, dropped or added, as windows that run until `at`."""
    starts = {}
    for r in records:
        if r["event"] == "start":
            starts[r["id"]] = r
        elif r["event"] in CLOSES:
            starts.pop(r["id"], None)
    return [{**s, "started": s["at"], "at": at.isoformat()} for s in starts.values()]


def left_open(records, at):
    """Items started more than LEFT_OPEN_AFTER before `at` and never closed: every later item overlaps them."""
    return [{"id": s["id"], "run": s.get("run", ""), "started": s["started"]}
            for s in running(records, at) if at - parse_time(s["started"]) > LEFT_OPEN_AFTER]


def window(item):
    return (parse_time(item["started"]), parse_time(item["at"])) if item.get("started") else None


def overlaps(items, logged):
    """For each item, the ids of other logged items, from any run, whose start-to-end window overlaps its own."""
    found = []
    for item in items:
        mine = window(item)
        if item.get("credits_source") == "log":
            found.append([])
            continue
        others = [(o, window(o)) for o in logged if o is not item and not (o.get("id") == item.get("id") and o.get("started") == item.get("started"))]
        found.append([o.get("id") for o, theirs in others if mine and theirs and mine[0] < theirs[1] and theirs[0] < mine[1]])
    return found


def credits_report(items, logged=None):
    rows, crossed = [], overlaps(items, items if logged is None else logged)
    for i, others in zip(items, crossed):
        row = {"id": i.get("id"), "kind": i.get("kind"), "minutes_estimate": i.get("estimate"), "credits_source": i.get("credits_source", "account counter"), "minutes_actual": i["actual"], "credits_estimate": i.get("credits_estimate"), "credits_actual": i.get("credits_actual")}
        if i.get("credits_unknown"):
            row["credits_unknown"] = known_reasons(i["credits_unknown"])
        if others:
            row["overlaps"] = others
        rows.append(row)
    estimated = [r["credits_estimate"] for r in rows if is_number(r["credits_estimate"])]
    actual = [r["credits_actual"] for r in rows if is_number(r["credits_actual"])]
    return {
        "items": rows,
        "estimated": round(sum(estimated), 2) if estimated else None,
        "actual": round(sum(actual), 2) if actual else None,
        "items_estimated": len(estimated),
        "items_measured": len(actual),
        "items_overlapping": sum(bool(o) for o in crossed),
    }


WORKER_KINDS = {"build": "worker-build", "fix": "worker-fix", "review": "worker-review", "rereview": "worker-review", "research": "worker-research"}


def mine_path():
    return Path(os.environ.get("MINE_PY") or Path(__file__).resolve().parents[2] / "orchestrator-workers" / "scripts" / "mine.py")


def worker_records(run_dir, mined, logged):
    """`done` records for a run folder's worker rounds, from mine.py's JSON; credits are the round's own, from its log."""
    seen = {(r.get("run"), r["id"]) for r in logged}
    run = Path(run_dir).name
    out = []
    for r in mined.get("rounds", []):
        kind = WORKER_KINDS.get(r.get("kind"))
        if not kind or (run, r["name"]) in seen or not is_number(r.get("wall_min")):
            continue
        started = parse_time(r["start"])
        active = r["active_min"] if is_number(r.get("active_min")) else r["wall_min"]
        credits = r.get("credits")
        record = {"event": "done", "id": r["name"], "kind": kind, "estimate": None, "actual": round(active, 1), "wall_min": round(r["wall_min"], 1), "method": "history", "serves": "", "run": run, "imported": True, "credits_source": "log", "started": started.isoformat(), "at": (started + timedelta(minutes=active)).isoformat()}
        record |= {"credits_actual": round(credits, 2)} if is_number(credits) else {"credits_actual": None, "credits_unknown": "not-read"}
        out.append(record)
    return out


def import_run(run_dir):
    done = subprocess.run([sys.executable, "-B", str(mine_path()), str(run_dir), "--json"], capture_output=True, timeout=120, stdin=subprocess.DEVNULL)
    if done.returncode != 0:
        return None
    records = worker_records(run_dir, json.loads(done.stdout.decode("utf-8")), completed(read()))
    for record in records:
        append(record)
    return records


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
    return parse_time(text)


def load_run():
    path = run_path()
    return json.loads(path.read_text()) if path.exists() else None


def save_run(run):
    path = run_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run, indent=1))


SESSION_FIELDS = ("sessionId", "session_id", "transcript_path", "transcriptPath")


def session_text(payload):
    return " ".join(str((payload or {}).get(field) or "") for field in SESSION_FIELDS)


def guard_decision(run, records, at, payload=None):
    """The reason the agent must keep working, or None to let the turn end; also returns the run to save."""
    if not run or run.get("blocked") or at >= parse_time(run["until"]):
        return None, run
    if not run.get("session") or run["session"] not in session_text(payload):
        return None, run
    finished = {r["id"] for r in records if r["event"] in ("end", "done", "drop")}
    left = [i for i in run.get("planned") or [] if i not in finished]
    if run.get("planned") and not left:
        return None, run
    progressed = run.get("seen") != len(records)
    blocks = 1 if progressed else run.get("blocks", 0) + 1
    if blocks > GUARD_LIMIT:
        return None, {**run, "blocks": 0, "seen": len(records)}
    stop = parse_time(run["until"]).strftime("%H:%M")
    what = f"{len(left)} planned items are not done (next: {left[0]})" if left else "items may remain"
    reason = (
        f"Run {run['run']} is armed until {stop} and {what}. Do not end the turn: put any question that blocks "
        "nothing in the session memory for the final report, and take the next item. Only if something blocks "
        "every remaining item, run `estimates.py block --reason \"...\"` first; at the wrap-up, `estimates.py disarm`."
    )
    return reason, {**run, "blocks": blocks, "seen": len(records)}


def guard(payload=None):
    """The Stop hook: prints a block decision while an armed run has work left; fails open on any error."""
    try:
        reason, run = guard_decision(load_run(), read(), now(), payload)
        if run is not None:
            save_run(run)
        with run_path().with_name("run-guard.log").open("a") as log:
            log.write(json.dumps({"at": now().isoformat(), "fields": sorted(payload or {}), "session": session_text(payload)[-160:], "blocked": reason is not None}) + "\n")
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
    p.add_argument("--credits", type=float, default=None, help="estimated credits the item spends")
    p = sub.add_parser("end", help="stamp the end of an item")
    p.add_argument("--id", required=True)
    p = sub.add_parser("drop", help="close an item another item covered, or one logged by mistake, so no history counts it")
    p.add_argument("--id", required=True)
    p.add_argument("--reason", required=True, help="for example: covered by <id>")
    p = sub.add_parser("add", help="record a finished item whose actual is already known")
    p.add_argument("--id", required=True)
    p.add_argument("--kind", required=True)
    p.add_argument("--estimate", type=float, required=True)
    p.add_argument("--actual", type=float, required=True)
    p.add_argument("--method", required=True, choices=METHODS)
    p.add_argument("--serves", default="")
    p.add_argument("--at", default=None, help="ISO time it ended; default now")
    p.add_argument("--run", default="")
    p = sub.add_parser("import-run", help="log a worker run folder's builds, fixes, reviews and research as worker-* items, with credits from each worker's own log")
    p.add_argument("run_dir")
    p = sub.add_parser("estimate", help="P50 and P90 for a kind from the log, or minutes for a count of rounds")
    p.add_argument("--kind")
    p.add_argument("--rounds", type=int, help="think-write-run-verify cycles the item needs")
    p.add_argument("--risk", type=float, default=1.0, help="1.0 known ground to 2.0 many unknowns")
    p.add_argument("--days", type=int, default=180)
    p = sub.add_parser("forecast", help="Monte Carlo forecast of a plan against a window")
    p.add_argument("--plan", required=True, help="JSON list of {id, what, kind, estimate, method[, after, slot]}; what = one line saying what the item is")
    p.add_argument("--window", type=float, required=True, help="minutes until the stop time")
    p.add_argument("--runs", type=int, default=1000)
    p.add_argument("--days", type=int, default=180)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--slots", type=int, default=1, help="worker slots running at once; 1 forecasts every item in sequence")
    p = sub.add_parser("throughput", help="days to finish N more items, from items finished per day, zero days included")
    p.add_argument("--items", type=int, required=True, help="items left to finish")
    p.add_argument("--kind", action="append", default=None, help="count only this kind; repeat for more; default every kind except imported worker rounds")
    p.add_argument("--days", type=int, default=28, help="full days of history before today")
    p.add_argument("--runs", type=int, default=1000)
    p.add_argument("--seed", type=int, default=None)
    p = sub.add_parser("report", help="estimate against actual for one run, or all")
    p.add_argument("--run", default=None)
    p = sub.add_parser("kinds", help="markdown table of measured pace per kind")
    p.add_argument("--days", type=int, default=180)
    p = sub.add_parser("arm", help="start the run guard: a Stop hook keeps the agent working until the stop time")
    p.add_argument("--run", required=True)
    p.add_argument("--until", required=True, help="stop time, HH:MM (its next occurrence) or ISO")
    p.add_argument("--session", required=True, help="the chat's session id; other agent sessions (SDK, CLI) load the same hook and must not be held")
    p.add_argument("--plan", default=None, help="plan JSON; the guard lets the turn end once every item in it is done")
    p = sub.add_parser("block", help="a blocker stops every remaining item: let the turn end until the next start")
    p.add_argument("--reason", required=True)
    sub.add_parser("disarm", help="end the run guard at the wrap-up")
    sub.add_parser("guard", help="the Stop hook's check; reads the hook's JSON on stdin")
    args = parser.parse_args(argv)

    if args.command == "start":
        credits = credits_fields("start")
        record = {"event": "start", "id": args.id, "kind": args.kind, "estimate": args.estimate, "method": args.method, "serves": args.serves, "run": args.run, "credits_estimate": args.credits} | credits | {"at": now().isoformat()}
        append(record)
        run = load_run()
        if run and run.get("blocked"):
            save_run({k: v for k, v in run.items() if k not in ("blocked", "blockedAt")})
        shown = ("id", "kind", "estimate", "method", "credits_estimate", "credits_at_start", "credits_unknown")
        print(json.dumps({k: record[k] for k in shown if k in record} | {"started": record["at"]}))
    elif args.command == "end":
        start = open_start(read(), args.id)
        append({"event": "end", "id": args.id} | (end_credits(start) if start else {}) | {"at": now().isoformat()})
        done = [i for i in completed(read()) if i["id"] == args.id]
        if not done:
            print(f"no open start for {args.id}", file=sys.stderr)
            return 1
        shown = ("id", "kind", "estimate", "actual", "credits_estimate", "credits_actual", "credits_unknown")
        print(json.dumps({k: done[-1][k] for k in shown if k in done[-1]}))
    elif args.command == "drop":
        append({"event": "drop", "id": args.id, "reason": args.reason, "at": now().isoformat()})
        print(json.dumps({"id": args.id, "dropped": args.reason}))
    elif args.command == "add":
        append({"event": "done", "id": args.id, "kind": args.kind, "estimate": args.estimate, "actual": args.actual, "method": args.method, "serves": args.serves, "run": args.run, "at": (parse_time(args.at) if args.at else now()).isoformat()})
    elif args.command == "import-run":
        records = import_run(args.run_dir)
        if records is None:
            print("mine.py failed on that run folder", file=sys.stderr)
            return 1
        print(json.dumps({"imported": len(records), "kinds": sorted({r["kind"] for r in records})}))
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
        try:
            result = forecast(plan, args.window, recent(completed(read()), args.days), args.runs, args.seed, args.slots)
        except ValueError as e:
            print(e, file=sys.stderr)
            return 2
        print(json.dumps(result))
    elif args.command == "throughput":
        if args.items < 1 or args.days < 1 or args.runs < 1:
            print("--items, --days and --runs must be at least 1", file=sys.stderr)
            return 2
        counts = daily_counts(completed(read()), args.days, now().date(), args.kind)
        try:
            result = throughput(counts, args.items, args.runs, args.seed)
        except ValueError as e:
            print(e, file=sys.stderr)
            return 2
        print(json.dumps(result))
    elif args.command == "report":
        records = read()
        logged = completed(records)
        items = [i for i in logged if args.run is None or i.get("run") == args.run]
        at = now()
        logged += running(records, at)
        print(json.dumps(report(items, logged) | {"left_open": left_open(records, at)}, indent=2))
    elif args.command == "kinds":
        print(kinds_table(recent(completed(read()), args.days)))
    elif args.command == "arm":
        at = now()
        planned = [item["id"] for item in json.loads(Path(args.plan).read_text())] if args.plan else None
        save_run({"run": args.run, "until": until_time(args.until, at).isoformat(), "session": args.session, "planned": planned, "armedAt": at.isoformat()})
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
        try:
            payload = json.loads(sys.stdin.read() or "{}")
        except ValueError:
            payload = {}
        output = guard(payload if isinstance(payload, dict) else {})
        if output:
            print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
