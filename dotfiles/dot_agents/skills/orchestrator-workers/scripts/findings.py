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
PATH_LINE = re.compile(r'(?<![\w/.-])((?:/|\.{1,2}/)?(?:[\w.-]+/)*(?:[\w-][\w.-]*\.[A-Za-z][A-Za-z0-9]*|\.\w[\w.-]*'
                       r'|[A-Z]\w*file|(?<=/)[\w-]+)):(\d+)')
GRADE = re.compile(r'\b(Blocker|Major|Minor|Nit)\b')
RUBRIC = re.compile(r'\b(COR|DATA|SEC|PERF|REL|UX|COMP|COST|VERIF|MAINT|REPORT)\s+L([1-3])/I([1-4])\b')
ITEM = re.compile(r'^(?:#{1,6}\s+)?[*_\s]*(?:(?P<pre>[BFcM])(?P<pn>\d+)|(?P<num>\d+)(?:\s*\(\s*(?P<rp>[BF])?(?P<rn>\d+)\s*\))?)'
                  r'[*_]*[.):][*_]*\s+(?P<body>.*)$')
DETAIL = re.compile(r'^[*_]*(?:class|cause|fix|where|scenario|evidence|impact|likelihood|why|repro\w*|steps|tests?|location|'
                    r'files?|severity|grade|status|details?)[*_]*\s*:', re.I)
LOOKS = re.compile(r'\[(?:Blocker|Major|Minor)\]|(?<!non-)(?<!non)\b(?:new\s+)?(?:blocker|blocking)\b(?!\s*:\s*none)', re.I)
STATUS = re.compile(r'\b(not\s+(?:yet\s+)?fixed|unfixed|unchanged|partly|partially|partial|incomplete|rejected|withdrawn|'
                    r'fixed)\b', re.I)
VERDICT_STATE = {'not fixed': 'unchanged', 'partly': 'updated', 'fixed': 'absent', 'rejected': 'absent'}
INTRODUCED = re.compile(r'\bintroduced by (?:the|this) fix\b|\bfix[- ]introduced\b', re.I)
REF = re.compile(r'\b(?:([BFc])(\d+)|(?:findings?|#)\s*(\d+(?:\s*(?:,|and|&)\s*\d+)*))\b', re.I)
SAME_KIND = re.compile(r'^[#*_\s]*same\s+kind\b[^:]*(?::[*_]*\s*(.*))?$', re.I)
BRIEF_LABELS = (('accepted', ('ACCEPTED', 'FIX THESE')), ('rejected', ('REJECTED', 'NOT TO CHANGE')),
                ('recorded', ('RECORDED', 'RECORD ONLY')))
BRIEF_END = re.compile(r"^[*_#\s]*(?:[A-Z]{2,}(?:[ '-]+[A-Z]{2,})+\b|[A-Z]{3,}\s*(?:\([^)]*\))?\s*[:,]|(?i:for each finding)\b)")
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
    return (m.group(1), int(m.group(2))) if m else (None, None)


def plain(text):
    """The text without Markdown emphasis markers, so tags wrapped in ** or __ still read."""
    return re.sub(r'(?<!\w)_{1,3}|_{1,3}(?!\w)', '', re.sub(r'\*+', '', text or ''))


def class_label(c):
    """Only the class label: the rest of its sentence (location, explanation) is cut."""
    c = plain(c).strip(' `')
    cut = [m.start() for m in (PATH_LINE.search(c), re.search(r'\[|\s\(|\s[—–-]\s|[.;](?:\s|$)|,\s(?:see|at|in)\b', c)) if m]
    c = c[:min(cut)] if cut else c
    return c.strip(' .;:,`').lower() or None


