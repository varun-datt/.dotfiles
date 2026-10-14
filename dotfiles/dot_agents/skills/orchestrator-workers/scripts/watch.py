#!/usr/bin/env python3
"""Watchdog for orchestrator-workers: turns time into a notification for the orchestrator.

Usage (run in an async terminal; the orchestrator is notified when it exits):
    timeout 86400 python3 watch.py [HEARTBEAT_MIN]     # default heartbeat 30 awake minutes
    python3 watch.py --tables                          # the status table on every exit
    python3 watch.py --progress                        # one line a minute, for a wait inside a turn
    python3 watch.py --help

It exits, with a reason, as soon as:
    ALERT     a worker died (no result event) or its output has not grown for OW_STALL_MIN awake minutes;
    ALERT     a worker hit its --max-ai-credits cap (CAPPED; its result event still says exitCode 0);
    ALERT     a running worker passed its time budget (once per worker; recorded in <run>/over-alerted.txt);
    IDLE      no worker is running;
    HEARTBEAT HEARTBEAT_MIN awake minutes have passed.
Restart it after every report. A pidfile (<run>/watch.pid) stops a second copy from running.

Output: when the run folder is in the run registry (`state.py init`), the dashboard shows the table, so
every exit prints one line: the reason, the workers it names, and counts (running, stalled, died).
Otherwise, or with --tables, it prints the reason line and then the status table.

Sleep handling: a wall-clock gap of more than two ticks means the machine slept. Sleep does not count
towards the heartbeat, and the stall clock restarts at wake, so a sleeping laptop does not raise a
false stall the moment it wakes.

Environment: OW_RUN_DIR, OW_PREFIX, OW_STALL_MIN (see status.py); OW_REGISTRY (see state.py).
"""
import argparse, json, os, signal, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import state, status

TICK = 60


def alerted():
    try:
        with open(os.path.join(status.RUN, 'over-alerted.txt')) as f:
            return f.read().split()
    except OSError:
        return []


def registered():
    real = os.path.realpath(status.RUN)
    try:
        with open(state.registry_path(), encoding='utf-8') as f:
            lines = f.read().splitlines()
    except (OSError, ValueError):
        return False
    for raw in lines:
        try:
            e = json.loads(raw)
        except ValueError:
            continue
        if isinstance(e, dict) and isinstance(e.get('dir'), str) and os.path.realpath(e['dir']) == real:
            return True
    return False


def counts(rs):
    capped = sum(r['state'] == 'CAPPED' for r in rs)
    return (f"running={sum(r['state'] == 'running' for r in rs)} stalled={sum(r['state'] == 'STALLED' for r in rs)} "
            f"died={sum(r['state'].startswith('DIED') for r in rs)}" + (f" capped={capped}" if capped else ''))


def main(argv=None):
    ap = argparse.ArgumentParser(description='Exit with a reason when a worker stalls, dies, runs over budget, '
                                             'all workers finish, or the heartbeat is due.',
                                 epilog=f'Run folder: {status.RUN} (set OW_RUN_DIR). A registered run gets one line '
                                        'per exit; an unregistered one gets the reason and the status table.')
    ap.add_argument('heartbeat_min', nargs='?', type=float, default=30, help='heartbeat in awake minutes (default 30)')
    ap.add_argument('--tables', action='store_true', help='print the reason and the status table, even for a registered run')
    ap.add_argument('--progress', action='store_true', help='print one short line each minute while watching')
    args = ap.parse_args(argv)

    os.makedirs(status.RUN, exist_ok=True)
    pidfile = os.path.join(status.RUN, 'watch.pid')
    if os.path.exists(pidfile):
        try:
            with open(pidfile) as f:
                os.kill(int(f.read()), 0)
            print('watchdog already running; not starting a second one')
            return 0
        except (OSError, ValueError):
            pass
    with open(pidfile, 'w') as f:
        f.write(str(os.getpid()))
    # `timeout` sends TERM; exit through `finally` so the pidfile goes too.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))

    awake = 0.0
    last = last_wake = time.time()
    reason = None
    named = []
    try:
        while reason is None:
            now = time.time()
            gap = now - last
            last = now
            if gap > 2 * TICK:
                last_wake = now
            else:
                awake += gap
            rs = status.rows()
            since_wake = (now - last_wake) / 60
            over = [r for r in rs if r['state'] in ('running', 'STALLED') and r['elapsed'] > r['budget']
                    and r['name'] not in alerted()]
            stuck = [r for r in rs if r['state'].startswith('DIED') or (
                r['state'] == 'STALLED' and min(r['idle'], since_wake) >= status.STALL_MIN)]
            capped = [r for r in rs if r['state'] == 'CAPPED']
            if stuck or capped:
                reason = 'ALERT: a worker stalled or died' if stuck else 'ALERT: a worker hit its credit cap'
                named = [f"{r['name']} {r['state'].split()[0]}" for r in stuck] + [
                    f"{r['name']} CAPPED {status.credits(r.get('cap') or {})}" for r in capped]
            elif over:
                with open(os.path.join(status.RUN, 'over-alerted.txt'), 'a') as f:
                    f.write(''.join(r['name'] + '\n' for r in over))
                reason = 'ALERT: over time budget: ' + ', '.join(
                    f"{r['name']} {r['elapsed']:.0f}m/{r['budget']}m" for r in over)
            elif not any(r['state'] in ('running', 'STALLED') for r in rs):
                reason = 'IDLE: no worker running'
            elif awake >= args.heartbeat_min * 60:
                reason = f'HEARTBEAT: {args.heartbeat_min:.0f} awake minutes'
            else:
                if args.progress:
                    left = max(0.0, args.heartbeat_min - awake / 60)
                    print(f"{time.strftime('%H:%M')} watching: {counts(rs)}; heartbeat in {left:.0f}m", flush=True)
                time.sleep(TICK)
    finally:
        try:
            os.remove(pidfile)
        except OSError:
            pass
    if args.tables or not registered():
        print(reason, flush=True)
        return status.main([])
    print(f"{reason}{': ' + ', '.join(named) if named else ''}; {counts(rs)}", flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
