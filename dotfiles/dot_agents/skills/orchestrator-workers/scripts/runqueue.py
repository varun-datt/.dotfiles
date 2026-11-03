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

Pipeline: `add <id> --pipeline build,review,suspend:rulings,fix,recheck,suspend:merge --worktree DIR` runs the
steps in order, each when the one before ended with exit 0, through the skill's own launchers: build and fix with
route.py run (rounds <id> and <id>-fix1, briefs <run>/<id>.prompt.md and <id>-fix1.prompt.md), review and recheck
with review.sh (<id>-review, <id>-rereview) after reviewprep.py writes their inputs. Reviews never take a slot.
A step that exits non-zero (or whose prep fails, exit 2) stops the pipeline: it waits on the chat with its exit
code, until `retry <id>` relaunches it or `retry <id> --passed` marks it passed. `suspend:<name>` waits on the
chat until <run>/<id>.<name>.done exists; a rulings.done whose first word is `none` skips the fix and recheck.
The last step must be a suspend; when it resumes, the item is done. A step's exit code also goes to
<run>/<round>.queue-exit, so a restarted runner never relaunches a step that started.
States of a pipeline item: waiting, ready, running, failed N, suspended, done (status names the step).

    python3 runqueue.py wait [--max-min 30]   # the chat's one blocking call: returns when something needs it
"""
import argparse, contextlib, fcntl, filecmp, json, os, re, shlex, shutil, signal, subprocess, sys, tempfile, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import reviewprep  # noqa: E402

ROUTE = os.path.join(HERE, 'route.py')
REVIEW = os.path.join(HERE, 'review.sh')
STEPS = ('build', 'review', 'fix', 'recheck')
SUSPEND = re.compile(r'^suspend:([A-Za-z0-9_-]+)$')
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


def round_name(it, name):
    return it['id'] + {'build': '', 'review': '-review', 'fix': reviewprep.FIX_ROUND, 'recheck': '-rereview'}[name]


def passed(s):
    return bool(s.get('skipped')) or (s.get('end') is not None and s.get('exit') == 0)


def current(it):
    return next((s for s in it['pipeline'] if not passed(s)), None)


def done_file(rd, it, name):
    return os.path.join(rd, f"{it['id']}.{name}.done")


def exit_file(rd, rnd):
    return os.path.join(rd, rnd + '.queue-exit')


def state(it, by_id):
    if it.get('done'):
        return 'done'
    if 'pipeline' in it:
        s = current(it)
        if s is None:
            return 'done'
        if s.get('end') is not None:
            return f"failed {'?' if s.get('exit') is None else s['exit']}"
        if blockers(it, by_id):
            return 'waiting'
        if SUSPEND.match(s['name']):
            return 'suspended'
        return 'running' if s.get('start') is not None else 'ready'
    if it.get('end') is not None:
        return f"exited {'?' if it.get('exit') is None else it['exit']}"
    if it.get('start') is not None:
        return 'running'
    return 'waiting' if blockers(it, by_id) else 'ready'


def takes_slot(it):
    return it['slot'] and ('pipeline' not in it or (current(it) or {}).get('name') in ('build', 'fix'))


def continues(it):
    """True for a pipeline item past its first step: finishing it, oldest started first, comes before starting
    another."""
    return 'pipeline' in it and current(it) is not it['pipeline'][0]


def needs(items):
    """(key, line, since) for each item waiting on the chat: a plain item that exited, or a pipeline item
    suspended or stopped by a failed step. The key changes when the item reaches a new such point."""
    by_id = {it['id']: it for it in items}
    for it in items:
        st = state(it, by_id)
        if 'pipeline' not in it:
            if st.startswith('exited'):
                yield f"{it['id']}:exit:{it['end']}", f"{it['id']} {st}", it['end']
            continue
        s = current(it)
        if st == 'suspended' and s.get('start') is not None:
            yield (f"{it['id']}:{s['name']}:{s['start']}",
                   f"{it['id']} {s['name']}: write {it['id']}.{s['name'][8:]}.done", s['start'])
        elif st.startswith('failed'):
            why = f": {s['reason']}" if s.get('reason') else ''
            yield f"{it['id']}:{s['name']}:{s['end']}", f"{it['id']} {s['name']} {st}{why}", s['end']


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
    out = [line for _, line, t in needs(items) if t > since]
    if not any(s == 'running' for s in states.values()):
        out += [f"{it['id']} waits on {','.join(blockers(it, by_id))}" for it in items if states[it['id']] == 'waiting']
    return out


WRAP = 'echo $$ > "${0%exit}pid"; "$@" </dev/null; rc=$?; echo $rc > "$0.tmp" && mv "$0.tmp" "$0"; exit $rc'


def pid_file(rd, rnd):
    return os.path.join(rd, rnd + '.queue-pid')


def round_pid(rd, rnd, pid=None):
    """The pid of the round's launcher while it runs, found by its saved pid, the pid file it writes, or its command
    line, which names <round>.queue-exit (a stop between launch and save leaves neither); None when it does not run."""
    marker = ' ' + exit_file(rd, rnd) + ' '
    try:
        out = subprocess.run(['ps', '-axww', '-o', 'pid=,command='], capture_output=True, text=True, timeout=30,
                             stdin=subprocess.DEVNULL).stdout
        cmds = {int(p): c for p, c in (ln.split(None, 1) for ln in out.splitlines() if len(ln.split(None, 1)) == 2)
                if p.isdigit()}
    except (OSError, subprocess.SubprocessError):
        cmds = {}
    known = [pid]
    with contextlib.suppress(OSError, ValueError):
        with open(pid_file(rd, rnd)) as f:
            known.append(int(f.read()))
    if not cmds:
        return next((p for p in known if p and alive(p)), None)
    ours = [p for p, c in cmds.items() if c.startswith('/bin/sh -c ') and marker in c + ' ']
    return next((p for p in known if p in ours), None) or next(iter(ours), None)


def fix_prompt(rd, it):
    """<id>-fix1.prompt.md, else the build's prompt with its body swapped for <id>-fix1.body.md."""
    fix = round_name(it, 'fix')
    path = os.path.join(rd, fix + '.prompt.md')
    if os.path.isfile(path):
        return path
    body_path, build_body = os.path.join(rd, fix + '.body.md'), os.path.join(rd, it['id'] + '.body.md')
    if not os.path.isfile(body_path):
        raise reviewprep.PrepError(f'no {fix}.prompt.md or {fix}.body.md')
    try:
        prompt, body = reviewprep.read(it['brief']), reviewprep.read(build_body)
    except OSError:
        raise reviewprep.PrepError(f"no {fix}.prompt.md, and no {it['id']}.body.md to swap in the build's prompt")
    if not body.strip() or prompt.count(body) != 1:
        raise reviewprep.PrepError(f"no {fix}.prompt.md, and {it['id']}.body.md is not once in the build's prompt")
    reviewprep.write(path, prompt.replace(body, reviewprep.read(body_path)))
    return path


