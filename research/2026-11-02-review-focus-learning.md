# Review focus learning: a record that steers what each review looks at

Research for task rb1, 2026-11-02. Status: proposal for the owner. Data: [findings.csv](2026-11-02-review-focus-learning/findings.csv) (676 graded findings) and [reviews.csv](2026-11-02-review-focus-learning/reviews.csv) (149 graded rounds). Every number below comes from those two files unless a source is named.

## In short

- **Reviews pay; fixes are where the credits go.** First reviews earned 11.9 value points per 100 credits under the starting weights (64 reviews, 4,874 credits). Only 6 of 64 earned nothing, and 4 of those 6 earned nothing only because nobody ruled on their findings. Fix rounds cost 22,048 credits, about 61 per accepted finding. Re-reviews earned 4.1 per 100, and half of them (34 of 69) found nothing. So the owner's short re-review check is backed by the data, and there is little to save by skipping first reviews. (VERIFIED from the CSVs)
- **Keep the starting weights, with five changes.** The ranking of reviews hardly moves when the harm weight is 5 or 20 instead of 10 (rank correlation 0.98 and 0.99). Contrived findings (L3) were rejected 22% of the time, against 4–5% for L1 and L2, so L3 stays at 0.1. The five changes:
  - a finding the orchestrator demoted counts at most as "degraded";
  - decay counts reviews, not days (half-life of 40 first reviews), because the whole history spans 7 days;
  - a repeated kind reaches the owner only when it spans 4 or more runs and is worth 20 points or more (8 kinds instead of 44);
  - every blocking finding must carry a ruling before its review is scored;
  - an escape is doubled for its area's prior but also counts as a miss against the focus that passed it. (INFERRED from the data)
- **The record**:
  - `findings.jsonl`, `reviews.jsonl` and `escapes.jsonl` in each run folder, next to `rulings.jsonl` and `routes.jsonl`;
  - `mine.py` fills it. It already reads the reviewers' cause tags (`mine.py:752`, `:834`), so the brief's "it does not today" is out of date; what it lacks is the link from each tag to its finding, ruling and cost;
  - `route.py` reuses its Beta posterior and Thompson draw to pick 2 or 3 focus blocks per review, plus one explore block in 1 review out of 5;
  - `review.sh` fills the existing `{{FOCUS_AREAS_OR_DELETE}}` slot (`assets/review.md:54`).
- **Skip by rule for now, not by prediction.** A back-test that predicted each review's value from earlier reviews of the same areas barely beat chance (rank correlation 0.21, 42 reviews). Skipping its lowest quarter would have saved 18% of credits, lost 16% of value, and caught none of the 6 reviews that earned under 2 points. So skip only changes that touch no focus area (2 of 44 past reviews). Switch on a learned skip only after it passes a stated back-test bar. (VERIFIED back-test; the rule is INFERRED)
- **The requirement script catches less than hoped.** Of 45 blocking findings whose only fault was an unmet requirement, a failing test named for that requirement would have caught 12, would have partly caught 14, and would have missed 19. The reason: the author writes the test from their own reading of the requirement. So the script, plus a "must fail on the base code" check, replaces the review's checklist step. The four focus blocks still read the brief's SHALL lines. (VERIFIED counts; the judgment per row is INFERRED)

## Method and the dataset

**Sources graded** (VERIFIED):
- every run folder under `~/.local/state/orchestrator-workers/` whose name starts `amc-`: 10-27, 10-28, 10-29, 10-30, 10-31, 11-01, 11-01-research and 11-02;
- one dotfiles item, the router launcher, which was reviewed inside run 10-30.

**Rows**: one per finding (676). The columns are in the CSV header and follow a shared grading key:
- harm level (impact I1–I4) and likelihood (L1–L3), from the rubric;
- cause tag;
- focus: the first of harm, workflow, surprise, requirement, test, report or debt that applies;
- code area: turn-state, store, folders-perms, fencing, ui:<view>, tests-gates, skill-scripts, kb, docs or other;
- ruling: accepted, demoted, rejected, not-reproduced or not-ruled;
- origin: new, fix-left, fix-introduced or pre;
- for unmet requirements, whether a named failing test would have caught the finding.

**Where the rulings came from**:
- the fix brief's "ACCEPTED, fix these" and "REJECTED by the orchestrator" lists;
- fix reports that said "could not reproduce";
- `rulings.jsonl`;
- the downgrades in `amc-2026-11-02/discuss.md`.

**How the rows were graded**:
- 10-27 to 10-30 (228 rows): rows were mapped from the earlier review-severity CSV and joined to the build-quality cause tags (210 joined; 18 kept without a cause). Focus and code area were set by rule (INFERRED).
- 10-31 (164 rows) and 11-02 (201 rows): two grader workers read each report against the key.
- 83 rows were graded by hand or from `rulings.jsonl`.

The `grade_source` column says which method made each row.

**Not graded, or graded only in part** (VERIFIED):
- **No final message**: `canvas-b-rereview3` and `canvas-b-rereview4` (10-29), and `p4-review` and `p5-review` (10-31, about 110 credits each). They are left out of worth; the re-runs `p4-review2` and `p5-review2` are in.
- **No usable findings**: `canvas-b-rereview2` was blocked and returned no evidence, and `g10a-post-review` never ran.
- **Research critique message missing**: `rw1-critique`; its rulings were used instead.
- **hr1-critique**: count only (6 rows), no detail.
- **10-27 in-chat reviews**: 26 rows with no credit record, so they are left out of worth per credit.
- **No ruling exists**: 95 rows are not-ruled, either because they were non-blocking or because no fix round followed (`s2`, `p2`, `d4`).
- **Grader conventions** (INFERRED): non-standard tags were mapped (RENDER→EDGE, PARSER→BOUND); the 10-31 ACCEPTANCE lines were not counted as numbered requirements.

