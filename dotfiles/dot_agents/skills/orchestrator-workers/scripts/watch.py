#!/usr/bin/env python3
"""Watchdog for orchestrator-workers: turns time into a notification for the orchestrator.

Usage (run in an async terminal; the orchestrator is notified when it exits):
    timeout 86400 python3 watch.py [HEARTBEAT_MIN]     # default heartbeat 30 awake minutes
    python3 watch.py --help

It exits, printing one reason line and then the status table, as soon as:
    ALERT     a worker died (no result event) or its output has not grown for OW_STALL_MIN awake minutes;
    ALERT     a running worker passed its time budget (once per worker; recorded in <run>/over-alerted.txt);
    IDLE      no worker is running;
    HEARTBEAT HEARTBEAT_MIN awake minutes have passed.
Restart it after every report. A pidfile (<run>/watch.pid) stops a second copy from running.

Sleep handling: a wall-clock gap of more than two ticks means the machine slept. Sleep does not count
towards the heartbeat, and the stall clock restarts at wake, so a sleeping laptop does not raise a
false stall the moment it wakes.

Environment: OW_RUN_DIR, OW_PREFIX, OW_STALL_MIN (see status.py).
"""
import argparse, os, signal, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import status

TICK = 60


def alerted():
    try:
        with open(os.path.join(status.RUN, 'over-alerted.txt')) as f:
            return f.read().split()
    except OSError:
        return []


def main(argv=None):
    ap = argparse.ArgumentParser(description='Exit with a reason when a worker stalls, dies, runs over budget, '
                                             'all workers finish, or the heartbeat is due; then print status.',
                                 epilog=f'Run folder: {status.RUN} (set OW_RUN_DIR).')
    ap.add_argument('heartbeat_min', nargs='?', type=float, default=30, help='heartbeat in awake minutes (default 30)')
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
            if any(r['state'].startswith('DIED') for r in rs) or any(
                    r['state'] == 'STALLED' and min(r['idle'], since_wake) >= status.STALL_MIN for r in rs):
                reason = 'ALERT: a worker stalled or died'
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
                time.sleep(TICK)
    finally:
        try:
            os.remove(pidfile)
        except OSError:
            pass
    print(reason, flush=True)
    return status.main([])


if __name__ == '__main__':
    sys.exit(main())
