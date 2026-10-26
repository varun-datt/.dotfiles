# Session mode: read the whole session

The context window is not the session. After a compaction it holds a summary, so a distill that reads only what is in view misses most of a long session. Read the log the agent's app keeps on disk.

## Where the log is

| Surface | Full log | Tool outputs |
| --- | --- | --- |
| VS Code chat | `<workspaceStorage>/<hash>/GitHub.copilot-chat/transcripts/<session>.jsonl`: every user message, every reply and its reasoning, every tool call with its arguments | Not in the transcript. `<hash>/chatSessions/<session>.jsonl` keeps them for each finished request, and `debug-logs/<session>/main.jsonl` keeps its newest ~100 MB (`github.copilot.chat.agentDebugLog.fileLogging.maxSessionLogSizeMB`). Neither is complete: in a 6.5-hour session, 245 of 1,654 calls had no output in either. Subagent replies: `debug-logs/<session>/*-<call id>.jsonl` |
| Copilot CLI and SDK | `~/.copilot/session-state/<session>/events.jsonl` | In the log |
| Cursor | `~/.cursor/projects/<folder>/agent-transcripts/<session>/<session>.jsonl`, the folder named after the path with each run of other characters as `-` (`/Users/me/.local/x` is `Users-me-local-x`): the user's messages, the replies, every tool call with its arguments, and failed turns. No timestamps (the digest dates it by the file's own times), no reasoning. Subagents: `<session>/subagents/<id>.jsonl`, joined to their `Task` call by the prompt (checked 2026-10-26 on 270 transcripts, one format) | Not kept anywhere |

The VS Code transcript marks a terminal command as succeeded even when it exited non-zero; a failure shows only in its output.

## Steps

Neither the log's size nor this chat's is a reason to skip a step or to distill from the context window: beyond two chunks, you coordinate and read no chunk yourself.

1. Find the log. `python3 ~/.agents/skills/distill/scripts/session_log.py find` lists the logs for the current folder, newest first. Pass `--session <id>` when the id is known; in VS Code it is the last folder of the session's debug-log path.
2. Condense it. `session_log.py digest [--session <id>]` writes `~/.cache/distill/<session>/chunk-NN.md` and prints what it read. A chunk holds the user's messages verbatim, the agent's replies and reasoning, one line per tool call, and, where the output is still on disk, a shell call's error lines, the answers to questions and subagents' replies.
3. Read every chunk, start to end. Up to two chunks, read them yourself. Beyond that, give each chunk to its own subagent with the chunk prompt below, all in one batch; each writes its part of the ledger to `ledger-NN.md` beside its chunk.
4. Keep a ledger at `~/.cache/distill/<session>/ledger.md`: a `## chunk-NN` heading for each chunk, with its candidates under it, or `none`. Subagents' parts join with `cat ledger-*.md > ledger.md` in that folder. Then run `session_log.py coverage --out ~/.cache/distill/<session> --ledger <ledger>`; it fails while any chunk has no heading or nothing under it. Do not judge candidates before it passes.
5. Up to two chunks, merge the ledger's candidates and judge them yourself in step 3 of SKILL.md. Beyond that, give steps 3 to 7 to one subagent with the judge prompt below, show the user its report, and write a rule, procedure or skill it proposes only after the user's yes. Either way, a candidate whose quote is not in its chunk is dropped as `unsupported`, and a record cites the live source re-checked in step 4, never the digest.
6. Delete `~/.cache/distill/<session>/` in step 6. It holds everything the session saw, including private and work content.

If no log is found, distill from the context window and say so at the top of the report, with how much it covers (for example, "context only: a summary up to 03:20, then the full turns").

## Chunk prompt

Fill in the paths and send it as is. A subagent does not inherit the user's rules, so the prompt restates them.

```text
Read all of <chunk path>, start to end: one slice of an agent session's log. Read only: change nothing and run nothing that changes state, except writing your answer to <ledger part path>.

List candidates for lasting records, not a summary. A candidate is any of: a correction or ruling by the user, a decision and its reason, a failure or surprise and what was expected instead, a trap in a tool or command, open work and what would release it, something that worked and should be repeated.

For each, one line: time | kind | the claim, conclusion first | the log line that shows it, quoted in at most 20 words.

Answer "none" if nothing qualifies. Do not judge whether it is already recorded or worth keeping; that is done later. Quote no private or work content beyond the evidence.

Write your answer under the heading `## chunk-NN`, with the chunk's number, to <ledger part path>, and reply with only the number of candidates.
```

## Judge prompt

Fill in the session id, the folder, the ledger path and whether this is a handoff, and send it as is.

```text
Run steps 1 and 3 to 7 of ~/.agents/skills/distill/SKILL.md on session <id>, from <folder>; read that file and references/session.md first. You are the judging subagent of step 5 there: judge here and delegate nothing. The candidates are in <ledger path>, under one heading per chunk; the chunks they cite are beside it.

Before you judge a candidate, find its quote in its chunk; if the quote is not there, drop the candidate as unsupported.

You may write facts and events, capture personal items with the wiki's command, and commit the files you changed by explicit path. Never use `git add -A`, and never push. Write no new or changed rule, procedure or skill: give each as a proposed diff with its path. Ask nothing; list what you would have asked.

Reply with the step 7 report, then the proposed diffs, then your questions. Handoff: <yes or no>; if yes, end with the Next session block. Quote no private or work content beyond the evidence.
```
