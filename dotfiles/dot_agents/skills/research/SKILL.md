---
name: research
description: Answers one research question from primary sources and leaves one cited, dated note where the repository keeps research. Use when research is handed to a worker or subagent (wayfinder's research tickets, one worker per question) or when a decision waits on an outside fact and the answer should be a file, not a chat reply. For research answered inside the chat, use web-research.
---

# Research

You do the research yourself. If you are already a subagent or worker, never start another agent
for it.

## 1. Pin the question

1. Write down the question, the answer that would settle it, and the stopping point: at most 3
   subtopics and 3 to 5 searches each, unless the caller set another.
2. Search the owner's knowledge first: `python3 ~/.agents/skills/kb/scripts/kb.py search "<question>"`.

## 2. Read primary sources

- Find with `tvly search "<query>" --json`, read with `tvly extract "<url>" --json`. Keep raw output
  in a temporary folder outside the repository.
- Primary sources are official docs, source code, specs, first-party APIs and the paper itself.
  Follow each claim back to the source that owns it; a secondary write-up is only a lead to one.
- A `tvly research` report is a list of leads, not evidence.
- An extract that returns only page chrome (navigation, sign-in or cookie text) is a failed read:
  say so and read the page another way.
- If `gh` cannot read a public repository, read its pages with `tvly extract`.

## 3. Write one note

- One Markdown file named `YYYY-MM-DD-<topic>.md`, where the repository keeps research: the home
  its `AGENTS.md` names, else its existing research folder, else `research/`, and say which.
- Lead with the answer. Put a URL on every claim, mark inference as inference, and name what
  stayed unresolved and every source that could not be read, with why.
- Return the note's path and a summary of three lines at most.

The caller checks the note against its question and the owner rules on it; there are no critique
or fix rounds.
