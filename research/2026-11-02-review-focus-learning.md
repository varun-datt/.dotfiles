# Review focus learning: a record that steers what each review looks at

Research for task rb1, 2026-11-02, revised the same day after a cross-family critique. Status: proposal for the owner. Data: [findings.csv](2026-11-02-review-focus-learning/findings.csv) (676 graded findings), [reviews.csv](2026-11-02-review-focus-learning/reviews.csv) (149 graded rounds) and [review-areas.csv](2026-11-02-review-focus-learning/review-areas.csv) (lines per area for the 44 reviews with file data). Every number below comes from those files unless a source is named, and every number names its cohort: **first 62** (first reviews), **post 2** (reviews after merge), **re-review 69**, **critique 16** (research critiques).

## In short

- **First reviews pay; fixes are where the credits go.** First 62 earned 11.8 value points per 100 credits under the starting weights (4,874 credits); only 6 earned nothing, 4 of them because nobody ruled. Fix rounds cost 22,048 credits, about 61 per accepted finding. Re-review 69 earned 4.1 per 100 (3.1 scoring a carried defect once), and 34 of 69 found nothing, which backs the owner's short re-review check. (VERIFIED)
- **The requirement-to-test gate first, then narrowing.** Test and requirement held 29% of first-62 value. That is historical exposure, not proven future loss, but no review should narrow until the gate is built and measured against those findings. (VERIFIED share; order INFERRED)
- **Keep the starting weights, with fixes.** Harm at 5 or 20 instead of 10 barely moves the ranking (rank correlation 0.98, 0.99). L3 findings were ruled wrong 18% of the time against 1–3% for L1 and L2. A demoted finding counts at most as degraded; "wrong" lowers an area, "out of scope" does not; Corrections score 0. The decay, owner-flag bar and escape factor are tuning guesses. (VERIFIED rates; weights INFERRED)
- **The record** (D1): rows per finding, review and escape in each run folder, a stable defect id so a defect seen twice scores once, and a log of which focus blocks each review was shown and their chances, so later policies can be judged offline. `mine.py` already reads cause tags (`mine.py:752`, `:834`) but does not link them to findings, rulings and cost.
- **Focus choice** (D2): fixed four blocks; the learner runs in shadow mode only. 132 possible (focus, area) arms, 68 ever seen with points, 47 of them in one review.
- **Skip by rule, not prediction** (D3). An explicit path map (scripts and prompts are code; unknown means review) skips 1 of 44 past reviews. A learned skip failed its back-test: skipping a fifth saved 19% of credits but lost 12% of value (24% and 18% on the last two runs, 13 reviews). (VERIFIED)
- **The requirement gate** (D4) catches less than hoped: of 45 requirement-only blocking findings, a named test would have caught 12, partly 14, missed 19. It does catch tests that cannot fail (the most repeated kind, 19 items) if each new test fails on the base code on its assertion, not on a missing import. (VERIFIED counts; per-row judgments INFERRED)

## Method and the dataset

**Sources graded** (VERIFIED): every run folder under `~/.local/state/orchestrator-workers/` whose name starts `amc-` (10-27 to 11-02, eight folders), plus one dotfiles item, the router launcher, reviewed inside run 10-30.

**Rows**: one per finding (676), following a shared grading key; the `grade_source` column says how each row was made.

| Column | Values |
|---|---|
| impact, likelihood | I1–I4 and L1–L3, from the rubric |
| cause | the reviewer's cause tag (blank for 117 rows) |
| focus | the first of harm, workflow, surprise, requirement, test, report or debt that applies |
| code_area | turn-state, store, folders-perms, fencing, ui:<view>, tests-gates, skill-scripts, kb, docs, other |
| ruling, ruling_reason | accepted, demoted, rejected, not-reproduced, not-ruled; wrong, out-of-scope, unclear |
| origin | new, fix-left, fix-introduced, pre (unknown for 18 rows) |
| unmet_req, test_would_catch | whether a requirement was unmet, and whether a named failing test would have caught it |

| Rounds | How graded |
|---|---|
| 10-27 to 10-30 (228 rows) | mapped from the earlier review-severity CSV and joined to the build-quality cause tags; focus and area set by rule (INFERRED) |
| 10-31 (164) and 11-02 (201) | two grader workers read each report against the key |
| 83 rows | by hand or from `rulings.jsonl` |

**Rulings** came from the fix briefs' ACCEPTED and REJECTED lists, fix reports that said "could not reproduce", `rulings.jsonl`, and the downgrades in `amc-2026-11-02/discuss.md`.

**How "blocking" in older records maps to the rubric** (applied to every row; `references/rubric.md:42` has Blocker and Major both block and get a fix round). `block_reviewer` keeps the reviewer's call; `ruling` records what the orchestrator did: accepted = sent to a fix round, whatever its label; demoted = kept as real, moved to a non-blocking home; rejected = named in a REJECTED list or ruled not a defect. So 63 Blocker→Major rows in `rulings.jsonl` are accepted and 4 Blocker→Minor demoted. Points come from the graded harm, so an old "Blocker" never inflates them. A finding in a REJECTED paragraph is rejected even if sent to debt from there (8 rows changed from demoted; one row moved from folders-perms to tests-gates).

**Why a finding was rejected** (code rows): wrong (not a defect, by design, far-fetched or not reproduced; 11), out of scope (pre-existing, the gate's job, the owner's call; 19), unclear (no reason recorded; 11). Only wrong and unclear count against a focus or area; tables count them together as "wrong".

**Blank fields** were not validated: 117 rows have no cause (42 code rows; 67 from `rulings.jsonl`, 26 hand-graded) and 18 no origin.

**Not graded, or only in part** (VERIFIED): four rounds with no final message (`canvas-b-rereview3` and `4`, the first `p4-review` and `p5-review`; their re-runs are in); `canvas-b-rereview2` (no evidence), `g10a-post-review` (never ran); `rw1-critique` and `hr1-critique` (rulings or count only); 26 in-chat 10-27 rows with no credits, left out of worth. 95 rows are unruled (non-blocking, or no fix round). RENDER→EDGE and PARSER→BOUND were mapped.

