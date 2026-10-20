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
- A worker that started its gates in a background shell and ended its turn "waiting" lost its report. In `-p` mode the session ends with the turn, and a resumed session cannot read the old shell. Gates now run in the foreground, tee to `.gates/<gate>.log`, and the report is the last message. [ran: event log of the lost run]
- Asking for a full-label mutation run "to show the output" cost over an hour, because each control starts browser servers. Ask for a few exact labels without browser tests. [notes]
- Two branches appending to the same test fixture merged cleanly but broke a count assertion in a third test. Run the full browser suite on every merge, not only the merged branches' own specs. [ran]
- Owner rule: escalate only what needs the owner (decisions, steering, blockers, sign-ins, risks); everything else goes to the run notes and the status view. Event-by-event reports cost the owner's attention. [owner, 2026-10-11]

- **Re-check before repeating an ask to the owner** (2026-10-11). I asked the owner for a one-click
  action, never re-read the state it changes, and repeated "still waiting for you" twice after they
  had done it. A pending owner action is a claim about live state: read that state (a file size, a
  table row) each time before restating it.

## 2026-10-12: second orchestrator stretch

- **An idle chat was not woken by its watchdog.** Over-budget alerts at 03:37 and 04:15 started no
  turn; they arrived with the owner's next message at 07:05. Two workers ran 2.4-2.9x over budget
  and a fix round took 4.6 hours, unattended. A heartbeat at 02:56 had started a turn. Cause OPEN.
  Interim, untested: wait in-turn on the watchdog with a bounded sync call instead of ending the
  turn. Research: [follow-ups.md](follow-ups.md) (e). [notes]
- **Finish before starting** (now a rule in [../SKILL.md](../SKILL.md)). Two freed slots went to
  new builds while two started items were one fix round from merging. All three slots then ran for
  4.5-5 hours, the last rounds waited, and one branch drifted 23 commits behind main. [notes]
- **Main moves during a multi-round item.** A branch took three rounds over nine hours while main
  moved 23 commits, and its verified last round then conflicted in five files. Check with
  `git merge-tree --write-tree` before writing the last fix round. [notes]
- **A merge gate counts against the machine.** Three workers plus a merge gate held the load at
  18-28 on 18 CPUs: browser tests timed out, a check run failed under load and passed alone, and
  rounds ran 2.4-4.6x their budgets. INFERRED: run two workers while a merge gate runs. [notes]
- **A merge gate re-runs every control of the label.** 54 controls that each rebuilt a bundle took
  4.5 hours. Count a label's controls and their cost before planning the merge. [ran]
- **Test port bases from 49000 to 50900 sat inside macOS's ephemeral range** (49152-65535,
  `sysctl net.inet.ip.portrange.first`); one port collided on two of three runs. [ran]
- **Gate a stop or a delete on its check with `&&`.** A `;` let a stop run although its check had
  found two child processes. [notes]
- **The last fix rounds skipped their review.** From 2026-10-11 the orchestrator verified each last
  fix round by reading its diff, where this skill prescribes a post-merge review, and six merged
  rounds had no reviewer from another family. Changing a review step is the owner's call; the
  missed reviews were queued. [notes]

## 2026-10-13: third orchestrator stretch

- **macOS deletes files in `/tmp` that have sat untouched for three days.** `/usr/libexec/tmp_cleaner`
  (launchd `com.apple.tmp_cleaner`, daily at 00:00) deletes files under `/tmp` whose access,
  modify and change times are all more than 3 days old, then empty folders. One night it removed a
  merge worktree's `.git` and 530 of its 846 files. The branches survived; the worktree did not.
  Keep worktrees and run folders outside `/tmp`. [ran: the plist, the script, folder times]
- **A skill kept in public dotfiles names no project, even in its examples.** The owner did not
  want an employer project named in his public dotfiles, and five example labels already were.
  Before the owner pushes, check with `git grep -i <name> @{u}` as well as `HEAD`. [ran]
- **When asking the owner to act in another system, say which repository, what the action does
  there, and who will see it.** One ask said only "push main", and its answer was a question. [notes]
- **A plugged-in Mac still idle-slept.** With AC `sleep 1`, the Mac entered Idle Sleep at 100%
  charge despite VS Code's sleep assertion, and every worker froze for 51 minutes until the power
  button. The fix is the owner's setting "Prevent automatic sleeping on power adapter when the
  display is off" (AC `sleep 0`). Check it before unattended work. [ran: `pmset -g log`, `pmset -g custom`]
