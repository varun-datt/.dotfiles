---
name: estimating-work
description: Estimate work in minutes from measured pace, and plan, run and report a window of unattended work. Use when asked for an estimate or "how long will this take", when planning work for a set time, when the owner approves a list of items to build, or when the owner leaves the agent to work alone for some hours. Not for project schedules, story points or other people's work.
---

# estimating-work

A language model estimates in human time: its pre-task estimates "overshoot actual duration by
4–7×" (arXiv 2604.00010), and an agent's estimate "is often from training data, which is based on
human speed" (agent-estimate, Show HN). On 2026-10-25 this agent estimated 49 items at 1,245
minutes and spent 358; no estimate went below 10 minutes while 40 items took under 10. So never
judge minutes. Estimate from evidence, best first: the kind's logged history (the outside view);
else a count of rounds, the unit agent-speed estimators use; judged minutes only as a last resort,
corrected by this agent's judged history. Forecast by Monte Carlo. Evidence and method: the wiki
note `00-inbox/research-agent-work-planning/findings-estimation.md`.

`scripts/estimates.py` keeps the history in `~/.agents/state/estimates.jsonl` (or `$ESTIMATES_LOG`).

## Before

1. Run `date`. Write down the window's end and the stop time: the end minus 30 minutes for the
   wrap-up.
2. Ask the owner, in one question round before they leave:
   - the work mix; the default is about 70% features, 15% bugs and fixes, 10% spikes that unblock a
     decision, 5% docs, and it bends to dependencies: an enabler a planned feature needs goes first
     and counts toward that feature ([references/work-mix.md](references/work-mix.md));
   - every decision the planned items need. A UX decision not taken is built as the recommended
     option, chosen from human-factors research (the `visual-house-style` skill's attention and
     interaction rules), and flagged for review.
   - one budget for paid live runs (a real engine that spends the owner's credits): estimate each
     item's paid calls (messages, side questions, summaries, workers it starts) and the runs they
     group into, and ask once. Runs inside the approved budget need no further ask; ask again only
     to go over it (owner, 2026-10-25: "do not ask before each live Copilot run, ask approximate
     whatever you need upfront").
3. Split the work into items that each end in a commit or a finished artifact, not in a question.
   One feature at a time, its tests and doc updates inside it.
4. Give each item a kind from [references/pace.md](references/pace.md) and an estimate with its
   method, best first:
   - `history`: `estimates.py estimate --kind fix` gives the P50 and P90 once the kind has 5
     logged items.
   - `rounds`: count the think, write, run and verify cycles the item needs with agent-estimation's
     anchors (1–2 boilerplate, 3–5 moderate, 5–10 exploratory, 8–15 high uncertainty), add 10–20%
     for joining parts, and run `estimates.py estimate --rounds <n> --risk <1.0 to 2.0>` (3 minutes
     a round until the log corrects it).
   - `judged`: a minute figure, only when neither works, flagged as a guess.

   An item a person would need hours for is where agents fail more often (METR: the 80% time
   horizon is about a fifth of the 50% one), so split it until each piece ends in a commit.
5. Forecast: write the plan as JSON (`[{"id", "what", "kind", "estimate", "method"}]`, where
   `what` is one line saying what the item is: after a compaction, ids alone lost what four items
   meant, 2026-10-26) and run
   `estimates.py forecast --plan plan.json --window <minutes to the stop time>`. It draws `history`
   items from their kind's logged actuals and corrects the others by their own method's history.
   When workers run in parallel (the queue runner's `--slots N`), add `--slots N`: `worker-*` kinds
   share N slots, an item with `"slot": false` runs beside them (a review or research), any other
   kind runs one at a time in the chat's own lane, and `"after": ["<id>", ...]` holds an item until
   those earlier items finish; a waiting item holds no slot. The output adds `slots` and
   `sequential_p50` (the one-at-a-time sum). `--slots 1` reproduces the old numbers only for plans
   without `slot` or `after` fields: with `slot: false` an item runs beside the single slot.
   Fill the plan to the window's P50, then add an overflow tier from the backlog, in the owner's
   mix, up to what fits at P90. Say what is out of scope.
6. Arm the run guard: `estimates.py arm --run <run> --until <stop time HH:MM> --session <chat id>
   --plan plan.json`. While it is armed, a Stop hook (`~/.copilot/hooks/run-guard.json`) refuses to
   let that chat's turn end before the stop time while a planned item has no `end`. The chat id in
   VS Code is the last folder of the session's debug-log path. Other agent sessions (SDK and CLI
   runs) load the same hook, so the guard holds only the chat named by `--session` (2026-10-26:
   unscoped, it held an SDK spike's autopilot session). Each check is logged to
   `~/.agents/state/run-guard.log`. Write the plan, the stop time and the
   owner's decisions into the session memory too: a compaction or a terminal notification can
   start a turn with all of it out of view (2026-10-26).

## During

- Stamp every item: `estimates.py start --id <id> --kind <kind> --estimate <min> --method <method>
  --run <run>` before it (an enabler adds `--serves <feature id>`), `estimates.py end --id <id>`
  after its commit. Never work out minutes by hand. An item another item covered, or one logged by
  mistake, is closed with `estimates.py drop --id <id> --reason "covered by <id>"` instead of
  `end`, so no history or report counts it (2026-10-26: two covered items logged 0 minutes).
- Worker items (`copilot -p` runs of the orchestrator-workers skill) have their own kinds:
  `worker-build`, `worker-fix`, `worker-review`, `worker-research`. Workers took 7 to 66 minutes
  per build on 2026-10-28 (median 31, 14 builds) and reviews 2 to 48 (median 6, 11 reviews), against
  4 to 8 minutes for the in-chat items behind `fix` and `feature`, so never mix them. Import a run
  folder's history with `estimates.py import-run <run folder>` (it runs the sibling skill's
  `mine.py --json`, skips items already logged), then `estimates.py estimate --kind worker-build`.
  Merge and resume rounds are not imported. The imported actual is `active_min`: the sum of the
  gaps between a round's consecutive events, leaving out any gap over 10 minutes (`IDLE_GAP` in
  `mine.py`), so a round resumed hours later does not count the wait; `wall_min` is kept as its own
  field. For an id with an imported row, history uses that row only; the hand-logged row's estimate
  is kept, so `report` compares it with the imported `active_min`.
- Per-item credits for workers come from the worker's own log (`mine.py`), not the account
  counter: the counter's delta double counts when workers overlap and includes the owner's other
  chats. Imported items carry `credits_source: "log"`; stamped in-chat items show
  `"account counter"`. The counter stays only as the whole account's total.
- Give `start` a credit estimate too, `--credits <n>`. `start` and `end` each read the account's
  credits-used figure (`gh api /copilot_internal/user`, undocumented) and `end` stores the
  difference as the item's credit actual (in-chat items only). A failed read never blocks a stamp; it marks the
  item's credits unknown, with a reason code (`gh-missing`, `gh-exit-<n>`, `timeout`,
  `gh-error`, `bad-json`, `no-quota`, `no-figure`). On 2026-10-28, 21 reads 15 s apart from 11:16:50 to
  11:22:06, while this session made paid calls, read 858929 first and 858929 last: it did
  not move in those five minutes. That shows nothing about how often it moves; the lag after a
  known spend is not yet measured.