**What "worth" means** (one scoring function for every number): points = harm × likelihood (10, 3, 1, 0 for I1–I4; 1.0, 0.5, 0.1 for L1–L3; 0.5 if missing), counted only if accepted or demoted (full under the starting weights, START; capped at "degraded" under the recommended, REC). Everything else, and every Correction, scores 0. Worth is points per 100 `ai_credits=`. "Accepted" stands for "the orchestrator judged it real and worth a fix round"; it does not prove the defect was real, the fix right, or that it mattered to the owner.

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
| Useful review comments (Bosu et al.) | https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/bosu2015useful.pdf | useful means "judged useful by author of the change"; a change "within one line distance" of the comment is a feature of their classifier ("precision: 88% and recall: 78%"), not the definition; overall usefulness density 65.5% over 1,496,340 comments; interviewees rated "almost 69% comments" useful or somewhat useful; more files, fewer useful comments | "Accepted" is a proxy like theirs: someone downstream acted on it |
| Review at Microsoft (Czerwonka et al.) | https://www.microsoft.com/en-us/research/wp-content/uploads/2015/05/PID3556473.pdf | "only about 15% of comments ... indicate a possible defect"; a reviewer new to an area "only 33%" useful, later "about 67%" | Weight by harm; give each review its area's history |
| Review defect types (Mäntylä and Lassenius) | https://mmantyla.github.io/wiki/What+Types+of+Defects+Are+Really+Discovered+in+Code+Reviews%253F.html | "75 percent of defects found during the review do not affect the visible functionality" | Without harm weights, maintainability findings dominate |
| Review at Google (Sadowski et al.) | https://sback.it/publications/icse2018seip.pdf | aims are "education, maintaining norms, gatekeeping, and accident prevention" | Defect-finding is one aim; debt focus stays |
| Cisco review study | https://static0.smartbear.co/support/media/resources/cc/book/code-review-cisco-case-study.pdf | "61% of the reviews uncovered no defects"; "under 200, not to exceed 400" lines | Size is a prior; big diffs get less from review |
| Risky files reviewed less (Thongtanunam et al.) | https://rebels.cs.uwaterloo.ca/papers/msr2015_thongtanunam.pdf | risky files "tend to be reviewed less rigorously" | Steer focus toward risky areas |
| Defect removal efficiency (Capers Jones) | https://www.ppi-int.com/wp-content/uploads/2021/01/Software-Defect-Removal-Efficiency.pdf | DRE = "percentage of defects found and repaired prior to release", "After a fixed period of 90 days" (ISBSG "release plus 30 days"); inspections "more than 65% efficient" | An escape is leakage per review over a stated window; no source for the factor of 2 (OPEN) |
| Learned test ordering (RETECS; COLEMAN) | https://arxiv.org/pdf/1811.04122; https://github.com/jacksonpradolima/coleman4hcs | "better to reward each test case's priority individually"; RETECS's table policy uses ϵ-greedy with "Exploration Rate ϵ 0.2", its network policy adds "a random value drawn from a Gaussian distribution"; COLEMAN offers Thompson sampling with "sliding window" variants | Reward each focus separately; forget old outcomes; 0.2 exploration has precedent |
| Test selection at Facebook | https://arxiv.org/html/1810.05286v2 | retrains weekly; samples "close to a quarter of submitted code changes" | 1 in 5 exploration is in line |
| Thompson sampling tutorial (Russo et al.) | https://web.stanford.edu/~bvr/pubs/TS_Tutorial.pdf | with a window "The agent never ceases to explore" | Decay keeps the sampler exploring |
| Risk-based skip at Meta (RADAR) | https://arxiv.org/html/2605.30208v1 | uses risk "to identify diffs that do not need human review"; threshold moved "from the 25th to the 50th percentile"; "not a causal estimate" | Start strict; loosen a step at a time while escapes stay flat |
| Tricorder at Google | https://research.google.com/pubs/archive/43322.pdf | "A rate ≥10% puts the analyzer on probation"; above 25% "turn the analyzer off"; best analysers "0-3%" | A wrong rate per focus, with probation and shut-off |
| Mutation testing at Google | https://arxiv.org/html/2102.11378v2 | "Mutants are only generated for lines that are changed"; median mutants per changelist "820 for traditional mutagenesis, 77 for 1-per-line selection, and only 7 for arid-1-per-line selection" (one per line plus suppressing unproductive "arid" nodes); productive mutants "from 15% to 89%" | The break check for `keeps` tests; expect about 77 mutants a change unless arid-node suppression is built too |
| SARIF 2.1.0 (OASIS) | https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html | `partialFingerprints` "contributes to the stable, unique identity, or fingerprint, of the result"; `baselineState` is "new", "unchanged", "updated" or "absent" | A stable defect id and the link states between observations |

