# Valuing work

How to decide what to do first, in any repository: when proposing work, ranking a backlog,
choosing a window's plan, or deciding whether a piece of debt or a flaky test is worth fixing.
Gates first, then cost of delay divided by the scarce resource. Research behind it: the wiki
notes `00-inbox/research-work-value/findings-value-methods.md`,
`findings-debt-and-flakes.md` and `findings-measurable-inputs.md`.

## 1. Gates

Fix now, before any ranking, an item that:

- hides real failures (a test that cannot fail, a check that reads green on an error);
- loses data, or opens a security hole;
- wastes credits right now, or makes work redo itself;
- blocks merges with no retry;
- breaks a flow in daily use.

A gate is not priced: a number would price trust and data loss too low.

## 2. Cost of delay

Cost of delay = value x urgency x confidence (Reinertsen's CD3; SAFe's WSJF uses the same idea).

| Value | When |
| --- | --- |
| 8 | Over 30 owner minutes a week; a gate line of the current milestone; protects data, secrets or the merge path |
| 3 | 5 to 30 owner minutes a week; 30 to 120 lane minutes a week; a should-have for the current milestone |
| 1 | The rest, polish included |

- **Urgency:** 4 now (each week of delay costs more, or a current milestone waits on it), 2 soon,
  1 whenever.
- **Confidence:** 1.0 measured, 0.8 reasoned from evidence, 0.5 a guess.
- A spike is valued by the decision it unblocks. An enabler is scored as one bundle with what it
  enables (log it with `--serves`).

## 3. Divide by the scarce resource

- **Queue A**, an item that needs more than 2 owner minutes (approving behaviours, reading,
  ruling, looking at renders): score = cost of delay / owner minutes.
- **Queue B**, an item that needs no owner time: score = cost of delay / the agent's P50 minutes
  for its kind (`estimates.py estimate --kind <kind>`).
- No kind of work gets a share of time: the scores alone fill a plan, enablers first. The mix of
  kinds is reported after a run ([work-mix.md](work-mix.md)), never planned.

## 4. Debt and flaky tests

A debt item's cost of delay is its interest, in agent-minute equivalents a week:

- `I = N x (p_fail x C_fail + p_retry x C_retry)`: N checks a week that run the code or test,
  the chance a check fails on it after retries, and the chance it passes only on retry.
- `C_fail = t_rerun + t_diag + a x w x t_owner + b x t_block`: rerun and diagnosis minutes, the
  share of failures that reach the owner times the owner's minutes, and the share that block a
  merge times the lane's wait. `w` = 10 agent minutes per owner minute until it is measured.
- Rank it against features with `I / fix hours`, the fix including its proof under load.
- `estimates.py interest --checks <check log> [--debt <register>]` gives `I` for each test that
  failed or passed only on retry, and for each open debt row that names one. It measures N,
  `p_fail`, `p_retry`, `t_rerun` (the median check length), `t_block` (the median wait from a
  failing check to the next passing check on its branch) and `b` (the share of failing checks
  run to merge), and lists the items whose start-to-end window on that repository and branch held
  a failing check. `t_diag`, `a`, `t_owner`, `w` and `C_retry` are judged defaults, as are
  `t_rerun`, `t_block` and `b` when the log cannot measure them; each row says which; `--judge
  NAME=VALUE` replaces one.

Then one rule per item:

| Rule | When |
| --- | --- |
| Fix now | A gate above, or its score beats the next item's |
| Quarantine | Fails after retry at least 2 times in 20 checks and the fix takes over an hour or is uncertain. It leaves the merge gate, keeps running off it, gets a debt row, and returns after 20 clean runs |
| Batch | It lives in a file a planned item touches: fix it inside that item |
| Accept | Rare, absorbed by retry, blocks no merge, low score. Keep the row; re-grade after 3 runs |
| Delete | The test adds no unique coverage, or a smaller test can replace it. Never the first response |

A debt row names its test with a `[tests: <file> > <title>]` suffix on its scenario, so failures
count per row.

## 5. The proposal card

Every proposal carries one card, each input marked measured, proxy or judged, with its source:

```text
Item: <name (id)>   Queue: A | B   Gate: none | <which>
Value: 3 (judged: ...)   Urgency: 2 (...)   Confidence: 0.8
Owner minutes: 15 (judged)   Agent P50: 23 min (history: feature-gated)
Score: 0.32   Debt rule: fix now | quarantine | batch | accept | delete
Measured: ...   Judged: ...
```

## 6. Who rules, and when to rescore

- The agent scores and proposes everything. The owner rules only on value 8, urgency now, a
  confidence of 0.5 among the top five, and the pick from queue A.
- Rescore an item when something it rests on changes (an item done, a new failure kind, a
  ruling); refresh measured rates weekly. Rescoring everything each round costs more than it
  tells.

## Sources

- Cost of delay divided by duration and urgency profiles:
  <https://blackswanfarming.com/cost-of-delay-divided-by-duration/>,
  <https://blackswanfarming.com/urgency-profiles/>
- Flaky tests: Google (<https://testing.googleblog.com/2016/05/flaky-tests-at-google-and-how-we.html>),
  GitHub (<https://github.blog/engineering/engineering-principles/reducing-flaky-builds-by-18x/>),
  Slack (<https://slack.engineering/handling-flaky-tests-at-scale-auto-detection-suppression/>),
  Parry et al. (<https://o-parry.github.io/papers/2021a.pdf>)
- Debt as interest on change: <https://martinfowler.com/bliki/TechnicalDebt.html>; hotspots:
  <https://codescene.io/docs/guides/technical/hotspots.html>
