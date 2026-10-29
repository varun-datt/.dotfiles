#!/usr/bin/env python3
"""Mine a run folder: what each round and item cost, how its reviews went, and the dynamic credit caps.

Usage:
    python3 mine.py [RUN] [--since DATE] [--repo PATH]          text summary
    python3 mine.py [RUN] --json                                 everything, for tools
    python3 mine.py [RUN] --caps                                 --max-ai-credits per kind and model
    options: --history RUN...  earlier runs join the caps' window; --prices FILE; --chat DEBUG_LOG_DIR; --budget N
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
COLD_AFTER = 300
CLASSES = ('input', 'output', 'cache_read', 'cache_write')
USAGE_KEYS = CLASSES + ('reasoning', 'calls')
PRICE_KEYS = {'input': 'inputPrice', 'output': 'outputPrice', 'cache_read': 'cacheReadPrice',
              'cache_write': 'cacheWritePrice'}
HERE = os.path.dirname(os.path.abspath(__file__))
NEEDED = ('model.call_start', 'user.message', 'session.usage_checkpoint', 'result', 'session.info', 'session.warning',
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
         'exit': None, 'error': False, 'cap': None, 'first': None, 'last': None,
         'usage_cum': None}
    calls = []
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
            elif t == 'model.call_start':
                at = parse_time(e.get('timestamp'))
                if at:
                    calls.append(at)
            elif t == 'session.tools_updated' and fallback_model is None:
                fallback_model = d.get('model')
            elif t == 'session.usage_checkpoint':
                r['cum_credits'] = (d.get('totalNanoAiu') or 0) / 1e9
                r['cum_premium'] = d.get('totalPremiumRequests')
                r['usage_cum'] = cumulative_usage(d, r['model']) or r['usage_cum']
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
    calls.sort()
    r['call_starts'] = len(calls)
    r['cold_calls'] = sum((b - a).total_seconds() > COLD_AFTER for a, b in zip(calls, calls[1:]))
    r['model'] = r['model'] or fallback_model
    r['effort'] = r['effort'] or fallback_effort
    return r


def cumulative_usage(checkpoint, model):
    """The session's running token classes and call count for the round's model, from a usage checkpoint."""
    snap = checkpoint.get('accountingSnapshot')
    metrics = snap.get('modelMetrics') if isinstance(snap, dict) else None
    if not isinstance(metrics, dict) or not metrics:
        return None
    m = metrics.get(model) or next(iter(metrics.values())) or {}
    u = m.get('usage') or {}
    cache_read, cache_write = u.get('cacheReadTokens') or 0, u.get('cacheWriteTokens') or 0
    return {'input': max(0, (u.get('inputTokens') or 0) - cache_read - cache_write), 'output': u.get('outputTokens') or 0,
            'cache_read': cache_read, 'cache_write': cache_write, 'reasoning': u.get('reasoningTokens') or 0,
            'calls': (m.get('requests') or {}).get('count') or 0}


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
                       'usage_cum': r['usage_cum'], 'cold_calls': r['cold_calls'], 'call_starts': r['call_starts'],
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
        prev_u = dict.fromkeys(USAGE_KEYS, 0)
        for i, r in enumerate(rs):
            if i and r['kind'] == 'build':
                r['kind'], r['item'] = 'other', first['item']
            # A fresh launch (a -p catch-up merge, say) is whole; it is partial only when an earlier launch of its item lost its events.
            r['partial'] = i == 0 and r['kind'] not in FIRST_KINDS and any(
                item == r['item'] and at <= r['start'] for item, at in lost)
            r['credits'] = r['premium'] = r['usage'] = None
            cum = r['usage_cum']
            if cum:
                if cum['calls'] < prev_u['calls']:
                    prev_u = dict.fromkeys(USAGE_KEYS, 0)
                r['usage'] = {k: cum[k] - prev_u[k] for k in USAGE_KEYS}
                prev_u = cum
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


def load_prices(run=None, path=None):
    """Credits per 1M tokens by model: --prices, else <run>/prices.json, else the prices.json beside this script."""
    for p in (path, run and os.path.join(run, 'prices.json'), os.path.join(HERE, 'prices.json')):
        if p and os.path.isfile(p):
            with open(p, encoding='utf-8') as f:
                data = json.load(f)
            return {k: v for k, v in data.items() if isinstance(v, dict)}
    return {}


def price_tokens(tokens, price):
    return {c: (tokens.get(c) or 0) * (price or {}).get(PRICE_KEYS[c], 0) / 1e6 for c in CLASSES}


def add_costs(rounds, prices):
    for r in rounds:
        price = prices.get(r['model'])
        r['priced'] = price_tokens(r['usage'], price) if r.get('usage') and price else None


def usable(r):
    return r['credits'] is not None and not r['partial'] and r['kind'] != 'other'


def price_ratio(rs, source, target, prices):
    mix = dict.fromkeys(CLASSES, 0)
    for r in rs:
        for c in CLASSES:
            mix[c] += (r.get('usage') or {}).get(c) or 0
    have = sum(price_tokens(mix, prices.get(source)).values())
    if not have or target not in prices:
        return None
    return sum(price_tokens(mix, prices[target]).values()) / have


def caps(rounds, factor=FACTOR, window=WINDOW, min_rounds=MIN_ROUNDS, floor=FLOOR, prices=None):
    prices = prices or {}
    groups = collections.defaultdict(list)
    for r in rounds:
        if usable(r):
            groups[(r['kind'], r['model'] or '?')].append(r)
    out = []
    for (kind, model), rs in sorted(groups.items()):
        last = [r['credits'] for r in sorted(rs, key=lambda x: x['start'])[-window:]]
        med = statistics.median(last)
        enough = len(last) >= min_rounds
        row = {'kind': kind, 'model': model, 'n': len(last), 'median': round(med, 1),
               'cap': max(CLI_MIN_CAP, round(factor * med) if enough else floor),
               'from': f'{factor} x median' if enough else f'floor (n < {min_rounds})'}
        if not enough:
            donors = sorted(((len(g), m) for (k, m), g in groups.items()
                             if k == kind and m != model and len(g) >= min_rounds), reverse=True)
            for _, donor in donors:
                dr = sorted(groups[(kind, donor)], key=lambda x: x['start'])[-window:]
                ratio = price_ratio(dr, donor, model, prices)
                if ratio:
                    dmed = statistics.median(r['credits'] for r in dr) * ratio
                    row.update(median=round(dmed, 1), cap=max(CLI_MIN_CAP, round(factor * dmed)),
                               **{'from': f'derived from {donor} by price (x{ratio:.2f})'})
                    break
        out.append(row)
    return out


def cap_evidence(rounds, min_rounds=MIN_ROUNDS):
    """Rounds that would have hit each candidate cap, from each kind and model's own median and P90 (in-sample)."""
    groups = collections.defaultdict(list)
    for r in rounds:
        if usable(r):
            groups[(r['kind'], r['model'] or '?')].append(r['credits'])
    names = ('2x', '3x', '4x', 'p90x1.2')
    total, n_all = dict.fromkeys(names, 0), 0
    for cs in groups.values():
        if len(cs) < min_rounds:
            continue
        med = statistics.median(cs)
        p90 = statistics.quantiles(cs, n=10, method='inclusive')[-1]
        limits = {'2x': 2 * med, '3x': 3 * med, '4x': 4 * med, 'p90x1.2': 1.2 * p90}
        n_all += len(cs)
        for k in names:
            total[k] += sum(c > limits[k] for c in cs)
    return {'rounds': n_all, 'hit': total}


