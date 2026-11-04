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
  chat for four hours ([lessons](references/lessons.md)), and on 2026-10-27 an in-chat review
  blocked the chat for three ([lessons](references/lessons.md#2026-10-27-a-subagent-review-blocked-the-run)).
  The [queue runner](#queue-runner) now launches the next item, and alerts you, not the chat, when
  the chat goes idle. To look yourself, set `OW_RUN_DIR` to the run folder, then:
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
  - To stop the queue runner: `kill $(cat "$OW_RUN_DIR/queue.pid")`. Items it launched keep running.
  - Resume a stopped worker later with `copilot -r ow-<item>` and a [resume prompt](assets/resume.md).

## Start

Before any work, ask these in **one batch**. Give options and a recommendation for each, and say
which answers you inferred from the repository.

1. **Goal and items:** the deliverable; each item with its acceptance criteria; the plan and
   decision files that settle the details. For a complex item: what was surveyed for reuse
   (products, libraries, patterns), or a research step first, and which dependencies it may add
   (owner, 2026-10-27: skipping that research is "a vary big miss"). Split an item expected to
   take over 45 minutes, or one touching two of the project's hot spots (turn and run state, file
   containment, a shared view's state), into two items: large items averaged 3.1 blocking findings
   against 1.6 for small ones, and three rounds ran out of credits or time (2026-10-30).
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
   Never wrap a launch in `caffeinate`: this Mac kills it within seconds. A queued item that runs it fails
   at launch, where `route.py run`, `review.sh` and `resume.py` refuse (exit 2) because they find caffeinate
   among their ancestor processes. Command text is not checked: a program inside shell text has no end of forms.
10. **Anything** the plan leaves unclear.

**After the answers:**
- record the rulings, dated;
- create the run folder and copy [scripts/budgets.example.json](scripts/budgets.example.json) into it
  as `budgets.json`;
- start `runqueue.py run` in an async terminal and `watch.py` in another as a stall watchdog; wait with `runqueue.py wait` ([queue runner](#queue-runner));
- run `python3 ~/.agents/skills/orchestrator-workers/scripts/state.py init --title "<goal>" --client vscode|cli --session-id <id>`; it writes `<run>/orchestrator.json` and registers the run for the dashboard. Record each item, the queue and every question for the owner only through `state.py item|queue|ask|answered` ([details](references/details.md#state-file));
- work autonomously.

## Roles

| Role | Does | Never |
| --- | --- | --- |
| **Orchestrator** | Plans waves, writes prompts, dispatches, grades reports claim by claim, re-runs load-bearing claims, merges, runs gates on main, writes records, reports | Writes product code: it dispatches instead |
| **Worker** (`copilot -p`, own worktree and branch) | One item; commits each step with explicit paths; runs every gate; reports with labels | Pushes; edits the orchestrator's records; touches the owner's instance |
| **Reviewer** (read-only, another model family) | One review of the diff against the task; at most one fixes-only re-review | Writes, runs a shell, fetches URLs |
| **Research worker** | A proposal with options and a recommendation; commits only its proposal files | Changes product code |

**No in-chat subagents in an unattended run.** Never use an in-chat subagent tool (VS Code
`runSubagent`, Copilot CLI `task`) for anything a later item waits on, reviews included. It has no
timeout and blocks the orchestrator until it returns. Run that work as a CLI process under
`timeout`. Subagents are fine only for work nothing waits on, and only while the owner is watching.

## Lifecycle

```
task -> worker -> grade report -> ONE review -> ONE fix round (a fresh session, short brief)
  -> ONE fixes-only re-review, only if blocking findings were fixed
  -> trial merge -> merge -> gates on main -> restart owner's instance -> records
```

- **Only judgement wakes the chat.** Queue each item as a [pipeline](#queue-runner): the runner prepares and
  launches the review, the fix round and the re-check itself, and stops at two suspend points, ruling the
  review's findings and merging, because only those need judgement. The chat waits for the next one with
  `runqueue.py wait`; a failed step also stops the pipeline and waits on the chat.
- **The blocking rule** ([references/rubric.md](references/rubric.md), owner, 2026-10-30): the
  reviewer grades every finding by likelihood and impact; Blocker and Major block (I1 at L1–L2; I2
  at L1–L2; I3 at L1). Minor goes to debt: one line on the repository's `docs/tech-debt.md`.
- The orchestrator accepts or rejects each finding, with a reason.
- **Research learnings travel** (owner, 2026-11-01): after merging a research proposal, the
  orchestrator adds a one-line pointer to each item its "Helps other items" list names, at the
  level it names; user-level changes (instructions, skills, the wiki) are proposed to the owner
  first.
- **Tech debt** (`scripts/debt.py`, one `docs/tech-debt.md` per repository): the orchestrator adds a
  row for each Minor finding and each Major the owner merged as a known gap. A brief that touches a
  listed file names its rows (`debt.py for-files <repo> <paths>`) and fixes those under about 15
  minutes: its `TECH DEBT:` line lists the ids it fixes with their lines, or says why not, and
  `route.py run` warns (exit unchanged) for each open row on a named path whose id the brief leaves out; the worktree's root folder itself is not matched, since every brief names it in YOUR RESOURCES. A class seen 3 times becomes a planned item; past about 30 open rows, each run plans one
  debt item; `debt.py stale` lists rows untouched for 3 runs, to close "won't fix" or keep.
- A finding the re-review leaves open pauses the item for the owner (owner, 2026-10-31, confirmed
  2026-11-02): one fix round, then the owner decides. `route.py run` refuses any fix round after an item's first (exit 2) unless `--override` carries `owner_approved=<where the owner said so>`, and `mine.py --quality` flags one launched without it.
  A fix made after the re-review, once the owner
  approves it, goes to a **post-merge review (commit-then-review)** on main, so nothing lands unreviewed.
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
python3 ~/.agents/skills/orchestrator-workers/scripts/route.py run <item> --kind build \
  --brief "$OW_RUN_DIR/<item>.prompt.md" --worktree <wt-root>/<item> \
  [--add-dir <path> ...] [--override "model=..,effort=..,context=..,cap=<n>|none,reason=.."] </dev/null
```

- **Every round goes through `route.py run`; a run must not write its own copilot launch scripts.**
  Scripts with a fixed `MODEL` and `EFFORT` bypassed the router on 2026-10-30. The launcher checks
  the brief (exit 5), picks the model, effort, context tier and cap or takes `--override` (refused
  without a `reason=`), logs the decision with the CLI version to `routes.jsonl`, waits for load
  (exit 12), writes `<item>.start`, `<item>.base` and the time budget in `budgets.json`, and runs
  `copilot -p` under a timeout with exactly the logged values, no MCP servers, push denied and no
  questions, into `<item>.jsonl` and `<item>.err`. On exit it sweeps the worktree's leftovers. It
  exits non-zero when copilot fails (124 on timeout) or the round errored (4) or hit its cap (3).
  Re-running it before the round launched reuses the logged decision; `--fresh` draws again.
- **Run it in an async terminal**, so its completion wakes the orchestrator. Never poll in a loop.
  Why each flag is there: [references/details.md](references/details.md#launch-flags).
- **Load and leftovers** (`scripts/sweep.py`): a launch, review or merge gate waits while the Mac
  swaps or a `yes` stress process runs, and on exit stops orphans (parent 1) whose working folder
  is in its worktree, plus orphan `yes`, naming each in the log. Never sweep the owner's own
  checkout. Why: on 2026-10-29 seven leaked `yes` processes ran 5 hours at 5.3 cores while the
  Mac swapped, and the merge gates in that window failed on load-sensitive tests.
- **The brief check** (`scripts/brief.py`) refuses a prompt with an unfilled `{{PLACEHOLDER}}`,
  or a worker prompt without a filled REUSE CHECK and ALLOWED DEPENDENCIES line: on 2026-10-27 one
  brief had no research step and another's "use a library if one fits" lost to the preamble's
  dependency rule, so both features were hand-written. A worker brief (not a fix round) is also
  refused when a top-level numbered MUST has no "SHALL" ("WHEN <event or state>, <part> SHALL <response>"),
  or its RISK, CASES THE ORCHESTRATOR KNOWS or FACTS TO VERIFY line is missing or empty; each
  may say "none" with a reason, and a bare "none" in backticks or with punctuation is still empty.
  A TIME BUDGET over 45 minutes only warns: split the item. The prompt's kind comes from its first
  line (the preamble's opening, then a "THIS IS A FIX ROUND" line before "TASK:"), not from a quote
  further down; `brief.py check --kind <kind>` overrides it. A fix round (kind fix, or a round named
  `<item>-fixN`, which `route.py run` checks as one) is refused unless each finding under FIX THESE has a
  WHY NOW line, `N HARM: <what the owner loses if it merges>` or `N DEPENDS: <the planned item that builds
  on it>` (owner, 2026-11-02: a fix round must earn its place; other findings go to the tech-debt list).
- **Model, effort, context tier and credit cap:** `route.py run` (or `route.py pick` to see the choice without launching) chooses them per round and logs why ([router](references/routing.md#the-router)); the static table in [references/routing.md](references/routing.md) is its fallback. The cap comes from `python3 scripts/mine.py "$OW_RUN_DIR" --history <earlier run> ... --caps`. A kind with under 5 rounds on a model gets a cap derived from another model's rounds by price (`scripts/prices.json`, refreshed from the SDK's `listModels()`). `--chat <debug-log-dir> --budget N` prints the run's spend, chat included (an upper bound), against N and how many more rounds fit.
- **Reviewer:** run it with `bash scripts/review.sh <item>-review <worktree> [prompt-file]`, which
  launches it through `route.py run --kind review` (`--help` lists the options it passes on, such
  as `--override` and `--timeout`) and writes the verdict line to `<run>/<name>.txt` for `mine.py`.
  The router picks another model family from the author's model, read from the author round's
  log when `--author-model` is not given. It denies `shell(git push)`, `shell(git commit)`, `shell(npm)` and `url`, not the whole
  shell, because the reviewer reads `git diff`. Write `REVIEW-DIFF.patch` and `REVIEW-REPORT.md` into the author's worktree, uncommitted.
  It runs at high effort, and fills the rubric's blocking scope from `--scope product|tool`, which wins over the default, by default `tool` only when every changed file is under `dotfiles/dot_agents/skills/*/scripts/` (owner, 2026-11-02); a re-review or critique prompt, which has no rubric, gets the scope line and the rubric's Scope rule at its end.
  A diff about file-system races or sandbox escapes can hit OpenAI's 422 "cybersecurity risk"
  filter on gpt-6.1-sol, or a sub-agent that refuses (2026-10-29: 3 rounds, 131 credits, no
  verdict). Tell the reviewer to work in its own session, and after one 422 fall back to Opus at
  max in a fresh session, saying the review is same-family: `--override "model=..,effort=max,same_family=yes,reason=422 .."`.
  Without `same_family=yes` the launcher refuses any review in the author's family, and any review whose author it
  cannot find (no `--author-model`, no author round log, none saved with a reused decision).
- **An INFERRED vendor fact gets its live check before the build**, and the brief's FACTS TO
  VERIFY carries the result. On 2026-10-29 a feature built on Copilot's message ids merged, and
  the live check after it showed the ids were snapshot positions: a fix round and a second merge
  undid it.
- **Bring main into a branch before its review** when main has moved under the files the item
  touches, so the reviewer reads the code that will merge (one stale selector, 2026-10-30).
- **Fix rounds** (`<prefix><item>-fixN`) go back to the builder: `route.py run <item>-fix1 --kind fix
  --resume-session <item>` resumes the build's own session, with the fix brief alone as its prompt, so
  it does not relearn the item (owner, 2026-11-02, reversing 2026-10-29's fresh fix sessions, which were
  chosen when resumed rounds averaged 92k tokens per request against 75k for builds; compare the first
  resumed fixes with run amc-2026-11-02-p1's fresh ones, median 421 credits). The pipeline does this
  whenever `routes.jsonl` holds the build's launch, and starts a fresh session otherwise. Fix rounds are
  narrow (owner,
  2026-11-02, after fix rounds cost more than builds): the brief carries only the blocking findings,
  each with where, what goes wrong and what done looks like; one test per finding that fails first;
  only the checks for the changed files; no impact map, case table or mutation runs, and screenshots
  only for a UI finding ([fix.md](assets/fix.md)). A whole kind is fixed only when the finding lists
  its cases; other cases the fixer sees go to the debt list, and a kind in 3 or more items goes to
  the owner as a structural fix. One round per item; a further round goes on the owner's list.
- **Resume rounds** (`<item>-resumeN`, a stopped worker): `copilot -r ow-<item>` with the same
  flags; `python3 -B scripts/resume.py <item> <round> <stop|none> <timeout>` does it from the item's
  last launch in `routes.jsonl`, with the prompt in `$OW_RUN_DIR/<round>.prompt.md`. Credit caps
  for both: [routing](references/routing.md#credit-caps).
- **Before merging a note or page,** `python3 -B scripts/merge_check.py --patterns <file> <files>`
  checks the redaction patterns on word boundaries and literal `\u` escapes.
- **A `result` event is not success.** Check `exitCode` and `session.error`; `scripts/result.py`
  shows both, plus spend and the report. A round past its unseen credit stop exits 3 and leaves
  `<round>.stopped` ([routing](references/routing.md#credit-caps)).

**Prompts** ([assets/](assets/)); placeholders are `{{NAME}}` or `{{NAME|default}}`:
- **Worker:** [preamble-worker.md](assets/preamble-worker.md) + [task-body.md](assets/task-body.md).
  The preamble opens with the build method (map, cases, facts, small steps, tests that fail when
  broken, rows checked against evidence), naming the `software-testing` case lists by their
  deployed path, then carries the shared rules: never push, no secrets, `commit --only`, gates in
  the foreground, polls at most every 240 s to keep the cache warm, a labelled report with an
  impact map and a case table.
- **Research worker:** [preamble-research.md](assets/preamble-research.md) + a body. Its note is
  critiqued by another model family with [critique-research.md](assets/critique-research.md),
  against a snapshot of the note, page, task and report; the critic also asks whether the note
  builds what already exists (owner, 2026-11-01).
- **Reviews:** [review.md](assets/review.md), which grades on [references/rubric.md](references/rubric.md)
  (`review.sh` fills `{{RUBRIC}}`) and tags each finding's cause and class, and the short
  [rereview.md](assets/rereview.md), which only checks each named finding was fixed, its test, and
  harm the fix itself adds, at high effort.
- **Fix round:** [preamble-worker.md](assets/preamble-worker.md) + [fix.md](assets/fix.md), a
  fresh session, so it names the branch, worktree, base commit and ports.
- **Resume round, sent with `-r`:** [resume.md](assets/resume.md); short, because the session
  keeps its context.

Standing owner rules are appended to the preambles as soon as they are made.

## Queue runner

`scripts/runqueue.py` launches the next approved item when a slot frees, so a stalled chat no
longer stops the run. (It is not `queue.py`, which would hide Python's own `queue` module from
every script in the folder.)

- **Start it** in an async terminal: `timeout 172800 python3 scripts/runqueue.py run --slots 3`. When the
  client is VS Code, add `--chat-log <session transcript>`; the transcript grows on every tool call. The chat
  waits on it with `runqueue.py wait` (below); start `watch.py` beside it only as a stall watchdog.
- **Queue every approved item** with `runqueue.py add <id> --cmd "<launch command>" [--after <ids>]`
  instead of launching it by hand. `--after` names only queued ids, so queue an item that waits on
  one started by hand after that one merges. Queue reviews with `--no-slot` and a `review.sh` command.
  `add` refuses a command in which the word `copilot` appears (quotes, `$(...)` and backticks removed) or
  that names a readable file holding it, unless the one program it invokes is the skill's `route.py run` or
  `review.sh`, bare or through `nohup`, `timeout`, `env` or a `zsh -c "..."` holding only that (any `;`, `&&`,
  `|` or `$(...)` loses the exemption), or it carries `--unrouted-reason "<text>"`, which is stored with the item.
  A false refusal is acceptable; pass the reason or drop the extra commands.
- **After each merge,** call `runqueue.py done <id>`. Items that wait on it become ready.
- **`runqueue.py status`** shows each item: waiting, ready, running, exited N or done; a pipeline item also
  names its step and what it waits on (a running round, the chat's done file, or a failure with its exit code).
- **Pipelines: queue the whole item once** (owner, 2026-11-02, after the chat cost 7,105 of a run's 22,454 credits
  re-reading its context at every round's end):
  `runqueue.py add <id> --pipeline build,review,suspend:rulings,fix,recheck,suspend:merge --worktree <wt>
  [--brief <prompt>] [--route-args "<route.py run options>"] [--review-args "<review.sh options>"]`. The runner
  launches each step when the one before exits 0: build and fix through `route.py run` (rounds `<id>` and
  `<id>-fix1`), review and re-check through `review.sh` (`<id>-review`, `<id>-rereview`), after
  `scripts/reviewprep.py` writes `REVIEW-DIFF.patch`, `REVIEW-REPORT.md` and the filled prompt (risk blocks from
  the brief's RISK line; the re-check's findings from the fix brief's numbered list). Reviews take no slot. The
  diff starts at the HEAD the build (or fix) step had at its first launch, so a retry does not narrow it;
  `<id>.reviewbase` overrides it after a catch-up with main.
  - **Suspend points** are the two steps that need judgement: `suspend:rulings` (accept or reject each finding)
    and `suspend:merge`. The item waits on the chat, the idle alert names it, and it resumes when
    `<run>/<id>.<name>.done` exists. For rulings, write `<id>-fix1.body.md` (or the whole
    `<id>-fix1.prompt.md`; otherwise the build's prompt with its body swapped is used) and then
    `<id>.rulings.done`; write `none` in it to skip the fix and re-check when nothing blocks. Writing
    `<id>.merge.done` after the merge marks the item done. `add` refuses a done file left from before.
  - **A failed step stops the pipeline**: a non-zero exit (3 capped, 4 errored, 5 brief refused, 12 load,
    124 timed out) or a prep failure (exit 2: no base, an empty diff, no report or findings) waits on the chat
    with its reason. `runqueue.py retry <id>` relaunches it; `retry <id> --passed` marks it passed after the
    chat finished it by hand, and `--report <round>` names the resume round whose report the next review or
    re-check reads (by default the newest of `<round>.jsonl` and `<round>-resumeN.jsonl`). `retry` refuses
    while the step's round may still run. A further fix round is never automatic.
  - **Briefs:** review and re-check read the task and risks from the brief the build or fix was launched with
    (`--brief`, or the fix brief above).
  - **Restarts are safe:** a step that started is never relaunched; its exit code is kept in
    `<run>/<round>.queue-exit`. A restarted runner finds a round still running by its pid, its
    `<run>/<round>.queue-pid` or its command line; one that vanished without an exit code shows `failed ?`.
  - **Finish before starting:** a ready fix, re-check or other later step of a started item takes a freed slot
    before any new build, oldest started first, whatever the build's priority.
  - **Wait in one blocking call:** `runqueue.py wait [--max-min 30]` returns when an item newly needs the chat
    (a suspend, a failed step, a plain item that exited), printing one line each, and exits 1 on timeout.
    Run it in a foreground terminal; it prints a tick each minute.
- **It alerts the owner, not the chat.** When the chat has been idle for `--idle-alert` minutes
  (default 20) and something waits on it, the runner posts a macOS notification and appends the
  line to `ALERT.log`, once for each new item waiting: it does not repeat while the same items
  wait (owner, 2026-11-01). Nothing is sent while the chat is active or nothing waits on it.

## Time budgets and monitoring

A **time budget** is a timebox: a fixed number of minutes the worker should finish in.

- **Defaults:** build 90 min, fix or resume 60, review 30, re-review 20, research 30. Override them
  per run in `budgets.json`.
- **Status table:** `status.py`. Its states are running, STALLED, DIED, ERRORED, CAPPED, done and
  superseded. A capped round shows its credits against the cap. A died or errored round
  reads superseded once a later round of the same item starts.
- **Watchdog:** `watch.py`, in an async terminal; with the queue runner it is only a stall watchdog, and the
  chat waits with `runqueue.py wait`. It exits on:
  - a stall: 20 awake minutes without output;
  - a death;
  - a round that hit its credit cap (CAPPED);
  - a budget overrun, once per worker;
  - no worker running, unless the queue runner has a pipeline step ready or launching;
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
- **Workers may run while a merge gate runs, at most 2 of them** (owner, 2026-10-29: merging one
  item at a time left the slots idle about 45 minutes; three workers plus a gate once held the
  load at 18-28 on 18 CPUs). Queue each merge gate as a slot item with a high `--priority`, so
  with `--slots 3` it takes the next free slot and two workers run beside it.
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
  [references/lessons.md](references/lessons.md), dated, with tags. This skill is public, so its
  lessons and the source-project examples in [references/details.md](references/details.md) follow
  the rule at the top of lessons.md.
- **Running notes** in the run folder: each launch, result, spend, verdict and ruling, with its
  time.
- **Per item:** wall-clock time, spend, blocking findings and fix cycles. `python3 scripts/mine.py "$OW_RUN_DIR" --repo <repo>` reads them from the run folder.
- **Rulings and review quality:** when you rule on a review's Blocker or Major (accept, change its grade, reject, or fail to reproduce it), record it at once with `python3 scripts/rule.py add "$OW_RUN_DIR" <review round> <n> --grade <reviewer's> --ruled <yours> --by <who> --reason "<why>" --area <AREA>`. At the end of a run, `mine.py "$OW_RUN_DIR" --rulings` shows agreement per area and reviewer model, and `mine.py "$OW_RUN_DIR" --quality` shows the first-review clean rate (over first reviews), blockers per review (over first reviews with an orchestrator count; a reviewer's clean verdict with no ruling, `.accepted` line or fix brief counts as 0 by design, so a run with no rulings still has a rate), fix rounds per item (over every item in the run with at least one fix round, its build and first review in the run or not; one without them is listed as "provenance missing"), the share of credits that went to review and fixes, and the cause Pareto. For an item with no rulings, write `<run>/<item>.accepted` with one line (`none` or `N blocking`). Each new rubric version gets a blind second grade: `python3 scripts/sample.py <findings.csv> --n 40 --strata area --seed <N> --out <tmp>`, a second grader fills `sheet.csv`, then `python3 scripts/kappa.py <key.csv> <sheet.csv> --column <grade>`.
- **Project timeline:** each run names its project's archive folder with `state.py init --archive <folder>`; `python3 scripts/timeline.py --export` writes `timeline.html` across all the project's runs and `spend-by-day.md` there ([details](references/details.md#timeline-export)).
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
