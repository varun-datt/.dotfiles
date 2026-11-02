#!/usr/bin/env python3
"""The review record: every finding of a run's reviews as a SARIF 2.1.0 result (`mine.py RUN --findings`).

Writes <out>/findings.jsonl (one SARIF `result` per observation of a finding, in round order) and
<out>/defects.jsonl (one line per defect id), and with --sarif <out>/findings.sarif (one SARIF log).
SARIF 2.1.0: https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html. Field use:
    ruleId          the cause code (MUST, ADJ, ...); absent when the finding has none
    level           error for Blocker and Major, warning for Minor, note for anything else
    message.text    the finding's title
    locations       the first path:line in the finding
    partialFingerprints["reviewDefect/v1"]  the defect id: a hash of item, file, code area (the file's
                    folder), cause and class, never the line; "/<k>" tells apart findings of one fingerprint
    baselineState   new (first observation), unchanged (re-review: not fixed), updated (partly fixed),
                    absent (fixed)
    suppressions    one, kind external and status accepted, when the finding was ruled wrong or out of
                    scope (the suppression is what is accepted); none when accepted, demoted or unruled
    properties      everything SARIF has no field for (run, item, round, ruling, ruling_source, ...)
Rulings, most trusted first: rulings.jsonl (a Blocker ruled Major is accepted), the next fix brief's
ACCEPTED list, its REJECTED list (an item sent to debt is out of scope), its RECORDED / "Record only"
lines (demoted), "could not reproduce" in the fix report (rejected, wrong), then a later re-review that
carries the defect (accepted). A finding no source rules stays unruled.
"""
import collections, difflib, hashlib, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mine

SARIF_SCHEMA = 'https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json'
FP_KEY = 'reviewDefect/v1'
LEVELS = {'Blocker': 'error', 'Major': 'error', 'Minor': 'warning'}
BASELINE = ('new', 'unchanged', 'updated', 'absent')
SOURCES = ('rulings.jsonl', 'fix-brief-accepted', 'fix-brief-rejected', 'fix-brief-recorded', 'fix-report',
           'rereview')
CRITIQUE = re.compile(r'-critique(?:-[a-z0-9]+)?$')
LINK = re.compile(r'\[[^\]]*\]\(([^)\s#]+)#L(\d+)[^)]*\)')
PATH_LINE = re.compile(r'(?<![\w/.-])((?:[\w.-]+/)*[\w-][\w.-]*\.[A-Za-z][A-Za-z0-9]*):(\d+)')
GRADE = re.compile(r'\b(Blocker|Major|Minor|Nit)\b')
RUBRIC = re.compile(r'\b(COR|DATA|SEC|PERF|REL|UX|COMP|COST|VERIF|MAINT|REPORT)\s+L([1-3])/I([1-4])\b')
ITEM = re.compile(r'^[*_\s]*(?:(B)(\d+)|(F)?(\d+))[.):][*_]*\s+(.*)$')
TABLE_N = re.compile(r'^\|\s*[*_]*(\d+)[*_]*\s*\|')
KNOWN_LIMIT = re.compile(r'\bknown limit\b|\brecord it\b|\bdo not (?:build|fix)\b', re.I)
# The security-review caller contract's follow-up choices, which end its report as a numbered list.
OPTIONS = re.compile(r'^[\s*_"]*(?:Fix highest severity issues|Fix all issues|Commit a summary of findings)\b', re.I)
NOT_REPRO = re.compile(r"\b(?:could\s*n[o']t|cannot|can't|could\s+not|unable\s+to)\s+reproduce|\bnot\s+reproduced\b", re.I)
SECTIONS = (('new', ('new blocking', 'new harm', 'new finding', 'new major', 'new blocker')),
            ('minor', ('minor', 'non-blocking', 'nonblocking', 'new minor')),
            ('pre', ('pre-existing', 'preexisting')),
            ('correction', ('correction', 'unsupported report')),
            ('check', ('check',)),
            ('blocking', ('blocking', 'findings', 'major', 'blocker')),
            ('skip', ('nit', 'not checked', 'outside scope', 'verified', 'open', 'case against', 'met', 'requirement')))
