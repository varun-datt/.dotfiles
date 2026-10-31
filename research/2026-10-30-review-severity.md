# Review severity: what a review is for, a rubric, and a blocking rule

Spike for the orchestrator-workers reviews, 2026-10-30. Each claim is VERIFIED (read through `tvly extract`, run, or read at path:line), INFERRED or OPEN. "Our data" means the run folders `~/.local/state/orchestrator-workers/amc-2026-10-27` to `-30`. It holds 236 reviewer findings on 39 items, from 68 review and re-review rounds that `mine.py` logs plus 6 run-27 reviews held in the orchestrator's chat. Each finding was graded by hand: [findings.csv](2026-10-30-review-severity/findings.csv). The rubric is [rubric.md](2026-10-30-review-severity/rubric.md); the draft prompts are [review.md](2026-10-30-review-severity/review.md) and [rereview.md](2026-10-30-review-severity/rereview.md). Charts: [docs/design/review-severity.html](../docs/design/review-severity.html).

## In short

- **Q1 Purpose.** In the studies, reviews find mostly upkeep issues (75% in two studies; about 15% of comments point at a defect). The defects they do find are the ones tests miss: wrong behaviour, missed cases, races. Our review's job is narrower: stop what would hurt the owner, check the report's claims, and leave the rest to tools. AMC's gates cover types, lint, an accessibility scan, tests and a build. They lack a secret scan, a start-up size budget and colour-contrast checks, and they have no static security scan.
- **Q2 Major.** There are 11 areas, mapped to ISO/IEC 25010's nine characteristics, plus three the data added: paid spend, the checks themselves, and the author's report. "Major" means the owner loses data, leaks something, gets a wrong result or a broken flow, or a check stops working.
- **Q3 Rubric.** Severity comes from likelihood (normal use, plausible, contrived) against impact (harm, wrong, degraded, cosmetic), giving Blocker, Major, Minor or Nit. Pre-existing and Correction are separate classes. A Major must carry a failure scenario, file:line, and VERIFIED or INFERRED. An INFERRED Major gets reproduced before anyone fixes it.
- **Q4 Blocking.** Blocker and Major block. Minor goes to one tech-debt list per repository, which AMC's PLAN.md "Known gaps" lines already start. Nits are one counted line. The orchestrator rules on each finding and records it; the owner can overrule. Debt is paid when an item touches the same file, or when a class repeats.
- **Q5 Calibration.** Don't tell the reviewer "only majors": Anthropic's Opus 5 guidance warns models then report less. Ask for every finding, graded by rule, with minors in one line. Record each ruling as data and measure agreement. Depth follows the risk areas.
- **Q6 Our data.** Today 143 findings blocked; under the rubric 109 would, because 44 drop and 10 rise. First reviews that block go from 30 of 32 to 27 of 32. 8 rounds would not have run: 796 credits and 75 minutes, 6.0% of fix and re-review spend. No dropped finding has evidence of hitting the owner. Of the 44, 17 were real but contrived or minor.
- **Q7 Also.** Fixes caused at least 8 new defects. A reviewer re-raised a rejected finding. Corrections should not cost fix rounds. Review the brief, because unmet MUSTs are the cheapest catch. Reviews of documents need a claims rubric.
- **Gains and costs.** The rubric gains fewer and shorter fix rounds, grades that can be checked, and a debt list that gets paid. It costs a longer prompt (about 900 more words in), one ruling line per finding, and a list to tend. Its risk is that a real problem is graded "contrived". The second-grader check in Q6 and the "Check" list in the rubric are there to catch that.

## Q1 What a review is for, and what it leaves to tools

Facts, human review:

- VERIFIED, Mäntylä and Lassenius: "75 percent of defects found during the review do not affect the visible functionality"; they improved evolvability (https://aaltodoc.aalto.fi/server/api/core/bitstreams/cab054e8-0c06-47ab-8754-54bb09a0a6d3/content). Beller et al. found "the similar 75:25 ratio" in open source, and "7–35% of review comments are discarded" (https://sback.it/publications/msr2014.pdf).
- VERIFIED, Czerwonka et al. at Microsoft: "Only about 15% of comments provided by reviewers indicate a possible defect, much less a blocking defect"; at least 50% concern maintainability (https://www.microsoft.com/en-us/research/wp-content/uploads/2015/05/PID3556473.pdf).
- VERIFIED, Bacchelli and Bird: developers name finding defects as their top motive, but outcomes are mostly code improvement and understanding; "code and change understanding is the key aspect" (https://sback.it/publications/icse2013.pdf).
- VERIFIED, Sadowski et al. at Google: four purposes, "education, maintaining norms, gatekeeping, and accident prevention" (https://sback.it/publications/icse2018seip.pdf).
- VERIFIED, Bosu et al.: 64.2–68.6% of comments rated useful across five Microsoft products, 65.5% overall (https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/bosu2015useful.pdf).
- VERIFIED, Google's standard: approve once a change "definitely improves the overall code health … even if the CL isn't perfect"; "there is no such thing as 'perfect' code" (https://google.github.io/eng-practices/review/reviewer/standard.html).

Facts, AI review:

- VERIFIED, Cihan et al.: 73.8% of bot comments were marked resolved, but pull request closure grew from 5 h 52 min to 8 h 20 min, with "faulty reviews, unnecessary corrections, and irrelevant comments" (https://arxiv.org/html/2412.18531v1).
- VERIFIED: AI review comments on GitHub Actions were addressed 0.9–19.2% of the time, against 60% for humans (https://arxiv.org/html/2508.18771v2).
- VERIFIED: RovoDev's comments led to code changes 38.70% of the time, against 44.45% for human comments (https://arxiv.org/html/2601.01129v1).
- VERIFIED: SWR-Bench gives the best PR-review F1 as 19.38%. Aggregating several reviews raised F1 "by up to 43.67%" (https://arxiv.org/html/2509.01494v2).
- VERIFIED: 46.41% of agent-written fixes were rejected (https://arxiv.org/html/2606.13468v1). Mozilla's reviewers said an LLM assistant "sometimes focuses on low-priority findings, introducing noise" (https://arxiv.org/html/2505.16339v1).

Facts, vendors' own claims about their tools (claims, not independent results):

- VERIFIED, OpenAI Codex: the rubric has P0 ("Drop everything to fix") to P3 ("Nice to have"). A bug must be "introduced in the commit", must not "rely on unstated assumptions", and must have "provably affected" code identified (https://raw.githubusercontent.com/openai/codex/main/codex-rs/prompts/templates/review/rubric.md). On GitHub, "Codex flags only P0 and P1 issues" (https://learn.chatgpt.com/docs/third-party/github).
- VERIFIED, Claude Code Review uses three labels: Important ("should be fixed before merging"), Nit ("not blocking") and Pre-existing. A verification step "filters out false positives", and a review "never approves or blocks" (https://code.claude.com/docs/en/code-review-pull-requests, https://code.claude.com/docs/en/code-review).
- VERIFIED, Anthropic's security-review action reports "HIGH-CONFIDENCE" issues only, with hard exclusions (denial of service, rate limiting, outdated libraries, races "theoretical rather than practical"), a 0.7 confidence floor, and "Better to miss some theoretical issues than flood the report" (https://raw.githubusercontent.com/anthropics/claude-code-security-review/main/.claude/commands/security-review.md).
- VERIFIED, Qodo PR-Agent: "For clear bugs and security issues, be thorough. Do not skip a genuine problem just because the trigger scenario is narrow. For lower-severity concerns … If you cannot confidently explain why something is a problem with a concrete scenario, do not flag it" (https://raw.githubusercontent.com/qodo-ai/pr-agent/main/pr_agent/settings/pr_reviewer_prompts.toml). Qodo's threshold applies to inline comments only; a finding below it "is never dropped" from the summary (https://docs.qodo.ai/code-review/severity-thresholds).
- VERIFIED, Greptile: 79% of its comments were nits and 19% good. Having the LLM rate severity from 1 to 10 "was nearly random". Learning each team's bar from reactions raised the address rate from 19% to "55+%" (https://www.greptile.com/blog/make-llms-shut-up).
- VERIFIED, other vendors: CodeRabbit's "assertive" profile "may feel nitpicky" against the default "chill" (https://docs.coderabbit.ai/reference/configuration); Cursor Bugbot adds "learned rules" (https://cursor.com/docs/bugbot); Graphite calls acceptance rate its "most important metric" (https://www.braintrust.dev/customers/graphite); Uber's uReview pairs a generator with a grader from another vendor, suppresses "categories with historically low developer value", and reports 75% of comments rated useful (https://www.uber.com/us/en/blog/ureview); GitHub's Copilot code review card names hallucinated problems as a risk (https://docs.github.com/copilot/responsible-use-of-github-copilot-features/responsible-use-of-github-copilot-code-review).
- VERIFIED, tools: Google's analysis platform shows a check in review only if it has under 10% effective false positives. It turns a check off when "Not useful" clicks pass 10% (https://cacm.acm.org/research/lessons-from-building-static-analysis-tools-at-google). Developers first rated 85% of Google's surfaced mutants unproductive, until "arid" code was skipped (https://arxiv.org/html/2102.11378v2).

Facts, our gates:

| Check | Belongs to | In the gates today | Source |
|---|---|---|---|
| Types | tool | yes, `tsc` | AMC `package.json` `check` |
| Lint, including accessibility lint | tool | yes, Oxlint | same |
| Unit and OS tests | tool | yes, vitest | same |
| Browser tests with an accessibility scan | tool | yes, Playwright with axe in both themes | `docs/testing.md:221` |
| Build | tool | yes | same |
| Mutation checks (does a new test fail when its code breaks) | tool, run by the worker | by hand per item; the reviewer reads the results | orchestrator-workers `SKILL.md:246-256` |
| Dependency audit | tool | only in periodic maintenance, not per merge | AMC `scripts/maintenance.ts:170` |
| Secret scan | tool | dotfiles only, through the gitleaks hook; AMC has none | commit-guard skill |
| Static security scan | tool | none | none |
| Start-up size budget | tool | none; a reviewer found 1,314 characters of growth | finding `diff-colour` rereview |
| Colour contrast across themes | tool | axe in the views it visits; reviewers found 2 contrast failures | `markers`, `diff-colour` |
| Layout and visual checks | tool and a look | `expectCleanLayout` and the owner's rule to look at images | AMC `AGENTS.md:80-89` |

INFERRED: a review earns its cost on what tools cannot see: the brief's intent, the order of events, where outside text flows, what is lost when a step stops halfway, whether a test can fail, and whether the report is true. About 8 of our 109 Major or worse findings were tool-catchable (3 broken existing tests, 2 start-up size, 2 contrast, 1 flaky spec). Our reviewers spend almost nothing on style (1 maintainability finding, 8 Nits of 236), so the 75%-upkeep pattern does not appear; our noise is contrived security cases and repeats.

## Q2 What counts as major, area by area

Facts:

- VERIFIED: ISO/IEC 25010:2023 has nine product characteristics. Usability became "Interaction Capability" and Portability became "Flexibility", and "Safety" was added (https://quality.arc42.org/standards/iso-25010, https://iso25000.com/index.php/en/iso-25000-standards/iso-25010).
- VERIFIED: OWASP's Code Review Guide and its Application Security Verification Standard (ASVS 5.0.0) are the security references (https://owasp.org/www-project-code-review-guide/, https://owasp.org/www-project-application-security-verification-standard/). Google's guide lists design, functionality, complexity, tests, naming, comments, style and documentation (https://google.github.io/eng-practices/review/reviewer/looking-for.html).
- VERIFIED: the owner's attention rule says "a normal state is quiet or absent; colour, motion, badges … go only to what needs the person" (`~/.agents/skills/visual-house-style/SKILL.md`, "Screens people work in"). AMC requires turn and state changes to list event orders and get a review by a second model family (`AGENTS.md:74-79`).
- VERIFIED, our findings by area, counted from `findings.csv`: SEC 48, UX 39, COR 36, REL 30, VERIF 27, REPORT 19, DATA 16, PERF 12, COMP 5, DOC 2, MAINT 1, COST 1.

The checklist (INFERRED from the sources above and the 236 findings):

| Area | ISO 25010 | Major when | Example from our findings |
|---|---|---|---|
| COR correctness | Functional suitability | A MUST or owner ruling is unmet, or normal input gives a wrong result | Blocked items hold idle slots, so forecasts run long (`forecast-parallel`) |
| DATA integrity, loss, migration | Reliability, Safety | Owner data or typed text can be lost or overwritten | Stop during lookup clears unsent draft pieces (`drafts`, Blocker) |
| SEC security and privacy | Security | Outside text can steer a model, secrets leak, or an approval is bypassed | One approval authorises any later command of the same kind (`p7-cursor`, Blocker) |
| PERF performance, resources | Performance efficiency | Normal data hangs a flow, or a stated budget is broken | Parsing history blocks the host on the owner's 137 MiB lines (`insights-history`) |
| REL ordering, failure | Reliability | Stop, restart or a late event leaves wrong state or acts twice | After restart, a completed answer replays and can start an unapproved fix (`run-edges`) |
| UX experience, accessibility | Interaction capability | A flow breaks or misleads, focus is taken, contrast fails AA, or a normal state shouts | Leaving Find a file pulls focus back into the tree (`tree`) |
| COMP compatibility, operability | Compatibility, Flexibility | Start-up, upgrade or install fails, or owner settings drop | Stable start from an app terminal runs Electron as Node (`stable-env`) |
| COST paid spend | none | Paid calls can pass an approved budget | Live-suite counter bypassed, so paid sends exceed the limit (`live-checks`) |
| VERIF the checks | Maintainability (testability) | A check cannot fail, or an existing test breaks or flakes | Sleep guard misses a common sleep form (`flake-3`) |
| MAINT | Maintainability | Only when it blocks the next planned change | none in our data |
| REPORT the author's report | none | Never Major: a Correction | Report claims every reviewer mark is shown (`pr-overview`) |

Added areas, INFERRED. COST is new: AMC spends the owner's credits, and its testing rules turn on budgets (`docs/testing.md:6,83-85`). VERIF is separate because a check that cannot fail hides every later defect. REPORT is separate because 19 findings were about what the report claimed, not about the code. Safety in ISO's sense is DATA plus unapproved actions here.

## Q3 The severity rubric

Facts, published scales (all VERIFIED unless marked):

| Scale | Levels | What sets the level | Source |
|---|---|---|---|
| Codex review | P0–P3; only P0 and P1 posted on GitHub | Urgency, and "universal issues that do not depend on any assumptions about the inputs" for P0 | the rubric and GitHub URLs in Q1 |
| Google Issue Tracker | P0 (immediate) to P4 (eventually) | Outage, critical function, workaround | https://developers.google.com/issue-tracker/concepts/issues |
| Mozilla | S1 catastrophic (includes "data loss"), S2 serious, S3 normal ("a work around exists"), S4 trivial | Impact, lowered for "uncommon" steps | https://firefox-source-docs.mozilla.org/bug-mgmt/guides/severity.html, https://wiki.mozilla.org/BMO/UserGuide/BugFields |
| Microsoft SDL bug bar | Critical, Important, Moderate, Low | Impact, lowered when "extensive user interaction" is needed | https://learn.microsoft.com/en-us/security/engineering/security-bug-bar-sample |
| OWASP risk rating | Low, Medium, High from "Risk = Likelihood × Impact" | Two 0–9 scores | https://owasp.org/www-community/OWASP_Risk_Rating_Methodology |
| CVSS v4.0 | 0–10 base score | Exploitability and impact metrics | https://www.first.org/cvss/v4.0/specification-document |
| ISTQB | Severity: "the degree of impact that a defect has" | Impact, kept apart from priority | https://glossary.istqb.org/en_US/term/severity |
| Conventional Comments | Labels such as issue, suggestion, nitpick, with "(blocking)" or "(non-blocking)" decorations | The reviewer's label | https://conventionalcomments.org/ |
| Google comments | "Nit:", "Optional", "FYI" prefixes | The reviewer's label | https://google.github.io/eng-practices/review/reviewer/comments.html |
| impeccable (owner's skill) | P0 "Prevents task completion", P1 "significant difficulty or confusion", P2 "workaround exists", P3 polish | Impact on the user | `~/.agents/skills/impeccable/reference/critique.md:649-660` |

OPEN: Google's S0–S4 severity scale was not on the page read; IEEE 1044 is paywalled and was not read.

Proposal (INFERRED): one two-factor scale, taken from OWASP's likelihood × impact, with Mozilla's and Microsoft's habit of lowering a grade for uncommon steps. It uses words a model can apply, not scores.

| | L1 normal use | L2 plausible | L3 contrived |
|---|---|---|---|
| **I1 harm** (loss, leak, bypass, unapproved action) | Blocker | Blocker | Minor, shown to the owner |
| **I2 wrong** (wrong result, MUST unmet, broken flow, dead check) | Major | Major | Minor |
| **I3 degraded** (slow, confusing, barrier with workaround) | Major | Minor | Minor |
| **I4 cosmetic** | Minor | Nit | Nit |

Why these choices:

- **Three likelihood steps, not two.** Today's two-way rule splits the middle badly: Stop pressed mid-request is "normal use" to one reviewer and "far-fetched" to another. L2 names those moments; 52 of our 109 Major or worse findings are L2.
- **Outside text is hostile at L1.** Text from repositories, pull requests and models arrives in normal use, so prompt-injection paths stay Major. A local attacker racing the file system is L3.
- **I1 at L3 is Minor, but shown to the owner.** PR-Agent's "do not skip a genuine problem just because the trigger scenario is narrow" argues for keeping it visible. The owner's own rulings argue against blocking: he accepted the canvas race class on 2026-10-29 (AMC `PLAN.md:1352-1357`).
- **Words, not numbers.** Greptile found self-rated 1–10 severity "nearly random". Models state confidence in an inflated way (https://arxiv.org/html/2604.01457v1), and verbal confidence is calibrated only under some prompts (https://arxiv.org/html/2412.14737).
- **Evidence.** A Blocker or Major carries four things: a failure scenario ("when X, Y does Z, so the owner sees W"), file:line, the reason for each grade, and VERIFIED or INFERRED with the command that would confirm it. This follows Codex's "provably affected" and PR-Agent's "concrete scenario".
- **An unconfirmed Major** with no scenario goes under "Check". With a scenario but INFERRED, it blocks, and the fix round first reproduces it with a failing test; if it cannot, no code changes and the finding becomes a debt row marked "not reproduced" (as `references/lessons.md:191-195` advises). An INFERRED Blocker blocks until disproved: a false alarm costs less than lost data.

## Q4 The blocking rule and the tech-debt list

Facts:

- VERIFIED, today's rule: "a finding blocks only if it can happen with the owner's data or in normal use. Far-fetched findings are recorded and batched into a later item. The orchestrator accepts or rejects each finding, with a reason" (`dotfiles/dot_agents/skills/orchestrator-workers/SKILL.md:114-116`). Nothing records the batch or the reasons in a fixed place.
- VERIFIED: AMC's `PLAN.md` "Known gaps (review, not blocking)" lines already act as a debt list:
  - `notes-search`, 4 findings merged unfixed, 2 of them called blocking (`PLAN.md:543-551`);
  - `measures-view` (`:668-669`);
  - `insights-history` (`:1694-1697`);
  - the canvas race class (`:1352-1357`);
  - the pull-request deleted-first-line gap (`:1892-1893`).
- VERIFIED, AMC `PLAN.md:272`, the owner's standing rule from 2026-10-30: when a re-review or merge gate "leaves a specific finding after a branch's allowed fix round, one more round runs without asking, up to about 250 credits per branch".
- VERIFIED, Microsoft's playbook: issues not "in the scope of the PR" go to "separate tasks (e.g., bugs, technical debt). Don't block the current PR due to issues that are out of scope" (https://microsoft.github.io/code-with-engineering-playbook/code-reviews/process-guidance/reviewer-guidance/).
- VERIFIED, Fowler: debt is prudent or reckless, deliberate or inadvertent, and prudent debt "may not be worth paying down if the interest payments are sufficiently small – such as if it were in a rarely touched part" (https://martinfowler.com/bliki/TechnicalDebtQuadrant.html).
- VERIFIED: SQALE measures debt as "remediation cost" and adds the costs up (https://en.wikipedia.org/wiki/SQALE). MADR records decisions as dated files with options and consequences (https://adr.github.io/madr/).

Proposal (INFERRED):

- **What blocks.** Blocker and Major block a merge and cost a fix round; nothing else does.
- **Re-review scope.** Only the fixed Blocker and Major findings plus anything the fix diff breaks (a fix that trades one race for another is a new Major, as AMC learned on turn handling, `AGENTS.md:74-79`). Minors are not re-checked; untouched code is out of scope. A Blocker or Major left open gets the owner's one extra round; then the owner chooses to merge with a known-gap line or run another. Never a third re-review without him; canvas-b had five.
- **Who decides.** The reviewer grades; the orchestrator rules on each Blocker and Major (accept, demote or reject with a reason, or "not reproduced" after a fix round); the owner can overrule either. Each ruling is one line in `<run>/rulings.jsonl` (reviewer's grade, ruled grade, who, why); accepted known gaps also get a debt row.
- **The register.** One per repository at `docs/tech-debt.md`, which absorbs PLAN.md's known-gap lines. Each row holds: id, area, grade, file, a one-line scenario, the source round, the date, and the estimated minutes to fix (SQALE's remediation cost). Prudent or reckless isn't recorded: everything here is inadvertent and prudent by construction.
- **Paying down.** A brief that touches a listed file names its rows; the worker fixes those under about 15 minutes. A class seen 3 times becomes a planned item. Past about 30 open rows, each run plans one debt item. A row untouched for 3 runs is re-graded: closed "won't fix" with a reason, or kept (Fowler's rarely-touched point).
- **Nits.** One counted line in the review, never listed and never stored.

## Q5 Reviewer recall and calibration

Facts:

- VERIFIED, Anthropic, for Claude Opus 5: "If your review prompt says 'only report high-severity issues' or 'be conservative,' the model might follow that instruction literally and report less; ask it to report everything and filter in a separate pass instead" (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5).
- VERIFIED, the opposite design: Anthropic's security action filters at the source, with a 0.7 confidence floor and hard exclusions. Codex posts only P0 and P1. Qodo keeps everything in the summary.
- VERIFIED: aggregating several reviews raised F1 by up to 43.67% (SWR-Bench). uReview's best setup paired a generator with a grader from another vendor. Google keeps a check only while its "Not useful" ratio stays under 10%. Graphite tracks acceptance rate.
- VERIFIED, our orchestrator's rulings against the rubric:
  - Of 143 blocking findings, the orchestrator rejected 10. The rubric demotes 9 of those 10. The tenth, `forecast-parallel` #1, the orchestrator ruled intended; the rubric keeps it Major.
  - It accepted 30 findings that the rubric demotes, and those went into fix rounds.
  - A rejected finding was raised again as blocking, twice (`pr-overview`, a read-only POST).
- VERIFIED: lessons from 2026-10-16. "A cheaper shadow reviewer missed a reproduced blocker" (`references/lessons.md:221-222`). A fix prompt that names cases "gets those cases fixed, not their class" (`:191-195`).

INFERRED:

- **Report everything, filter by rule.** Telling the reviewer "majors only" risks the under-reporting Anthropic's guidance for Claude Opus 5 warns about, and it leaves no trail to calibrate against. Ask for every finding, graded by the rubric, with Minor findings as one line each and Nits as a count. The prompts' word limits (900 and 600) bound the token cost; the extra cost is mostly input, about 900 words of rubric. The filter is the rule, and a second model checks it: the orchestrator, from another family, rules on every Major, as uReview's grader does.
- **Calibrate from the rulings.** `mine.py` reads `rulings.jsonl` and reports, per area and reviewer model, the acceptance rate (target 75% or more, uReview's useful rate; Bosu found 65.5%), demotion rate, "not reproduced" rate, and demoted rows later proved real. An area under 50% acceptance for two runs gets a rubric rule or an exclusion, as Google turns off noisy checks. The owner's overrules are the gold labels.
- **Depth follows risk** (`references/routing.md:49-60`): a diff in a risk area gets max effort (which `review.sh` supports) plus that area's checklist block (the menu in the draft `review.md`), and every I1 at L3 is listed for the owner; other diffs get high effort and the base checklist; documents get a claims check (Q7). A second reviewer from a third family, merged as SWR-Bench aggregates, is worth a trial on risk-area diffs only, at about 68 credits a round; not proposed by default.

## Q6 Our own data

How I counted (VERIFIED, ran): `mine.py` over the four run folders (211 rounds); each review's last message through `result.py`, and for the 6 run-27 in-chat reviews the fix prompts that quote them. Each finding was graded by hand with its area, evidence level, whether the orchestrator accepted it (fix briefs, PLAN.md) and whether a later round fixed it (the fixer's report and the next re-review). 7 reviewed bundles had no findings. Tooling note: `mine.py` files 4 run-27 re-reviews (`rv-p7-fix1`, `rv-p7-fix3`, `rv-t7-fix1`, `rv-p6-fix1`) as fix rounds of items named `rv-*`.

Before and after (VERIFIED counts, grades INFERRED):

| | Today | Under the rubric |
|---|---|---|
| Findings that block | 143 | 109 (14 Blocker, 95 Major) |
| Blocking findings demoted | | 44 (42 Minor, 2 Pre-existing) |
| Non-blocking findings promoted | | 10 |
| First reviews that block (items with a verdict) | 30 of 32 | 27 of 32 |
| The same, with the 6 in-chat reviews | 36 of 38 | 33 of 38 |
| Re-review findings that block | 33 | 19 |

Of the 44 demotions, 26 are L3 (contrived): 12 in SEC, mostly file-system races and hostile names, and 14 elsewhere. 16 are L2: 14 degraded (I3) and 2 pre-existing. 2 are L1, both cosmetic.

The owner's "26 of 28" comes from `research/2026-10-30-router-effort-context.md:208`, counted at about 19:35 on 2026-10-30, before the last items were reviewed. My count by item with a verdict is 30 of 32 (94%), against 93% then. The same proportion; the exact 28 items are OPEN, because that doc does not list them.

Rounds that would not have run (VERIFIED costs from `mine.py`; which rounds is INFERRED). A chain stops at the first review where the rubric finds no Blocker or Major.

| Item | Rounds | Credits | Minutes |
|---|---|---|---|
| gaps-3 | fix1 | 99.5 | 20.1 |
| canvas-b | fix2, rereview2–5 | 633.0 | 41.8 |
| panel-menu | fix2, rereview2 | 63.4 | 13.3 |
| **Total** | **8 rounds** | **795.9** | **75.2** |

For scale: all rounds 36,695 credits; fix rounds 72 (11,610 credits, 2,324 minutes); re-reviews 34 (1,715 credits, plus 177 misfiled); reviews 34 (2,304 credits).

The 8 rounds are 6.0% of fix and re-review spend and 2.2% of all spend. The larger effect is scope. Fix rounds that also carried demoted findings could have been shorter. If fix cost scales with the number of findings, about 25% of 9,237 credits over 48 fix rounds, roughly 2,300, went to findings the rubric demotes (INFERRED, crude).

False negatives (VERIFIED from the records; INFERRED meaning): none of the 44 demoted findings has a record of hitting the owner's data or normal use; 17 were confirmed real (10 at L2, 7 at L3), true but contrived or minor, and become debt rows. One counter-case: `pr-threads` review #2 (zones drop extra selections, demoted to Minor), whose fix caused a new Major (restoring the view re-folds a thread). The rubric is also stricter in 10 places, for example a wrong "context filled" claim (`clusters`) and an existing browser test that now times out (`diff-colour`).

Consistency (INFERRED): one grader, me, with the hard calls on L2 against L3. 26 of 44 demotions turn on "contrived". To measure it, a grader from another model family should grade a stratified sample of 40 rows from `findings.csv` blind: 10 Blocker or Major, 20 demoted, and 10 others. Compute Cohen's kappa on the four levels, aim for 0.6 or more, and rewrite the definition behind each disagreement. Repeat it on every new run's rulings.

## Q7 Other things that matter

1. **Review is cheaper than fixing (VERIFIED costs).** A review round averaged about 68 credits and 6 minutes; a fix round about 161 credits and 32 minutes. NASA's study puts a requirements error fixed at build at 7–16 times the cost of fixing it at requirements, and 21–78 times at test (https://ntrs.nasa.gov/api/citations/20100036670/downloads/20100036670.pdf). At least 6 of our Major or worse findings were a brief MUST or owner ruling missed. A short review of the brief against the plan before the build is the cheapest catch (INFERRED).
2. **Fixes cause defects (VERIFIED, 8 cases).** Among them: a secret on the approval card (`p7-cursor`), a budget that broke the basic live check (`live-checks`), focus theft (`tree`), a lost note (`drafts`) and a replayed answer (`run-edges`). The re-review's job is mostly the fix diff, which the draft makes explicit. Build side: fix briefs should name the class and require a reproduction first.
3. **Rulings must reach the reviewer (VERIFIED).** A rejected finding came back twice (`pr-overview`). The draft adds a "prior rulings" field.
4. **Corrections are not code fixes (VERIFIED, 19 findings).** Report overclaims were 19 findings and 0 Majors. The orchestrator fixes the record without a fix round.
5. **Documents and research need their own check (INFERRED).** For them, the rubric's impact axis becomes "a decision would be made on a false claim". A Major is an unsupported claim that a decision rests on; a Minor is an unsupported claim nothing rests on. The reviewer checks each claim's source rather than each line.

Prompt noise (VERIFIED): some reviews printed the security-review summary table and a "follow-up options" menu, which come from the global instructions (`notes-search-review`). The drafts forbid both.

## Reuse check

Copied or adapted: OWASP's likelihood × impact (the matrix); Mozilla's and Microsoft's lowering for uncommon steps (L3); Codex's "introduced", "provably affected" and "no unstated assumptions" criteria; Claude Code Review's Important, Nit and Pre-existing classes; PR-Agent's concrete-scenario rule and its narrow-trigger exception (evidence, and I1 at L3 shown to the owner); Qodo's "never dropped" summary (report-all); Conventional Comments' blocking decorations (the per-finding label); Google's 10% turn-off and Graphite's acceptance rate (calibration); SQALE's remediation cost and Fowler's paydown test (the register); the owner's `impeccable` P0 and P1, folded into Major for UX.

Not fitting: CVSS (built for published vulnerabilities, too fine for a model in review); Microsoft's bug bar (shipped products); Anthropic's hard exclusions as written (they drop denial of service and rate limits, which are PERF and COST here); Greptile's and Bugbot's learned filters (they need thousands of reactions); CodeRabbit's profiles (a dial, not a rubric).

Invented: the L2 list of unlucky moments, the COST and VERIF areas, the "Check" list, and reproduce-first for INFERRED Majors.

## Build-side notes (for the sibling worker)

- 8 fixes caused new defects; fix briefs should name the class, list its members, and start with a reproduction.
- At least 6 Major or worse findings were unmet brief MUSTs or owner rulings; a brief check before the build would catch these.
- 19 findings were report overclaims; the worker's report template could require file:line for each claim.
- 3 existing tests broke and 1 spec flaked: the worker's gate run did not catch them before review.

## Decisions for the owner

Owner's rulings (2026-10-30): D1, D2, D3 and D4 all option 2, as recommended.

**D1. The blocking threshold.** It binds `SKILL.md`'s Lifecycle rule, the verdict count `mine.py` reads, the router's success reward (D1 of the 2026-10-30 router spike) and every fix brief.

1. Keep today's one-line rule and use the rubric only to describe findings.
2. The matrix: Blocker and Major block (I1 at L1–L2; I2 at L1–L2; I3 at L1). Minor goes to debt.
3. Only Blockers block. Majors go to a fix round only when the orchestrator judges the fix cheap.

Recommended: 2. Option 1 leaves the L2 middle to each reviewer's mood. Option 3 would have merged 95 Majors, including 6 unmet MUSTs.

**D2. What the reviewer reports.** It binds `review.md`, `rereview.md` and the calibration in D4.

1. Majors only.
2. Every finding, graded: Blockers and Majors in full, Minors one line each, Nits as a count.
3. Every finding in full.

Recommended: 2. It follows Anthropic's Opus 5 advice against "only high-severity", keeps an audit trail, and stays inside the word limits. Option 3 recreates today's noise.

**D3. Where minor findings go.** It binds AMC's `PLAN.md`, every brief that touches a listed file, and the run plan.

1. Only the run's records.
2. A register per repository at `docs/tech-debt.md`, absorbing PLAN.md's known gaps, with the paydown rules in Q4.
3. Items in the plan's backlog.

Recommended: 2. Option 1 is where today's "batched into a later item" goes to die. Option 3 mixes 1-minute fixes with features and loses the file link that makes paydown cheap.

**D4. How rulings are recorded and calibrated.** It binds `mine.py`, the orchestrator's procedure, and future rubric changes.

1. Free-text reasons in fix briefs, as today.
2. One line per Blocker or Major in `<run>/rulings.jsonl`, plus agreement figures in `mine.py`, plus a 40-row blind second grader each new rubric version.
3. Option 2, with the owner ruling every Major.

Recommended: 2. It turns rulings into data at about one line per finding. Option 3 puts 95 decisions per four runs on the owner.

## Build plan

Each phase fits one worker session, standard library only, with tests in the skill's `scripts/test_*.py`.

1. **Rubric and prompts.** Add `references/rubric.md`; replace `assets/review.md` and `assets/rereview.md` with the drafts; `review.sh` fills `{{RUBRIC}}` from the file. Update SKILL.md's Lifecycle rule to D1.

   Tests: `review.sh` refuses a prompt with `{{RUBRIC}}` unfilled; a filled prompt holds the matrix; `mine.py` still reads "Blocking: none" and "2 blocking" from fixture messages in the new format.
2. **Rulings.** `scripts/rule.py add <run> <round> <n> --grade Major --ruled Minor --by orchestrator --reason ...` appends to `rulings.jsonl`. `mine.py --rulings` reports acceptance, demotion and not-reproduced rates per area and model.

   Tests: a fixture with 3 rulings reports one of each kind; a ruling for an unknown round is refused; `rv-*` re-reviews are no longer filed as fixes.
3. **Debt register.** `scripts/debt.py add|list|close|for-files <paths>` keeps `docs/tech-debt.md` in a repository. `brief.py` appends the rows for the files a brief names.

   Tests: rows round-trip; `for-files` finds rows by path; a row older than 3 runs is listed for re-grading; AMC's 5 known-gap blocks import as rows (dry run).
4. **Calibration sample.** `scripts/sample.py findings.csv --n 40 --strata` writes a blind grading sheet. `kappa.py` scores two sheets.

   Tests: a known pair of sheets gives the known kappa, and the strata counts hold.
5. **Risk depth.** `review.sh` reads the risk areas `route.py` matched and inserts their checklist blocks from the menu.

   Tests: a diff touching `src/host/sessions.ts` gets the turn-and-state block and max effort, and a docs-only diff gets neither.

Case against: the rubric's main lever is the L3 "contrived" band, and I set it from the owner's past rulings and my own single grading. If a second grader disagrees on L2 against L3 (kappa under 0.6), or a demoted finding later hits the owner's data, the band is too wide. The savings shown here (6.0% of fix spend) would not justify the risk. The test that would show it: a demoted row reopened by a real defect report within the next two runs.

## Appendix: sources not read

These pages failed through `tvly extract`. None was read another way.

- The Claude Code review plugin command (`raw.githubusercontent.com/anthropics/claude-code/main/plugins/code-review/commands/code-review.md`): failed.
- Claude Code Review's customise and read-findings pages: 404.
- Codex's `review_prompt.md`: 404. Its rubric template was read instead.
- Microsoft's privacy bug bar: failed.
- Qodo's review-effort page: 404.
