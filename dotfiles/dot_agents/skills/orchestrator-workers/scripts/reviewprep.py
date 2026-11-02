#!/usr/bin/env python3
"""Write one item's review inputs, so a review or re-check launches without the chat.

Usage:
    python3 reviewprep.py review <item> --worktree DIR [--run-dir RUN] [--brief FILE] [--report ROUND]
    python3 reviewprep.py recheck <item> --worktree DIR [--run-dir RUN] [--brief FILE] [--report ROUND]
    python3 reviewprep.py --help

review: writes REVIEW-DIFF.patch (`git diff <base>...HEAD`; base from <run>/<item>.reviewbase, else --base (the
queue runner passes the build step's HEAD at its first launch, which a retry keeps), else <item>.base, which
route.py run rewrites at every launch) and REVIEW-REPORT.md (the build's last message, from result.py on the newest
of <item>.jsonl and its resume rounds' <item>-resumeN.jsonl, or --report's) into the worktree, uncommitted, and
fills assets/review.md into <run>/<item>-review.md: the task from the build's brief (--brief, else
<item>.prompt.md, else <item>.body.md), cut to <item>.body.md when the brief holds it, one risk block per name on
its RISK line (from the menu in review.md's own comment), prior rulings from <item>.rulings.md, project rules from
<item>.security.md or security.md.
recheck: writes the fix diff (`git diff <base>..HEAD`, base from --base, else <item>-fix1.base) and the fix report,
and fills assets/rereview.md into <run>/<item>-rereview.md from the numbered findings under "FIX THESE" in the fix
brief (--brief, else <item>-fix1.prompt.md, else <item>-fix1.body.md), up to the next section heading.
Placeholders are filled in one pass over the template, so inserted text is never read as one. {{RUBRIC}} is left
for review.sh. Exit 2, with the reason and nothing launched, when a base is missing or unknown to git, the diff is
empty, a report or findings are missing, or a placeholder stays.
"""
import argparse, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, '..', 'assets')
RISKS = {
    'Trust boundaries': r'trust|boundar',
    'Durable data': r'data|durable',
    'Processes': r'process',
    'Turn and state handling': r'turn|host-state|state handling|event order',
    'Credentials and privacy': r'credential|privacy|secret',
    'The checks themselves': r'checks?$|checks? ',
    'Paid calls': r'paid|spend',
}
FIX_ROUND = '-fix1'


class PrepError(Exception):
    pass


def read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def first(*paths):
    return next((p for p in paths if os.path.isfile(p)), None)


def write(path, text):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(text)
    os.replace(tmp, path)