- Re-run the forecast after each item, and move the overflow line if it shifts.
- Count each live run's paid calls against the approved budget, and ask before a run that would
  go over it.
- When a feature turns out to need an enabler (a fix, a spike, some debt), take the enabler next and
  re-forecast; never hold it back to keep the mix.
- Carry each item to completion or to a blocker (owner, 2026-10-25). Where a case is unclear, let
  research decide it, say so in the commit and the plan, and keep it for the owner's review.
- When an item blocks on a decision, write the question down and take the next item. A question
  that blocks nothing never ends a turn: it goes in the session memory for the final report. Only
  when something blocks every remaining item, `estimates.py block --reason "<what, why>"` lets the
  turn end; the next `start` re-arms the guard.
- A turn that starts without the plan in view reads the session memory before anything else: on
  2026-10-26 a turn begun by a terminal notification lost the plan and ended on a question about
  an unrelated failing test, mid-run.
- Unattended runs send each item to a `copilot -p` worker under `timeout`, through the
  orchestrator-workers skill: an in-chat sub-agent call has no timeout, and one stalled a run for
  3 h 11 min (2026-10-27). Keep in-chat sub-agents (`runSubagent`, agent `worker`) for short
  attended work. Brief a worker with the item's `what`, the owner's rulings and the files; read its
  diff and look at its renders before the next item.
- Keep the todo list current: after a reset it is the one list still in view, and a stale one makes
  a run look unstarted.
- Polish found on the way becomes a backlog item, not work now.
- When the plan is done, spare time buys depth: more test cases, and at most two second-model review
  rounds per run, fixing high severity only; lower findings go to the backlog.
- Stop only at the stop time, or when every tier is empty.

## After

- `estimates.py disarm` first, so the wrap-up's final message can end the turn.
- `estimates.py report --run <run>`: estimate against actual, how many came within 25%, minutes by
  kind, and features with their enablers as one share, against the mix asked for. Its `credits`
  part lists each item's minutes and credits, estimate beside actual, and the run's totals. The
  figure counts every session's spend on the account, so an item whose window overlaps another's
  is marked `overlaps`: their actuals double count the shared spend. Put it in the final message
  and the state file.
- Regenerate the pace table with `estimates.py kinds` and add the run to its runs table.
- Run the tests after changing the script: `python3 -B scripts/test_estimates.py`.
