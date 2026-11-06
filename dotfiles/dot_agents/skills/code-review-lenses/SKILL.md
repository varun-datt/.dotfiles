---
name: code-review-lenses
description: "Review code for where defects actually hid, not for style. A short set of lenses - remote-contract assumptions, failure channel, test doubles that cannot see the bug, unpinned boundaries, identifiers leaking through side channels, absent-versus-empty-versus-zero, coincidental config agreement, dependency truth, which files a search sees - each taken from a real defect. Use when reviewing a PR or a service for correctness, when scoping a review so it stays bounded, when choosing which lenses are worth a separate pass, or when a green suite under review might not be able to fail (the software-testing skill's mutation checks prove it). Not for style or coding standards, and not for diagnosing a reported failure (diagnosing-bugs)."
---

# Code-review lenses

A lens is one question asked of every file in scope. Asking one at a time finds more than a
general read: each example below survived at least one general review.

Style, naming and formatting are out of scope. Evidence rules — N files read for a claim about
N, re-derive an absence, provenance tags — are in the repository's own `AGENTS.md`, where it has
them, and are not repeated.

## 1. Scope the review before starting

1. List the surfaces: each service, library, and **each remote call by endpoint**, caller and
   callee. A call has two sides; a review that reads only the client has read half.
2. A lens gets its own pass only if it carries a **mechanical check** (a grep, a script, a tool
   run — never "review carefully"), a rough **cost**, and **one real defect it would have caught**
   that the review already done missed. If no lens clears that, stop: the review is done.
   Also skip a lens whose question an open work item already owns.
3. Before raising anything, search earlier findings and rulings for it. §3 has the example.

## 2. The lenses

| Lens                          | Ask                                                                                                                                                                                         | Where it was real                                                                                                                                                                                                                                                                                    |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Object lifetime**           | What is registered once but holds per-call data?                                                                                                                                            | A scoring class registered as one shared instance kept per-call state. A line-by-line read against the old code missed it, however carefully applied. Check every registration's lifetime against the type's mutable fields                                                                           |
| **Remote contract**           | What does this code assume about the other service — page size, filter edges (`<` or `<=`), sort and tie order, merge semantics, not-found, status codes — and does the **server** do that? | A lookup asked for a page of two and assumed it held this record and its predecessor; the server ignored the page size and returned every earlier record. Separately, a documented 409 had no throw site. A generated client shows what is sent, never what the server does                          |
| **Failure channel**           | Does each failure reach the caller as the right kind: retry, permanent, or a gap in the output? Does it stay the size of the unit that failed, or does one handler around a loop over independent units (sources, items, files) throw away the ones that succeeded? | A custom exception derived from `Exception`, missed a filtered `catch`, and read as a transport failure — so the caller retried a permanent input problem three times, then re-queued the whole unit of work. Separately, one `try` around a loop over skill libraries turned one library's HTTP 403 into "no results" for all, hiding a required upgrade another library had found; every fixture had one library, so no test could see it |
| **Test doubles**              | Does the fake do what the real service does with each parameter - apply what it applies, ignore what it ignores? Could any test fail if the real service behaved differently?               | A fake was made to apply a page size so a page-of-two defect became visible. The real server ignores the page size, so the change made the fake less faithful and the tests pinned behaviour the server does not have. Read the server's code before making a fake "more faithful"                   |
| **Boundary pinning**          | Would a test notice `>` becoming `>=`? Can a value derived from an input (a parent's parent, an offset, a joined `..`) leave the range the next call assumes?                                | A library at 98% line coverage whose decision logic scored 65% under mutation testing: 25 surviving changes, nearly all at decision edges. Coverage says a line ran, not that its result was checked. It finds edges no test pins, not defects, so it fails the §1 bar unless the stakes justify it. Separately, a scan started two folders above a matched file; for a file at the repository root that is outside the repository, and `relative_to(root)` raised. Fixtures put every file at least two folders deep |
| **Side-channel disclosure**   | Can a personal identifier or restricted value leave through an exception message, URL, header, status detail or stored step message rather than a log field?                                | A customer identifier was taken out of log fields as a precaution, but stayed interpolated in exception messages that the outer handler logs as a field. The owner then accepted it: check whether the value is actually restricted before calling a leak a defect                                   |
| **Absent, empty, zero**       | Are "not there", "empty" and "zero" each handled, and kept distinct across every hop to storage?                                                                                            | A stored score of 0 meant "computed, unavailable" and NULL meant "does not apply"; the new path wrote 0 for both, and a downstream client's non-nullable `int` blocked the fix until its contract changed                                                                                            |
| **Coincidental agreement**    | Do two values match only because nobody set an override?                                                                                                                                    | Two chart objects selected pods through a helper that differs from the pods' own labels only when `fullnameOverride` is set. One was a security policy: with the override set it matches nothing, applies to nothing, and fails **open**                                                             |
| **Dependency truth**          | Does the resolved version exist upstream, and is it what CI will get?                                                                                                                       | A local feed held a version never published; everything resolved and built. The real package later raised a transitive floor that the local stand-in did not, and the first clean restore failed                                                                                                     |
| **File set**                  | Which files does a search see: the repository's, or everything in the folder? Is that decided once, or in each search?                                                                      | Two searches in an agent-file checker walked the whole folder without the others' skip list: runs failed on a prompt file in `.git` and an ignored local note, and warned on `SKILL.md` files in an ignored `.venv`. Now one list, `git ls-files --cached --others --exclude-standard`, feeds all    |
| **Telemetry contract**        | Is a log field's name or type something an index or dashboard depends on?                                                                                                                   | An index mapping switched field discovery off and listed 32 fields; none of the 9 a dashboard filtered on was among them, so they were stored but unsearchable and every panel went blank with no error                                                                                              |
| **Parity versus improvement** | Is this change meant to reproduce old behaviour or improve it?                                                                                                                              | A real fix to an unbounded scan was deferred, so it would not ride in on a change whose job was to match the old system                                                                                                                                                                              |

Also considered, and not given their own pass in the first scope they were tried on: per-call
cost (perf runs already measure it), time kinds (a project-wide rule already governed it),
deferred or commented-out logic (zero markers in scope), requirement traceability (a marker
convention covers it). They stay on the list; the §1 test decides per scope.

## 3. Habits that saved a wrong finding

- **Check earlier rulings first.** A correlation header sent as null on every outbound call looked
  like broken correlation. An earlier review had already shown the server reads it from the
  incoming call. Raising it again would have cost a round with the owner.
- **Size a finding with a count and a control, never with text.** When the lens is disclosure,
  count matches — do not print them — and run a positive control in the same query (a field every
  line has) so a zero means absence, not a broken match.
- **A finding against a green suite needs a negative control.** Restore the old code or the old
  fake and show the new test fails; otherwise "the test passes" is also true of a test that
  cannot fail. [Mutation checks](../software-testing/references/mutation-checks.md) do this
  without editing the code.
- **State what the fix binds.** A new header, name or file layout that nothing else uses yet is a
  precedent, and needs a ruling rather than a pick.