def git(wt, *args):
    p = subprocess.run(['git', '-C', wt, *args], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if p.returncode:
        raise PrepError(f"git {' '.join(args)} failed in {wt}: {p.stderr.strip()[:200]}")
    return p.stdout


def base_of(rd, wt, names, head=None):
    """The first named file's commit, else head (the step's HEAD at its first launch), else the last named file's."""
    path = first(*(os.path.join(rd, n) for n in names[:-1]))
    if not path and head:
        base = head
    else:
        path = path or first(os.path.join(rd, names[-1]))
        if not path:
            raise PrepError(f"no {' or '.join(names)} in {rd}")
        base = read(path).strip()
        if not base:
            raise PrepError(f'{os.path.basename(path)} is empty')
    git(wt, 'rev-parse', '--verify', '--quiet', base + '^{commit}')
    return base


def report(rd, rnd, named=None):
    """The final report of the round named (a resume round passed with `retry --passed`), else of whichever of <rnd>
    and its resume rounds <rnd>-resumeN wrote its log last."""
    if not named:
        logs = [(os.path.getmtime(os.path.join(rd, f)), int(m.group(1) or 0), m.group(0)[:-6]) for f in os.listdir(rd)
                for m in [re.fullmatch(re.escape(rnd) + r'(?:-resume(\d+))?\.jsonl', f)] if m]
        named = max(logs)[2] if logs else rnd
    rnd = named
    path = os.path.join(rd, rnd + '.jsonl')
    if not os.path.isfile(path):
        raise PrepError(f'no {rnd}.jsonl for the report')
    out = subprocess.run([sys.executable, '-B', os.path.join(HERE, 'result.py'), path],
                         capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
    body = out.split('\n' + '-' * 20 + '\n', 1)
    if len(body) < 2 or not body[1].strip() or body[1].strip() == 'NO assistant.message':
        raise PrepError(f'{rnd}.jsonl has no final report')
    return body[1]


def strip_head(text):
    return re.sub(r'\A<!--.*?-->\n', '', text, flags=re.S)


def fill(text, fills):
    """Fill the template's {{NAME}} and {{NAME|default}} in one pass, so inserted text is never read as a placeholder."""
    left = set()

    def one(m):
        whole, name, default = m.group(1), m.group(2), m.group(3)
        for key in (whole, name):
            if key in fills:
                return fills[key]
        if default is not None:
            return default
        if name != 'RUBRIC':
            left.add(whole)
        return m.group(0)
    text = re.sub(r'\{\{(([^}|]+)(?:\|([^}]*))?)\}\}', one, text)
    if left:
        raise PrepError(f"unfilled placeholders: {' '.join(sorted(left))}")
    return text


def risk_blocks(template, body):
    """One block of review.md's risk menu per name on the brief's RISK line; a name the menu lacks is kept as is."""
    menu = {}
    head = re.match(r'\A<!--(.*?)-->', template, re.S)
    for m in re.finditer(r'^- ([^:\n]+): (.+?)(?=^- |\Z)', head.group(1).split('from this menu:', 1)[-1] if head else '',
                         re.M | re.S):
        menu[m.group(1).strip()] = f"- {m.group(1).strip()}: {' '.join(m.group(2).split())}"
    line = re.search(r'^RISK:(.*)$', body, re.M)
    if not line:
        return ''
    names = [n.strip(' .;') for n in re.sub(r'\([^)]*\)', '', line.group(1)).split(',')]
    out = []
    for n in names:
        if not n or n.lower() == 'none':
            continue
        label = next((lab for lab, pat in RISKS.items() if re.search(pat, n.lower())), None)
        block = menu.get(label) if label else None
        if label and not block:
            raise PrepError(f'review.md has no "{label}" block in its risk menu')
        if block and block not in out:
            out.append(block)
        elif not block:
            out.append(f'- {n}: the task names this risk; check it.')
    return '\n'.join(out)


def task_text(rd, rnd, brief=None):
    """The brief the round was launched with, or only its task when <rnd>.body.md is inside it: a body.md the brief
    does not hold is stale. Without a brief, <rnd>.prompt.md, else <rnd>.body.md."""
    body = first(os.path.join(rd, rnd + '.body.md'))
    path = brief or first(os.path.join(rd, rnd + '.prompt.md'))
    if not path or not os.path.isfile(path):
        if brief:
            raise PrepError(f'no brief at {brief}')
        if not body:
            raise PrepError(f'no {rnd}.body.md or {rnd}.prompt.md for the task')
        return read(body)
    text = read(path)
    if body and read(body).strip() and read(body).strip() in text:
        return read(body)
    return text


def review(rd, item, wt, head=None, brief=None, report_round=None):
    base = base_of(rd, wt, [item + '.reviewbase', item + '.base'], head)
    diff = git(wt, 'diff', f'{base}...HEAD')
    if not diff.strip():
        raise PrepError(f'empty diff from {base[:12]} to HEAD; nothing to review')
    body, rep = task_text(rd, item, brief), report(rd, item, report_round)
    template = read(os.path.join(ASSETS, 'review.md'))
    commits = git(wt, 'log', '--format=%h %s', f'{base}..HEAD').strip().replace('\n', '; ')
    branch = git(wt, 'rev-parse', '--abbrev-ref', 'HEAD').strip()
    rulings = first(os.path.join(rd, item + '.rulings.md'))
    security = first(os.path.join(rd, item + '.security.md'), os.path.join(rd, 'security.md'))
    text = fill(strip_head(template), {
        'TASK': body.strip(),
        'GATES_RUN': f'see the gates section of REVIEW-REPORT.md (branch `{branch}`, base {base}, commits: {commits})',
        'PRIOR_RULINGS|none': read(rulings).strip() if rulings else 'none',
        'PROJECT_SECURITY_SECTIONS': read(security).strip() if security else '',
        'RISK_CHECKS_OR_DELETE': risk_blocks(template, body),
        'FOCUS_AREAS_OR_DELETE': '',
        'BLOCKING_RULE_SOURCE': 'owner, 2026-10-30, the rubric above',
    })
    write(os.path.join(wt, 'REVIEW-DIFF.patch'), diff)
    write(os.path.join(wt, 'REVIEW-REPORT.md'), rep)
    out = os.path.join(rd, item + '-review.md')
    write(out, text)
    return out


HEADING = re.compile(r'#|[A-Z]{3,}(?:[ -][A-Z]+)*(?=[\s:,(]|$)|\S.*:$')


def findings(text):
    """(number, title, where, done when) for each numbered finding under the fix brief's "FIX THESE" line, up to
    the next section heading (an unindented capitalised label such as NOT TO CHANGE, or a line ending in a colon);
    blank lines do not end the list."""
    head = re.search(r'^FIX THESE[^\n]*\n', text, re.M)
    if not head:
        return []
    found = []
    for line in text[head.end():].splitlines():
        num = re.match(r'(\d+)\. (.+)', line)
        if num:
            found.append([num.group(1), num.group(2)])
        elif line.strip() and not line[0].isspace() and HEADING.match(line):
            break
        elif line.strip() and found:
            found[-1][1] += ' ' + line
    out = []
    for n, f in found:
        f = ' '.join(f.split())
        where = re.search(r'Where: (.+?)\.(?: What goes wrong:| Done when:|$)', f)
        done = re.search(r'Done when: (.+?)(?: Cases:|$)', f)
        title = re.split(r'\.? Where: ', f, maxsplit=1)[0].rstrip('.')
        out.append((n, title, where.group(1) if where else 'see the fix brief',
                    done.group(1).rstrip('.') if done else 'see the fix brief'))
    return out


def recheck(rd, item, wt, head=None, brief=None, report_round=None):
    fix = item + FIX_ROUND
    base = base_of(rd, wt, [fix + '.base'], head)
    diff = git(wt, 'diff', f'{base}..HEAD')
    if not diff.strip():
        raise PrepError(f'empty diff from {base[:12]} to HEAD; the fix round committed nothing')
    found = findings(task_text(rd, fix, brief))
    if not found:
        raise PrepError(f'no numbered findings under "FIX THESE" in the {fix} brief')
    rep = report(rd, fix, report_round)
    commits = git(wt, 'log', '--format=%h %s', f'{base}..HEAD').strip().replace('\n', '; ')
    n1, t1, w1, d1 = found[0]
    text = fill(strip_head(read(os.path.join(ASSETS, 'rereview.md'))), {
        'FINDING_1': t1, 'FILE_LINE_1': w1, 'DONE_WHEN_1': d1,
        'MORE_FINDINGS': '\n'.join(f'{n}. {t}. Where: {w}. Done when: {d}.' for n, t, w, d in found[1:]),
        'FIX_COMMITS': commits, 'BRANCH': git(wt, 'rev-parse', '--abbrev-ref', 'HEAD').strip(),
    })
    if n1 != '1':
        text = text.replace('\n1. ' + t1, f'\n{n1}. ' + t1, 1)
    write(os.path.join(wt, 'REVIEW-DIFF.patch'), diff)
    write(os.path.join(wt, 'REVIEW-REPORT.md'), rep)
    out = os.path.join(rd, item + '-rereview.md')
    write(out, text)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write an item's review or re-check prompt and inputs.")
    ap.add_argument('kind', choices=('review', 'recheck'))
    ap.add_argument('item')
    ap.add_argument('--worktree', required=True, help="the item's worktree")
    ap.add_argument('--run-dir', help='run folder (default: $OW_RUN_DIR)')
    ap.add_argument('--base', help='commit the diff starts from, unless <item>.reviewbase exists')
    ap.add_argument('--brief', help='the brief the build (or fix) round was launched with')
    ap.add_argument('--report', help='round whose final report to use (a resume round)')
    a = ap.parse_args(argv)
    rd = os.path.abspath(os.path.expanduser(a.run_dir or os.environ.get('OW_RUN_DIR') or '.'))
    try:
        out = (review if a.kind == 'review' else recheck)(rd, a.item, os.path.abspath(os.path.expanduser(a.worktree)),
                                                          a.base, a.brief and os.path.abspath(os.path.expanduser(a.brief)),
                                                          a.report)
    except (PrepError, OSError) as ex:
        print(f'reviewprep: {ex}', file=sys.stderr)
        return 2
    print(out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