def step_argv(rd, it, s):
    name = s['name']
    rnd, wt = round_name(it, name), it['worktree']
    if name in ('build', 'fix'):
        brief = it['brief'] if name == 'build' else fix_prompt(rd, it)
        if not os.path.isfile(brief):
            raise reviewprep.PrepError(f'no brief at {brief}')
        s['brief'] = brief
        return [sys.executable, '-B', ROUTE, 'run', rnd, '--kind', name, '--run', rd, '--brief', brief,
                '--worktree', wt, *it.get('route_args', [])]
    # route.py run rewrites <round>.base on every launch, so a retried round would hide its first attempt's commits.
    author = next((t for t in it['pipeline'] if t['name'] == ('build' if name == 'review' else 'fix')), {})
    brief = author.get('brief') or (it['brief'] if name == 'review' else None)
    (reviewprep.review if name == 'review' else reviewprep.recheck)(rd, it['id'], wt, author.get('head'), brief,
                                                                    author.get('report'))
    return ['bash', REVIEW, *it.get('review_args', []), rnd, wt]


def launch_step(rd, q, it, s):
    """Start the item's current step; a prep failure ends it at once with exit 2 and the reason."""
    rnd, now = round_name(it, s['name']), time.time()
    for path in (exit_file(rd, rnd), pid_file(rd, rnd)):
        with contextlib.suppress(FileNotFoundError):
            os.remove(path)
    try:
        if s['name'] in ('build', 'fix') and not s.get('head'):
            s['head'] = reviewprep.git(it['worktree'], 'rev-parse', 'HEAD').strip()
        argv = step_argv(rd, it, s)
    except (reviewprep.PrepError, OSError) as ex:
        s.update(start=now, end=now, exit=2, pid=None, reason=str(ex)[:300])
        return None
    s.update(start=now, end=None, exit=None, pid=None, reason=None)
    save(rd, q)
    try:
        with open(os.path.join(rd, f"{it['id']}.runner.log"), 'ab') as log:
            p = subprocess.Popen(['/bin/sh', '-c', WRAP, exit_file(rd, rnd), *argv], start_new_session=True,
                                 stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                 env={**os.environ, 'OW_RUN_DIR': rd})
    except OSError as ex:
        s.update(end=time.time(), exit=127, reason=str(ex)[:300])
        return None
    s['pid'] = p.pid
    save(rd, q)
    return p


