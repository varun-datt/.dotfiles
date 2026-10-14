#!/usr/bin/env python3
"""Status table for orchestrator-workers sessions: workers, reviewers and research workers.

Usage:
    python3 status.py            # active workers only
    python3 status.py --all      # every run, including finished ones
    python3 status.py --help

Environment:
    OW_RUN_DIR    run folder (default: ~/.local/state/orchestrator-workers/run).
                     Keep it out of /tmp; it holds the only copy of each worker's output.
    OW_PREFIX     session-name prefix given to `copilot -n` (default: "ow-").
    OW_STALL_MIN  minutes without output growth that count as a stall (default: 20).

Run-folder convention, one set per run (a build, review, fix, resume or merge round):
    <name>.start   epoch seconds written just before launch (`date +%s > <name>.start`)
    <name>.jsonl   `copilot --output-format json` output
    <name>.err     stderr
A worker launched with `-n ${OW_PREFIX}<item>` is recognised as live for <item>.jsonl and for
later rounds named <item>-fix1, <item>-review, <item>-resume1 ... The run file name must equal the
session name minus the prefix, or a live worker reads as dead.

Time budgets (timeboxes) in minutes come from <run>/budgets.json ({"*": 90, "<name>": 45, ...}); a name not
listed falls back to the suffix defaults below, then to "*", then to 90.
"""
import argparse, glob, json, os, re, subprocess, sys, time

RUN = os.path.abspath(os.path.expanduser(os.environ.get(
    'OW_RUN_DIR', '~/.local/state/orchestrator-workers/run')))
PREFIX = os.environ.get('OW_PREFIX', 'ow-')
STALL_MIN = float(os.environ.get('OW_STALL_MIN', '20'))
BUDGET_DEFAULT = [('-rereview', 20), ('-review', 30), ('-fix', 60), ('-resume', 60), ('-merge', 60),
                  ('-research', 30)]
ROUND = r'-(fix|resume|review|rereview|merge)\w*$'
# Only a retry, fix or resume continues a capped round's work; a review of it does not.
CONTINUE = r'-(fix|resume)\w*$'
CREDITS = re.compile(r'(\d[\d,]*(?:\.\d+)?)\s*/\s*(\d[\d,]*(?:\.\d+)?)\s*AI credits used')


def limit_event(e):
    """(used, cap, reached) from a --max-ai-credits session.info or session.warning event, else None.

    Matching on the event type keeps tool output that quotes these messages from counting.
    """
    if e.get('type') not in ('session.info', 'session.warning'):
        return None
    msg = str((e.get('data') or {}).get('message') or '')
    reached = 'Session limit reached' in msg
    m = CREDITS.search(msg)
    if not (m or reached):
        return None
    used, cap = (float(m.group(1).replace(',', '')), float(m.group(2).replace(',', ''))) if m else (None, None)
    return used, cap, reached


def cap_state(cap, lim):
    """Fold one limit_event result into {'used', 'cap', 'capped'}."""
    cap = dict(cap or {'used': None, 'cap': None, 'capped': False})
    used, limit, reached = lim
    if used is not None:
        cap['used'], cap['cap'] = used, limit
    cap['capped'] = cap['capped'] or reached
    return cap


def budget(name):
    try:
        with open(os.path.join(RUN, 'budgets.json')) as f:
            b = json.load(f)
    except (OSError, ValueError):
        b = {}
    if name in b:
        return b[name]
    for suffix, minutes in BUDGET_DEFAULT:
        if re.search(re.escape(suffix) + r'\w*$', name):
            return minutes
    return b.get('*', 90)


def procs():
    out = subprocess.run(['ps', '-axww', '-o', 'pid=,args='], capture_output=True, text=True).stdout
    names = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 2 or os.path.basename(parts[1]) != 'copilot':
            continue
        for flag, value in zip(parts[1:], parts[2:]):
            if flag in ('-n', '-r', '--name', '--resume') and value.startswith(PREFIX):
                names.add(value[len(PREFIX):])
            elif flag.startswith(('--name=', '--resume=')) and flag.split('=', 1)[1].startswith(PREFIX):
                names.add(flag.split('=', 1)[1][len(PREFIX):])
    return names


def activity(path):
    open_calls, last_type, usage, cap = {}, None, None, None
    i = last_error = last_progress = 0
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            try:
                e = json.loads(line)
            except Exception:
                continue
            i += 1
            t, d = e.get('type'), e.get('data') or {}
            # A `result` event is not success: check its exitCode and any session.error after progress.
            if t == 'result' and e.get('exitCode') not in (0, None):
                last_error = i + 1
            if t == 'session.error':
                last_error = i
            if t in ('model.call_finished', 'tool.execution_complete'):
                last_progress = i
            if t in ('tool.execution_start', 'tool.execution_complete', 'model.call_start', 'model.call_finished', 'result'):
                last_type = t
            if t == 'tool.execution_start':
                args = d.get('arguments') or {}
                desc = args.get('command') or args.get('description') or args.get('path') or args.get('skill') or ''
                open_calls[d.get('toolCallId')] = f"{d.get('toolName')}: {' '.join(str(desc).split())[:70]}"
            elif t == 'tool.execution_complete':
                open_calls.pop(d.get('toolCallId'), None)
            elif t == 'session.usage_checkpoint':
                usage = d
            lim = limit_event(e)
            if lim:
                cap = cap_state(cap, lim)
    if cap and cap['capped']:
        now_doing = f"CAPPED at {credits(cap)} AI credits; extend or narrow it"
    elif last_type == 'result':
        now_doing = 'ENDED ON ERROR' if last_error > last_progress else 'finished'
    elif open_calls:
        now_doing = list(open_calls.values())[-1]
    elif last_type == 'model.call_start':
        now_doing = 'thinking (model call)'
    else:
        now_doing = last_type or 'starting'
    return last_type, now_doing, usage, cap


