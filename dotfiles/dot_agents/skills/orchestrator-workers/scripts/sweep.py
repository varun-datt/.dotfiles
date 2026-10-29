#!/usr/bin/env python3
"""Stop what a finished worker left running, and hold heavy work while the Mac swaps.

  sweep.py leftovers WORKTREE [--kill]   orphans (parent 1) whose working folder is inside WORKTREE,
                                         and orphan `yes` processes anywhere; --kill stops them
  sweep.py load [--wait MIN]             exit 0 when no `yes` runs and swapouts are not rising;
                                         else re-check every 30 s for MIN minutes, then exit 12

On 2026-10-29 a worker's stress loop, a zsh script run by bash, killed 1 of its 8 `yes` processes;
the other 7 ran orphaned for about 5 hours at 5.3 cores while the Mac swapped.
"""
import argparse, os, re, signal, subprocess, sys, time

SWAP_PAGES = 1000  # pages swapped out per sample that count as swapping: a guess, so every check prints its reading
SAMPLE_S = 5


def processes():
    out = subprocess.run(['/bin/ps', '-axo', 'pid=,ppid=,comm='], capture_output=True, text=True,
                         stdin=subprocess.DEVNULL).stdout
    procs = {}
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            procs[int(parts[0])] = (int(parts[1]), parts[2])
    return procs


def cwds():
    out = subprocess.run(['/usr/sbin/lsof', '-nP', '-d', 'cwd', '-Fpn'], capture_output=True, text=True,
                         stdin=subprocess.DEVNULL).stdout
    res, pid = {}, None
    for line in out.splitlines():
        if line.startswith('p') and line[1:].isdigit():
            pid = int(line[1:])
        elif line.startswith('n') and pid is not None:
            res[pid] = line[1:]
    return res


def is_yes(comm):
    return os.path.basename(comm) == 'yes'


def leftovers(worktree, procs, dirs):
    root = worktree.rstrip('/') + '/'
    return sorted((pid, comm, dirs.get(pid, '')) for pid, (ppid, comm) in procs.items()
                  if ppid == 1 and ((dirs.get(pid, '') + '/').startswith(root) or is_yes(comm)))


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def stop(pids):
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    deadline = time.time() + 3
    while time.time() < deadline and any(alive(p) for p in pids):
        time.sleep(0.2)
    for pid in pids:
        if alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass


def swapouts():
    out = subprocess.run(['/usr/bin/vm_stat'], capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
    m = re.search(r'^Swapouts:\s+(\d+)', out, re.M)
    return int(m.group(1)) if m else 0


def load_reason(procs, swap_delta):
    stress = [pid for pid, (_, comm) in procs.items() if is_yes(comm)]
    if stress:
        return f'{len(stress)} yes process(es) running'
    if swap_delta > SWAP_PAGES:
        return f'swapping: {swap_delta} pages out in {SAMPLE_S} s'
    return None


def cmd_leftovers(args):
    root = os.path.realpath(os.path.expanduser(args.worktree))
    stopped = []
    for _ in range(3):  # stopping a parent orphans its children, so look again
        found = leftovers(root, processes(), cwds())
        if not found or not args.kill:
            break
        stop([pid for pid, _, _ in found])
        stopped += found
    for pid, comm, cwd in (stopped if args.kill else found):
        print(f"{'stopped' if args.kill else 'left running'} {pid} {comm} cwd={cwd or '?'}")
    n = len(stopped if args.kill else found)
    print(f"leftovers in {root}: {n} {'stopped' if args.kill else 'found'}" if n else f"leftovers in {root}: none")
    return 0


def cmd_load(args):
    deadline = time.time() + args.wait * 60
    last = None
    while True:
        a = swapouts()
        time.sleep(SAMPLE_S)
        delta = swapouts() - a
        reason = load_reason(processes(), delta)
        if reason is None:
            print(f"load ok: swapouts +{delta} in {SAMPLE_S} s")
            return 0
        if reason != last:
            print(f"{time.strftime('%H:%M:%S')} holding: {reason}", flush=True)
            last = reason
        if time.time() >= deadline:
            print(f"LOAD: still {reason} after {args.wait:g} min")
            return 12
        time.sleep(30)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    lo = sub.add_parser('leftovers', help='list or stop what a finished worker left running')
    lo.add_argument('worktree')
    lo.add_argument('--kill', action='store_true')
    ld = sub.add_parser('load', help='wait until nothing swaps and no stress load runs')
    ld.add_argument('--wait', type=float, default=0, help='minutes to keep re-checking (default 0)')
    args = ap.parse_args(argv)
    return cmd_leftovers(args) if args.cmd == 'leftovers' else cmd_load(args)


if __name__ == '__main__':
    sys.exit(main())
