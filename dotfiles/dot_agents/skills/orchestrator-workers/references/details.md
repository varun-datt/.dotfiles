# Details: orchestrator-workers

The long tables behind [../SKILL.md](../SKILL.md). Labels: VERIFIED, INFERRED, OPEN. *Example
(source project)* marks a fact from the source session.

## Launch flags

VERIFIED: every flag below is listed by `copilot --help` for CLI 1.0.95.

| Flag | Why |
| --- | --- |
| `timeout <s>` | A hard cap on a hung run; about 3x the budget (INFERRED) |
| `COPILOT_TASK_WAIT_TIMEOUT_SECONDS` | A `-p` run that leaves a background task running is cut off after 600 s. The variable is not listed in `copilot help environment` (OPEN). The real fix is the preamble's rule: gates run in the foreground |
| `-C <worktree>` | The worker works in its own worktree |
| `-n <prefix><item>` | `-r` can resume it by name, and `status.py` recognises it as live. Name run files `<item>*` |
| `--model`, `--reasoning-effort <effort>` | By the kind of round, from [routing.md](routing.md); never the automatic choice |
| `--max-ai-credits <cap>` | Ends a runaway round; the cap comes from `mine.py --caps` ([routing](routing.md#credit-caps)). The minimum is 30, and the last model call may overshoot it (VERIFIED, `copilot --help`, CLI 1.0.97) |
| `--no-ask-user`, `--allow-all-tools` | Headless: nobody is there to answer a question or a permission prompt |
| `--deny-tool 'shell(git push)'` | Deny rules win over allow-all |
| `--disable-builtin-mcps`, `--disable-mcp-server <name>` | Allow-all also approves MCP write tools, and the deny rules do not cover them. Check that `session.mcp_servers_loaded` shows `disabled` |
| `--add-dir <path>` | `-p` sessions are denied files outside the worktree. This grants access, writing included, so the prompt must say read-only |
| `--output-format json` | JSONL events for `status.py` and `result.py` |
| `</dev/null`, `2> <item>.err` | No stdin to wait on; stderr carries CLI-wide failures |
| Reviewer: `--deny-tool=write --deny-tool=shell --deny-tool=url` | Read-only. Use a model from another family |

**Reading a result.**
- The last `assistant.message` holds the report.
- A `result` event is not success on its own. Check its `exitCode`, and look for any
  `session.error` after the last progress.
- `session.usage_checkpoint` is cumulative across `-r` resumes.

## Failure modes and recoveries

| Failure | Sign | Recovery |
| --- | --- | --- |
| CLI-wide stop | Every worker ends in the same second. stderr: "Cannot invoke native session after disposal has started" | Resume each one with [resume.md](../assets/resume.md), naming its last commit; re-run the reviews. Cause OPEN |
| Editor quits | Workers launched from its terminals die | Resume them. Launching outside the editor is untested (OPEN) |
| Window reload | A worker hangs inside one model call for 25 minutes or more | Kill it by PID and resume it |
| Sleep or battery | Every worker stalls. A model call that fails five times ends the run with `session.error` | Keep the machine on AC power and snapshot uncommitted work. *Example (source project):* `caffeinate` was killed, INFERRED by endpoint policy; do not bypass that |
| Leftover test servers | Port clashes; invalid mutations | Find them with `ps` and `lsof` and kill them by PID. Give every worker its own ports |
| Leaked processes | Supervision tests leave orphans that ignore TERM, for hours | Check `ps` after such runs; kill process groups |
| Load flakes | A timing test fails, then passes alone | Re-run it alone, record it, and fix the timing assumption with a median of repeats and a ceiling |
| No access outside the worktree | "Permission denied" on a sibling repository | Relaunch with `--add-dir` and a read-only line in the prompt |
| Shell reads outside the worktree | Reads outside the worktree appear in the tool calls | Name what is off limits, and check the tool calls |
| False success | `exitCode` 1 or a `session.error`, while the shell exits 0 | `status.py` shows ERRORED |
| Credit cap reached | A `session.warning` event "Session limit reached (32.5/30 AI credits used)", not tool output quoting it; `result` `exitCode` 0 and the shell exits 0, so it looks done | `status.py` and `result.py` show CAPPED with credits against the cap (`result.py` exits 3), and `watch.py` alerts. Only a later fix or resume of the item supersedes it, never a review. Then extend or narrow it ([routing](routing.md#credit-caps)) |
| Overclaimed security | "The real keys are masked" | Check it against the real values yourself, printing only true or false |
| A gate run disturbed | The merge folder was checked out during a run | Re-run the gates; kill any leftover servers; keep the merge folder for gate runs only |

## State file

`<run>/orchestrator.json` holds what only the orchestrator knows: each item's kind and gate commands, the queue, and the questions for the owner. Write it only with `scripts/state.py`, never by hand; each write replaces the file atomically under a lock and prints one line.

Commands and options: `python3 scripts/state.py --help`, and `<command> --help`. `init` also registers the run once in
`OW_REGISTRY` (default `~/.local/state/orchestrator-workers/registry.jsonl`); an item's `--gate` commands let a status view show its worker as at its gates.

The owner answers in the chat. Record the answer with `answered` as soon as you act on it, or the question stays open on the dashboard.

## Cost

- **Who spends.** *Example (source project, measured 2026-10-10):* programmatic sessions (workers,
  reviewers and research workers) used 92% of Copilot CLI credits, 75,836 of 82,062. Interactive
  sessions used 6,226 (VERIFIED, read).
- **Per round** (VERIFIED, read in the notes):
  - a worker round: about 15 premium requests and 350–1,750 credits;
  - a review: 1 premium request and 130–1,000 credits.
- **Reviewer price.** About 2.5x the worker model's per token. *Example (source project):*
  - GPT-6 Astra: $10, $12.50 and $50 per million input, cache-write and output tokens;
  - Opus 5.5: $4, $5 and $20;
  - cached input differs 5x: $1 against $0.20;
  - one credit is $0.01.

  Prices VERIFIED (read in the record), not re-fetched; whether they are current is OPEN.
- **Context.** *Example (source project):*
  - a single session's median was 268K input tokens per model call;
  - the orchestrator's median was 117K at its 27th call.
- **Savings:**
  - workers commit each step;
  - reviewers read a diff;
  - re-reviews cover the fixes only;
  - the orchestrator reads summaries, not transcripts;
  - routing by kind of round, keep-warm polling and dynamic caps ([routing.md](routing.md)).
- **Credit caps, probed** (VERIFIED by the orchestrator, CLI 1.0.97, `-p` with `--max-ai-credits 30`):
  - after model calls the session prints `session.info` "Session limits: X/30 AI credits used." (seen only near a cap: rounds far below theirs print no such line);
  - near the cap it adds "the next model call is final; tools will be disabled.";
  - then a `session.info` "Session limit reached..." and a `session.warning` "Session limit reached (32.5/30 AI credits used)...": the last call overshot the cap;
  - Whether a `-r` resume counts the conversation's earlier credits against the new cap is OPEN; the help says limits "apply across the current conversation".
- **Mining** (`scripts/mine.py`): per round, credits and premium requests are the difference between consecutive `session.usage_checkpoint` totals of the same session, from its `result` `sessionId`; a session's first round that is not a build, research or review is listed as partial, outside caps and markers, only when an earlier launch of its item (a `<name>.start`) has no events in the folder; a fresh `-p` merge or catch-up counts in full. A capped review or re-review reads `incomplete`, never a verdict; the report's own line is kept as `raw_verdict`. A round that died before any checkpoint has unknown credits, and its spend lands in the next round of its session (INFERRED).
