#!/usr/bin/env python3
"""Pick each worker round's model, effort and credit cap from the brief, past outcomes and the budget left.

Usage:
    python3 route.py pick --run RUN --item ID --kind build|fix|review|research|small|resume|merge --prompt FILE
                          [--author-model M] [--diff FILE] [--budget-left F] [--run-fraction F] [--seed N]
    python3 route.py escalate --run RUN --item ID
    python3 route.py report --run RUN
    python3 route.py eval-classifier --run RUN [--models a,b,c] [--max-credits N]

pick prints `MODEL=... EFFORT=... CONTEXT=... CAP=...` (and a `# reason` line) and appends one JSON line to RUN/routes.jsonl.
The policies (categories, floors, targets) and the model mapping live in ../references/routes.json.
Design and reading guide: ../references/routing.md.
"""
import argparse, collections, datetime, json, os, random, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
CONFIG = os.path.join(HERE, '..', 'references', 'routes.json')
STATE_ROOT = os.environ.get('OW_STATE_ROOT') or os.path.expanduser('~/.local/state/orchestrator-workers')
KINDS = ('build', 'fix', 'review', 'research', 'small', 'resume', 'merge')
MINE_KIND = {'small': 'build', 'catchup': 'merge', 'rereview': 'review'}
EFFORTS = ('low', 'medium', 'high', 'xhigh', 'max')
GRADES = ('risk', 'ambiguity', 'breadth', 'verification', 'novelty')
NOT_ROUND = ('markers.jsonl', 'routes.jsonl')


def load_config(path=None):
    with open(path or CONFIG, encoding='utf-8') as f:
        return json.load(f)


def family(model, cfg):
    for prefix, fam in cfg['families'].items():
        if model.startswith(prefix):
            return fam
    return model


def strongest(cfg, avoid_family=None):
    for fam, model in cfg['strongest'].items():
        if fam != avoid_family:
            return model
    return cfg['strongest'][cfg['default_family']]


def resolve(name, cfg, avoid_family=None, same=None):
    if name == 'strongest':
        return strongest(cfg, avoid_family)
    if name == 'strongest-other-family':
        return strongest(cfg, avoid_family or cfg['default_family'])
    if name == 'same':
        return same or cfg['static']['fix']['model']
    return name


def higher(a, b):
    return a if EFFORTS.index(a) >= EFFORTS.index(b) else b


def mine_kind(kind):
    return MINE_KIND.get(kind, kind)


def risk_hits(text, cfg):
    low = text.lower()
    return [{'area': area, 'quote': m.group(0)} for area, pat in cfg['risk_patterns']
            for m in [re.search(pat, low)] if m]


def sessions_touch(text, cfg):
    floor = next((f for f in cfg['floors'] if 'text' in f['when']), None)
    if not floor:
        return None
    for line in text.splitlines():
        if re.search(floor['when']['text'], line) and not re.search(floor['when']['text_unless'], line, re.I):
            return line.strip()[:160]
    return None


def candidates(kind, cfg):
    return [c for c, v in cfg['categories'].items() if mine_kind(kind) in v['kinds'] or kind in v['kinds']]


def keyword_classify(text, kind, cfg):
    cats = candidates(kind, cfg)
    head = next((ln for ln in text.splitlines() if ln.startswith('TASK:')), text[:300])
    if kind == 'research' or re.search(r'\b(research|proposal|document|write-?up)\b', head, re.I):
        cat = 'docs-research'
    elif re.search(r'\b(fix|flake|bug|repair|refactor|tidy)\b', head, re.I):
        cat = 'change-existing'
    elif kind == 'build':
        cat = 'new-feature'
    else:
        cat = cats[0]
    if cat not in cats:
        cat = cats[0]
    musts = len(re.findall(r'^\s*\d+\.\s', text, re.M))
    hits = risk_hits(text, cfg)

    def find(pat):
        m = re.search(pat, text, re.I)
        return m.group(0) if m else ''
    grades = {
        'risk': (4 if hits else 2, hits[0]['quote'] if hits else ''),
        'ambiguity': (3, find(r'options?|recommend\w*|decide')) if re.search(r'options?|recommend|decide', text, re.I) else (2, ''),
        'breadth': (2 if musts <= 4 else 3 if musts <= 7 else 4, f'{musts} numbered MUST items'),
        'verification': (3, find(r'browser|e2e|mutation|under load')) if re.search(r'browser|e2e|mutation|under load', text, re.I) else (2, ''),
        'novelty': (4, find(r'new (?:feature|route|tab|pane)|from scratch')) if re.search(r'new (?:feature|route|tab|pane)|from scratch', text, re.I) else (2, ''),
    }
    return {'source': 'fallback', 'category': cat, 'grades': {k: {'grade': g, 'quote': q} for k, (g, q) in grades.items()}}


