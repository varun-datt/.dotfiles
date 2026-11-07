# Why a Major got in: grading and recording the cause

Spike for the orchestrator-workers skill, 2026-11-06. Questions (owner, 2026-11-06): for each Major or Blocker, the review should also say "why that class or type of issue happened, what was missing in the implementation that caused it to happen in the first place", saved in the notes next to the problem; and should "the criteria for major vs. minor / non-blocking" be researched first. Each claim is VERIFIED (read through `tvly extract`, or read at path:line), INFERRED or OPEN.

## In short

- **Most of this was researched already, and nothing pointed to it.** Grading: [2026-10-30-review-severity.md](2026-10-30-review-severity.md). Why builds miss things: [2026-10-30-build-quality.md](2026-10-30-build-quality.md). The findings record: [2026-11-02-review-focus-learning.md](2026-11-02-review-focus-learning.md). The skill's [rubric](../dotfiles/dot_agents/skills/orchestrator-workers/references/rubric.md), [review prompt](../dotfiles/dot_agents/skills/orchestrator-workers/assets/review.md) and [fix prompt](../dotfiles/dot_agents/skills/orchestrator-workers/assets/fix.md) link to none of them (VERIFIED, `grep -c research` gives 0 in each); `references/routing.md` does link its research notes.
- **Major vs Minor needs no new research.** The rubric is likelihood times impact, after OWASP, with the owner's 2026-11-02 scope rulings. One point is for the owner to discuss, not to research: in check tools, a missing test the brief names is Major, which is how today's rare-case test became a Major.
- **What is missing is where a problem got in.** Each finding already carries a kind (its class) and one cause word (ORDER, ADJ, SPEC, ...), derived on 2026-10-30 because no published list fits agent builds. No finding records which step let it in or what that step lacked. The PSP's defect log records exactly that: the phase a defect was injected in and the phase it was found in.

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

## What was not done

- Not read: IEEE 1044 (paywalled); CMMI's causal analysis and defect escape analysis were not re-read; the PSP's defect type standard table was not reached in the extract.
- Web reads, all through `tvly`: one search and two extracts.

Case against: three more fields per Major is more for a reviewer to fill, and on 2026-10-30 two graders from different model families agreed on the cause word for 33 of 40 findings (Cohen's kappa 0.80, [build-quality.md](2026-10-30-build-quality.md) line 47); a phase may agree less, since the reviewer cannot see the plan. Falsified if the fields, filled for the next 10 Majors, do not repeat in a way that points to a change.