def credits(cap):
    used = '?' if cap.get('used') is None else f"{cap['used']:g}"
    limit = '?' if cap.get('cap') is None else f"{cap['cap']:g}"
    return f'{used}/{limit}'


def rows():
    if not os.path.isdir(RUN):
        return []
    running = procs()
    now = time.time()
    out = []
    starts = sorted(glob.glob(os.path.join(RUN, '*.start')), key=os.path.getmtime)
    newest = {}
    for sf in starts:
        nm = os.path.basename(sf)[:-6]
        for r in running:
            if nm == r or nm.startswith(r + '-'):
                newest[r] = nm
    for start_file in starts:
        name = os.path.basename(start_file)[:-6]
        jl = os.path.join(RUN, name + '.jsonl')
        if not os.path.exists(jl):
            continue
        try:
            with open(start_file) as f:
                start = int(f.read().strip())
        except (OSError, ValueError):
            start = int(os.path.getmtime(start_file))
        mtime = os.path.getmtime(jl)
        last_type, doing, usage, cap = activity(jl)
        alive = any((name == r or name.startswith(r + '-')) and newest.get(r) == name for r in running)
        later = [s for s in starts if os.path.getmtime(s) > os.path.getmtime(start_file)]
        fam = re.sub(ROUND, '', name)
        superseded = any(re.sub(ROUND, '', os.path.basename(s)[:-6]) == fam for s in later)
        continued = any(re.sub(CONTINUE, '', os.path.basename(s)[:-6]) == fam for s in later)
        # A capped run still ends with a `result` whose exitCode is 0, so the cap is checked first.
        if cap and cap['capped']:
            state = 'superseded' if continued and not alive else 'CAPPED'
        elif last_type == 'result' and doing != 'ENDED ON ERROR':
            state = 'done'
        elif last_type == 'result':
            state = 'superseded' if superseded else 'ERRORED'
        elif alive:
            state = 'STALLED' if now - mtime >= STALL_MIN * 60 else 'running'
        else:
            state = 'superseded' if superseded else 'DIED (no result)'
        end = now if state in ('running', 'STALLED') else mtime
        prem = usage.get('totalPremiumRequests') if usage else None
        aiu = (usage.get('totalNanoAiu') or 0) / 1e9 if usage else None
        out.append({'name': name, 'state': state, 'elapsed': (end - start) / 60, 'idle': (now - mtime) / 60,
                    'doing': doing, 'premium': prem, 'aiu': aiu, 'budget': budget(name), 'cap': cap})
    return out


def table(rs, only_active=False):
    lines = []
    for r in rs:
        if only_active and r['state'] in ('done', 'superseded'):
            continue
        spend = f"{r['premium']}pr/{r['aiu']:.0f}AIU" if r['premium'] is not None else '-'
        if r.get('cap') and r['cap'].get('cap') is not None:
            spend = f"{credits(r['cap'])}cr"
        idle = f"{r['idle']:.0f}m" if r['state'] != 'done' else ''
        over = (f" OVER {r['elapsed'] / r['budget']:.1f}x of {r['budget']}m"
                if r['state'] in ('running', 'STALLED') and r['elapsed'] > r['budget'] else '')
        lines.append(f"{r['name']:<24} {r['state']:<9} {r['elapsed']:>5.0f}m  idle {idle:<4} {spend:<13} "
                     f"{r['doing'] if r['state'] != 'done' else ''}{over}")
    return '\n'.join(lines)


def power():
    try:
        batt = subprocess.run(['pmset', '-g', 'batt'], capture_output=True, text=True).stdout
    except OSError:
        return '?'
    if "'AC Power'" in batt:
        return 'AC'
    return 'battery ' + (batt.split('\t')[-1].split(';')[0].strip() if '\t' in batt else '?')


def main(argv=None):
    ap = argparse.ArgumentParser(description='Status table of orchestrator-workers sessions.',
                                 epilog=f'Run folder: {RUN} (set OW_RUN_DIR). Prefix: {PREFIX!r} (set OW_PREFIX).')
    ap.add_argument('--all', action='store_true', help='include finished and superseded runs')
    args = ap.parse_args(argv)
    rs = rows()
    load = os.getloadavg()
    print(f"{time.strftime('%H:%M')}  running={sum(r['state'] == 'running' for r in rs)} "
          f"stalled={sum(r['state'] == 'STALLED' for r in rs)} died={sum(r['state'].startswith('DIED') for r in rs)} "
          f"errored={sum(r['state'] == 'ERRORED' for r in rs)} done={sum(r['state'] == 'done' for r in rs)} "
          f"capped={sum(r['state'] == 'CAPPED' for r in rs)}  "
          f"load={load[0]:.1f}/{os.cpu_count()}cpu  power={power()}")
    if not os.path.isdir(RUN):
        print(f'(run folder {RUN} does not exist yet)')
    t = table(rs, only_active=not args.all)
    if t:
        print(t)


if __name__ == '__main__':
    sys.exit(main())