def classifier_prompt(text, kind, cfg):
    cats = '\n'.join(f"- {c}: {cfg['categories'][c]['description']}" for c in candidates(kind, cfg))
    return (
        'You grade a coding-agent brief so a router can pick a model. Answer with one JSON object and nothing else.\n'
        f'Round kind: {kind}\nCategories (pick exactly one key):\n{cats}\n'
        'Grade each of risk, ambiguity, breadth, verification (how hard it is to check the result) and novelty from 1 (trivial) to 5 (extreme).\n'
        'Give each grade a short exact quote (under 15 words) copied from the brief that justifies it.\n'
        'Format: {"category":"<key>","grades":{"risk":{"grade":1,"quote":"..."},"ambiguity":{...},"breadth":{...},"verification":{...},"novelty":{...}}}\n'
        f'BRIEF:\n{text[:cfg["classifier"]["max_brief_chars"]]}')


def parse_classifier(raw, text, kind, cfg):
    start, end = raw.find('{'), raw.rfind('}')
    data = json.loads(raw[start:end + 1])
    cat = data['category']
    if cat not in candidates(kind, cfg):
        raise ValueError(f'category {cat!r} not allowed for kind {kind}')
    out = {}
    for k in GRADES:
        g = data['grades'][k]
        grade = int(g['grade'])
        if not 1 <= grade <= 5:
            raise ValueError(f'grade {k}={grade} out of range')
        quote = str(g.get('quote', ''))
        out[k] = {'grade': grade, 'quote': quote, 'quote_found': quote.lower() in text.lower() if quote else False}
    return {'source': 'classifier', 'category': cat, 'grades': out}


def copilot_classify(text, kind, cfg, model=None):
    c = cfg['classifier']
    cmd = ['timeout', str(c['timeout_s']), 'copilot', '-p', classifier_prompt(text, kind, cfg), '-s', '--model', model or c['model'],
           '--reasoning-effort', 'low', '--available-tools', '', '--disable-builtin-mcps', '--no-custom-instructions',
           '--no-ask-user', '--no-auto-update', '--stream', 'off', '--max-ai-credits', '30', '--output-format', 'json']
    done = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if done.returncode != 0:
        raise RuntimeError(f'copilot exited {done.returncode}')
    content, credits = '', None
    for line in done.stdout.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get('type') == 'assistant.message' and e['data'].get('content'):
            content = e['data']['content']
        elif e.get('type') == 'session.usage_checkpoint':
            credits = (e['data'].get('totalNanoAiu') or 0) / 1e9
    out = parse_classifier(content, text, kind, cfg)
    out['credits'] = credits
    return out


def classify(text, kind, cfg, call=None):
    """The classifier's reading of the brief, or the keyword rules' with the reason the classifier was not used."""
    try:
        return (call or copilot_classify)(text, kind, cfg)
    except Exception as e:
        out = keyword_classify(text, kind, cfg)
        out['fallback_reason'] = f'{type(e).__name__}: {e}'[:200]
        return out


def tier_of(grades, cfg):
    g = {k: v['grade'] for k, v in grades.items()}
    score = sum(g.values()) / len(g)
    cut = cfg['tier_cutoffs']
    if score >= cut['hard'] or g['risk'] >= cut['hard_risk']:
        return 'hard', score
    return ('easy' if score <= cut['easy'] else 'medium'), score


