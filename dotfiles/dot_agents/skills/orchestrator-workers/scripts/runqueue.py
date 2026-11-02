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
`add` refuses a command in which the word copilot appears (quotes, $(...), ${...} and backticks removed), or that
names a readable file holding it (followed three files deep, from the current folder; a named script it cannot read
is refused too), unless the one program it invokes is the skill's own route.py run or review.sh: bare, or through
nohup, timeout, env, assignments or a `sh|bash|zsh -c '...'` whose string is only that. Any ; && || | or $(...)
loses the exemption. A false refusal is acceptable; --unrouted-reason says why it may run anyway and is kept with
the item. A copilot call it still cannot see is caught afterwards by `mine.py --audit`.
`add` and `run` refuse (exit 2) when started by a caffeinate process, which this Mac kills within seconds. Command
text is not checked for caffeinate: an item that runs it fails at launch, where route.py run and review.sh refuse
because caffeinate is then their ancestor process.

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
import argparse, contextlib, fcntl, filecmp, json, os, re, shlex, shutil, signal, subprocess, sys, tempfile, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
OWN = ('route.py', 'review.sh')
SEP = set(';&|()\n')
SHELLS = {'sh', 'bash', 'zsh'}
PYTHON = re.compile(r'^python[\d.]*$')
ASSIGN = re.compile(r'^[A-Za-z_]\w*=')
REDIR = re.compile(r'\d*(?:>>?|<)(?:&?\d+\b|&-)?(?:\s*[^\s;&|()<>\'"`]+)?')
SCRIPT = re.compile(r'\.(?:z|ba)?sh$|\.py$|\.command$')


def guard(cmd, cwd=None):
    """None when the command may be queued; 'copilot' when it, or a readable file it names, mentions copilot and the
    program it invokes is not the skill's route.py run or review.sh; 'unreadable' when it names a script it cannot read."""
    cwd = cwd or os.getcwd()
    return None if exempt(cmd, cwd) else mentions(cmd, [cwd], set(), 0)


def own(path):
    for name in OWN:
        mine = os.path.join(HERE, name)
        with contextlib.suppress(OSError):
            if os.path.samefile(path, mine) or filecmp.cmp(path, mine, shallow=False):
                return True
    return False


def ours(tok, name, cwd, search=False):
    if os.path.basename(tok) != name:
        return False
    p = os.path.expanduser(os.path.expandvars(tok))
    if search and '/' not in p:
        p = shutil.which(p) or p
    p = os.path.join(cwd, p)
    return os.path.isfile(p) and own(p)


def words(cmd):
    """The command's words, redirections dropped and ; & | ( ) and newlines as their own tokens; None when unbalanced."""
    lex = shlex.shlex(REDIR.sub(' ', cmd.replace('\\\n', ' ')), posix=True, punctuation_chars=';&|()\n')
    lex.whitespace, lex.whitespace_split = ' \t\r', True
    try:
        return list(lex)
    except ValueError:
        return None


def read_ps():
    # ucomm is the executable's file name, which `exec -a` cannot hide; comm is argv[0].
    return ''.join(subprocess.run(['ps', '-A', '-o', 'pid=', '-o', 'ppid=', '-o', f'{col}='], capture_output=True,
                                  text=True, stdin=subprocess.DEVNULL, timeout=10, check=True).stdout
                   for col in ('ucomm', 'comm'))


def processes(ps=None):
    """{pid: (ppid, [names])} from lines of '<pid> <ppid> <name>'; a pid may have several lines, one per name."""
    table = {}
    for line in (ps or read_ps)().splitlines():
        f = line.split(None, 2)
        if len(f) == 3 and f[0].isdigit() and f[1].isdigit():
            table.setdefault(int(f[0]), (int(f[1]), []))[1].append(f[2].strip())
    return table


def caffeinated_ancestor(ps=None):
    """'<pid> <program>' of the nearest ancestor process whose program is caffeinate, else None; also None, with a
    warning, when the process table cannot be read."""
    try:
        table = processes(ps)
    except (OSError, subprocess.SubprocessError) as e:
        print(f'warning: could not read the process table, so a caffeinate parent was not checked: {e}',
              file=sys.stderr)
        return None
    pid, seen = os.getppid(), set()
    while pid > 1 and pid in table and pid not in seen:
        seen.add(pid)
        ppid, names = table[pid]
        for comm in names:
            if os.path.basename(comm.split()[0] if comm.split() else comm) == 'caffeinate':
                return f'{pid} {comm}'
        pid = ppid
    return None