def exit_code(rd, rnd):
    try:
        with open(exit_file(rd, rnd)) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def poll_step(rd, it, s, procs, now):
    rnd = round_name(it, s['name'])
    p = procs.get(rnd)
    if p is not None:
        rc = p.poll()
        if rc is None:
            return
        procs.pop(rnd)
    else:
        rc = exit_code(rd, rnd)
        if rc is None:
            live = round_pid(rd, rnd, s.get('pid'))
            if live:
                s['pid'] = live
                return
            # It may have written its exit code and ended between the two checks.
            rc = exit_code(rd, rnd)
    s['end'], s['exit'] = now, rc


def advance(rd, it, by_id, now):
    """Start each suspend that comes due, resume it when its done file exists, and mark the item done when its
    last step passes. A rulings.done whose first word is none skips the steps up to the next suspend."""
    while not it.get('done') and not blockers(it, by_id):
        s = current(it)
        if s is None:
            it['done'] = True
            return
        m = SUSPEND.match(s['name'])
        if not m or s.get('end') is not None:
            return
        if s.get('start') is None:
            s['start'] = now
        path = done_file(rd, it, m.group(1))
        if not os.path.exists(path):
            return
        s['end'], s['exit'] = now, 0
        try:
            with open(path, encoding='utf-8', errors='replace') as f:
                word = (f.read().split() or [''])[0].lower().strip('.')
        except OSError:
            word = ''
        if m.group(1) == 'rulings' and word == 'none':
            for t in it['pipeline'][it['pipeline'].index(s) + 1:]:
                if SUSPEND.match(t['name']):
                    break
                t['skipped'] = True


