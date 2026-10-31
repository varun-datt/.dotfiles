#!/usr/bin/env python3
"""Queue runner for orchestrator-workers: launches the next approved item when a slot frees, so a
stalled orchestrator chat no longer stops the run, and alerts the owner when the chat goes idle.

Usage:
    python3 runqueue.py add <id> --cmd "<shell command>" [--after id1,id2] [--no-slot] [--priority N]
                                 [--unrouted-reason "<why>"]
    python3 runqueue.py done <id>        # merged or closed; items waiting on it become ready
    python3 runqueue.py status           # one line per item
    timeout 172800 python3 runqueue.py run [--slots 3] [--poll 30] [--idle-alert 20] [--chat-log PATH]
    python3 runqueue.py --help

Every subcommand works on <run>/queue.json (OW_RUN_DIR, or --run-dir) under <run>/queue.lock.
`add`, `done` and `status` touch <run>/heartbeat: they are the chat's sign of life.
`add` refuses a command that runs `copilot` unless route.py or review.sh is the program it invokes: bare, after
env, timeout, nohup or assignments, inside `sh|bash|zsh -c '...'`, after ; && || or |, or inside a script file it
runs (read from the current folder; an unreadable script is refused too). --unrouted-reason says why it may run
anyway and is kept with the item. A copilot call it cannot see is caught afterwards by `mine.py --audit`.

`run` launches ready items (highest priority first, then in the order added) while fewer than
--slots slot items run; --no-slot items (reviews) do not count. Each item runs in its own process
group with output in <run>/<id>.runner.log, and its pid, start, end and exit code go to queue.json.
It exits when every item is done, or on SIGTERM, which leaves launched items running.
A pidfile (<run>/queue.pid) stops a second copy from running.

Dead-man alert: the chat's last activity is the newest mtime of <run>/heartbeat and --chat-log (the
VS Code session transcript). When that is older than --idle-alert minutes and something waits on the
chat (an item exited after that and is not done, or nothing runs while items wait), it posts a macOS
notification to the owner and appends the line to <run>/ALERT.log, at most once per --idle-alert
minutes while it stays true. --idle-alert 0 turns it off.

States: waiting (on an item not done), ready, running, exited N, done.
"""
import argparse, contextlib, fcntl, json, os, re, shlex, signal, subprocess, sys, tempfile, threading, time

SEP = set(';&|()\n')
WRAPPERS = {'env': {'-u', '-C', '-P'}, 'timeout': {'-s', '-k'}, 'gtimeout': {'-s', '-k'}, 'nohup': set(), 'nice': {'-n'},
            'caffeinate': {'-t', '-w'}, 'sudo': {'-u', '-g'}, 'setsid': set(), 'stdbuf': set(), 'time': set(),
            'exec': {'-a'}, 'command': set(), 'builtin': set(), 'xargs': {'-I', '-n', '-P', '-L', '-d'}}
KEYWORDS = {'{', '}', '!', 'if', 'then', 'else', 'elif', 'do', 'while', 'until', 'fi', 'done'}
SHELL = re.compile(r'^(?:ba|z|da|k)?sh$')
PYTHON = re.compile(r'^python[\d.]*$')
ASSIGN = re.compile(r'^[A-Za-z_]\w*=')
SUBST = re.compile(r'(?:\$\(|`)\s*(?:\S*/)?copilot\b')
PY_COPILOT = re.compile(r'''["']copilot["']''')
EXEMPT = ('route.py', 'review.sh')


def unrouted(cmd, cwd=None, depth=0):
    """'copilot' when a shell command runs copilot other than through route.py or review.sh as the invoked program,
    'unreadable' when it runs a script that cannot be read to check, else None."""
    if depth > 6:
        return 'unreadable'
    lex = shlex.shlex(cmd.replace('\\\n', ' '), posix=True, punctuation_chars=';&|()\n')
    lex.whitespace, lex.whitespace_split = ' \t\r', True
    try:
        toks = list(lex)
    except ValueError:
        return 'copilot' if re.search(r'\bcopilot\b', cmd) else None
    cwd, found, seg = cwd or os.getcwd(), None, []
    for t in toks + [';']:
        if t and set(t) <= SEP:
            res, cwd = segment(seg, cwd, depth)
            if res == 'copilot':
                return res
            found, seg = found or res, []
        else:
            seg.append(t)
    return found


