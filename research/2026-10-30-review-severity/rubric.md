# Review severity rubric

One page for a review prompt to include. It grades a finding by **how likely it is in the owner's use** and **what it does when it happens**. A review exists to stop changes that would hurt the owner and to correct the record; style, naming and polish belong to tools and the tech-debt list.

## 1. Was it introduced by this change?

No: it is **Pre-existing**. It never blocks. Say it in one line; if it would be Major, the orchestrator adds it to the tech-debt list.

## 2. Likelihood

- **L1 Normal use.** Happens with the owner's data, settings and normal flow: the first try, default settings, real data sizes. Text from outside systems (repositories, pull requests, web pages, model output) is untrusted in normal use, so a path that lets it steer a model or a command is L1.
- **L2 Plausible.** A normal action at an unlucky moment: Stop, close, reload or a double click mid-request; a slow or failing source; a restart or upgrade; a second window; keyboard-only or screen-reader use.
- **L3 Contrived.** Needs a local attacker racing the file system, a hostile file name the owner would not create, a timing window no normal action opens, an explicit unusual override, or a data shape the owner does not have.

## 3. Impact

- **I1 Harm.** The owner's data or typed text is lost or corrupted; a secret or private content goes where it should not (a model, another person, a public repository); an approval, confinement or sandbox is bypassed; an action runs without the owner's approval.
- **I2 Wrong.** A wrong result is shown or recorded; a MUST in the brief or an owner ruling is unmet; a flow cannot be completed; paid spend can pass an approved limit; a check cannot fail, or fails on unchanged code.
- **I3 Degraded.** Slow, confusing or misleading but workable; an accessibility barrier with a workaround; sensitive text in a local-only log.
- **I4 Cosmetic**, or negligible at the owner's scale.

## 4. Severity

| | L1 normal | L2 plausible | L3 contrived |
|---|---|---|---|
| **I1 harm** | Blocker | Blocker | Minor, tagged SEC or DATA for the owner |
| **I2 wrong** | Major | Major | Minor |
| **I3 degraded** | Major | Minor | Minor |
| **I4 cosmetic** | Minor | Nit | Nit |

Where the matrix gives way:

- **Tests.** A missing or weak test is Minor, unless the brief names that test or the change is to the checks themselves (harness, gate script, mutation control): then Major. An existing test that now fails, or flakes on a loaded machine, is Major.
- **Nit.** Style, naming, wording, comments and preference are Nits whatever the matrix says.
- **Correction.** The author's report claims something the diff does not do. It does not block; the orchestrator corrects the record. If the unmet claim is a MUST, report the MUST as its own Major.
- **Already ruled.** Do not re-raise a finding the orchestrator or owner rejected, unless you have new evidence; cite the ruling.

## 5. What each level does

| Level | Merge | Where it goes |
|---|---|---|
| Blocker, Major | Blocks: one fix round | Fix brief; re-review checks the fix |
| Minor | Does not block | One line on the repository's tech-debt list |
| Nit | Does not block | Counted in one line, never listed |
| Pre-existing | Does not block | Tech-debt list if it would be Major, else dropped |
| Correction | Does not block | The orchestrator fixes the record |

## 6. Evidence a Blocker or Major must carry

1. **A failure scenario:** "When <action or data>, <code> does <wrong thing>, so <what the owner sees or loses>."
2. **Where:** file:line.
3. **Grade:** likelihood and impact, each with a reason of a few words.
4. **Evidence level:** VERIFIED (ran it, or the code makes it certain) or INFERRED (read, not run), with the one command or test that would confirm it.

A finding with no concrete scenario is not Major: list it under **Check** for the orchestrator. An INFERRED Blocker blocks until disproved. An INFERRED Major blocks, but the fix round's first step is to reproduce it with a failing test; if that fails, the fixer changes no code and the finding goes to the tech-debt list marked "not reproduced".

## 7. Areas (what "major" means in each)

| Code | Area | Major when |
|---|---|---|
| COR | Correctness against the brief | A MUST or owner ruling is unmet, or a normal input gives a wrong result |
| DATA | Data integrity, loss, migration | Owner data or typed text can be lost, corrupted, overwritten or misattributed |
| SEC | Security and privacy | Outside text can steer a model or command; secrets or private content leak; an approval or confinement is bypassed |
| PERF | Performance and resources | Normal data makes a flow hang or slow visibly, or a stated budget (start-up, size) is exceeded |
| REL | Reliability, ordering, failure handling | Stop, restart, a failing source or a late event leaves wrong state or runs an action twice |
| UX | User experience and accessibility | A flow breaks, misleads, steals focus, fails WCAG AA, or calls attention to a normal state |
| COMP | Compatibility and operability | Start-up, upgrade, install or a supported platform fails, or owner settings are dropped |
| COST | Paid spend | Paid calls can pass an approved budget or repeat without the owner asking |
| VERIF | The checks | A check cannot fail, an existing test breaks or flakes, or a test the brief names is missing |
| MAINT | Maintainability | Only when it blocks the next planned change |
| REPORT | The author's report | Never Major: a Correction |
