#!/usr/bin/env python3
"""Pick each worker round's model, effort and credit cap from the brief, past outcomes and the budget left.

Usage:
    python3 route.py run ROUND --kind K --brief FILE --worktree DIR [--run RUN] [--author-model M]
                          [--override "model=..,effort=..,context=..,cap=N|none,owner_approved=..,reason=.."] [--add-dir DIR ...]
                          [--timeout S] [--fresh] [pick's options]
    python3 route.py pick --run RUN --item ID --kind build|fix|review|research|small|resume|merge --prompt FILE
                          [--author-model M] [--diff FILE] [--budget-left F] [--run-fraction F] [--seed N] [--fresh]
    python3 route.py escalate --run RUN --item ID
    python3 route.py report --run RUN
    python3 route.py eval-classifier --run RUN [--models a,b,c] [--max-credits N]

run is the one way to launch a worker or review round: it refuses to start under caffeinate (exit 2; this Mac kills
caffeinate, and the round with it), checks the brief (brief.py check, exit 5), picks or
takes the override (whose reason is required), logs the decision with the CLI version, waits for load
(sweep.py load --wait 15, exit 12), writes ROUND.start, ROUND.base and the time budget, launches `copilot -p`
with exactly the logged model, effort, context and cap under a timeout, sweeps leftovers on exit, and exits
non-zero when copilot failed (its code; 124 timed out), the round hit its cap (3) or errored (4).
pick prints `MODEL=... EFFORT=... CONTEXT=... CAP=...` (and a `# reason` line) and appends one JSON line to RUN/routes.jsonl.
pick and run reuse a round's logged decision that has not launched yet; --fresh draws again.
A review without --author-model takes the model of the item's latest author round log. A review whose final model
(picked, overridden or reused) is in the author's family is refused (exit 2, logged as a refuse event) unless the
override says same_family=yes: the fallback after a 422 refusal, which the audit then shows as overridden. A reused
decision falls back on the author saved with it; a review whose author is unknown from all three is refused the same way.
A review, re-review or critique runs at high effort unless the override names another; run logs the size of the
worktree's REVIEW-DIFF.patch as inputs.diff_chars (null, with diff_source null, when there is none, as for a critique).
A second fix round for an item (named <item>-fixN with N >= 2, or after a fix launch for it in routes.jsonl) is
refused (exit 2, a refuse event) unless the override carries owner_approved=<where the owner said so>, logged with
the launch. resume.py continues a round and is not checked.
The policies (categories, floors, targets) and the model mapping live in ../references/routes.json.
Design and reading guide: ../references/routing.md.
"""
import argparse, collections, contextlib, datetime, fcntl, json, os, random, re, signal, subprocess, sys, tempfile

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


TASK_START = re.compile(r"^(?:TASK:|THIS IS A FIX ROUND)", re.M)
REVIEW_EFFORT = 'high'
FIX_N = re.compile(r'-fix(\d+)$')


def task_part(text):
    """The item's own task; shared preambles and the rubric name sessions.ts and risk words in every prompt."""
    text = re.sub(r"^==== RUBRIC ====$.*?^==== END OF RUBRIC ====$", "", text, flags=re.S | re.M)
    m = re.search(r"^==== THE AUTHOR'S TASK ====$(.*?)^==== END OF TASK ====$", text, re.S | re.M)
    if m:
        text = m.group(1)
    m = TASK_START.search(text)
    return text[m.start():] if m else text


def changed_files(diff):
    return re.findall(r'^\+\+\+ b/(\S+)', diff, re.M) + re.findall(r'^--- a/(\S+)', diff, re.M)


TOOL_PATH = re.compile(r'dotfiles/dot_agents/skills/[^/]+/scripts/')


def patch_paths(diff):
    """Every path a git patch names, old and new, including renames and binary or mode-only changes."""
    paths = []
    for line in diff.splitlines():
        m = re.match(r'(?:\+\+\+ b/|--- a/|rename (?:from|to) |copy (?:from|to) )(.+)', line)
        if m:
            paths.append(m.group(1).split('\t')[0].strip('"'))
            continue
        if line.startswith('diff --git '):
            rest = line[len('diff --git '):]
            q = re.fullmatch(r'"a/(.+)" "b/(.+)"', rest)
            if q:
                paths += [q.group(1), q.group(2)]
                continue
            h = (len(rest) - 1) // 2
            if rest[:2] == 'a/' and rest[h:h + 3] == ' b/' and rest[2:h] == rest[h + 3:]:
                paths.append(rest[2:h])
            else:
                paths += re.findall(r'(?:^| )[ab]/(\S+)', rest)
    return sorted(set(p for p in paths if p))


