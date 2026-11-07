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

Neither the log's size nor this chat's is a reason to skip a step or to distill from the context window: you coordinate, and read and judge nothing yourself, however few the chunks.

1. Find the log. `python3 ~/.agents/skills/distill/scripts/session_log.py find` lists the logs for the current folder, newest first. Pass `--session <id>` when the id is known; in VS Code it is the last folder of the session's debug-log path.
2. Condense it. `session_log.py digest [--session <id>]` writes `~/.cache/distill/<session>/chunk-NN.md` and prints what it read. A chunk holds the user's messages verbatim, the agent's replies and reasoning, one line per tool call, and, where the output is still on disk, a shell call's error lines, the answers to questions and subagents' replies.
3. Read every chunk, start to end: give each chunk to its own subagent that can write files, with the chunk prompt below, on the reading model from the Models table in SKILL.md: VS Code's `distill-reader` agent, or the `general-purpose` type in Copilot CLI and SDK sessions, never a read-only one such as VS Code's Explore or the CLI's `explore`. Start chunk-01's subagent alone, and the rest in one batch as soon as it returns: subagents started together each pay full price for the same ~50k-token start, while those started after one has finished find it in the prompt cache at a twenty-fifth of the price, for about five minutes (2026-10-30: nine readers started together paid about 25 credits each for it; the judge, started 1.5 minutes after them, found 40k of its 50k tokens cached). Each writes its part of the ledger to `ledger-NN.md` beside its chunk.
4. Keep a ledger at `~/.cache/distill/<session>/ledger.md`: a `## chunk-NN` heading for each chunk, with its candidates under it, or `none`. Once every subagent has replied, their parts join with `for f in ledger-[0-9]*.md; do cat "$f"; echo; done > ledger.md` in that folder, so a part without a final newline cannot swallow the next part's heading; a chunk whose part is missing goes to a new subagent. When a subagent declines to read its chunk, rerun that chunk on a model of another family before halving it. Then run `session_log.py coverage --out ~/.cache/distill/<session> --ledger <ledger>`; it fails while any chunk has no heading or nothing under it. Do not judge candidates before it passes. Then run `session_log.py quotes --out ~/.cache/distill/<session> --ledger <ledger>`: it keeps the candidates whose quote is in their chunk in `ledger.checked.md` and moves the rest to `unsupported.md`, matching across case, spacing, curly quotes, dashes, escapes and `...` gaps.
5. Give steps 1 and 3 of SKILL.md to a judging subagent with the judge prompt below; it writes its verdicts to `verdicts.md` beside the ledger. Then give steps 4 to 7, for the kept candidates only, to a fresh writing subagent with the writer prompt below. Both are VS Code's `worker` agent (the CLI's `general-purpose` type), on the judging model from the Models table; neither carries the other's reading, so neither has to compact. Show the user the writer's report, and write a rule, procedure or skill it proposes only after the user's yes. A candidate in `unsupported.md` is dropped as `unsupported`, and a record cites the live source re-checked in step 4, never the digest.
6. Once the writer has replied, in VS Code run `session_log.py cost --out ~/.cache/distill/<session>` and add its table to the report: what the chat, each reader and the judges spent, their cache misses and compactions. Then delete `~/.cache/distill/<session>/`. It holds everything the session saw, including private and work content.

If no log is found, distill from the context window and say so at the top of the report, with how much it covers (for example, "context only: a summary up to 03:20, then the full turns").

## Chunk prompt

Fill in the paths and the lines already recorded, and send it as is. A subagent does not inherit the user's rules, so the prompt restates them.

```text
Read all of <chunk path>, start to end: one slice of an agent session's log. Change nothing and run nothing that changes state, except writing your answer to <ledger part path>.

List candidates for lasting records, not a summary. A candidate is any of: a correction or ruling by the user, a decision and its reason, a failure or surprise and what was expected instead, a trap in a tool or command, open work and what would release it, something that worked and should be repeated.

For each, one line: time | kind | the claim, conclusion first | the log line that shows it, quoted in at most 20 words.

Answer "none" if nothing qualifies. Skip what these lines already say, and open no file to check them: <one line per topic already recorded, with its record's path>. Do not judge whether a candidate is worth keeping; that is done later. Quote no private or work content beyond the evidence.

Write your answer under the heading `## chunk-NN`, with the chunk's number, to <ledger part path>, and reply with only the number of candidates.
```

## Judge prompt

Fill in the session id, the folder and the checked ledger's path, and send it as is.

```text
Run steps 1 and 3 of ~/.agents/skills/distill/SKILL.md on session <id>, from <folder>; read that file first. You are the judging subagent of step 5 of references/session.md: judge here, delegate nothing, and write nothing but <folder>/verdicts.md. The candidates are in <checked ledger path>, under one heading per chunk; the chunks they cite are beside it.

Every candidate there has had its quote found in its chunk by a script; do not check quotes again, and judge nothing in unsupported.md. To test whether a record already says a candidate, search for it (`python3 ~/.agents/skills/kb/scripts/kb.py search "<claim>"`, or grep) and open only the lines a hit points to, never a whole file.

Write verdicts.md: under `## kept`, one line per kept candidate: kind | destination | the claim, conclusion first | its chunk and quote; under `## dropped`, the count per drop reason with one example of each. Reply with only the number kept. Quote no private or work content beyond the evidence.
```

## Writer prompt

Fill in the session id, the folder and whether this is a handoff, and send it as is.

```text
Run steps 4 to 7 of ~/.agents/skills/distill/SKILL.md on session <id>, from <folder>; read that file first. You are the writing subagent of step 5 of references/session.md: delegate nothing. The kept candidates, with their kind and destination, are in <folder>/verdicts.md; the chunks they cite are beside it. In the report, count the dropped ones listed there, and those in unsupported.md as dropped `unsupported`. Leave <folder> in place: the chat deletes it.

You may write facts and events, capture personal items with the wiki's command, and commit the files you changed by explicit path. Never use `git add -A`, and never push. Write no new or changed rule, procedure or skill: give each as a proposed diff with its path. Ask nothing; list what you would have asked.

Reply with the step 7 report, then the proposed diffs, then your questions. Handoff: <yes or no>; if yes, end with the Next session block. Quote no private or work content beyond the evidence.
```