def run(rd, slots=3, poll=30.0, idle_alert=20.0, chat_log=None, stop=None):
    procs, started, alerted = {}, time.time(), set()
    while True:
        with locked(rd):
            q = load(rd)
            items = q['items']
            now = time.time()
            for it in items:
                if 'pipeline' in it:
                    s = current(it)
                    if not it.get('done') and s and s.get('start') is not None and s.get('end') is None \
                            and not SUSPEND.match(s['name']):
                        poll_step(rd, it, s, procs, now)
                    continue
                if it.get('start') is not None and it.get('end') is None:
                    p = procs.get(it['id'])
                    if p is not None:
                        rc = p.poll()
                    else:
                        rc = None if alive(it['pid']) else 'gone'
                    if rc is not None:
                        it['end'], it['exit'] = now, None if rc == 'gone' else rc
            by_id = {it['id']: it for it in items}
            for it in items:
                if 'pipeline' in it:
                    advance(rd, it, by_id, now)
            busy = sum(1 for it in items if takes_slot(it) and state(it, by_id) == 'running')
            ready = sorted((i for i, it in enumerate(items) if state(it, by_id) == 'ready'),
                           key=lambda i: (0, items[i]['pipeline'][0].get('start') or items[i]['added'], i)
                           if continues(items[i]) else (1, -items[i]['priority'], i))
            for i in ready:
                it = items[i]
                if takes_slot(it) and busy >= slots:
                    continue
                if 'pipeline' in it:
                    s = current(it)
                    p = launch_step(rd, q, it, s)
                    if p is not None:
                        procs[round_name(it, s['name'])] = p
                        busy += takes_slot(it)
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
    a = sub.add_parser('add', parents=[common], help='append an item: a --cmd, or a --pipeline of steps')
    a.add_argument('id')
    how = a.add_mutually_exclusive_group(required=True)
    how.add_argument('--cmd', dest='shell', help='shell command that runs the item')
    how.add_argument('--pipeline', help='steps run in order, e.g. build,review,suspend:rulings,fix,recheck,suspend:merge '
                     '(build, review, fix, recheck, suspend:<name>; the last must be a suspend)')
    a.add_argument('--worktree', help="with --pipeline: the item's worktree")
    a.add_argument('--brief', help='with --pipeline: the build prompt (default <run>/<id>.prompt.md)')
    a.add_argument('--route-args', default='', help='with --pipeline: extra route.py run options for build and fix')
    a.add_argument('--review-args', default='', help='with --pipeline: extra review.sh options for review and recheck')
    a.add_argument('--after', default='', help='comma-separated ids that must be done first')
    a.add_argument('--no-slot', action='store_true', help='does not count against --slots (reviews)')
    a.add_argument('--priority', type=int, default=0, help='higher launches first (default 0)')
    a.add_argument('--unrouted-reason', help='why a command that runs copilot skips route.py run (logged with the item)')
    d = sub.add_parser('done', parents=[common], help='mark an item merged or closed')
    d.add_argument('id')
    t = sub.add_parser('retry', parents=[common], help="relaunch a pipeline item's failed step")
    t.add_argument('id')
    t.add_argument('--passed', action='store_true', help='mark the failed step passed instead (the chat finished it by hand)')
    t.add_argument('--report', metavar='ROUND', help='with --passed: the round that finished it (a resume round), '
                   'whose report the next review or re-check reads (default: the newest of the round and its '
                   '<round>-resumeN rounds)')
    sub.add_parser('status', parents=[common], help='one line per item')
    w = sub.add_parser('wait', parents=[common], help='block until an item newly needs the chat, then print it')
    w.add_argument('--max-min', type=float, default=30, help='give up after this many minutes, exit 1 (default 30)')
    w.add_argument('--settle', type=float, default=30, help='seconds to wait for others once one is seen (default 30)')
    w.add_argument('--poll', type=float, default=20, help='seconds between checks (default 20)')
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
    if args.cmd == 'wait':
        return wait(rd, args.max_min, args.settle, args.poll)
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
            if args.pipeline is not None:
                item, err = pipeline_item(rd, args)
                if err:
                    print(f'queue: {err}', file=sys.stderr)
                    return 2
                items.append({'id': args.id, 'after': after, 'slot': not args.no_slot, 'priority': args.priority,
                              'added': time.time(), 'done': False, **item})
                save(rd, q)
                return 0
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
        elif args.cmd == 'retry':
            it = by_id.get(args.id)
            if it is None or 'pipeline' not in it or not state(it, by_id).startswith('failed'):
                print(f'queue: {args.id} is not a pipeline item stopped by a failed step', file=sys.stderr)
                return 2
            s = current(it)
            live = round_pid(rd, round_name(it, s['name']), s.get('pid'))
            if live:
                print(f"queue: {round_name(it, s['name'])} may still run (pid {live}); stop it or let it end first",
                      file=sys.stderr)
                return 2
            if args.report and (not args.passed or not os.path.isfile(os.path.join(rd, args.report + '.jsonl'))):
                print(f'queue: --report needs --passed and an existing {args.report}.jsonl', file=sys.stderr)
                return 2
            if args.passed:
                s.update(exit=0, passed_by='chat', **({'report': args.report} if args.report else {}))
            else:
                s.update(start=None, end=None, exit=None, pid=None, reason=None)
            save(rd, q)
    if args.cmd == 'status':
        now = time.time()
        for it in items:
            st = state(it, by_id)
            if 'pipeline' in it:
                print(pipeline_status(it, st, by_id, now))
                continue
            since = it['start'] if it.get('start') is not None else it['added']
            mins = ((it.get('end') or now) - since) / 60
            after = blockers(it, by_id)
            print(f"{it['id']}  {st}  {mins:.0f}m" + (f"  waits on {','.join(after)}" if st == 'waiting' else ''))
    return 0


