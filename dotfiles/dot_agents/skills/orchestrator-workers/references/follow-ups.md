# Follow-ups: orchestrator-workers

Research for future sessions, none of it dashboard work. Each item has a question, a scope, sources
and a stopping point. The URLs come from the source records and were not re-fetched (OPEN whether
they are current).

## (a) DEEP RESEARCH: improve and optimise the pattern, including a Copilot CLI orchestrator

**Question.** What would make this pattern cheaper, faster and more robust? How would it differ with
GitHub Copilot CLI as the orchestrator instead of VS Code chat?

**Scope.**
- **Cost:**
  - the worker and reviewer model mix;
  - reasoning effort;
  - review diff size, and whether a cheaper reviewer finds the same blocking findings;
  - orchestrator context growth and compaction.
- **Speed:** wave planning, the parallel limit, branching from a predecessor, earlier trial merges.
- **Robustness:**
  - the unexplained mass stops (F93 and the 2026-10-09 repeat);
  - `--no-auto-update`;
  - launching workers outside editor terminals (`setsid`, launchd, tmux);
  - whether `COPILOT_TASK_WAIT_TIMEOUT_SECONDS` is honoured.
  - VS Code's `chat.tools.terminal.detachBackgroundProcesses` (default off) wraps background
    commands in `nohup`: do workers then survive an editor quit? (OPEN)
- **A CLI orchestrator:**
  - **hooks:** session start and end, tool-use alerts, a Stop hook that posts status;
  - **background and delegated sessions** against `copilot -p` workers;
  - **resuming** the orchestrator itself;
  - **its own token cost;**
  - **monitoring:** OpenTelemetry against `status.py` and `watch.py`, and completion
    notification.

- **Owner questions, 2026-10-11** (quality and results first):
  - **Modes:** a plan-first mode (discussion, an overall plan, owner approval, then execution)
    beside direct execution. How is a plan written, approved and changed?
  - **Managing workers efficiently:** scheduling, dependency-aware waves, parallelism, and when
    to resume a session rather than relaunch it.
  - **Existing skills, tools and frameworks to build in,** for planning, analysis, orchestration,
    session management and anything else recommended. Examine these; none is a conclusion:
    - GitHub Spec Kit;
    - obra/superpowers: its brainstorming, plan-writing, plan-execution and subagent skills;
    - VS Code's Plan agent and handoffs;
    - Copilot CLI's modes and delegation;
    - Claude Code subagents and agent teams;
    - Microsoft Agent Framework's orchestration patterns;
    - LangGraph's supervisor;
    - OpenAI Agents SDK handoffs.
  - **Token optimisation and coordination:**
    - how the orchestrator and workers communicate (structured handoffs, shared files);
    - stable prompt prefixes for caching;
    - summaries rather than transcripts, and diff-only reviews;
    - model routing and compaction;
    - what costs quality.
  - **Status without context cost:** what the orchestrator reports, and whether a dashboard view
    of the run folder replaces polling.
  - **Escalation:** what earns the owner's attention (decisions, steering, blockers, sign-ins,
    risks), and what goes to a live status view instead. Owner rule, 2026-10-11: escalate only.
  - **Build or rely on the harness:** how much of this to build, against what agent harnesses
    (GitHub Copilot, Cursor, Claude Code, OpenAI Codex and others) already provide or are likely
    to provide soon. Give an educated prediction, labelled INFERRED, with the signals behind it.

**Sources.**
- [../SKILL.md](../SKILL.md), [details.md](details.md), [lessons.md](lessons.md),
  [../scripts/](../scripts/).
- `copilot --help` and `copilot help environment`.
- The [CLI command reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference),
  including its OpenTelemetry section.
- [Models and pricing](https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing).
- One finished run's `~/.copilot/session-state/*/events.jsonl`. Counts only, no message text.

**Stop when:**
- you have a ranked list of at most 10 changes, each with evidence labels, expected saving or risk
  reduction, and adoption cost;
- you have a one-page comparison of a VS Code and a CLI orchestrator, with a recommendation;
- you have a recommended design for the modes and for worker management, naming what to adopt from
  existing skills and frameworks;
- proposed edits to this skill are written but not applied until the owner approves.

Budget: about 60 minutes.

## (b) DEEP RESEARCH, for a future session (not dashboard work): VS Code chat, the VS Code Agents window and Copilot CLI

**Question.** For this owner, which surface fits which work, and why?

**Scope.** Compare the three surfaces on:
- **experience:** context, diffs, steering, interruption, several sessions at once;
- **features:** agents and subagents, background runs, worktrees, resuming, checkpoints;
- **customisation:** skills, hooks, prompt files, custom agents, instructions, MCP; where each
  lives and which surfaces share it;
- **monitoring and telemetry:** OpenTelemetry, debug logs, session stores, usage checkpoints;
- **limits:** file access, background-task timeouts, rate limits, coupling to the editor's lifetime;
- **cost:** credits per comparable task, and each surface's share of the owner's usage;
- **when to use which.**

Leave out cloud agents that cannot run this machine's tools.

