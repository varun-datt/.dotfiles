"""Resume a stopped worker session as a new round, with the launch's own flags.

Usage: python3 -B resume.py <item> <round> <stop|none> <timeout-seconds>
Reads $OW_RUN_DIR/routes.jsonl (the item's last launch) and $OW_RUN_DIR/<round>.prompt.md;
writes <round>.start, <round>.jsonl and <round>.err there, then prints result.py's summary.
A round's credits are its cumulative ai_credits minus the previous round's.
The worker sees no credit cap (owner, 2026-11-02): <stop> is the unseen stop route.py uses, read from
the session's usage records; past it the round ends with exit 3 and writes <round>.stopped.
Refuses (exit 2) when this process runs under caffeinate, however it was started: this Mac kills caffeinate.
"""
import json
import os
import pathlib
import subprocess
import sys
import time

SCRIPTS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))


def last_launch(routes_path, item):
    launches = []
    for line in pathlib.Path(routes_path).read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get('event') == 'launch' and row.get('round') == item:
            launches.append(row)
    if not launches:
        raise SystemExit(f'no launch of {item} in {routes_path}')
    return launches[-1]


def resume_argv(launch_argv, item, prompt):
    argv = list(launch_argv)
    i = argv.index('-n')
    argv[i:i + 2] = ['-r', f'ow-{item}']
    if '--max-ai-credits' in argv:
        i = argv.index('--max-ai-credits')
        del argv[i:i + 2]
    if argv[-1] != '-p':
        raise SystemExit('the launch argv must end with -p')
    return argv + [prompt]


def main(args):
    if len(args) != 4:
        raise SystemExit(__doc__)
    import mine
    import route
    import runqueue
    item, round_name, timeout = args[0], args[1], int(args[3])
    stop = None if args[2].lower() == 'none' else float(args[2])
    run = pathlib.Path(os.environ.get('OW_RUN_DIR', '')).expanduser()
    if not (run / 'routes.jsonl').is_file():
        raise SystemExit('set OW_RUN_DIR to the run folder holding routes.jsonl')
    launch = last_launch(run / 'routes.jsonl', item)
    refusal = runqueue.caffeinate_refusal()
    if refusal:
        print(f'resume.py: {refusal}', file=sys.stderr)
        return 2
    argv = resume_argv(launch['argv'], item, (run / f'{round_name}.prompt.md').read_text())
    worktree = argv[argv.index('-C') + 1]
    (run / f'{round_name}.start').write_text(f'{int(time.time())}\n')
    env = {**os.environ, 'GIT_CONFIG_COUNT': '1',
           'GIT_CONFIG_KEY_0': 'url.blocked-by-orchestrator://.pushInsteadOf', 'GIT_CONFIG_VALUE_0': ''}
    print(f'{round_name}: resume ow-{item} stop {stop} timeout {timeout}s at {time.strftime("%H:%M:%S")}',
          flush=True)
    spend = route.Spend(f'ow-{item}', mine.load_prices(str(run)))
    with open(run / f'{round_name}.jsonl', 'wb') as out, open(run / f'{round_name}.err', 'wb') as err:
        proc = subprocess.Popen(argv, cwd=worktree, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                env=env, start_new_session=True)
        rc, stopped_at = route.wait_round(proc, timeout, stop, spend)
    if stopped_at is not None:
        (run / f'{round_name}.stopped').write_text(json.dumps({'credits': stopped_at, 'stop': stop}) + '\n')
        print(f'STOPPED: {round_name} spent {stopped_at} credits, past its stop of {stop}; resumable', flush=True)
    print(f'{round_name} rc {rc} at {time.strftime("%H:%M:%S")}', flush=True)
    subprocess.run([sys.executable, '-B', str(SCRIPTS / 'result.py'), str(run / f'{round_name}.jsonl'),
                    '--no-report'], stdin=subprocess.DEVNULL)
    return rc


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