PREFIX = {'minor': 'm', 'pre': 'p', 'correction': 'x', 'check': 'k'}
WRONG = ('by design', 'not a defect', 'not a bug', 'wrong', 'far-fetched', 'contrived', 'reproduc', 'belong',
         'intended', 'correct as', 'already', 'incorrect', 'false', 'holds outside data only', 'misread')
SCOPE = ('debt', 'pre-existing', 'preexisting', 'out of scope', 'out-of-scope', 'scope', 'gate', "owner's call",
         'owner decides', 'later', 'not this', 'separate', 'follow-up', 'phase')
WORD = re.compile(r'[a-z][a-z0-9]{2,}')
STOP = set('the and for with that this from into its are was were not but has have than then when what which '
           'only also each every still does did can its their there here these those both they them our your '
           'fix fixed finding findings verified inferred open read blocking major minor test tests'.split())


def is_fix(r):
    # load_rounds gives a research run's fix round the run's kind; the name still says fix.
    return r['kind'] == 'fix' or bool(re.search(r'-fix\d*$', r['name']))


def section_of(line):
    """The section a heading line opens, or None when the line is not a heading."""
    s = line.strip()
    bare = s.strip('#*_ ').rstrip('.:').strip('*_ ').lower()
    heading = s.startswith('#') or (s.startswith(('**', '__')) and s.rstrip('.: ').endswith(('**', '__'))
                                    and len(bare) < 40)
    if not heading or not bare or re.match(r'\d+\s+(?:blocking|blocker|major)', bare):
        return None
    for name, words in SECTIONS:
        if any(bare.startswith(w) for w in words):
            return name
    return 'skip'


def first_location(text):
    """(path, line) of the first path:line in the text; a Markdown link to path#Lnn counts as path:nn."""
    flat = LINK.sub(lambda m: f' {m.group(1)}:{m.group(2)} ', text or '')
    m = PATH_LINE.search(flat)
    return (m.group(1).lstrip('./') or None, int(m.group(2))) if m else (None, None)


def tags(text):
    """(cause, class, area, likelihood, impact, grade) read with mine.py's readers."""
    lines = (text or '').splitlines()
    got = mine.causes(text)
    cause, cls = (got[0] if got else (None, None))
    for line in lines:
        m = mine.CLASS_LINE.match(line.strip())
        if m and not cls:
            cls = m.group(1).strip()
            break
        inline = re.search(r'\bclass\s*:\s*([^.;\n]+)', line, re.I)
        if inline and not cls:
            cls = inline.group(1).strip(' *_`')
            break
    r = RUBRIC.search(text or '')
    g = GRADE.search(text or '')
    return (cause, (cls or None) and cls.strip().lower(), r and r.group(1), r and f'L{r.group(2)}',
            r and f'I{r.group(3)}', g and g.group(1))


def title_of(text):
    first = re.sub(r'\s+', ' ', (text or '').strip().splitlines()[0] if text.strip() else '')
    first = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', first)
    m = re.search(r'\b(?:Blocker|Major|Minor|Nit)\]?\s*(?:[A-Z]+\s+L[1-3]/I[1-4]\s+)?[A-Z]*\s*:\s*(.+)$', first)
    t = m.group(1) if m else first
    t = re.sub(r'^[\s*_]*(?:(?:VERIFIED|INFERRED|OPEN)\b[^:—-]*[:—-]\s*)+', '', t)
    t = re.sub(r'^[\s*_]*(?:[\w./-]+:[\d–,\s-]+)+[:)]?\s*[*_]*\s*', '', t)
    t = t.replace('**', '').replace('__', '').strip(' *_')
    return t[:200] or '(untitled finding)'


def status_of(text):
    low = (text or '').lower()
    if re.search(r'\bnot\s+fixed\b|\bremains?\b|\bstill\b|\bunfixed\b', low[:300]):
        if re.search(r'\bpartly\b|\bpartially\b|\bincomplete\b', low[:300]):
            return 'updated'
        return 'unchanged'
    if re.search(r'\bpartly\b|\bpartially\b|\bincomplete\b|\bpartial\b', low[:300]):
        return 'updated'
    if re.search(r'\bfixed\b', low[:300]):
        return 'absent'
    return None