**What "worth" means**:
- Worth is value points per 100 credits.
- A finding's points are its harm weight × its likelihood weight, counted only if it was accepted (or, under the starting weights, demoted).
- Credits are the round's `ai_credits=` total.

## What established practice gives this design

Each quote was read with `tvly extract` (VERIFIED); the Lewis paper through its Wayback Machine copy, also with tvly. Three quotes were checked a second time. The last column is INFERRED.

| Practice | Source read | What it says | Gives this design |
|---|---|---|---|
| Risk-based testing (ISTQB CTFL v4.0) | https://www.gasq.org/files/content/gasq/downloads/certification/ISTQB/Foundation%20Level/ISTQB_CTFL_Syllabus-v4.0%20.pdf | "the risk level is calculated as the multiplication of risk likelihood and risk impact"; "Defects cluster together"; "Tests wear out"; "Traceability of test cases to requirements can verify that the requirements are covered" | The harm × likelihood grid; area clustering; exploration; the SHALL-to-test map |
| OWASP risk rating | https://owasp.org/www-community/OWASP_Risk_Rating_Methodology | "Risk = Likelihood * Impact"; compare "the ratings produced by the model with ratings produced by a team of experts"; "not all risks are worth fixing" | Fixed starting weights, tuned by the fix round's accept or reject |
| Decay of change history (Graves et al.) | https://cs.uwaterloo.ca/~m2nagapp/courses/CS846/1171/papers/graves_tse98.pdf | old changes "downweighted by a factor of about 50 percent per year" | Decay is sound; the rate must be set per project |
| Relative churn (Nagappan and Ball) | https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/icse05churn.pdf | relative churn "highly predictive", "accuracy of 89.0 percent" | Size and churn as a prior |
| FixCache (Kim, Zimmermann et al.) and its re-test (Rahman et al.) | https://www.cs.ucdavis.edu/~devanbu/teaching/289/Schedule_files/Kim-Predicting.pdf; https://softwareprocess.es/pubs/rahman2011FSE-bugcache.pdf | "10% of the source code files ... account for 73%-95% of faults"; a plain count of recent fixes is "in a statistical dead heat" | Count accepted findings per area; nothing cleverer is needed |
| Effort-aware prediction (Kamei et al.) | https://das.encs.concordia.ca/pdf/Kamei_TSE2013.pdf | "20 percent of all effort suffices to identify 35 percent" of risky changes | Judge worth per credit, not per review |
| Bug prediction at Google (Lewis et al.) | https://web.archive.org/web/20160316010910/http://static.googleusercontent.com/media/research.google.com/en/us/pubs/archive/41145.pdf; https://google-engtools.blogspot.com/2011/12/bug-prediction-at-google.html | "found no identifiable change in developer behavior"; output must be "actionable"; an old fix's influence "tends towards 0" | Each focus arrives as a block of questions, never a score |
| Hotspots (CodeScene, code-maat) | https://codescene.io/docs/guides/technical/hotspots.html; https://github.com/adamtornhill/code-maat | "high change frequency and low Code Health"; "Hotspots point to code review candidates"; change coupling, "--max-changeset-size ... 30" | The churn prior; later, weight areas that change together |
| Useful review comments (Bosu et al.) | https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/bosu2015useful.pdf | "almost 69% comments" useful or somewhat useful; useful = code changed "within one line distance"; more files, fewer valuable comments | "Accepted" is the right signal |
| Review at Microsoft (Czerwonka et al.) | https://www.microsoft.com/en-us/research/wp-content/uploads/2015/05/PID3556473.pdf | "only about 15% of comments ... indicate a possible defect"; a reviewer new to an area "only 33%" useful, later "about 67%" | Weight by harm; give each review its area's history |
| Review defect types (Mäntylä and Lassenius) | https://mmantyla.github.io/wiki/What+Types+of+Defects+Are+Really+Discovered+in+Code+Reviews%253F.html | "75 percent of defects found during the review do not affect the visible functionality" | Without harm weights, maintainability findings dominate |
| Review at Google (Sadowski et al.) | https://sback.it/publications/icse2018seip.pdf | aims are "education, maintaining norms, gatekeeping, and accident prevention" | Defect-finding is one aim; debt focus stays |
| Cisco review study | https://static0.smartbear.co/support/media/resources/cc/book/code-review-cisco-case-study.pdf | "61% of the reviews uncovered no defects"; "under 200, not to exceed 400" lines | Size is a prior; big diffs get less from review |
| Risky files reviewed less (Thongtanunam et al.) | https://rebels.cs.uwaterloo.ca/papers/msr2015_thongtanunam.pdf | risky files "tend to be reviewed less rigorously" | Steer focus toward risky areas |
| Defect removal efficiency (Capers Jones) | https://www.ppi-int.com/wp-content/uploads/2021/01/Software-Defect-Removal-Efficiency.pdf | DRE = "percentage of defects found and repaired prior to release", "After a fixed period of 90 days" (ISBSG "release plus 30 days"); inspections "more than 65% efficient" | An escape is leakage per review over a stated window; no source for the factor of 2 (OPEN) |
| Learned test ordering (RETECS; COLEMAN) | https://arxiv.org/pdf/1811.04122; https://github.com/jacksonpradolima/coleman4hcs | "better to reward each test case's priority individually"; Thompson sampling with "sliding window" variants | Reward each focus separately; forget old outcomes |
| Test selection at Facebook | https://arxiv.org/html/1810.05286v2 | retrains weekly; samples "close to a quarter of submitted code changes" | 1 in 5 exploration is in line |
| Thompson sampling tutorial (Russo et al.) | https://web.stanford.edu/~bvr/pubs/TS_Tutorial.pdf | with a window "The agent never ceases to explore" | Decay keeps the sampler exploring |
| Risk-based skip at Meta (RADAR) | https://arxiv.org/html/2605.30208v1 | uses risk "to identify diffs that do not need human review"; threshold moved "from the 25th to the 50th percentile"; "not a causal estimate" | Start strict; loosen a step at a time while escapes stay flat |
| Tricorder at Google | https://research.google.com/pubs/archive/43322.pdf | "A rate ≥10% puts the analyzer on probation"; above 25% "turn the analyzer off"; best analysers "0-3%" | A not-useful rate per focus, with probation and shut-off |
| Mutation testing at Google | https://arxiv.org/html/2102.11378v2 | "Mutants are only generated for lines that are changed"; "a median of only 7 mutants per changelist"; productive mutants "from 15% to 89%" | The requirement script's break check |

