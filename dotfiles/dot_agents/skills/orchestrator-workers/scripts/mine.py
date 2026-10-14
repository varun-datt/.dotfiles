#!/usr/bin/env python3
"""Mine a run folder: what each round and item cost, how its reviews went, and the dynamic credit caps.

Usage:
    python3 mine.py [RUN] [--since DATE] [--repo PATH]          text summary
    python3 mine.py [RUN] --json                                 everything, for tools
    python3 mine.py [RUN] --caps                                 --max-ai-credits per kind and model
    python3 mine.py --help

RUN defaults to OW_RUN_DIR. Every <name>.jsonl there is one round (markers.jsonl excepted):
    kind     from the run name's last suffix: -fix, -resume, -review, -rereview, -merge, -catchup or
             -research, each with an optional number; no suffix is a build; a round with no known suffix
             that continues an earlier round's session is "other"
    model    and effort from the round's prompt event
    credits  and premium requests from session.usage_checkpoint, which is cumulative across `copilot -r`
             resumes, so each round is the difference from the previous round of its session; reviews and
             re-reviews are their own sessions
    CAPPED   the round hit its --max-ai-credits cap (a "Session limit reached" event)
    verdict  for reviews and re-reviews, from <name>.txt: "Blocking: none" or "N blocking"
An item is the run name without its suffixes. --repo reads `git log --merges --first-parent` of that
repository's HEAD: an item counts as merged when a merge subject names a branch "<prefix>/<item>".

Caps (owner, 2026-10-13): 3 x the median credits of the last 20 rounds of the same kind and model, or a
fixed floor while there are fewer than 5. Markers (`state.py marker`) are measured as the median credits
per round of each kind they cover, before and after, up to the neighbouring markers.
"""
import argparse, collections, datetime, json, os, re, statistics, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import status

SUFFIX = re.compile(r'-(rereview|review|fix|resume|merge|catchup|research)\d*$')
REVIEW_KINDS = ('review', 'rereview')
WORKER_KINDS = ('build', 'research', 'fix', 'resume', 'merge', 'catchup', 'other')
SCOPES = {'all': WORKER_KINDS + REVIEW_KINDS, 'workers': WORKER_KINDS, 'reviews': REVIEW_KINDS,
          'merges': ('merge', 'catchup')}
FIRST_KINDS = ('build', 'research') + REVIEW_KINDS
FACTOR, WINDOW, MIN_ROUNDS = 3, 20, 5
# ASSUMED, for the owner: above the largest single round measured in the source project (3,213).
FLOOR = 3000
CLI_MIN_CAP = 30
NEEDED = ('user.message', 'session.usage_checkpoint', 'result', 'session.info', 'session.warning',
          'session.tools_updated', 'session.error')
TYPE_PREFIX = '{"type":"'
TIMESTAMP = re.compile(r'"timestamp"\s*:\s*"([^"]+)"')
VERDICT = re.compile(r'^(?:blocking\s*:\s*none\b|(\d+)\s+blocking\b)', re.I)
UTC = datetime.timezone.utc


def parse_time(text):
    try:
        t = datetime.datetime.fromisoformat(str(text).replace('Z', '+00:00'))
    except ValueError:
        return None
    return t if t.tzinfo else t.astimezone()


def stamp(line):
    # The top-level timestamp is the line's last key; an earlier match can sit inside nested data.
    found = TIMESTAMP.findall(line)
    return parse_time(found[-1]) if found else None


def split_name(name):
    kinds, item = [], name
    while True:
        m = SUFFIX.search(item)
        if not m or m.start() == 0:
            break
        kinds.append(m.group(1))
        item = item[:m.start()]
    return item, (kinds[0] if kinds else 'build')


def verdict(path):
    """('none', 0), ('N blocking', N), ('missing', None) or ('no verdict', None) from a review's report."""
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        return 'missing', None
    for line in lines:
        m = VERDICT.match(line.strip().lstrip('*_#> ').strip())
        if m:
            n = int(m.group(1)) if m.group(1) else 0
            return ('none' if n == 0 else f'{n} blocking'), n
    return 'no verdict', None


