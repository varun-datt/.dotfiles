# Lessons: orchestrator-workers

Dated lessons learned, one or two lines each. VERIFIED as read in the source records unless marked
INFERRED or OPEN. Project names appear only as examples.

**Evidence tags**, written `id (short name)`:
- `Fnn`: a row in the source project's FINDINGS register, for example `F93`.
- `PF-nnn`: a pitfall in the source project's blueprint, for example `PF-37`.
- `notes`: the orchestrator's running notes in the run folder.
- `runbook`: the source session's orchestrator runbook.

## Before the pattern: generic pitfalls from the source blueprint

- 2026-10-04: Parallel test servers that each start a build race on the output folder. Build once
  before the servers start. [PF-37 (parallel builds race)]
- 2026-10-05: Copies of a test suite that share fixed fixture folders and ports collide. Namespace
  both per run; a port that was probed and then released can still be taken.
  [PF-76 (shared fixtures and ports)]
- 2026-10-06: A mutation harness that probes fewer ports than its tests need loses mutations to port
  clashes. Those runs are invalid, not killed. [PF-116 (harness port span)]
- 2026-10-07: A worktree that links the main checkout's dependency folder breaks every start once it
  installs a package. A worktree that changes dependencies needs its own copy.
  [PF-135 (shared dependency folder)]
- 2026-10-07: A test driver with no per-request timeout can hang. The outer timeout then kills it
  before cleanup, which leaves servers running. Bound every request.
  [PF-145 (unbounded driver requests)]

## 2026-10-08: first orchestrator session

- `--allow-all-tools` also approves every MCP server's tools, write tools included, and `--deny-tool`
  does not cover them. Disable them, and check `session.mcp_servers_loaded`. [runbook]
- `session.usage_checkpoint` is cumulative across `copilot -r`; subtract the earlier round. [notes]
- The orchestrator may reject a finding, with a recorded reason. Examples: a finding that asks for a
  new feature (it becomes an owner question), or one that misreads intended behaviour. [notes]
- Start a dependent item from its predecessor's branch to save wall-clock time, then merge main into
  it later. [notes]
- A worker's test harness can ignore the port base it is given. Check harnesses before running
  workers in parallel. [notes]
- On battery with the screen locked, the Mac sleeps and every worker stalls at once (for 90 minutes).
  [runbook]
- A `result` event is not success. A model call that fails five times ends the run with
  `session.error` and then `result`, while the shell exits 0. [runbook]
- In `-p` mode a worker that ends its turn with a background task still running is cut off after
  600 s (`background_task_wait_timeout`, `exitCode` 1). Run gates in the foreground. [runbook]
- Keep the run folder out of `/tmp`. Snapshot uncommitted work before anything risky. [notes]
- After a merge adds a lockfile, run the install step in the merge folder before the gates. [notes]
- A watchdog that is silent on battery misses heartbeats. Count awake minutes instead, and treat a
  wall-clock gap as sleep. [notes]
- `-p` sessions are denied files outside their worktree. `--add-dir` grants access, writing
  included, so pair it with a read-only instruction. [runbook]
- A run superseded by a later round of the same item must not raise an alert. [notes]
- Name run files after the session, `-n <prefix><name>` becoming `<name>.jsonl`, or a live worker
  reads as dead. [runbook]
- One CLI failure ended all five workers in the same second ("Cannot invoke native session after
  disposal has started"). Committing each step kept the loss small. Cause OPEN.
  [F93 (CLI mass stop)]
- A worker can read outside its worktree through the shell, even without `--add-dir`. Name what is
  off limits, and check its tool calls. [runbook]
- Check a security claim against the real values yourself, printing only true or false. One
  "the real keys are masked" claim was false. [F97 (signing keys)]
- When two branches raise a cache or redaction version to the same number, raise it once more at the
  merge. [runbook]
- Mutation controls that break process supervision leak fixtures that ignore TERM, for hours. Check
  `ps` after such runs. [F96 (orphaned fixtures)]
- Send fixes made after the one re-review to a post-merge review (commit-then-review). [runbook]
- Run a trial merge (`--no-commit`, then `--abort`) while the review runs. [runbook]
- `caffeinate` was killed on this machine, INFERRED by endpoint policy. Do not bypass it; only AC
  power prevents the sleep stall. [runbook]
- A real-browser smoke run can fail once and pass on the same commit. Re-run it before reopening an
  item. [F90 (Safari flake)]

## 2026-10-09

- Workers launched from editor terminals die when the editor quits. Launching them outside the
  editor is untested (OPEN). [notes]
- A second mass stop happened with no editor quit, no sleep and the same CLI version. Cause OPEN.
  [notes]
- 17 orphaned fixture processes were found, 3 to 12.5 hours old. The harness should kill the process
  group after each control. [F96 (orphaned fixtures)]
- Two branches added competing mechanisms for one job. A merge kept both, each refusing the other's
  inputs. Consolidating them is an owner question. [notes]

## 2026-10-11

- Never check out anything in the merge folder while a gate runs there. Docs-only merges go straight
  into the main checkout. [notes]
- `git rerere` re-applied an earlier union resolution when a merge was redone. [notes]
- A window reload stalled two workers for 25 minutes inside one model call. Kill them by PID and
  resume them. [notes]
- Gates that need a newer interpreter fail on the system default. Put the right one first on PATH.
  [notes]
- The first once-per-worker alert re-alerted on every tick: a file opened with `a+` reads empty.
  [notes]
- A worker at 2.2x its budget had edited another session's area. Check main's dirty state before
  merging. [notes]
- Plan `--add-dir` for any source outside the repository, such as editor chat files. [notes]
- Editor OpenTelemetry needs `enabled: true`. With content capture on, it wrote 45.7 MB in 51
  minutes, so plan rotation first. [notes]
- Every worker gets a time budget. At 1x, read its last calls. By 2.5x, stop it and resume it with a
  narrower brief. [runbook]
- Budget from gate cost, not item size. One gate cycle (unit check, browser suite, targeted mutation controls) took about 20-25 min on an idle machine, and a worker needs at least two. A 60-min budget for a small item ran 160 min: 134 min in tools, 77 of them mutation controls, one run 53 min while later runs took 10 (cause OPEN). [ran: event timings of the source run]
- Finished background terminals are disposed only if never revealed, and no setting closes finished ones. Select the finished tabs and Kill; never "Kill All Terminals", which kills running workers. [VS Code 1.141 docs and workbench source, read by a research worker]

