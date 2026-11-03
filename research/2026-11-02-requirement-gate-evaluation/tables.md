## Dropped finding items

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

## Q1 per finding

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

**45 requirement-only** (31 in scope):

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

**30 TEST** (25 in scope):

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

## Q2 controls

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

## Q3 cost

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

## Q4 new modules and absent code

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

## Summary

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