def read_round(path):
    """One run file's facts, or None when it holds no copilot events."""
    r = {'session': None, 'cum_credits': None, 'cum_premium': None, 'model': None, 'effort': None,
         'exit': None, 'error': False, 'cap': None, 'first': None, 'last': None}
    fallback_model = fallback_effort = None
    typed = False
    last_line = None
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            if line.startswith(TYPE_PREFIX):
                t = line[len(TYPE_PREFIX):line.find('"', len(TYPE_PREFIX))]
                typed = True
                if r['first'] is None:
                    r['first'] = stamp(line)
                last_line = line
                if t not in NEEDED:
                    continue
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if not isinstance(e, dict) or not isinstance(e.get('type'), str):
                continue
            typed = True
            last_line = line
            if r['first'] is None and e.get('timestamp'):
                r['first'] = parse_time(e['timestamp'])
            t, d = e['type'], e.get('data') if isinstance(e.get('data'), dict) else {}
            if t == 'user.message' and r['model'] is None:
                rr = d.get('responsesReasoning') if isinstance(d.get('responsesReasoning'), dict) else {}
                r['model'], r['effort'] = rr.get('model'), rr.get('effort')
            elif t == 'session.tools_updated' and fallback_model is None:
                fallback_model = d.get('model')
            elif t == 'session.usage_checkpoint':
                r['cum_credits'] = (d.get('totalNanoAiu') or 0) / 1e9
                r['cum_premium'] = d.get('totalPremiumRequests')
                for state in d.get('promptCacheBreakState') or []:
                    for m in ((state or {}).get('models') or {}).values():
                        fallback_effort = fallback_effort or (m or {}).get('reasoning_effort')
            elif t == 'result':
                r['exit'] = e.get('exitCode')
                r['session'] = e.get('sessionId') or r['session']
            elif t == 'session.error':
                r['error'] = True
            if e.get('sessionId') and not r['session']:
                r['session'] = e['sessionId']
            lim = status.limit_event(e)
            if lim:
                r['cap'] = status.cap_state(r['cap'], lim)
    if not typed:
        return None
    r['last'] = stamp(last_line) if last_line else None
    r['model'] = r['model'] or fallback_model
    r['effort'] = r['effort'] or fallback_effort
    return r


def load_rounds(run):
    rounds = []
    for fn in sorted(os.listdir(run)):
        if not fn.endswith('.jsonl') or fn == 'markers.jsonl':
            continue
        name = fn[:-len('.jsonl')]
        path = os.path.join(run, fn)
        r = read_round(path)
        if r is None:
            continue
        start = None
        try:
            with open(os.path.join(run, name + '.start')) as f:
                start = datetime.datetime.fromtimestamp(int(f.read().strip()), UTC)
        except (OSError, ValueError):
            pass
        start = start or r['first'] or datetime.datetime.fromtimestamp(os.path.getmtime(path), UTC)
        end = r['last'] or datetime.datetime.fromtimestamp(os.path.getmtime(path), UTC)
        item, kind = split_name(name)
        cap = r['cap'] or {}
        rounds.append({'name': name, 'item': item, 'kind': kind, 'model': r['model'], 'effort': r['effort'],
                       'start': start, 'wall_min': max(0.0, (end - start).total_seconds() / 60),
                       'session': r['session'], 'cum_credits': r['cum_credits'], 'cum_premium': r['cum_premium'],
                       'capped': bool(cap.get('capped')), 'cap': cap.get('cap'), 'cap_used': cap.get('used'),
                       'exit': r['exit'], 'error': r['error'], 'ended': r['exit'] is not None,
                       'verdict': None, 'blocking': None, 'raw_verdict': None})
        if kind in REVIEW_KINDS:
            v, b = verdict(os.path.join(run, name + '.txt'))
            if rounds[-1]['capped']:
                rounds[-1].update(verdict='incomplete', blocking=None, raw_verdict=v)
            else:
                rounds[-1]['verdict'], rounds[-1]['blocking'] = v, b
    rounds.sort(key=lambda x: (x['start'], x['name']))
    decumulate(rounds, lost_rounds(run, {r['name'] for r in rounds}))
    return rounds