- **An in-turn wait must print, and a filter on it breaks it.** A sync wait that printed a
  line a minute held the turn for 25 minutes, twice. The same wait piped through `grep -v` and,
  later, `tail -4` went silent and was moved to the background. The second time, with the rule
  already written down, was the handoff trigger "a rule broken twice". Give the wait script its
  own quiet option rather than filtering it at the call. [ran]
- **Ask early how much checking an item gets; the owner may want pieces sooner than perfect.**
  How heavy the process is should be the owner's call: ask at the start, not after a day of building. [owner]
- **A rule broken three times needs a check, not another line.** The in-turn wait rule above was
  broken a third time while written down. A wait that refuses to run when its output is piped makes
  the slip impossible. [ran]
- **A pipe hides the exit code from `&&`.** `python3 -m unittest 2>&1 | tail -2 && install` installed
  after a failing run, because `&&` reads `tail`'s status. Capture the code first
  (`cmd > log; rc=$?`), or use `setopt pipefail`. Extends "gate on its check with `&&`" above. [ran]
- **An exported run variable leaked into the skill's own tests.** With `OW_PREFIX` exported for a
  marker command, one status test failed 10 of 10 times on two revisions, and 0 of 5 once the
  variable was unset. Tests must set every variable they read; run them with `env -u`. [ran]
- **A finished worker went unnoticed for an hour.** It ended between two waits, and each wait
  reported only a count that dropped while it ran. Have each wait report the rounds that ended
  since the previous one. [ran]
- **Copies of the skill's scripts in a run folder go stale silently.** A run folder kept its own
  `status.py` and `watch.py` from three days earlier: they still showed four long-superseded
  rounds as errored and knew nothing of capped rounds. Call the installed skill's scripts. [ran]
- **A credit cap far from its limit prints nothing.** Two resumed rounds and three fresh rounds,
  each launched with `--max-ai-credits` far above what it spent, printed no `Session limits` line
  at all. The 30-credit probe printed one after each call only because it was always near its cap.
  So silence says nothing about whether a cap applies; a resumed session's cap stays OPEN until the
  probe in [follow-ups](follow-ups.md) (g) runs. [ran: 0 limit events in 5 rounds]

## 2026-10-16: fourth orchestrator stretch

- **A fix prompt that names the failing cases gets those cases fixed, not their class.** Two fix
  rounds on a keyboard-focus slice each fixed exactly the paths the review had named, and the next
  review found the same fault on paths nobody named. Name the class, have the worker reproduce each
  case with real input before changing code, and have it list every member of the class with a
  test. [notes]
- **A worker's fakes encode the worker's own assumptions about an outside system.** A tool passed
  every gate while querying a log field the real store does not have; one zero-row live query
  (select the field, limit 0) found it in seconds. Before reviewing a worker's tool that reads an
  outside system, run one cheap live schema read yourself. [ran]
- **Closing the terminal that launched a worker does not stop the worker.** Three workers started
  under `timeout` kept running after their editor terminals were killed, and stopped only when
  killed by process id. `timeout` without `--foreground` runs the command in its own process
  group, which the terminal's hangup does not reach (INFERRED). Stop workers by pid and assert none
  remain. Quitting the editor (2026-10-09 above) was not re-tested. [ran: 9 worker processes after
  3 terminal kills]
- **Editing a running shell script changes what its running copies execute.** zsh reads a script as
  it goes, so editing the launcher while launches were in flight made each of them fail at its
  last line with a parse error, after the worker had finished. Edit a launcher only when no launch
  runs, or write a new file and move it over the old name. [ran]
- **Review prompts filled by hand went out unfilled in 6 of 84 launches.** Those reviews ran
  without their security sentence and word limit, and nothing failed. A launcher check that
  refuses a prompt still holding a `{{NAME}}` placeholder ended it; see (h) in
  [follow-ups](follow-ups.md). [ran]
- **A resumed session reports its running total, not the round's cost.** Copying each round's
  reported credits into a ledger overstated every fix round by all the earlier rounds of its
  session. A round costs the growth of the session total across the round; the per-call records
  alone miss some calls. `F185` (usage records miss calls) [ran]
- **Local usage logs held about half of what the provider billed for the same month.** Measure an
  exact window as the difference of two readings of the provider's own counter. `F183` (local
  logs vs the provider) [ran]
- **Routing trials: a cheaper shadow reviewer missed a reproduced privacy blocker** that the usual
  reviewer caught, so the shadow trial stopped. A mid-tier model on two fix rounds saved no credits
  and finished faster; that trial paused until the owner says whether wall time matters. [notes]
