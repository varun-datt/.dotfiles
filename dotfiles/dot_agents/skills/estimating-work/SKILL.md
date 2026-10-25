---
name: estimating-work
description: Estimate work in minutes from measured pace, and plan, run and report a window of unattended work. Use when asked for an estimate or "how long will this take", when planning work for a set time, or when the owner leaves the agent to work alone for some hours. Not for project schedules, story points or other people's work.
---

# estimating-work

A language model estimates in human time: its pre-task estimates "overshoot actual duration by
4–7×" (arXiv 2604.00010). On 2026-10-25 this agent estimated 49 items at 1,245 minutes and spent
358; no estimate went below 10 minutes while 40 items took under 10. So never judge minutes. Take
the outside view: each kind of item's measured pace, corrected by this agent's own history of
estimate against actual, forecast by Monte Carlo. Evidence and method: the wiki note
`00-inbox/research-agent-work-planning/findings-estimation.md`.

`scripts/estimates.py` keeps the history in `~/.agents/state/estimates.jsonl` (or `$ESTIMATES_LOG`).

## Before

1. Run `date`. Write down the window's end and the stop time: the end minus 30 minutes for the
   wrap-up.
2. Ask the owner, in one question round before they leave:
   - the work mix; the default is about 70% features, 15% bugs and fixes, 10% spikes that unblock a
     decision, 5% docs ([references/work-mix.md](references/work-mix.md));
   - every decision the planned items need. A UX decision not taken is built as the recommended
     option, chosen from human-factors research (the `visual-house-style` skill's attention and
     interaction rules), and flagged for review.
3. Split the work into items that each end in a commit or a finished artifact, not in a question.
   One feature at a time, its tests and doc updates inside it.
4. Give each item a kind from [references/pace.md](references/pace.md) and take its estimate from
   the history: `estimates.py estimate --kind fix` gives the P50 and P90. A kind with fewer than 5
   logged items gets a judged estimate marked as a guess.
5. Forecast: write the plan as JSON (`[{"id", "kind", "estimate"}]`) and run
   `estimates.py forecast --plan plan.json --window <minutes to the stop time>`. Fill the plan to
   the window's P50, then add an overflow tier from the backlog, in the owner's mix, up to what
   fits at P90. Say what is out of scope.

## During

- Stamp every item: `estimates.py start --id <id> --kind <kind> --estimate <min> --run <run>` before
  it, `estimates.py end --id <id>` after its commit. Never work out minutes by hand.
- Re-run the forecast after each item, and move the overflow line if it shifts.
- When an item blocks on a decision, write the question down and take the next item.
- Polish found on the way becomes a backlog item, not work now.
- When the plan is done, spare time buys depth: more test cases, and at most two second-model review
  rounds per run, fixing high severity only; lower findings go to the backlog.
- Stop only at the stop time, or when every tier is empty.

## After

- `estimates.py report --run <run>`: estimate against actual, how many came within 25%, and minutes
  by kind against the mix asked for. Put it in the final message and the state file.
- Regenerate the pace table with `estimates.py kinds` and add the run to its runs table.
- Run the tests after changing the script: `python3 -B scripts/test_estimates.py`.