def lost_rounds(run, loaded):
    """(item, start) of each launched round (a <name>.start) whose events are not in the folder."""
    out = []
    for fn in os.listdir(run):
        name = fn[:-len('.start')]
        if not fn.endswith('.start') or name in loaded:
            continue
        try:
            with open(os.path.join(run, fn)) as f:
                at = datetime.datetime.fromtimestamp(int(f.read().strip()), UTC)
        except (OSError, ValueError):
            at = datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(run, fn)), UTC)
        out.append((split_name(name)[0], at))
    return out


def decumulate(rounds, lost=()):
    """Turn cumulative per-session usage into per-round credits and premium requests."""
    def family(r):
        return ('review', r['name']) if r['kind'] in REVIEW_KINDS else ('worker', r['item'])
    known = {}
    for r in rounds:
        if r['session']:
            known.setdefault(family(r), r['session'])
    sessions = collections.defaultdict(list)
    for r in rounds:
        r['session'] = r['session'] or known.get(family(r)) or '/'.join(family(r))
        sessions[r['session']].append(r)
    for rs in sessions.values():
        first = rs[0]
        prev_c = prev_p = 0
        for i, r in enumerate(rs):
            if i and r['kind'] == 'build':
                r['kind'], r['item'] = 'other', first['item']
            # A fresh launch (a -p catch-up merge, say) is whole; it is partial only when an earlier launch of its item lost its events.
            r['partial'] = i == 0 and r['kind'] not in FIRST_KINDS and any(
                item == r['item'] and at <= r['start'] for item, at in lost)
            r['credits'] = r['premium'] = None
            if r['cum_credits'] is None:
                continue
            # A fall in the running total means a fresh session joined by name, not a resume.
            if r['cum_credits'] < prev_c:
                prev_c = prev_p = 0
            r['credits'] = r['cum_credits'] - prev_c
            if r['cum_premium'] is not None:
                r['premium'] = r['cum_premium'] - prev_p
                prev_p = r['cum_premium']
            prev_c = r['cum_credits']