def review_scope(diff):
    """(scope, tool files, note): tool when every changed file is a skill script, else product; a mixed diff's
    tool files are graded as tool whatever the scope."""
    if diff is None:
        return 'product', [], 'no REVIEW-DIFF.patch in the worktree'
    paths = patch_paths(diff)
    if not paths:
        return 'product', [], 'REVIEW-DIFF.patch names no file'
    tools = [p for p in paths if TOOL_PATH.match(p)]
    if len(tools) == len(paths):
        return 'tool', tools, 'every changed file is under dotfiles/dot_agents/skills/*/scripts/'
    return 'product', tools, 'some changed files are outside dotfiles/dot_agents/skills/*/scripts/'


def sessions_touch(text, cfg, changed=()):
    floor = next((f for f in cfg['floors'] if 'text' in f['when']), None)
    if not floor:
        return None
    w = floor['when']
    for line in text.splitlines():
        if w.get('risk_line') and re.match(w['risk_line'], line):
            return line.strip()[:160]
        if w.get('text_skip') and re.match(w['text_skip'], line):
            continue
        if re.search(w['text'], line) and not re.search(w['text_unless'], line, re.I):
            return line.strip()[:160]
    return next((f'changed: {p}' for p in changed if re.search(w['text'], p)), None)


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
            d = logged.get((r['name'], mine_kind(r['kind']))) or logged.get((r['item'], mine_kind(r['kind'])))
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
    measured = history['caps'].get((mine_kind(kind), model))
    if kind in cfg.get('uncapped_kinds', ()):
        return measured
    return measured or cfg['default_cap']


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
         seed=None, call=None, resumed_model=None, changed=()):
    rng = rng or random.Random(seed)
    cls = classify(text, kind, cfg, call)
    category = cls['category']
    tier, score = tier_of(cls['grades'], cfg)
    hits = risk_hits(text + '\n' + diff, cfg)
    if cls['grades']['risk']['grade'] >= cfg['tier_cutoffs']['hard_risk']:
        hits.append({'area': 'classifier risk grade', 'quote': cls['grades']['risk']['quote']})
    sess = sessions_touch(text, cfg, changed_files(diff) + list(changed))
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
    if kind == 'review':
        effort, effort_why = REVIEW_EFFORT, 'reviews, re-reviews and critiques at high (owner, 2026-11-02, batch 2)'
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
    last = next((d for d in reversed(read_decisions(run)) if d.get('item') == item and d.get('event') in ('pick', 'escalate')), None)
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


