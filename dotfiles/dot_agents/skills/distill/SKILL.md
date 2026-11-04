---
name: distill
description: Distills a source into lasting records, with a mode per source - a finished or paused agent session (the default, read from its full log on disk rather than the context window), a research, spike or scratch folder, or a document. Workspace knowledge goes into the repository's own homes (or a standard layout it creates), personal and generic knowledge goes to the user's wiki inbox, each item verified first; then it reports what it kept and dropped. Use when the user asks to distill, wrap up, archive or hand off a session, to save what a session learned, or to distil, mine, close out or clean up a research folder or a document. Replaces distill-session.
---

# Distill

Turn what a source holds into records someone will use later, then report. Most sources yield a few lines; some yield none. Where the workspace's own instructions differ from these steps, follow the workspace.

## Mode

Pick the mode from what the user named; with no argument, distill this session.

| Mode | Source | Read also |
| --- | --- | --- |
| session | this session's full log on disk, not the context window; the files it changed and its commits | [references/session.md](references/session.md) |
| research | a research, spike, probe or scratch folder | [references/research.md](references/research.md) |
| document | one document: a design, a plan, a long note, a report | [references/document.md](references/document.md) |

The steps below hold for every mode; a mode's reference adds to steps 2 and 6.

## Models

Route each kind of work to the cheapest model that does it as well; credits are billed by token, and a long source is mostly input.

| Work | Model | Why |
| --- | --- | --- |
| Reading a chunk and listing candidates | GPT-6.1 Sol | Extraction, not judgement. On 2026-10-30 Sol read a chunk for 23.5 credits that Opus read for 61 on average, and listed the most candidates; the default model refused a chunk on 2026-10-27 and Opus one on 2026-10-30, and Sol read both |
| A chunk its reader refused | The other family (Claude Opus 5.5) | On 2026-10-27 halving a refused chunk did not help and switching family did |
| Checking quotes and coverage | `session_log.py`, no model | Mechanical |
| Judging, writing records, the report (step 3 on) | Claude Opus 5.5 | Judgement against existing records: a miss loses a record, a wrong call adds a duplicate |
| A source of up to two chunks, or one document | This chat, no subagent | A subagent's start (about 50k tokens of instructions) costs more than it saves |