def tags(text):
    """(cause, class, area, likelihood, impact, grade) read with mine.py's readers."""
    text = plain(text)
    lines = text.splitlines()
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
    return (cause, cls and class_label(cls), r and r.group(1), r and f'L{r.group(2)}',
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
    """The re-review's verdict on a carried finding: its first status word (fixed, partly, not fixed, rejected), else None."""
    m = STATUS.search((text or '')[:300])
    if not m:
        return None
    w = re.sub(r'\s+', ' ', m.group(1).lower())
    if w.startswith('not') or w in ('unfixed', 'unchanged'):
        return 'not fixed'
    if w in ('rejected', 'withdrawn'):
        return 'rejected'
    return 'fixed' if w == 'fixed' else 'partly'


def is_blocking(text, section, grade, status):
    low = (text or '')[:400].lower()
    if section in PREFIX or section == 'same-kind':
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


def title_cell(cells, header):
    """The finding's title in a table row: its Finding / Issue / Vulnerability column, else its longest prose cell."""
    for name in ('finding', 'issue', 'vulnerability', 'title', 'summary', 'description', 'problem', 'earlier finding'):
        if header and name in header:
            k = header.index(name)
            if k < len(cells) and cells[k]:
                return cells[k]
    prose = [c for c in cells if not re.fullmatch(r'[\d\W]*|[A-Z]+|blocking|non-?blocking', c, re.I)]
    return max(prose, key=len) if prose else None


def label_item(m, section, rereview, counters):
    """(label, section, ref) for a labelled item: ref is the earlier review's finding a re-review item names."""
    pre, n, body = m.group('pre'), m.group('pn') or m.group('num'), m.group('body')
    if pre == 'M':
        counters['minor'] = max(counters['minor'], int(n))
        return 'm' + n, 'minor', None
    sec = section if section not in ('skip', None) else 'blocking'
    if rereview and sec == 'blocking':
        if pre == 'c' or (pre is None and m.group('rn') is None):
            return 'c' + n, sec, None
        if m.group('rn'):
            return 'c' + n, sec, ('F' if m.group('rp') == 'F' else '') + m.group('rn')
        if STATUS.search(body[:120]):
            return 'c' + n, sec, ('F' if pre == 'F' else '') + n
        return ('F' + n if pre == 'F' else n), 'new', None
    if pre == 'F':
        return 'F' + n, sec, None
    if pre == 'c':
        return 'c' + n, sec, None
    return n, sec, None


def split(report, rereview=False, dropped=None):
    """Findings in a review report: (label, text, section) per numbered item, table row or tagged paragraph.

    Finding-like lines no finding takes in (outside skipped sections) are appended to `dropped` as (line, text)."""
    out, cur, section, counters = [], None, None, collections.Counter()
    fenced, table, header, gap = False, None, None, False

    def close():
        if not cur:
            return
        same = next((o for o in out if o['label'] == cur['label'] and o['section'] == cur['section']), None)
        if same:
            same['text'] += '\n' + cur['text']
        elif not OPTIONS.match(cur['text']):
            out.append(cur)
    for i, raw in enumerate((report or '').splitlines(), 1):
        s = raw.strip()
        if s.startswith(('```', '~~~')):
            fenced = not fenced
            continue
        if fenced:
            continue
        if not s:
            gap = gap or cur is not None
            continue
        m = ITEM.match(s) if not raw[:1].isspace() else None
        heading = bool(m) and s.startswith(('#', '**', '__'))
        if m and heading and section_of('# ' + m.group('body')) not in ('skip', None):
            m, heading = None, False
        sec = None if m else section_of(s)
        if sec:
            close()
            cur, section, gap = None, sec, False
            continue
        if cur is not None and gap and not m and not (cur.get('heading') or raw[:1].isspace() or DETAIL.match(s)):
            close()
            cur = None
        gap = False
        t = TABLE_N.match(s)
        num_from_table = None
        if s.startswith('|'):
            cells = [c.strip().strip('*_` ') for c in s.strip('|').split('|')]
            low = [c.lower() for c in cells]
            if all(re.fullmatch(r':?-+:?', c) for c in cells if c):
                continue
            if any(c in ('#', 'finding', 'severity', 'vulnerability', 'issue', 'earlier finding') for c in low) and not t:
                close()
                cur, table, header = None, 0, low
                continue
            if table is not None and not t:
                table += 1
                t = re.match(r'^()', s)
                num_from_table = str(table)
        else:
            table = None
        tagged = (section in PREFIX or section in ('blocking', 'new')) and (mine.GRADED_TAG.search(plain(s)) or RUBRIC.search(plain(s))) \
            and not m and not t and not raw[:1].isspace()
        tagged = tagged or (section == 'correction' and s and not m and not s.startswith('|'))
        if section == 'skip' and not (m and m.group('pre') in ('B', 'M')):
            if cur and s:
                cur['text'] += '\n' + s
            continue
        if m or t or tagged:
            close()
            ref = None
            if t:
                num, body = (num_from_table or t.group(1)), s
                sec = section or 'blocking'
                label = PREFIX[sec] + num if sec in PREFIX else (('c' + num) if rereview and sec == 'blocking' else num)
            elif m:
                label, sec, ref = label_item(m, section, rereview, counters)
                body = m.group('body')
                if sec in PREFIX and not label.startswith(PREFIX[sec]):
                    counters[sec] += 1
                    label = PREFIX[sec] + str(counters[sec])
            else:
                sec, body = section or 'blocking', s
                if sec in PREFIX:
                    counters[sec] += 1
                    label = PREFIX[sec] + str(counters[sec])
                else:
                    label = 'b' + str(len(out) + 1)
            cur = {'label': label, 'text': body, 'section': sec, 'ref': ref, 'heading': heading, 'line': i}
            if t:
                cur['title'] = title_cell([c.strip().strip('*_` ') for c in s.strip('|').split('|')], header)
            continue
        if cur is not None:
            cur['text'] += '\n' + s
        elif dropped is not None and (mine.GRADED_TAG.search(plain(s)) or RUBRIC.search(plain(s)) or LOOKS.search(plain(s))) \
                and not mine.VERDICT.match(plain(s).lstrip('# ').strip()):
            dropped.append((i, s))
    close()
    return out


def same_kind(report):
    """The items of a fix report's "Same kind, not fixed" list, each as a finding of section same-kind."""
    out, on, gap = [], False, False
    for i, raw in enumerate((report or '').splitlines(), 1):
        s = raw.strip()
        m = SAME_KIND.match(s) if not on else None
        if m:
            on, gap = True, False
            rest = (m.group(1) or '').strip(' *_')
            if rest and not re.match(r'none\b', rest, re.I):
                out.append({'label': 's' + str(len(out) + 1), 'text': rest, 'section': 'same-kind', 'line': i})
            continue
        if not on:
            continue
        if not s:
            gap = True
            continue
        if s.startswith('#') or (section_of(s) and not mine.LIST_ITEM.match(s)):
            break
        if mine.LIST_ITEM.match(s) and not raw[:1].isspace():
            item = re.sub(r'^(?:[-*+]|\d+[.)])\s+', '', s)
            if not re.match(r'none\b', item, re.I):
                out.append({'label': 's' + str(len(out) + 1), 'text': item, 'section': 'same-kind', 'line': i})
        elif out and (raw[:1].isspace() or not gap):
            out[-1]['text'] += '\n' + s
        else:
            break
        gap = False
    return out


def parse(report, rereview=False, dropped=None, fix=False):
    found = []
    for f in (same_kind(report) if fix else split(report, rereview, dropped)):
        cause, cls, area, lik, imp, grade = tags(f['text'])
        if cause is None:
            cells = [c.strip().strip('*_`') for c in f['text'].split('|')]
            cause = next((c.upper() for c in cells if c.upper() in mine.CAUSES), None)
        if grade is None and f['section'] in ('minor',):
            grade = 'Minor'
        path, line = first_location(f['text'])
        verdict = status_of(f['text']) if f['label'].startswith('c') else None
        status = VERDICT_STATE.get(verdict)
        found.append({'n': f['label'], 'section': f['section'], 'title': f.get('title') or title_of(f['text']),
                      'text': f['text'], 'cause': cause, 'class': cls, 'area': area, 'likelihood': lik, 'impact': imp,
                      'grade': grade, 'file': path, 'line': line, 'status': status, 'verdict': verdict,
                      'ref': f.get('ref'), 'blocking': bool(is_blocking(f['text'], f['section'], grade, status))})
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


def match(items, findings, floor=0.25, hint=None, margin=None, ambiguous=None):
    """Greedy one-to-one pairs (item index, finding index) by shared words and files, best first.

    With a margin, an item whose best free finding is within the margin of another free one is left unpaired and
    appended to `ambiguous` as (item index, [finding indexes])."""
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
    for neg, i, j in sorted(scored):
        if i not in used_i and j not in used_j:
            if margin is not None:
                close = [jj for s2, ii, jj in scored if ii == i and jj != j and jj not in used_j and -s2 >= -neg - margin]
                if close:
                    used_i.add(i)
                    if ambiguous is not None:
                        ambiguous.append((i, [j] + close))
                    continue
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


def pieces(text):
    """A ruling paragraph cut into its items: at a top-level ";" or sentence end, never inside () or backticks."""
    out, cur, depth, tick = [], '', 0, False
    for k, ch in enumerate(text):
        if ch == '`':
            tick = not tick
        elif not tick and ch == '(':
            depth += 1
        elif not tick and ch == ')':
            depth = max(0, depth - 1)
        end = not tick and depth == 0 and (ch == ';' or (ch == '.' and re.match(r'\s+[A-Z`]', text[k + 1:k + 3] or '')))
        cur += ch
        if end:
            out.append(cur)
            cur = ''
    out.append(cur)
    return [x.strip(' ;') for x in out if x.strip(' ;.') and not re.match(r'^none\b', x.strip().lower())]


def brief_label(line):
    up = line.strip().lstrip('*_#').strip().upper()
    return next((key for key, words in BRIEF_LABELS if up.startswith(words)), None)


def list_after(lines, i):
    """A label line's items, up to the next label: its list items (blank lines between them allowed), else its
    paragraph cut into items."""
    line = lines[i]
    head = re.sub(r'^[^:(]*(?:\([^)]*\))?[^:]*:', '', line, count=1).strip(' *_') if ':' in line else ''
    items, para, gap = [], [head] if head else [], False
    for nxt in lines[i + 1:]:
        s = nxt.strip()
        if not s:
            gap = True
            continue
        if brief_label(nxt) or (not nxt[:1].isspace() and (BRIEF_END.match(nxt) or s.startswith('#'))
                                and not mine.LIST_ITEM.match(s)):
            break
        if mine.LIST_ITEM.match(s) and not nxt[:1].isspace():
            items.append(s)
        elif items and (nxt[:1].isspace() or not gap):
            items[-1] += ' ' + s
        elif items or (para and gap):
            break
        else:
            para.append(s)
        gap = False
    if items:
        return items
    return pieces(' '.join(para).strip())


def brief(run, fix_name):
    """{'accepted': [...], 'rejected': [...], 'recorded': [...], 'qualifier': {...}} from a fix round's brief, or None."""
    for fn in (fix_name + '.md', fix_name + '.prompt.md', fix_name + '.body.md'):
        try:
            with open(os.path.join(run, fn), encoding='utf-8', errors='replace') as f:
                lines = re.split(r'(?m)^==== ORIGINAL TASK ====\s*$', f.read())[0].splitlines()
        except OSError:
            continue
        out = {'accepted': [], 'rejected': [], 'recorded': [], 'qualifier': {}}
        seen = False
        for i, line in enumerate(lines):
            key = brief_label(line)
            if not key:
                continue
            out[key] += list_after(lines, i)
            q = re.match(r'^[^:(]*\(([^)]*)\)', line)
            if q:
                out['qualifier'][key] = q.group(1)
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


def refs(text):
    """Finding labels a ruling names explicitly (B1 -> 1, c3, F2, "finding 2"), its own list number left out."""
    body = re.sub(r'^\s*(?:[-*+]|\d+[.)])\s+', '', text or '')
    out = []
    for m in REF.finditer(body):
        if m.group(1):
            out.append({'b': '', 'f': 'F', 'c': 'c'}[m.group(1).lower()] + m.group(2))
        else:
            out += re.findall(r'\d+', m.group(3))
    return out


def defect_fp(item, f):
    folder = os.path.dirname(f['file']) if f['file'] else ''
    key = '\x1f'.join([item, f['file'] or '', folder, f['cause'] or '', f['class'] or ''])
    return hashlib.sha256(key.encode('utf-8')).hexdigest()[:16], folder or None


def report_of(run, r):
    """(text, file it came from): the round's last message, else <name>.txt, else its .jsonl message."""
    if r.get('report'):
        return r['report'], r['name'] + '.jsonl'
    try:
        with open(os.path.join(run, r['name'] + '.txt'), encoding='utf-8', errors='replace') as f:
            return f.read(), r['name'] + '.txt'
    except OSError:
        pass
    msg = fix_message(run, r['name'])
    return msg, r['name'] + '.jsonl'


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
        kind = 'critique' if CRITIQUE.search(r['name']) else ('fix' if is_fix(r) else r['kind'])
        by_item.setdefault(CRITIQUE.sub('', r['name']) if kind == 'critique' else r['item'], []).append(dict(r, kind=kind))
    obs, unparsed, reviews, ambiguous = [], [], 0, []
    defects = collections.OrderedDict()

    def observe(f, r, item, fp_seen, next_fix, prev_fix, link=None):
        fp, folder = defect_fp(item, f)
        f['code_area'] = folder
        o = {'f': f, 'round': r, 'item': item, 'fp': fp, 'rulings': [], 'next_fix': next_fix}
        if link:
            o['defect'] = link['defect']
            o['state'] = f['status'] or 'unchanged'
            link['carried_by'], link['carried_verdict'], link['carried_text'] = r['name'], f['verdict'], f['text']
        else:
            fp_seen[fp] += 1
            k = fp_seen[fp]
            did = f'{fp}/{k}'
            while did in defects:
                k += 1
                did = f'{fp}/{k}'
            o['defect'] = did
            o['state'] = 'new'
            introduced = r['kind'] == 'rereview' and prev_fix and f['cause'] != 'PRE' and \
                (f['section'] == 'new' or INTRODUCED.search(f['text']))
            o['introduced_by'] = prev_fix['name'] if introduced else None
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
        return o

    for item, rs in by_item.items():
        rs.sort(key=lambda x: (x['start'], x['name']))
        open_obs = []
        for idx, r in enumerate(rs):
            prev_fix = next((x for x in reversed(rs[:idx]) if is_fix(x)), None)
            next_fix = next((x for x in rs[idx + 1:] if is_fix(x)), None)
            if r['kind'] == 'fix':
                report, _ = report_of(run, r)
                fp_seen = collections.Counter()
                for f in parse(report, fix=True):
                    observe(f, r, item, fp_seen, next_fix, prev_fix)
                continue
            if r['kind'] not in mine.REVIEW_KINDS + ('critique',):
                continue
            reviews += 1
            report, source = report_of(run, r)
            dropped = []
            found = parse(report, r['kind'] == 'rereview', dropped)
            numbered = {f['n'] for f in found}
            for (rnd, n), row in rulings.items():
                if rnd == r['name'] and n not in numbered:
                    found.append({'n': n, 'section': 'blocking', 'title': f"finding {n} of {rnd} (from rulings.jsonl)",
                                  'text': row.get('reason') or '', 'cause': None, 'class': None,
                                  'area': row.get('area'), 'likelihood': None, 'impact': None, 'grade': row.get('grade'),
                                  'file': None, 'line': None, 'status': None, 'verdict': None, 'ref': None,
                                  'blocking': row.get('grade') in ('Blocker', 'Major'), 'ruling_only': True})
            if not found and (r.get('blocking') or 0) > 0:
                unparsed.append({'round': r['name'], 'file': source,
                                 'line': 1, 'why': f"verdict says {r['blocking']} blocking but no finding was split out"})
            elif (r.get('blocking') or 0) > 0 and not any(f['blocking'] for f in found):
                # Tables graded only by severity (CRITICAL, HIGH, MEDIUM): the verdict's count marks the first rows.
                for f in [f for f in found if f['section'] in ('blocking', 'new')
                          and not re.search(r'non-?\s?blocking', f['text'], re.I)][:r['blocking']]:
                    f['blocking'], f['blocking_from'] = True, 'verdict'
            elif found and (r.get('blocking') or 0) > sum(1 for f in found if f['blocking']):
                unparsed.append({'round': r['name'], 'file': source, 'line': 1,
                                 'why': f"verdict says {r['blocking']} blocking but only "
                                        f"{sum(1 for f in found if f['blocking'])} blocking findings were split out"})
            for line, text in dropped:
                unparsed.append({'round': r['name'], 'file': source, 'line': line,
                                 'why': f'finding-like line not taken into any finding: {text[:80]}'})
            prev_brief = brief(run, prev_fix['name']) if prev_fix else None
            carried = [f for f in found if f['n'].startswith('c')]
            links = {}
            if carried and open_obs:
                targets = list(open_obs)
                for f in carried:
                    named = [o for o in targets if f['ref'] and o['f']['n'] == f['ref']
                             and all(o is not v for v in links.values())]
                    if named:
                        links[id(f)] = named[-1]
                accepted = (prev_brief or {}).get('accepted') or []
                if accepted and len(accepted) >= len(carried):
                    pairs = match(accepted, [o['f'] for o in targets], floor=0.2)
                    by_brief = {i: j for i, j in pairs}
                    for f in carried:
                        k = int(f['n'][1:]) - 1 if f['n'][1:].isdigit() else -1
                        if id(f) not in links and k in by_brief and all(targets[by_brief[k]] is not v for v in links.values()):
                            links[id(f)] = targets[by_brief[k]]
                rest = [f for f in carried if id(f) not in links]
                free = [o for o in targets if all(o is not v for v in links.values())]
                for i, j in match([f['text'] for f in rest], [o['f'] for o in free], floor=0.2,
                                  hint=lambda i, j: rest[i]['n'][1:] == free[j]['f']['n']):
                    links[id(rest[i])] = free[j]
            fp_seen = collections.Counter()
            this = [observe(f, r, item, fp_seen, next_fix, prev_fix, links.get(id(f))) for f in found]
            open_obs = [o for o in open_obs if o.get('carried_by') is None] + this
            rule(run, r, this, rulings, next_fix, ambiguous)
    for o in obs:
        verdict = o.get('carried_verdict')
        if o.get('carried_by') and verdict in ('fixed', 'partly', 'not fixed'):
            o['rulings'].append({'ruling': 'accepted', 'reason': None, 'source': 'rereview',
                                 'evidence': f"{o['carried_by']}: {verdict}"})
        elif o.get('carried_by') and verdict == 'rejected':
            o['rulings'].append({'ruling': 'rejected', 'reason': reason_of(o['carried_text']), 'source': 'rereview',
                                 'evidence': f"{o['carried_by']}: {o['carried_text'][:180]}"})
    results = [result(run_name, o) for o in obs]
    # SARIF 2.1.0 section 3.27.23: within a run, every result carries suppressions or none does.
    if any('suppressions' in x for x in results):
        for x in results:
            x.setdefault('suppressions', [])
    for a in ambiguous:
        unparsed.append(a)
    return results, list(defects.values()), {'reviews': reviews, 'findings': len(results), 'defects': len(defects),
                                             'unparsed': len({u['round'] for u in unparsed if u.get('kind') != 'ambiguous'}),
                                             'ambiguous': len(ambiguous)}, unparsed


def rule(run, r, this, rulings, next_fix, ambiguous=None):
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
        by_n = {f['n']: j for j, f in enumerate(fs)}
        lists = (('accepted', 'fix-brief-accepted'), ('rejected', 'fix-brief-rejected'), ('recorded', 'fix-brief-recorded'))

        def give(key, source, text, j):
            if key == 'accepted':
                ruling = {'ruling': 'accepted', 'reason': None}
            elif key == 'recorded':
                ruling = {'ruling': 'demoted', 'reason': None}
            else:
                reason = reason_of(text)
                if reason == 'unclear' and b['qualifier'].get(key):
                    reason = reason_of(b['qualifier'][key])
                ruling = {'ruling': 'rejected', 'reason': reason}
            this[j]['rulings'].append(dict(ruling, source=source, evidence=text[:200]))
        named, rest = set(), {}
        for key, source in lists:
            for i, text in enumerate(b[key]):
                js = [by_n[x] for x in refs(text) if x in by_n]
                for j in js:
                    give(key, source, text, j)
                    named.add(j)
                if not js:
                    rest.setdefault(key, []).append(text)
        free = [j for j in range(len(fs)) if j not in named]
        for key, source in lists:
            items, amb = rest.get(key, []), []
            for i, jj in match(items, [fs[j] for j in free], margin=0.05, ambiguous=amb):
                give(key, source, items[i], free[jj])
            for i, js in amb:
                if ambiguous is not None:
                    ambiguous.append({'kind': 'ambiguous', 'round': r['name'], 'file': next_fix['name'] + ' brief',
                                      'line': 0, 'why': f"{key} item {items[i][:60]!r} fits findings "
                                      + ', '.join(fs[free[j]]['n'] for j in js) + ' equally; left unruled'})
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
                                                                       ('pre' if f['section'] == 'pre' else
                                                                        'same-kind' if f['section'] == 'same-kind' else 'new')),
             'rereviewVerdict': f.get('verdict'),
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
        if u.get('kind') == 'ambiguous':
            lines.append(f"  ambiguous ruling: {u['round']}: {u['why']}")
        else:
            lines.append(f"  not parsed: {u['file']} line {u['line']}: {u['why']}")
    return '\n'.join(lines), counts