**Could not be traced to a primary source:**
- Mende and Koschke's effort-aware models (known only through Kamei);
- the Cisco "spot checking 20% to 33%" claim (known only through SmartBear's page; not in the Cisco chapter);
- the brief's "Bosu 65% useful" figure. The paper says 69% (OPEN).

## What this project's history shows

All figures in this section are VERIFIED from the CSVs. Interpretations are marked.

**What each kind of round earned** (starting weights):

| Round kind | Rounds | Credits | Value | Per 100 credits | Median | Earned nothing |
|---|---|---|---|---|---|---|
| First review | 62 | 4,874 | 581 | 11.9 | 9.9 | 6 |
| Review after merge | 2 | 137 | 12.5 | 9.1 | 8.9 | 0 |
| Re-review | 69 | 3,680 | 149 | 4.1 | 0.8 | 34 |
| Research critique | 16 | 1,801 | 244 | 13.6 | 13.9 | 3 |

**Fix rounds dominate the cost.**
- Fix rounds cost 22,048 credits for 360 accepted findings, about 61 credits each. By comparison, first reviews cost about 14 credits per accepted or demoted finding.
- The 11-02 PLAN row says the same: "fix rounds cost 6,569 credits against 6,421 for builds" (`agent-mission-control/PLAN.md:319`).
- INFERRED: preventing a kind of fault (a structural fix, a gate) is worth about four times as much as finding it in review.

**Rejection rate by likelihood** (code rows, not-useful = rejected or not reproduced ÷ ruled):

| Likelihood | Not useful |
|---|---|
| L1 normal use | 4% |
| L2 plausible | 5% |
| L3 contrived | 22% |

- Pre-existing findings (origin pre) were not useful 28% of the time; I4 cosmetic findings 22%.
- INFERRED: the rubric's likelihood grade already predicts false alarms well, so L3 keeps its low weight of 0.1.

**Value by focus** (first reviews, re-reviews and after-merge reviews; START = the starting weights; hit rate = share of the 64 first reviews in which the focus found at least one accepted finding worth 1 point or more):

| Focus | Findings | Accepted | Not useful | Share of value (START) | Hit rate |
|---|---|---|---|---|---|
| harm | 64 | 50 | 11% | 28% | 33% |
| surprise | 110 | 95 | 3% | 25% | 47% |
| test | 87 | 61 | 5% | 19% | 48% |
| workflow | 123 | 95 | 8% | 18% | 53% |
| requirement | 64 | 51 | 14% | 9% | 28% |
| debt | 48 | 35 | 12% | 1% | — |
| report | 89 | 43 | 0% | 0% | 12% |

- The four focuses the owner kept (harm, workflow, surprise, debt) held 72% of the value.
- "Test" (19%) and "requirement" (9%) move to the merge gate, so the gate must carry about a quarter of the value the reviews found.
- The focus share moves a lot from run to run: test was 0% of first-review value on 10-27, 45% on 10-29 and 2% on 10-30.
- INFERRED: the focus was assigned after the fact. Every past review used the full checklist, so these are the focuses of what a look-everywhere review found, not what a narrowed review will find.

**Value by code area**:
- skill-scripts 16%, tests-gates 15%, turn-state 15%, folders-perms 13%, fencing 9%, kb 5%, store 5%.
- Each UI view earned 0–3%, and all UI views together about 21%.
- folders-perms had the most rejections: 14 of 76.

**Kinds repeated across 3 or more items**:
- 44 kinds (cause × area) meet the starting "3 or more items" bar. That is too many to bring to the owner.
- 8 kinds span 4 or more runs and are worth 20 points or more:

| Kind (cause × area) | Items |
|---|---|
| TEST × tests-gates (tests that cannot fail) | 20 |
| ORDER × turn-state | 10 |
| MUST × ui | 10 |
| ORDER × ui | 8 |
| EDGE × skill-scripts | 8 |
| BOUND × folders-perms | 7 |
| ADJ × turn-state | 7 |
| ADJ × fencing | 4 |

**Re-reviews.**
- Of 84 blocking re-review findings:
  - 53 were "fix-left": a member of the class the fix left open;
  - 26 were "fix-introduced": a regression the fix itself made;
  - 5 were other or unknown.
- INFERRED: a short check that looks only at the named findings would see the first group, but would miss most of the second unless it also reads the fix diff.

**Escapes.**
- The two reviews after merge found 8 findings in code a review had passed: 6 accepted, 2 of them I1.
- Later reviews raised 36 pre-existing findings; folders-perms 8, ui 9 and fencing 6 were the largest groups.
- The AMC debt register lists 7 rows found as pre-existing escapes: TD-43, TD-55 and TD-59 to TD-63 (`agent-mission-control/docs/tech-debt.md`).
- INFERRED: that is too few escapes to calibrate a weight.

**Size.**
- Rank correlation of changed lines with value: 0.26. With worth per credit: 0.16 (44 reviews with file data).
- Mean worth by size:

| Changed lines | Mean worth |
|---|---|
| 0–200 | 7.4 |
| 200–600 | 10.8 |
| 600–1,200 | 14.7 |
| over 1,200 | 9.9 |

- This fits the Cisco and Bosu finding that very large changes are reviewed less well. Size is a weak prior only.

**Sensitivity of the weights.** Rank correlation of per-review worth against the starting weights, for 64 first reviews:

| Variant | Correlation | Overlap of the top 10 |
|---|---|---|
| harm 5 | 0.98 | 7 |
| harm 20 | 0.99 | 9 |
| L3 0.3 | 0.99 | 10 |
| L2 1.0 | 0.96 | 10 |
| flat impact | 0.89 | 5 |
| count only | 0.84 | 7 |
| recommended | 0.96 | 8 |

- INFERRED: the exact weights matter little, but weighting by harm at all matters a good deal. With flat impact or a plain count, the focus order changes and harm drops from first place to fifth.

**The back-test of a learned skip** (VERIFIED; it ran in the session's `backtest.py`, not committed):
- Each review's value was predicted from the mean value of earlier reviews that touched the same areas, with areas taken from the changed files on the AMC `ow/<item>` branches.
- The prediction tracked actual value only weakly: rank correlation 0.21 over 42 reviews.
- Skipping its lowest quarter (10 reviews) would have saved 681 of 3,704 credits and lost 66 of 406 value points. None of the 6 reviews that earned less than 2 points were in that quarter.
- The owner's file rule ("only changes whose files touch a focus area"), back-tested on the same reviews:
  - Counting UI as a focus area (surprise), it would skip 2 of 44 reviews (tests and docs only, 5.6 per 100 credits).
  - Counting only host code, it would also skip 5 UI-only reviews. One of them, `d3-review`, found 13 points of harm and workflow value.

## What already exists (reuse check)

All of the second column is VERIFIED by reading the deployed files; the third column is INFERRED design.

| Part | What it does today | What the design reuses or adds |
|---|---|---|
| `mine.py` | `causes()` (:834) already parses cause tags in table cells, in `cause: CODE` and in the rubric's `AREA L1/I2 CODE` form (`GRADED_TAG`, :752); `quality()` (:905) counts them into one Pareto list; `read_rulings()` (:757) reads `rulings.jsonl`; `fix_brief_accepted()` (:859) counts the ACCEPTED list | Reuse every reader. Add one row per finding that joins its number, file:line, grade, cause, ruling and the round's credits, and add the REJECTED list and "could not reproduce" |
| `route.py` | `load_history()` (:284) walks every run folder; `arm_posterior()` (:338) builds a Beta from the cell's outcomes plus the kind's other outcomes at a reduced weight (`kind_share`); `choose()` (:367) draws from each Beta; `log()` (:526) writes `routes.jsonl` | Reuse all four. An "arm" becomes a (focus, area) pair |
| `review.sh`, `assets/review.md` | An unfilled `{{FOCUS_AREAS_OR_DELETE}}` slot (:54) and a `{{RISK_CHECKS_OR_DELETE}}` menu of risk blocks (:8–23) | The focus blocks succeed the risk menu; `review.sh` fills the slot |
| `debt.py` | `for-files` (:192), `stale` (:216), `import-plan` (:288), `add` | Debt findings go in through `add`; a row found in merged code is one source of escapes |
| `brief.py` | `must_items()` (:77) extracts numbered MUST lines | Reused for the SHALL-to-test map |
| `merge_check.py` | A pattern check on merge text | Nothing fits running tests; the requirement script is new and sits beside it |
| `result.py` | Prints a round's summary | Nothing new needed; the record reads the same files |
| `~/.agents/skills` | `software-testing`, `receiving-code-review` and `verification-before-completion` give advice | None records findings, so nothing there fits the record |

## What to track, and with what weight

| Track | Recommended weight | Why (evidence) |
|---|---|---|
| Harm of each finding | harm 10, wrong 3, degraded 1, cosmetic 0 | Ranking barely moves at 5 or 20 (0.98, 0.99); harm is 28% of value from 11% of findings. Keep. |
| Likelihood | normal 1.0, plausible 0.5, contrived 0.1 | L3 rejected 22% vs 4–5%; 0.3 changes nothing (0.99). Keep. |
| Ruling after the fix round | accepted full; demoted capped at "degraded"; rejected or not reproduced 0, and a miss for its (focus, area) | The orchestrator's demotion is the expert's call (OWASP). A miss is what lowers the area. |
| Unruled blocking finding | held back; the review is not scored until ruled | 4 of the 6 zero-worth reviews were zero only for lack of a ruling. |
| Report overclaim (Correction) | 0.5 when scoring old reviews; not a review focus from now on | 89 rows, all moved to the merge gate. |
| Escape | 2 × its points to its area's prior, and a miss for the focus that passed it | The owner's start. Too few escapes (8 after merge) to test it; no source for 2 (OPEN). |
| Area | per (focus, area) Beta, with half-life of 40 first reviews | The history spans 7 days, so 30 days would barely decay. Focus share swings between runs; Graves' code decay is yearly. |
| Same kind across items | owner flag at 4 or more runs and 20 or more points; below that, a debt row | "3 or more items" flags 44 kinds; the stricter bar flags 8. |
| Review and fix credits | worth = points per 100 review credits; fix credits per accepted finding tracked per kind | Fixes cost about 61 per finding against about 14 to find it, so prevention pays where a kind repeats. |
| Change size and churn | prior only: lines changed, capped at 1,200 | Correlation 0.16–0.26; the largest changes earn less. |
| Exploration | 1 review in 5 adds one focus block outside the top picks | Facebook samples about a quarter; Tricorder-style probation needs this data. |
| Not-useful rate per focus | probation at 10%, shut-off review at 25% | Tricorder. Requirement focus ran at 14%, harm at 11%. |

## Decisions

### D1. Where the record lives

1. JSONL files in each run folder: `findings.jsonl`, `reviews.jsonl` and `escapes.jsonl`, next to `rulings.jsonl` and `routes.jsonl`, read across runs by `load_history()`.
   - Trade-off: there are many small files, and no queries beyond Python.
2. One SQLite database under `~/.local/state/orchestrator-workers/`.
   - Trade-off: easy queries, but a new store, a lock, and a second source of truth beside the run folders.
3. A CSV in each project repo.
   - Trade-off: the owner sees it in review, but it mixes machine state into the repo, and the dotfiles repo is public.

**Recommended: 1.** It follows the existing pattern, so the record lives where the evidence lives, needs no new dependency, and can be rebuilt from the reports at any time by `mine.py --findings`.

### D2. How each review's focus is chosen

1. **Learned per (focus, area).**
   - **The arms.** Each arm is a Beta built the way `arm_posterior()` builds one.
     - Success: the focus found an accepted finding worth 1 point or more in that area.
     - Failure: the focus found nothing, raised a rejected finding, or passed code where an escape later appeared.
   - **Pooling.** The focus-wide history joins at the `kind_share` weight.
   - **Choosing.** For each review, draw from every arm whose area the change touches, and take the 2 or 3 highest focus blocks.
   - **Always included.**
     - "Harm" is always in when the change touches an always-review area: the store, folders and permissions, paid calls, or fencing.
     - "Debt" is always appended as one short paragraph, because it costs little and feeds the debt list.
   - **Exploring.** In 1 review in 5, chosen at random and logged, one block from outside the top picks is added.
2. **Fixed rules.** A path-to-focus table (for example, `sessions.ts` gives workflow; `src/ui` gives surprise), with no learning.
   - Trade-off: predictable and cheap, but it never learns, and the focus share swings between runs.
3. **A worth score with no sampling.** Rank areas by decayed points per credit, and use a fixed audit share for exploration.
   - Trade-off: simpler, but it ignores uncertainty, so an area with 2 lucky findings outranks one with 40 steady ones.

**Recommended: 1.** It reuses the router's sampler, which already handles sparse cells by pooling. Its uncertainty is built in, so exploration comes from the draw and not only from the 1-in-5 rule. Lewis's warning is met because the output is a block of questions, not a score.

### D3. When a review is skipped

1. **Skip by rule now; learned skip later.**
   - **For now.** Skip only when the change touches no file in a focus area: tests, docs and the record itself. Log every skip.
   - **Turning on the learned skip.** Do it only when a back-test over the last 40 first reviews shows that skipping the lowest predicted fifth loses less than half its share of credits in value. Today it loses 16% of value for 18% of credits, so it fails.
   - **Moving the threshold.** Then move it RADAR-style, one fifth at a time. Never skip a change that touches an always-review area. Move up only while the escape rate stays at or below its last level.
   - **The escape rate.** Escapes ÷ (accepted findings + escapes), per area, over 30 days or 40 reviews, whichever is longer.
2. **Learned skip now**, at the 10th percentile of past worth (0.94 points per 100 credits).
   - Trade-off: it saves a few credits, but the back-test shows it skips the wrong reviews.
3. **Never skip.**
   - Trade-off: the safest choice. It costs about 3% of review credits on tests-and-docs changes that earned 5.6 per 100.

**Recommended: 1.** The data says first reviews nearly all earn their cost and that today's history cannot yet pick out the ones that will not. A rule-based skip takes the small clear win. The learned skip waits until it can prove itself, as Meta's did.

### D4. The script that replaces "is each requirement met"

1. **Map and break.**
   - **The map.** The author's report has a table: SHALL number → test name → kind (`new` or `keeps`).
   - **The checks.** The merge gate checks that every SHALL from `must_items()` is mapped and that each named test exists and passes.
   - **The break check.** For `new` tests, run the test on the base commit with only the branch's test files applied; it must fail. For `keeps` tests, which guard behaviour that already existed, apply Google-style one-per-line mutants to the changed lines the test covers; at least one must make it fail.
   - **What the review keeps.** The review keeps the SHALL lines as context. A reviewer reports an unmet SHALL only when it causes harm, breaks a workflow or would surprise the owner.
2. **Map only.** Names exist and pass.
   - Trade-off: cheap, but it cannot catch a test that cannot fail. TEST × tests-gates is the most repeated kind (20 items).
3. **The author supplies a break patch per SHALL**, and the gate applies it and expects a failure.
   - Trade-off: precise, but the author picks the break, which is the same bias that makes their test miss.

**Recommended: 1.** Running the test on the base is an exact, cheap check for new behaviour, and the per-line mutants cover the rest at Google's cost of about 7 per change.

What it can and cannot catch (VERIFIED counts; per-row judgments INFERRED):
- **Requirement-only findings.** Of 45 blocking findings whose only fault was an unmet requirement, a named failing test would have caught 12 (27%), partly caught 14 (31%) and missed 19 (42%).
- **All unmet-requirement findings.** Counting every blocking finding that also left a requirement unmet (167 of 297, 56%), it would catch 31 (19%), partly catch 53 and miss 83.
- **What it misses.** Among the 167, the commonest causes after MUST (46) are another caller or path (ADJ, 31), event order (ORDER, 19) and boundary values (EDGE, 17): cases the author's reading, and so the author's test, did not imagine (INFERRED).
- **What it adds.** It does catch the "test" focus's main fault: tests that cannot fail (TEST cause, 17 of 30 blocking test-focus findings). A reviewer catches these only by reading carefully.
- **The trade.** The script is certain where it applies and blind outside the author's reading. A reviewer is uncertain everywhere but reads beyond the author. That is why the focus blocks keep the SHALLs as context.

## The record's design

**Schema** (JSONL, one object per line; ids are `<run>/<round>/<n>`):
- `findings.jsonl`: run, item, round, round_kind, n, file, line, area_code (COR, SEC and the rest), likelihood, impact, cause, class, focus (harm, workflow, surprise, debt, or legacy), code_area, origin, blocking (by the reviewer), ruling, ruling_source, unmet_req, mapped_test, points (computed), weights_version.
- `reviews.jsonl`: run, round, item, kind, model, effort, credits, changed_lines, areas_touched, focus_blocks (the list given to the reviewer), explored (the block added by sampling, or null), skipped (with its reason), points, worth, ruled (true once every blocking finding has a ruling).
- `escapes.jsonl`: run, found_by (a round, owner, or a debt id), file, line, area, impact, likelihood, blamed_item, passed_by (the review round that passed it), window_days, points.

**How `mine.py` fills it** (`mine.py <run> --findings`):
1. Split each review report into findings by its headings and numbered items. Read the tag with the existing `GRADED_TAG` or `CAUSE_TAG` and `CLASS_LINE`. Take file:line from the first `path:line` in the finding.
2. Rulings, in order of trust:
   - `rulings.jsonl` (already read);
   - the next fix brief's ACCEPTED list (already counted; now read item by item, matching each item's text back to its finding number);
   - its REJECTED list;
   - "could not reproduce" in the fix report, which gives not-reproduced;
   - a re-review verdict on a carried finding, which gives fixed_later.
3. Credits come from the existing round records, and changed lines from `git diff --numstat <base>...<branch>`.
4. Back-fill: run it over the eight `amc-` folders and compare with `findings.csv`, which becomes its test oracle.

**How a review gets its focus** (`route.py focus <item> --diff <patch>`):
1. Map the changed files to code areas, using a path table in `references/routes.json`.
2. If no file is in a focus area, log a skip and stop. That is the D3 rule.
3. Load history with `load_history()`, decayed by review count. For each touched area and each focus, build the Beta with `arm_posterior()`, using a prior of (1, 1) widened by the change-size prior. Draw, and keep the top 2 or 3. Add "harm" for always-review areas. Explore 1 in 5.
4. Write `{event: "focus", blocks, draws, explored}` to `routes.jsonl`. `review.sh` reads it and pastes each block's text into the focus slot.

**Each focus block's text** (short, in `assets/review-focus/<focus>.md`):
- what to look for;
- the area's last three accepted findings in one line each, so the reviewer starts from the area's history (Czerwonka's 33% → 67%);
- the brief's SHALL lines.

**Escapes are detected four ways, and each writes an `escapes.jsonl` row:**
- **A later finding in passed code.** When `--findings` sees a finding with origin pre, or any finding in a review after merge, it runs `git blame` on its file:line. If the line came from an item merged within the window, that item's first review is `passed_by`.
- **Debt rows.** `debt.py add` takes `--escape <item>` when a row is found in merged code.
- **The owner.** `mine.py escape --file --line --impact` records something the owner hit in use.
- **Fix regressions.** Fix-left and fix-introduced findings from re-reviews are written with `found_by` set to the re-review and `passed_by` set to the fix round. They score the fix method, not the review.

**How worth is measured, run by run:**
- `mine.py --worth` prints a per-review table like the one below.
- It also prints the run's totals: points per 100 review credits, fix credits per accepted finding, escape rate per area, not-useful rate per focus, and the repeated kinds that meet the bar.
- The run report compares each with the last three runs.
- A focus at 10% not-useful goes on probation (its block is rewritten). At 25%, it comes to the owner.

## Worth of each past first review

Credits are `ai_credits=`. "Acc" counts accepted or demoted findings; "Rej" counts rejected or not reproduced. START uses the starting weights and REC the recommended ones. Re-reviews and critiques are in `reviews.csv`.

| Run | Review | Credits | Findings | Acc | Rej | START | REC |
|---|---|---|---|---|---|---|---|
| 10-27 | rv-p7-post (after merge) | 73 | 4 | 4 | 0 | 13.1 | 13.1 |
| 10-27 | rv-diagram | 80 | 3 | 3 | 0 | 4.0 | 4.0 |
| 10-27 | rv-files54 | 36 | 8 | 6 | 0 | 18.4 | 18.4 |
| 10-27 | rv-p6-runs | 49 | 5 | 5 | 0 | 33.3 | 33.3 |
| 10-27 | rv-t7-codeintel | 66 | 4 | 4 | 0 | 40.2 | 40.2 |
| 10-27 | rv-ux4 (no ruling) | 30 | 3 | 0 | 0 | 0.0 | 0.0 |
| 10-28 | pm-credit-tracker | 24 | 1 | 1 | 0 | 12.2 | 12.2 |
| 10-28 | rv-big-files | 56 | 10 | 8 | 2 | 16.6 | 17.5 |
| 10-28 | rv-canvas-a | 128 | 3 | 2 | 1 | 2.4 | 2.7 |
| 10-28 | rv-credit-tracker | 38 | 7 | 7 | 0 | 27.9 | 29.2 |
| 10-28 | rv-gaps-1 | 95 | 4 | 4 | 0 | 7.9 | 8.4 |
| 10-28 | rv-gaps-3 | 82 | 5 | 1 | 3 | 1.2 | 1.2 |
| 10-28 | rv-insights-history | 114 | 3 | 3 | 0 | 1.2 | 1.2 |
| 10-28 | rv-pr-overview | 134 | 6 | 5 | 1 | 7.9 | 8.2 |
| 10-29 | canvas-b-review1 | 72 | 3 | 3 | 0 | 5.6 | 5.6 |
| 10-29 | flake-3-review1 | 71 | 5 | 5 | 0 | 14.8 | 14.8 |
| 10-29 | pr-threads-review1 | 153 | 8 | 8 | 0 | 7.4 | 7.4 |
| 10-29 | refused-send-review1 | 53 | 3 | 3 | 0 | 6.2 | 5.8 |
| 10-29 | stable-env-review1 | 54 | 4 | 4 | 0 | 10.3 | 10.3 |
| 10-30 | clusters-review | 72 | 4 | 4 | 0 | 8.4 | 8.4 |
| 10-30 | diff-colour-review | 45 | 3 | 3 | 0 | 14.3 | 14.3 |
| 10-30 | drafts-review | 55 | 6 | 6 | 0 | 27.1 | 27.1 |
| 10-30 | forecast-parallel-review | 34 | 2 | 1 | 1 | 8.9 | 8.9 |
| 10-30 | home-reorder-review | 56 | 5 | 4 | 0 | 5.3 | 5.3 |
| 10-30 | insights-history-review | 55 | 3 | 0 | 2 | 0.0 | 0.0 |
| 10-30 | live-checks-review | 63 | 4 | 4 | 0 | 4.8 | 6.4 |
| 10-30 | markers-review | 46 | 7 | 6 | 0 | 29.5 | 29.5 |
| 10-30 | measures-view-review | 53 | 4 | 2 | 0 | 0.9 | 0.9 |
| 10-30 | notes-search-review | 127 | 5 | 0 | 4 | 0.0 | 0.0 |
| 10-30 | panel-menu-review | 55 | 3 | 3 | 0 | 6.4 | 7.3 |
| 10-30 | router-launcher-review (dotfiles) | 50 | 4 | 3 | 0 | 8.0 | 8.0 |
| 10-30 | router-outcomes-review | 53 | 3 | 3 | 0 | 9.0 | 9.0 |
| 10-30 | run-edges-review | 58 | 4 | 4 | 0 | 7.8 | 8.7 |
| 10-30 | startup-review | 63 | 4 | 2 | 0 | 5.3 | 5.3 |
| 10-30 | tree-review | 62 | 5 | 4 | 0 | 8.6 | 8.6 |
| 10-31 | d1-review | 115 | 3 | 2 | 0 | 0.9 | 0.2 |
| 10-31 | d2-review | 162 | 7 | 6 | 1 | 16.7 | 10.9 |
| 10-31 | d3-review | 76 | 6 | 5 | 0 | 21.1 | 21.1 |
| 10-31 | d4-review (no ruling) | 53 | 1 | 0 | 0 | 0.0 | 0.0 |
| 10-31 | f29-review | 71 | 8 | 6 | 2 | 14.1 | 14.8 |
| 10-31 | f35-review | 121 | 10 | 7 | 2 | 9.6 | 10.0 |
| 10-31 | f85-review | 144 | 8 | 8 | 0 | 12.2 | 12.5 |
| 10-31 | f94-review | 128 | 8 | 7 | 1 | 10.5 | 10.9 |
| 10-31 | p1-review | 55 | 6 | 5 | 1 | 16.4 | 17.4 |
| 10-31 | p2-review (no ruling) | 64 | 4 | 0 | 0 | 0.0 | 0.0 |
| 10-31 | p3-review | 87 | 6 | 6 | 0 | 11.5 | 8.8 |
| 10-31 | p4-review2 | 72 | 12 | 12 | 0 | 32.2 | 27.6 |
| 10-31 | p5-review2 | 76 | 11 | 9 | 0 | 26.3 | 7.2 |
| 10-31 | p6-review | 68 | 7 | 6 | 1 | 9.0 | 8.4 |
| 11-02 | g10a-post-review2 (after merge) | 64 | 4 | 2 | 1 | 4.7 | 4.7 |
| 11-02 | f6-review | 95 | 6 | 6 | 0 | 6.6 | 7.2 |
| 11-02 | f7-review | 96 | 10 | 8 | 1 | 12.8 | 13.8 |
| 11-02 | g10a-review | 90 | 15 | 11 | 0 | 18.6 | 19.7 |
| 11-02 | g10b-review | 105 | 13 | 11 | 2 | 19.0 | 19.9 |
| 11-02 | g10c-review | 116 | 10 | 10 | 0 | 21.3 | 19.5 |
| 11-02 | g10d-review | 75 | 9 | 5 | 2 | 10.0 | 10.6 |
| 11-02 | g91a-review | 101 | 10 | 9 | 1 | 12.2 | 13.2 |
| 11-02 | g92a-review | 98 | 14 | 13 | 1 | 38.0 | 29.3 |
| 11-02 | g93a-review | 118 | 14 | 13 | 0 | 16.1 | 17.0 |
| 11-02 | o1-review | 141 | 8 | 8 | 0 | 9.9 | 8.2 |
| 11-02 | o2-review | 53 | 4 | 4 | 0 | 17.1 | 18.0 |
| 11-02 | o3-review | 58 | 6 | 6 | 0 | 20.8 | 21.6 |
| 11-02 | s1-review | 80 | 8 | 8 | 0 | 19.2 | 20.2 |
| 11-02 | s2-review (no ruling) | 74 | 3 | 0 | 0 | 0.0 | 0.0 |

**Which focuses and areas earned their cost** (INFERRED from the tables above):
- **Focuses**:
  - Harm, surprise and workflow each earned a large share (18–28%) and found something in a third to a half of reviews.
  - Requirement earned the least for its findings and had the highest not-useful rate (14%), which supports moving it out.
  - Debt earned almost nothing in points, which is right for a focus that does not block. It should be judged by the repeated kinds it surfaces, not by points.
- **Areas**: turn-state, folders-perms, tests-gates, skill-scripts and fencing earned their cost. Single UI views rarely did on their own, but UI as a whole did (about 21%).
- **Low earners**: the lowest first reviews were UI or search slices (`rv-insights-history`, `measures-view`, `notes-search`, `rv-gaps-3`), where findings were rejected or minor.

## Unknowns (OPEN)

- **Whether narrowed reviews keep the yield.** Will reviews narrowed to four focuses still find what full reviews found in those focuses? No past review was narrowed. The first run after the build should compare its per-focus hit rate with the table above.
- **Per-focus cost.** Credits cannot be split by focus in past data, so worth per focus is a share of value, not value per credit.
- **The escape weight.** The factor of 2 has no source and no data to test it (8 after-merge findings). The half-life of 40 reviews is a judgment and needs a back-test once more runs exist.
- **The grading itself.** The per-row judgments of focus, code area, unmet requirement and test-would-catch were made by graders. They were not checked by a second grader, apart from spot checks.
- **Unread sources.** The ISTQB glossary wording (the pages did not load), CodeScene's recency weighting, RETECS's exploration method, and Tornhill's book (paid) were not read.

## Build plan

Each phase is one worker session; the tests are the ones that prove it.

| Phase | Work | Tests that prove it |
|---|---|---|
| 1 | `mine.py --findings` reads reports and rulings into `findings.jsonl` | Fixture reports in the three past formats (a table with a cause column, a rubric `AREA Lx/Iy CODE` line with a class line, a numbered list with `cause:`); a fix brief with ACCEPTED and REJECTED lists; a fix report with "could not reproduce"; a back-fill over the `amc-` folders agrees with `findings.csv` on ruling for at least 90% of blocking rows |
| 2 | `reviews.jsonl`, `references/review-weights.json`, `mine.py --worth` | Worth for 10 named reviews matches `reviews.csv` within 0.1; an unruled blocking finding keeps its review unscored; a demoted finding is capped at "degraded" points |
| 3 | `assets/review-focus/{harm,workflow,surprise,debt}.md`; review.md's checks 1, 8, 9 and 10 and the test half of check 2 replaced by the slot; `review.sh --focus` fills it (default all four); the short re-review template lists the named findings and the fix diff | `test_review.py`: the slot is filled; no check names requirements or test quality; the default is all four; the re-review prompt holds the fix diff |
| 4 | `route.py focus` | A seeded draw is repeatable; an always-review area forces harm; the explore share is 0.2 ± 0.03 over 2,000 draws; an outcome's weight halves after 40 reviews; a decision row lands in `routes.jsonl` |
| 5 | The skip rule and the back-test gate | A docs-only diff is skipped and logged; a store diff is never skipped; `mine.py --skip-backtest` reproduces this note's 0.21 correlation and 16%/18% figures and reports "learned skip not allowed" |
| 6 | Escapes | In a fixture git repo, a later finding on a line blamed to a merged item writes an escape with the right `passed_by`; `debt.py add --escape` writes one; fix-introduced findings are charged to the fix round |
| 7 | The requirement script in the merge gate | A `new` test that passes on the base fails the gate; an unmapped SHALL fails it; a `keeps` test that survives every mutant fails it; a correct branch passes |
| 8 | The run report: per-run comparison, not-useful probation flags, repeated-kind list | On the 11-02 folder the repeated-kind list matches this note's 8 kinds |

## Helps other items

- **Fix rounds cost about four times what finding a fault costs** (61 against about 14 credits per finding). The 20-item TEST × tests-gates kind alone holds about 79 points. This holds for the orchestrator skill and for any project it runs. Category: cost of quality; prevention over detection.
- **The rubric's likelihood grade predicts false alarms** (L3 22% against 4–5%). The orchestrator could send L3 findings straight to the debt list instead of a fix round. Pre-existing findings were rejected at 28% and could go to debt by default. This holds for every review this skill runs. Category: alert precision (alert fatigue).
- **Fix regressions are a third of what re-reviews find** (26 of 84). Whatever replaces re-reviews must read the fix diff. This holds for the fix method at skill level. Category: bad-fix injection.
- **A ruling for every blocking finding.** Unruled findings turned four reviews into zeros. The fix brief or `rulings.jsonl` should be written for every review, even when no fix round follows. This holds for the skill and any measurement built on it. Category: measurement completeness.
- **The brief's premise was out of date**: `mine.py` already reads cause tags. Briefs that state what a script does should cite the line. This holds at user level, for every brief. Category: stale documentation in instructions.
- **Learning from 7 days of bursty runs.** Count decay in rounds, not days. The router's own history has the same shape. This holds for `route.py`. Category: non-stationary learning.
- **Research critiques earned the most per credit** (13.6 per 100). Keep them for research notes. This holds at skill level. Category: review return on cost.
- **This dataset is a ready test oracle.** `findings.csv` and its grading key can test `mine.py`'s parsers and any later change to the rubric. This holds for this skill. Category: evaluation dataset.

Case against: every focus label and test-would-catch call was assigned after the fact by graders reading full-checklist reviews, so the record's starting priors may describe what an unfocused reviewer stumbled on rather than what a focused one will find. One run of narrowed reviews whose per-focus hit rates differ sharply from the table above would falsify the priors.