def static_choice(kind, risky, author, same, cfg):
    s = cfg['static'][kind]
    name, effort = s['model'], s['effort']
    if risky and 'risk_model' in s:
        name = s['risk_model']
    if risky:
        effort = s.get('risk_effort', 'high' if 'risk_model' in s else effort)
    avoid = family(author, cfg) if author else None
    return {'model': resolve(name, cfg, avoid, same), 'effort': effort}


def load_mine(path):
    done = subprocess.run([sys.executable, '-B', os.path.join(HERE, 'mine.py'), path, '--json'],
                          capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if done.returncode != 0:
        return [], []
    d = json.loads(done.stdout)
    return d['rounds'], d['items']


def round_ok(r, item):
    if r.get('capped') or r.get('error') or r.get('exit') != 0:
        return False
    if r['kind'] in ('review', 'rereview'):
        return r.get('verdict') != 'incomplete'
    return (item.get('blocking') in (None, 0)) and item.get('fix_rounds', 0) <= 1


def round_dirs(root):
    out = []
    for dirpath, dirnames, files in os.walk(root):
        depth = os.path.relpath(dirpath, root).count(os.sep) + (dirpath != root)
        if any(f.endswith('.jsonl') and f not in NOT_ROUND for f in files):
            out.append(dirpath)
        if depth >= 2:
            dirnames[:] = []
    return sorted(out)


def read_decisions(run):
    path = os.path.join(run, 'routes.jsonl')
    if not os.path.isfile(path):
        return []
    with open(path, encoding='utf-8') as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def build_history(rounds_items, decisions=()):
    """Past rounds as {kind, category, tier, model, ok, item}; category and tier come from a logged decision, else None."""
    hist = []
    logged = {(d['item'], mine_kind(d['kind'])): d for d in decisions if d.get('event') == 'pick'}
    for run, rounds, items in rounds_items:
        by_item = {i['item']: i for i in items}
        for r in rounds:
            if not r.get('ended') or not r.get('model') or r['kind'] == 'other':
                continue
            d = logged.get((r['item'], mine_kind(r['kind'])))
            hist.append({'kind': mine_kind(r['kind']), 'category': d and d['category'], 'tier': d and d['tier'],
                         'model': r['model'], 'effort': r.get('effort'),
                         'context': (d and d['choice'].get('context')) or 'default',
                         'item': r['item'], 'ok': round_ok(r, by_item.get(r['item'], {}))})
    return hist


def load_history(run, root=None):
    root = root or STATE_ROOT
    dirs = round_dirs(root)
    loaded = [(d, *load_mine(d)) for d in dirs]
    decisions = [d for x in dict.fromkeys([*dirs, run]) for d in read_decisions(x)]
    hist = build_history(loaded, decisions)
    caps = {}
    others = [d for d in dirs if os.path.abspath(d) != os.path.abspath(run)]
    cmd = [sys.executable, '-B', os.path.join(HERE, 'mine.py'), run, '--caps']
    if others:
        cmd += ['--history', *others]
    done = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    for line in done.stdout.splitlines():
        m = re.match(r'^(\w+)\s+(\S+)\s+--max-ai-credits (\d+)', line)
        if m:
            caps[(m.group(1), m.group(2))] = int(m.group(3))
    return {'rounds': hist, 'caps': caps}


def cap_for(kind, model, history, cfg):
    return history['caps'].get((mine_kind(kind), model), cfg['default_cap'])


def posterior(model, kind, category, tier, hist, cfg):
    """(alpha, beta, n, level): successes and failures of this model in the cell, widened to the category, then the kind."""
    mk = mine_kind(kind)
    mine = [r for r in hist if r['model'] == model and r['kind'] == mk]
    levels = (('cell', [r for r in mine if r['category'] == category and r['tier'] == tier]),
              ('category', [r for r in mine if r['category'] == category]),
              ('kind', mine))
    level, used = levels[-1]
    for name, rs in levels:
        if len(rs) >= cfg['min_rounds']:
            level, used = name, rs
            break
    prior = cfg['prior']['strongest'] if model in cfg['strongest'].values() else cfg['prior'][tier]
    wins = sum(r['ok'] for r in used)
    return prior[0] + wins, prior[1] + len(used) - wins, len(used), level


def overspend(budget_left, run_fraction):
    if budget_left is None or run_fraction is None:
        return 0.0
    return max(0.0, (1 - budget_left) - run_fraction)


def target_for(tier, budget_left, run_fraction, cfg):
    b = cfg['budget']
    return max(b['min_target'], cfg['targets'][tier] - b['gain'] * overspend(budget_left, run_fraction))


def arm_posterior(rounds, field, value, kind, category, tier, prior, cfg):
    """Beta for one arm: the cell's own outcomes plus the kind's other outcomes at a reduced weight (a shared prior)."""
    mk = mine_kind(kind)
    mine = [r for r in rounds if r['kind'] == mk and r.get(field) == value]
    cell = [r for r in mine if r['category'] == category and r['tier'] == tier]
    rest = [r for r in mine if not (r['category'] == category and r['tier'] == tier)]
    w = cfg['learning']['kind_share']
    rest_wins = sum(r['ok'] for r in rest)
    cell_wins = sum(r['ok'] for r in cell)
    a = prior[0] + cell_wins + w * rest_wins
    b = prior[1] + len(cell) - cell_wins + w * (len(rest) - rest_wins)
    return a, b, len(cell), len(rest)


def beta_sd(a, b):
    return (a * b / ((a + b) ** 2 * (a + b + 1))) ** 0.5


def quality_tie(cheap, target, cfg):
    """Why the stronger arm wins, or None: too few outcomes in the cell, or the cheaper arm not clearly above the target."""
    q = cfg['quality']
    if cheap['cell_n'] < q['min_cell_rounds']:
        return f"quality first: {cheap['arm']} has {cheap['cell_n']} outcomes in the cell < {q['min_cell_rounds']}"
    low = cheap['mean'] - q['tie_sd'] * beta_sd(cheap['alpha'], cheap['beta'])
    if low < target:
        return f"quality first: {cheap['arm']} mean {cheap['mean']:.2f} - {q['tie_sd']} sd = {low:.2f} < target {target:.2f}"
    return None


def choose(arms, target, rng, quality_on, cfg):
    """arms ordered cheapest first; Thompson-sample, take the cheapest clearing the target, then apply the quality rule."""
    for s in arms:
        s['sample'] = round(rng.betavariate(s['alpha'], s['beta']), 3)
    pick_i = next((i for i, s in enumerate(arms) if s['sample'] >= target), len(arms) - 1)
    why = (f"cheapest sampled success >= {target:.2f}: {arms[pick_i]['arm']} ({arms[pick_i]['sample']})"
           if arms[pick_i]['sample'] >= target else f'no arm cleared {target:.2f}; the strongest')
    if quality_on and pick_i < len(arms) - 1:
        tie = quality_tie(arms[pick_i], target, cfg)
        if tie:
            return arms[-1]['arm'], tie
    return arms[pick_i]['arm'], why


def context_signals(text, grades, cfg):
    c = cfg['context']
    hits = [name for name, pat in c['signals'] if re.search(pat, text, re.I)]
    files = set(re.findall(r'\b[\w./-]+\.(?:ts|tsx|js|py|md|json|css|go|rs|java|cs)\b', text))
    if len(files) >= c['many_files']:
        hits.append(f'{len(files)} file paths')
    if len(text) >= c['long_brief_chars']:
        hits.append(f'{len(text)} chars of brief')
    if grades['breadth']['grade'] >= c['breadth_grade']:
        hits.append(f"breadth {grades['breadth']['grade']}")
    return hits


def pick(item, kind, text, history, cfg, author=None, diff='', budget_left=None, run_fraction=None, rng=None,
         seed=None, call=None, resumed_model=None):
    rng = rng or random.Random(seed)
    cls = classify(text, kind, cfg, call)
    category = cls['category']
    tier, score = tier_of(cls['grades'], cfg)
    hits = risk_hits(text + '\n' + diff, cfg)
    if cls['grades']['risk']['grade'] >= cfg['tier_cutoffs']['hard_risk']:
        hits.append({'area': 'classifier risk grade', 'quote': cls['grades']['risk']['quote']})
    sess = sessions_touch(text, cfg)
    avoid = family(author, cfg) if kind == 'review' and author else None
    same = resumed_model or author or next((r['model'] for r in reversed(history['rounds'])
                                           if r['item'] == item and r['kind'] != 'review'), None)
    static = static_choice(kind, bool(hits), author if kind == 'review' else None, same, cfg)

    floor = None
    for f in cfg['floors']:
        w = f['when']
        if (w.get('category') == category and kind == 'build') or (w.get('text') and sess) or (w.get('risk') and hits):
            floor = f
            break
    pool = [m for m in cfg['categories']['review' if kind == 'review' else category]['pool']
            if not avoid or family(m, cfg) != avoid]
    if kind == 'review' and not pool:
        pool = [strongest(cfg, avoid)]
    scores, target = {}, target_for(tier, budget_left, run_fraction, cfg)
    quality_on = overspend(budget_left, run_fraction) <= 0
    rule_effort = cfg['effort']['calm'] if all(cls['grades'][k]['grade'] <= cfg['effort']['calm_max_grade']
                                               for k in ('ambiguity', 'verification')) else cfg['effort']['else']
    lc = cfg['learning']
    ladder = lc['effort_arms']
    i = ladder.index(rule_effort) if rule_effort in ladder else len(ladder) - 1
    effort_scores = []
    for e in ladder[i:i + 2]:
        a, b, cn, rn = arm_posterior(history['rounds'], 'effort', e, kind, category, tier,
                                     lc['rule_prior'] if e == rule_effort else lc['other_prior'], cfg)
        effort_scores.append({'arm': e, 'alpha': a, 'beta': b, 'cell_n': cn, 'kind_n': rn, 'mean': round(a / (a + b), 3)})
    effort, effort_why = choose(effort_scores, target, rng, quality_on, cfg)
    effort = higher(effort, cfg['kind_min_effort'].get(kind, 'low'))
    ctx_hits = context_signals(text, cls['grades'], cfg)
    context_scores, cc = [], cfg['context']
    if len(ctx_hits) >= cc['min_signals']:
        for x in ('default', 'long_context'):
            a, b, cn, rn = arm_posterior(history['rounds'], 'context', x, kind, category, tier, cc['prior'][x], cfg)
            context_scores.append({'arm': x, 'alpha': a, 'beta': b, 'cell_n': cn, 'kind_n': rn, 'mean': round(a / (a + b), 3)})
        context, context_why = choose(context_scores, target, rng, False, cfg)
        context_why += f" (signals: {', '.join(ctx_hits)})"
    else:
        context, context_why = 'default', f"{len(ctx_hits)} long-context signal(s) < {cc['min_signals']}"
    if floor:
        model = resolve(floor['model'], cfg, avoid)
        effort = higher(effort, floor['effort'])
        if kind == 'review' and floor.get('review_effort'):
            effort = floor['review_effort']
        reason = f"floor {floor['name']}"
    elif kind == 'resume' and same:
        model, reason = same, 'resume keeps the model of the round it continues'
    else:
        arms, mk = [], mine_kind(kind)
        for m in pool:
            a, b, n, level = posterior(m, kind, category, tier, history['rounds'], cfg)
            cell_n = sum(1 for r in history['rounds'] if r['model'] == m and r['kind'] == mk
                         and r['category'] == category and r['tier'] == tier)
            arms.append({'arm': m, 'alpha': a, 'beta': b, 'n': n, 'level': level, 'cell_n': cell_n,
                         'mean': round(a / (a + b), 3)})
        model, reason = choose(arms, target, rng, quality_on, cfg)
        scores = {s.pop('arm'): s for s in arms}
        reason += f" [{scores[model]['level']} n={scores[model]['n']}]"
    if kind == 'review' and avoid and family(model, cfg) == avoid:
        model = strongest(cfg, avoid)
    cap = cap_for(kind, model, history, cfg)
    if not quality_on:
        reason += ' | budget: spend ahead of time, quality rule off'
    reason += f" | effort {effort}: {effort_why} | context {context}: {context_why}"
    reason += f" | {category}/{tier} (score {score:.1f}, {cls['source']})"
    if hits:
        reason += f" | risk: {hits[0]['area']}"
    return {'event': 'pick', 'at': datetime.datetime.now().astimezone().isoformat(timespec='seconds'), 'item': item, 'kind': kind,
            'inputs': {'prompt_chars': len(text), 'author_model': author, 'budget_left': budget_left,
                       'run_fraction': run_fraction, 'seed': seed, 'diff_chars': len(diff)},
            'classifier': cls, 'category': category, 'tier': tier, 'score': round(score, 2), 'cell': f'{category}/{tier}',
            'risk_hits': hits, 'scores': scores, 'effort_scores': effort_scores, 'context_scores': context_scores,
            'context_signals': ctx_hits, 'quality_rule': quality_on, 'rule_effort': rule_effort,
            'target': round(target, 3), 'floor': floor and floor['name'],
            'choice': {'model': model, 'effort': effort, 'context': context, 'cap': cap}, 'static': static,
            'differs': (model, effort) != (static['model'], static['effort']), 'reason': reason}


def escalate(item, history, cfg, run):
    last = next((d for d in reversed(read_decisions(run)) if d['item'] == item and d.get('event') in ('pick', 'escalate')), None)
    if not last:
        raise LookupError(f'no logged decision for {item}')
    kind, cur = last['kind'], last['choice']
    cat = 'review' if kind == 'review' else last['category']
    avoid = family(last['inputs']['author_model'], cfg) if kind == 'review' and last['inputs'].get('author_model') else None
    pool = [m for m in cfg['categories'][cat]['pool'] if not avoid or family(m, cfg) != avoid]
    higher_models = [m for m in pool[pool.index(cur['model']) + 1:]] if cur['model'] in pool else []
    top = not higher_models
    model = cur['model'] if top else higher_models[0]
    effort = cur['effort']
    reason = f"{cur['model']} at {effort} capped or failed its gate; " + ('already the top of its pool' if top else f'next up the pool: {model}')
    return {'event': 'escalate', 'at': datetime.datetime.now().astimezone().isoformat(timespec='seconds'), 'item': item,
            'kind': kind, 'category': last['category'], 'tier': last['tier'], 'inputs': last['inputs'],
            'choice': {'model': model, 'effort': effort, 'context': cur.get('context', 'default'),
                       'cap': cap_for(kind, model, history, cfg)}, 'top_of_pool': top,
            'reason': reason}


def log(run, record):
    with open(os.path.join(run, 'routes.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')


def emit(rec):
    c = rec['choice']
    print(f"MODEL={c['model']} EFFORT={c['effort']} CONTEXT={c.get('context', 'default')} CAP={c['cap']}")
    print(f"# {rec['reason']}")


def report(run, rounds=None, items=None):
    decisions = read_decisions(run)
    if rounds is None:
        rounds, items = load_mine(run)
    by_item = {i['item']: i for i in items}
    lines, by_arm = [], collections.defaultdict(lambda: [0, 0])
    for d in decisions:
        c = d['choice']
        match = [r for r in rounds if r['item'] == d['item'] and mine_kind(r['kind']) == mine_kind(d['kind'])]
        r = next((x for x in match if x['model'] == c['model']), match[-1] if match else None)
        if r is None:
            outcome = 'no round yet'
        else:
            good = round_ok(r, by_item.get(r['item'], {}))
            ok = 'ok' if good else 'FAILED'
            outcome = (f"ran {r['model']}/{r['effort']}, {r['credits'] or 0:,.0f} credits"
                       f"{', CAPPED' if r['capped'] else ''}, {ok}")
            for arm in (f"effort {r['effort']}", f"context {c.get('context', 'default')}"):
                by_arm[arm][0 if good else 1] += 1
        st = d.get('static')
        diff = ''
        if st:
            diff = 'same as table' if not d.get('differs') else f"table: {st['model']}/{st['effort']}"
        lines.append(f"{d['item']:<18} {d['event']:<8} {d['kind']:<8} {c['model']}/{c['effort']}/"
                     f"{c.get('context', 'default')}/cap {c['cap']}  [{diff}]  {outcome}")
    for arm, (ok, bad) in sorted(by_arm.items()):
        lines.append(f"{arm:<26} {ok} ok, {bad} failed")
    return lines


def eval_rounds(run, root=None):
    """(run dir, round, ok) for this run's rounds and the two previous run folders', each with a prompt file."""
    root = root or STATE_ROOT
    run = os.path.abspath(run)
    sibs = sorted(d for d in (os.path.join(root, x) for x in os.listdir(root)) if os.path.isdir(d))
    before = [d for d in sibs if os.path.basename(d) < os.path.basename(run)][-2:]
    out = []
    for d in [run, *reversed(before)]:
        rounds, items = load_mine(d)
        by_item = {i['item']: i for i in items}
        for r in rounds:
            p = os.path.join(d, f"{r.get('name')}.prompt.md")
            if r.get('ended') and r['kind'] in KINDS + ('catchup', 'rereview') and os.path.isfile(p):
                out.append((d, r, p, round_ok(r, by_item.get(r['item'], {}))))
    return out


def eval_classifier(samples, models, cfg, max_credits, call=None):
    """Grade each brief with each model, brief by brief, until the next brief would pass max_credits."""
    call = call or (lambda t, k, c, m: copilot_classify(t, k, c, m))
    res = {m: [] for m in models}
    spent, per_call = 0.0, {m: None for m in models}
    for _, r, path, ok in samples:
        need = sum(per_call[m] or 0 for m in models)
        if spent + need > max_credits:
            break
        with open(path, encoding='utf-8') as f:
            text = f.read()
        kind = r['kind'] if r['kind'] in KINDS else mine_kind(r['kind'])
        for m in models:
            try:
                out = call(text, kind, cfg, m)
                tier = tier_of(out['grades'], cfg)[0]
            except Exception:
                out, tier = {'credits': None}, None
            cr = out.get('credits') or 0.0
            spent += cr
            per_call[m] = max(per_call[m] or 0, cr)
            res[m].append({'round': r.get('name'), 'tier': tier, 'ok': ok, 'credits': cr})
    rows = []
    base = res[models[0]]
    for m in models:
        rs = [x for x in res[m] if x['tier']]
        hit = [x for x in rs if (x['tier'] == 'hard') == (not x['ok'])]
        fails, oks = [x for x in rs if not x['ok']], [x for x in rs if x['ok']]
        tpr = sum(x['tier'] == 'hard' for x in fails) / len(fails) if fails else None
        tnr = sum(x['tier'] != 'hard' for x in oks) / len(oks) if oks else None
        agree = sum(a['tier'] == b['tier'] for a, b in zip(res[m], base) if a['tier']) / len(rs) if rs else 0
        rows.append({'model': m, 'n': len(rs), 'errors': len(res[m]) - len(rs),
                     'credits_per_call': round(sum(x['credits'] for x in res[m]) / max(1, len(res[m])), 3),
                     'agreement': round(agree, 2), 'accuracy': round(len(hit) / len(rs), 2) if rs else None,
                     'balanced': round((tpr + tnr) / 2, 2) if tpr is not None and tnr is not None else None,
                     'fails': len(fails)})
    return rows, res, round(spent, 2)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('pick')
    p.add_argument('--run', required=True)
    p.add_argument('--item', required=True)
    p.add_argument('--kind', required=True, choices=KINDS)
    p.add_argument('--prompt', required=True, help='the brief file')
    p.add_argument('--author-model', help='a review: the author round\'s model; a resume: the model it continues')
    p.add_argument('--diff', help='a diff file whose text is also checked for risk areas')
    p.add_argument('--budget-left', type=float, help='fraction of the run\'s credit budget still unspent (0 to 1)')
    p.add_argument('--run-fraction', type=float, help='fraction of the run\'s planned time already elapsed (0 to 1)')
    p.add_argument('--seed', type=int, help='fix the random draws (logged either way)')
    p.add_argument('--grades-json', help='a classifier answer to use instead of calling copilot (a file or JSON)')
    p.add_argument('--no-classifier', action='store_true', help='use the keyword rules without calling copilot')
    p.add_argument('--history-root', default=STATE_ROOT)
    p.add_argument('--config')
    e = sub.add_parser('escalate')
    e.add_argument('--run', required=True)
    e.add_argument('--item', required=True)
    e.add_argument('--history-root', default=STATE_ROOT)
    e.add_argument('--config')
    r = sub.add_parser('report')
    r.add_argument('--run', required=True)
    v = sub.add_parser('eval-classifier')
    v.add_argument('--run', required=True)
    v.add_argument('--models', help='comma-separated; default: the classifier pool in routes.json')
    v.add_argument('--max-credits', type=float, default=60)
    v.add_argument('--history-root', default=STATE_ROOT)
    v.add_argument('--config')
    a = ap.parse_args(argv)
    run = os.path.abspath(os.path.expanduser(a.run))
    if not os.path.isdir(run):
        print(f'route.py: no run folder at {run}', file=sys.stderr)
        return 2
    if a.cmd == 'report':
        print('\n'.join(report(run)))
        return 0
    cfg = load_config(a.config)
    if a.cmd == 'eval-classifier':
        models = a.models.split(',') if a.models else cfg['classifier']['pool']
        rows, _, spent = eval_classifier(eval_rounds(run, a.history_root), models, cfg, a.max_credits)
        print(f"{'model':<20} {'briefs':>6} {'errors':>6} {'fails':>5} {'cr/call':>7} {'agree':>5} {'acc':>5} {'bal':>5}")
        for x in rows:
            print(f"{x['model']:<20} {x['n']:>6} {x['errors']:>6} {x['fails']:>5} {x['credits_per_call']:>7} "
                  f"{x['agreement']:>5} {x['accuracy']!s:>5} {x['balanced']!s:>5}")
        print(f'# {spent} credits; agree = same tier as {models[0]}; acc and bal: hard tier against failed or capped rounds')
        return 0
    history = load_history(run, a.history_root)
    if a.cmd == 'escalate':
        try:
            rec = escalate(a.item, history, cfg, run)
        except LookupError as ex:
            print(f'route.py: {ex}', file=sys.stderr)
            return 2
        log(run, rec)
        emit(rec)
        return 0
    with open(os.path.expanduser(a.prompt), encoding='utf-8') as f:
        text = f.read()
    diff = ''
    if a.diff:
        with open(os.path.expanduser(a.diff), encoding='utf-8', errors='replace') as f:
            diff = f.read()
    call = None
    if a.no_classifier:
        def call(*_):
            raise RuntimeError('classifier disabled')
    elif a.grades_json:
        raw = a.grades_json
        if os.path.isfile(os.path.expanduser(raw)):
            with open(os.path.expanduser(raw), encoding='utf-8') as f:
                raw = f.read()

        def call(t, k, c):
            out = parse_classifier(raw, t, k, c)
            out['source'] = 'stub'
            return out
    seed = a.seed if a.seed is not None else random.SystemRandom().randrange(2 ** 31)
    rec = pick(a.item, a.kind, text, history, cfg, a.author_model, diff, a.budget_left, a.run_fraction,
               random.Random(seed), seed, call, a.author_model if a.kind == 'resume' else None)
    log(run, rec)
    emit(rec)
    return 0


if __name__ == '__main__':
    sys.exit(main())