**Could not be traced to a primary source:**
- Mende and Koschke's effort-aware models (known only through Kamei);
- the Cisco "spot checking 20% to 33%" claim (known only through SmartBear's page; not in the Cisco chapter).

The Bosu 65.5% figure is now traced: it is the overall usefulness density, in a table numbered II in the copy tvly returned (the critique cites Table V; the numbering may differ between versions).

**Sources added after the critique** (read with `tvly extract`, VERIFIED; whether each changes a decision is INFERRED):
- **Orthogonal Defect Classification** (IBM's ODC v5.2, https://s3.us.cloud-object-storage.appdomain.cloud/res-files/70-ODC-5-2.pdf; the 1992 paper failed to fetch from three hosts). It records "Activity, Trigger and Impact" when a defect is opened and "Target, Defect Type, Qualifier, Age and Source" when closed, as separate fields; Age "ReFixed" means "introduced by the solution provided to fix a previous defect". Our cause tag mixes type and trigger. Changes D1: add a `trigger` field.
- **SZZ on the Linux kernel** (https://arxiv.org/html/2308.05060v2). Blame-based linking of a fix to the change that introduced it had "recall and precision between 0.40 and 0.60", and "17.47% of bug-fixing commits are ghost commits". Changes D1: blame only proposes an escape; a confirmation counts it.
- **Offline bandit evaluation** (Li et al. 2012, https://proceedings.mlr.press/v26/li12a/li12a.pdf). Replaying logs gives "provably unbiased evaluations" when arms were chosen "uniformly at random", and "any randomized logging policy is allowed" if each choice's probability is known. Changes D1 and D2: log every exposure with its chance.
- **A fixed-checklist baseline** (Sabaliauskaite et al., ISESE 2002, https://www.computer.org/csdl/proceedings-article/isese/2002/17960148/12OmNyQphby). With 59 students, checklist reading found as many defects as perspective-based reading (70% and 69%) at lower cost per defect. Changes D2: the fixed blocks are the baseline to beat.
- **Benchmark method** (Macroscope, https://macroscope.com/content/ai-code-review-benchmark-best-models; a vendor page, so method only). Include "10 clean pull requests" because "Without them you are measuring recall only"; count bugs found, valid findings and total comments; "Score by severity, not by count". It does not mention repeated runs. Changes phase 4: clean controls and severity-weighted precision and recall.

## What this project's history shows

All figures in this section are VERIFIED from the CSVs. Interpretations are marked.

**What each cohort earned** (one scoring function; START, with REC per 100 credits in the last column):

| Cohort | Rounds | Credits | Value | Per 100 credits | Median | Earned nothing | REC per 100 |
|---|---|---|---|---|---|---|---|
| first 62 | 62 | 4,874 | 574.8 | 11.8 | 9.8 | 6 | 10.9 |
| post 2 | 2 | 137 | 12.5 | 9.1 | 8.9 | 0 | 9.1 |
| re-review 69 | 69 | 3,680 | 149.4 | 4.1 | 0.8 | 34 | 3.2 |
| re-review 69, carried defects scored once | 69 | 3,680 | 114.4 | 3.1 | 0 | 35 | — |
| critique 16 | 16 | 1,801 | 244.0 | 13.6 | 13.9 | 3 | 13.6 |

- 39 re-review findings repeat a defect from the first review (35 START points; the router launcher's re-review c3 is its first finding 4). The record's defect id removes this double count.

**Fix rounds dominate the cost.** They cost 22,048 credits for 360 accepted findings, about 61 each; first 62 cost about 16 per accepted or demoted finding. The 11-02 PLAN row agrees: "fix rounds cost 6,569 credits against 6,421 for builds" (`agent-mission-control/PLAN.md:319`). INFERRED: where a kind repeats, prevention may pay more than detection, but these two numbers do not say by how much.

**How often a ruled finding was wrong, by likelihood** (code rows; wrong = wrong or unclear):

| Likelihood | Ruled | Wrong | Wrong or out of scope |
|---|---|---|---|
| L1 normal use | 187 | 2.7% | 4.3% |
| L2 plausible | 162 | 1.2% | 6.8% |
| L3 contrived | 82 | 18.3% | 26.8% |

Pre-existing findings were rarely wrong (6%) but often out of scope (34% together); I4 cosmetic findings were wrong 2 times in 9. INFERRED: the likelihood grade already predicts false alarms, so L3 keeps 0.1.

**Value by focus** (first 62; START; hit rate = share of the 62 in which the focus found an accepted finding worth 1 point or more):

| Focus | Findings | Accepted or demoted | Wrong (% of ruled) | Out of scope | Share of value | Hit rate |
|---|---|---|---|---|---|---|
| harm | 37 | 30 | 4 (11%) | 3 | 26.2% | 32% |
| surprise | 70 | 63 | 0 | 4 | 24.8% | 48% |
| workflow | 79 | 65 | 7 (9%) | 2 | 18.9% | 53% |
| test | 57 | 43 | 0 | 4 | 18.1% | 48% |
| requirement | 54 | 45 | 6 (11%) | 2 | 11.1% | 29% |
| debt | 29 | 19 | 2 (8%) | 3 | 1.0% | 0% |
| report | 52 | 39 | 0 | 0 | 0% | 0% |

The four kept focuses held 71% of first-62 value; test and requirement held 29.2% (29.1% with post 2; 29.7% over every code round). That is the exposure the gate must cover before reviews narrow. The test share swings by run (0% on 10-27, 45% on 10-29, 2% on 10-30). INFERRED: focus was assigned after the fact to full-checklist reviews, so this is what a look-everywhere review found, not what a narrowed one will find.

**Value by code area** (first 62): ui 21% (24 views, none above 2.2%), skill-scripts 17%, turn-state 15%, tests-gates 14%, folders-perms 11%, fencing 9%, kb 6%, store 5%. folders-perms had the most wrong findings, 11 of 47.

**Why learning per (focus, area) is not yet possible** (first 62): 33 areas earned points, so the four kept focuses give 132 possible arms; 68 were ever seen with points, 47 of them in one review, 7 in five or more.

**Kinds repeated across 3 or more items** (all rounds): 43 kinds (cause × area), too many to bring to the owner. 8 span 4 or more runs and 20 or more points (a tuning guess that gives a short list):

| Kind (cause × area) | Items | Points | Runs |
|---|---|---|---|
| TEST × tests-gates (tests that cannot fail) | 19 | 79.0 | 5 |
| ORDER × turn-state | 10 | 25.8 | 5 |
| MUST × ui | 10 | 31.5 | 4 |
| ORDER × ui | 8 | 31.5 | 4 |
| EDGE × skill-scripts | 8 | 35.4 | 4 |
| BOUND × folders-perms | 7 | 42.0 | 4 |
| ADJ × turn-state | 7 | 22.6 | 5 |
| ADJ × fencing | 4 | 24.0 | 4 |

**Re-reviews** (re-review 69). Of 84 blocking findings, 53 were fix-left (the class the fix left open), 26 fix-introduced (ODC's "ReFixed") and 5 other. INFERRED: a check of only the named findings sees the first group but misses most of the second unless it reads the fix diff.

**Escapes.** Post 2 found 8 findings in passed code: 6 accepted, 2 of them I1. Later reviews raised 36 pre-existing findings (ui 9, folders-perms 8, fencing 6). The AMC debt register lists 7 pre-existing escapes (TD-43, TD-55, TD-59 to TD-63, `agent-mission-control/docs/tech-debt.md`). INFERRED: too few to calibrate a weight.

**Size** (43 first reviews with file data): rank correlation of changed lines with value 0.22, with worth 0.12. Size is a weak prior only, and the largest changes earn less, as Cisco and Bosu found.

| Changed lines | Reviews | Mean worth |
|---|---|---|
| 0–200 | 9 | 7.7 |
| 200–600 | 17 | 10.8 |
| 600–1,200 | 10 | 14.5 |
| over 1,200 | 7 | 9.4 |

**Sensitivity of the weights** (first 62; rank correlation of per-review worth against START):

| Variant | Correlation | Overlap of the top 10 |
|---|---|---|
| harm 5 | 0.98 | 7 |
| harm 20 | 0.99 | 9 |
| L3 0.3 | 0.99 | 10 |
| L2 1.0 | 0.96 | 10 |
| flat impact | 0.90 | 5 |
| count only | 0.84 | 6 |
| recommended | 0.96 | 8 |

INFERRED: the precise weights matter little; weighting by harm at all matters a good deal (with flat impact or a plain count, harm drops from first focus to fifth).

**The file rule for skipping** (44 first and post reviews with file data from the AMC `ow/<item>` branches, possibly partial; lines per area in `review-areas.csv`). Each file maps explicitly to host, UI, scripts (including root `.ts` and `.js`), executable prompts (skills, agent files, prompt templates), config, tests, docs, or unknown; a review is skipped only when every file is tests or docs. With UI as a focus area that skips 1 of 44: a docs-only change, 53 of 3,890 credits, 0.5 of 410 points. Counting only host code would also skip 4 UI reviews, among them `d3-review` (16 points, 10 of them harm). The round-1 rule sent unmapped paths to "tests and docs" and so skipped `stable-env-review1`, which changed a script and earned 5.5 points; its "2 of 44" is withdrawn.

**The back-test of a learned skip** (VERIFIED; run in the session's `analyse3.py`, not committed; inputs in `review-areas.csv`). Each first review's worth is predicted as the line-weighted mean worth of earlier reviews in its areas (the all-review mean for an area with none). Ties go to the earlier review, never the outcome. Reviews with an unruled blocking finding (9 of 43) are left out, not scored zero. The policy is D3's: skip the lowest-predicted fifth; the bar is value lost under half the share of credits saved.

| Test | Reviews | Rank correlation | Skipped | Credits saved | Value lost | Bar |
|---|---|---|---|---|---|---|
| all runs, in order | 33 | 0.32 | 7 | 19% | 12% | fails |
| last two runs only (10-31 and 11-02), each predicted from every earlier review | 13 | 0.05 | 3 | 24% | 18% | fails |
| smallest fifth by lines (baseline), all runs | 33 | — | 7 | 20% | 19% | fails |

Only 2 of the 7 skipped were in the actual lowest fifth. The last-two-runs test is the tail of the same sequence, not a clean hold-out, and has 13 reviews: indicative only. The round-1 figures (0.21, lowest quarter) used a maximum of area means and are superseded.

## What already exists (reuse check)

All of the second column is VERIFIED by reading the deployed files; the third column is INFERRED design.

| Part | What it does today | What the design reuses or adds |
|---|---|---|
| `mine.py` | `causes()` (:834) already parses cause tags in table cells, in `cause: CODE` and in the rubric's `AREA L1/I2 CODE` form (`GRADED_TAG`, :752); `quality()` (:905) counts them into one Pareto list; `read_rulings()` (:757) reads `rulings.jsonl`; `fix_brief_accepted()` (:859) counts the ACCEPTED list | Reuse every reader. Add one row per finding that joins its number, file:line, grade, cause, ruling and the round's credits, and add the REJECTED list and "could not reproduce" |
| `route.py` | `load_history()` (:284) walks every run folder; `arm_posterior()` (:338) builds a Beta from the cell's outcomes plus the kind's other outcomes at a reduced weight (`kind_share`); `choose()` (:367) draws from each Beta; `log()` (:526) writes `routes.jsonl` | Reuse all four for the shadow policy: an arm is a (focus, area) pair; its draw and its chance are logged, not acted on |
| `review.sh`, `assets/review.md` | An unfilled `{{FOCUS_AREAS_OR_DELETE}}` slot (:54) and a `{{RISK_CHECKS_OR_DELETE}}` menu of risk blocks (:8–23) | The focus blocks succeed the risk menu; `review.sh` fills the slot |
| `debt.py` | `for-files` (:192), `stale` (:216), `import-plan` (:288), `add` | Debt findings go in through `add`; a row found in merged code is one source of escapes |
| `brief.py` | `must_items()` (:77) extracts numbered MUST lines | Reused for the SHALL-to-test map |
| `merge_check.py` | A pattern check on merge text | Nothing fits running tests; the requirement script is new and sits beside it |
| `result.py` | Prints a round's summary | Nothing new needed; the record reads the same files |
| `~/.agents/skills` | `software-testing`, `receiving-code-review` and `verification-before-completion` give advice | None records findings, so nothing there fits the record |

## What to track, and with what weight

Rows marked "tuning guess" have no data or source behind their number; they are starting settings to be revised once the record has data, not estimates.

| Track | Recommended weight | Why (evidence) |
|---|---|---|
| Harm of each finding | harm 10, wrong result 3, degraded 1, cosmetic 0 | First 62: ranking barely moves at 5 or 20 (0.98, 0.99); harm is 26% of value from 10% of findings. Keep. |
| Likelihood | normal 1.0, plausible 0.5, contrived 0.1 | Code rows: L3 wrong 18% against 1–3%; 0.3 changes nothing (0.99). Keep. |
| Trigger (new, after ODC) | none; a label for scoring the workflow focus | Separates how a defect shows (restart, late event, failing source) from its cause. |
| Ruling after the fix round | accepted full; demoted capped at "degraded"; rejected 0 | The orchestrator's demotion is the expert's call (OWASP). |
| Why rejected | wrong or unclear: a miss for its (focus, area); out of scope: neutral | Pre-existing findings were 34% wrong or out of scope but only 6% wrong; penalising scope would punish reviewers for the brief's edges. |
| Unruled blocking finding | held back; the review is not scored until ruled | 4 of the 6 zero-worth first reviews were zero only for lack of a ruling. |
| Report overclaim (Correction) | 0 everywhere; not a review focus from now on | 89 rows, all moved to the merge gate. One scoring function. |
| Same defect seen again | scored once, at its first observation | 39 carried re-review findings, 35 points. |
| Escape | 2 × its points to its area's prior, and a miss for the focus that passed it (tuning guess) | The owner's start. Too few escapes (8 in post 2) to test it; no source for 2. |
| Area | per (focus, area) Beta, half-life of 40 first reviews (tuning guess) | The history spans 7 days, so a 30-day half-life would barely decay; Graves' code decay is yearly, which does not transfer. |
| Same kind across items | owner flag at 4 or more runs and 20 or more points; below that, a debt row (tuning guess) | "3 or more items" flags 43 kinds; this bar flags 8. |
| Review and fix credits | worth = points per 100 review credits; fix credits per accepted finding, per kind | Fixes cost about 61 per accepted finding; first 62 cost about 16 per finding found. |
| Change size and churn | prior only: lines changed, capped at 1,200 | First reviews: correlation 0.12–0.22; the largest changes earn less. |
| Exposure | each review logs the focus blocks it was shown and the chance of each | Li et al.: without the chance, no other policy can be judged from the log. |
| Exploration (shadow) | the shadow policy logs one outside block in 1 review in 5 | RETECS used ϵ 0.2; Facebook samples about a quarter. |
| Wrong rate per focus | probation at 10%, owner review at 25% | Tricorder's thresholds. First 62: harm and requirement 11%, workflow 9%. |

## Decisions

### D1. Where the record lives, and what makes it judgeable later

1. JSONL files in each run folder (`findings.jsonl` per observation, `defects.jsonl` per defect id, `reviews.jsonl` per review with the blocks shown and their chances, `escapes.jsonl`), beside `rulings.jsonl` and `routes.jsonl`, read across runs by `load_history()`.
   - Trade-off: many small files; no queries beyond Python.
2. One SQLite database under `~/.local/state/orchestrator-workers/`.
   - Trade-off: easy joins on defect ids, but a new store, a lock, and a second source of truth.
3. A CSV in each project repo.
   - Trade-off: visible in review, but machine state in the repo, and the dotfiles repo is public.

**Recommended: 1.** The record lives with its evidence, needs no new dependency, and `mine.py --findings` can rebuild it any time. Changed from round 1: the defect id (a carried finding scores once, after SARIF's fingerprints and baseline states), the exposure log with chances (without it, Li et al.'s replay cannot judge a policy the record did not run), and a `trigger` field after ODC.

### D2. How each review's focus is chosen

1. **Learned per (focus, area) now.** A Beta per arm as `arm_posterior()` builds one; draw for every touched area, keep the top 2 or 3 blocks, explore 1 in 5.
   - Trade-off: it adapts, but 47 of 68 arms seen rest on one review, so early draws are mostly noise, and a narrowed review cannot find what it was not asked about.
2. **Fixed four blocks, learner in shadow mode.** Every review gets harm, workflow, surprise and debt. The Thompson policy logs what it would have chosen, with draws and chances. Its reward is points per credit, not a hit; "wrong" counts against a (focus, area), "out of scope" does not. It switches on only when at least 5 ruled reviews stand behind each arm it would use, and a log replay (Li et al.) plus clean controls show it beats the fixed blocks on severity-weighted value per credit.
   - Trade-off: no saving until then, and a little logging work in `route.py`.
3. **Fixed rules forever.** A path-to-focus table, no learning.
   - Trade-off: predictable and cheap, but it never learns, and focus shares swing between runs.

**Recommended: 2.** Changed from round 1, which recommended option 1. A fixed checklist is a fair baseline (Sabaliauskaite et al.: as effective as a targeted method, at lower cost), the arms are too sparse, and the shadow log is what lets a later switch be judged. The output stays a block of questions, not a score, as Lewis warned.

### D3. When a review is skipped

1. **Skip by an explicit file rule now; a learned skip later, behind a back-test.** Map every changed file (host, UI, scripts, executable prompts, config, tests, docs, unknown); skip only when every file is tests or docs, never for unknown; log every skip. On past data this skips 1 of 44. The learned skip turns on only when the back-test, rerun on the record, passes its bar (value lost under half the share of credits saved) on runs it was not tuned on; today it fails (12% of value for 19% of credits; 18% for 24% on the last two runs). Its threshold then moves one step at a time (RADAR-style), never for a change touching an always-review area (store, folders and permissions, paid calls, fencing), and only while the escape rate (confirmed escapes ÷ (accepted findings + confirmed escapes), per area, over 40 reviews, a tuning guess) holds.
2. **Learned skip now**, at the 10th percentile of past worth.
   - Trade-off: saves a few credits, but the back-test shows it skips the wrong reviews.
3. **Never skip.**
   - Trade-off: safest; on past data it costs 53 of 3,890 credits, one docs-only change.

**Recommended: 1.** Changed from round 1: the file map is explicit (scripts and prompts are code, unknown is reviewed), cutting past skips from 2 to 1, and the learned skip is tested as D3 would run it (a fifth, not a quarter). It still fails, so it stays off.

### D4. The script that replaces "is each requirement met"

1. **Map and break.** The author's report maps each SHALL number to a test name and kind (`new` or `keeps`). The merge gate checks every SHALL from `must_items()` is mapped and each named test exists and passes. A `new` test is run on the base commit with only the branch's test files applied and must fail on an assertion; a compile or import failure shows only that the code is absent, not that the test checks it. A `keeps` test (guarding existing behaviour) must fail under at least one one-per-line mutant of the changed lines it covers; expect about 77 mutants a change (Google's median without arid-node suppression), measured in phase 4. The review keeps the SHALL lines as context and reports an unmet SHALL only when it causes harm, breaks a workflow or would surprise the owner.
2. **Map only.** Names exist and pass.
   - Trade-off: cheap, but blind to tests that cannot fail, the most repeated kind (19 items).
3. **The author supplies a break patch per SHALL**, which the gate applies, expecting a failure.
   - Trade-off: precise, but the author picks the break, the same bias that makes their test miss.

**Recommended: 1.** Changed from round 1: an assertion failure is required, the mutant cost is quoted correctly, and the gate is built and evaluated before any review narrows. Running the test on the base is a cheap, strong check for new behaviour; mutants cover the rest at a cost still to be measured.

What it can and cannot catch (VERIFIED counts; per-row judgments INFERRED):
- Of 45 blocking findings whose only fault was an unmet requirement, a named failing test would have caught 12 (27%), partly caught 14 (31%) and missed 19 (42%). Of all 167 blocking findings that left a requirement unmet (56% of 297), it would catch 31, partly 53, miss 83.
- It misses what the author did not imagine: after MUST (46), the commonest causes among the 167 are another caller (ADJ, 31), event order (ORDER, 19) and boundary values (EDGE, 17).
- It catches tests that cannot fail (TEST, 17 of 30 blocking test-focus findings), which a reviewer finds only by careful reading.
- The script is reliable where it applies and blind beyond the author's reading; a reviewer is the reverse. Hence the SHALLs stay in the focus blocks as context.
- Residual risk of narrowing: test and requirement held 29% of first-62 value, and the gate fully catches about a quarter of the requirement-only findings. How much of the rest the four blocks pick up is unknown until phase 4; this is historical exposure, not a proven loss.

## The record's design

**Schema** (JSONL in each run folder; ids are `<run>/<round>/<n>`):

| File | One row per | Fields |
|---|---|---|
| `findings.jsonl` | observation of a defect | run, item, round, round_kind, n, defect_id, state (new, persisted, regression, escape: SARIF's baselineState under our names), file, line, area_code, likelihood, impact, cause, trigger, class, focus, code_area, origin, blocking, ruling, ruling_reason (wrong, out-of-scope, unclear), ruling_source, unmet_req, mapped_test, points (0 after a defect's first observation), weights_version |
| `defects.jsonl` | defect | defect_id, fingerprint (item, file, code area, cause, class; no line, since fixes move it), first_seen, last_state, fixed_in, linked_escape |
| `reviews.jsonl` | review | run, round, item, kind, model, effort, credits, changed_lines, file_kinds, focus_blocks (each with its chance of being shown; 1.0 for the fixed four), shadow_pick (blocks, draws, chances), skipped (with reason), points, worth, ruled |
| `escapes.jsonl` | escape | run, found_by, defect_id, file, line, area, impact, likelihood, proposed_by, confirmed_by (empty until confirmed), passed_by, window, points |

**How `mine.py <run> --findings` fills it.** It splits each report into findings by headings and numbered items, reads the tag with the existing `GRADED_TAG` or `CAUSE_TAG` and `CLASS_LINE`, and takes the first `path:line`. Rulings come, in order of trust, from `rulings.jsonl` (Blocker→Major counts as accepted), the fix brief's ACCEPTED list (now matched item by item), its REJECTED list (reason sorted into wrong, out of scope or unclear), "could not reproduce" in the fix report (wrong), and a re-review verdict. A re-review finding that names a first-review finding takes its defect id and state `persisted`; a fix-introduced one gets a new id and state `regression`. Credits come from the round records, changed lines from `git diff --numstat`. Back-filled over the eight `amc-` folders, it is tested against `findings.csv`.

**How a review gets its focus** (`route.py focus <item> --diff <patch>`): map each file to its kind and code area with an explicit path table in `references/routes.json` (unmatched is `unknown`); if every file is tests or docs, log a skip and stop; otherwise show all four blocks, each logged at chance 1.0. The shadow policy loads history with `load_history()`, builds each (focus, area) Beta with `arm_posterior()` from points per credit scaled to 0–1, pooled at `kind_share`, keeps the top 2 or 3 draws plus one outside block in 1 review in 5, and logs picks, draws and chances (estimated by repeating the draw) in `routes.jsonl`. Nothing is acted on.

**Each focus block** (`assets/review-focus/<focus>.md`) holds what to look for (the workflow block lists stop, restart, late event, failing source, a flow that cannot finish), the area's last three accepted findings in a line each (a weak stand-in for the area experience Czerwonka et al. found useful), and the brief's SHALL lines.

**Escapes are proposed, then confirmed:**

| Source | Proposed by | Counts when |
|---|---|---|
| A later finding (origin pre, or after merge) in passed code | `git blame` on its file:line names the merged item as `passed_by` | the fix report or orchestrator confirms (blame is right about half the time in SZZ studies) |
| A debt row found in merged code | `debt.py add --escape <item>` | at once |
| Something the owner hit in use | `mine.py escape --file --line --impact` | at once |
| A fix-introduced finding | state `regression`, `passed_by` the fix round | at once; scores the fix method, not the review |

**Worth, run by run.** `mine.py --worth` prints a per-review table like the one below, scored once per defect, and per-cohort totals: points per 100 review credits, fix credits per accepted finding, confirmed escape rate per area, wrong rate per focus (out of scope apart), repeated kinds over the bar, and the shadow policy's replayed value against the fixed blocks, each against the last three runs. A focus at 10% wrong goes on probation (its block is rewritten); at 25% it comes to the owner.

## Worth of each past first review

First 62 and post 2, scored with the one function. Credits are `ai_credits=`. "Acc" counts accepted or demoted findings; "Wrong / scope" counts findings ruled wrong or unclear, then out of scope. START uses the starting weights and REC the recommended ones (worth per 100 credits). Re-reviews (with a deduplicated value column) and critiques are in `reviews.csv`.

| Run | Review | Credits | Findings | Acc | Wrong / scope | START | REC |
|---|---|---|---|---|---|---|---|
| 10-27 | rv-diagram | 80 | 3 | 3 | 0/0 | 4.0 | 4.0 |
| 10-27 | rv-files54 | 36 | 8 | 6 | 0/0 | 18.4 | 18.4 |
| 10-27 | rv-p6-runs | 49 | 5 | 5 | 0/0 | 33.3 | 33.3 |
| 10-27 | rv-t7-codeintel | 66 | 4 | 4 | 0/0 | 40.2 | 40.2 |
| 10-27 | rv-ux4 (no ruling) | 30 | 3 | 0 | 0/0 | 0.0 | 0.0 |
| 10-27 | rv-p7-post (after merge) | 73 | 4 | 4 | 0/0 | 13.1 | 13.1 |
| 10-28 | pm-credit-tracker | 24 | 1 | 1 | 0/0 | 12.2 | 12.2 |
| 10-28 | rv-big-files | 56 | 10 | 8 | 1/1 | 16.6 | 16.6 |
| 10-28 | rv-canvas-a | 128 | 3 | 2 | 1/0 | 2.4 | 2.4 |
| 10-28 | rv-credit-tracker | 38 | 7 | 7 | 0/0 | 27.9 | 27.9 |
| 10-28 | rv-gaps-1 | 95 | 4 | 4 | 0/0 | 7.9 | 7.9 |
| 10-28 | rv-gaps-3 | 82 | 5 | 1 | 1/2 | 1.2 | 1.2 |
| 10-28 | rv-insights-history | 114 | 3 | 3 | 0/0 | 1.2 | 1.2 |
| 10-28 | rv-pr-overview | 134 | 6 | 5 | 1/0 | 7.9 | 7.9 |
| 10-29 | canvas-b-review1 | 72 | 3 | 3 | 0/0 | 5.6 | 5.6 |
| 10-29 | flake-3-review1 | 71 | 5 | 5 | 0/0 | 14.8 | 14.8 |
| 10-29 | pr-threads-review1 | 153 | 8 | 8 | 0/0 | 7.4 | 7.4 |
| 10-29 | refused-send-review1 | 53 | 3 | 3 | 0/0 | 6.2 | 5.8 |
| 10-29 | stable-env-review1 | 54 | 4 | 4 | 0/0 | 10.3 | 10.3 |
| 10-30 | clusters-review | 72 | 4 | 4 | 0/0 | 8.4 | 8.4 |
| 10-30 | diff-colour-review | 45 | 3 | 3 | 0/0 | 14.3 | 14.3 |
| 10-30 | drafts-review | 55 | 6 | 6 | 0/0 | 27.1 | 27.1 |
| 10-30 | forecast-parallel-review | 34 | 2 | 1 | 1/0 | 8.9 | 8.9 |
| 10-30 | home-reorder-review | 56 | 5 | 4 | 0/0 | 5.3 | 5.3 |
| 10-30 | insights-history-review | 55 | 3 | 0 | 2/0 | 0.0 | 0.0 |
| 10-30 | live-checks-review | 63 | 4 | 4 | 0/0 | 4.8 | 4.8 |
| 10-30 | markers-review | 46 | 7 | 6 | 0/0 | 29.5 | 29.5 |
| 10-30 | measures-view-review | 53 | 4 | 2 | 0/0 | 0.9 | 0.9 |
| 10-30 | notes-search-review | 127 | 5 | 0 | 4/0 | 0.0 | 0.0 |
| 10-30 | panel-menu-review | 55 | 3 | 3 | 0/0 | 6.4 | 6.4 |
| 10-30 | router-launcher-review (dotfiles) | 50 | 4 | 3 | 0/0 | 8.0 | 8.0 |
| 10-30 | router-outcomes-review | 53 | 3 | 3 | 0/0 | 9.0 | 9.0 |
| 10-30 | run-edges-review | 58 | 4 | 4 | 0/0 | 7.8 | 7.8 |
| 10-30 | startup-review | 63 | 4 | 2 | 0/0 | 5.3 | 5.3 |
| 10-30 | tree-review | 62 | 5 | 4 | 0/0 | 8.6 | 8.6 |
| 10-31 | d1-review | 115 | 3 | 2 | 0/0 | 0.9 | 0.2 |
| 10-31 | d2-review | 162 | 7 | 6 | 1/0 | 16.7 | 10.6 |
| 10-31 | d3-review | 76 | 6 | 5 | 0/0 | 21.1 | 21.1 |
| 10-31 | d4-review (no ruling) | 53 | 1 | 0 | 0/0 | 0.0 | 0.0 |
| 10-31 | f29-review | 71 | 8 | 6 | 2/0 | 14.1 | 14.1 |
| 10-31 | f35-review | 121 | 10 | 7 | 1/1 | 9.6 | 9.6 |
| 10-31 | f85-review | 144 | 8 | 8 | 0/0 | 12.2 | 12.2 |
| 10-31 | f94-review | 128 | 8 | 7 | 1/0 | 10.5 | 10.5 |
| 10-31 | p1-review | 55 | 6 | 5 | 0/1 | 16.4 | 16.4 |
| 10-31 | p2-review (no ruling) | 64 | 4 | 0 | 0/0 | 0.0 | 0.0 |
| 10-31 | p3-review | 87 | 6 | 6 | 0/0 | 11.5 | 8.2 |
| 10-31 | p4-review2 | 72 | 12 | 12 | 0/0 | 32.2 | 26.9 |
| 10-31 | p5-review2 | 76 | 11 | 9 | 0/0 | 26.3 | 7.2 |
| 10-31 | p6-review | 68 | 7 | 6 | 1/0 | 9.0 | 7.7 |
| 11-02 | f6-review | 95 | 6 | 6 | 0/0 | 6.6 | 6.6 |
| 11-02 | f7-review | 96 | 10 | 8 | 1/0 | 12.8 | 12.8 |
| 11-02 | g10a-review | 90 | 15 | 10 | 0/1 | 18.1 | 18.1 |
| 11-02 | g10b-review | 105 | 13 | 11 | 0/2 | 19.0 | 19.0 |
| 11-02 | g10c-review | 116 | 10 | 10 | 0/0 | 21.3 | 18.7 |
| 11-02 | g10d-review | 75 | 9 | 5 | 0/2 | 10.0 | 10.0 |
| 11-02 | g91a-review | 101 | 10 | 8 | 1/1 | 11.7 | 11.7 |
| 11-02 | g92a-review | 98 | 14 | 10 | 0/4 | 37.1 | 28.0 |
| 11-02 | g93a-review | 118 | 14 | 13 | 0/0 | 16.1 | 16.1 |
| 11-02 | o1-review | 141 | 8 | 5 | 0/3 | 6.7 | 6.7 |
| 11-02 | o2-review | 53 | 4 | 4 | 0/0 | 17.1 | 17.1 |
| 11-02 | o3-review | 58 | 6 | 6 | 0/0 | 20.8 | 20.8 |
| 11-02 | s1-review | 80 | 8 | 8 | 0/0 | 19.2 | 18.9 |
| 11-02 | s2-review (no ruling) | 74 | 3 | 0 | 0/0 | 0.0 | 0.0 |
| 11-02 | g10a-post-review2 (after merge) | 64 | 4 | 2 | 0/1 | 4.7 | 4.7 |

**Which focuses and areas earned their cost** (first 62; INFERRED from the tables above): harm, surprise and workflow each earned 19–26% and found something in a third to a half of reviews. Test earned 18% with no wrong findings; its value moves to the gate only if phase 4 shows the gate catches it. Requirement earned 11% with the highest wrong rate (11%, with harm), which supports moving it out once the gate is in. Debt earned almost nothing in points, as a non-blocking focus should; judge it by the repeated kinds it surfaces. Turn-state, folders-perms, tests-gates, skill-scripts and fencing earned their cost; single UI views rarely did, UI as a whole did (21%). The lowest first reviews were UI or search slices (`rv-insights-history`, `measures-view`, `notes-search`, `rv-gaps-3`).

## Unknowns (OPEN)

- **Whether narrowed reviews keep the yield.** No past review was narrowed; phase 6 compares per-focus value per credit with the table above.
- **Per-focus cost.** Past credits cannot be split by focus, so focus worth is a share of value, not value per credit.
- **The tuning guesses.** The escape factor of 2, the 40-review half-life, the 4-run and 20-point owner flag and the 5-reviews-per-arm bar have no source or data behind them.
- **Repeated runs.** Whether the same review run twice finds the same things was not measured, and the benchmark page did not describe repeats.
- **The grading itself.** Focus, code area, unmet requirement and test-would-catch were judged by graders, checked only by spot checks and the critique's 25-row sample (its row errors are fixed here). Blank causes and origins were not validated.
- **Unread sources.** The ISTQB glossary (pages did not load), CodeScene's recency weighting, Tornhill's book (paid), and the 1992 ODC paper (three hosts failed; IBM's v5.2 document read instead).

## Build plan

Each phase is one worker session; the tests are the ones that prove it. Changed from round 1: the requirement gate and its evaluation now come before any narrowing, the focus learner runs in shadow mode, and escapes need a confirmed link.

| Phase | Work | Tests that prove it |
|---|---|---|
| 1 | `mine.py --findings` reads reports and rulings into `findings.jsonl` and `defects.jsonl`, with `ruling_reason`, the severity-mapping rule and defect ids | Fixture reports in the three past formats (a table with a cause column, a rubric `AREA Lx/Iy CODE` line with a class line, a numbered list with `cause:`); a fix brief with ACCEPTED and REJECTED lists, where a REJECTED item sent to debt comes out rejected and out of scope; a fix report with "could not reproduce"; a Blocker→Major ruling comes out accepted; the router launcher's re-review c3 gets the defect id of its first finding 4; a back-fill over the `amc-` folders agrees with `findings.csv` on ruling for at least 90% of blocking rows |
| 2 | `reviews.jsonl`, `references/review-weights.json`, `mine.py --worth` | Cohort totals match this note (first 62: 574.8 points, 11.8 per 100; re-review 69 deduplicated: 114.4); an unruled blocking finding keeps its review unscored; a demoted finding is capped at "degraded" under REC; a Correction scores 0 |
| 3 | The requirement gate in the merge gate (D4) | A `new` test that passes on the base fails the gate; one that fails on the base only by import or compile error fails the gate; an unmapped SHALL fails it; a `keeps` test that survives every mutant fails it; a correct branch passes |
| 4 | Evaluate the gate on past items before anything narrows | Rerun the gate on the reviewed commits of past items with requirement-only or TEST findings, plus at least 10 clean controls (items whose review found neither). Report how many past findings it catches against the graded 12 of 45 and 17 of 30, its false alarms on the controls, and mutants and minutes per change. The owner decides on narrowing from this table |
| 5 | Shadow focus policy: `route.py focus` | Every review still gets all four blocks, logged with chance 1.0; the shadow pick, its draws and chances land in `routes.jsonl`; a seeded draw is repeatable; the shadow explore share is 0.2 ± 0.03 over 2,000 draws; an outcome's weight halves after 40 reviews; a replay script scores the shadow policy from the log |
| 6 | Narrowing and the short re-review, only after phase 4 and the owner's go: `assets/review-focus/*.md`, the slot in review.md, `review.sh --focus`, the re-review template | `test_review.py`: the slot is filled; no check names requirements or test quality; the re-review prompt lists the named findings and holds the fix diff |
| 7 | The skip rule and the back-test command | The explicit path map: a docs-only diff is skipped and logged; a script, prompt, config or unknown path is never skipped; `mine.py --skip-backtest` reproduces this note's figures from `review-areas.csv` (rank correlation 0.32, 19% of credits for 12% of value) and reports "learned skip not allowed" |
| 8 | Escapes | In a fixture git repo, a later finding on a line blamed to a merged item writes a proposed escape that does not count until confirmed; `debt.py add --escape` writes one; fix-introduced findings are charged to the fix round |
| 9 | The run report: per-cohort comparison, wrong-rate probation flags, repeated-kind list, shadow replay | On the 11-02 folder the repeated-kind list matches this note's 8 kinds |

## Helps other items

- **Fix rounds are the large cost** (about 61 credits per accepted finding against 16 to find one); TEST × tests-gates alone holds 79 points. Where a kind repeats, prevention may pay more than detection, by an unmeasured amount. Skill and every project it runs. Category: cost of quality.
- **Likelihood predicts false alarms** (L3 wrong 18% against 1–3%). L3 findings, and pre-existing ones (34% out of scope), could go to debt instead of a fix round. Skill level. Category: alert precision (alert fatigue).
- **Fix regressions are a third of what re-reviews find** (26 of 84), so any re-review check must read the fix diff. Skill level. Category: bad-fix injection (ODC's ReFixed).
- **A ruling and its reason for every blocking finding.** Unruled findings zeroed four first reviews, and 11 rejections have no reason. Skill level. Category: measurement completeness.
- **Log the chance with every choice.** A skill that picks among options (router, focus, model) can be judged offline only if it logs what it picked and how likely that was. `route.py` today, and every learning loop at user level. Category: off-policy evaluation.
- **Score a defect once.** Carried defects inflated re-review value by about a quarter (149 to 114). Skill level. Category: deduplication of observations.
- **An unknown path is not safe.** Any rule that skips work by path maps every kind and treats unknown as risky. User level. Category: fail-safe defaults.
- **The brief's premise was out of date** (`mine.py` already reads cause tags). Briefs that state what a script does should cite the line. User level. Category: stale documentation in instructions.
- **This dataset is a test oracle** for `mine.py`'s parsers and later rubric changes. Skill level. Category: evaluation dataset.

Case against: gate-first and shadow mode delay every saving, and the review credits they protect are small (4,874 for first reviews against 22,048 for fixes), so the owner may reasonably narrow now and watch escapes. And every focus label and test-would-catch call was assigned after the fact to full-checklist reviews, so the 29% exposure and the gate's 12 of 45 may be wrong either way. Phase 4 falsifies the second: if the gate catches most past test and requirement findings with few false alarms on clean controls, narrowing is safe sooner; if narrowed reviews in phase 6 keep their per-focus value per credit near the table above, the first falls too.