**Sources.**
- [VS Code: monitoring agents](https://code.visualstudio.com/docs/agents/guides/monitoring-agents),
  and the VS Code docs on prompt files, custom agents, hooks and the Agents window.
- The Copilot CLI command reference.
- The owner's AI-usage proposal, for the measured credit split and the OpenTelemetry findings.
- [lessons.md](lessons.md).
- One identical small task on each surface, if the owner allows it.

**Stop when:**
- you have a table of surface against dimension, every cell labelled;
- each surface has a one-paragraph "use it when" rule;
- you have at most five recommended setup changes, none applied without approval.

Budget: about 60 minutes.

## (c) The cause of the CLI mass stops

**Question.** Why did every worker end with "Cannot invoke native session after disposal has
started" on 2026-10-08 (F93), and again on 2026-10-09 with no editor quit?

**Scope.** Read the CLI logs, auto-update records and session-store events around both times.
Change nothing.

**Sources.** `~/.copilot/logs/` (OPEN: the exact location), `copilot help environment`, the run's
`.err` files and [lessons.md](lessons.md).

**Stop when** you have a cause, or ranked hypotheses with evidence, plus one mitigation. Budget:
30 minutes.

## (d) DEEP RESEARCH: what the orchestrator decides alone, what goes to the owner, and how to enforce the line

**Question.** Which choices may an orchestrator or a worker make alone, which must go to the owner,
and how can that line be enforced rather than only written down?

**Starting recommendation** (orchestrator, 2026-10-13; INFERRED from one run, for the research to
test, not to adopt):

| If the choice… | Who decides | Example from the 2026-10-08 run |
| --- | --- | --- |
| changes what the owner sees, does or reads: product behaviour, workflow, navigation, defaults, wording | Owner | search syntax; navigation layout; a page's name |
| binds beyond the change: the first instance of a pattern, or a name, path or file layout others will copy | Owner | how a shared tool is packaged and installed |
| is hard to undo or leaves the machine: push, delete, publish, send, migrate without a backup, credentials | Owner | pushing a branch so an install can fetch its pinned commit |
| changes architecture: a new service, data store, dependency or cross-component contract | Owner | integrating a developer portal; a new parser dependency |
| moves cost, performance or reliability past a stated budget, or trades one for another | Owner | telemetry content capture that grew a log file fast; models for workers and reviewers |
| weakens a check, a test, a review step or a privacy control | Owner | a timing test changed to a median with a ceiling; last fix rounds verified by the orchestrator's diff read instead of a review, done without approval |
| touches security or privacy, or someone else's system | Owner | a security finding in another team's service; how test-environment data is handled |
| changes scope: drops or adds part of what was asked | Owner | — |
| is reversible and inside an accepted design: implementation detail, tests, internal names, ordering, retries, a conflict resolution that keeps both behaviours, a far-fetched finding rejected with a reason | Orchestrator or worker, recorded as ASSUMED, for the owner, wherever the owner might rule otherwise | time limits per job kind; judging a review finding non-blocking |
| is mechanics: ports, worktree paths, run names, logs | Orchestrator; not recorded | test port bases |

Tie-break: a one-way door goes to the owner; a two-way door is decided and recorded.

**Scope.**
- Test the table against the run's owner rulings and the choices workers recorded as ASSUMED: which
  rows the owner would move, and where a choice slipped through unasked.
- Frameworks to examine, none a conclusion: one-way and two-way doors; RACI and DACI; risk tiers;
  architecture decision records; the human-in-the-loop points in Anthropic's "Building effective
  agents", OpenAI's practical guide to building agents (guardrails, human intervention), LangGraph
  interrupts, Microsoft Agent Framework's human-in-the-loop, and the review gates of GitHub
  Copilot's coding agent.
- **Writing it down:** wording for a workspace `AGENTS.md`, this skill and the worker preambles. A
  short table with examples, against adjective rules ("significant", "major") that agents read
  loosely.
- **Enforcing it** as far as possible, each with what it cannot catch:
  - tool denies (`--deny-tool`), and hooks that block an action: push, delete, settings writes,
    edits to decision records;
  - a required "Decisions" section in every worker report, with a "binds" column, and a Stop hook
    that refuses a report without it;
  - the reviewer checking the diff for an unlabelled decision;
  - escalations kept as data, a state file of decisions with type and status that a status view
    lists, instead of prose;
  - a check that every ASSUMED choice reaches the owner's end-of-session batch.

**Sources.** The rule in the source workspace's `AGENTS.md` that architecture and design decisions
are never settled alone; the run's owner rulings (the project's orchestrator runbook);
[lessons.md](lessons.md); the Copilot CLI and VS Code docs on hooks and tool permissions; the
frameworks above (re-fetch each URL).

**Stop when:**
- the table is revised, each row with an example from the run and a source;
- wording is proposed for `AGENTS.md`, this skill and the preambles;
- at most five enforcement mechanisms are ranked by coverage and cost, each with what it misses;
- nothing is applied until the owner approves.

Budget: about 60 minutes.

