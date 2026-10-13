---
name: web-research
description: Searches multiple web sources, synthesizes findings, and produces cited research reports using delegated subagents. Use when the user asks to research a topic online, search the web, look something up, find current information, compare options, or produce a research report.
---

# Web Research

Plan the question, delegate subtopics to parallel subagents, then synthesize one cited answer.

## 1. Plan

1. Create `research_<topic>/` in the current working directory, unless the user or the active instructions name another location.
2. Break the question into distinct, non-overlapping subtopics:
   - Simple fact-finding: 1–2
   - Comparison: one per option, max 3
   - Complex investigation: 3–5
3. Write `research_<topic>/research_plan.md` with the question, the subtopics, what each should return, and how the results will be combined.

## 2. Delegate

Spawn one subagent per subtopic with the agent's subagent or task tool, up to 3 in parallel. Subagents don't see this conversation, so each prompt must stand alone:

```text
Research <specific question, no acronyms>.
Search with <search tool>; fetch a page with <fetch tool> when a snippet isn't enough.
Use 3–5 searches. Write key facts, short quotes, and the source URL for each claim to
<absolute path>/research_<topic>/findings_<subtopic>.md, then return a short summary.
```

- Name the search and fetch tools in the prompt and confirm the subagent has them. The Tavily skills (`tavily-search`, `tavily-extract`) need a terminal; if the subagent has none, give it the built-in web search and fetch tools, or run those searches yourself.
- Give the findings path as an absolute path.
- If no subagent tool is available, research the subtopics one at a time yourself, with the same budget and files.

## 3. Synthesize

1. List `research_<topic>/` and read every `findings_*.md` file.
2. Answer the original question directly, integrate the subtopics, cite a URL for each claim, and name gaps or conflicting sources.
3. Check any subagent claim you rely on before presenting it.
4. Write `research_<topic>/research_report.md` only when the user asks for a report file.

## Practices

- Plan before delegating.
- Keep subtopics distinct so subagents don't repeat each other's searches.
- Stop at the budget; 3–5 searches per subtopic is usually enough.
