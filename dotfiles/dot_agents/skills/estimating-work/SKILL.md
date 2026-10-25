---
name: estimating-work
description: Estimate work in minutes from measured pace, and plan, run and report a window of unattended work. Use when asked for an estimate or "how long will this take", when planning work for a set time, or when the owner leaves the agent to work alone for some hours. Not for project schedules, story points or other people's work.
---

# estimating-work

An item count says nothing about time. An away run of 12 items stopped after 64 of 360 minutes
because no item had an estimate, there was no overflow, and half the items ended in a question for
the owner. Estimate in minutes from [references/pace.md](references/pace.md), and correct that
table after every run.

## Before

1. Run `date`. Write down the window's end and the stop time: the end minus 30 minutes for the
   wrap-up.
2. Split the work into items that each end in a commit or a finished artifact, not in a question.
   Ask every decision an item needs now, before the owner leaves. An item still missing a decision
   moves to the end of the plan.
3. Estimate each item in minutes from the closest row in the pace table. Mark an estimate with no
   matching row as a guess.
4. Fill 1.5 to 2 times the window, in ordered tiers: the plan, then overflow. Say what is out of
   scope.

## During

- After each item, run `date` and log the item, its estimate and its actual in the state file.
- When an item blocks on a decision, write the question down and take the next item.
- Spare time buys depth, such as more test cases or an independent review, never an early stop.
- Stop only at the stop time, or when every tier is empty.

## After

- Report estimate against actual for every item, in the final message and the state file.
- Add the run to the runs table in `references/pace.md`. When the actuals miss a pace row in the
  same direction run after run, change the row.