## (e) Worker reliability: stalled, rate-limited, erroring and dead workers, handled even when the orchestrator's chat is idle

**Question.** How does the orchestrator detect and recover a worker that stalls, is rate-limited,
errors or dies, and how is that guaranteed while the orchestrator's chat takes no turn?

**Observed in the 2026-10-08 run** (VERIFIED from the run notes unless marked):
- Watchdog alerts started no turn in an idle chat for four hours ([lessons.md](lessons.md),
  2026-10-12). Cause OPEN.
- Model calls that never answered: 25 minutes after a window reload, 38 minutes with no cause seen.
- `session.error` "Failed to get response from the AI model; retried 5 times" after sleep, with exit
  0.
- Two unexplained mass stops (item (c)), and every worker stopping when the editor quit.
- Rate limits and exhausted premium requests: not seen. What they look like in `events.jsonl` and
  `.err` is OPEN.

**Scope.**
- A failure table: each failure, its signal (`events.jsonl`, `.err`, exit code, process table), the
  automatic action, the orchestrator's action, and when the owner is told.
- What the watchdog may do with no orchestrator turn, for example kill a stalled run and resume it
  once, or back off on a rate limit; and how each automatic action is logged where the next turn
  reads it.
- Keeping the orchestrator responsive: waiting in-turn on the watchdog with a bounded sync call,
  against ending the turn on an async notification; how VS Code delivers terminal notifications to
  an idle chat (docs, then source); a CLI orchestrator loop; launching outside the editor (launchd,
  tmux, `setsid`).
- Retry without duplicate work: commit per step, idempotent resume prompts, and when to relaunch
  instead of resuming.
- Hard caps (`timeout`) against soft budgets (alerts), and an automatic action at 2.5x.

**Sources.** [lessons.md](lessons.md); [../scripts/status.py](../scripts/status.py) and
[../scripts/watch.py](../scripts/watch.py); the run's `.err` and `events.jsonl` files;
`copilot help environment`; the Copilot CLI and VS Code docs on background terminals and agent
notifications; GitHub's rate-limit and premium-request docs (re-fetch each URL).

**Stop when:**
- the failure table is complete, each row labelled;
- one mechanism for the idle-chat gap is recommended and tested on a toy run: a two-minute fake
  worker finishing while the chat is idle;
- script changes are proposed, not applied.

Budget: about 60 minutes.

## (f) When an orchestrator session should hand off, and what the handoff holds

**Question.** Which signals say an orchestrator session has run long enough, and how is the handoff
made cheap and complete?

**Observed in the 2026-10-08 run**, one chat over five days with several compactions:
- After compactions, slips that a rule already in context covered recurred: a stop chained with `;`
  instead of `&&`; an owner ask repeated twice without re-reading the state it changes; a notes edit
  that swallowed a line; a handoff table stale within hours.
- The owner asked for the switch at 00:45 on 2026-10-12; in-flight work kept the chat busy until
  07:16.
- Terminal notifications go only to the chat that launched the terminal, so the old chat had to stay
  open. Its watchdog exits on each alert, and only a turn restarts it.
- The chat's session memory, which is cleared with the chat, held the only full log until it was
  copied to the run folder at close, although this skill puts the notes there.

**Starting recommendation** (INFERRED, to test): hand off at the first of
- the second compaction;
- a rule already in context broken twice;
- a wave boundary, with all in-flight work merged or parked;
- the owner asking.

Keep the run folder and a state file current at every event, so that a handoff is a pointer rather
than a writing task. The new chat starts its own watchdog; workers keep running across the handoff.

**Scope.**
- Signals: context size and compaction count (what VS Code and the CLI expose), turn latency, rules
  broken that the context already holds, owner corrections, stale summaries.
- Long-context degradation, compaction and structured note-taking: Anthropic's "Effective context
  engineering for AI agents", Chroma's "Context rot", Claude Code's auto-compact, Copilot CLI
  `/compact`, VS Code's conversation summarisation (re-fetch each URL).
- The handoff's contents: rulings, queue, in-flight sessions with resume commands, prompts ready,
  merge state, pending owner decisions, and what the new session must re-verify. The project's
  orchestrator runbook has worked examples.
- Ownership of worker terminals and notifications across chats.

**Stop when:**
- you have a checklist of hand-off triggers, each with a threshold and evidence;
- you have a handoff template;
- edits to "Hand off before the context fills" in [../SKILL.md](../SKILL.md) are proposed, not
  applied.

Budget: about 45 minutes.

## (g) Small fixes, found 2026-10-13

Not research: each is a change with a test.
- **`test_status.py` reads the caller's environment.** Pin `OW_PREFIX` and `OW_RUN_DIR` in every test
  that runs `status.py`, as `test_state.py` already does ([lessons](lessons.md)).
- **Ship the in-turn wait in `scripts/`.** The run folder's wait script refuses a pipe and reports
  rounds that ended since the previous wait; neither exists in the skill, so the next run starts
  without both.
- **Settle whether a cap applies to a resumed session.** Cheap probe: resume a small session with a
  cap below what it has already spent, and see whether its first call is refused.
