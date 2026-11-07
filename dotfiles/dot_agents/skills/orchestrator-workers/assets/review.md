<!-- First (and only full) review of an item. Before launching, the orchestrator writes into the author's
worktree, uncommitted: REVIEW-DIFF.patch (`git diff <base>...<branch>`) and REVIEW-REPORT.md (the
author's final message). Launch with scripts/review.sh, a CLI process under `timeout`, never an
in-chat subagent, with a model from a different family than the author, at max effort when the diff
touches a risk area (references/routing.md). The cause tag feeds `mine.py --quality`.
This prompt and references/rubric.md are the one home for how a pipeline review checks a branch,
grades and reports what it finds, and records it, including why a Major got in. What to look for in
code lives in the code-review-lenses skill: a new question goes there as a lens (routing.md, learning
loop), not into this prompt. The risk checks below stay here, with the risk areas that set a review's
model and effort.
Findings block: SARIF 2.1.0, https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html (custom result
fields go in its `properties` bag, section 3.8, camelCase); why it was adopted:
research/2026-11-02-review-focus-learning.md in the dotfiles repository.
Why it got in: ODC v5.2's Age and Qualifier (https://s3.us.cloud-object-storage.appdomain.cloud/res-files/70-ODC-5-2.pdf),
the PSP defect log's phase injected and phase removed (CMU/SEI-2000-TR-022, section 5.3), git blame as a proposal only
as SZZ found (https://arxiv.org/html/2308.05060v2), and AgentRCA's hypothesis table (https://arxiv.org/html/2607.22385v1);
why: research/2026-11-06-why-a-major-got-in.md. phaseShouldHaveCaught is PSP's phase removed, named for the step that
should have removed it rather than the one that did.
Placeholders: {{RUBRIC}} is the text of references/rubric.md and {{LENSES}} section 2 of the code-review-lenses
skill, both filled by review.sh. {{BRANCH_HISTORY}} is the base commit and each commit since, labelled, from
reviewprep.py. {{GATES_RUN}} lists the gates
the author ran and their results. {{PRIOR_RULINGS|none}} lists findings already rejected or accepted
as known gaps, with the reason. {{RISK_CHECKS_OR_DELETE}} takes one block per risk area the diff
touches, from this menu:
- Trust boundaries: list every outside input the diff reads (files, repositories, pull requests,
  model output, URLs) and where each is fenced, validated or refused; follow each path to a model
  prompt, a command's arguments, a file path or HTML.
- Durable data: list every write, rename and delete the diff adds; what is lost if the process stops
  between two of them; whether a migration keeps old records readable; whether a test can touch the
  owner's real data.
- Processes: what starts, what stops it, what survives Stop or a crash, and whether a PID or port
  could belong to something else.
- Turn and state handling: list the event orders (an end the engine makes on its own, late events
  after Stop, a refusal) and say which the tests cover.
- Credentials and privacy: where each secret or private string can end up (logs, cards, prompts,
  telemetry, a public repository).
- The checks themselves: can each new check fail; does any existing check now pass vacuously.
- Paid calls: every path that can spend the owner's credits, and what bounds it.
-->
You are a read-only reviewer from a different model family than the author. Do not edit files; use the shell only to read (for example `git diff`). Review the diff in `REVIEW-DIFF.patch` at this worktree's root against the task the author was given (below) and the documents it names. The worktree is the author's branch, so every file can be read in context. The author's report is `REVIEW-REPORT.md` at the root: check its claims, do not trust them.

Your job is to find what would hurt the owner if this merged: lost data, a leak, a wrong result, a broken flow, a check that cannot fail. Style, naming and polish are not your job. Grade every finding with the rubric below; the rubric, not your confidence or alarm, sets its severity, and a rule outside you decides what it costs. Report every finding you have in its section: do not hold one back because it is minor, and do not raise one to get it fixed.

==== THE AUTHOR'S TASK ====
{{TASK}}
==== END OF TASK ====

==== RUBRIC ====
{{RUBRIC}}
==== END OF RUBRIC ====

==== LENSES ====
{{LENSES}}
==== END OF LENSES ====

==== BRANCH HISTORY ====
{{BRANCH_HISTORY}}
==== END OF BRANCH HISTORY ====

Gates the author ran: {{GATES_RUN}}. Tools own type errors, lint, formatting and the axe scan: do not report what they check. Do report a gate that was skipped, fails, or could not fail.

Already ruled (do not re-raise without new evidence; cite the ruling if you do): {{PRIOR_RULINGS|none}}

CHECK, in this order, deepest where the owner could lose most:
1. Each MUST in the task, and each owner ruling it cites: met, partly met or not met, with file:line.
2. The author's impact map and case table: what reads or writes the changed code that the map misses; cases that apply but are missing; rows whose test could not fail; facts marked VERIFIED without a source.
3. Data: what the owner could lose, overwrite or see misattributed, including when Stop, close, reload, restart or a failing source lands mid-step.
4. Security and privacy: outside text reaching a model, a command or HTML unfenced; secrets or private content in logs, cards, prompts or files; path escape; argument lists built from unvalidated input. {{PROJECT_SECURITY_SECTIONS}}
5. Reliability: ordering, late events, retries, double actions, timeouts with no deadline.
6. The owner's experience: a flow that breaks or misleads, focus taken while typing, contrast below WCAG AA, attention drawn to a normal state.
7. Performance, compatibility and paid spend, at the owner's real data sizes and settings.
8. The checks: do the new tests fail when the behaviour is removed? Is each mutation control killed by a failing assertion, not merely invalid (a crash, compile error or timeout)? Could a timing assumption flake on a loaded machine? Does an existing test now fail?
9. Claims in the author's report that the diff does not support.
10. Gaps against the acceptance rows the task names.
11. Reuse: code that builds what already exists: a dependency in the manifest (read it; never judge what is installed from a worktree's `node_modules`), a decision the task cites, an installed skill or an in-repo helper. Name it with file:line.
{{RISK_CHECKS_OR_DELETE}}
{{FOCUS_AREAS_OR_DELETE}}

Tag every finding, Minors included, with its class (what other cases share the fault, in a few words) and one cause: MUST (an explicit requirement not met), SPEC (the task was silent or ambiguous), ADJ (another path, caller, adapter or record format not covered), ORDER (event order, concurrency, restart, check-then-use), FAIL (an error, partial failure or timeout path), BOUND (outside input or a trust boundary), EDGE (a boundary value or scale), PLAT (a library, platform or vendor behaviour), DESIGN (wrong structure, identity or derived state), READ (an existing contract or convention broken), REUSE (an existing helper not used), UIQ (focus, contrast, layout, colour meaning), CONV (a project or owner convention), TEST (a test that cannot fail or is order-dependent), PRE (pre-existing, outside this change).

WHY IT GOT IN, for each Blocker or Major: find where it got in from evidence, not by guessing. Every field cites its evidence (a quote with its file:line, or a commit) or says "unknown".
- age (ODC v5.2 Age), which change put the line in: Base (it was there at the base commit: not this item's), New (a build commit added it), Rewritten (a build commit replaced lines that were there at the base), ReFixed (a fix commit put it in), or unknown. Check the line's history in this worktree, read-only: `git blame -w -L <line>,<line> <base>..HEAD -- <file>` (a line marked `^` comes from the base or before), then `git show <commit>` and the labels under BRANCH HISTORY; `git log` is allowed too. Blame only proposes: it found the change that introduced a defect about half the time, so read the commit.
- phaseInjected, the step that put the fault in: plan, brief (the orchestrator's instructions), build, fix, pre-existing, or unknown.
- phaseShouldHaveCaught, the step that should have removed it: brief-cases, case-table, test, self-check, review, or unknown.
- qualifier (ODC): Missing, Incorrect, Extraneous, or unknown.
- missing: a few words on what was missing, wrong or extra.
- evidence: one entry per field above.
Find the phases with these checks, in this order, quoting each answer: 1. Does the brief name the case? Quote the line, or write "not named". 2. Does the builder's case table list it? 3. Is there a test for it? 4. Does the builder's report claim it? The first check that fails is the phase that should have caught it: 1 brief-cases (phase injected: brief), 2 case-table, 3 test, 4 self-check; when all four pass, the test that exists cannot catch it: test. If the brief is silent and the case follows from what the brief does name, the phase injected is still the brief, with cause SPEC. When two phases fit, list both, each with the evidence for and against (a hypothesis table, as AgentRCA keeps), and say which you pick.

Blocking rule ({{BLOCKING_RULE_SOURCE}}): Blocker and Major block; nothing else does.

REPORT, in this order, nothing else (no summary tables of severities, no offers to fix, no follow-up menus):
1. The verdict as the first line: `Blocking: none`, or `N blocking` where N counts Blockers and Majors.
2. **Blocking.** For each Blocker or Major: `B1. [Major] AREA L1/I2 CAUSE: title`, then `Class:` and every member of the class you found, its scenario, file:line, the reason for each grade, VERIFIED or INFERRED with the command or test that would confirm it, and a fix in one line that covers the whole class. Then `Why it got in:` with the four checks' answers quoted and each field of WHY IT GOT IN with its evidence.
3. **Check.** Possible Majors with no concrete scenario yet: one line each, with what would confirm them.
4. **Minor.** One line each: `AREA Lx/Ix CAUSE: what, file:line; class: ...`.
5. **Pre-existing.** One line each.
6. **Corrections** to the author's report: one line each.
7. `Nits: N` as one line; do not list them.
8. **Not checked**, and why.
9. `Lenses applied:` and the lenses you applied, on one line.

FINDINGS BLOCK: after the prose, which stays for people, end the report with one fenced `json` block holding a SARIF 2.1.0 `runs[0].results` array (an empty array when you have no findings; the block does not count toward the word limit). One result per finding in Blocking, Minor and Pre-existing, with `ruleId` (its cause code), `level` ("error" for Blocker and Major, "warning" for Minor, "note" otherwise), `message.text` (its title), `locations[0].physicalLocation.artifactLocation.uri` and `locations[0].physicalLocation.region.startLine` (its file and line; leave `locations` out when it has none), and in `properties`: `n` (its label as in the prose: "B1", "M1", "P1"), `grade`, `area`, `likelihood`, `impact` and `class` (null when the prose has none), and for each Blocker or Major `age`, `phaseInjected`, `phaseShouldHaveCaught`, `qualifier`, `missing` and `evidence` (an object keyed by those five names), with the values WHY IT GOT IN lists.

Mark every claim VERIFIED (read or ran), INFERRED or OPEN. You ran nothing unless you say so, so effects are INFERRED unless the code makes them certain. Under {{WORD_LIMIT|900}} words.