@contextlib.contextmanager
def locked(path):
    with open(path + '.lock', 'a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def write_json(path, data):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix='.' + os.path.basename(path) + '.')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(tmp)
        raise


def log(run, record):
    path = os.path.join(run, 'routes.jsonl')
    with locked(path), open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')


def pending(run, rnd):
    """The round's latest decision that no launch has used yet, else None."""
    last = None
    for d in read_decisions(run):
        if d.get('event') in ('pick', 'escalate') and d.get('item') == rnd:
            last = d
        elif d.get('event') == 'launch' and d.get('round') == rnd:
            last = None
    return last


OVERRIDE_KEYS = ('model', 'effort', 'context', 'cap')


def parse_override(spec):
    """{field: value, ..., 'reason': text} from "model=..,effort=..,context=..,cap=N|none,reason=..": reason last, required."""
    head, sep, reason = spec.partition('reason=')
    reason = reason.strip()
    if not sep or not reason:
        raise ValueError('an override needs reason=<why>, last')
    out = {}
    for part in filter(None, (p.strip() for p in head.split(','))):
        k, eq, v = (x.strip() for x in part.partition('='))
        if k == 'same_family':
            if v != 'yes':
                raise ValueError('same_family takes only yes (the fallback after a 422 refusal)')
            out[k] = True
            continue
        if k == 'owner_approved':
            if not v:
                raise ValueError('owner_approved needs where the owner said so, for example "PLAN 2026-11-02 batch 2 8a"')
            out[k] = v
            continue
        if not eq or k not in OVERRIDE_KEYS or not v:
            raise ValueError(f'bad override field {part!r}; use {", ".join(OVERRIDE_KEYS)}')
        if k == 'model' and v == 'auto':
            raise ValueError('never the automatic model choice')
        if k == 'effort' and v not in EFFORTS:
            raise ValueError(f'effort must be one of {", ".join(EFFORTS)}')
        if k == 'context' and v not in ('default', 'long_context'):
            raise ValueError('context must be default or long_context')
        if k == 'cap':
            if v == 'none':
                v = None
            elif not v.isdigit() or int(v) <= 0:
                raise ValueError('cap must be a positive whole number or none')
            else:
                v = int(v)
        out[k] = v
    if not any(k in out for k in OVERRIDE_KEYS + ('owner_approved',)):
        raise ValueError(f'an override sets at least one of {", ".join(OVERRIDE_KEYS + ("owner_approved",))} before reason=')
    out['reason'] = reason
    return out


def apply_override(rec, ov, rnd):
    base = rec.get('routed_choice') or rec['choice']
    choice = {**base, **{k: ov[k] for k in OVERRIDE_KEYS if k in ov}}
    return {**rec, 'at': datetime.datetime.now().astimezone().isoformat(timespec='seconds'), 'item': rnd,
            'override': ov, 'routed_choice': base, 'choice': choice,
            'reason': f"override: {ov['reason']} | routed: {rec.get('routed_reason', rec['reason'])}",
            'routed_reason': rec.get('routed_reason', rec['reason'])}


def same_family_refused(run, rnd, kind, rec, author, cfg):
    """Log and report a review whose final model shares the author's family, or whose author is unknown from the
    argument, the log and the saved decision, without override same_family=yes."""
    if kind != 'review' or (rec.get('override') or {}).get('same_family'):
        return False
    author = author or (rec.get('inputs') or {}).get('author_model')
    if author and family(rec['choice']['model'], cfg) != family(author, cfg):
        return False
    why = 'review in the author\'s model family' if author else 'review whose author model is unknown'
    log(run, {'event': 'refuse', 'at': datetime.datetime.now().astimezone().isoformat(timespec='seconds'), 'round': rnd,
              'kind': kind, 'model': rec['choice']['model'], 'author_model': author, 'decision_at': rec.get('at'),
              'reason': why})
    print(f"route.py: refused: {why} ({rnd} would run {rec['choice']['model']}, author {author or 'unknown'}); "
          'pass --author-model, or only for the fallback after a 422, --override "...,same_family=yes,reason=.."',
          file=sys.stderr)
    return True


def earlier_fix_round(run, rnd, kind):
    """Why rnd would be an item's second fix round (its name is <item>-fixN with N >= 2, or routes.jsonl already
    has a fix launch for the item), else None. A resume continues a round, so it is never a new fix round."""
    import mine
    item, name_kind = mine.split_name(rnd)
    if kind == 'resume' or (kind != 'fix' and name_kind != 'fix'):
        return None
    m = FIX_N.search(rnd)
    if name_kind == 'fix' and m and int(m.group(1)) >= 2:
        return f'{rnd} is fix round {int(m.group(1))} of {item}'
    for _, d in mine.read_routes(run):
        r = d.get('round')
        if d.get('event') == 'launch' and isinstance(r, str) and mine.split_name(r)[0] == item and \
                (d.get('kind') == 'fix' or mine.split_name(r)[1] == 'fix'):
            return f'{item} already had fix round {r} (launched {d.get("at")})'
    return None


def fix_round_refused(run, rnd, kind, ov):
    """Log and report a second fix round for an item without owner_approved in the override (owner, 2026-10-31:
    one review, one fix round, then the owner decides)."""
    why = earlier_fix_round(run, rnd, kind)
    if not why or (ov or {}).get('owner_approved'):
        return False
    log(run, {'event': 'refuse', 'at': datetime.datetime.now().astimezone().isoformat(timespec='seconds'), 'round': rnd,
              'kind': kind, 'reason': f'second fix round without the owner: {why}'})
    print(f'route.py run: refused: {why}; one fix round, then the owner decides; with their approval pass '
          '--override "owner_approved=<where the owner said so>,reason=.."', file=sys.stderr)
    return True


def author_from_log(run, rnd):
    """(model, file) of the item's latest author round log in the run folder, else (None, None)."""
    import mine
    item = mine.split_name(rnd)[0]
    found = []
    for fn in os.listdir(run):
        if not fn.endswith('.jsonl') or fn in NOT_ROUND:
            continue
        it, kind = mine.split_name(fn[:-len('.jsonl')])
        if it == item and kind not in mine.REVIEW_KINDS:
            found.append((os.path.getmtime(os.path.join(run, fn)), fn))
    for _, fn in sorted(found, reverse=True):
        r = mine.read_round(os.path.join(run, fn))
        if r and r.get('model'):
            return r['model'], fn
    return None, None


def mcp_servers():
    try:
        with open(os.path.expanduser('~/.copilot/mcp-config.json'), encoding='utf-8') as f:
            return list(json.load(f).get('mcpServers', {}))
    except (OSError, ValueError, AttributeError):
        return []


def cli_version():
    try:
        done = subprocess.run(['copilot', '--version'], capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    lines = done.stdout.strip().splitlines()
    return lines[0].strip() if done.returncode == 0 and lines else None


def launch_argv(rnd, kind, wt, choice, add_dirs, prompt):
    argv = ['copilot', '-C', wt, '-n', os.environ.get('OW_PREFIX', 'ow-') + rnd, '--model', choice['model'],
            '--reasoning-effort', choice['effort'], '--context', choice.get('context') or 'default']
    argv += ['--no-ask-user', '--allow-all-tools', '--deny-tool', 'shell(git push)']
    if kind == 'review':
        argv += ['--deny-tool', 'shell(git commit)', '--deny-tool', 'shell(npm)', '--deny-tool=url']
    argv += ['--disable-builtin-mcps']
    for s in mcp_servers():
        argv += ['--disable-mcp-server', s]
    for d in add_dirs:
        argv += ['--add-dir', d]
    return argv + ['--output-format', 'json', '-p', prompt]


def set_budget(run, rnd, kind, text):
    """Write the round's time budget in minutes to budgets.json (the brief's TIME BUDGET, else the one there) and return it."""
    path = os.path.join(run, 'budgets.json')
    with locked(path):
        try:
            with open(path, encoding='utf-8') as f:
                b = json.load(f)
        except FileNotFoundError:
            b = {}
        m = re.search(r'^TIME BUDGET:\s*(\d+)', text, re.M)
        old = b.get(rnd, b.get(mine_kind(kind)))
        b[rnd] = int(m.group(1)) if m else old if isinstance(old, (int, float)) else (30 if kind == 'review' else 60)
        write_json(path, b)
    return b[rnd]


def sweep(*args):
    return subprocess.run([sys.executable, '-B', os.path.join(HERE, 'sweep.py'), *args], stdin=subprocess.DEVNULL).returncode


SESSION_STATE = os.environ.get('OW_SESSION_STATE') or os.path.expanduser('~/.copilot/session-state')


class Spend:
    """Credits a named CLI session has spent, priced from its usage records; unlike --max-ai-credits the worker never sees it."""

    def __init__(self, name, prices, root=SESSION_STATE):
        self.name, self.prices, self.root, self.offsets, self.credits = name, prices, root, {}, 0.0

    def dirs(self):
        try:
            entries = os.listdir(self.root)
        except OSError:
            return []
        found = []
        for d in entries:
            try:
                with open(os.path.join(self.root, d, 'workspace.yaml'), encoding='utf-8') as f:
                    if re.search(rf'^name: {re.escape(self.name)}\s*$', f.read(), re.M):
                        found.append(os.path.join(self.root, d))
            except OSError:
                continue
        return found

    def read(self):
        import mine
        for d in self.dirs():
            path = os.path.join(d, 'events.jsonl')
            try:
                with open(path, 'rb') as f:
                    f.seek(self.offsets.get(path, 0))
                    data = f.read()
            except OSError:
                continue
            end = data.rfind(b'\n') + 1
            self.offsets[path] = self.offsets.get(path, 0) + end
            for line in data[:end].splitlines():
                if b'session.usage_record' not in line:
                    continue
                try:
                    u = json.loads(line)['data']['usage']
                except (ValueError, KeyError, TypeError):
                    continue
                cr, cw = u.get('cacheReadTokens') or 0, u.get('cacheWriteTokens') or 0
                tokens = {'input': max(0, (u.get('inputTokens') or 0) - cr - cw), 'output': u.get('outputTokens') or 0,
                          'cache_read': cr, 'cache_write': cw}
                self.credits += sum(mine.price_tokens(tokens, self.prices.get(u.get('model'))).values())
        return self.credits


def wait_round(p, secs, stop, spend, poll=30):
    """(rc, credits when stopped or None): wait for the round, ending it at its time limit or past its credit stop."""
    deadline, base = datetime.datetime.now().timestamp() + secs, spend.read() if stop is not None else 0
    while True:
        try:
            return p.wait(timeout=max(1, min(poll, deadline - datetime.datetime.now().timestamp()))), None
        except subprocess.TimeoutExpired:
            pass
        used = spend.read() - base if stop is not None else 0
        over = stop is not None and used > stop
        if over or datetime.datetime.now().timestamp() >= deadline:
            for sig in (signal.SIGTERM, signal.SIGKILL):
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    os.killpg(p.pid, sig)
                try:
                    p.wait(timeout=10)
                    break
                except subprocess.TimeoutExpired:
                    pass
            return (STOPPED, round(used, 1)) if over else (124, None)


STOPPED = 3


def outcome(rc, path):
    """The launcher's exit code: copilot's own when non-zero, 3 when the round hit its cap, 4 when it errored or has no result."""
    import mine
    if rc == STOPPED:
        return STOPPED
    r = mine.read_round(path) if os.path.exists(path) else None
    if rc != 0:
        return 128 - rc if rc < 0 else rc
    if r and (r['cap'] or {}).get('capped'):
        return 3
    if r is None or r['error'] or r['exit'] != 0:
        return 4
    return 0


REVIEW_TAIL = '\n\nYour LAST message is the only one read: repeat every finding in it in full, even ones an earlier message gave.\n'


def run_round(a, cfg):
    import runqueue
    refusal = runqueue.caffeinate_refusal()
    if refusal:
        print(f'route.py run: {refusal}', file=sys.stderr)
        return 2
    run = os.path.abspath(os.path.expanduser(a.run or os.environ.get('OW_RUN_DIR') or ''))
    rnd, kind, wt = a.round, a.kind, os.path.abspath(os.path.expanduser(a.worktree))
    if not a.run and not os.environ.get('OW_RUN_DIR') or not os.path.isdir(run):
        print('route.py run: set --run or OW_RUN_DIR to the run folder', file=sys.stderr)
        return 2
    if not os.path.isdir(wt):
        print(f'route.py run: no worktree at {wt}', file=sys.stderr)
        return 2
    try:
        ov = parse_override(a.override) if a.override is not None else None
    except ValueError as ex:
        print(f'route.py run: override refused: {ex}', file=sys.stderr)
        return 2
    if fix_round_refused(run, rnd, kind, ov):
        return 2
    brief = os.path.abspath(os.path.expanduser(a.brief))
    if subprocess.run([sys.executable, '-B', os.path.join(HERE, 'brief.py'), 'check', '--repo', wt, brief],
                      stdin=subprocess.DEVNULL).returncode:
        return 5
    with open(brief, encoding='utf-8') as f:
        text = f.read()
    review_diff = os.path.join(wt, 'REVIEW-DIFF.patch')
    a.diff_size = None
    if kind in ('review', 'fix') and os.path.isfile(review_diff):
        with open(review_diff, encoding='utf-8', errors='replace') as f:
            patch = f.read()
        a.changed = changed_files(patch)
        if kind == 'review':
            a.diff_size = (len(patch), review_diff)
    author_src = 'argument' if a.author_model else None
    if kind == 'review' and not a.author_model:
        a.author_model, fn = author_from_log(run, rnd)
        author_src = fn and f'log:{fn}'
    version = cli_version()
    with locked(os.path.join(run, f'.{rnd}.route')):
        rec, new = None if a.fresh else pending(run, rnd), None
        if rec is not None and ov is not None and rec.get('override') != ov:
            new = apply_override(rec, ov, rnd)
        elif rec is None:
            new = draw(a, run, rnd, kind, text, cfg)
            new['inputs']['author_source'] = author_src
            if ov is not None:
                new = apply_override(new, ov, rnd)
        if same_family_refused(run, rnd, kind, new or rec, a.author_model, cfg):
            return 2
        if new is not None:
            rec = new
            if kind == 'review' and not a.diff:
                size, src = a.diff_size or (None, None)
                rec['inputs'] = {**rec.get('inputs', {}), 'diff_chars': size, 'diff_source': src}
            rec.update(cli_version=version, model_id=rec['choice']['model'], worktree=wt)
            log(run, rec)
    c = rec['choice']
    minutes = set_budget(run, rnd, kind, text)
    secs = a.timeout or int(minutes * 60 * (1 if kind == 'review' else 3))
    emit(rec)
    if a.load_wait and sweep('load', '--wait', str(a.load_wait)):
        print(f'LOAD: {rnd} not launched', file=sys.stderr)
        return 12
    argv = launch_argv(rnd, kind, wt, c, a.add_dir or [], text + (REVIEW_TAIL if kind == 'review' else ''))
    jsonl = os.path.join(run, rnd + '.jsonl')
    try:
        with open(os.path.join(run, rnd + '.start'), 'w') as f:
            f.write(f'{int(datetime.datetime.now().timestamp())}\n')
        base = subprocess.run(['git', '-C', wt, 'rev-parse', 'HEAD'], capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if base.returncode == 0:
            with open(os.path.join(run, rnd + '.base'), 'w') as f:
                f.write(base.stdout)
        else:
            print(f'route.py run: no git HEAD in {wt}; {rnd}.base not written', file=sys.stderr)
        log(run, {'event': 'launch', 'at': datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
                  'round': rnd, 'kind': kind, 'decision_at': rec['at'], 'cli_version': version, 'model_id': c['model'],
                  'timeout_s': secs, 'brief': brief, 'argv': argv[:-1],
                  **({'owner_approved': ov['owner_approved']} if (ov or {}).get('owner_approved') else {})})
        env = {**os.environ, 'COPILOT_TASK_WAIT_TIMEOUT_SECONDS': str(min(5400, secs)), 'GIT_CONFIG_COUNT': '1',
               'GIT_CONFIG_KEY_0': 'url.blocked-by-orchestrator://.pushInsteadOf', 'GIT_CONFIG_VALUE_0': ''}
        print(f"launch {rnd} {c['model']}/{c['effort']}/{c.get('context', 'default')} cap {c.get('cap')} timeout {secs}s "
              f"at {datetime.datetime.now():%H:%M:%S}", flush=True)
        with open(jsonl, 'wb') as out, open(os.path.join(run, rnd + '.err'), 'wb') as err:
            try:
                p = subprocess.Popen(argv, cwd=wt, stdin=subprocess.DEVNULL, stdout=out, stderr=err, env=env,
                                     start_new_session=True)
            except OSError as ex:
                print(f'route.py run: cannot start copilot: {ex}', file=sys.stderr)
                return 127
            import mine
            spend = Spend(os.environ.get('OW_PREFIX', 'ow-') + rnd, mine.load_prices(run))
            rc, stopped_at = wait_round(p, secs, c.get('cap'), spend)
            if stopped_at is not None:
                write_json(os.path.join(run, rnd + '.stopped'), {'credits': stopped_at, 'stop': c.get('cap'),
                           'at': datetime.datetime.now().astimezone().isoformat(timespec='seconds')})
                print(f'STOPPED: {rnd} spent {stopped_at} credits, past its stop of {c.get("cap")}; resumable', flush=True)
    finally:
        sweep('leftovers', wt, '--kill')
    code = outcome(rc, jsonl)
    print(f"{rnd} exit {rc}{' TIMED OUT' if rc == 124 else ''} -> {code} at {datetime.datetime.now():%H:%M:%S}", flush=True)
    subprocess.run([sys.executable, '-B', os.path.join(HERE, 'result.py'), jsonl, '--no-report'], stdin=subprocess.DEVNULL)
    return code


def emit(rec):
    c = rec['choice']
    print(f"MODEL={c['model']} EFFORT={c['effort']} CONTEXT={c.get('context', 'default')} "
          f"CAP={'none' if c.get('cap') is None else c['cap']}")
    print(f"# {rec['reason']}")


def report(run, rounds=None, items=None):
    decisions = [d for d in read_decisions(run) if isinstance(d.get('choice'), dict)]
    if rounds is None:
        rounds, items = load_mine(run)
    by_item = {i['item']: i for i in items}
    lines, by_arm = [], collections.defaultdict(lambda: [0, 0])
    for d in decisions:
        c = d['choice']
        base = re.sub(r'-(re)?(fix|review)\d+$', '', d['item'])
        match = [r for r in rounds if r['item'] in (d['item'], base) and mine_kind(r['kind']) == mine_kind(d['kind'])]
        r = next((x for x in match if x['model'] == c['model']), match[-1] if match else None)
        if r is None:
            outcome = 'no round yet'
        elif not r.get('ended'):
            outcome = f"running {r['model']}/{r['effort']}"
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
    routing = argparse.ArgumentParser(add_help=False)
    routing.add_argument('--kind', required=True, choices=KINDS)
    routing.add_argument('--author-model', help='a review: the author round\'s model (default: read from its log); a resume: the model it continues')
    routing.add_argument('--diff', help='a diff file whose text is also checked for risk areas')
    routing.add_argument('--budget-left', type=float, help='fraction of the run\'s credit budget still unspent (0 to 1)')
    routing.add_argument('--run-fraction', type=float, help='fraction of the run\'s planned time already elapsed (0 to 1)')
    routing.add_argument('--seed', type=int, help='fix the random draws (logged either way)')
    routing.add_argument('--grades-json', help='a classifier answer to use instead of calling copilot (a file or JSON)')
    routing.add_argument('--no-classifier', action='store_true', help='use the keyword rules without calling copilot')
    routing.add_argument('--fresh', action='store_true', help='draw again instead of reusing the round\'s unlaunched decision')
    routing.add_argument('--history-root', default=STATE_ROOT)
    routing.add_argument('--config')
    p = sub.add_parser('pick', parents=[routing])
    p.add_argument('--run', required=True)
    p.add_argument('--item', required=True)
    p.add_argument('--prompt', required=True, help='the brief file')
    n = sub.add_parser('run', parents=[routing], help='pick or take the override, log it, and launch the round')
    n.add_argument('round', help='the round name: <item>, <item>-fixN, <item>-review ...')
    n.add_argument('--run', help='run folder (default: $OW_RUN_DIR)')
    n.add_argument('--brief', required=True)
    n.add_argument('--worktree', required=True)
    n.add_argument('--override', help='"model=..,effort=..,context=..,cap=N|none,owner_approved=..,reason=.." (reason required, last)')
    n.add_argument('--add-dir', action='append', help='passed to copilot; repeatable')
    n.add_argument('--timeout', type=int, help='seconds (default: from the time budget)')
    n.add_argument('--load-wait', type=float, default=15, help='minutes sweep.py load waits; 0 skips it (default 15)')
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
    if a.cmd == 'run':
        return run_round(a, load_config(a.config))
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
    if a.cmd == 'escalate':
        try:
            rec = escalate(a.item, load_history(run, a.history_root), cfg, run)
        except LookupError as ex:
            print(f'route.py: {ex}', file=sys.stderr)
            return 2
        rec.update(cli_version=cli_version(), model_id=rec['choice']['model'])
        log(run, rec)
        emit(rec)
        return 0
    with open(os.path.expanduser(a.prompt), encoding='utf-8') as f:
        text = f.read()
    if a.kind == 'review' and not a.author_model:
        a.author_model = author_from_log(run, a.item)[0]
    with locked(os.path.join(run, f'.{a.item}.route')):
        rec = None if a.fresh else pending(run, a.item)
        if rec is None:
            rec = draw(a, run, a.item, a.kind, text, cfg)
            if same_family_refused(run, a.item, a.kind, rec, a.author_model, cfg):
                return 2
            rec.update(cli_version=cli_version(), model_id=rec['choice']['model'])
            log(run, rec)
        else:
            if same_family_refused(run, a.item, a.kind, rec, a.author_model, cfg):
                return 2
            print(f'# reusing the decision logged at {rec["at"]}; --fresh draws again')
    emit(rec)
    return 0


def draw(a, run, item, kind, text, cfg):
    text = task_part(text)
    history = load_history(run, a.history_root)
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
    rec = pick(item, kind, text, history, cfg, a.author_model, diff, a.budget_left, a.run_fraction,
               random.Random(seed), seed, call, a.author_model if kind == 'resume' else None,
               getattr(a, 'changed', ()))
    if a.diff:
        rec['inputs']['diff_source'] = os.path.abspath(os.path.expanduser(a.diff))
    return rec


if __name__ == '__main__':
    sys.exit(main())
