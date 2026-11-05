---
schema: agent-state/v2
workspace: /absolute/path
updated: YYYY-MM-DD
---

# Current state

Read the section for the topic you are resuming, not the whole file. This holds what is true in the workspace now: what waits on the owner, what is in flight, and what was settled for work still in flight. Keep it under 25 KB, edited in place. No dated session notes: what happened lives in git, the repository's records and the session transcripts. When a topic closes, move what lasts to its long-term home (decisions, gotchas, findings, docs, skills, as the workspace's `AGENTS.md` names them) and delete the topic here; git keeps every earlier version. Write this file only from the terminal with `python3 ~/.agents/skills/distill/scripts/state.py write`, which refuses when the file changed since you read it.

## Waiting on the owner

- [ ] What the owner has to do or decide, in one line ([Topic name](#topic-name)).

## Topic name

- Status: what exists and works now, in the present tense.
- Next: an action concrete enough to start cold, or what blocks it and what would release it.
- Settled: a decision for this topic and its reason; not re-asked without new evidence.
- Links: branch, worktree, pull request, research folder, records.

## Open questions

- Question: what would settle it.
