# Build quality: why first reviews block, and what to change

Spike for the orchestrator-workers skill, 2026-10-30. Question (owner): "why do builds leave major issues? 26 of 28 first reviews blocked." Each claim is VERIFIED (read through `tvly extract`, read at path:line, or run), INFERRED or OPEN. "Our data" is the four run folders `~/.local/state/orchestrator-workers/amc-2026-10-27` to `-30`: 48 build rounds, 72 fix rounds, 33 reviews and 40 re-reviews. Data: [findings.csv](2026-10-30-build-quality/findings.csv) (one row per finding) and [first-reviews.csv](2026-10-30-build-quality/first-reviews.csv). Drafts ready to drop in: [preamble-worker.md](2026-10-30-build-quality/preamble-worker.md), [task-body.md](2026-10-30-build-quality/task-body.md), [fix.md](2026-10-30-build-quality/fix.md), [review.md](2026-10-30-build-quality/review.md) and the [software-testing skill](2026-10-30-build-quality/software-testing/SKILL.md) with two new references. Charts: [docs/design/build-quality.html](../docs/design/build-quality.html).

Terms used below. A **finding** is one problem a reviewer, the orchestrator, a merge gate or a live check raised. A **blocker** is a finding the reviewer called blocking and the orchestrator accepted as blocking (today's rule). A **first review** is the review of an item's first build. **Clean** means no blocker.

## In short

- **Q1 Our data.** VERIFIED: 26 of 27 first reviews in the 10-28 to 10-30 runs had a reviewer-blocking verdict, as `mine.py` counts them (its 27 include a rebuilt item's full review); under today's rule 24 of those 27 blocked. Counting only reviews of a first build, across all four runs, 34 of 37 blocked (92%). The owner's "28" is not reproduced exactly. The 133 blockers are mostly cases nobody listed: a missed event order (25) or adjacent path (25), an unchecked library or platform fact (20), a wrong structure (12), an edge value (11), an unhandled failure (9). Only 2 came from a brief that was silent on the rule. 34 arose after the first build (30 in fix rounds, 4 in a post-merge review); 31 of the 133 were a sibling an earlier fix had left (22) or a regression a fix introduced (9).
- **Q2 What makes a strong agent.** The evidence that holds up: discovery and a plan before code; targeted scenario questions, not long generic checklists; tests as the check, because models rarely correct themselves without an outside signal; small items; short instructions with the important ones first; a separate reviewer given the spec.
- **Q3 Existing methods and tools.** Adapt, don't adopt whole: EARS-style acceptance statements (Kiro), a written plan per task (obra/superpowers, Spec Kit), a pre-mortem, ODC's defect types, the PSP's checklist-from-your-own-defects loop. fast-check's scheduler and Stryker fit AMC but are new dependencies; the dotfiles keep runtime-patch mutation checks.
- **Q4 Proposals.** Five changes: a map-cases-facts method at the top of the preamble (P1); briefs with testable MUSTs, a RISK line and the cases the orchestrator already knows (P2); fix rounds that fix the class (P3); reviewer cause tags feeding a defect log and `mine.py --quality` (P4); orchestrator sizing and fact checks (P5). INFERRED: they would have prevented about 55 to 70 of the 133 blockers, for about 15 to 25% more build credits; the review-and-fix loop cost 1.11 times the build on the items that had one.
- **Q5 The measure.** First-review clean rate, baseline 8% (3 of 37); target 25% over the next 25 first reviews. Decide on blockers per first review instead (baseline 2.68): a drop to 1.5 shows with about 75 to 80% power after about 12 first reviews, while the clean rate needs about 59 per group to separate 8% from 25%.
- **Q6 Also.** The preamble's READ FIRST files went unread (CONTEXT.md in 2 of 47 builds); skills load only when a prompt names them (`software-testing` in 2 of 114 build and fix rounds); a lesson from 2026-10-16 already said to fix the class, and the fix template still says the opposite; the codebase has hot spots that keep producing the same classes.

What the changes gain and cost (INFERRED): roughly 40 to 50% of the blockers gone, the clean rate from 8% to about 25%, fix rounds from 1.77 to about 1 per looped item, for about 60 to 100 more credits and 5 to 8 more minutes per Opus build. The review-and-fix loop took 13,748 of 36,867 credits (37%) across the four runs.

## Q1 Our data: why the findings happened

### How I counted

- VERIFIED: every reviewer's last message, read with `python3 -B scripts/result.py <round>.jsonl` (72 review and re-review rounds), plus the findings in fix briefs for six 10-27 items reviewed in chat (`amc-2026-10-27/run10/*-fix1.md`), orchestrator-found defects in fix briefs (pre-review checks, merge gates, one live check), and acceptance from each fix brief's ACCEPTED and REJECTED lists and from PLAN.md's known-gap lines (`agent-mission-control/PLAN.md:547-551`, `:1694-1697`). Fixed-later comes from the next re-review. 264 findings, each paraphrased in under 20 words.
- VERIFIED, the owner's figure: `mine.py` over 10-28, 10-29 and 10-30 lists 27 items with a first-review count, 26 blocking (`mine.py <run> --repo …`, "blocking at review"). Counted from the findings with today's rule (the orchestrator accepted at least one blocker), 24 of those 27 blocked: notes-search's two blockers and the rebuilt insights-history's one were demoted to known gaps. The rebuilt insights-history review is of a branch first built on 10-28, so I count it as a fix-stage review below. Reviews of a first build only, all four runs, with the 10-27 items reviewed in chat: 34 of 37 blocked (92%); by the reviewer's own verdict, 35 of 37 (95%). OPEN: which 28 the owner counted.

### Two classifications

**What kind of defect (ODC).** I used IBM's Orthogonal Defect Classification, whose types and qualifier are defined in ODC v5.2 (VERIFIED, https://s3.us.cloud-object-storage.appdomain.cloud/res-files/70-ODC-5-2.pdf, §4.2.1-4.2.2): Assignment/Initialization, Checking, Algorithm/Method, Function/Class/Object, Timing/Serialization, Interface/O-O Messages, Relationship, each Missing, Incorrect or Extraneous. Adapted only by adding Test, Report and Documentation types for findings about tests and claims. Security findings also carry a CWE id (for example CWE-367 check-then-use, CWE-1427 prompt injection). The 133 blockers: Checking 30, Function 24, Timing 21, Algorithm 18, Assignment 13, Interface 13, Relationship 7; 79 Incorrect and 52 Missing. CWE: 1427 ten times in 6 items, 367 nine times in 7 items. Chillarege's point (VERIFIED, http://www.chillarege.com/docs/Papers/concept): the distribution of defect types is "the signature of the process", and a departure "points to the part of the process that is probably responsible". Here Checking and Timing dominate: validation and ordering, both things a builder decides before writing a line.

**Why the build let it through (cause).** No published list fits "why did an agent's build miss this"; LLM-bug taxonomies classify the defect, not the process gap (Tambon's "Missing Corner Case", 15.27% of 333 bugs, is the nearest; VERIFIED, https://arxiv.org/html/2403.08937). So I derived the causes from the findings, then checked them against the round logs:

| Cause | Meaning | Blockers (n=133) | Main home |
|---|---|---|---|
| ORDER | an event order, concurrency, restart or check-then-use case not considered | 25 | worker process; codebase hot spot |
| ADJ | another path, caller, adapter, record format or doc not covered | 25 | worker process (discovery) |
| PLAT | a library, platform or vendor behaviour not known or not checked | 20 | worker process; model knowledge |
| DESIGN | wrong structure, identity or derived state; regex where a parser fits | 12 | worker process (plan); model |
| EDGE | a boundary value or scale not considered | 11 | worker process (tests) |
| FAIL | an error, partial-failure or timeout path not handled | 9 | worker process |
| MUST | an explicit requirement missed, and its tests did not catch it | 7 | worker process (verification) |
| BOUND | outside input or a trust boundary not modelled | 7 | worker process; codebase |
| READ | an existing contract or convention broken without reading it | 5 | worker process (discovery) |
| TEST | the test could not fail, or was order-dependent | 5 | worker process; tooling |
| SPEC, CONV, UIQ, REUSE | silent brief; convention; UI quality; duplicated logic | 2, 2, 2, 1 | brief; skills; tooling; discovery |

The full set (264 findings, all labels) adds TEST 29, UIQ 19 and REPORT 18 (unsupported claims in the worker's report), which mostly sit in non-blocking findings and orchestrator checks.

VERIFIED, agreement: a second grader from another model family (gpt-6.1-sol, given only the paraphrases and the code definitions) coded a random 40: it agreed on 33 (Cohen's kappa 0.80), and on 37 when my secondary cause counts. The disagreements were mostly BOUND against ADJ for a fence or a path variant.

### Pareto and breakdowns

- **Overall:** ORDER, ADJ and PLAT make 53% of blockers; with DESIGN, EDGE and FAIL, 77%. Every one of these is a case or fact the builder could have listed before coding.
- **By stage:** 99 blockers at first build, 30 in fix rounds (20 a sibling the fix left, 9 introduced by the fix, 1 other), 4 in a post-merge review (2 siblings, 2 pre-existing). ORDER and ADJ are 18 of the 34 after-build blockers. VERIFIED, `references/lessons.md:191-195` (2026-10-16): "A fix prompt that names the failing cases gets those cases fixed, not their class." `assets/fix.md:4` still says "Fix only the findings below; do not widen the scope."
- **By run:** 10-27 44 blockers in 11 items (ORDER 10, PLAT 7); 10-28 20 in 7 (ADJ 8); 10-29 21 in 5; 10-30 48 in 15 (DESIGN 9, ORDER 8, ADJ 7, MUST 6). INFERRED: no trend; the mix shifts with what was built.
- **By kind:** host-state items (turns, runs) 9 of 18 blockers are ORDER; boundary items (containment, fencing) ADJ 8, ORDER 8, BOUND 6; UI items PLAT 12 of 43 (library focus and folding behaviour, React rules); dotfiles items ADJ 3 of 9 (record kinds, legacy names).
- **By size** (build active minutes: S up to 15, M 15-40, L over 40): mean blockers per first review S 1.6 (10 items), M 3.0 (17), L 3.1 (9). Clean first reviews: S 2, M 1, L 0.
- **Did the brief cover it?** 51 blockers fell under an explicit MUST or ruling, 17 were implied and 64 the brief did not mention. The briefs are detailed (run-edges' brief listed six event orders, `run1030/tasks.md:35`) and the build still missed variants of them.

### What the logs say about each cause

- VERIFIED, discovery: the preamble says "READ FIRST: AGENTS.md, CONTEXT.md, docs/testing.md and PLAN.md's Light rules" (`run1030/preamble.md:3`). Of 47 builds, 2 read CONTEXT.md (a third searched it and got matches from other files only; corrected after review) and 13 read docs/testing.md; several only measured them with `wc -c` (clusters, drafts; `files/docs_read.py` in the session). AGENTS.md was read by 1, which may be because Copilot CLI loads it itself (INFERRED, not visible in the logs).
- VERIFIED, adjacent code: for 16 adjacent-path or contract findings that cite code the build did not write, the build had opened the cited lines (±15) in 7 and never in 9 (for example drafts' fork copy and `deliver()`, stable-env's environment readers, markers' existing `.marker` class, live-checks' harness counter). So about half are "never looked" and half "looked but did not reason". A map step answers the first; a case list the second.
- VERIFIED, skills: across 114 build and fix rounds, `impeccable` loaded in 17 builds and `web-design-guidelines` in 13 (the preamble names both for UI work), `software-testing` in 2 rounds (both fix briefs that named it), and `verification-before-completion`, `diagnosing-bugs` and `karpathy-guidelines` in none. INFERRED: under `copilot -p`, a skill loads when a prompt names it, not from its description.
- VERIFIED, tests and discovery effort: builds ran tests often (median 11 test commands per build) and made a median 26 tool calls before their first edit. So the builds did discover and test; what they discovered and tested did not include the cases the reviews found. 18 findings were claims in the worker's report that the diff or the logs did not support.
- Compaction: compacted builds averaged 2.81 blockers per first review (16 items), others 2.37 (19). INFERRED: weak, and confounded with size (compacted builds are the large ones).
- Model and effort: Sonnet high builds averaged 1.67 blockers (9 items), Opus high 2.96 (24). INFERRED: not a model effect we can claim; the orchestrator gave Sonnet the smaller items (median 124 against 404 build credits). OPEN until the router assigns comparable items to both.

### Where the causes sit

| Home | Evidence | Share (INFERRED) |
|---|---|---|
| Worker process | no impact map, no case list, facts assumed, self-review by re-reading | most of ORDER, ADJ, PLAT, EDGE, FAIL, DESIGN: about 75% |
| Brief and orchestrator | fix template says "do not widen"; L items not split; vendor facts checked after merge (context-jump); briefs name requirements but not their cases | SPEC 2, siblings left or regressions from fixes 31, BUDGET 3, INTEG 1, and a share of the 64 "silent" |
| Codebase | turn and run state hand-rolled across `sessions.ts` and `runs.ts`; path containment re-done per feature (CWE-367 in 7 items); fence sinks scattered (CWE-1427 in 6 items) | a contributor to most ORDER and BOUND |
| Tooling | skills not loaded unless named; no automated contrast, focus or test-isolation checks; reviews carry no cause tag | UIQ, TEST, CONV, and the missing learning loop |
| Model | not separable in this data | OPEN |
| Review | 11 of 145 reviewer-blocking findings rejected or deferred (8%); 3 re-review rounds of one item gave no verdict | small |

For the sibling rubric note (review side), one line each: 133 of 145 reviewer-blocking findings were accepted (2 in part), so the reviewer's blocking label is rarely wrong; 34 blockers were found only by re-reviews and a post-merge review, so a cap on re-reviews would let fix-round regressions through; a cause and class tag per finding (draft [review.md](2026-10-30-build-quality/review.md)) makes this classification automatic; findings in [findings.csv](2026-10-30-build-quality/findings.csv) carry `label` and `security_severity` columns for re-scoring.

## Q2 What makes a strong implementation agent

Each line: the practice, the evidence and its strength, what it costs per build, and the causes it answers.

| Practice | Evidence (strength) | Cost per build | Answers |
|---|---|---|---|
| Discover, then plan, then code | Anthropic's Claude Code guide: "Explore, plan, code, commit… without them, Claude tends to jump straight to coding" (vendor). GitHub: an ideal task has "complete acceptance criteria" and "directions about which files need to be changed" (vendor). Agentless: combined localisation found the right file in 81.67% against 78.67% for the best single method (benchmark ablation) | 5-10 tool calls; a few minutes | ADJ, READ, REUSE |
| Targeted scenarios, not a generic checklist | Porter, Votta and Basili: scenario reviewers had "a higher fault detection rate", "checklist reviewers were no more effective than ad hoc reviewers" (replicated experiment). Gawande: short do-confirm lists of "killer items" (secondary) | a page of reading; the case table | ORDER, FAIL, EDGE, BOUND |
| Pre-mortem | Klein, HBR 2007: prospective hindsight "increases the ability to correctly identify reasons for future outcomes by 30%" (one study, cited by Klein; original not read) | 2-3 sentences | all case causes |
| Handle and test error paths | Yuan et al., OSDI 2014: "92%" of catastrophic failures from "incorrect handling of non-fatal errors" (large empirical study). Watanabe et al.: agents' "optimistic error handling" was the exemplar of bug-fix revisions, 47.7% of revisions on 214 agent PRs (empirical) | one test per failure path | FAIL |
| Tests as the check, not self-reflection | Kamoi et al. (TACL survey): "self-correction works well in tasks that can use reliable external feedback"; Huang et al.: without oracle labels, performance "even deteriorates" (peer-reviewed). Reflexion's 91% came from unit-test feedback (benchmark) | already paid: tests exist | MUST, TEST, REPORT |
| Reproduce first | Agentless: reproduction tests raised SWE-bench Lite from 27.00% to 32.00%, for $0.25 per issue against $0.01 (benchmark ablation) | one failing test per finding in fix rounds | fix-stage findings |
| Tests can pass and still be wrong | 29.6% of plausible SWE-bench patches behave differently from the reference, and 28.6% of those are certainly wrong (peer-reviewed differential testing) | n/a | why mutation checks and case lists matter |
| Mutation checks | Google: usefulness of surfaced mutants rose "from 20% to 80%" with feedback; mutants are "coupled with real faults" (Petrović et al., ICSE 2021); "statistically significant correlation" with real-fault detection (Just et al., FSE 2014) | minutes per check; Stryker incremental reruns only the delta (vendor) | TEST |
| Order and race tests | fast-check's scheduler "has been specifically designed for detecting and testing race conditions" (vendor docs); property-based tests are strongest on "complex code" (Goldstein et al., ICSE 2024, interviews) | a dependency; longer tests | ORDER |
| State design | React: "avoid contradictions in state… avoid redundant state" (vendor docs); statecharts make "impossible states" visible (Harel 1987; Stately docs) | a design note per stateful item | DESIGN, ORDER |
| Small batches, short instructions | DORA 2024: 25% more AI adoption, 7.2% lower delivery stability, attributed to larger batches (large survey). IFScale: the best models reach 68% at 500 instructions, with a bias towards earlier ones; "Lost in the middle" (peer-reviewed). Anthropic: keep always-loaded instructions short, "staying under 200" lines (vendor) | none; it is a rewrite | P5 sizing; P1 placement |
| A separate reviewer with the spec | Anthropic: a reviewer in a fresh context "isn't swayed by the reasoning that produced the code", and should check "every requirement… and the listed edge cases have tests" (vendor) | already in place | review side |
| Reuse | GitClear (vendor claim, 211 million lines): copy-pasted lines rose from 8.3% to 12.3% while moved (refactored) lines fell from 25% to under 10%, 2021 to 2024 | the map's reuse column | REUSE (1 blocker here) |
| Agent-PR outcomes | AIDev: agents' PR acceptance 15 to 40 points below humans (dataset study). CodeRabbit (vendor claim, 470 PRs): "concurrency and dependency correctness" issues about 2×, error-handling gaps about 2× | n/a | confirms our mix is typical |

Sources, all VERIFIED through `tvly extract` and saved in the session: https://www.anthropic.com/engineering/claude-code-best-practices (and the 2024 version via the Wayback Machine), https://docs.github.com/en/copilot/tutorials/coding-agent/get-the-best-results, https://www.cs.umd.edu/users/basili/publications/technical/T101.pdf, http://homepages.se.edu/cvonbergen/files/2013/01/Performing-a-Project-Premortem.pdf, https://www.usenix.org/system/files/conference/osdi14/osdi14-paper-yuan.pdf, https://arxiv.org/html/2509.14745, https://arxiv.org/html/2406.01297, https://arxiv.org/html/2310.01798, https://arxiv.org/html/2303.11366, https://arxiv.org/html/2407.01489, https://arxiv.org/html/2503.15223, https://storage.googleapis.com/gweb-research2023-media/pubtools/4203.pdf, https://homes.cs.washington.edu/~rjust/publ/mutation_testing_practices_icse_2021.pdf, https://homes.cs.washington.edu/~rjust/publ/mutants_real_faults_fse_2014.pdf, https://fast-check.dev/docs/advanced/race-conditions, https://harrisongoldste.in/papers/icse24-pbt-in-practice.pdf, https://react.dev/learn/choosing-the-state-structure.md, https://stately.ai/docs/state-machines-and-statecharts, https://dora.dev/ai/gen-ai-report/, https://arxiv.org/html/2507.11538, https://arxiv.org/html/2307.03172, https://www.gitclear.com/ai_assistant_code_quality_2025_research, https://arxiv.org/html/2507.15003, https://www.coderabbit.ai/blog/state-of-ai-vs-human-code-generation-report. The full source list with saved file names is in the appendix.

Language and framework skill, from our findings (INFERRED from the reviews, each a fact a builder could look up): React (a render that mutated a props set broke under StrictMode; Suspense needs an error boundary); Monaco (models are shared per URI; restoring view state also restores folds); Headless Tree (search blur moves focus; ArrowRight on a leaf advances, against the WAI-ARIA pattern); Node (`lstat` on `link/` follows the link; no `openat`, so containment needs descriptor checks); Electron (`ELECTRON_RUN_AS_NODE` leaks into child processes; a CSP does not stop WebRTC); git (`status` ignores untracked files unless asked); the Copilot SDK (schemas drop unknown fields; context-breakdown ids are snapshot positions). OPEN: no published agent skill covers these libraries; vercel-labs' React rules are about performance, not these.

Design patterns and data structures that recurred: identity by array position (clusters' dismissals), keys scoped too narrowly (worker numbers across runs), two requests that had to be one (drafts' send then clear), derived state stored (home-reorder's Reset), presentation fed back as the model (panel-menu), hand-rolled parsing of Markdown, tags and TypeScript with regular expressions (three items), and a greedy scheduler that reserved slots for blocked jobs (forecast). Algorithms that grow badly: whole-file synchronous parsing of gigabytes on the host thread (insights-history), snapshots appended forever (drafts).

## Q3 Existing frameworks, skills, libraries and tools

All VERIFIED through `tvly extract` or `gh api` (repository files), as marked in the session's survey. Rules: AMC light rules 2 (use an existing pattern first), 9 (augment the tools AMC already uses) and 12 (anything outside AMC needs a reason and a fallback); the dotfiles take the standard library only.

| Name | What it offers | Fit | Recommendation |
|---|---|---|---|
| EARS (Kiro specs) | "WHEN [condition/event] THE SYSTEM SHALL [expected behavior]" (kiro.dev/docs/specs/feature-specs/) | a text convention | adapt for MUST lines (P2) |
| GitHub Spec Kit | specify, plan, tasks, `/analyze` consistency check; Given/When/Then scenarios; `[NEEDS CLARIFICATION]` markers | MIT, heavy as a pipeline | adapt the analyze idea into `brief.py` |
| obra/superpowers | `writing-plans` (exact files and the test per task), `test-driven-development`, `verification-before-completion` | MIT; owner's skill of that name is the same lineage | adapt the plan step into the preamble; skip the strict test-first rule (Fucci et al.: sequence mattered less than small steps) |
| mattpocock/skills | `code-review` with two axes, standards and spec; upstream of four owner skills | MIT | re-diff the four shared skills; borrow the spec axis for review |
| BMAD, Agent OS | full agile-persona methods | heavy; custom licence (BMAD) | skip |
| Aider architect mode | plan and edit by two models; +3 to 5 points on its own benchmark (vendor) | needs a new runtime | skip the split; keep the idea as a plan step |
| ODC; PSP; CMMI CAR | defect types; checklists rebuilt from one's own defect log; causal analysis | text practices | adopt in the defect log and case lists (P4) |
| fast-check, @fast-check/vitest | model-based tests and a scheduler for races | MIT, a devDependency | trial on one host-state item (decision 3) |
| Stryker (vitest runner, incremental) | scored mutation testing on the delta | Apache-2.0, a devDependency | later, after the trial |
| oxlint type-aware (`oxlint-tsgolint`) | `no-floating-promises`, `no-misused-promises` (59 of 61 rules) | AMC already runs oxlint with `react/rules-of-hooks` and `exhaustive-deps` on (`.oxlintrc.json`); type-aware rules are off | adopt; INFERRED few of our findings would have been caught |
| knip, jscpd, dependency-cruiser | dead code, copy-paste, import rules | fit | later: REUSE caused 1 blocker |
| Electron security checklist | first-party checklist | fits | feed the boundary case list |
| Electronegativity | Electron scanner | archived | skip |
| ruff, mypy, Hypothesis, mutmut | Python lint, types, properties, mutation | conflict with stdlib-only | skip; `py_compile` and the owner's runtime-patch mutation checks |
| shellcheck for zsh | none: zsh support removed in 2015 by its maintainer | n/a | `zsh -n` for syntax |

Already owned under `~/.agents/skills/`: `software-testing` (flaky tests, runtime-patch mutation checks), `verification-before-completion` (evidence before claims), `diagnosing-bugs`, `karpathy-guidelines`, `impeccable`, `web-design-guidelines`, `receiving-code-review`. They overlap the proposals only in verification; none lists cases by risk, and none was loaded by builds that did not name it.

## Q4 Proposals

Prevention counts are INFERRED: for each blocker, I asked whether the step would plausibly have surfaced it, then discounted for self-review limits (the same model lists the cases it can think of; Kamoi et al.). The counts overlap, because fix rounds run under the same preamble as builds; the total below removes the overlap. Only P1 and P2 can move the first-review clean rate: P3 acts after the first review.

**P1. Map, cases and facts at the top of the preamble** (draft [preamble-worker.md](2026-10-30-build-quality/preamble-worker.md), with the [case lists](2026-10-30-build-quality/software-testing/references/case-lists.md) and [event orders](2026-10-30-build-quality/software-testing/references/event-orders.md) references). Six steps replace the one-line self-review: map everything that reads or writes what changes (by `grep`, with "not read" marked); list the cases from the risk's case list plus a pre-mortem; check each fact the design rests on; build in small steps; prove each case with a test that fails when broken; check rows against evidence, not memory. The report gains an impact map and a case table, which the reviewer checks.
- Answers ADJ, ORDER, PLAT, EDGE, FAIL, BOUND, READ, TEST: 107 of 133 blockers.
- Would likely have prevented about 40 to 50 (INFERRED): the 9 of 16 adjacent misses in unopened code are the map's direct target; the read-but-missed half, the orders and the failure paths need the case lists, where I expect about a third to a half to be caught; facts are caught only when the builder notices it relies on one.
- Cost: about 15 to 25% more build tokens (INFERRED from the discovery share of today's builds: 20 to 30 tool calls before the first edit). That is about 60 to 100 credits and 5 to 8 minutes on an Opus build (median 404 credits), 20 to 30 credits on Sonnet.
- How to tell: blockers per first review in the causes it targets; the share of blockers whose case was in the table but untested (a process slip) against not in the table (a list gap).

**P2. Briefs with testable MUSTs, a RISK line, known cases and facts** (draft [task-body.md](2026-10-30-build-quality/task-body.md); `brief.py` checks). Each MUST is written as "WHEN <event or state>, <part> SHALL <response>", with its cases. RISK selects the case lists. CASES THE ORCHESTRATOR KNOWS carries siblings and orders the orchestrator already sees (earlier findings in the same files, the second engine, old record formats). FACTS TO VERIFY names vendor facts to check before building. `brief.py` refuses a worker brief with a MUST lacking "SHALL", or without RISK, CASES and FACTS lines (each may say "none" with a reason).
- Answers MUST 7, SPEC 2, and raises P1's catch rate on the 51 blockers under a MUST: about 8 to 12 more (INFERRED).
- Cost: orchestrator minutes per brief; a few hundred tokens per prompt.
- How to tell: blockers whose cause is MUST or SPEC; `brief.py` refusals per run.

**P3. Fix rounds fix the class** (drafts [fix.md](2026-10-30-build-quality/fix.md) and the review tag). Each accepted finding is reproduced by a failing test, named as a class, and every member the impact map finds gets a test. The re-review checks the class.
- Answers the 31 blockers that were a sibling an earlier fix left (22) or a regression a fix introduced (9); would likely have prevented 12 to 18 (INFERRED: the 2026-10-16 lesson says the narrow fix was the cause, and a reproduce-first step lifted Agentless by 5 points). About half of these overlap with P1, which fix rounds also follow.
- Cost: about 20 to 40% more per fix round (median 164 credits), against a second fix round and re-review (about 213 credits and 21 minutes) avoided.
- How to tell: fix rounds per item (baseline 1.77 on looped items) and re-review blockers whose origin is fix-left or fix-reg (baseline 31).

**P4. Reviewer cause tags, a defect log and `mine.py --quality`** (draft [review.md](2026-10-30-build-quality/review.md)). The reviewer tags each finding with a cause and a class; `mine.py --quality` reports the measures in Q5 and a Pareto of causes per run; after each run the orchestrator appends accepted findings to a defect log and updates a case list when a class recurs (PSP's checklist update; CMMI's causal analysis and resolution, "identify causes of defects… and take action to prevent them from occurring in the future", VERIFIED through a CMMI-DEV v1.2 mirror).
- Prevents nothing by itself; keeps P1's lists true and makes the measure automatic.
- Cost: about 50 more output tokens per review; one script change.

**P5. Orchestrator: size, facts and timing.** Split an item expected over 45 minutes or touching two hot spots (L items averaged 3.1 blockers against 1.6 for S, and three rounds ran out of credits or time); check an INFERRED vendor fact live before the build, not after the merge (context-jump's ids); bring main into a branch before its review when main has moved under the files it touches (one stale selector).
- Answers 0 to 3 of the 133 blockers (INFERRED: PLAT blockers a live probe settles, and part of the size effect). Its main effect is on defects that were not review blockers: 3 rounds out of credits or time, 1 stale selector after main moved, and 1 live-check failure after a merge.
- Cost: more, smaller items (each pays a review, about 68 credits); a few cheap live probes.

Not proposed now, for the AMC backlog (codebase): one containment primitive for files, used everywhere (check-then-use races in 7 items); a written state model (statechart) for turns and runs before more features land in `sessions.ts` and `runs.ts`; type-aware lint; automated contrast and focus checks in `expectCleanLayout`.

Try first: P1 with its case lists and P3, in the same run, with P4's tags so the next run measures them. They can ship together and still be told apart: P1 shows in the first-review measures, P3 only in fix rounds per item and re-review blockers. P2 and P5 follow.

Total, INFERRED: P1 40 to 50, P2 8 to 12, P3 12 to 18 (about half shared with P1), P5 0 to 3: about 55 to 70 of the 133 blockers (40 to 50%). On the 99 first-build blockers, P1 and P2 alone about 45: blockers per first review from 2.68 to about 1.45.

## Q5 The measure

- **First-review clean rate:** reviews of an item's first build with no blocker accepted by the orchestrator, over all such reviews. Baseline VERIFIED: 3 of 37 (8%) across the four runs, 2 of 26 (8%) for 10-28 to 10-30. Under the reviewer's own verdict: 2 of 37 (5%). It stays easy to re-score under a new rubric: each finding row carries the reviewer's label and the security severity.
- **Companions, with baselines (VERIFIED):** blockers per first review, 2.68 (99 in 37; variance 2.11); blockers per item across all its rounds, 3.6 (133 in 37), which guards against splitting items just to make first reviews look clean; fix rounds per item that had a loop, 1.77; review-and-fix share of a run's credits, 37% (13,748 of 36,867); loop credits per looped item, median 267 and 22 active minutes, 1.11 times its build; defects found after merge, 5 (four post-merge review blockers and one live-check failure); build credits per first-reviewed item, median 404 (Opus builds) and 124 (Sonnet builds).
- **Target:** clean rate 25% and blockers per first review at most 1.5, over the next 25 first reviews. Reasoning: blockers per review have variance close to their mean (2.11 for 2.68), as a Poisson count would; if that holds, the chance of none at a mean of 1.4 is about 25% (INFERRED; a near-Poisson spread is consistent with, not proof of, that model). 40% would need a mean near 0.9, which I do not expect without the codebase work.
- **Signal against noise:** the clean rate is too coarse at our volume. Separating 8% from 25% with 80% power at the one-sided 5% level needs about 59 first reviews per group (75 two-sided). Blockers per first review is the statistic to decide on: a drop from 2.68 to 1.5 has 80% power after 12 first reviews if the baseline rate holds (75.5% when its uncertainty is resampled; corrected after review) and 87% after 16 (exact conditional Poisson test against the 37 baseline reviews, one-sided 5%, simulated), about one run of 10-30's size. Write the test, its side and the stopping point down before the run. Report the clean rate as the headline; decide on the count.
- **Reported automatically:** `mine.py --quality` (P4) per run: first reviews, clean rate under both the reviewer's and the orchestrator's verdict, blockers per first review, fix rounds per item, loop credit share, post-merge defects and a cause Pareto from the reviewer's tags. Acceptance needs one record the orchestrator already makes: the fix brief's ACCEPTED and REJECTED lists, or a one-line `<item>.accepted` file.

## Q6 Anything else

1. **Instructions that are never acted on are cost, not control.** The AMC preamble is 9.3 KB with 19 hard rules; its READ FIRST files were read in 2 to 13 of 47 builds. IFScale and "lost in the middle" both say early, few and salient beats long. The draft moves the method to the top and keeps the rules list the same length.
2. **Skills need naming.** A skill a build should use goes into the preamble or brief by path; descriptions did not trigger it under `copilot -p` in our logs.
3. **Lessons need homes that act.** The 2026-10-16 lesson on fixing the class sat in `lessons.md` while `fix.md` said the opposite. A lesson that changes how a worker builds belongs in a template or a check, with the lesson linking to it (the owner's own rule on recurring mistakes).
4. **Report claims.** 18 findings were claims in the worker's report the diff did not support, mostly about coverage. The case table makes each claim point at a test, which the reviewer can read.
5. **Codebase hot spots.** Host-state and boundary items (turn and run state; containment and fencing) carried 49 of the 133 blockers in 12 of the 37 first-reviewed items, mostly ORDER, ADJ and BOUND. Process changes reduce them; a shared containment primitive and a state model would remove whole classes.

## Decisions for the owner

1. **How the build method reaches workers.**
   1. In the preamble only: cheapest, no skill change; the lists live in one template and grow it.
   2. **Recommended:** the preamble's six steps plus the case lists as `software-testing` references that the preamble names by path. The lists stay short, are reused by any agent that tests, and P4's defect log updates them in one place.
   3. Adopt obra/superpowers' `writing-plans` and `test-driven-development` as written: an outside method, more ceremony, and its strict test-first rule is not where the evidence points.
   Binds: the preamble's length and the review prompt, which checks the case table.
2. **Fix rounds.**
   1. Keep "fix only the findings below".
   2. **Recommended:** fix the class: reproduce, name the class, test each member. 31 of 133 blockers were siblings left by narrower fixes or regressions from them, and the lesson already says so.
   Binds: `fix.md`, `rereview.md` (checks the class) and the one-fix-round rule, which becomes easier to keep.
3. **Test libraries for orderings in AMC.**
   1. None: hand-written seams and runtime-patch mutation checks.
   2. **Recommended:** trial fast-check and @fast-check/vitest as devDependencies on one host-state item; host-state blockers were half orderings, and its scheduler generates orders a builder does not list. Light rules 2 and 12: a well-known MIT test library, not bundled into the app.
   3. Also Stryker incremental for scored mutation runs: wait until the trial shows the case table works.
   Binds: AMC's ALLOWED DEPENDENCIES for those items and its docs/testing.md.
4. **Who classifies findings.**
   1. The orchestrator by hand after each run.
   2. **Recommended:** the reviewer tags a cause and class per finding, and `mine.py --quality` counts them; the orchestrator corrects tags when it accepts or rejects. Agreement between two model families on a 40-finding sample was 83% (kappa 0.80), so tags are usable with spot checks.
   Binds: `review.md`, `rereview.md`, `mine.py`, and the sibling rubric's grading columns.

## Build plan

Each phase fits one worker session.

1. **Fix rounds and briefs (dotfiles).** Replace `assets/fix.md` and `assets/task-body.md` with the drafts; extend `brief.py`: a worker brief's MUST lines contain "SHALL", and RISK, CASES THE ORCHESTRATOR KNOWS and FACTS TO VERIFY are present and filled. Tests in `test_brief.py`: a brief without RISK fails; a MUST without SHALL fails; "none" with a reason passes; a fix prompt still passes. SKILL.md's prompt list, its fix-round line (the orchestrator saves the build's report as `<run>/<item>.report.md` with `result.py` and fills `{{BUILD_REPORT_PATH}}`) and the lesson link updated.
2. **Preamble and skill (dotfiles).** Replace `assets/preamble-worker.md` (remove `{{SELF_REVIEW_STEP}}` from SKILL.md's recipe), add `software-testing/references/case-lists.md` and `event-orders.md`, replace `software-testing/SKILL.md`. Tests: `brief.py check` on a filled sample of the new preamble plus body passes; every link in the new references resolves (a small link check); the AMC run preamble (`run1030/preamble.md` successor) is regenerated from the template in the next run.
3. **Review tags and measures (dotfiles).** Replace `assets/review.md`; add the class check to `assets/rereview.md`; `mine.py --quality`: first-review clean rate under both verdicts, blockers per first review, fix rounds per item, loop credit share, post-merge defects, cause Pareto from tags. Tests in `test_mine.py`: fixture rounds with tagged findings give the expected rate, counts and Pareto; an untagged review counts as "untagged"; acceptance read from a fix brief's ACCEPTED list.
4. **Orchestrator sizing (dotfiles).** SKILL.md's Start: split items over 45 minutes or touching two hot spots; live-check INFERRED vendor facts before the build; catch up with main before review when main touched the item's files. Test: `brief.py` warns when TIME BUDGET exceeds 45 (a warning, not a refusal).
5. **AMC trial (owner's decision 3).** One host-state item built with fast-check's scheduler, allowed by its brief. Measure its blockers against the host-state baseline (3.25 per first review).
6. **After two runs:** compare blockers per first review and fix rounds per item to the baselines here; update the case lists from the defect log; decide on Stryker and the codebase items.

Case against, from a reviewer of another model family (gpt-6.1-sol, given the note and drafts without my reasoning): the same model still invents both the cases and their test oracles, so more paperwork can reproduce the same blind spots, and 7 of the 16 adjacent-path misses were in code the builder had already read. What would falsify the recommendation: over comparable items, with the template followed, blockers per first review not falling below about 2 after 12 to 16 first reviews, or most blockers sitting on cases already in the case table with a passing test. Then the lever is the review (more, cheaper reviews of slices) or the codebase, not the brief. The same reviewer found four errors in my first draft, now corrected: the baseline counted a rebuilt item's review as a first review (8%, not 11%), the power figure used a normal approximation, P5's budget and integration findings were not blockers, and the fix template did not tell the fix round where the build's case table was.

## Appendix A: what could not be found out

- OPEN: which 28 first reviews the owner counted.
- OPEN: whether Copilot CLI injects AGENTS.md into `-p` sessions (not visible in the logs).
- OPEN: a model or effort effect on findings; the data confounds it with item size.
- OPEN: DORA 2025's seven capabilities (behind a form); Mitchell, Russo and Pennington's 1989 paper (cited by Klein only); Cursor's "best practices for coding with agents" (404, no archive).
- OPEN: costs of fast-check and Stryker on AMC's suite; not run.
- INFERRED throughout: the prevention estimates, the cost estimates and the target.

## Appendix B: sources and reads

Web pages were read through `tvly extract` by three research sub-agents in this session and saved under the session's `files/web/`; I re-checked 37 load-bearing quotes and figures against the saved pages (all found; Porter's only after undoing the PDF's letter spacing). Repository files (obra/superpowers, mattpocock/skills, anthropics/skills, github/spec-kit, BMAD, tsgolint, Electronegativity) were read with `gh api`. Reads that did not go through tvly: the raw README of `adamshostack/4QuestionFrame` with `curl` (the rendered page dropped the four questions); `gitclear.com/sitemap.xml` and `cursor.com/llms.txt` with `curl` to find live URLs (no content cited from them); one `curl -sIL` header check on Cursor's 404 page. Secondary sources marked as such: Gawande (book summary), STRIDE (Wikipedia), the CMMI-DEV v1.2 text (third-party mirror), Harel 1987 (mirror PDF).

Additional sources not linked above: ODC (http://www.chillarege.com/docs/Papers/concept; the v5.2 PDF), PSP (http://www.uml.org.cn/cmm/pdf/00tr0222.pdf, a mirror of CMU/SEI-2000-TR-022), Fagan 1976 (https://www.ida.liu.se/~TDDC90/literature/lab-papers/fagan76.pdf), Bacchelli and Bird (https://sback.it/publications/icse2013.pdf), Fucci et al. (https://arxiv.org/html/1611.05994), Rafique and Misic (https://raidoninc.com/assets/research/tddMetaAnalysis.pdf), SWE-agent (https://arxiv.org/html/2405.15793), Aider (https://aider.chat/2024/09/26/architect.html), Wang et al. (https://arxiv.org/html/2406.08731), Dou et al. (https://arxiv.org/html/2407.06153), Self-Refine (https://arxiv.org/html/2303.17651), CRITIC (https://arxiv.org/html/2305.11738), Chroma (https://research.trychroma.com/context-rot), Anthropic context engineering (https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents), Kiro (https://kiro.dev/docs/specs/feature-specs/), oxlint type-aware (https://oxc.rs/docs/guide/usage/linter/type-aware.html), Stryker (https://stryker-mutator.io/docs/stryker-js/incremental/), Electron security (https://www.electronjs.org/docs/latest/tutorial/security), shellcheck zsh (https://github.com/koalaman/shellcheck/issues/298), Google SRE postmortems (https://sre.google/sre-book/postmortem-culture).