def merges(repo):
    out = subprocess.run(['git', '-C', repo, 'log', '--merges', '--first-parent', '--format=%cI%x09%s', 'HEAD'],
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(' '.join(out.stderr.split()) or f'git log failed in {repo}')
    rows = []
    for line in reversed(out.stdout.splitlines()):
        when, _, subject = line.partition('\t')
        rows.append((when, subject))
    return rows


def merged_at(item, merge_rows):
    pat = re.compile(r'[\w.-]+/' + re.escape(item) + r'(?![\w.-])')
    for when, subject in merge_rows:
        if pat.search(subject):
            return when
    return None


def items(rounds, merge_rows=None):
    by = collections.OrderedDict()
    for r in rounds:
        by.setdefault(r['item'], []).append(r)
    out = []
    for item, rs in by.items():
        reviews = [r for r in rs if r['kind'] in REVIEW_KINDS]
        first = next((r for r in reviews if r['kind'] == 'review'), None)
        when = merged_at(item, merge_rows) if merge_rows is not None else None
        out.append({'item': item, 'rounds': len(rs), 'credits': sum(r['credits'] or 0 for r in rs),
                    'unknown_credits': sum(r['credits'] is None for r in rs),
                    'premium': sum(r['premium'] or 0 for r in rs),
                    'fix_rounds': sum(r['kind'] == 'fix' for r in rs), 'capped': sum(r['capped'] for r in rs),
                    'wall_min': sum(r['wall_min'] for r in rs),
                    'blocking': first['blocking'] if first else None,
                    'verdicts': [{'round': r['name'], 'verdict': r['verdict'], 'blocking': r['blocking'],
                                  'raw_verdict': r['raw_verdict']} for r in reviews],
                    'merged': None if merge_rows is None else when is not None, 'merged_at': when})
    return out


def usable(r):
    return r['credits'] is not None and not r['partial'] and r['kind'] != 'other'


def caps(rounds, factor=FACTOR, window=WINDOW, min_rounds=MIN_ROUNDS, floor=FLOOR):
    groups = collections.defaultdict(list)
    for r in rounds:
        if usable(r):
            groups[(r['kind'], r['model'] or '?')].append(r)
    out = []
    for (kind, model), rs in sorted(groups.items()):
        last = [r['credits'] for r in sorted(rs, key=lambda x: x['start'])[-window:]]
        med = statistics.median(last)
        enough = len(last) >= min_rounds
        out.append({'kind': kind, 'model': model, 'n': len(last), 'median': round(med, 1),
                    'cap': max(CLI_MIN_CAP, round(factor * med) if enough else floor),
                    'from': f'{factor} x median' if enough else f'floor (n < {min_rounds})'})
    return out


def load_markers(run):
    out = []
    try:
        with open(os.path.join(run, 'markers.jsonl'), encoding='utf-8') as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        return out
    for line in lines:
        try:
            m = json.loads(line)
        except ValueError:
            continue
        at = parse_time(m.get('at')) if isinstance(m, dict) else None
        if at and m.get('scope', 'all') in SCOPES:
            out.append({'at': at, 'label': str(m.get('label') or ''), 'scope': m.get('scope', 'all')})
    return sorted(out, key=lambda m: m['at'])


def measure(markers, rounds):
    """Median credits per round of each covered kind, between the neighbouring markers that cover it."""
    out = []
    for m in markers:
        rows, saving = [], 0.0
        for kind in SCOPES[m['scope']]:
            covering = [x['at'] for x in markers if kind in SCOPES[x['scope']]]
            lo = max((t for t in covering if t < m['at']), default=None)
            hi = min((t for t in covering if t > m['at']), default=None)
            rs = [r for r in rounds if r['kind'] == kind and usable(r)]
            before = [r['credits'] for r in rs if (lo is None or r['start'] >= lo) and r['start'] < m['at']]
            after = [r['credits'] for r in rs if r['start'] >= m['at'] and (hi is None or r['start'] < hi)]
            if not before and not after:
                continue
            mb = statistics.median(before) if before else None
            ma = statistics.median(after) if after else None
            if mb is not None and ma is not None:
                saving += (mb - ma) * len(after)
            rows.append({'kind': kind, 'before_n': len(before), 'before_median': mb and round(mb, 1),
                         'after_n': len(after), 'after_median': ma and round(ma, 1)})
        out.append({'at': iso(m['at']), 'label': m['label'], 'scope': m['scope'], 'kinds': rows,
                    'saving': round(saving)})
    return out


def days(rounds):
    by = collections.OrderedDict()
    for r in rounds:
        d = by.setdefault(r['start'].astimezone().date().isoformat(), {'rounds': 0, 'credits': 0.0, 'capped': 0})
        d['rounds'] += 1
        d['credits'] += r['credits'] or 0
        d['capped'] += r['capped']
    return [{'day': k, **v} for k, v in by.items()]


def kinds(rounds):
    by = collections.defaultdict(list)
    for r in rounds:
        by[(r['kind'], r['model'] or '?')].append(r)
    out = []
    for (kind, model), rs in sorted(by.items()):
        known = [r['credits'] for r in rs if r['credits'] is not None]
        out.append({'kind': kind, 'model': model, 'rounds': len(rs), 'credits': sum(known),
                    'median': round(statistics.median(known), 1) if known else None,
                    'capped': sum(r['capped'] for r in rs)})
    return out


def iso(t):
    return t.astimezone(UTC).isoformat(timespec='seconds').replace('+00:00', 'Z')


def text(report):
    rs, lines = report['rounds'], []
    total = sum(r['credits'] or 0 for r in rs)
    since = f" since {report['since']}" if report['since'] else ''
    lines.append(f"{report['run']}{since}: {len(rs)} rounds, {total:,.0f} credits, "
                 f"{sum(r['premium'] or 0 for r in rs):,} premium requests, {sum(r['capped'] for r in rs)} capped, "
                 f"{sum(r['credits'] is None for r in rs)} with unknown credits")
    lines.append('by kind and model: rounds, credits, median per round, capped')
    for k in report['kinds']:
        med = '-' if k['median'] is None else f"{k['median']:,.0f}"
        lines.append(f"  {k['kind']:<9} {k['model']:<22} {k['rounds']:>4} {k['credits']:>9,.0f} {med:>7} {k['capped']:>3}")
    lines.append('by day: rounds, credits, capped')
    for d in report['days']:
        lines.append(f"  {d['day']} {d['rounds']:>4} {d['credits']:>9,.0f} {d['capped']:>3}")
    lines.append('items: rounds, credits, fix rounds, blocking at review -> last verdict, merged')
    for it in report['items']:
        first = '-' if it['blocking'] is None else str(it['blocking'])
        last = it['verdicts'][-1]['verdict'] if it['verdicts'] else '-'
        merged = '' if it['merged'] is None else (f" merged {it['merged_at'][:10]}" if it['merged'] else ' not merged')
        unknown = f" (+{it['unknown_credits']} unknown)" if it['unknown_credits'] else ''
        capped = f" capped {it['capped']}" if it['capped'] else ''
        lines.append(f"  {it['item']:<28} {it['rounds']:>3} {it['credits']:>8,.0f}{unknown} fix {it['fix_rounds']} "
                     f"blocking {first} -> {last}{capped}{merged}")
    partial = [r['name'] for r in rs if r['partial']]
    if partial:
        lines.append(f"partial (earlier rounds of the session are not in the folder): {', '.join(partial)}")
    if report['markers']:
        lines.append('markers: median credits per round before -> after (n), estimated saving')
        for m in report['markers']:
            parts = [f"{k['kind']} {fmt(k['before_median'])} ({k['before_n']}) -> {fmt(k['after_median'])} ({k['after_n']})"
                     for k in m['kinds']]
            lines.append(f"  {m['at']} {m['label']!r} [{m['scope']}]: saving {m['saving']:,}; " + ('; '.join(parts) or 'no rounds'))
    return '\n'.join(lines)


def fmt(x):
    return '-' if x is None else f'{x:,.0f}'


def main(argv=None):
    ap = argparse.ArgumentParser(description='Mine a run folder for spend, review verdicts and dynamic credit caps.')
    ap.add_argument('run', nargs='?', default=status.RUN, help='run folder (default: $OW_RUN_DIR)')
    ap.add_argument('--since', help='only rounds started at or after this ISO date or time')
    ap.add_argument('--repo', help='repository whose `git log` shows which items were merged')
    out = ap.add_mutually_exclusive_group()
    out.add_argument('--json', action='store_true', help='print everything as JSON')
    out.add_argument('--caps', action='store_true', help='print the --max-ai-credits cap per kind and model')
    ap.add_argument('--floor', type=int, default=FLOOR, help=f'cap while a kind and model has fewer than {MIN_ROUNDS} rounds (default {FLOOR})')
    a = ap.parse_args(argv)

    run = os.path.abspath(os.path.expanduser(a.run))
    if not os.path.isdir(run):
        print(f'mine.py: no run folder at {run}', file=sys.stderr)
        return 2
    since = None
    if a.since:
        since = parse_time(a.since)
        if since is None:
            print(f'mine.py: --since {a.since!r} is not an ISO date or time', file=sys.stderr)
            return 2
    merge_rows = None
    if a.repo:
        try:
            merge_rows = merges(a.repo)
        except (OSError, RuntimeError) as e:
            print(f'mine.py: --repo: {e}', file=sys.stderr)
            return 2
    rounds = load_rounds(run)
    if since:
        rounds = [r for r in rounds if r['start'] >= since]
    cap_rows = caps(rounds, floor=a.floor)
    if a.caps:
        for c in cap_rows:
            print(f"{c['kind']:<9} {c['model']:<22} --max-ai-credits {c['cap']:<6} {c['from']}: median {c['median']:,.0f}, n={c['n']}")
        print(f"any other kind or model: --max-ai-credits {a.floor} floor (n < {MIN_ROUNDS})")
        return 0
    report = {'run': run, 'since': a.since, 'rounds': rounds, 'items': items(rounds, merge_rows),
              'kinds': kinds(rounds), 'days': days(rounds), 'caps': cap_rows,
              'markers': measure(load_markers(run), rounds)}
    if a.json:
        for r in rounds:
            r['start'] = iso(r['start'])
            r['wall_min'] = round(r['wall_min'], 1)
            for k in ('credits', 'cum_credits'):
                if r[k] is not None:
                    r[k] = round(r[k], 1)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    print(text(report))
    return 0


if __name__ == '__main__':
    sys.exit(main())
