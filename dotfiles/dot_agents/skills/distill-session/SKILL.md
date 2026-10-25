---
name: distill-session
description: Distills a finished or paused agent session into lasting records. Workspace knowledge goes into the repository's own homes (or a standard layout it creates), personal and generic knowledge goes to the user's wiki inbox, each item verified first; then it reports what it kept and dropped. Use when the user asks to distill, wrap up, archive or hand off a session, or to save what a session learned.
---

# Distill the session

Turn what this session learned into records someone will use later, then report. Most sessions yield a few lines; some yield none. Where the workspace's own instructions differ from these steps, follow the workspace.

Copy this checklist into your reply and tick it as you go:

```text
- [ ] 1 homes found   - [ ] 2 candidates gathered   - [ ] 3 each sorted
- [ ] 4 verified and written   - [ ] 5 personal items captured   - [ ] 6 finished   - [ ] 7 reported
```

## 1. Find the homes

Take the first that applies, per kind of record:

1. **This repository's declared homes.** Read `AGENTS.md` (its `Layout:` line first; also `CLAUDE.md`, `.github/copilot-instructions.md`) and the README for where decisions, the plan or backlog, gotchas, reference and handoff notes go. Use them even when they differ from the standard layout; never open a second home for the same kind.
2. **The parent knowledge repository.** If this repository sits inside another git working tree (`git -C .. rev-parse --show-toplevel`) whose `AGENTS.md` says `Layout: knowledge (PARA)` or whose root has `10-projects/` and `20-areas/`, write workspace items there, in the area or project for this repository.
3. **The standard layout.** For a standalone repository, create only the folders this run needs, as described in [references/layout.md](references/layout.md), and link each from `AGENTS.md`.

## 2. Gather candidates

1. Look at this session only: its messages, tool results, the files it changed and its commits.
2. Ask the review questions: what did we expect, what happened, why (ask twice), what will we do next time. Include what went well.
3. Keep what a future session would otherwise get wrong: corrections the user made, mistakes made twice, facts the code does not show (decisions and their reasons, where outside information lives, tool traps), and open work with what releases it.
4. Drop what the code, git history or existing instructions already say, the story of the session, and anything the session showed to be wrong. Drop a lesson that only states a fix without the expectation that failed.
5. Check the session's own claims and outputs for errors; report only the major ones.

## 3. Sort each candidate

Give it a **kind**: `fact`, `rule` (always or never), `procedure` (multi-step how-to), `event` (a decision, incident or change, with its date; an incident that meets a postmortem trigger in [references/layout.md](references/layout.md) is offered the postmortem template), or `lesson` (expected, got, why, next time).

Give it a **destination**:

| Who reads it next | True only in this repository | True everywhere |
| --- | --- | --- |
| An agent | workspace: `AGENTS.md`, skills, instructions | personal agent layer: propose only (step 6) |
| The user | workspace: reference, timeline, handoff | wiki inbox (step 5) |

True only for this session: drop. True for this repository but unsafe to commit there (private, employer or personal content in a shared or public repository): treat as personal. Fits two homes: store it once in the narrower one and link from the other. Team or organisation rules: flag, never write.

## 4. Verify and write workspace items

1. Write each entry as one concrete, checkable line, conclusion first, with its reason and a citation (path and line, commit, command or URL).
2. Before writing, re-open the cited source live (re-run, re-read, re-fetch) and note the commit or time. If it disagrees, write the corrected version.
3. Search the target for the same concept: update the existing entry rather than adding a near-duplicate, and fix or remove any entry this session proved wrong.
4. Facts and events may be written directly. A new or changed `rule`, `procedure` or skill is shown as a diff and waits for the user's yes.
5. Keep an always-loaded file under about 200 lines; move detail into a linked file.
6. After editing a table or heading, re-read it: same cell count in every row, headings intact, nothing duplicated by a partial match.

## 5. Capture personal and generic items

1. Run the redaction and secret checks the user's instructions name on every line first. A line that fails is dropped and reported, never captured.
2. Append each line with the wiki's own command: `make -C ~/sandbox/wiki capture M="<line>"`. One line per item: `[distill <session date and time>] <kind>: <claim> (why: <reason>; source: <repository alias>, <path, commit or URL>) #distilled`.
3. Write the raw line before any rewording, and report the path the command prints. Do not file into wiki notes, and never commit the wiki; its triage files the inbox later.
4. If the wiki is missing, append the same lines to `~/.agents/state/<workspace>/distilled-personal.md` and say so.

## 6. Finish

1. Remove temporary files the session made; ask if you are unsure whether something is temporary.
2. Commit every workspace file you changed, with a message that says what was recorded. Never push.
3. Personal agent rules (true for this user in every repository) are not written: list them in the report as proposed text for the user's personal instructions.
4. You are done when every candidate has a home or an explicit "not worth keeping", and every repository you touched is clean.

## 7. Report

1. What the session did, its result and what it means.
2. What you recorded and where (count per destination), what you dropped and why, and any major errors you found.
3. Proposed personal agent rules, verbatim.
4. Learnings for the user, not for yourself.
5. Any way to improve these instructions, or "none".

## Handoff

When asked for a handoff, distill first, then end the report with a short prompt that starts the next session: the goal, where the records are, the first step, and anything waiting on the user. Put it last, in a fenced `text` block under the heading "Next session". Do not save it as a file.
