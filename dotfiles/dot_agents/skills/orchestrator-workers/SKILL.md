---
name: orchestrator-workers
description: "Manual-only. Runs one orchestrator session that plans multi-item work, dispatches each item to a Copilot CLI worker in its own git worktree, has a read-only reviewer from another model family check it (an evaluator-optimizer loop), then merges, gates and records. Use only when the owner invokes it, for work with several items, acceptance criteria and hours of runtime."
argument-hint: "<goal, or a path to the plan>"
disable-model-invocation: true
---

# Orchestrator-workers

One **orchestrator** session plans and judges. **Workers**, **reviewers** and **research workers**
are separate Copilot CLI sessions, each in its own git worktree. The name follows Anthropic's
"Building effective agents": *orchestrator-workers*, with an *evaluator-optimizer* review loop.

## How to use

- **Start it:**
  - in VS Code chat: `/orchestrator-workers <goal, or a path to the plan>`;
  - in Copilot CLI: the same slash command, or "use the orchestrator-workers skill".

  It never starts on its own.
- **What happens next:**
  1. One batch of upfront questions ([Start](#start)), each with a recommendation.
  2. Autonomous work: waves of workers, reviews, merges.
  3. Messages to you only when you need to act: a decision, steering, a blocker or a risk. Everything
     else is in the status table and the end-of-session summary.
  4. Parked questions asked in one batch at the end.
- **Watch it:** you don't need to. The orchestrator escalates only what needs you
  ([Escalate, don't report](#time-budgets-and-monitoring)); the status table holds the rest. The
  watchdog below is meant to wake it, but on 2026-10-12 its alerts did not wake an idle VS Code
  chat for four hours ([lessons](references/lessons.md)). To look yourself, set `OW_RUN_DIR` to the run folder, then:
  - `python3 ~/.agents/skills/orchestrator-workers/scripts/status.py [--all]` shows a table of every worker: its state, elapsed and idle
    minutes, spend, current activity, and `OVER 2.2x of 60m`.
  - `python3 ~/.agents/skills/orchestrator-workers/scripts/watch.py` is the orchestrator's watchdog
    ([monitoring](#time-budgets-and-monitoring)); `--help` lists its options.
- **Stop it:**
  - Tell the orchestrator "stop". It stops launching, reports, and leaves worktrees and commits in
    place.
  - To stop a worker yourself: find its PID with `ps -axww -o pid=,args= | grep -- '-n ow-'`, then
    `kill <PID>`.
  - To stop the watchdog: `kill $(cat "$OW_RUN_DIR/watch.pid")`.
  - Resume a stopped worker later with `copilot -r ow-<item>` and a [resume prompt](assets/resume.md).

## Start

Before any work, ask these in **one batch**. Give options and a recommendation for each, and say
which answers you inferred from the repository.

1. **Goal and items:** the deliverable; each item with its acceptance criteria; the plan and
   decision files that settle the details.
2. **Where:**
   - the repository and its main branch;
   - the worktree root: a dedicated folder outside `/tmp`, for example
     `~/worktrees/<repo>/<branch>`, because macOS deletes old files there ([lessons](references/lessons.md));
   - the run folder, `OW_RUN_DIR`: outside `/tmp`, for example
     `~/.local/state/orchestrator-workers/<date>`;
   - the session prefix, `OW_PREFIX`, default `ow-`.
3. **Gates:**
   - what each item must pass;
   - how to restart and health-check the owner's running instance after a merge;
   - which ports and instances are off limits.
4. **Models:** settled per kind of round by [references/routing.md](references/routing.md) (owner, 2026-10-13). Ask only which models are today's strongest, mid-tier and other-family reviewer, and which items touch a risk area.
5. **Order:** proposed waves and dependencies, and the most workers at once (recommended: 3).
   Propose any extra items now.
6. **Rules:** confirm one review per item; one fixes-only re-review only when blocking findings were
   fixed; the blocking rule (§Lifecycle); and `--no-ff` merges to main, never pushed.
7. **Boundaries:**
   - sibling repositories workers may read (`--add-dir`, read-only);
   - external systems that stay read-only;
   - MCP servers to disable;
   - files another session is editing now.
8. **Time and reporting:** time budgets (defaults below); the heartbeat (recommended: 30 min); where
   decisions, findings and lessons are recorded.
9. **Power:** will the machine stay on AC power and awake? On battery, every worker stalls.
   For unattended work, check it rather than ask: `pmset -g custom` must show `sleep 0` under
   AC Power. A Mac with AC `sleep 1` went to idle sleep while plugged in, and every worker froze.
10. **Anything** the plan leaves unclear.

**After the answers:**
- record the rulings, dated;
- create the run folder and copy [scripts/budgets.example.json](scripts/budgets.example.json) into it
  as `budgets.json`;
- start `watch.py` in an async terminal;
- run `python3 ~/.agents/skills/orchestrator-workers/scripts/state.py init --title "<goal>" --client vscode|cli --session-id <id>`; it writes `<run>/orchestrator.json` and registers the run for the dashboard. Record each item, the queue and every question for the owner only through `state.py item|queue|ask|answered` ([details](references/details.md#state-file));
- work autonomously.

## Roles

| Role | Does | Never |
| --- | --- | --- |
| **Orchestrator** | Plans waves, writes prompts, dispatches, grades reports claim by claim, re-runs load-bearing claims, merges, runs gates on main, writes records, reports | Writes product code: it dispatches instead |
| **Worker** (`copilot -p`, own worktree and branch) | One item; commits each step with explicit paths; runs every gate; reports with labels | Pushes; edits the orchestrator's records; touches the owner's instance |
| **Reviewer** (read-only, another model family) | One review of the diff against the task; at most one fixes-only re-review | Writes, runs a shell, fetches URLs |
| **Research worker** | A proposal with options and a recommendation; commits only its proposal files | Changes product code |

## Lifecycle

```
task -> worker -> grade report -> ONE review -> fix round (resume the worker)
  -> ONE fixes-only re-review, only if blocking findings were fixed
  -> trial merge -> merge -> gates on main -> restart owner's instance -> records
```

- **The blocking rule:** a finding blocks only if it can happen with the owner's data or in normal
  use. Far-fetched findings are recorded and batched into a later item.
- The orchestrator accepts or rejects each finding, with a reason.
- Fixes made after the re-review go to a **post-merge review (commit-then-review)** on main, so
  nothing lands unreviewed. Anything still open is recorded for the owner.
- **Parallelism** is decided per item, from its dependencies and the files it touches.
- **Finish before starting** (owner, 2026-10-13). A freed slot goes first to the oldest started
  item's next step: a fix round, a catch-up with main, then the merge. A new build starts only
  when no started item is waiting for a slot.

## Launch recipe

Per item:
- a worktree: `git worktree add -b <prefix>/<item> <wt-root>/<item> main`;
- its own test port base, below 49152 where macOS's ephemeral range starts (48400, 48500 …), and
  its own install port;
- migration or version numbers reserved in its task body.

```sh
date +%s > "$OW_RUN_DIR/<item>.start"
git -C <wt-root>/<item> rev-parse HEAD > "$OW_RUN_DIR/<item>.base"
COPILOT_TASK_WAIT_TIMEOUT_SECONDS=5400 timeout <seconds> \
  copilot -C <wt-root>/<item> -n "${OW_PREFIX:-ow-}<item>" \
  --model <model> --reasoning-effort <effort> --max-ai-credits <cap> --no-ask-user --allow-all-tools \
  --deny-tool 'shell(git push)' --disable-builtin-mcps --disable-mcp-server <name> \
  [--add-dir <path>] --output-format json -p "$(cat "$OW_RUN_DIR/<item>.prompt.md")" \
  </dev/null > "$OW_RUN_DIR/<item>.jsonl" 2> "$OW_RUN_DIR/<item>.err"
```

- **Run it in an async terminal**, so its completion wakes the orchestrator. Never poll in a loop.
  Why each flag is there: [references/details.md](references/details.md#launch-flags).
- **Model, effort and credit cap:** by the kind of round, from [references/routing.md](references/routing.md); the cap comes from `python3 scripts/mine.py "$OW_RUN_DIR" --caps`.
- **Reviewer:** add `--deny-tool=write --deny-tool=shell --deny-tool=url` and use another model
  family. Write `REVIEW-DIFF.patch` and `REVIEW-REPORT.md` into the author's worktree, uncommitted.
- **Fix and resume rounds:** `copilot -r ow-<item>` with the same flags. Name the run
  `<item>-fix1` or `<item>-resume1`; for its credit cap see [routing](references/routing.md#credit-caps).
- **A `result` event is not success.** Check `exitCode` and `session.error`; `scripts/result.py`
  shows both, plus spend and the report. A round that hit its credit cap also exits 0 ([details](references/details.md#failure-modes-and-recoveries)).

**Prompts** ([assets/](assets/)); placeholders are `{{NAME}}` or `{{NAME|default}}`:
- **Worker:** [preamble-worker.md](assets/preamble-worker.md) + [task-body.md](assets/task-body.md).
  The preamble carries the shared rules: never push, no secrets, `commit --only`, gates in the
  foreground, polls at most every 240 s to keep the cache warm, a labelled report.
- **Research worker:** [preamble-research.md](assets/preamble-research.md) + a body.
- **Reviews:** [review.md](assets/review.md) and the fixes-only [rereview.md](assets/rereview.md).
- **Rounds sent with `-r`:** [fix.md](assets/fix.md) and [resume.md](assets/resume.md). They stay
  short, because the session keeps its context.

Standing owner rules are appended to the preambles as soon as they are made.

## Time budgets and monitoring

A **time budget** is a timebox: a fixed number of minutes the worker should finish in.

- **Defaults:** build 90 min, fix or resume 60, review 30, re-review 20, research 30. Override them
  per run in `budgets.json`.
- **Status table:** `status.py`. Its states are running, STALLED, DIED, ERRORED, CAPPED, done and
  superseded. A capped round shows its credits against the cap. A died or errored round
  reads superseded once a later round of the same item starts.
- **Watchdog:** `watch.py`, in an async terminal. It exits on:
  - a stall: 20 awake minutes without output;
  - a death;
  - a round that hit its credit cap (CAPPED);
  - a budget overrun, once per worker;
  - no worker running;
  - the heartbeat.

  Restart it after every report. Sleep resets the stall clock.

  Its output and options: `watch.py --help`. For a wait inside a turn, add `--progress`, and never
  pipe or filter that wait: a filter silences it ([lessons](references/lessons.md)).
- **At 1x budget:** read the worker's last calls. Is it progressing, looping or blocked?
- **At 2.5x budget:** stop it and resume it with a narrower brief, unless its final gates are
  nearly done.
- **On a stall:** kill it by PID and restart it once.
- **Escalate, don't report** (owner rule, 2026-10-11). Message the owner only when they must act: a
  decision, a point to steer, a blocker, a sign-in, or a risk such as power. Keep it concise and high
  level. Starts, finishes, verdicts, merges and overruns the orchestrator can handle go to the run
  notes, the status table and the end-of-session summary, not to the owner. A heartbeat with nothing
  to escalate gets at most one line.
- **Call temporary things temporary** (owner rule, 2026-10-11). A stopgap, placeholder or interim
  file in a report to the owner is named as temporary, with what replaces it, so it is not read
  as the design.

## Gates and mutation controls

- **Gates:** the checks an item must pass: type check, unit tests, build, browser suite, and
  mutation controls. Workers run them on their own ports, and the orchestrator re-runs them on main
  after each merge.
- **Mutation controls:** deliberate breaks of each new behaviour. Each one ends in one state:
  - **killed:** a failing assertion catches it;
  - **survived:** no test fails;
  - **invalid:** a crash, compile error or timeout, which proves nothing.
- **Mutation score:** killed out of valid controls.
- **Stale controls:** controls whose target code no longer exists.

## Merge discipline

- **Trial merge** while the review runs: `git merge --no-commit`, then `--abort`. It often changes
  the plan. Repeat it with `git merge-tree --write-tree main <branch>` before writing the last fix
  round, and fold any catch-up with main into that round.
- **Make the `--no-ff` merge in the merge folder**, run the gates there, then fast-forward main to
  that commit. Never push. Large conflicts go back to the worker, which merges main into its own
  branch.
- **The merge folder is reserved for gate runs.** Never check out anything else there while a gate
  runs.
- **Docs-only merges** go straight to main.
- **Append-only lists** (control registries, imports): resolve conflicts as a union, then check for
  duplicates.
- **Version bumps:** if two branches raise the same version to the same number, raise it once more
  at the merge.
- **`git config rerere.enabled true`**, so redone merges reuse your resolutions.
- **A new lockfile:** run the install step in the merge folder before the gates.
- **After the merge:** restart the owner's instance and check its health.

## Records

Only the orchestrator writes records; workers and reviewers send drafts.

- **Decisions:** owner rulings, dated, recorded at once, never re-asked.
- **Findings:** workers draft them as `F-NEW-1`; they are numbered `Fnn` at merge, with evidence
  tags.
- **Lessons:** generic ones go to the project's blueprint. Lessons about this pattern go to
  [references/lessons.md](references/lessons.md), dated, with tags.
- **Running notes** in the run folder: each launch, result, spend, verdict and ruling, with its
  time.
- **Per item:** wall-clock time, spend, blocking findings and fix cycles. `python3 scripts/mine.py "$OW_RUN_DIR" --repo <repo>` reads them from the run folder.
- **End of day:** the [learning loop](references/routing.md#learning-loop).

Label every claim VERIFIED (read or ran), INFERRED or OPEN.

## Owner interaction

- **Questions:** batch them, each with options and a recommendation. Say what each choice binds
  beyond itself.
- **Mid-session:** record the question, park only the part it blocks, and carry on. Ask everything
  at the end, unless it blocks all the work.
- **Hand off before the context fills.** After a compaction, or when the queue outlives the session,
  write a handoff (rulings, queue, in-flight workers with resume commands, waiting questions) and
  start a new orchestrator session. Never archive a chat that owns running worker terminals: that
  disposes them.
- **Only the owner decides:** security findings in someone else's system, weakening a check, and
  anything that changes what the owner sees or can do.

## More

- [references/details.md](references/details.md): the flag table, failure modes and recoveries,
  cost.
- [references/routing.md](references/routing.md): model, effort and credit cap per kind of round; risk areas; the learning loop.
- [references/lessons.md](references/lessons.md): dated lessons.
- [references/follow-ups.md](references/follow-ups.md): open research.
