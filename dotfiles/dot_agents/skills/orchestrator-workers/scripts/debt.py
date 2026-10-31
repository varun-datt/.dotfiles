#!/usr/bin/env python3
"""Keeper of a repository's tech-debt register, <repo>/docs/tech-debt.md: known findings that did not block a merge.

Usage:
    python3 debt.py add <repo> --area A --grade Major|Minor --file PATH --scenario "one line" --source ROUND --minutes N
    python3 debt.py list <repo> [--open|--all]                 the table's rows (default: open ones)
    python3 debt.py close <repo> TD-<n> --reason "one line"     mark a row closed; it is never deleted
    python3 debt.py for-files <repo> PATH ...                   open rows on these files or under these folders,
                                                                as lines a brief pastes under a heading
    python3 debt.py stale <repo> --runs FILE [--threshold 3]    open rows with THRESHOLD or more runs since their date
    python3 debt.py import-plan PLAN.md --dry-run [--counts]    rows a PLAN.md's "Known gaps" passages would give,
                                                                by item number (a column-0 "N."), or "?" under a bullet

The register is a markdown table; text outside the table is kept as written. Ids are TD-<n>, one above the
highest ever used (a `<!-- debt.py next id: n -->` line after the table remembers it if a row is deleted by hand).
A run, for `stale`, is a line of FILE that starts with its date (YYYY-MM-DD); a row's runs are those dated
after the row. Every write replaces the file whole under a lock on docs/.
"""
import argparse, contextlib, datetime, fcntl, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from state import Refused, one_line, regular_or_absent, write_atomic  # noqa: E402

REGISTER = os.path.join('docs', 'tech-debt.md')
GRADES = ('Major', 'Minor')
COLUMNS = ('Id', 'Date', 'Area', 'Grade', 'File', 'Scenario', 'Source', 'Minutes', 'Status')
HEADER = re.compile(r'^\|\s*Id\s*\|\s*Date\s*\|')
NEXT = re.compile(r'^<!-- debt\.py next id: (\d+) -->$')
ROW_ID = re.compile(r'^TD-(\d+)$')
DATE = re.compile(r'^(\d{4}-\d{2}-\d{2})\b')
CELL_SPLIT = re.compile(r'(?<!\\)\|')
TITLE = """# Tech debt

Known findings that did not block a merge, kept by `debt.py` (the orchestrator-workers skill). A brief that touches a listed file names its rows and fixes those under about 15 minutes; a class seen 3 times becomes a planned item; past about 30 open rows, each run plans one debt item; a row untouched for 3 runs is re-graded. Edit text outside the table freely.

"""


def today():
    return datetime.date.today().isoformat()


def cell(value, what, allow_empty=False):
    text = str(value or '').strip()
    if not text and not allow_empty:
        raise Refused(f'{what} is empty')
    if '\n' in text or '\r' in text:
        raise Refused(f'{what} must be one line')
    if '|' in text:
        raise Refused(f'{what} must not hold a "|", which would break the table')
    return text


def rel_path(repo, path):
    raw = cell(path, '--file')
    if '`' in raw:
        raise Refused('--file must not hold a backtick')
    if os.path.isabs(raw):
        raise Refused(f'--file {raw!r} must be relative to the repository')
    norm = os.path.normpath(raw)
    if norm == '.' or norm == '..' or norm.startswith('..' + os.sep):
        raise Refused(f'--file {raw!r} is not inside the repository')
    return norm


def repo_dir(given):
    repo = os.path.abspath(os.path.expanduser(given))
    if not os.path.isdir(repo):
        raise Refused(f'repository {given!r} is not a folder')
    return repo