In VS Code, pass the model to the subagent call as `GPT-6.1 Sol (copilot)`; there is no effort setting per call, so each model runs at the effort VS Code is set to for it (on 2026-10-30, Opus high and Sol medium). In Copilot CLI, pass `--model`. Claude Haiku 5.5 and GPT-6 Luna cost about a fortieth of Opus per token (VS Code's `models.json`, 2026-10-30) but are untested here: try one beside Sol on two chunks before routing reading to it.

Copy this checklist into your reply and tick it as you go:

```text
- [ ] 1 homes found   - [ ] 2 every part read   - [ ] 3 each judged and sorted
- [ ] 4 verified and written   - [ ] 5 personal items captured   - [ ] 6 finished   - [ ] 7 reported
```

## 1. Find the homes

Take the first that applies, per kind of record:

1. **This repository's declared homes.** Read `AGENTS.md` (its `Layout:` line first; also `CLAUDE.md`, `.github/copilot-instructions.md`) and the README for where decisions, the plan or backlog, gotchas, reference and handoff notes go. Use them even when they differ from the standard layout; never open a second home for the same kind.
2. **The parent knowledge repository.** If this repository sits inside another git working tree (`git -C .. rev-parse --show-toplevel`) whose `AGENTS.md` says `Layout: knowledge (PARA)` or whose root has `10-projects/` and `20-areas/`, write workspace items there, in the area or project for this repository.
3. **The standard layout.** For a standalone repository, create only the folders this run needs, as described in [references/layout.md](references/layout.md), and link each from `AGENTS.md`.

## 2. Gather candidates from all of it

1. Read all of the source, not only what is in view. For a session that is its full log on disk: after a compaction the context window holds only a summary. [references/session.md](references/session.md) condenses the log into chunks and checks that every chunk was read.
2. Ask the review questions of each part: what did we expect, what happened, why (ask twice), what will we do next time. Include what went well.
3. Write down every candidate: corrections the user made, mistakes made twice, facts the code does not show (decisions and their reasons, where outside information lives, tool traps), open work with what releases it, and what worked. Gather generously; step 3 judges. When subagents read the source, hand each one the list of what is already recorded (the repository's AGENTS.md rules, the personal instructions, the trap tables of the skills the source touched) and ask for only what those do not already say, each with the record it checked. Say which topics the source has already moved elsewhere (such as findings already in a skill) so readers skip them.
4. Check the source's own claims and outputs for errors; report only the major ones.

## 3. Judge, then sort each candidate

Merge candidates that say the same thing. Keep one only if it passes every test below; otherwise drop it with the reason of the first test it fails.

| Test | Drop reason |
| --- | --- |
| Nothing already says it: not the code, git history, instructions or an existing record (search them; fix a record this source proved wrong instead of adding one) | `recorded` |
| Without it, a future session or the user would act wrongly or lose time; what happened, told as a story, does not count | `story` |
| It holds beyond this source, or it is open work with what releases it | `one-off` |
| The source showed it, rather than guessed it, and did not later show it wrong | `unsupported` |
| A lesson states the expectation that failed, not only the fix | `fix-only` |

Expect few: most sources leave a handful of records. When more than about ten pass, apply the tests again, harder, and merge before writing; a long list is the bloat this step exists to stop.

Give each kept candidate a **kind**: `fact`, `rule` (always or never), `procedure` (multi-step how-to), `event` (a decision, incident or outside change, with its date; not a merge, deploy or ticket update, which their own history holds; an incident that meets a postmortem trigger in [references/layout.md](references/layout.md) is offered the postmortem template), or `lesson` (expected, got, why, next time).

Give it a **destination**:

| Who reads it next | True only in this repository | True everywhere |
| --- | --- | --- |
| An agent | workspace: `AGENTS.md`, skills, instructions | personal agent layer: propose only (step 6) |
| The user | workspace: reference, timeline, handoff | wiki inbox (step 5) |

True for this repository but unsafe to commit there (private, employer or personal content in a shared or public repository): treat as personal. Fits two homes: store it once in the narrower one and link from the other. Team or organisation rules: flag, never write.

## 4. Verify and write workspace items

1. Write each entry as one concrete, checkable line, conclusion first, with its reason and a citation (path and line, commit, command or URL).
2. Before writing, re-open the cited source live (re-run, re-read, re-fetch) and note the commit or time. If it disagrees, write the corrected version.
3. Search the target for the same concept: update the existing entry rather than adding a near-duplicate, and fix or remove any entry this session proved wrong.
4. Facts and events may be written directly. A new or changed `rule`, `procedure` or skill is shown as a diff and waits for the user's yes.
5. Keep an always-loaded file under about 200 lines; move detail into a linked file.
6. After editing a table or heading, re-read it: same cell count in every row, headings intact, nothing duplicated by a partial match.

## 5. Capture personal and generic items

1. Run the redaction and secret checks the user's instructions name on every line first. A line that fails is dropped and reported, never captured.
2. Append each line with the wiki's own command: `make -C ~/sandbox/wiki capture M="<line>"`. One line per item: `[distill <mode> <date and time>] <kind>: <claim> (why: <reason>; source: <repository alias>, <path, commit or URL>) #distilled`.
3. Write the raw line before any rewording, and report the path the command prints. Do not file into wiki notes, and never commit the wiki; its triage files the inbox later.
4. If the wiki is missing, append the same lines to `~/.agents/state/<workspace>/distilled-personal.md` and say so.
5. The wiki holds a summary of every project, area and system (`~/.local/share/chezmoi/docs/knowledge-layout.md`, "The wiki is the front door"). When the source changed what one says, or found a project, area or system with none, capture one line of kind `summary`: `summary: [[<note>]] <what changed or what it is>`; for a project, area or system with no note yet, write its proposed name without `[[ ]]`, because a link to a missing note fails the wiki's check. Work only in general terms.

## 6. Finish

1. Remove temporary files this run made; ask if you are unsure whether something is temporary. A research folder or document is removed only as its mode's reference says.
2. Commit every workspace file you changed, with a message that says what was recorded. Never push.
3. Personal agent rules (true for this user in every repository) are not written: list them in the report as proposed text for the user's personal instructions.
4. You are done when every candidate has a home or an explicit "not worth keeping", and every repository you touched is clean.

## 7. Report

1. What the source was, what it did or found, and what it means.
2. What you recorded and where (count per destination), what you dropped (count per drop reason, with an example of each), and any major errors you found.
3. Proposed personal agent rules, verbatim.
4. Learnings for the user, not for yourself.
5. Any way to improve these instructions, or "none".

## Handoff

Session mode only. When asked for a handoff, distill first, then end the report with a short prompt that starts the next session: the goal, where the records are, the first step, and anything waiting on the user. Put it last, in a fenced `text` block under the heading "Next session". Do not save it as a file.