def pipeline_item(rd, args):
    """(the item's pipeline fields, None), or (None, why it is refused)."""
    names = [n.strip() for n in args.pipeline.split(',') if n.strip()]
    bad = [n for n in names if n not in STEPS and not SUSPEND.match(n)]
    if not names or bad:
        return None, f"unknown pipeline step: {', '.join(bad) or '(none given)'}; use {', '.join(STEPS)} or suspend:<name>"
    if not SUSPEND.match(names[-1]):
        return None, 'the last pipeline step must be a suspend (such as suspend:merge), so the chat ends the item'
    if len(set(names)) != len(names):
        return None, 'a pipeline step appears twice; one review, one fix round and one re-check per item'
    if 'recheck' in names and ('fix' not in names or names.index('fix') > names.index('recheck')):
        return None, 'recheck needs a fix step before it'
    if not args.worktree or not os.path.isdir(os.path.expanduser(args.worktree)):
        return None, f'--pipeline needs --worktree naming an existing folder (got {args.worktree!r})'
    stale = [p for p in (os.path.join(rd, f'{args.id}.{n[8:]}.done') for n in names if SUSPEND.match(n))
             if os.path.exists(p)]
    if stale:
        return None, f"remove the done file left from before, or it resumes its suspend at once: {', '.join(stale)}"
    try:
        route_args, review_args = shlex.split(args.route_args), shlex.split(args.review_args)
    except ValueError as ex:
        return None, f'cannot split --route-args or --review-args: {ex}'
    return {'pipeline': [{'name': n, 'start': None, 'end': None, 'exit': None, 'pid': None} for n in names],
            'worktree': os.path.abspath(os.path.expanduser(args.worktree)),
            'brief': os.path.abspath(os.path.expanduser(args.brief or os.path.join(rd, args.id + '.prompt.md'))),
            'route_args': route_args, 'review_args': review_args}, None


def pipeline_status(it, st, by_id, now):
    s = current(it)
    if s is None:
        return f"{it['id']}  done"
    k = it['pipeline'].index(s)
    head = f"{it['id']}  {s['name']} ({k + 1}/{len(it['pipeline'])})"
    since = s['start'] if s.get('start') is not None else it['added']
    if st == 'running':
        what = f"running {round_name(it, s['name'])}"
    elif st == 'suspended':
        what = f"waits on the chat: {it['id']}.{s['name'][8:]}.done"
    elif st.startswith('failed'):
        what = f"{st}, waits on the chat" + (f": {s['reason']}" if s.get('reason') else '')
        now = s['end']
    elif st == 'waiting':
        what = f"waiting  waits on {','.join(blockers(it, by_id))}"
    else:
        what = st
    return f"{head}  {what}  {(now - since) / 60:.0f}m"


def wait(rd, max_min, settle, poll):
    """Block until an item reaches a point that needs the chat which no earlier call printed (kept in
    <run>/queue.seen), print one line each and exit 0; exit 1 after max_min minutes, printing a tick each minute."""
    path = os.path.join(rd, 'queue.seen')

    def fresh():
        try:
            with open(path, encoding='utf-8') as f:
                seen = set(f.read().split('\n'))
        except FileNotFoundError:
            seen = set()
        with locked(rd):
            items = load(rd)['items']
        return [(k, line) for k, line, _ in needs(items) if k not in seen], items

    t0 = tick = time.time()
    while True:
        new, items = fresh()
        if new:
            if settle:
                time.sleep(settle)
                new, items = fresh()
            with open(path, 'a', encoding='utf-8') as f:
                f.write(''.join(k + '\n' for k, _ in new))
            for _, line in new:
                print(line, flush=True)
            return 0
        if items and all(it.get('done') for it in items):
            print('all items done', flush=True)
            return 0
        if time.time() - t0 >= max_min * 60:
            print(time.strftime('%H:%M'), 'nothing needs the chat yet', flush=True)
            return 1
        time.sleep(poll)
        if time.time() - tick >= 60:
            tick = time.time()
            print(time.strftime('%H:%M'), 'waiting', flush=True)


if __name__ == '__main__':
    sys.exit(main())
