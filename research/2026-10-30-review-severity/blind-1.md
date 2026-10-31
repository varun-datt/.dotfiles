# Blind second grade, round 1 (2026-10-31)

**Result: kappa 0.537 on six levels (agreement 67.5%, 27 of 40), under the 0.6 aim.** The rubric is not yet consistent enough to trust its demotions without a check.

How it ran: `sample.py findings.csv --n 40 --strata severity_rubric --seed 31` drew the sheet (strata by grade, not by area, so every level appears; `sample.py` flagged S22, S23 and S31 as naming a ruling or a grade, and they were left as written). GPT-6.1 Sol graded it blind from `rubric.md` and the one-line text only, in 1.3 minutes for 10.6 credits. `kappa.py key.csv graded.csv --column severity_rubric` scored it. Files: [sheet.csv](blind-1/sheet.csv), [key.csv](blind-1/key.csv) (the first grade), [graded.csv](blind-1/graded.csv).

## Where the graders split

| Pattern | Rows | First grade → blind grade |
|---|---|---|
| Likelihood: L3 "contrived" against L1 "normal use" | S07, S25, S27, S32 | Minor → Major or Blocker |
| Likelihood: L2 against L1 | S26, S08 | Minor ↔ Major |
| Impact: harm (I1) against wrong (I2) | S34, S37 | Blocker ↔ Major |
| Impact: degraded (I3) against cosmetic (I4) | S05 | Major → Minor |
| Test or visibility preference read as Nit | S28, S39 | Minor → Nit |
| "Already ruled" has no level of its own | S23 | Minor → Correction |
| Pre-existing not visible in the text | S24 | Pre-existing → Minor |

Six of the thirteen splits are on likelihood, four of them on the L3 band: the case against in the research note named exactly this. Five of the six likelihood splits went upward (more severe) in the blind grade, so the first grade's demotions are the ones in doubt.

## What it does and does not show (INFERRED)

- The blind grader saw a one-line paraphrase; the first grader saw the review, the code and the owner's rulings. It marked 11 of 40 rows "thin". Part of the gap is context, not the rubric. A fair second round gives both graders the same text: the finding as the reviewer wrote it.
- S25 and S27 (canvas external loads, WebRTC leak): the first grade's reason for L3 is not in the CSV (OPEN). Under the rubric's L1 rule ("text from outside systems is untrusted in normal use") they are L1 unless the input is shown to be the owner's own.

## Proposed definition changes (for the owner)

1. L3: add "the input is the owner's own and never comes from an outside system" as an explicit L3 condition, so S25 and S27 grade the same way twice.
2. I1 against I2: add "a draft or typed text the owner did not save is lost" to I1 (S37), and "wrong but visible and recoverable" to I2 (S34).
3. Give "Already ruled" its own output: Correction.
4. Repeat the blind grade with full finding text before changing the band; aim kappa 0.6 or more.