def caffeinate_refusal(ps=None):
    """The one-line refusal when a process this one runs under is caffeinate, however it was started; else None.
    Command text is not read: a program inside shell text has no end of forms."""
    hit = caffeinated_ancestor(ps)
    where = hit and f'this launcher runs under caffeinate (pid {hit})'
    return where and (f'refused: {where}; this Mac kills caffeinate within seconds and the launch dies with it '
                      '(references/lessons.md, "caffeinate was killed"): keep the Mac on AC power instead')


def exempt(cmd, cwd, depth=0):
    """True when the only program the command invokes is the skill's route.py run or review.sh, bare or through nohup,
    timeout, env or a sh|bash|zsh -c wrapper whose string is itself only such a command."""
    if depth > 3 or re.search(r'\$\(|`|[<>]\(', cmd):
        return False
    toks = words(cmd)
    if toks is None:
        return False
    if toks and toks[-1] == '&':
        toks.pop()
    if not toks or any(t and set(t) <= SEP for t in toks):
        return False
    i = 0
    while i < len(toks):
        if ASSIGN.match(toks[i]):
            i += 1
        elif toks[i] in ('nohup', 'env'):
            i += 1
        elif toks[i] in ('timeout', 'gtimeout'):
            i += 1
            while i < len(toks) and toks[i].startswith('-'):
                i += 2 if toks[i] in ('-s', '-k', '--signal', '--kill-after') else 1
            i += 1
        else:
            break
    rest = toks[i:]
    if not rest:
        return False
    prog = os.path.basename(rest[0])
    if prog in SHELLS and len(rest) == 3 and rest[1] == '-c':
        return exempt(rest[2], cwd, depth + 1)
    if prog in SHELLS:
        return len(rest) > 1 and ours(rest[1], 'review.sh', cwd)
    if PYTHON.match(prog):
        j = 1
        while j < len(rest) and rest[j] in ('-B', '-u', '-E', '-s', '-S'):
            j += 1
        return j + 1 < len(rest) and rest[j + 1] == 'run' and ours(rest[j], 'route.py', cwd)
    if prog == 'route.py':
        return len(rest) > 1 and rest[1] == 'run' and ours(rest[0], 'route.py', cwd, True)
    return prog == 'review.sh' and ours(rest[0], 'review.sh', cwd, True)


def mentions(text, bases, seen, depth):
    """'copilot' when the text, with quotes, $(...), ${...} and backticks removed, or a readable file it names (to
    depth 3, skipping the skill's own route.py and review.sh) holds the word copilot."""
    flat = re.sub(r'\\\n|[\'"`\\]|\$[({]|[(){}]', '', text)
    bare = re.sub(r'\$\{[^}]*\}|\$\w+', '', re.sub(r'\\\n|[\'"`\\]', '', text))
    if 'copilot' in flat.lower() or 'copilot' in bare.lower():
        return 'copilot'
    toks, found = set(re.split(r'[\s;&|<>=]+', flat)), None
    with contextlib.suppress(ValueError):
        toks.update(shlex.split(text))
    bases = bases + [os.path.join(bases[0], os.path.expanduser(os.path.expandvars(d)))
                     for d in re.findall(r'(?:^|[\s;&|])cd\s+([^\s;&|<>]+)', flat)]
    for t in toks:
        if not t or len(t) > 1024:
            continue
        p = os.path.expanduser(os.path.expandvars(t))
        f = next((h for h in (os.path.join(b, p) for b in bases) if os.path.isfile(h)), None)
        if f is None:
            if depth == 0 and SCRIPT.search(p):
                found = found or 'unreadable'
            continue
        f = os.path.realpath(f)
        if f in seen or depth >= 3 or own(f):
            continue
        seen.add(f)
        try:
            with open(f, 'rb') as fh:
                raw = fh.read(1 << 20)
        except OSError:
            found = found or 'unreadable'
            continue
        if b'\0' in raw[:8192]:
            continue
        if mentions(raw.decode('utf-8', 'replace'), [bases[0], os.path.dirname(f)], seen, depth + 1) == 'copilot':
            return 'copilot'
    return found


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
    procs, started, alerted = {}, time.time(), set()
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
                alerted = set()
            elif set(waits) - alerted:
                alerted |= set(waits)
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
    if args.cmd in ('add', 'run'):
        refusal = caffeinate_refusal()
        if refusal:
            print(f'queue: {refusal}', file=sys.stderr)
            return 2

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
            verdict = guard(args.shell)
            if verdict and not reason:
                why = ('mentions copilot, itself or in a file it names, and does not invoke route.py run or review.sh'
                       if verdict == 'copilot' else 'names a script the queue cannot read to check for copilot')
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