def is_blocking(text, section, grade, status):
    low = (text or '')[:400].lower()
    if section in PREFIX:
        return False
    if re.search(r'non-?\s?blocking', low):
        return False
    if status == 'absent':
        return False
    if status in ('unchanged', 'updated'):
        return True
    if grade in ('Blocker', 'Major') or re.search(r'\bblocking\b', low):
        return True
    return section in ('blocking', 'new') and grade is None and None


def split(report, rereview=False):
    """Findings in a review report: (label, text, section) per numbered item, table row or tagged paragraph."""
    out, cur, section, counters = [], None, None, collections.Counter()
    fenced, table = False, None

    def close():
        if not cur:
            return
        same = next((o for o in out if o['label'] == cur['label'] and o['section'] == cur['section']), None)
        if same:
            same['text'] += '\n' + cur['text']
        elif not OPTIONS.match(cur['text']):
            out.append(cur)
    for raw in (report or '').splitlines():
        s = raw.strip()
        if s.startswith(('```', '~~~')):
            fenced = not fenced
            continue
        if fenced:
            continue
        sec = section_of(s)
        if sec:
            close()
            cur, section = None, sec
            continue
        m = ITEM.match(s) if not raw[:1].isspace() else None
        t = TABLE_N.match(s)
        if s.startswith('|'):
            cells = [c.strip().strip('*_` ').lower() for c in s.strip('|').split('|')]
            if all(re.fullmatch(r':?-+:?', c) for c in cells if c):
                continue
            if any(c in ('#', 'finding', 'severity', 'vulnerability', 'issue') for c in cells) and not t:
                close()
                cur, table = None, 0
                continue
            if table is not None and not t:
                table += 1
                t = re.match(r'^()', s)
                num_from_table = str(table)
            else:
                num_from_table = None
        else:
            table = None
            num_from_table = None
        tagged = (section in PREFIX or section in ('blocking', 'new')) and (mine.GRADED_TAG.search(s) or RUBRIC.search(s)) \
            and not m and not t and not raw[:1].isspace()
        tagged = tagged or (section == 'correction' and s and not m and not s.startswith('|'))
        if section == 'skip' and not (m and m.group(1)):
            if cur and s:
                cur['text'] += '\n' + s
            continue
        if m or t or tagged:
            close()
            sec = section or 'blocking'
            if m and m.group(1):
                sec = 'new' if rereview else ('blocking' if sec in ('skip', None) else sec)
            if t:
                num, body = (num_from_table or t.group(1)), s
            elif m:
                num, body = (m.group(2) or (m.group(3) or '') + m.group(4)), m.group(5)
            else:
                num, body = None, s
            if sec in PREFIX:
                counters[sec] += 1
                label = PREFIX[sec] + str(counters[sec])
            elif rereview and sec == 'blocking' and not (m and m.group(1)):
                label = 'c' + str(num)
            else:
                label = str(num) if num else 'b' + str(len(out) + 1)
            cur = {'label': label, 'text': body, 'section': sec}
            continue
        if cur is not None:
            if not s:
                close()
                cur = None
                continue
            cur['text'] += '\n' + s
    close()
    return out


def parse(report, rereview=False):
    found = []
    for f in split(report, rereview):
        cause, cls, area, lik, imp, grade = tags(f['text'])
        if cause is None:
            cells = [c.strip().strip('*_`') for c in f['text'].split('|')]
            cause = next((c.upper() for c in cells if c.upper() in mine.CAUSES), None)
        if grade is None and f['section'] in ('minor',):
            grade = 'Minor'
        path, line = first_location(f['text'])
        status = status_of(f['text']) if f['label'].startswith('c') else None
        found.append({'n': f['label'], 'section': f['section'], 'title': title_of(f['text']), 'text': f['text'],
                      'cause': cause, 'class': cls, 'area': area, 'likelihood': lik, 'impact': imp, 'grade': grade,
                      'file': path, 'line': line, 'status': status,
                      'blocking': bool(is_blocking(f['text'], f['section'], grade, status))})
    return found


def words(text):
    out = set()
    text = PATH_LINE.sub(' ', re.sub(r'\]\([^)]*\)', ']', text or ''))
    for w in WORD.findall(text.lower()):
        if w in STOP:
            continue
        out.add(w[:-1] if w.endswith('s') and len(w) > 4 else w)
    return out


