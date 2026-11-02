"""Resume a stopped worker session as a new round, with the launch's own flags.

Usage: python3 -B resume.py <item> <round> <cap> <timeout-seconds>
Reads $OW_RUN_DIR/routes.jsonl (the item's last launch) and $OW_RUN_DIR/<round>.prompt.md;
writes <round>.start, <round>.jsonl and <round>.err there, then prints result.py's summary.
A round's credits are its cumulative ai_credits minus the previous round's.
"""
import json
import os
import pathlib
import subprocess
import sys
import time

SCRIPTS = pathlib.Path(__file__).resolve().parent


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


def resume_argv(launch_argv, item, cap, prompt):
    argv = list(launch_argv)
    i = argv.index('-n')
    argv[i:i + 2] = ['-r', f'ow-{item}']
    if '--max-ai-credits' in argv:
        argv[argv.index('--max-ai-credits') + 1] = str(cap)
    else:
        argv[-1:-1] = ['--max-ai-credits', str(cap)]
    if argv[-1] != '-p':
        raise SystemExit('the launch argv must end with -p')
    return argv + [prompt]


def main(args):
    if len(args) != 4:
        raise SystemExit(__doc__)
    item, round_name, cap, timeout = args[0], args[1], args[2], int(args[3])
    run = pathlib.Path(os.environ.get('OW_RUN_DIR', '')).expanduser()
    if not (run / 'routes.jsonl').is_file():
        raise SystemExit('set OW_RUN_DIR to the run folder holding routes.jsonl')
    launch = last_launch(run / 'routes.jsonl', item)
    argv = resume_argv(launch['argv'], item, cap, (run / f'{round_name}.prompt.md').read_text())
    worktree = argv[argv.index('-C') + 1]
    (run / f'{round_name}.start').write_text(f'{int(time.time())}\n')
    env = {**os.environ, 'GIT_CONFIG_COUNT': '1',
           'GIT_CONFIG_KEY_0': 'url.blocked-by-orchestrator://.pushInsteadOf', 'GIT_CONFIG_VALUE_0': ''}
    print(f'{round_name}: resume ow-{item} cap {cap} timeout {timeout}s at {time.strftime("%H:%M:%S")}',
          flush=True)
    with open(run / f'{round_name}.jsonl', 'wb') as out, open(run / f'{round_name}.err', 'wb') as err:
        proc = subprocess.Popen(argv, cwd=worktree, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                env=env, start_new_session=True)
        try:
            rc = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, 15)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, 9)
            rc = 124
    print(f'{round_name} rc {rc} at {time.strftime("%H:%M:%S")}', flush=True)
    subprocess.run([sys.executable, '-B', str(SCRIPTS / 'result.py'), str(run / f'{round_name}.jsonl'),
                    '--no-report'], stdin=subprocess.DEVNULL)
    return rc


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