def segment(seg, cwd, depth):
    if any(SUBST.search(t) for t in seg):
        return 'copilot', cwd
    i = 0
    while True:
        while i < len(seg) and (seg[i] in KEYWORDS or ASSIGN.match(seg[i])):
            i += 1
        if i >= len(seg):
            return None, cwd
        prog = os.path.basename(seg[i])
        if prog not in WRAPPERS:
            break
        i += 1
        while i < len(seg) and (seg[i].startswith('-') or prog == 'env' and ASSIGN.match(seg[i])):
            if prog == 'env' and seg[i] == '-S' and i + 1 < len(seg):
                return unrouted(seg[i + 1], cwd, depth + 1), cwd
            i += 2 if seg[i] in WRAPPERS[prog] else 1
        if prog in ('timeout', 'gtimeout'):
            i += 1
    args = seg[i + 1:]
    if prog == 'copilot':
        return 'copilot', cwd
    if prog == 'cd':
        return None, os.path.join(cwd, os.path.expanduser(args[0] if args else '~'))
    if prog in EXEMPT:
        return None, cwd
    sh, py = SHELL.match(prog), PYTHON.match(prog)
    if sh or py:
        j = 0
        while j < len(args) and args[j][:1] in '-+':
            opt = args[j]
            if sh and not opt.startswith('--') and 'c' in opt[1:] or py and opt == '-c':
                code = args[j + 1] if j + 1 < len(args) else ''
                return (unrouted(code, cwd, depth + 1) if sh else 'copilot' if PY_COPILOT.search(code) else None), cwd
            if py and opt == '-m':
                return None, cwd
            j += 2 if opt in ('-o', '+o', '-W', '-X') else 1
        return (script(args[j], cwd, depth, bool(py)) if j < len(args) else None), cwd
    if '/' in seg[i] or re.search(r'\.(?:z|ba)?sh$', prog):
        return script(seg[i], cwd, depth), cwd
    return None, cwd


def script(path, cwd, depth, python=False):
    if os.path.basename(path) in EXEMPT:
        return None
    try:
        with open(os.path.join(cwd, os.path.expandvars(os.path.expanduser(path))), 'rb') as f:
            raw = f.read()
    except OSError:
        return 'unreadable'
    text = raw.decode('utf-8', 'replace')
    if not (python or raw.startswith(b'#!') or re.search(r'\.(?:z|ba)?sh$|\.py$', path)):
        return None
    if python or path.endswith('.py') or 'python' in text.split('\n', 1)[0]:
        return 'copilot' if PY_COPILOT.search(text) else None
    return unrouted(text, cwd, depth + 1)


def run_dir(arg=None):
    return os.path.abspath(os.path.expanduser(
        arg or os.environ.get('OW_RUN_DIR', '~/.local/state/orchestrator-workers/run')))


