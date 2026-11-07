# Why a Major got in: grading and recording the cause

Spike for the orchestrator-workers skill, 2026-11-06. Questions (owner, 2026-11-06): for each Major or Blocker, the review should also say "why that class or type of issue happened, what was missing in the implementation that caused it to happen in the first place", saved in the notes next to the problem; and should "the criteria for major vs. minor / non-blocking" be researched first. Each claim is VERIFIED (read through `tvly extract`, or read at path:line), INFERRED or OPEN.

## In short

- **Most of this was researched already, and nothing pointed to it.** Grading: [2026-10-30-review-severity.md](2026-10-30-review-severity.md). Why builds miss things: [2026-10-30-build-quality.md](2026-10-30-build-quality.md). The findings record: [2026-11-02-review-focus-learning.md](2026-11-02-review-focus-learning.md). The skill's [rubric](../dotfiles/dot_agents/skills/orchestrator-workers/references/rubric.md), [review prompt](../dotfiles/dot_agents/skills/orchestrator-workers/assets/review.md) and [fix prompt](../dotfiles/dot_agents/skills/orchestrator-workers/assets/fix.md) link to none of them (VERIFIED, `grep -c research` gives 0 in each); `references/routing.md` does link its research notes.
- **Major vs Minor needs no new research.** The rubric is likelihood times impact, after OWASP, with the owner's 2026-11-02 scope rulings. One point is for the owner to discuss, not to research: in check tools, a missing test the brief names is Major, which is how today's rare-case test became a Major.
- **What is missing is where a problem got in.** Each finding already carries a kind (its class) and one cause word (ORDER, ADJ, SPEC, ...), derived on 2026-10-30 because no published list fits agent builds. No finding records which step let it in or what that step lacked. The PSP's defect log records exactly that: the phase a defect was injected in and the phase it was found in.
- **To find the cause without guessing, the reviewer needs three things it lacks.** It needs the base commit and the list of build and fix commits, so it can tell where a line came from. It needs the field definitions and a fixed order of checks. And it needs a rule that every field cites evidence or says "unknown". A script can propose ODC's Age (Base, New, Rewritten, ReFixed) from `git blame`; the reviewer confirms it, and I add what only the planning chat shows.

## Major vs Minor

- VERIFIED, what exists: [rubric.md](../dotfiles/dot_agents/skills/orchestrator-workers/references/rubric.md) grades likelihood in normal use (L1 to L3) against impact (I1 harm to I4 cosmetic); Blocker and Major block, Minor goes to the tech-debt list as one line. It was built from the 2026-10-30 note's reuse check: OWASP's likelihood times impact, Mozilla's and Microsoft's lowering for uncommon steps, Google's review standard, Conventional Comments' blocking and non-blocking labels ([review-severity.md](2026-10-30-review-severity.md), "Reuse check").
- VERIFIED, owner rulings in it: the scope rule (2026-11-02): in product code a finding blocks only with an effect the owner sees; in check tools an unmet requirement or a missing or weak test stays Major.
- OPEN, not read: IEEE 1044 (paywalled, as on 2026-10-30).
- For discussion: the owner said minor and non-blocking problems are not a concern. The rubric already keeps them out of the way. Where it may grade higher than the owner wants is the check-tool rule: on 2026-11-06 a missing test for a rare case (both rounds spending nothing) was graded Major because the brief named it, though the behaviour was right.

## Where a problem got in

Established names to borrow, rather than inventing ours:

| Source | What it records | Use here |
|---|---|---|
| PSP defect recording log (CMU/SEI-2000-TR-022, section 5.3; VERIFIED, http://www.uml.org.cn/cmm/pdf/00tr0222.pdf, a mirror of the SEI report) | "the defects they inject, the phases in which they injected them, the phases in which they found and fixed them, and how long it took to fix them", with a defect type standard | **phase injected** and **phase removed**, with our own phases |
| PSP's principle (VERIFIED, https://en.wikipedia.org/wiki/Personal_software_process) | "remove defects as close as possible to where and when they were injected"; review checklists built from one's own defect data | the step that should have caught it, and the loop from repeated causes to checklists |
| ODC v5.2 (VERIFIED on 2026-10-30, [build-quality.md](2026-10-30-build-quality.md), "Two classifications") | defect type, and a qualifier: Missing, Incorrect or Extraneous | **qualifier**: what was missing, or wrong, or extra |
| The cause words in [review.md](../dotfiles/dot_agents/skills/orchestrator-workers/assets/review.md) | one word for the kind of gap, derived from 264 findings on 2026-10-30 | kept as they are |

A proposal to discuss (INFERRED, not built): for each Blocker or Major, three more fields next to the cause word.

- **Phase injected:** the plan, the brief (the orchestrator's instructions), the build, a fix round, or pre-existing code.
- **Phase that should have removed it:** the brief's cases, the builder's case list, a test, the builder's self-check, or the review. PSP's "phase removed" is where it was found; the gap between the two is how far it escaped.
- **Qualifier and what was missing:** ODC's Missing, Incorrect or Extraneous, and a few words.

The reviewer sees the brief, the diff and the worker's report, so it can name the brief or the build, but not the planning chat; the orchestrator adds the plan's part when ruling. The fields go in the findings record (each SARIF result's `properties`, where `cause` and `class` already sit) and into the tech-debt row when the problem is not fixed. A phase and cause that repeat become a proposed change to the method, as the owner's rule on patterns already says.

Worked example, 2026-11-06 (run amc-2026-11-02-p1, item mf): phase injected: the brief, where one sentence packed two conditions into one test case; should have been removed by: the fix round's mapping of brief cases to tests; qualifier: Missing (a test); cause word: SPEC.

## What the reviewer needs to find the cause, not guess

Owner, 2026-11-06, on the proposal above: "ensure the reviewer is not just guessing, but it has the right knowledge, frameworks, tools or anything else you can think that's need to narrow down the root cause - if that's not available research it".

What the evidence says:

- VERIFIED, an LLM finds causes from evidence when given a taxonomy, tools and a ledger. AgentRCA (https://arxiv.org/html/2607.22385v1, industrial systems, not code) gives the agent "a natural-language taxonomy of potential faults" in its prompt and a suite of diagnostic tools, and makes it keep a hypothesis table that "requires the agent to track supporting and contradicting evidence before producing a final answer". Its ablations: "diagnostic performance depends strongly on the available tools: when operating-condition matching or directional statistical evidence is removed, accuracy drops sharply". INFERRED: the same three parts carry over to a reviewer, which has the taxonomy (the cause words) but no tool for where a line came from and no ledger.
- VERIFIED, ODC already has a field for where a defect sits in the code's history. ODC v5.2's Age (section 4.2.4, the PDF above): Base ("not injected by the current project, and was therefore a latent defect"), New, Rewritten ("introduced as a direct result of redesign and/or rewrite of old function"), ReFixed ("introduced by the solution provided to fix a previous defect"). ODC is meant to be fitted to a local process "by defining the Activities during a development process and their mapping to the ODC Triggers". So Age comes before the PSP phase: Age says which change put the line in, the phase says which step of that change lacked what.
- VERIFIED on 2026-11-02, `git blame` is a proposal, not an answer. Blame-based linking of a fix to the change that introduced it had "recall and precision between 0.40 and 0.60" on the Linux kernel ([review-focus-learning.md](2026-11-02-review-focus-learning.md) line 86).
- VERIFIED, a failing case can be narrowed by its nearest passing case. Causal Testing (Johnson, Brun and Meliou, ICSE 2020, https://people.cs.umass.edu/~brun/pubs/pubs/Johnson20icse.pdf) builds minimally different passing tests next to a failing one; it could try 71% of the real defects it could classify and helped with 77% of those. INFERRED: for a reviewer, this is a probe that shows the defect and its smallest passing neighbour.
- VERIFIED, from search excerpts only: the fishbone (Ishikawa) diagram sorts causes into fixed categories such as people, methods, materials and environment. INFERRED: the "Where the causes sit" homes in [build-quality.md](2026-10-30-build-quality.md) (worker process, brief and orchestrator, codebase, tooling, model, review) are this repository's categories.

What the reviewer has today (VERIFIED, [review.md](../dotfiles/dot_agents/skills/orchestrator-workers/assets/review.md)): the brief, the diff, the builder's report with its impact map and case table, the worktree read-only, the gates run, earlier rulings, and the cause words. It lacks: the base commit and which commits are build or fix (blame cannot tell Base from New without them); the Age, phase and qualifier definitions; a rule that each field cites its evidence or says "unknown"; and the plan and owner rulings behind the brief.

Proposal (INFERRED, not built), for each Blocker or Major:

1. **Age, proposed by a script.** `findings.py` already stores each finding's file and line. A script runs `git blame` on that line against the base commit and the branch's commit list, and proposes Base, New, Rewritten or ReFixed with the commit. Structure first: a script proposes the same way each time; the reviewer confirms by reading the commit, or overrides it with evidence.
2. **Phase injected and phase that should have removed it, by the reviewer, through a fixed order of checks, each quoted:** Does the brief name the case? (quote the line, or "not named") Does the builder's case table list it? Is there a test for it? Did the builder's report claim it? The first check that fails is the phase. If the brief is silent and the case follows from what the brief does name, the phase is still the brief, with cause SPEC.
3. **Qualifier** (ODC: Missing, Incorrect, Extraneous) and a few words on what was missing.
4. **Evidence or "unknown"** for every field. When two phases fit, list both with the evidence for and against, as AgentRCA's hypothesis table does.
5. **The orchestrator adds the plan's part when ruling:** the planning chat and owner rulings the reviewer cannot see, with a quote, or confirms the reviewer's fields.

The review prompt is given the base commit, the commit list labelled build or fix, the field definitions, and the order of checks.

## What was not done

- Not read: IEEE 1044 (paywalled); CMMI's causal analysis and defect escape analysis were not re-read; the PSP's defect type standard table was not reached in the extract.
- Not found through `tvly`: Card's "Learning from our mistakes with defect causal analysis" (IEEE Software, 1998) and Kalinowski's work on defect causal analysis; the searches returned other pages. 5 Whys was not read; it is widely known and not cited here.
- Not tested: whether a reviewer fills these fields consistently. That needs the fields filled on real Majors and checked against the orchestrator's own reading.
- Web reads, all through `tvly`: seven searches and four extracts across both parts.

Case against: the fields add work to every Major, and a reviewer may fill them by habit rather than evidence. On 2026-10-30 two graders from different model families agreed on the cause word for 33 of 40 findings (Cohen's kappa 0.80, [build-quality.md](2026-10-30-build-quality.md) line 47); a phase may agree less, since the reviewer cannot see the plan, and blame is right only about half the time. AgentRCA's evidence comes from industrial sensors, not code review, so its gains may not carry over. Falsified if, on the next 10 Majors, the orchestrator's check disagrees with the reviewer's phase on more than a few, or the fields do not repeat in a way that points to a change.
