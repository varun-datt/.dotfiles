#!/usr/bin/env python3
"""Writer of <run>/orchestrator.json, the record of what only the orchestrator knows: items, queue, asks.

Usage:
    python3 state.py init --title "Docs build" [--client vscode|cli] [--session-id ID] [--repo PATH] [--plan FILE]
    python3 state.py item <item> [--title T] [--kind build|research|docs] [--gate "npm test" ...] [--note N]
    python3 state.py queue <item> [--title T] [--after <item> ...]      add or replace a queued item
    python3 state.py queue <item> --remove                              take it off the queue
    python3 state.py ask <id> --kind decision|steering|sign-in|blocker --question Q
                         [--item <item>] [--option "per user" ...] [--recommend A] [--context LINK] [--blocks <item> ...]
    python3 state.py answered <id> <answer ...>
    python3 state.py marker "<label>" [--scope all|workers|reviews|merges] [--at ISO]
                                       a routing or cap change, appended to <run>/markers.jsonl

Environment:
    OW_RUN_DIR    run folder (default: ~/.local/state/orchestrator-workers/run); --run overrides it.
    OW_PREFIX     session-name prefix given to `copilot -n` (default: "ow-").
    OW_REGISTRY   run registry that `init` appends to (default: ~/.local/state/orchestrator-workers/registry.jsonl).

Every write replaces the file whole (temporary file, fsync, rename) under a lock, and prints one line.
Markers live in <run>/markers.jsonl, not in orchestrator.json, so readers of the state file are unaffected;
mine.py measures each one.
Options are keyed A, B, C ... in the order given.
"""
import argparse, contextlib, datetime, fcntl, json, os, re, sys, tempfile

STATE = 'orchestrator.json'
MARKERS = 'markers.jsonl'
SCOPES = ('all', 'workers', 'reviews', 'merges')
SCHEMA = 1
KINDS = ('build', 'research', 'docs')
ASK_KINDS = ('decision', 'steering', 'sign-in', 'blocker')
CLIENTS = ('vscode', 'cli')
NAME = re.compile(r'^[A-Za-z0-9][\w.-]{0,63}$')
ASK_ID = re.compile(r'^[A-Za-z0-9][\w.-]{0,31}$')
PREFIX = re.compile(r'^[A-Za-z0-9._-]{1,40}$')
SESSION_ID = re.compile(r'^[0-9A-Za-z-]{8,64}$')
MAX_OPTIONS = 8


class Refused(Exception):
    pass


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def one_line(text):
    return ' '.join(str(text).split())


def run_dir(given):
    raw = given or os.environ.get('OW_RUN_DIR') or '~/.local/state/orchestrator-workers/run'
    return os.path.abspath(os.path.expanduser(raw))


def registry_path():
    return os.path.abspath(os.path.expanduser(os.environ.get('OW_REGISTRY') or '~/.local/state/orchestrator-workers/registry.jsonl'))