def similarity(a, b):
    wa, wb = words(a['text'] if isinstance(a, dict) else a), words(b['text'] if isinstance(b, dict) else b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / min(len(wa), len(wb))


def files_in(text):
    flat = LINK.sub(lambda m: f' {m.group(1)}:{m.group(2)} ', text or '')
    return {os.path.basename(p) for p, _ in PATH_LINE.findall(flat)} | \
        {os.path.basename(p) for p in re.findall(r'`([\w./-]+\.[A-Za-z]+)`', text or '')}


def match(items, findings, floor=0.25, hint=None):
    """Greedy one-to-one pairs (item index, finding index) by shared words and files, best first."""
    scored = []
    for i, it in enumerate(items):
        fi = files_in(it)
        for j, f in enumerate(findings):
            s = similarity(it, f) + (0.15 if fi & files_in(f['text']) else 0)
            if hint and hint(i, j):
                s += 0.05
            if s >= floor:
                scored.append((-s, i, j))
    used_i, used_j, pairs = set(), set(), []
    for _, i, j in sorted(scored):
        if i not in used_i and j not in used_j:
            used_i.add(i)
            used_j.add(j)
            pairs.append((i, j))
    return pairs


def reason_of(text):
    low = (text or '').lower()
    if any(w in low for w in SCOPE):
        return 'out-of-scope'
    if any(w in low for w in WRONG):
        return 'wrong'
    return 'unclear'


def list_after(lines, i):
    """The text after a label line's colon, then its list items (or its paragraph) up to a blank line."""
    head = lines[i].split(':', 1)[1].strip() if ':' in lines[i] else ''
    items, para = [], [head] if head else []
    for nxt in lines[i + 1:]:
        s = nxt.strip()
        if not s:
            if items or para:
                break
            continue
        if mine.LIST_ITEM.match(s):
            items.append(s)
        elif items and nxt[:1].isspace():
            items[-1] += ' ' + s
        elif items:
            break
        else:
            para.append(s)
    if items:
        return items
    text = ' '.join(para).strip()
    return [] if not text or re.match(r'^none\b', text.lower()) else [text]


def brief(run, fix_name):
    """{'accepted': [...], 'rejected': [...], 'recorded': [...]} from a fix round's brief, or None without one."""
    for fn in (fix_name + '.md', fix_name + '.prompt.md', fix_name + '.body.md'):
        try:
            with open(os.path.join(run, fn), encoding='utf-8', errors='replace') as f:
                lines = re.split(r'(?m)^==== ORIGINAL TASK ====\s*$', f.read())[0].splitlines()
        except OSError:
            continue
        out = {'accepted': [], 'rejected': [], 'recorded': []}
        seen = False
        for i, line in enumerate(lines):
            up = line.strip().lstrip('*_').upper()
            if up.startswith('ACCEPTED'):
                out['accepted'] += list_after(lines, i)
            elif up.startswith(('REJECTED', 'NOT TO CHANGE')):
                out['rejected'] += list_after(lines, i)
            elif up.startswith(('RECORDED', 'RECORD ONLY')):
                out['recorded'] += list_after(lines, i)
            else:
                continue
            seen = True
        if not seen:
            # Older briefs (2026-10-27 to 10-29) list the findings to fix as numbered items under a THIS ROUND or Fix round line.
            start = next((i for i, line in enumerate(lines)
                          if line.strip().upper().startswith(('THIS ROUND', 'FIX ROUND'))), None)
            for line in lines[start + 1:] if start is not None else []:
                s = line.strip()
                if mine.LIST_ITEM.match(s):
                    out['accepted'].append(s)
                elif out['accepted'] and s and line[:1].isspace():
                    out['accepted'][-1] += ' ' + s
                elif out['accepted']:
                    break
            out['recorded'] = [a for a in out['accepted'] if KNOWN_LIMIT.search(a)]
            out['accepted'] = [a for a in out['accepted'] if not KNOWN_LIMIT.search(a)]
            seen = bool(out['accepted'] or out['recorded'])
        if seen:
            return out
    return None


def defect_fp(item, f):
    folder = os.path.dirname(f['file']) if f['file'] else ''
    key = '\x1f'.join([item, f['file'] or '', folder, f['cause'] or '', f['class'] or ''])
    return hashlib.sha256(key.encode('utf-8')).hexdigest()[:16], folder or None


def report_of(run, r):
    text = r.get('report')
    if not text:
        try:
            with open(os.path.join(run, r['name'] + '.txt'), encoding='utf-8', errors='replace') as f:
                text = f.read()
        except OSError:
            text = None
    return text


def fix_message(run, name):
    try:
        r = mine.read_round(os.path.join(run, name + '.jsonl'))
    except OSError:
        return None
    return r and r['message']


def record(run, rounds=None):
    """(results, defects, counts, unparsed) for a run folder."""
    run = os.path.abspath(run)
    run_name = os.path.basename(run.rstrip(os.sep))
    if rounds is None:
        rounds = mine.load_rounds(run) if os.path.isdir(run) else []
    rulings = {}
    for row in mine.latest(mine.read_rulings(run) or []):
        rulings[(row['round'], str(row.get('n')))] = row
    by_item = collections.OrderedDict()
    for r in rounds:
        kind = 'critique' if CRITIQUE.search(r['name']) else r['kind']
        by_item.setdefault(CRITIQUE.sub('', r['name']) if kind == 'critique' else r['item'], []).append(dict(r, kind=kind))
    obs, unparsed, reviews = [], [], 0
    defects = collections.OrderedDict()
    for item, rs in by_item.items():
        rs.sort(key=lambda x: (x['start'], x['name']))
        open_obs = []
        for idx, r in enumerate(rs):
            if r['kind'] not in mine.REVIEW_KINDS + ('critique',):
                continue
            reviews += 1
            report = report_of(run, r)
            found = parse(report, r['kind'] == 'rereview')
            numbered = {f['n'] for f in found}
            for (rnd, n), row in rulings.items():
                if rnd == r['name'] and n not in numbered:
                    found.append({'n': n, 'section': 'blocking', 'title': f"finding {n} of {rnd} (from rulings.jsonl)",
                                  'text': row.get('reason') or '', 'cause': None, 'class': None,
                                  'area': row.get('area'), 'likelihood': None, 'impact': None, 'grade': row.get('grade'),
                                  'file': None, 'line': None, 'status': None, 'blocking': row.get('grade') in ('Blocker', 'Major'),
                                  'ruling_only': True})
            if not found and (r.get('blocking') or 0) > 0:
                unparsed.append({'round': r['name'], 'file': r['name'] + ('.txt' if not r.get('report') else '.jsonl'),
                                 'line': 1, 'why': f"verdict says {r['blocking']} blocking but no finding was split out"})
            elif (r.get('blocking') or 0) > 0 and not any(f['blocking'] for f in found):
                # Tables graded only by severity (CRITICAL, HIGH, MEDIUM): the verdict's count marks the first rows.
                for f in [f for f in found if f['section'] in ('blocking', 'new')
                          and not re.search(r'non-?\s?blocking', f['text'], re.I)][:r['blocking']]:
                    f['blocking'], f['blocking_from'] = True, 'verdict'
            prev_fix = next((x for x in reversed(rs[:idx]) if is_fix(x)), None)
            next_fix = next((x for x in rs[idx + 1:] if is_fix(x)), None)
            prev_brief = brief(run, prev_fix['name']) if prev_fix else None
            carried = [f for f in found if f['n'].startswith('c')]
            links = {}
            if carried and open_obs:
                accepted = (prev_brief or {}).get('accepted') or []
                targets = [o for o in open_obs]

                def hint(i, j, carried=carried, targets=targets):
                    return carried[i]['n'][1:] == targets[j]['f']['n']
                if accepted and len(accepted) >= len(carried):
                    pairs = match(accepted, [o['f'] for o in targets], floor=0.2)
                    by_brief = {i: j for i, j in pairs}
                    for ci, f in enumerate(carried):
                        k = int(f['n'][1:]) - 1 if f['n'][1:].isdigit() else -1
                        if k in by_brief:
                            links[id(f)] = targets[by_brief[k]]
                rest = [f for f in carried if id(f) not in links]
                free = [o for o in targets if all(o is not v for v in links.values())]
                for i, j in match([f['text'] for f in rest], [o['f'] for o in free], floor=0.2,
                                  hint=lambda i, j: rest[i]['n'][1:] == free[j]['f']['n']):
                    links[id(rest[i])] = free[j]
            fp_seen = collections.Counter()
            for f in found:
                fp, folder = defect_fp(item, f)
                f['code_area'] = folder
                o = {'f': f, 'round': r, 'item': item, 'fp': fp, 'rulings': [], 'next_fix': next_fix}
                link = links.get(id(f))
                if link:
                    o['defect'] = link['defect']
                    o['state'] = f['status'] or 'unchanged'
                    link['carried_by'] = r['name']
                else:
                    fp_seen[fp] += 1
                    base = f'{fp}/{fp_seen[fp]}'
                    did = base
                    k = fp_seen[fp]
                    while did in defects:
                        k += 1
                        did = f'{fp}/{k}'
                    o['defect'] = did
                    o['state'] = 'new'
                    o['introduced_by'] = prev_fix['name'] if r['kind'] == 'rereview' and prev_fix else None
                    defects[did] = {'defect_id': did, 'fingerprint': {'item': item, 'file': f['file'],
                                    'code_area': folder, 'cause': f['cause'], 'class': f['class']},
                                    'first_seen': f"{run_name}/{r['name']}/{f['n']}", 'introduced_by': o['introduced_by'],
                                    'observations': 0, 'last_state': None, 'fixed_in': None}
                d = defects[o['defect']]
                d['observations'] += 1
                d['last_state'] = o['state']
                if o['state'] == 'absent':
                    d['fixed_in'] = r['name']
                obs.append(o)
            this = [o for o in obs if o['round'] is r]
            open_obs = [o for o in open_obs if o.get('carried_by') is None] + this
            rule(run, r, this, rulings, next_fix)
    for o in obs:
        if o.get('carried_by'):
            o['rulings'].append({'ruling': 'accepted', 'reason': None, 'source': 'rereview',
                                 'evidence': f"carried by {o['carried_by']}"})
    results = [result(run_name, o) for o in obs]
    return results, list(defects.values()), {'reviews': reviews, 'findings': len(results),
                                             'defects': len(defects), 'unparsed': len(unparsed)}, unparsed


def rule(run, r, this, rulings, next_fix):
    for o in this:
        row = rulings.get((r['name'], o['f']['n']))
        if row:
            kind = mine.ruling_kind(row)
            if kind in ('accepted', 'promoted') or (kind == 'demoted' and row.get('ruled') in ('Blocker', 'Major')):
                o['rulings'].append({'ruling': 'accepted', 'reason': None, 'source': 'rulings.jsonl', 'evidence': row.get('reason')})
            elif kind == 'demoted':
                o['rulings'].append({'ruling': 'demoted', 'reason': None, 'source': 'rulings.jsonl', 'evidence': row.get('reason')})
            elif kind == 'rejected':
                o['rulings'].append({'ruling': 'rejected', 'reason': reason_of(row.get('reason')), 'source': 'rulings.jsonl',
                                     'evidence': row.get('reason')})
            elif kind == 'not-reproduced':
                o['rulings'].append({'ruling': 'rejected', 'reason': 'wrong', 'source': 'rulings.jsonl', 'evidence': row.get('reason')})
    if not next_fix or not this:
        return
    b = brief(run, next_fix['name'])
    fs = [o['f'] for o in this]
    if b:
        for key, source in (('accepted', 'fix-brief-accepted'), ('rejected', 'fix-brief-rejected'),
                            ('recorded', 'fix-brief-recorded')):
            items = b[key]
            for i, j in match(items, fs):
                text = items[i]
                if key == 'accepted':
                    ruling = {'ruling': 'accepted', 'reason': None}
                elif key == 'recorded':
                    ruling = {'ruling': 'demoted', 'reason': None}
                else:
                    ruling = {'ruling': 'rejected', 'reason': reason_of(text)}
                this[j]['rulings'].append(dict(ruling, source=source, evidence=text[:200]))
    msg = fix_message(run, next_fix['name'])
    if msg:
        paras = [p for p in re.split(r'\n\s*\n|\n(?=\s*(?:[-*+]|\d+[.)])\s)', msg) if NOT_REPRO.search(p)]
        for i, j in match(paras, fs, floor=0.15,
                          hint=lambda i, j: bool(re.search(r'(?:finding|B|#)\s*' + re.escape(fs[j]['n']) + r'\b', paras[i]))):
            this[j]['rulings'].append({'ruling': 'rejected', 'reason': 'wrong', 'source': 'fix-report',
                                       'evidence': paras[i].strip()[:200]})


def result(run_name, o):
    f, r = o['f'], o['round']
    ranked = sorted(o['rulings'], key=lambda x: SOURCES.index(x['source']))
    win = ranked[0] if ranked else None
    props = {'run': run_name, 'item': o['item'], 'round': r['name'], 'roundKind': r['kind'], 'n': f['n'],
             'grade': f['grade'], 'area': f['area'], 'likelihood': f['likelihood'], 'impact': f['impact'],
             'trigger': None, 'class': f['class'], 'focus': None, 'codeArea': f['code_area'],
             'origin': 'fix-introduced' if o.get('introduced_by') else ('fix-left' if o['state'] != 'new' else
                                                                       ('pre' if f['section'] == 'pre' else 'new')),
             'blocking': f['blocking'], 'section': f['section'],
             'ruling': win and win['ruling'], 'rulingReason': win and win['reason'], 'rulingSource': win and win['source'],
             'rulingEvidence': win and win['evidence'], 'rulingOthers': [x for x in ranked[1:]],
             'introducedBy': o.get('introduced_by'), 'unmetRequirement': None, 'mappedTest': None, 'points': None,
             'weightsVersion': None}
    if f.get('ruling_only'):
        props['fromRulingOnly'] = True
    if f.get('blocking_from'):
        props['blockingFrom'] = f['blocking_from']
    res = {'ruleId': f['cause'], 'level': LEVELS.get(f['grade'], 'note'), 'message': {'text': f['title']},
           'partialFingerprints': {FP_KEY: o['defect']}, 'baselineState': o['state'], 'properties': props}
    if res['ruleId'] is None:
        del res['ruleId']
    if f['file']:
        loc = {'artifactLocation': {'uri': f['file']}}
        if f['line'] and f['line'] >= 1:
            loc['region'] = {'startLine': f['line']}
        res['locations'] = [{'physicalLocation': loc}]
    if win and win['ruling'] == 'rejected':
        res['suppressions'] = [{'kind': 'external', 'status': 'accepted',
                                'justification': f"{win['reason']}: {win['evidence'] or 'ruled by ' + win['source']}"}]
    return res


def sarif_log(results):
    rules = sorted({x['ruleId'] for x in results if x.get('ruleId')})
    return {'$schema': SARIF_SCHEMA, 'version': '2.1.0',
            'runs': [{'tool': {'driver': {'name': 'orchestrator-workers-review', 'rules': [{'id': c} for c in rules]}},
                      'results': results}]}


def dump(rows):
    return ''.join(json.dumps(x, ensure_ascii=False, sort_keys=True) + '\n' for x in rows)


def write(run, out=None, sarif=False):
    out = out or run
    if not os.path.isdir(run):
        results, defects, counts, unparsed = [], [], {'reviews': 0, 'findings': 0, 'defects': 0, 'unparsed': 0}, []
    else:
        results, defects, counts, unparsed = record(run)
    os.makedirs(out, exist_ok=True)
    files = {'findings.jsonl': dump(results), 'defects.jsonl': dump(defects)}
    if sarif:
        files['findings.sarif'] = json.dumps(sarif_log(results), ensure_ascii=False, sort_keys=True, indent=1) + '\n'
    for name, text in files.items():
        tmp = os.path.join(out, name + '.tmp')
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(text)
        os.replace(tmp, os.path.join(out, name))
    lines = [f"findings: {counts['reviews']} reviews, {counts['findings']} findings, {counts['defects']} defects, "
             f"{counts['unparsed']} reports not parsed; written to {out}"]
    for u in unparsed:
        lines.append(f"  not parsed: {u['file']} line {u['line']}: {u['why']}")
    return '\n'.join(lines), counts