@contextlib.contextmanager
def locked(rd):
    os.makedirs(rd, exist_ok=True)
    with open(os.path.join(rd, 'queue.lock'), 'a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def load(rd):
    try:
        with open(os.path.join(rd, 'queue.json'), encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {'items': []}


def save(rd, q):
    fd, tmp = tempfile.mkstemp(dir=rd, prefix='.queue.', suffix='.json')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(q, f, indent=1)
    os.replace(tmp, os.path.join(rd, 'queue.json'))


def touch(rd):
    os.makedirs(rd, exist_ok=True)
    with open(os.path.join(rd, 'heartbeat'), 'a'):
        pass
    os.utime(os.path.join(rd, 'heartbeat'))


def blockers(it, by_id):
    return [a for a in it['after'] if not by_id.get(a, {}).get('done')]


def state(it, by_id):
    if it.get('done'):
        return 'done'
    if it.get('end') is not None:
        return f"exited {'?' if it.get('exit') is None else it['exit']}"
    if it.get('start') is not None:
        return 'running'
    return 'waiting' if blockers(it, by_id) else 'ready'


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def notify(msg):
    try:
        subprocess.run(['osascript', '-e', 'on run argv',
                        '-e', 'display notification (item 1 of argv) with title "Orchestrator idle" sound name "Glass"',
                        '-e', 'end run', msg], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        pass


def last_activity(rd, chat_log, fallback):
    times = []
    for p in (os.path.join(rd, 'heartbeat'), chat_log):
        if p:
            try:
                times.append(os.path.getmtime(p))
            except OSError:
                pass
    return max(times) if times else fallback


def waiting_on_chat(items, since):
    by_id = {it['id']: it for it in items}
    states = {it['id']: state(it, by_id) for it in items}
    out = [f"{it['id']} {states[it['id']]}" for it in items
           if states[it['id']].startswith('exited') and it['end'] > since]
    if not any(s == 'running' for s in states.values()):
        out += [f"{it['id']} waits on {','.join(blockers(it, by_id))}" for it in items if states[it['id']] == 'waiting']
    return out


def run(rd, slots=3, poll=30.0, idle_alert=20.0, chat_log=None, stop=None):
    procs, started, last_alert = {}, time.time(), None
    while True:
        with locked(rd):
            q = load(rd)
            items = q['items']
            now = time.time()
            for it in items:
                if it.get('start') is not None and it.get('end') is None:
                    p = procs.get(it['id'])
                    if p is not None:
                        rc = p.poll()
                    else:
                        rc = None if alive(it['pid']) else 'gone'
                    if rc is not None:
                        it['end'], it['exit'] = now, None if rc == 'gone' else rc
            by_id = {it['id']: it for it in items}
            busy = sum(1 for it in items if it['slot'] and state(it, by_id) == 'running')
            ready = sorted((i for i, it in enumerate(items) if state(it, by_id) == 'ready'),
                           key=lambda i: (-items[i]['priority'], i))
            for i in ready:
                it = items[i]
                if it['slot'] and busy >= slots:
                    continue
                with open(os.path.join(rd, f"{it['id']}.runner.log"), 'ab') as log:
                    p = subprocess.Popen(it['cmd'], shell=True, start_new_session=True, stdin=subprocess.DEVNULL,
                                         stdout=log, stderr=subprocess.STDOUT, env={**os.environ, 'OW_RUN_DIR': rd})
                procs[it['id']] = p
                it.update(pid=p.pid, start=time.time(), end=None, exit=None)
                busy += it['slot']
            save(rd, q)
        if items and all(it.get('done') for it in items):
            return 0
        if idle_alert > 0:
            seen = last_activity(rd, chat_log, started)
            idle = time.time() - seen
            waits = waiting_on_chat(items, seen) if idle >= idle_alert * 60 else []
            if not waits:
                last_alert = None
            elif last_alert is None or time.time() - last_alert >= idle_alert * 60:
                last_alert = time.time()
                msg = f"Chat idle {idle / 60:.0f} min; waiting on it: {', '.join(waits)}"
                with open(os.path.join(rd, 'ALERT.log'), 'a', encoding='utf-8') as f:
                    f.write(f"{time.strftime('%Y-%m-%d %H:%M')} {msg}\n")
                notify(msg)
        if stop is not None and stop.is_set():
            return 0
        time.sleep(poll)


def main(argv=None):
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--run-dir', help='run folder (default: $OW_RUN_DIR)')
    ap = argparse.ArgumentParser(description='Queue approved items and launch each when a slot frees.')
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('add', parents=[common], help='append an item')
    a.add_argument('id')
    a.add_argument('--cmd', required=True, dest='shell', help='shell command that runs the item')
    a.add_argument('--after', default='', help='comma-separated ids that must be done first')
    a.add_argument('--no-slot', action='store_true', help='does not count against --slots (reviews)')
    a.add_argument('--priority', type=int, default=0, help='higher launches first (default 0)')
    a.add_argument('--unrouted-reason', help='why a command that runs copilot skips route.py run (logged with the item)')
    d = sub.add_parser('done', parents=[common], help='mark an item merged or closed')
    d.add_argument('id')
    sub.add_parser('status', parents=[common], help='one line per item')
    r = sub.add_parser('run', parents=[common], help='the long-running loop')
    r.add_argument('--slots', type=int, default=3, help='slot items running at once (default 3)')
    r.add_argument('--poll', type=float, default=30, help='seconds between checks (default 30)')
    r.add_argument('--idle-alert', type=float, default=20, help='minutes of chat idleness before the owner is alerted; 0 turns it off (default 20)')
    r.add_argument('--chat-log', help='session transcript whose mtime counts as chat activity')
    args = ap.parse_args(argv)
    rd = run_dir(args.run_dir)

    if args.cmd == 'run':
        pidfile = os.path.join(rd, 'queue.pid')
        os.makedirs(rd, exist_ok=True)
        try:
            with open(pidfile) as f:
                pid = int(f.read())
            if pid != os.getpid() and alive(pid):
                print('queue runner already running; not starting a second one')
                return 0
        except (OSError, ValueError):
            pass
        with open(pidfile, 'w') as f:
            f.write(str(os.getpid()))
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
        try:
            return run(rd, args.slots, args.poll, args.idle_alert, args.chat_log)
        finally:
            with contextlib.suppress(OSError):
                os.remove(pidfile)

    touch(rd)
    with locked(rd):
        q = load(rd)
        items = q['items']
        by_id = {it['id']: it for it in items}
        if args.cmd == 'add':
            after = [x for x in args.after.split(',') if x]
            if args.id in by_id:
                print(f'queue: {args.id} is already queued', file=sys.stderr)
                return 2
            unknown = [x for x in after if x not in by_id]
            if unknown:
                print(f"queue: unknown --after id: {', '.join(unknown)}", file=sys.stderr)
                return 2
            reason = (args.unrouted_reason or '').strip()
            verdict = unrouted(args.shell)
            if verdict and not reason:
                why = ('runs copilot without route.py run' if verdict == 'copilot'
                       else 'runs a script the queue cannot read to check for copilot')
                print(f'queue: this command {why}; launch it with route.py run, '
                      'or pass --unrouted-reason "<why>"', file=sys.stderr)
                return 2
            items.append({'id': args.id, 'cmd': args.shell, 'after': after, 'slot': not args.no_slot,
                          'priority': args.priority, 'added': time.time(), 'done': False,
                          'pid': None, 'start': None, 'end': None, 'exit': None,
                          **({'unrouted_reason': reason} if reason else {})})
            save(rd, q)
        elif args.cmd == 'done':
            if args.id not in by_id:
                print(f'queue: no item {args.id}', file=sys.stderr)
                return 2
            by_id[args.id]['done'] = True
            save(rd, q)
    if args.cmd == 'status':
        now = time.time()
        for it in items:
            st = state(it, by_id)
            since = it['start'] if it.get('start') is not None else it['added']
            mins = ((it.get('end') or now) - since) / 60
            wait = blockers(it, by_id)
            print(f"{it['id']}  {st}  {mins:.0f}m" + (f"  waits on {','.join(wait)}" if st == 'waiting' else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
