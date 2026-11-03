# Requirement gate evaluation: the gate on past AMC items, with clean controls

Research for task r4 (review record phase 4), 2026-11-02. It reruns the unmerged requirement gate (`reqgate.py`, branch `ow/r3`, [D4](2026-11-02-review-focus-learning.md#d4-the-script-that-replaces-is-each-requirement-met)) on the commits the first review saw, for past items with requirement-only or TEST findings and 12 clean controls. Data, per-item JSON and driver scripts: [2026-11-02-requirement-gate-evaluation/](2026-11-02-requirement-gate-evaluation/). Labels: VERIFIED (ran or read; source named), INFERRED (judgement), OPEN (unknown).

## In short

- **The gate catches almost none of the past requirement-only findings.** Of 31 in scope (of the note's 45), it flags the finding's own MUST for a test-quality reason once (g10d, a FAIL_TO_PASS test that passes on the base). Of the 8 graded "a named failing test would have caught it", it catches 0. The grading imagined a test written to the requirement; the gate checks only the *author's* tests, which passed without reaching it. (VERIFIED counts; why INFERRED)
- **On TEST findings it does somewhat better, but not on the "tests that cannot fail" it was built for.** Of 25 in scope (of 30), it flags 4 for a test-quality reason (2 on the finding's own test); of the 13 with cause TEST, 2, and those only at MUST level. Most sit in new test files that fail to import on the base, which proves nothing. (VERIFIED counts)
- **Under the note's assertion-only rule the gate fails nearly everything, controls included.** 10 of 12 clean controls fail, all for code absent on the base, none for a weak test. Under SWE-bench's rule (any non-pass on the base is a valid FAIL_TO_PASS), 1 of 12 fails, for a test that passes on the base. As the gate runs today, Playwright included, 12 of 12 fail. (VERIFIED)
- **Stryker cost per change: median 2.7 minutes, 146 mutants; 9.9 minutes at most below the 20-minute cap, which one item of 231 added lines hit** (17 of 35 items measured, smallest first; VERIFIED). ignoreStatic halved one item's time and changed little elsewhere.
- **Recommendation: do not narrow reviews on this gate yet.** Fix it first (SWE-bench's base rule, the mutant check on new code, Playwright marked or run), then rerun this evaluation, one command per phase.

## At a glance

<!-- table:summary -->
| | assertion-only rule (D4), INFERRED map | D4, strict map | SWE-bench rule, INFERRED map | SWE-bench rule, strict map |
| --- | --- | --- | --- | --- |
| Requirement-only findings caught or MUST flagged (of 31; graded yes: of 8) | 1 (0) | 1 (0) | 1 (0) | 1 (0) |
| ... MUST had no test (`none`, reported, not failed) | 0 | 7 | 0 | 7 |
| ... item failed only for another reason | 26 | 18 | 11 | 6 |
| TEST-focus findings caught or MUST flagged (of 25; cause TEST: of 13) | 4 (2) | 4 (2) | 4 (2) | 4 (2) |
| ... MUST had no test (`none`, reported, not failed) | 2 | 11 | 2 | 11 |
| ... item failed only for another reason | 16 | 8 | 10 | 7 |
| Clean controls failed (of 12) | 10 | 10 | 1 | 1 |
| Clean controls failed with Playwright counted, as the gate runs today | 12 | | 9 | |
| Minutes per change, base and head runs (median / largest, 37 items) | 0.26 / 1.19 | same | same | same |
| Minutes per change with Stryker (median / largest, 17 items; partial, smallest first) | 2.74 / 20.03 | same | same | same |
| Mutants generated per change (median / largest) | 146 / 553 | same | same | same |
<!-- /table -->

## Items, commits and how they were chosen

**Finding items** (VERIFIED, `scripts/discover.py` → `items.json`): every (run, item) pair holding one of the 45 requirement-only findings (recomputed from `findings.csv`: 12 yes, 14 partial, 19 no) or 30 blocking test-focus findings (17 with cause TEST): 35 pairs.

**Two commits per item.** The head is the round's own `<round>.base` file in the run folder, cross-checked against `ow/<item>`'s reflog at the round's `.start` time; they agree for every AMC item. The build base is `<item>.base`, looked up through earlier runs; where the branch had merged main, the base is the main parent of the newest first-parent merge before the head (insights-history 10-30, g10b, g10c, g10d, o1). One head is INFERRED: `ow/diagram` and its reflog are gone, so the head is the newest first-parent commit of the merge's branch side committed before `rv-diagram.start`. `base_how` and `head_how` in `items.json` name the rule per item. Findings from re-review or post rounds are judged against the first review's head; their own round heads are recorded too.

**Dropped** (VERIFIED): 10 pairs, 19 findings (14 requirement-only, 5 test-focus). Seven dotfiles items reviewed in AMC runs (p1, p3–p6, o2, o3) and two router items have no commits in AMC; p7-cursor (10-27) has no recoverable head. In scope: **31 of 45** requirement-only (8 of the 12 "yes") and **25 of 30** TEST (13 of the 17 with cause TEST).

<!-- table:dropped -->
| item | findings | why |
| --- | --- | --- |
| amc-2026-10-27__p7-cursor | 1: rv-p7-post #1 (test) | no head found |
| amc-2026-10-30__router-launcher | 2: router-launcher-rereview #c2 (requirement), router-launcher-review #2 (requirement) | base b44ca0f269 not in the AMC repository; no head found |
| amc-2026-10-30__router-outcomes | 1: router-outcomes-review #2 (requirement) | base bb831b6b27 not in the AMC repository; no head found |
| amc-2026-10-31__p1 | 1: p1-review #3 (requirement) | base 567da2ece8 not in the AMC repository; head f3b74cbd9f not in the AMC repository |
| amc-2026-10-31__p3 | 1: p3-review #2 (test) | base 567da2ece8 not in the AMC repository; head f806264fe9 not in the AMC repository |
| amc-2026-10-31__p4 | 1: p4-review2 #8 (test) | base 567da2ece8 not in the AMC repository; head 08c1e69172 not in the AMC repository |
| amc-2026-10-31__p5 | 7: p5-review2 #2 (requirement), p5-review2 #3 (requirement), p5-review2 #4 (requirement), p5-review2 #5 (requirement), p5-review2 #6 (requirement), p5-review2 #7 (requirement), p5-review2 #8 (test) | base 567da2ece8 not in the AMC repository; head eae1d22c04 not in the AMC repository |
| amc-2026-10-31__p6 | 2: p6-review #1 (requirement), p6-review #2 (requirement) | base efea86a582 not in the AMC repository; head b7f56fc9cc not in the AMC repository |
| amc-2026-11-02__o2 | 1: o2-review #2 (test) | base efa173d7d3 not in the AMC repository; head 3064932e02 not in the AMC repository |
| amc-2026-11-02__o3 | 2: o3-rereview #c1 (requirement), o3-review #4 (requirement) | base efa173d7d3 not in the AMC repository; head 6325af7f01 not in the AMC repository |
<!-- /table -->

**Controls** (VERIFIED): AMC first reviews with no blocking requirement- or test-focus finding, and items never named in any finding: 33. Eligible (commits found, tests changed): 20. Shuffled with `random.Random(20261102)`, first 12 taken: gaps-3, drafts, notes-search, panel-menu, run-edges, tree, d1, d3, d4, f29, f35, s2.

**Requirements maps** (INFERRED, every one). Six worker sessions read each brief's MUSTs (`brief.py` `must_items()`) and the tests the branch added or changed, and wrote `items/<run>__<item>.map.json`: per MUST the tests, their kind (FAIL_TO_PASS or PASS_TO_PASS), runner (Vitest, Playwright, live) and whether the title or comments cite the MUST ("strict"). Only one AMC test (d1) cites a MUST number; "strict" mostly means a title restating the MUST. `scripts/validate_maps.py` confirmed every brief MUST appears in its map (VERIFIED for all 37) and found 7 maps with `it.each` or template-string titles, which the gate ran without a "missing" result. Strict results are derived from the full run's verdicts; real strict runs on d1, diff-colour and g10d matched on all 10 lines (`strict_check.json`, VERIFIED).

**Running.** `scripts/run_gate.py <phase>` calls `reqgate.py check --warn --json` on each item with `--repo ~/sandbox/personal/agent-mission-control --timeout 180`; phase `f2p` with `--mutants none`, the Stryker phases with `--stryker-timeout 1200` and AMC main's Stryker config (Vitest runner, `perTest`, concurrency 4), one item at a time (`scripts/stryker_queue.py`). Each run waits for `sweep.py load` (every recorded exit 0) and checks for leftover gate worktrees (none left at the end). `scripts/analyse.py` and `scripts/splice.py` build the tables. No old commit failed on main's `node_modules`: all 145 base load failures name a `src/` module the branch adds, none a package (VERIFIED by reason text), so "environment" never applied.

## Q1. Past findings: what the gate catches

**Caught**: the gate fails the finding's own test for a test-quality reason (FAIL_TO_PASS passing on the base, PASS_TO_PASS killing no mutant, failing at head). **MUST flagged**: such a reason on another test of the finding's MUST. **None only**: the MUST has no test, reported but not failed. **Flagged, not for this**: the item fails only for absent base code, an unrunnable Playwright or live test, or similar. **Miss**: otherwise. Finding-to-MUST links are INFERRED by the map workers from the review text.

<!-- table:q1requirement -->
| verdict | map | strict | map, SWE | strict, SWE |
| --- | --- | --- | --- | --- |
| MUST flagged | 1 | 1 | 1 | 1 |
| none only | 0 | 7 | 0 | 7 |
| flagged, not for this | 26 | 18 | 11 | 6 |
| miss | 4 | 5 | 19 | 17 |

Crossed with the graded column (map rule):

| graded would catch | n | caught | MUST flagged | other |
| --- | --- | --- | --- | --- |
| no | 14 | 0 | 0 | 14 |
| partial | 9 | 0 | 1 | 8 |
| yes | 8 | 0 | 0 | 8 |
<!-- /table -->

<!-- table:q1test -->
| verdict | map | strict | map, SWE | strict, SWE |
| --- | --- | --- | --- | --- |
| caught | 2 | 1 | 2 | 1 |
| MUST flagged | 2 | 3 | 2 | 3 |
| none only | 2 | 11 | 2 | 11 |
| flagged, not for this | 16 | 8 | 10 | 7 |
| miss | 3 | 2 | 9 | 3 |

Crossed with the graded column (map rule):

| graded cause | n | caught | MUST flagged | other |
| --- | --- | --- | --- | --- |
| cause TEST (a test that cannot fail) | 13 | 0 | 2 | 11 |
| other cause | 12 | 2 | 0 | 10 |
<!-- /table -->

Per finding (graded = the note's `test_would_catch` for requirement-only, the cause for TEST; kinds are the gate's reasons under the map rule):

<!-- table:q1rows -->
| item | finding | focus/cause | graded | map | strict | map, SWE rule | kinds (map) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| diagram (2026-10-27) | rv-diagram #2 | requirement/MUST | yes | flagged, not for this | none only | flagged, not for this | F2P load on base (new module); unsupported runner (playwright) |
| big-files (2026-10-28) | rv-big-files #4 | requirement/READ | yes | miss | none only | miss | pass |
| big-files (2026-10-28) | rv-big-files #5 | requirement/PRE | no | miss | miss | miss | pass |
| gaps-1 (2026-10-28) | rv-gaps-1 #2 | requirement/ADJ | no | miss | miss | miss | pass |
| pr-overview (2026-10-28) | rv-pr-overview #F4 | requirement/MUST | yes | flagged, not for this | none only | flagged, not for this | F2P error on base (other non-assertion); unsupported runner (playwright) |
| canvas-b (2026-10-29) | canvas-b-rereview1 #1 | requirement/PLAT | no | flagged, not for this | flagged, not for this | flagged, not for this | unsupported runner (playwright) |
| canvas-b (2026-10-29) | canvas-b-review1 #1 | requirement/BOUND | no | flagged, not for this | flagged, not for this | flagged, not for this | F2P error on base (missing export); unsupported runner (playwright) |
| canvas-b (2026-10-29) | canvas-b-review1 #2 | requirement/ADJ | no | flagged, not for this | flagged, not for this | flagged, not for this | unsupported runner (playwright) |
| insights-history (2026-10-29) | insights-history-rereview1 #1 | requirement/ADJ | partial | flagged, not for this | none only | miss | F2P load on base (new module) |
| clusters (2026-10-30) | clusters-review #1 | requirement/MUST | yes | flagged, not for this | flagged, not for this | flagged, not for this | F2P error on base (missing export); unsupported runner (playwright) |
| clusters (2026-10-30) | clusters-review #3 | requirement/DESIGN | no | flagged, not for this | flagged, not for this | miss | F2P load on base (new module) |
| diff-colour (2026-10-30) | diff-colour-review #1 | requirement/MUST | yes | flagged, not for this | none only | flagged, not for this | unsupported runner (playwright) |
| insights-history (2026-10-30) | insights-history-review #1 | requirement/PLAT | no | flagged, not for this | none only | miss | F2P load on base (new module) |
| markers (2026-10-30) | markers-rereview #4b | requirement/UIQ | yes | flagged, not for this | flagged, not for this | flagged, not for this | F2P load on base (new module); unsupported runner (playwright) |
| f6 (2026-11-02) | f6-rereview #1 | requirement/BOUND | no | flagged, not for this | flagged, not for this | miss | F2P load on base (new module) |
| f7 (2026-11-02) | f7-rereview #c3 | requirement/MUST | no | flagged, not for this | flagged, not for this | miss | F2P load on base (new module) |
| f7 (2026-11-02) | f7-review #3 | requirement/MUST | no | flagged, not for this | flagged, not for this | miss | F2P load on base (new module) |
| f7 (2026-11-02) | f7-review #4 | requirement/MUST | no | flagged, not for this | flagged, not for this | miss | F2P load on base (new module) |
| g10a (2026-11-02) | g10a-rereview #c1 | requirement/ADJ | no | flagged, not for this | flagged, not for this | miss | F2P error on base (other non-assertion) |
| g10a (2026-11-02) | g10a-review #1 | requirement/ADJ | partial | flagged, not for this | flagged, not for this | miss | F2P error on base (other non-assertion) |
| g10a (2026-11-02) | g10a-review #2 | requirement/MUST | partial | flagged, not for this | miss | flagged, not for this | unsupported runner (playwright) |
| g10b (2026-11-02) | g10b-review #3 | requirement/DESIGN | partial | flagged, not for this | flagged, not for this | flagged, not for this | F2P load on base (new module); unsupported runner (playwright) |
| g10b (2026-11-02) | g10b-review #5 | requirement/EDGE | yes | flagged, not for this | flagged, not for this | miss | F2P load on base (new module) |
| g10d (2026-11-02) | g10d-review #2 | requirement/MUST | partial | MUST flagged | MUST flagged | MUST flagged | F2P passes on base |
| g10d (2026-11-02) | g10d-review #3 | requirement/MUST | no | flagged, not for this | flagged, not for this | flagged, not for this | unsupported runner (playwright) |
| g91a (2026-11-02) | g91a-review #4 | requirement/MUST | partial | flagged, not for this | flagged, not for this | miss | F2P load on base (new module) |
| g93a (2026-11-02) | g93a-review #2 | requirement/MUST | yes | flagged, not for this | flagged, not for this | miss | F2P load on base (new module) |
| g93a (2026-11-02) | g93a-review #3 | requirement/MUST | partial | flagged, not for this | none only | miss | F2P load on base (new module) |
| g93a (2026-11-02) | g93a-review #4 | requirement/MUST | partial | flagged, not for this | flagged, not for this | miss | F2P load on base (new module) |
| o1 (2026-11-02) | o1-review #2 | requirement/ADJ | no | flagged, not for this | miss | miss | F2P error on base (missing export) |
| o1 (2026-11-02) | o1-review #3 | requirement/MUST | partial | miss | miss | miss | pass |
| pr-overview (2026-10-28) | rv-pr-overview #F5 | test/CONV | other | flagged, not for this | none only | flagged, not for this | F2P error on base (missing export); F2P error on base (other non-assertion); unsupported runner (playwright) |
| flake-3 (2026-10-29) | flake-3-review1 #1 | test/TEST | TEST | miss | none only | miss | P2P covers no changed line |
| flake-3 (2026-10-29) | flake-3-review1 #2 | test/DESIGN | other | caught | caught | caught | F2P passes on base |
| flake-3 (2026-10-29) | flake-3-review1 #3 | test/ADJ | other | caught | MUST flagged | caught | F2P passes on base |
| pr-threads (2026-10-29) | pr-threads-review1 #4 | test/TEST | TEST | flagged, not for this | none only | flagged, not for this | unsupported runner (playwright) |
| live-checks (2026-10-30) | live-checks-rereview2 #2b | test/ADJ | other | none only | none only | none only | none; unsupported runner (live) |
| live-checks (2026-10-30) | live-checks-review #2 | test/TEST | TEST | none only | none only | none only | none; unsupported runner (live) |
| f7 (2026-11-02) | f7-review #5 | test/TEST | TEST | flagged, not for this | none only | miss | F2P load on base (new module) |
| g10a (2026-11-02) | g10a-rereview #c2 | test/TEST | TEST | flagged, not for this | flagged, not for this | flagged, not for this | unsupported runner (playwright) |
| g10a (2026-11-02) | g10a-rereview #c3 | test/TEST | TEST | flagged, not for this | flagged, not for this | flagged, not for this | F2P error on base (missing export); unsupported runner (playwright) |
| g10a (2026-11-02) | g10a-review #6 | test/MUST | other | flagged, not for this | flagged, not for this | flagged, not for this | F2P error on base (missing export); unsupported runner (playwright) |
| g10a-post (2026-11-02) | g10a-post-rereview #c1 | test/TEST | TEST | flagged, not for this | flagged, not for this | flagged, not for this | F2P load on base (new module); unsupported runner (playwright) |
| g10b (2026-11-02) | g10b-rereview #c3 | test/MUST | other | flagged, not for this | flagged, not for this | flagged, not for this | F2P load on base (new module); unsupported runner (playwright) |
| g10b (2026-11-02) | g10b-review #6 | test/MUST | other | flagged, not for this | flagged, not for this | miss | F2P error on base (other non-assertion); F2P load on base (new module) |
| g10b (2026-11-02) | g10b-review #7 | test/MUST | other | flagged, not for this | flagged, not for this | flagged, not for this | F2P load on base (new module); unsupported runner (playwright) |
| g10c (2026-11-02) | g10c-rereview #c1 | test/TEST | TEST | miss | miss | miss | pass |
| g10c (2026-11-02) | g10c-review #4 | test/TEST | TEST | miss | miss | miss | pass |
| g10d (2026-11-02) | g10d-rereview #c1 | test/TEST | TEST | MUST flagged | MUST flagged | MUST flagged | F2P passes on base |
| g10d (2026-11-02) | g10d-review #4 | test/TEST | TEST | MUST flagged | MUST flagged | MUST flagged | F2P passes on base |
| g91a (2026-11-02) | g91a-review #5 | test/MUST | other | flagged, not for this | flagged, not for this | flagged, not for this | F2P load on base (new module); unsupported runner (playwright) |
| g92a (2026-11-02) | g92a-review #7 | test/MUST | other | flagged, not for this | none only | miss | F2P error on base (other non-assertion) |
| g93a (2026-11-02) | g93a-rereview #c1 | test/MUST | other | flagged, not for this | none only | miss | F2P error on base (missing export); F2P load on base (new module) |
| g93a (2026-11-02) | g93a-review #7 | test/TEST | TEST | flagged, not for this | none only | flagged, not for this | F2P load on base (new module); unsupported runner (playwright) |
| s1 (2026-11-02) | s1-rereview #1 | test/TEST | TEST | flagged, not for this | none only | miss | F2P load on base (new module) |
| s1 (2026-11-02) | s1-review #5 | test/MUST | other | flagged, not for this | none only | miss | F2P load on base (new module) |
<!-- /table -->

Why so low (INFERRED): the grader's "yes" imagines a test written *to the missed requirement*; the gate sees only the author's tests, which passed at head, so it fails a requirement-only finding only when the MUST maps to a test that cannot fail, or to nothing. Readers mapped every MUST they could; an honest author might leave more `none` lines, as the strict column's 7 suggest. Whether `none` fails the gate is already the owner's open call (SKILL.md "Gates and mutation controls"); if it did, the strict map would catch 8 of 31.

Where a gate limit touched Q1 (VERIFIED from reasons): 86 mapped Playwright lines error at head because the gate runs every `.ts` file with Vitest, and 3 live-suite lines. Some PASS_TO_PASS tests "cover no changed line" and the gate passes them as "not checked", including flake-3's TEST finding #1. g10a-post's Stryker run returned "attribution unavailable": the gate found neither of its two PASS_TO_PASS tests in Stryker's `testFiles`, though their template titles expand to the mapped names; why is OPEN, as the gate deletes Stryker's report with its worktree.

## Q2. Clean controls: false alarms

<!-- table:q2 -->
| control | Stryker checked | as run (Playwright counted) | map: fails? | kinds | strict: fails? | map, SWE: fails? | kinds (SWE) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gaps-3 | yes | FAIL | FAIL | F2P error on base (missing export) | FAIL | pass | - |
| drafts | no | FAIL | FAIL | F2P load on base (new module) | FAIL | pass | - |
| notes-search | no | FAIL | FAIL | F2P error on base (missing export) | FAIL | pass | - |
| panel-menu | no | FAIL | FAIL | F2P error on base (missing export) | FAIL | pass | - |
| run-edges | no | FAIL | FAIL | F2P error on base (other non-assertion); F2P passes on base | FAIL | FAIL | F2P passes on base |
| tree | no | FAIL | pass | - | pass | pass | - |
| d1 | yes | FAIL | FAIL | F2P load on base (new module) | FAIL | pass | - |
| d3 | no | FAIL | pass | - | pass | pass | - |
| d4 | yes | FAIL | FAIL | F2P error on base (missing export) | FAIL | pass | - |
| f29 | no | FAIL | FAIL | F2P error on base (missing export); F2P error on base (other non-assertion) | FAIL | pass | - |
| f35 | no | FAIL | FAIL | F2P error on base (missing export); F2P load on base (new module) | FAIL | pass | - |
| s2 | yes | FAIL | FAIL | F2P error on base (missing export) | FAIL | pass | - |

False alarms by kind (count of controls with at least one, map rule; SWE rule):

| kind | map | strict | map, SWE | strict, SWE |
| --- | --- | --- | --- | --- |
| F2P error on base (missing export) | 7 | 6 | 0 | 0 |
| F2P error on base (other non-assertion) | 2 | 1 | 0 | 0 |
| F2P load on base (new module) | 3 | 3 | 0 | 0 |
| F2P passes on base | 1 | 1 | 1 | 1 |
| none line (reported, not a failure) | 4 | 11 | 4 | 11 |
| **controls failed** | 10 | 10 | 1 | 1 |

As run, Playwright counted: 12 of 12 fail.
<!-- /table -->

Every assertion-only false alarm is absent code: a new module (3 controls), a missing export (7), another throw or timeout (2). The alarm both rules share, run-edges, is a FAIL_TO_PASS test passing on the base: a weak test or a mislabelled PASS_TO_PASS (INFERRED). No control raised "PASS_TO_PASS test with no killed mutant" or "attribution unavailable" (Stryker checked the 4 with Vitest PASS_TO_PASS lines). tree and d3 changed only Playwright tests.

## Q3. Mutants and minutes per change

<!-- table:q3 -->
| item | set | src lines added | phase | wall min | mutants generated | mutants run | Stryker statuses | gate's PASS_TO_PASS verdicts | ignoreStatic: wall min | ignoreStatic: generated / run |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| g10a-post | finding | 66 | p2p | 0.11 | 146 | 68 | NoCoverage 78, Killed 66, Survived 2 | P2P attribution unavailable | - | - |
| panel-menu | control | 40 | cost | 0.2 | 65 | 40 | Killed 36, NoCoverage 25, Survived 4 | - | - | - |
| live-checks | finding | 20 | cost | 1.32 | 39 | 36 | Survived 23, Killed 13, NoCoverage 3 | - | 1.28 | 39 / 36 |
| flake-3 | finding | 1 | p2p | 1.43 | 0 | 0 | - | P2P covers no changed line | 1.18 | 0 / 0 |
| diff-colour | finding | 133 | cost | 1.43 | 237 | 138 | NoCoverage 99, Killed 91, Survived 47 | - | - | - |
| s1 | finding | 124 | cost | 2.02 | 347 | 299 | Killed 216, Survived 83, NoCoverage 48 | - | 0.97 | 347 / 278 |
| d4 | control | 22 | p2p | 2.1 | 30 | 29 | Killed 26, Survived 3, NoCoverage 1 | pass | - | - |
| gaps-1 | finding | 15 | p2p | 2.11 | 37 | 36 | Killed 20, Survived 9, Timeout 7, NoCoverage 1 | P2P covers no changed line | 1.98 | 37 / 36 |
| gaps-3 | control | 37 | p2p | 2.74 | 76 | 71 | Survived 42, Killed 24, NoCoverage 5, Timeout 5 | pass | - | - |
| s2 | control | 32 | p2p | 3.82 | 130 | 54 | NoCoverage 76, Killed 36, Timeout 12, Survived 6 | P2P covers no changed line | - | - |
| d1 | control | 105 | p2p | 3.88 | 158 | 143 | Killed 100, Survived 41, NoCoverage 15, Timeout 2 | P2P covers no changed line; pass | 2.61 | 158 / 142 |
| big-files | finding | 96 | cost | 4.12 | 207 | 143 | Killed 113, NoCoverage 64, Survived 30 | - | - | - |
| notes-search | control | 197 | cost | 5.45 | 553 | 159 | NoCoverage 394, Killed 99, Survived 52, Timeout 8 | - | - | - |
| f29 | control | 177 | cost | 5.85 | 358 | 277 | Killed 246, NoCoverage 81, Survived 28, Timeout 3 | - | - | - |
| g10d | finding | 92 | p2p | 5.89 | 228 | 114 | NoCoverage 114, Killed 81, Survived 19, Timeout 14 | pass | - | - |
| o1 | finding | 137 | cost | 9.94 | 283 | 203 | Killed 167, NoCoverage 80, Survived 21, Timeout 15 | - | - | - |
| g93a | finding | 231 | p2p | 20.03 (Stryker timed out after 1200.0 s) | 0 | 0 | - | Stryker timed out | - | - |

median 2.74 min, largest 20.03 min over 17 items.

No Vitest test in the map, so no Stryker run: d3, tree.

Not reached inside the time budget (larger changes): canvas-b, clusters, diagram, drafts, f35, f6, f7, g10a, g10b, g10c, g91a, g92a, insights-history (10-29), insights-history (10-30), markers, pr-overview, pr-threads, run-edges.
<!-- /table -->

"Mutants generated" sums Stryker's statuses (`mutant_statuses`, from its `mutation-testing-elements` report); "mutants run" excludes NoCoverage, Ignored and Pending, as the gate does. Wall minutes cover the whole gate run; the FAIL_TO_PASS phase alone took a median 0.26, at most 1.19, minutes per item. The Stryker item's reference points were 110 mutants in 3.2 minutes (`fcfd240`) and 744 in about 60 (`d11a3f6`). The queue ran smallest change first and stopped at the time budget, so the table leans to small changes and is **partial**: 18 larger items were not reached (listed above; VERIFIED). g93a hit the 20-minute cap; the gate discards Stryker's progress on a timeout, so its progress is OPEN (a gate limit). **ignoreStatic** (with and without, 5 items, VERIFIED): s1 2.02 → 0.97 min with 21 of 299 mutants set aside, d1 3.88 → 2.61 min with 1 of 143, gaps-1 and live-checks unchanged, flake-3 has no mutant. Load from other workers varies, so the d1 gain is INFERRED to be partly noise; nothing approaches the Stryker item's 85%. Only Stryker's own statuses are reported, not the gate's `KilledByOtherTests`.

## Q4. New modules and absent code, under both rules

SWE-bench's harness counts a FAIL_TO_PASS test as failing on the base when it is missing from the log or its status is FAILED, ERROR or SKIPPED (`test_failed`, [swebench/harness/grading.py](https://github.com/SWE-bench/SWE-bench/blob/main/swebench/harness/grading.py), read 2026-11-02 with `tvly extract`), and as passing only on PASSED or XFAIL (`test_passed`). The paper defines FAIL_TO_PASS as failing before the PR and passing after ([arXiv 2310.06770](https://arxiv.org/abs/2310.06770), "Execution-based validation"). So an import error on the base is a valid failure for SWE-bench and a gate failure under D4. (VERIFIED)

<!-- table:q4 -->
| item | set | FAIL_TO_PASS | fail on assertion | load on base (new module) | error on base: missing export | error on base: other | passes on base | new source files | gate fails (D4) | gate fails (SWE) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| diagram | finding | 13 | 0 | 8 | 0 | 0 | 0 | 2 | FAIL | pass |
| big-files | finding | 12 | 9 | 0 | 0 | 1 | 0 | 0 | FAIL | pass |
| gaps-1 | finding | 7 | 7 | 0 | 0 | 0 | 0 | 0 | pass | pass |
| pr-overview | finding | 13 | 0 | 0 | 2 | 7 | 0 | 1 | FAIL | pass |
| canvas-b | finding | 18 | 1 | 4 | 4 | 1 | 0 | 3 | FAIL | pass |
| flake-3 | finding | 3 | 0 | 0 | 0 | 0 | 3 | 0 | FAIL | FAIL |
| insights-history | finding | 13 | 0 | 12 | 0 | 0 | 0 | 2 | FAIL | pass |
| pr-threads | finding | 15 | 3 | 0 | 0 | 0 | 0 | 1 | pass | pass |
| clusters | finding | 13 | 0 | 7 | 4 | 0 | 0 | 2 | FAIL | pass |
| diff-colour | finding | 7 | 0 | 4 | 0 | 0 | 0 | 2 | FAIL | pass |
| insights-history | finding | 14 | 0 | 13 | 0 | 0 | 0 | 2 | FAIL | pass |
| live-checks | finding | 6 | 2 | 0 | 0 | 0 | 0 | 0 | pass | pass |
| markers | finding | 9 | 0 | 7 | 0 | 0 | 0 | 2 | FAIL | pass |
| f6 | finding | 12 | 0 | 12 | 0 | 0 | 0 | 2 | FAIL | pass |
| f7 | finding | 9 | 0 | 9 | 0 | 0 | 0 | 1 | FAIL | pass |
| g10a | finding | 14 | 4 | 3 | 1 | 4 | 0 | 1 | FAIL | pass |
| g10a-post | finding | 3 | 0 | 2 | 0 | 0 | 0 | 1 | FAIL | FAIL |
| g10b | finding | 14 | 1 | 7 | 0 | 4 | 1 | 1 | FAIL | FAIL |
| g10c | finding | 9 | 9 | 0 | 0 | 0 | 0 | 0 | pass | pass |
| g10d | finding | 7 | 3 | 0 | 0 | 1 | 1 | 0 | FAIL | FAIL |
| g91a | finding | 11 | 0 | 10 | 0 | 0 | 0 | 2 | FAIL | pass |
| g92a | finding | 12 | 0 | 6 | 0 | 6 | 0 | 1 | FAIL | pass |
| g93a | finding | 15 | 0 | 12 | 2 | 0 | 0 | 2 | FAIL | FAIL |
| o1 | finding | 12 | 7 | 0 | 2 | 3 | 0 | 0 | FAIL | pass |
| s1 | finding | 15 | 5 | 8 | 0 | 0 | 0 | 1 | FAIL | pass |
| gaps-3 | control | 6 | 4 | 0 | 2 | 0 | 0 | 0 | FAIL | pass |
| drafts | control | 11 | 0 | 6 | 0 | 0 | 0 | 3 | FAIL | pass |
| notes-search | control | 12 | 1 | 0 | 6 | 0 | 0 | 1 | FAIL | pass |
| panel-menu | control | 8 | 3 | 0 | 3 | 0 | 0 | 0 | FAIL | pass |
| run-edges | control | 12 | 6 | 0 | 0 | 3 | 1 | 0 | FAIL | FAIL |
| tree | control | 5 | 0 | 0 | 0 | 0 | 0 | 0 | pass | pass |
| d1 | control | 8 | 0 | 8 | 0 | 0 | 0 | 1 | FAIL | pass |
| d3 | control | 2 | 0 | 0 | 0 | 0 | 0 | 0 | pass | pass |
| d4 | control | 6 | 5 | 0 | 1 | 0 | 0 | 0 | FAIL | pass |
| f29 | control | 14 | 6 | 0 | 5 | 1 | 0 | 0 | FAIL | pass |
| f35 | control | 12 | 2 | 7 | 2 | 0 | 0 | 1 | FAIL | pass |
| s2 | control | 9 | 4 | 0 | 2 | 0 | 0 | 0 | FAIL | pass |
<!-- /table -->

Totals (VERIFIED, `results.json`): of 300 Vitest FAIL_TO_PASS lines on 37 items, 82 fail on an assertion, 145 fail to load a module the branch adds (19 items), 36 call an export the base lacks, 31 throw another error or time out, and 6 pass on the base. Items failing the gate, assertion-only rule against SWE-bench's: findings 21 of 25 against 4; controls 10 of 12 against 1. At finding level (Q1, map against map SWE): requirement-only "flagged, not for this" falls 26 → 11 (the rest Playwright), "miss" rises 4 → 19; TEST "flagged, not for this" falls 16 → 10.

Neither rule tells a strong new-module test from a weak one: under D4 all fail, under SWE-bench's all pass. INFERRED: for code with no base, the established "can this test fail?" check is mutation testing, which the gate already runs on PASS_TO_PASS lines; extending it to FAIL_TO_PASS tests that fail to load on the base closes the gap at the Q3 cost.

## What the gate cannot catch, which the four review blocks still must

From the review record note's "What it can and cannot catch" (VERIFIED counts there), confirmed here:
- **What the author did not imagine.** Among the 167 blocking findings with an unmet requirement: MUST (46), another caller (ADJ, 31), event order (ORDER, 19), boundary values (EDGE, 17). Here 2 of the 16 ADJ, DESIGN, PLAT, BOUND and PRE findings in scope were caught, both flake-3's, by a FAIL_TO_PASS test passing on the base; the other 14 were missed or flagged for something else (VERIFIED, Q1 rows).
- **Requirements the author's passing tests never reached**, the whole requirement-only class above: 1 of 31 caught.
- **Anything in Playwright or the live suite**, until the gate can run them: browser and desktop behaviour, accessibility, theming (86 mapped lines here).
- **PASS_TO_PASS tests that cover no changed line**, which pass the gate as "not checked".

## Owner decisions

1. **Narrow reviews?** Options: (a) now; (b) after the gate is fixed and this evaluation rerun clean; (c) never on this gate. (a) saves credits but drops what the requirement and test blocks find, with almost nothing replacing it; (b) costs one rerun; (c) keeps today's cost. **Recommend (b)**, and keep the requirement and test blocks in full until then.
2. **Base-run rule for FAIL_TO_PASS.** (a) Keep D4's assertion-only rule: 10 of 12 clean controls fail, all for absent code. (b) SWE-bench's rule: 1 of 12, but a new-module test that cannot fail passes. (c) SWE-bench's rule plus the mutant check on FAIL_TO_PASS tests that fail to load on the base. **Recommend (c)**: the industry rule, plus the standard adequacy check where no base exists.
3. **Playwright and live tests in the map.** (a) Run them in the gate; (b) mark them and report "not checked"; (c) as is, failing every item with a browser test. **Recommend (b) now, (a) later**: (c) makes the gate unusable on AMC.
4. **Should `none` fail the gate?** (a) Yes: the strict map would catch 8 of 31 requirement-only findings, but every docs, operations or privacy MUST would need a test or waiver. (b) No, report it (today). **Recommend (b), listing `none` lines first in the review prompt.**
5. **PASS_TO_PASS tests that cover no changed line.** (a) Fail; (b) report as today. **Recommend (a)**: a guard touching none of the change shows nothing.
6. **The invented `KilledByOtherTests` key** (paused in p1's discuss.md). **Recommend dropping it** for Stryker's statuses and `killedBy`, per the standing rule on standard names.
7. **Stryker cost and ignoreStatic.** (a) ignoreStatic on by default: s1 ran in half the time, but static mutants are then untested; (b) off, as today. Keep concurrency 4 and the 20-minute cap either way, and have the gate keep Stryker's progress on a timeout. **Recommend (b)** until large items are measured: only 1 of 5 measured items changed much (Q3).

## Helps other items

- **A check that a test can fail must not run on code that does not exist yet** (category: test adequacy, mutation testing). Base runs say nothing about new modules; mutation does. User level (orchestrator-workers skill).
- **Grade "would a test catch it" against the test that would actually exist** (category: counterfactual evaluation bias). The note's 12 of 45 assumed a test written to the missed requirement; the gate checks the author's tests. User level.
- **A gate must run every test kind its map accepts, or say "not checked"** (category: CI gate failure modes; skill level).
- **Old AMC commits ran on main's `node_modules` with no package failure across 37 items** (category: environment drift; project level).
- **Clean controls are needed before trusting a gate's catch rate** (category: false-positive rate, base rates). Without them the 26 "flagged" requirement-only findings would read as catches. User level.

Case against: readers wrote the maps after the fact, and an author working under the gate would write tests to pass it, so past items may not show how the gate changes behaviour. Falsified by a rerun on new items with author-written maps where the fixed gate (decisions 2 and 3) fails the items whose review then finds requirement or test faults, and passes clean ones.
