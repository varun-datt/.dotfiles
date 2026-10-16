---
name: web-research
description: Searches multiple web sources, synthesizes findings, and produces cited research reports using delegated subagents. Use when the user asks to research a topic online, search the web, look something up, find current information, compare options, or produce a research report.
---

# Web Research

Plan the question, gather the sources yourself with `tvly`, have parallel subagents read them, then synthesize one cited answer.

## 1. Plan

1. Create `research_<topic>/raw/` in the current working directory, unless the user or the active instructions name another location.
2. Break the question into distinct, non-overlapping subtopics:
   - Simple fact-finding: 1–2
   - Comparison: one per option, max 3
   - Complex investigation: 3–5
3. Write `research_<topic>/research_plan.md` with the question, the subtopics, what each should return, and how the results will be combined.

## 2. Gather

Run every search and extract yourself, one command at a time, and save each result under `research_<topic>/raw/`, named by subtopic:

```bash
tvly search "<query>" --json -o research_<topic>/raw/<subtopic>-search-<n>.json
tvly extract "<url>" --json -o research_<topic>/raw/<subtopic>-page-<n>.json
```

Subagents don't run these: in VS Code they share your shell, so two running commands at once can get each other's output.

## 3. Delegate

Spawn one subagent per subtopic with the agent's subagent or task tool, up to 3 in parallel, to read the saved files. Subagents don't see this conversation, so each prompt must stand alone:

```text
Read the files in <absolute path>/research_<topic>/raw/ whose names start with <subtopic>-.
Do not search, fetch, or run commands. Write key facts, short quotes, and the source URL for
each claim to <absolute path>/research_<topic>/findings_<subtopic>.md, list what the files
could not answer, then return a short summary.
```

- Give every path as an absolute path.
- If no subagent tool is available, read the files and write the findings yourself.

## 4. Synthesize

1. List `research_<topic>/` and read every `findings_*.md` file.
2. Answer the original question directly, integrate the subtopics, cite a URL for each claim, and name gaps or conflicting sources.
3. Check any subagent claim you rely on before presenting it.
4. Write `research_<topic>/research_report.md` only when the user asks for a report file.

## Practices

- Plan before delegating.
- Keep subtopics distinct so findings don't overlap.
- Stop at the budget; 3–5 searches per subtopic is usually enough.
