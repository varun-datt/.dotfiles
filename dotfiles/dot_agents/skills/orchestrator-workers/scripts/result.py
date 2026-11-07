#!/usr/bin/env python3
"""Summarise one worker run: events, models, wall time, spend, tool calls, then its final report.

Usage:
    python3 result.py <name>.jsonl [--no-report]
    python3 result.py <name>                       # resolved inside OW_RUN_DIR
    python3 result.py --help

The report is the last `assistant.message` content. A run's last event should be `result`; check its
exitCode and any `session.error` before trusting the report (status.py does this).
A run launched with --max-ai-credits that hit its cap still ends with exitCode 0; result_exit keeps that raw
code, while outcome=CAPPED and exit status 3 say it is never done: extend it (resume with a raised cap) or
narrow it. Other outcomes: ended (exitCode 0), ERRORED (another exitCode), NO RESULT.
`session.usage_checkpoint` is cumulative across `copilot -r` resumes, so for a round that continued a session the
usage line prints the growth since that session's previous round in this folder (mine.py's decumulate()) as
premium_requests and ai_credits, with the running total as session_premium_requests and session_ai_credits; when
the earlier rounds are not in the folder it prints only the session figures, labelled as the running total.
1 AI credit = totalNanoAiu / 1e9.
"""
import argparse, collections, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mine, status


def resumed(path, r):
    """Whether the round continued an earlier session: a -resume<N> name, a --resume-session launch, or a lost first round."""
    run, fn = os.path.split(os.path.abspath(path))
    name = fn[:-len('.jsonl')]
    launches = [d for _, d in mine.read_routes(run) if d.get('event') == 'launch' and d.get('round') == name]
    return (mine.split_name(name)[1] == 'resume' or bool(launches and launches[-1].get('resumes'))
            or bool(r and r.get('partial')))


def usage_line(path, usage):
    """The round's credits; a resumed session's checkpoint is its running total, so the earlier rounds are subtracted."""
    total_p, total_c = usage.get('totalPremiumRequests'), (usage.get('totalNanoAiu') or 0) / 1e9
    session = f"session_premium_requests={total_p} session_ai_credits={total_c:.1f}"
    r = mine.round_in_folder(path)
    if r and r['credits'] is not None and r['credits'] < r['cum_credits']:
        return f"premium_requests={r['premium']} ai_credits={r['credits']:.1f} {session} (session total)"
    if resumed(path, r):
        return f"{session} (session running total; its earlier rounds are not in this folder, so this round's share is unknown)"
    return f"premium_requests={total_p} ai_credits={total_c:.1f}"


def main(argv=None):
    ap = argparse.ArgumentParser(description='Summarise a copilot --output-format json run file.')
    ap.add_argument('path', help='<name>.jsonl, or a run name inside OW_RUN_DIR')
    ap.add_argument('--no-report', action='store_true', help='omit the final assistant message')
    args = ap.parse_args(argv)

    path = args.path
    if not os.path.exists(path):
        alt = os.path.join(status.RUN, path if path.endswith('.jsonl') else path + '.jsonl')
        if not os.path.exists(alt):
            print(f'no such run file: {path}', file=sys.stderr)
            return 2
        path = alt
    start_file = path.rsplit('.', 1)[0] + '.start'
    last_msg, usage, models, n = None, None, set(), 0
    tools = collections.Counter()
    result = cap = None
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            try:
                e = json.loads(line)
            except Exception:
                continue
            n += 1
            t = e.get('type')
            d = e.get('data') or {}
            if t == 'assistant.message' and d.get('content'):
                last_msg = d['content']
            if t == 'session.usage_checkpoint':
                usage = d
            if t == 'tool.execution_start':
                tools[str(d.get('toolName') or d.get('name') or '?')] += 1
            if t == 'result':
                result = e.get('exitCode')
            lim = status.limit_event(e)
            if lim:
                cap = status.cap_state(cap, lim)
            if isinstance(d, dict) and isinstance(d.get('model'), str):
                models.add(d['model'])
    start = None
    if os.path.exists(start_file):
        try:
            with open(start_file) as f:
                start = int(f.read().strip())
        except ValueError:
            pass
    wall = f" wall_min={(os.path.getmtime(path) - start) / 60:.1f}" if start else ''
    capped = bool(cap and cap['capped'])
    outcome = ('CAPPED' if capped else 'NO RESULT' if result is None else 'ERRORED' if result != 0 else 'ended')
    print(f"events={n} models={sorted(models)}{wall} result_exit={result if result is not None else 'NONE'}")
    print(f"outcome={outcome}")
    if cap and cap['capped']:
        print(f"CAPPED at {status.credits(cap)} AI credits: not done; extend it with a raised cap or narrow it")
    elif cap:
        print(f"cap: {status.credits(cap)} AI credits used")
    if usage:
        print(usage_line(path, usage))
    else:
        print('usage=none')
    mcp = {k: v for k, v in tools.items() if 'mcp' in k.lower() or '/' in k}
    print(f"tool_calls={sum(tools.values())} distinct_tools={len(tools)} mcp_calls={mcp or 0}")
    print('-' * 20)
    if not args.no_report:
        print(last_msg or 'NO assistant.message')
    return 3 if capped else 0


if __name__ == '__main__':
    sys.exit(main())