@contextlib.contextmanager
def locked(target):
    fd = os.open(os.path.join(os.path.dirname(target), '.' + os.path.basename(target) + '.lock'), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def write_atomic(target, text):
    folder = os.path.dirname(target)
    fd, tmp = tempfile.mkstemp(prefix='.' + os.path.basename(target) + '.', suffix='.tmp', dir=folder)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
    dfd = os.open(folder, os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


def regular_or_absent(target, what):
    if os.path.lexists(target) and (os.path.islink(target) or not os.path.isfile(target)):
        raise Refused(f'{what} {target} is not a regular file; not written')


def load(run):
    target = os.path.join(run, STATE)
    regular_or_absent(target, 'the state file')
    try:
        with open(target, encoding='utf-8') as f:
            doc = json.load(f)
    except FileNotFoundError:
        return target, None
    except (OSError, ValueError) as e:
        raise Refused(f'the state file {target} could not be read ({one_line(e)}); fix or move it, then retry')
    if not isinstance(doc, dict):
        raise Refused(f'the state file {target} is not a JSON object; fix or move it, then retry')
    return target, doc


def fresh():
    return {'schema': SCHEMA, 'updatedAt': None,
            'orchestrator': {'title': None, 'client': None, 'sessionId': None, 'prefix': os.environ.get('OW_PREFIX', 'ow-'), 'repo': None, 'plan': None},
            'items': {}, 'queue': [], 'asks': [], 'risks': []}


def edit(run, change, create=False):
    if not os.path.isdir(run):
        if not create:
            raise Refused(f'the run folder {run} does not exist; run `state.py init` first')
        os.makedirs(run, exist_ok=True)
    target = os.path.join(run, STATE)
    with locked(target):
        target, doc = load(run)
        doc = doc if doc is not None else fresh()
        for key, empty in (('items', {}), ('queue', []), ('asks', []), ('risks', [])):
            if doc.get(key) is None:
                doc[key] = empty
            elif not isinstance(doc[key], type(empty)):
                raise Refused(f'{key} in the state file {target} is not {"an object" if isinstance(empty, dict) else "a list"}; fix or move it, then retry')
        doc['schema'] = SCHEMA
        line = change(doc)
        doc['updatedAt'] = now()
        write_atomic(target, json.dumps(doc, indent=2, ensure_ascii=False) + '\n')
    return line


def name(value, what='item'):
    if not NAME.match(value or ''):
        raise Refused(f'{what} {value!r} must be 1 to 64 letters, digits, dots, dashes or underscores, starting with a letter or digit')
    return value


def register(run, prefix, title, session_id):
    reg = registry_path()
    os.makedirs(os.path.dirname(reg), exist_ok=True)
    real = os.path.realpath(run)
    with locked(reg):
        regular_or_absent(reg, 'the registry')
        try:
            with open(reg, encoding='utf-8') as f:
                text = f.read()
        except FileNotFoundError:
            text = ''
        for raw in text.splitlines():
            try:
                e = json.loads(raw)
            except ValueError:
                continue
            if isinstance(e, dict) and isinstance(e.get('dir'), str) and os.path.realpath(e['dir']) == real:
                return False
        entry = {'dir': real, 'prefix': prefix, 'title': title, 'sessionId': session_id}
        sep = '' if not text or text.endswith('\n') else '\n'
        write_atomic(reg, text + sep + json.dumps(entry, ensure_ascii=False) + '\n')
        return True


def cmd_init(a):
    prefix = os.environ.get('OW_PREFIX', 'ow-')
    if not PREFIX.match(prefix):
        raise Refused(f'OW_PREFIX {prefix!r} must be 1 to 40 letters, digits, dots, dashes or underscores')
    if a.session_id and not SESSION_ID.match(a.session_id):
        raise Refused('--session-id must be 8 to 64 letters, digits or dashes')
    title = one_line(a.title) if a.title else None

    def change(doc):
        o = doc.get('orchestrator') if isinstance(doc.get('orchestrator'), dict) else {}
        o['prefix'] = prefix
        for key, value in (('title', title), ('client', a.client), ('sessionId', a.session_id), ('repo', a.repo), ('plan', a.plan)):
            if value is not None:
                o[key] = value
            o.setdefault(key, None)
        doc['orchestrator'] = o
    edit(a.run, change, create=True)
    added = register(a.run, prefix, title, a.session_id)
    return f"init: {a.run} {'registered' if added else 'was already registered'}"


def cmd_item(a):
    item = name(a.item)

    def change(doc):
        it = doc['items'].get(item) if isinstance(doc['items'].get(item), dict) else {}
        if a.title is not None:
            it['title'] = one_line(a.title)
        if a.kind is not None:
            it['kind'] = a.kind
        if a.gate:
            it['gates'] = [one_line(g) for g in a.gate if one_line(g)]
        if a.note is not None:
            it['note'] = one_line(a.note)
        doc['items'][item] = it
        return f"item {item}: {it.get('kind') or 'kind not set'}, {len(it.get('gates') or [])} gate command(s)"
    return edit(a.run, change)


def cmd_queue(a):
    item = name(a.item)
    after = [name(x, '--after item') for x in a.after or []]

    def change(doc):
        q = [e for e in doc['queue'] if isinstance(e, dict)]
        at = next((i for i, e in enumerate(q) if e.get('item') == item), None)
        if a.remove:
            if at is None:
                return f'queue: {item} was not queued; {len(q)} queued'
            del q[at]
            doc['queue'] = q
            return f'queue: {item} removed; {len(q)} queued'
        entry = {'item': item, 'title': one_line(a.title) if a.title else (q[at].get('title') if at is not None else None), 'after': after}
        if at is None:
            q.append(entry)
        else:
            q[at] = entry
        doc['queue'] = q
        return f'queue: {item} at {q.index(entry) + 1} of {len(q)}'
    return edit(a.run, change)


def cmd_ask(a):
    if not ASK_ID.match(a.id):
        raise Refused(f'ask id {a.id!r} must be 1 to 32 letters, digits, dots, dashes or underscores')
    item = name(a.item) if a.item else None
    blocks = [name(x, '--blocks item') for x in a.blocks or []]
    texts = [one_line(o) for o in a.option or []]
    if len(texts) > MAX_OPTIONS or not all(texts):
        raise Refused(f'give 0 to {MAX_OPTIONS} non-empty --option values')
    options = [{'key': chr(ord('A') + i), 'text': t} for i, t in enumerate(texts)]
    if a.recommend is not None and a.recommend not in [o['key'] for o in options]:
        raise Refused(f"--recommend {a.recommend!r} is not an option key ({', '.join(o['key'] for o in options) or 'no options given'})")
    question = one_line(a.question)
    if not question:
        raise Refused('--question is empty')

    def change(doc):
        asks = doc['asks']
        old = next((x for x in asks if isinstance(x, dict) and x.get('id') == a.id), None)
        if old is not None and old.get('answeredAt'):
            raise Refused(f'ask {a.id} was answered at {old["answeredAt"]}; ask again under a new id')
        new = {'id': a.id, 'kind': a.kind, 'item': item, 'question': question, 'options': options, 'recommendation': a.recommend,
               'context': one_line(a.context) if a.context else None, 'blocks': blocks,
               'askedAt': old.get('askedAt') if old is not None and old.get('askedAt') else now(), 'answeredAt': None, 'answer': None}
        if old is None:
            asks.append(new)
        else:
            asks[asks.index(old)] = new
        open_n = sum(1 for x in asks if isinstance(x, dict) and not x.get('answeredAt'))
        return f"ask {a.id}: {'open' if old is None else 'updated'}, {open_n} open"
    return edit(a.run, change)


def cmd_answered(a):
    answer = one_line(' '.join(a.answer))
    if not answer:
        raise Refused('give the answer after the ask id')

    def change(doc):
        old = next((x for x in doc['asks'] if isinstance(x, dict) and x.get('id') == a.id), None)
        if old is None:
            raise Refused(f'no ask has id {a.id}')
        old['answeredAt'] = now()
        old['answer'] = answer
        open_n = sum(1 for x in doc['asks'] if isinstance(x, dict) and not x.get('answeredAt'))
        return f'answered {a.id}: {answer}; {open_n} open'
    return edit(a.run, change)


def iso_utc(value):
    try:
        t = datetime.datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise Refused(f'--at {value!r} is not an ISO date or time, for example 2026-10-13T18:00:00Z')
    if t.tzinfo is None:
        t = t.astimezone()
    return t.astimezone(datetime.timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def cmd_marker(a):
    label = one_line(a.label)
    if not label:
        raise Refused('the marker label is empty')
    at = iso_utc(a.at) if a.at else now()
    if not os.path.isdir(a.run):
        raise Refused(f'the run folder {a.run} does not exist; run `state.py init` first')
    target = os.path.join(a.run, MARKERS)
    with locked(target):
        regular_or_absent(target, 'the markers file')
        try:
            with open(target, encoding='utf-8') as f:
                text = f.read()
        except FileNotFoundError:
            text = ''
        sep = '' if not text or text.endswith('\n') else '\n'
        entry = {'at': at, 'label': label, 'scope': a.scope}
        write_atomic(target, text + sep + json.dumps(entry, ensure_ascii=False) + '\n')
    n = sum(1 for line in (text + sep).splitlines() if line.strip()) + 1
    return f'marker {label!r}: {a.scope} at {at}; {n} marker(s)'


def parser():
    ap = argparse.ArgumentParser(description='Write the orchestrator state file, <run>/orchestrator.json.')
    ap.add_argument('--run', help='run folder (default: $OW_RUN_DIR)')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('init', help='create the state file and register the run')
    p.add_argument('--title')
    p.add_argument('--client', choices=CLIENTS)
    p.add_argument('--session-id')
    p.add_argument('--repo')
    p.add_argument('--plan')
    p.set_defaults(fn=cmd_init)
    p = sub.add_parser('item', help='record what an item is')
    p.add_argument('item')
    p.add_argument('--title')
    p.add_argument('--kind', choices=KINDS)
    p.add_argument('--gate', action='append', help='a gate command; repeat for each')
    p.add_argument('--note')
    p.set_defaults(fn=cmd_item)
    p = sub.add_parser('queue', help='add, replace or remove a queued item')
    p.add_argument('item')
    p.add_argument('--title')
    p.add_argument('--after', action='append', help='an item this one waits for; repeat for each')
    p.add_argument('--remove', action='store_true')
    p.set_defaults(fn=cmd_queue)
    p = sub.add_parser('ask', help='open or update a question for the owner')
    p.add_argument('id')
    p.add_argument('--kind', choices=ASK_KINDS, required=True)
    p.add_argument('--question', required=True)
    p.add_argument('--item')
    p.add_argument('--option', action='append', help='an answer option, keyed A, B, C ... in order')
    p.add_argument('--recommend', help='the key of the recommended option')
    p.add_argument('--context', help='a link to the full context')
    p.add_argument('--blocks', action='append', help='an item this ask blocks; repeat for each')
    p.set_defaults(fn=cmd_ask)
    p = sub.add_parser('answered', help='record the owner\'s answer; the ask leaves the open list')
    p.add_argument('id')
    p.add_argument('answer', nargs='+')
    p.set_defaults(fn=cmd_answered)
    p = sub.add_parser('marker', help='record a routing or cap change so mine.py can measure its saving')
    p.add_argument('label')
    p.add_argument('--scope', choices=SCOPES, default='all', help='which rounds it affects (default: all)')
    p.add_argument('--at', help='when it took effect, ISO 8601 (default: now)')
    p.set_defaults(fn=cmd_marker)
    return ap


def main(argv=None):
    a = parser().parse_args(argv)
    a.run = run_dir(a.run)
    try:
        print(a.fn(a))
    except (Refused, OSError) as e:
        print(f'state.py {a.cmd}: {one_line(e)}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
