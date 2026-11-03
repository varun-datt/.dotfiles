# Requirement gate evaluation: the gate on past AMC items, with clean controls

Research for task r4 (review record phase 4), 2026-11-02, corrected the same day after a cross-family critique. It reruns the unmerged requirement gate (`reqgate.py`, branch `ow/r3`, [D4](2026-11-02-review-focus-learning.md#d4-the-script-that-replaces-is-each-requirement-met)) on the commits the first review saw, for past items with requirement-only or TEST findings and 12 clean controls. Data and scripts: [2026-11-02-requirement-gate-evaluation/](2026-11-02-requirement-gate-evaluation/). Labels: VERIFIED, INFERRED, OPEN.

## In short

- **The gate catches almost none of the past requirement-only findings.** Of 31 in scope, it flags one finding's MUST for a test-quality reason (g10d); of the 8 graded "a named failing test would have caught it", 0. The grading imagined a test written to the requirement; the gate checks the author's tests, which passed. (VERIFIED counts; why INFERRED)
- **It catches no TEST finding directly.** Of 25 in scope it flags 2 at MUST level (g10d, both cause TEST, of 13). flake-3's two "catches" in the first version were a mapping artefact (Q1). (VERIFIED)
- **Under the assertion-only rule (D4) it fails nearly everything.** 10 of 12 clean controls fail, all for code absent on the base. Under a permissive rule (any non-pass on the base counts as failing; an AMC option, not SWE-bench's protocol, Q4), 1 of 12; 3 of 12 if PASS_TO_PASS tests covering no changed line also fail. As run today, Playwright included, 12 of 12. (VERIFIED)
- **Stryker per change: median 2.7 minutes and 158 mutants (15 known counts, 2 unknown); one item of 231 added lines hit the 20-minute cap** (17 of 35 items, smallest first; VERIFIED). ignoreStatic halved one item's time.
- **Recommendation: do not narrow reviews yet.** Fix the gate (a mutant check for tests of absent code, Playwright marked or run, three defects), then rerun on author-written maps against the acceptance bar.
- **Scope:** the kept cohort only (31 of 45, 25 of 30); the dropped findings differ in kind.

## At a glance

<!-- table:summary -->
| | assertion-only rule (D4), INFERRED map | D4, strict map | permissive rule (any non-pass on base), INFERRED map | permissive rule, strict map |
| --- | --- | --- | --- | --- |
| Requirement-only findings caught or MUST flagged (of 31; graded yes: of 8) | 1 (0) | 1 (0) | 1 (0) | 1 (0) |
| ... MUST had no test (`none`, reported, not failed) | 0 | 7 | 0 | 7 |
| ... item failed only for another reason | 26 | 18 | 11 | 6 |
| TEST-focus findings caught or MUST flagged (of 25; cause TEST: of 13) | 2 (2) | 2 (2) | 2 (2) | 2 (2) |
| ... MUST had no test (`none`, reported, not failed) | 2 | 11 | 2 | 11 |
| ... item failed only for another reason | 18 | 10 | 12 | 9 |
| Clean controls failed (of 12) | 10 | 10 | 1 | 1 |
| ... with decision 5 option a (PASS_TO_PASS covering no changed line fails) | 10 | 10 | 3 | 2 |
| Clean controls failed with Playwright counted, as the gate runs today | 12 | | 9 | |
| Minutes per change, base and head runs (median / largest, 37 items) | 0.26 / 1.19 | same | same | same |
| Minutes per change with Stryker (median / largest, 17 items; partial, smallest first) | 2.74 / 20.03 | same | same | same |
| Mutants generated per change (median / largest; 15 known, 2 unknown) | 158 / 553 | same | same | same |
<!-- /table -->

## Items, commits and how they were chosen

**Finding items** (VERIFIED, `scripts/discover.py` → `items.json`): every (run, item) pair holding one of the 45 requirement-only findings (12 yes, 14 partial, 19 no) or 30 blocking TEST-focus findings (17 cause TEST): 35 pairs.

**Two commits per item.** Head: the first review round's `<round>.base`, cross-checked against `ow/<item>`'s reflog at the round's `.start`; they agree for every AMC item. Corrected after review (`scripts/fix_heads.py`, VERIFIED): insights-history (run 10-29) was first reviewed in run 10-28, head `056a7c5` not `b01f282`; g10a-post's first review is `g10a-post-review2`, head `3bf211b` not `3bb9731`; old outputs are in `items/superseded/`. Base: `<item>.base`; where the branch had merged main, the main parent of the newest first-parent merge before the head (5 items). One head is INFERRED (diagram: branch and reflog gone; the newest branch-side commit before `rv-diagram.start`). `base_how` and `head_how` in `items.json` name the rule per item.

**Dropped** (VERIFIED): 10 pairs, 19 findings: seven dotfiles items and two router items have no commits in AMC; p7-cursor has no recoverable head. In scope: **31 of 45** requirement-only (8 of 12 "yes") and **25 of 30** TEST (13 of 17 cause TEST).

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

**Controls** (VERIFIED): of 33 AMC items whose first review had no blocking requirement- or test-focus finding, 20 had commits and changed tests; shuffled with `random.Random(20261102)`, first 12: gaps-3, drafts, notes-search, panel-menu, run-edges, tree, d1, d3, d4, f29, f35, s2.

**Requirements maps** (INFERRED, every one). Worker sessions read each brief's MUSTs (`brief.py` `must_items()`) and the branch's changed tests and wrote `items/<run>__<item>.map.json`: per MUST the tests, kind, runner and whether the title or comments cite the MUST ("strict"; only d1 cites a MUST number). `validate_maps.py` confirmed every MUST appears (37 maps, VERIFIED). Real strict runs on 3 items matched the derived strict results on all 10 lines (`strict_check.json`).

**Running.** `scripts/run_gate.py <phase>` calls `reqgate.py check --warn --json` on AMC: `f2p` with `--mutants none`, Stryker phases with `--stryker-timeout 1200` and AMC main's config (Vitest, `perTest`, concurrency 4), one at a time after `sweep.py load` exits 0; no gate worktree was left. No old commit failed on main's `node_modules`: all 141 base load failures name a `src/` module the branch adds (VERIFIED), so "environment" never applied.

## Q1. Past findings: what the gate catches

**Caught**: the finding's own test fails for a test-quality reason (FAIL_TO_PASS passing on the base, PASS_TO_PASS killing no mutant, failing at head). **MUST flagged**: such a reason on another test of its MUST. **None only**: the MUST has no test (reported, not failed). **Flagged, not for this**: the item fails only for absent base code, Playwright or similar. **Miss**: otherwise. Finding-to-MUST links are INFERRED.

<!-- table:q1requirement -->
| verdict | map | strict | map, permissive | strict, permissive |
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
| verdict | map | strict | map, permissive | strict, permissive |
| --- | --- | --- | --- | --- |
| MUST flagged | 2 | 2 | 2 | 2 |
| none only | 2 | 11 | 2 | 11 |
| flagged, not for this | 18 | 10 | 12 | 9 |
| miss | 3 | 2 | 9 | 3 |

Crossed with the graded column (map rule):

| graded cause | n | caught | MUST flagged | other |
| --- | --- | --- | --- | --- |
| cause TEST (a test that cannot fail) | 13 | 0 | 2 | 11 |
| other cause | 12 | 0 | 0 | 12 |
<!-- /table -->

Per finding (graded: `test_would_catch`, or the cause for TEST):

<!-- table:q1rows -->
| item | finding | focus/cause | graded | map | strict | map, permissive | kinds (map) |
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
| flake-3 (2026-10-29) | flake-3-review1 #2 | test/DESIGN | other | flagged, not for this | flagged, not for this | flagged, not for this | mapping artefact: F2P passes on base |
| flake-3 (2026-10-29) | flake-3-review1 #3 | test/ADJ | other | flagged, not for this | flagged, not for this | flagged, not for this | mapping artefact: F2P passes on base |
| pr-threads (2026-10-29) | pr-threads-review1 #4 | test/TEST | TEST | flagged, not for this | none only | flagged, not for this | unsupported runner (playwright) |
| live-checks (2026-10-30) | live-checks-rereview2 #2b | test/ADJ | other | none only | none only | none only | none; unsupported runner (live) |
| live-checks (2026-10-30) | live-checks-review #2 | test/TEST | TEST | none only | none only | none only | none; unsupported runner (live) |
| f7 (2026-11-02) | f7-review #5 | test/TEST | TEST | flagged, not for this | none only | miss | F2P load on base (new module) |
| g10a (2026-11-02) | g10a-rereview #c2 | test/TEST | TEST | flagged, not for this | flagged, not for this | flagged, not for this | unsupported runner (playwright) |
| g10a (2026-11-02) | g10a-rereview #c3 | test/TEST | TEST | flagged, not for this | flagged, not for this | flagged, not for this | F2P error on base (missing export); unsupported runner (playwright) |
| g10a (2026-11-02) | g10a-review #6 | test/MUST | other | flagged, not for this | flagged, not for this | flagged, not for this | F2P error on base (missing export); unsupported runner (playwright) |
| g10a-post (2026-11-02) | g10a-post-rereview #c1 | test/TEST | TEST | flagged, not for this | flagged, not for this | flagged, not for this | unsupported runner (playwright) |
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

Why so low (INFERRED): the grader's "yes" imagines a test written to the missed requirement; the gate sees the author's tests, which passed at head. If `none` failed the gate (decision 4), the strict map would catch 8 of 31.

Gate limits in Q1 (VERIFIED): 86 Playwright and 3 live lines error at head (the gate runs every `.ts` file with Vitest); PASS_TO_PASS tests covering no changed line pass as "not checked" (flake-3 #1). g10a-post's changed file has no related Vitest test, so Stryker stops with "No tests were executed", reported as "Stryker failed" (gate defect 2).

**flake-3's two apparent catches are a mapping artefact** (VERIFIED, `scripts/flake3_mutants.py` → `flake3/mutants.json`, per the software-testing mutation-checks procedure: in memory, one process per mutant, a `none` control). Its hygiene guards, mapped FAIL_TO_PASS, scan test files, which the gate copies onto the base, so they pass on any base. Each fails its own assertion on the form it targets (live tests) and misses the reviewer's case (an arrow or promisified sleep; the port in the browser config); the flag would stand for a correct guard too. TEST direct catches: 2 → 0.

## Q2. Clean controls: false alarms

<!-- table:q2 -->
| control | Stryker checked | as run (Playwright counted) | map: fails? | kinds | strict: fails? | map, permissive: fails? | kinds (permissive) |
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

False alarms by kind (count of controls with at least one, map rule; permissive rule):

| kind | map | strict | map, permissive | strict, permissive |
| --- | --- | --- | --- | --- |
| F2P error on base (missing export) | 7 | 6 | 0 | 0 |
| F2P error on base (other non-assertion) | 2 | 1 | 0 | 0 |
| F2P load on base (new module) | 3 | 3 | 0 | 0 |
| F2P passes on base | 1 | 1 | 1 | 1 |
| none line (reported, not a failure) | 4 | 11 | 4 | 11 |
| **controls failed** | 10 | 10 | 1 | 1 |
| controls failed if a PASS_TO_PASS test covering no changed line fails (decision 5, option a) | 10 | 10 | 3 | 2 |

As run, Playwright counted: 12 of 12 fail.
<!-- /table -->

Every assertion-only false alarm is absent code: a new module (3 controls), a missing export (7), another throw or timeout (2). run-edges, failing under both rules, has a FAIL_TO_PASS test passing on the base: weak or mislabelled (INFERRED). No control raised "no killed mutant" or "attribution unavailable". If PASS_TO_PASS tests covering no changed line failed (decision 5a), d1 and s2 would fail too: 3 of 12 permissive (2 strict); D4 stays at 10 (VERIFIED, `fails_nocover`).

## Q3. Mutants and minutes per change

<!-- table:q3 -->
| item | set | src lines added | phase | wall min | mutants generated | mutants run | Stryker statuses | gate's PASS_TO_PASS verdicts | ignoreStatic: wall min | ignoreStatic: generated / run |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| g10a-post | finding | 41 | p2p | 0.07 (Stryker failed (exit 1):   innerError: u) | unknown | 0 | - | Stryker failed | - | - |
| panel-menu | control | 40 | cost | 0.2 | 65 | 40 | Killed 36, NoCoverage 25, Survived 4 | - | - | - |
| live-checks | finding | 20 | cost | 1.32 | 39 | 36 | Survived 23, Killed 13, NoCoverage 3 | - | 1.28 | 39 / 36 |
| flake-3 | finding | 1 | p2p | 1.43 | 0 | 0 | - | P2P covers no changed line | 1.18 | None / 0 |
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
| g93a | finding | 231 | p2p | 20.03 (Stryker timed out after 1200.0 s) | unknown | 0 | - | Stryker timed out | - | - |

Mutants generated: median 158, largest 553 over 15 known counts; unknown for 2 (g10a-post, g93a).

median 2.74 min, largest 20.03 min over 17 items.

No Vitest test in the map, so no Stryker run: d3, tree.

Not reached inside the time budget (larger changes): canvas-b, clusters, diagram, drafts, f35, f6, f7, g10a, g10b, g10c, g91a, g92a, insights-history (10-29), insights-history (10-30), markers, pr-overview, pr-threads, run-edges.
<!-- /table -->

"Mutants generated" sums Stryker's statuses from its `mutation-testing-elements` report; "mutants run" excludes NoCoverage, Ignored and Pending. Wall minutes cover the whole gate run; the FAIL_TO_PASS phase alone took a median 0.26 minutes. The Stryker item measured 110 mutants in 3.2 minutes (`fcfd240`) and 744 in about 60 (`d11a3f6`). The queue ran smallest first, so the table is **partial**: 18 larger items were not reached. Unknown mutant counts (OPEN, gate limits): g93a hit the 20-minute cap and the gate discards Stryker's progress; g10a-post's Stryker stopped before mutating. The median is over the 15 known counts (the first version zero-filled g93a and used g10a-post's later head: 146). **ignoreStatic** (5 items, VERIFIED): s1 2.02 → 0.97 min (21 of 299 mutants set aside), d1 3.88 → 2.61 (1 of 143; partly load noise, INFERRED), gaps-1 and live-checks unchanged; nothing near the Stryker item's 85%.

## Q4. New modules and absent code, under both rules

**What SWE-bench actually does** (VERIFIED, `tvly extract https://arxiv.org/html/2310.06770v3`): building the benchmark, "we check log_pre for ImportError and AttributeError occurrences … we remove all task instances with such errors in their log_pre from consideration" (Appendix A.3); section 2 also excludes tasks whose tests "invoke newly created functions or classes". The `test_failed` predicate in `swebench/harness/grading.py` grades a *candidate* patch's run (A.4), not base eligibility; the first version wrongly called it "SWE-bench's rule". SWE-bench leaves such instances out, which a merge gate cannot do with an item. The column is renamed **permissive (any non-pass on the base counts as failing)**: an AMC policy option with no industry backing.

<!-- table:q4 -->
| item | set | FAIL_TO_PASS | fail on assertion | load on base (new module) | error on base: missing export | error on base: other | passes on base | new source files | gate fails (D4) | gate fails (permissive) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| diagram | finding | 13 | 0 | 8 | 0 | 0 | 0 | 2 | FAIL | pass |
| big-files | finding | 12 | 9 | 0 | 0 | 1 | 0 | 0 | pass | pass |
| gaps-1 | finding | 7 | 7 | 0 | 0 | 0 | 0 | 0 | pass | pass |
| pr-overview | finding | 13 | 0 | 0 | 2 | 7 | 0 | 1 | FAIL | pass |
| canvas-b | finding | 18 | 1 | 4 | 4 | 1 | 0 | 3 | FAIL | pass |
| flake-3 | finding | 3 | 0 | 0 | 0 | 0 | 3 | 0 | FAIL | FAIL |
| insights-history | finding | 11 | 0 | 10 | 0 | 0 | 0 | 1 | FAIL | pass |
| pr-threads | finding | 15 | 3 | 0 | 0 | 0 | 0 | 1 | pass | pass |
| clusters | finding | 13 | 0 | 7 | 4 | 0 | 0 | 2 | FAIL | pass |
| diff-colour | finding | 7 | 0 | 4 | 0 | 0 | 0 | 2 | FAIL | pass |
| insights-history | finding | 14 | 0 | 13 | 0 | 0 | 0 | 2 | FAIL | pass |
| live-checks | finding | 6 | 2 | 0 | 0 | 0 | 0 | 0 | pass | pass |
| markers | finding | 9 | 0 | 7 | 0 | 0 | 0 | 2 | FAIL | pass |
| f6 | finding | 12 | 0 | 12 | 0 | 0 | 0 | 2 | FAIL | pass |
| f7 | finding | 9 | 0 | 9 | 0 | 0 | 0 | 1 | FAIL | pass |
| g10a | finding | 14 | 4 | 3 | 1 | 4 | 0 | 1 | FAIL | pass |
| g10a-post | finding | 1 | 0 | 0 | 0 | 0 | 0 | 0 | FAIL | FAIL |
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

Totals (VERIFIED, `results.json`): of 296 Vitest FAIL_TO_PASS lines on 37 items, 82 fail on an assertion, 141 fail to load a module the branch adds (18 items), 36 call a missing export, 31 throw another error or time out, 6 pass on the base. Items failing, D4 against permissive: findings 20 of 25 against 5; controls 10 of 12 against 1.

**Gate defect 1, the classifier** (VERIFIED, `reqgate.py` about lines 359–361; every gate JSON searched): a base failure counts as an assertion only if every message starts with `AssertionError`. Vitest's `.rejects` mismatch ("promise resolved … instead of rejecting") lacks it, so big-files' MUST 3 test (`tests/unit/attachments.test.ts` about line 148) read as a runtime error: the only such line of 296. Corrected, big-files passes under D4 (findings failing 21 → 20 of 25); no finding verdict, control or permissive count changes. Borderline, not reclassified: g92a's MUST 3 line fails with Vitest's matcher `TypeError` (`.toMatch()` got undefined).

Neither rule tells a strong new-module test from a weak one (INFERRED): the established check where no base exists is mutation testing, which the gate already runs on PASS_TO_PASS lines.

## Kept and dropped findings

<!-- table:strata -->
| focus | cause | kept | dropped |
| --- | --- | --- | --- |
| requirement | ADJ | 6 | 2 |
| requirement | BOUND | 2 | 0 |
| requirement | DESIGN | 2 | 1 |
| requirement | EDGE | 1 | 6 |
| requirement | MUST | 15 | 4 |
| requirement | PLAT | 2 | 0 |
| requirement | PRE | 1 | 0 |
| requirement | READ | 1 | 0 |
| requirement | SPEC | 0 | 1 |
| requirement | UIQ | 1 | 0 |
| **requirement, all** | | **31** | **14** |
| test | ADJ | 2 | 0 |
| test | CONV | 1 | 0 |
| test | DESIGN | 1 | 0 |
| test | MUST | 8 | 0 |
| test | PLAT | 0 | 1 |
| test | TEST | 13 | 4 |
| **test, all** | | **25** | **5** |

Requirement-only findings by the graded column "a named failing test would have caught it":

| graded | kept | dropped |
| --- | --- | --- |
| no | 14 | 5 |
| partial | 9 | 5 |
| yes | 8 | 4 |
<!-- /table -->

The 19 dropped findings differ in kind (VERIFIED, `stratify()` in `analyse.py`): 6 of 14 dropped requirement-only findings are EDGE against 1 of 31 kept; 4 of 5 dropped TEST-focus findings have cause TEST. Every number here holds for the **kept cohort** only; boundary-value requirements and dotfiles' Python tests are OPEN.

## How far the after-the-fact maps could explain the low catch rate

The maps were written after the review; `validate_maps.py` checks only that every MUST appears, not that links or FAIL_TO_PASS/PASS_TO_PASS labels are right, and flake-3 shows labels can be wrong. INFERRED bounds: remapping cannot turn the 26 "flagged, not for this" into catches (they fail for absent code or Playwright), and the requirement-only 0 of 8 rests on the author's tests passing at head; the TEST result (2 of 13) is the one most exposed. OPEN: the error rate.

Cheapest separation: (1) **measure on the next run's author-written maps** (the gate needs them anyway; no extra credits); (2) a **blinded remap** of 5 seeded items by a reader from another model family, without the findings, reporting agreement on links and kinds (Cohen's kappa), rerunning only the f2p phase (about 0.3 minutes each). Recommend (1); (2) only if a number is wanted first.

## Acceptance bar: what "rerun clean" means

Proposed (INFERRED), checkable in the rerun's summary table, on author-written maps:
- **Catch rate**: at least half of blocking TEST findings with cause TEST caught or MUST-flagged; requirement-only rates reported per cause, no bar.
- **False alarms**: at most 1 of 12 or more seeded clean controls failing, for any reason; unsupported runners "not checked", never passed.
- **Artefacts**: every apparent catch passes a mutation check before it counts.
- **Cost**: median Stryker minutes per change at most 5; progress kept at the 20-minute cap.

Today the gate meets only the cost bar, on small changes.

## What the gate cannot catch, which the four review blocks still must

From the review record note's "What it can and cannot catch", confirmed here:
- **What the author did not imagine** (ADJ 31, ORDER 19, EDGE 17 of 167 in the note): 0 of the 16 ADJ, DESIGN, PLAT, BOUND and PRE findings in scope caught (VERIFIED).
- **Requirements the author's passing tests never reached**: 1 of 31 caught.
- **Anything in Playwright or the live suite** until the gate runs them (86 mapped lines here).
- **PASS_TO_PASS tests covering no changed line** ("not checked").

## Owner decisions

1. **Narrow reviews?** (a) Now: saves credits, but nothing measured replaces the requirement and test blocks (0 direct catches). (b) After the gate is fixed and a rerun on author-written maps meets the acceptance bar: one run's cost. (c) Never on this gate. **Recommend (b)**, keeping both blocks in full until then.
2. **Base-run rule for FAIL_TO_PASS tests of absent code.** (a) D4's assertion-only rule: 10 of 12 controls fail, all for absent code. (b) Permissive: 1 of 12, but a new-module test that cannot fail passes; an AMC policy with no industry backing. (c) SWE-bench-style: as SWE-bench excludes such tests, take them out of the base check and require a killed mutant on the new lines instead, at Q3's cost. (d) (b) now, (c) later. **Recommend (c)**: it follows what SWE-bench does (exclude, not pass) and keeps a can-it-fail check; (d) if Stryker on large items proves too slow.
3. **Playwright and live tests.** (a) Run them in the gate; (b) report "not checked"; (c) as is, failing every item with a browser test. **Recommend (b) now, (a) later.**
4. **Should `none` fail the gate?** (a) Yes: the strict map would catch 8 of 31 requirement-only findings, but every docs or operations MUST needs a test or waiver. (b) No, report it. **Recommend (b), listing `none` lines first in the review prompt.**
5. **PASS_TO_PASS tests that cover no changed line.** (a) Fail: controls rise from 1 to 3 of 12 permissive (d1, s2). (b) Report, as today. (c) Report them first, and fail only when no test of that MUST covers a changed line. **Recommend (c)**, revised from (a): d1 and s2 had other tests covering their change (INFERRED). Treat Stryker's "No tests were executed" as the same case.
6. **`KilledByOtherTests`** (paused in p1's discuss.md). **Recommend dropping it** for Stryker's statuses and `killedBy`.
7. **ignoreStatic.** (a) On: s1 ran in half the time, but static mutants go untested; (b) off. **Recommend (b)** until large items are measured; keep concurrency 4 and the 20-minute cap.
8. **Gate defects** (no gate code changed here): the `AssertionError`-prefix classifier (1 of 296 lines misread, 1 borderline); "No tests were executed" reported as a Stryker failure; progress discarded on timeout. **Recommend fixing all three** before the rerun.

## Helps other items

- **A can-it-fail check must not run on code that does not exist yet** (category: test adequacy, mutation testing). User level (orchestrator-workers skill).
- **Grade "would a test catch it" against the test that would actually exist** (category: counterfactual evaluation bias). User level.
- **A gate must run every test kind its map accepts, or say "not checked"** (category: CI gate failure modes; skill level).
- **Old AMC commits ran on main's `node_modules` across 37 items** (category: environment drift; project level).
- **Clean controls before trusting a catch rate** (category: false-positive rate). Without them 26 "flagged" findings would read as catches. User level.
- **Check a benchmark's protocol before borrowing its rule** (category: construct validity). SWE-bench's grader was read as its base rule. User level.
- **A test that scans the repo's own test files passes on any base once head tests are copied there** (category: test-kind labelling). Mutation-check each apparent catch. User level (software-testing skill).
- **Classify a runner's failures by its error types, not a message prefix** (category: test-result parsing). Skill level (orchestrator-workers).

Case against: an author working under the gate would write tests to pass it, so past items may not show how it changes behaviour. Falsified if the fixed gate, on new items with author-written maps, fails those whose review then finds requirement or test faults and passes clean ones.
