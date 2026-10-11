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
