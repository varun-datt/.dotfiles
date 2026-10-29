#!/usr/bin/env python3
"""Pick each worker round's model, effort and credit cap from the brief, past outcomes and the budget left.

Usage:
    python3 route.py pick --run RUN --item ID --kind build|fix|review|research|small|resume|merge --prompt FILE
                          [--author-model M] [--diff FILE] [--budget-left F] [--run-fraction F] [--seed N]
    python3 route.py escalate --run RUN --item ID
    python3 route.py report --run RUN

pick prints `MODEL=... EFFORT=... CAP=...` (and a `# reason` line) and appends one JSON line to RUN/routes.jsonl.
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


def copilot_classify(text, kind, cfg):
    c = cfg['classifier']
    cmd = ['timeout', str(c['timeout_s']), 'copilot', '-p', classifier_prompt(text, kind, cfg), '-s', '--model', c['model'],
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
                         'model': r['model'], 'item': r['item'], 'ok': round_ok(r, by_item.get(r['item'], {}))})
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


def target_for(tier, budget_left, run_fraction, cfg):
    base = cfg['targets'][tier]
    if budget_left is None or run_fraction is None:
        return base
    ahead = (1 - budget_left) - run_fraction
    b = cfg['budget']
    return max(b['min_target'], base - b['gain'] * max(0.0, ahead))


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
    effort = cfg['effort']['calm'] if all(cls['grades'][k]['grade'] <= cfg['effort']['calm_max_grade']
                                          for k in ('ambiguity', 'verification')) else cfg['effort']['else']
    effort = higher(effort, cfg['kind_min_effort'].get(kind, 'low'))
    if floor:
        model = resolve(floor['model'], cfg, avoid)
        effort = higher(effort, floor['effort'])
        if kind == 'review' and floor.get('review_effort'):
            effort = floor['review_effort']
        reason = f"floor {floor['name']}"
    elif kind == 'resume' and same:
        model, reason = same, 'resume keeps the model of the round it continues'
    else:
        for m in pool:
            a, b, n, level = posterior(m, kind, category, tier, history['rounds'], cfg)
            scores[m] = {'alpha': a, 'beta': b, 'n': n, 'level': level, 'mean': round(a / (a + b), 3),
                         'sample': round(rng.betavariate(a, b), 3)}
        model = next((m for m in pool if scores[m]['sample'] >= target), pool[-1])
        reason = (f"cheapest sampled success >= {target:.2f}: {model} ({scores[model]['sample']}, "
                  f"{scores[model]['level']} n={scores[model]['n']})" if scores[model]['sample'] >= target
                  else f'no model cleared {target:.2f}; strongest of the pool')
    if kind == 'review' and avoid and family(model, cfg) == avoid:
        model = strongest(cfg, avoid)
    cap = cap_for(kind, model, history, cfg)
    reason += f" | {category}/{tier} (score {score:.1f}, {cls['source']})"
    if hits:
        reason += f" | risk: {hits[0]['area']}"
    return {'event': 'pick', 'at': datetime.datetime.now().astimezone().isoformat(timespec='seconds'), 'item': item, 'kind': kind,
            'inputs': {'prompt_chars': len(text), 'author_model': author, 'budget_left': budget_left,
                       'run_fraction': run_fraction, 'seed': seed, 'diff_chars': len(diff)},
            'classifier': cls, 'category': category, 'tier': tier, 'score': round(score, 2), 'cell': f'{category}/{tier}',
            'risk_hits': hits, 'scores': scores, 'target': round(target, 3), 'floor': floor and floor['name'],
            'choice': {'model': model, 'effort': effort, 'cap': cap}, 'static': static,
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
            'choice': {'model': model, 'effort': effort, 'cap': cap_for(kind, model, history, cfg)}, 'top_of_pool': top,
            'reason': reason}


def log(run, record):
    with open(os.path.join(run, 'routes.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')


def emit(rec):
    c = rec['choice']
    print(f"MODEL={c['model']} EFFORT={c['effort']} CAP={c['cap']}")
    print(f"# {rec['reason']}")


def report(run, rounds=None, items=None):
    decisions = read_decisions(run)
    if rounds is None:
        rounds, items = load_mine(run)
    by_item = {i['item']: i for i in items}
    lines = []
    for d in decisions:
        c = d['choice']
        match = [r for r in rounds if r['item'] == d['item'] and mine_kind(r['kind']) == mine_kind(d['kind'])]
        r = next((x for x in match if x['model'] == c['model']), match[-1] if match else None)
        if r is None:
            outcome = 'no round yet'
        else:
            ok = 'ok' if round_ok(r, by_item.get(r['item'], {})) else 'FAILED'
            outcome = (f"ran {r['model']}/{r['effort']}, {r['credits'] or 0:,.0f} credits"
                       f"{', CAPPED' if r['capped'] else ''}, {ok}")
        st = d.get('static')
        diff = ''
        if st:
            diff = 'same as table' if not d.get('differs') else f"table: {st['model']}/{st['effort']}"
        lines.append(f"{d['item']:<18} {d['event']:<8} {d['kind']:<8} {c['model']}/{c['effort']}/cap {c['cap']}  [{diff}]  {outcome}")
    return lines


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
    a = ap.parse_args(argv)
    run = os.path.abspath(os.path.expanduser(a.run))
    if not os.path.isdir(run):
        print(f'route.py: no run folder at {run}', file=sys.stderr)
        return 2
    if a.cmd == 'report':
        print('\n'.join(report(run)))
        return 0
    cfg = load_config(a.config)
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