@contextlib.contextmanager
def locked(folder):
    fd = os.open(folder, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


class Register:
    def __init__(self, text):
        self.lines, self.next_id = [], 0
        for line in text.splitlines():
            m = NEXT.match(line.strip())
            if m:
                self.next_id = max(self.next_id, int(m.group(1)))
            else:
                self.lines.append(line)
        self.start = next((i for i, line in enumerate(self.lines) if HEADER.match(line)), None)
        self.rows, self.end = [], None
        if self.start is not None:
            i = self.start + 2
            while i < len(self.lines) and self.lines[i].startswith('|'):
                self.rows.append(self.parse(self.lines[i], i + 1))
                i += 1
            self.end = i
        for r in self.rows:
            self.next_id = max(self.next_id, int(ROW_ID.match(r['Id']).group(1)) + 1)
        self.next_id = max(self.next_id, 1)

    @staticmethod
    def parse(line, lineno):
        cells = [c.strip() for c in CELL_SPLIT.split(line.strip())[1:-1]]
        if len(cells) != len(COLUMNS) or not ROW_ID.match(cells[0]):
            raise Refused(f'line {lineno} of the register is not a {len(COLUMNS)}-column row with a TD-<n> id; fix it by hand, then retry')
        return dict(zip(COLUMNS, cells))

    @staticmethod
    def render(row):
        return '| ' + ' | '.join(row[c] for c in COLUMNS) + ' |'

    def text(self):
        table = ['| ' + ' | '.join(COLUMNS) + ' |', '|' + ' --- |' * len(COLUMNS)] + [self.render(r) for r in self.rows]
        marker = f'<!-- debt.py next id: {self.next_id} -->'
        lines = self.lines
        if self.start is None:
            body = lines + ([''] if lines and lines[-1].strip() else []) + table + [marker]
        else:
            body = lines[:self.start] + table + [marker] + lines[self.end:]
        return '\n'.join(body) + '\n'


def read(repo):
    target = os.path.join(repo, REGISTER)
    regular_or_absent(target, 'the register')
    try:
        with open(target, encoding='utf-8') as f:
            return target, f.read()
    except FileNotFoundError:
        return target, None


def change(repo, fn):
    folder = os.path.join(repo, 'docs')
    if os.path.islink(folder) or (os.path.lexists(folder) and not os.path.isdir(folder)):
        raise Refused(f'{folder} is not a folder')
    os.makedirs(folder, exist_ok=True)
    with locked(folder):
        target, text = read(repo)
        reg = Register(TITLE if text is None else text)
        out = fn(reg)
        write_atomic(target, reg.text())
    return out


def is_open(row):
    return row['Status'] == 'open'


def cmd_add(a):
    repo = repo_dir(a.repo)
    fields = {'Area': cell(a.area, '--area'), 'Grade': a.grade, 'File': rel_path(repo, a.file),
              'Scenario': cell(a.scenario, '--scenario'), 'Source': cell(a.source, '--source')}
    if a.minutes < 1:
        raise Refused('--minutes must be 1 or more')

    def add(reg):
        row = {'Id': f'TD-{reg.next_id}', 'Date': today(), **fields, 'Minutes': str(a.minutes), 'Status': 'open'}
        reg.rows.append(row)
        reg.next_id += 1
        return f"added {row['Id']} to {REGISTER}"
    return change(repo, add)


def cmd_list(a):
    _, text = read(repo_dir(a.repo))
    rows = [] if text is None else Register(text).rows
    rows = rows if a.all else [r for r in rows if is_open(r)]
    return '\n'.join(Register.render(r) for r in rows)


def cmd_close(a):
    repo = repo_dir(a.repo)
    reason = cell(a.reason, '--reason')
    if not os.path.isfile(os.path.join(repo, REGISTER)):
        raise Refused(f'{a.repo} has no {REGISTER}')

    def close(reg):
        row = next((r for r in reg.rows if r['Id'] == a.id), None)
        if row is None:
            raise Refused(f'no row {a.id!r} in {REGISTER}')
        if not is_open(row):
            raise Refused(f'{a.id} is already {row["Status"]}')
        row['Status'] = f'closed {today()}: {reason}'
        return f'closed {a.id}'
    return change(repo, close)


def cmd_for_files(a):
    repo = repo_dir(a.repo)
    _, text = read(repo)
    if text is None:
        return ''
    wanted = []
    for p in a.paths:
        if os.path.isabs(p):
            p = os.path.relpath(p, repo)
        wanted.append(os.path.normpath(p))
    out = []
    for r in Register(text).rows:
        f = r['File']
        if is_open(r) and any(w == '.' or f == w or f.startswith(w.rstrip(os.sep) + os.sep) for w in wanted):
            gone = '' if os.path.lexists(os.path.join(repo, f)) else ' (the file no longer exists; close the row if the finding went with it)'
            out.append(f"- {r['Id']} ({r['Grade']}, {r['Area']}, about {r['Minutes']} min) `{f}`: {r['Scenario']}{gone}")
    return '\n'.join(out)


def cmd_stale(a):
    repo = repo_dir(a.repo)
    try:
        with open(a.runs, encoding='utf-8') as f:
            runs = [m.group(1) for m in (DATE.match(line.strip()) for line in f) if m]
    except OSError as e:
        raise Refused(f'the runs file could not be read ({e.strerror})')
    _, text = read(repo)
    out = []
    for r in ([] if text is None else Register(text).rows):
        since = sum(1 for d in runs if d > r['Date'])
        if is_open(r) and since >= a.threshold:
            out.append(f"{r['Id']} {since} runs since {r['Date']}: re-grade (close won't fix with a reason, or keep) `{r['File']}`")
    return '\n'.join(out)


ITEM = re.compile(r'^(\d+)\. \S')
BULLET = re.compile(r'^[-*] \S')
GAPS = re.compile(r'\bKnown gaps?\b([^:.\n]{0,60}):', re.I)


def scan(text, start, stop):
    """Yield (index, char) at nesting depth 0 outside backticks."""
    depth, tick = 0, False
    for i in range(start, len(text)):
        ch = text[i]
        if ch == '`':
            tick = not tick
        elif not tick and ch in '([':
            depth += 1
        elif not tick and ch in ')]':
            depth = max(0, depth - 1)
        elif not tick and depth == 0:
            if stop(i, ch):
                return i
    return len(text)


def gaps_in(passage):
    end = scan(passage, 0, lambda i, ch: ch == '.' and (i + 1 == len(passage) or (passage[i + 1] == ' ' and passage[i + 2:i + 3].isupper())))
    body = passage[:end]
    parts, last = [], 0
    while True:
        cut = scan(body, last, lambda i, ch: ch == ';')
        parts.append(body[last:cut])
        if cut >= len(body):
            break
        last = cut + 1
    return [p.strip().replace('|', '/') for p in parts if p.strip()]


def plan_passages(text):
    blocks, item, buf, first = [], None, [], 0
    for n, line in enumerate(text.splitlines(), 1):
        m = ITEM.match(line)
        if m or BULLET.match(line) or line.startswith('#') or line.startswith('|'):
            blocks.append((item, first, buf))
            item, buf, first = (m.group(1) if m else '?' if BULLET.match(line) else None), [], n
        buf.append((n, line))
    blocks.append((item, first, buf))
    for item, _, lines in blocks:
        if item is None:
            continue
        joined, starts = '', []
        for n, line in lines:
            starts.append((len(joined), n))
            joined += ' '.join(line.split()) + ' '
        for m in GAPS.finditer(joined):
            line_no = max(n for at, n in starts if at <= m.start())
            yield item, line_no, gaps_in(joined[m.end():].strip())


def cmd_import_plan(a):
    try:
        with open(a.plan, encoding='utf-8') as f:
            text = f.read()
    except OSError as e:
        raise Refused(f'{a.plan} could not be read ({e.strerror})')
    out = []
    for item, line_no, gaps in plan_passages(text):
        if a.counts:
            out.append(f'item {item} (line {line_no}): {len(gaps)} rows')
            continue
        for g in gaps:
            out.append(f'item {item} (line {line_no}) | area ? | grade ? | file ? | {g}')
    return '\n'.join(out)


def parser():
    ap = argparse.ArgumentParser(description='Keep a repository\'s tech-debt register, <repo>/docs/tech-debt.md.')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('add', help='append a row with a new id and today\'s date')
    p.add_argument('repo')
    p.add_argument('--area', required=True)
    p.add_argument('--grade', choices=GRADES, required=True)
    p.add_argument('--file', required=True, help='path relative to the repository')
    p.add_argument('--scenario', required=True, help='one line, no "|"')
    p.add_argument('--source', required=True, help='the review round that found it')
    p.add_argument('--minutes', type=int, required=True, help='estimated minutes to fix')
    p.set_defaults(fn=cmd_add)
    p = sub.add_parser('list', help='print the rows')
    p.add_argument('repo')
    g = p.add_mutually_exclusive_group()
    g.add_argument('--open', action='store_true', help='open rows only (the default)')
    g.add_argument('--all', action='store_true', help='open and closed rows')
    p.set_defaults(fn=cmd_list)
    p = sub.add_parser('close', help='mark a row closed with today\'s date and a reason')
    p.add_argument('repo')
    p.add_argument('id', help='TD-<n>')
    p.add_argument('--reason', required=True)
    p.set_defaults(fn=cmd_close)
    p = sub.add_parser('for-files', help='open rows on these files or under these folders, for a brief')
    p.add_argument('repo')
    p.add_argument('paths', nargs='+')
    p.set_defaults(fn=cmd_for_files)
    p = sub.add_parser('stale', help='open rows untouched for THRESHOLD runs, for re-grading')
    p.add_argument('repo')
    p.add_argument('--runs', required=True, help='a file whose lines start with each run\'s date, YYYY-MM-DD')
    p.add_argument('--threshold', type=int, default=3)
    p.set_defaults(fn=cmd_stale)
    p = sub.add_parser('import-plan', help='print the rows a PLAN.md\'s "Known gaps" passages would give')
    p.add_argument('plan')
    p.add_argument('--dry-run', action='store_true', required=True)
    p.add_argument('--counts', action='store_true', help='print one count per passage instead of the rows')
    p.set_defaults(fn=cmd_import_plan)
    return ap


def main(argv=None):
    a = parser().parse_args(argv)
    try:
        out = a.fn(a)
    except (Refused, OSError) as e:
        print(f'debt.py {a.cmd}: {one_line(e)}', file=sys.stderr)
        return 1
    if out:
        print(out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