def usage_by_kind(rounds):
    by = collections.defaultdict(list)
    for r in rounds:
        by[(r['kind'], r['model'] or '?')].append(r)
    out = []
    for (kind, model), rs in sorted(by.items()):
        out.append({'kind': kind, 'model': model, 'rounds': len(rs), 'wall_min': round(sum(r['wall_min'] for r in rs), 1),
                    'calls': sum((r.get('usage') or {}).get('calls', r.get('call_starts', 0)) for r in rs),
                    'cold_calls': sum(r.get('cold_calls', 0) for r in rs),
                    'efforts': sorted({r['effort'] or '?' for r in rs}),
                    'tokens': {c: sum((r.get('usage') or {}).get(c, 0) for r in rs) for c in CLASSES + ('reasoning',)},
                    'credits_by_class': {c: round(sum((r.get('priced') or {}).get(c, 0) for r in rs), 1) for c in CLASSES}})
    return out


def chat_spend(path, prices):
    """Price an orchestrator chat's llm_request records; uncached input is priced as cache writes (an upper bound)."""
    files = [path] if os.path.isfile(path) else [os.path.join(path, f) for f in sorted(os.listdir(path))
                                                 if f.endswith('.jsonl')]
    by = collections.defaultdict(lambda: {**dict.fromkeys(CLASSES, 0), 'calls': 0})
    for fp in files:
        with open(fp, encoding='utf-8', errors='replace') as f:
            for line in f:
                if '"llm_request"' not in line:
                    continue
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                a = e.get('attrs') if isinstance(e, dict) else None
                if not isinstance(a, dict) or e.get('type') != 'llm_request':
                    continue
                cached = a.get('cachedTokens') or 0
                m = by[a.get('model') or '?']
                m['calls'] += 1
                m['cache_read'] += cached
                m['cache_write'] += max(0, (a.get('inputTokens') or 0) - cached)
                m['output'] += a.get('outputTokens') or 0
    models, total, unpriced = [], 0.0, []
    for model, t in sorted(by.items()):
        price = prices.get(model)
        credits = sum(price_tokens(t, price).values()) if price else None
        if credits is None:
            unpriced.append(model)
        else:
            total += credits
        models.append({'model': model, 'calls': t['calls'], 'tokens': {c: t[c] for c in CLASSES},
                       'credits': None if credits is None else round(credits, 1)})
    return {'credits': round(total, 1), 'upper_bound': True, 'models': models, 'unpriced': unpriced}


