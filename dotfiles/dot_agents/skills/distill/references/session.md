# Session mode: read the whole session

The context window is not the session. After a compaction it holds a summary, so a distill that reads only what is in view misses most of a long session. Read the log the agent's app keeps on disk.

## Where the log is

| Surface | Full log | Tool outputs |
| --- | --- | --- |
| VS Code chat | `<workspaceStorage>/<hash>/GitHub.copilot-chat/transcripts/<session>.jsonl`: every user message, every reply and its reasoning, every tool call with its arguments | Not in the transcript. `<hash>/chatSessions/<session>.jsonl` keeps them for each finished request, and `debug-logs/<session>/main.jsonl` keeps its newest ~100 MB (`github.copilot.chat.agentDebugLog.fileLogging.maxSessionLogSizeMB`). Neither is complete: in a 6.5-hour session, 245 of 1,654 calls had no output in either. Subagent replies: `debug-logs/<session>/*-<call id>.jsonl` |
| Copilot CLI and SDK | `~/.copilot/session-state/<session>/events.jsonl` | In the log |
| Cursor | Not read yet: `~/.cursor/projects/<folder>/agent-transcripts/` exists, its format is unchecked | |

The VS Code transcript marks a terminal command as succeeded even when it exited non-zero; a failure shows only in its output.

## Steps

1. Find the log. `python3 ~/.agents/skills/distill/scripts/session_log.py find` lists the logs for the current folder, newest first. Pass `--session <id>` when the id is known; in VS Code it is the last folder of the session's debug-log path.
2. Condense it. `session_log.py digest [--session <id>]` writes `~/.cache/distill/<session>/chunk-NN.md` and prints what it read. A chunk holds the user's messages verbatim, the agent's replies and reasoning, one line per tool call, and, where the output is still on disk, a shell call's error lines, the answers to questions and subagents' replies. `--no-reasoning` drops the reasoning when the chunks are too many to read.
3. Read every chunk, start to end. Up to two chunks, read them yourself. Beyond that, give each chunk to a read-only subagent with the prompt below, several at once, and spot-check each answer against its chunk before using it.
4. Keep a ledger at `~/.cache/distill/<session>/ledger.md`: a `## chunk-NN` heading for each chunk, with its candidates under it, or `none`. Then run `session_log.py coverage --out ~/.cache/distill/<session> --ledger <ledger>`; it fails while any chunk has no heading or nothing under it. Do not judge candidates before it passes.
5. Merge the ledger's candidates and judge them in step 3 of SKILL.md. The chunks show where to look; cite the live source you re-checked in step 4, never the digest.
6. Delete `~/.cache/distill/<session>/` in step 6. It holds everything the session saw, including private and work content.

If no log is found, distill from the context window and say so at the top of the report, with how much it covers (for example, "context only: a summary up to 03:20, then the full turns").

## Chunk prompt

Fill in the path and send it as is. A subagent does not inherit the user's rules, so the prompt restates them.

```text
Read all of <chunk path>, start to end: one slice of an agent session's log. Read only; change nothing and run nothing that changes state.

List candidates for lasting records, not a summary. A candidate is any of: a correction or ruling by the user, a decision and its reason, a failure or surprise and what was expected instead, a trap in a tool or command, open work and what would release it, something that worked and should be repeated.

For each, one line: time | kind | the claim, conclusion first | the log line that shows it, quoted in at most 20 words.

Answer "none" if nothing qualifies. Do not judge whether it is already recorded or worth keeping; that is done later. Quote no private or work content beyond the evidence.
```
