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
5. Forecast: write the plan as JSON (`[{"id", "kind", "estimate", "method"}]`) and run
   `estimates.py forecast --plan plan.json --window <minutes to the stop time>`. It draws `history`
   items from their kind's logged actuals and corrects the others by their own method's history.
   Fill the plan to the window's P50, then add an overflow tier from the backlog, in the owner's
   mix, up to what fits at P90. Say what is out of scope.
6. Arm the run guard: `estimates.py arm --run <run> --until <stop time HH:MM> --plan plan.json`.
   While it is armed, a Stop hook (`~/.copilot/hooks/run-guard.json`) refuses to let a turn end
   before the stop time while a planned item has no `end`. Write the plan, the stop time and the
   owner's decisions into the session memory too: a compaction or a terminal notification can
   start a turn with all of it out of view (2026-10-26).

## During

- Stamp every item: `estimates.py start --id <id> --kind <kind> --estimate <min> --method <method>
  --run <run>` before it (an enabler adds `--serves <feature id>`), `estimates.py end --id <id>`
  after its commit. Never work out minutes by hand.
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
- Keep the todo list current: after a reset it is the one list still in view, and a stale one makes
  a run look unstarted.
- Polish found on the way becomes a backlog item, not work now.
- When the plan is done, spare time buys depth: more test cases, and at most two second-model review
  rounds per run, fixing high severity only; lower findings go to the backlog.
- Stop only at the stop time, or when every tier is empty.

## After

- `estimates.py disarm` first, so the wrap-up's final message can end the turn.
- `estimates.py report --run <run>`: estimate against actual, how many came within 25%, minutes by
  kind, and features with their enablers as one share, against the mix asked for. Put it in the
  final message and the state file.
- Regenerate the pace table with `estimates.py kinds` and add the run to its runs table.
- Run the tests after changing the script: `python3 -B scripts/test_estimates.py`.