def budget_report(budget, rounds, chat, cap_rows):
    spent_rounds = sum(r['credits'] or 0 for r in rounds)
    spent = spent_rounds + (chat['credits'] if chat else 0)
    left = budget - spent
    fit = [{'kind': c['kind'], 'model': c['model'], 'median': c['median'],
            'rounds': int(left // c['median']) if left > 0 and c['median'] > 0 else 0} for c in cap_rows]
    return {'budget': budget, 'rounds_credits': round(spent_rounds, 1), 'chat_credits': chat['credits'] if chat else None,
            'spent': round(spent, 1), 'left': round(left, 1), 'fit': fit}


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
    lines.append('usage by kind and model: calls, cold calls (after a wait over 300 s), wall min, effort; '
                 'tokens in/out/cache read/cache write (k); credits in/out/cache read/cache write')
    for u in report['usage']:
        t, c = u['tokens'], u['credits_by_class']
        lines.append(f"  {u['kind']:<9} {u['model']:<22} {u['calls']:>5} {u['cold_calls']:>4} {u['wall_min']:>7,.0f} "
                     f"{','.join(u['efforts']):<8} " + '/'.join(f"{t[k] / 1000:,.0f}" for k in CLASSES) + '  '
                     + '/'.join(f"{c[k]:,.0f}" for k in CLASSES))
    ev = report['cap_evidence']
    if ev['rounds']:
        lines.append(f"rounds over a candidate cap ({ev['rounds']} rounds, kinds and models with 5 or more): "
                     + ', '.join(f"{k} {v}" for k, v in ev['hit'].items()))
    if report.get('chat'):
        ch = report['chat']
        lines.append(f"orchestrator chat: {ch['credits']:,.0f} credits, upper bound (uncached input priced as cache writes)"
                     + (f"; unpriced models: {', '.join(ch['unpriced'])}" if ch['unpriced'] else ''))
    if report.get('budget'):
        lines.append(spend_line(report['budget']))
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


def spend_line(b):
    chat = '' if b['chat_credits'] is None else f" + chat {b['chat_credits']:,.0f} (upper bound)"
    return (f"spend: {b['spent']:,.0f} of {b['budget']:,.0f} credits (rounds {b['rounds_credits']:,.0f}{chat}), "
            f"{b['left']:,.0f} left; more rounds at their medians: "
            + ', '.join(f"{f['kind']} {f['model']} {f['rounds']}" for f in b['fit']))


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
    ap.add_argument('--history', nargs='+', default=[], metavar='RUN', help="earlier run folders whose rounds join the caps' window")
    ap.add_argument('--prices', help='prices.json (default: <run>/prices.json, else the one beside this script)')
    ap.add_argument('--chat', help='VS Code debug-log folder (or main.jsonl) of the orchestrator chat to price')
    ap.add_argument('--budget', type=float, help="the run's credit ceiling: print spend against it")
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
    prices = load_prices(run, a.prices and os.path.expanduser(a.prices))
    history = []
    for h in a.history:
        h = os.path.abspath(os.path.expanduser(h))
        if not os.path.isdir(h):
            print(f'mine.py: no history folder at {h}', file=sys.stderr)
            return 2
        history += load_rounds(h)
    chat = None
    if a.chat:
        c = os.path.abspath(os.path.expanduser(a.chat))
        if not os.path.exists(c):
            print(f'mine.py: no chat log at {c}', file=sys.stderr)
            return 2
        chat = chat_spend(c, prices)
    rounds = load_rounds(run)
    if since:
        rounds = [r for r in rounds if r['start'] >= since]
    add_costs(rounds, prices)
    add_costs(history, prices)
    window = history + rounds
    cap_rows = caps(window, floor=a.floor, prices=prices)
    budget = budget_report(a.budget, rounds, chat, cap_rows) if a.budget is not None else None
    if a.caps:
        for c in cap_rows:
            print(f"{c['kind']:<9} {c['model']:<22} --max-ai-credits {c['cap']:<6} {c['from']}: median {c['median']:,.0f}, n={c['n']}")
        print(f"any other kind or model: --max-ai-credits {a.floor} floor (n < {MIN_ROUNDS})")
        if budget:
            print(spend_line(budget))
        elif chat:
            print(f"chat: {chat['credits']:,.0f} credits, upper bound")
        return 0
    report = {'run': run, 'since': a.since, 'rounds': rounds, 'items': items(rounds, merge_rows),
              'kinds': kinds(rounds), 'days': days(rounds), 'caps': cap_rows,
              'markers': measure(load_markers(run), rounds), 'usage': usage_by_kind(rounds),
              'cap_evidence': cap_evidence(window), 'prices': prices, 'chat': chat, 'budget': budget}
    if a.json:
        for r in rounds:
            r['start'] = iso(r['start'])
            r['wall_min'] = round(r['wall_min'], 1)
            r.pop('usage_cum', None)
            for k in ('credits', 'cum_credits'):
                if r[k] is not None:
                    r[k] = round(r[k], 1)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    print(text(report))
    return 0


if __name__ == '__main__':
    sys.exit(main())
