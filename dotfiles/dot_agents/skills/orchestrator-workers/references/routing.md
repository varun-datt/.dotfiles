# Routing: model, effort and credit cap per round

Owner rulings, 2026-10-13. The orchestrator applies them to every round it launches; changing them is the owner's call, except the cap and routing adjustments the [learning loop](#learning-loop) records as markers.

| Round (run name) | Model | Effort | Escalate when |
| --- | --- | --- | --- |
| Build of a new feature or turn handling (`<item>`) | Strongest worker model | high | - |
| Small item (`<item>`) | claude-sonnet-5.5 | medium | Strongest model at high when it touches a risk area or is unsure |
| Fix after review (`<item>-fixN`) | claude-sonnet-5.5, in a fresh session with a short brief | medium | - |
| Resume (`<item>-resumeN`) | The model of the round it resumes | high | - |
| Catch-up merge (`<item>-catchup`, `<item>-mergeN`) | Mid-tier model of the same family | high | Strongest model for 3 or more conflicts, code-level conflicts, or any risk area |
| Review and re-review (`<item>-reviewN`, `<item>-rereviewN`) | Another model family than the author | high | max when the diff touches a risk area |
| Research (`<item>-research`) and documents | claude-sonnet-5.5 | medium | - |

The 2026-10-29 rulings changed the build, fix, small item, document and research rows. Reviews stay at high, max on risk areas.

## The router

`scripts/route.py` now picks each round's model, effort and cap; the table above is its fallback (when the classifier fails) and its shadow (logged beside every choice). Policies and models are separate: `routes.json` holds plain-language categories, each with a pool of models cheapest first, plus the floors; changing models means editing only its pools and `strongest` entries.

```sh
python3 scripts/route.py run <round> --kind build|fix|review|research|small|resume|merge --brief <brief> --worktree <wt> [--run "$OW_RUN_DIR"] [--add-dir D ...] [--override "model=..,effort=..,context=..,cap=<n>|none,reason=.."] [--author-model M] [--timeout S] [--load-wait MIN] [--fresh]
python3 scripts/route.py pick --run "$OW_RUN_DIR" --item <id> --kind build|fix|review|research|small|resume|merge --prompt <brief> [--author-model M] [--diff FILE] [--budget-left F] [--run-fraction F] [--seed N] [--fresh]
python3 scripts/route.py escalate --run "$OW_RUN_DIR" --item <id>
python3 scripts/route.py report --run "$OW_RUN_DIR"
```

**`run` is the only way a round is launched; a run must not write its own copilot launch scripts** (on 2026-10-30 scripts with a fixed `MODEL` and `EFFORT` bypassed the router). It checks the brief with `brief.py check --repo <worktree>`, picks as `pick` does or takes `--override` (refused without `reason=`; the routed choice is kept as `routed_choice`, the override and its reason as `override`; `cap=none` launches uncapped, `auto` is refused), logs the decision with `cli_version` (`copilot --version`) and `model_id`, and runs `copilot -p` under a timeout with exactly the logged model, effort, context and cap, and the launch recipe's safety flags. A `launch` line in `routes.jsonl` records the argv without the prompt. For a review without `--author-model`, the author's model is read from the author round's log (`inputs.author_source`). It keeps the recipe's load wait, `.start` and `.base` files, time budget in `budgets.json` (from the brief's `TIME BUDGET:` line) and leftovers sweep; the timeout defaults to the budget for a review and 3x the budget otherwise. Exit codes: copilot's own when non-zero, 124 timeout, 3 capped, 4 errored or no clean result, 5 brief refused, 12 load, 2 usage or override refused. `budgets.json` and `routes.jsonl` are written under a lock, JSON through a temporary file and `os.replace`. Re-running `pick` or `run` for a round whose decision has not launched reuses that decision; `--fresh` draws again, and a run after a launch draws a new one.

`pick` prints `MODEL=... EFFORT=... CONTEXT=... CAP=...` and a `# reason` line, and launches nothing. Steps: one `claude-haiku-5.5` call through `copilot -p` (no tools, no MCP servers, under `timeout`, about 0.3 credits) returns the category and 1 to 5 grades with quotes; any failure falls back to keyword rules and the table. The tier (easy, medium, hard) comes from the grades; the cell is category x tier. Each pool model gets a Beta posterior from past rounds in the cell (widened to the category, then the kind, under 3 rounds), is Thompson-sampled, and the cheapest model whose sample clears the tier's target wins. The target falls as spend (`--budget-left`) runs ahead of time (`--run-fraction`). Floors always win: `src/host/sessions.ts` and risk areas get the strongest model at high (risk-area reviews max); a review is never the author's family; never `auto`. New features have no floor (owner, 2026-10-29: "router decides from grades, history and budget alone (risk floors stay)"); the table's build row is now only the shadow and the fallback. Success means: not capped, exit 0, no blocking review finding, at most one fix round. The cap comes from `mine.py --caps`.

Levers beyond the model (evidence: [research/2026-10-29-router-levers.md](../../../../../research/2026-10-29-router-levers.md)):

- **Quality first** (owner, 2026-10-29: "if a choice has to be made prioritize quality over cost"). For model, effort and context alike, the stronger arm wins when the cheaper one has fewer than `quality.min_cell_rounds` outcomes in its cell, or its mean minus `quality.tie_sd` standard deviations falls below the target. Only spend running ahead of time (`--budget-left` against `--run-fraction`) turns the rule off and lowers the target.
- **Effort** is a learned arm: the old rule (medium when ambiguity and verification are both 2 or lower, else high) picks the prior and the arm one step up. Each arm's Beta adds the kind's other outcomes at weight `learning.kind_share`, so few outcomes still count. Floors and `kind_min_effort` still win.
- **Context** is `default` unless the brief shows `context.min_signals` signals (long logs, the whole repository, large files, many file paths, a very long brief, breadth 5). When it does, `default` and `long_context` are learned the same way, with a prior that favours `default`.
- **Classifier** is a pool (`classifier.pool`). `route.py eval-classifier --run R [--models a,b] [--max-credits N]` grades the logged briefs of R and the two run folders before it with each model. It prints credits per call, agreement with the first model, and how well a hard tier predicts failed or capped rounds. First run, 2026-10-29 (44 credits): 7 briefs, too few to decide, so Haiku stays.
- `report` adds ok and failed tallies by effort and by context. After a capped round or a failed gate, `escalate` returns the next model up the pool at the same effort.

Reading `<run>/routes.jsonl`, one JSON line per decision: `inputs` (including the seed), `classifier` (`source` is `classifier`, `stub` or `fallback`, with `fallback_reason`; each grade with its quote), `cell`, `scores` (per model: alpha, beta, n, `level` the cell was widened to, the `sample`), `target`, `floor`, `choice`, `static` (the table's choice), `differs`, `reason`. `route.py report` prints each decision against the static choice and its round's outcome. Until `routes.jsonl` has logged decisions, history is read by kind only (the category and tier of past rounds are unknown), so the router leans on the kind-level record.

How outcomes are read. A review's verdict comes from `<run>/<name>.txt` when it exists (`review.sh` writes it after each review: one line, `Blocking: none` or `N blocking`), else from the review round's last top-level `assistant.message` in its log: the first line outside block quotes and code fences reading "Blocking: none", "no blocking findings" or "N blocking" (optionally after "Verdict:"), else the count of list items under a "Blocking" heading. `verdict_source` records which (`txt` or `log`); a review with neither reads "no verdict" and its blocking stays unknown. Before this, no run wrote the txt, so every reviewed item read blocking unknown and the router never saw a blocking finding. `mine.py` also counts silent compactions per round: a call whose context is below 60% of the previous call's, when the previous call was at 75% or more of the model's window (top-level tool calls only), reported per round with its peak context and per kind and model. `review.sh` launches through `route.py run --kind review`; to force an effort (say `max` for a risk area the router missed) pass `--override "effort=max,reason=.."`. A review whose final model is in the author's family is refused (exit 2, a `refuse` line in `routes.jsonl`), whether picked, overridden or reused (a reused decision is checked against the author saved with it when none is given now), and so is a review whose author is unknown from `--author-model`, the author round's log and the saved decision; only the fallback after a 422 passes, with `same_family=yes` in the override, and the audit shows it as overridden with that flag. `mine.py --audit` joins each round to the `routes.jsonl` decisions by item and kind (a decision matches a round only with the same item and kind, and with the round's own name when the decision names a round such as `a-fix2`; one under the round's own name is preferred, else the latest logged no later than 2 minutes after the round started; each decision is used by one round at most) and lists every round as routed, overridden (the decision carries an `override` field, whose model and effort are then the expected ones) or unrouted, flags every round whose model or effort in its own log differs from its decision, and lists decisions no round used. `status.py` shows the unrouted count in its header.

Owner's ruling, 2026-10-30, on the effort and context research (`research/2026-10-30-router-effort-context.md` in the dotfiles repository): D1 to D5 as recommended (D1 a graded reward per round; D5 the launcher plus the audit). Build phases 1 to 3 now (truthful outcomes, the audit, the launcher); phases 4 to 6 (graded reward, effort arms, propensities and pacing) after about two runs of clean data.

## Rules

- **Never the automatic model choice** (`auto`), for workers or reviewers. Always pass `--model` and `--reasoning-effort`, so spend and quality can be compared round by round.
- **Name each round by its kind.** `mine.py` reads the kind from the run name's suffix; a round with the wrong suffix is costed and capped as the wrong kind.
- **Keep warm.** The provider drops a session's cached context after 300 idle seconds, and the next call pays for the whole context again. Every worker polls at most every 240 s while a command runs (`initial_wait` and `read_bash` `delay` at 240 or less); the worker preamble carries the rule.

## Risk areas

A diff that touches any of these gets a max-effort review, and its builds and merges never get a cheaper model or a lower effort:

- credentials, tokens or sign-in;
- outside systems, especially any write to them;
- privacy: what is masked, shown, stored, logged or sent to a model;
- durable data: schema, migrations, backups, deletion, git writes;
- starting, signalling or killing processes;
- trust boundaries: host, origin and session checks, HTML sandboxing, path handling, subprocess arguments;
- the checks themselves: test harness, mutation controls, gate scripts;
- anything published to a public repository;
- shared foundations many features depend on.

## Credit caps

No round gets a credit cap it can see (owner, 2026-11-02): with `--max-ai-credits`, Opus rounds read the limit and rationed (three research rounds stopped on purpose at 130 to 142 of 1,200 and skipped their survey; uncapped, three did the whole task for 756, 666 and 1,155). Instead `route.py run` reads the session's own usage records every 30 s and ends the round when it passes its stop, about 3 times its estimate ([details](details.md#launch-flags)); the owner hears of every stop. Research rounds (`uncapped_kinds` in `routes.json`) get a stop only when history has an estimate for their kind and model; otherwise their time limit is their stop.

The stop is 3 x the rolling median credits of rounds of the same kind and model over the last 20 such rounds, or a fixed floor while there are fewer than 5. `python3 scripts/mine.py "$OW_RUN_DIR" --caps` prints each cap with the median and the number of rounds it came from; a kind and model it does not list uses the floor line. `--history <run> ...` adds earlier runs' rounds to the window, so a new run starts from measured caps. A kind with fewer than 5 rounds on a model but 5 or more on another gets the other model's cap times the ratio of the two models' prices over the measured token mix, labelled "derived from <model> by price". Prices are in `scripts/prices.json` (or `<run>/prices.json`, `--prices`); refresh from the SDK's `listModels()` `billing.tokenPrices`. `mine.py` also reports per kind and model the calls, tokens and credits by class, wall minutes, effort and calls after a wait over 300 s, and how many rounds would have hit 2 x, 3 x, 4 x the median and P90 x 1.2 (evidence for the factor). `--chat <debug-log-dir> --budget N` prices the orchestrator chat (uncached input as cache writes, an upper bound) and prints spend against N and how many more rounds of each kind and model fit at their medians.

- **A round that hit its cap** reads CAPPED ([details](details.md#failure-modes-and-recoveries)). Read its last calls:
  - **extend it if it was progressing:** resume it as `<item>-resumeN` with a raised cap, usually the same cap again on top of what it used;
  - **narrow it if it was looping,** as with time budgets: resume it with a narrower brief and the normal cap.
- **Resumed rounds** (`-r`). The cap counts only the resumed round, not the conversation's earlier credits (VERIFIED 2026-10-27, one observation: a build used 530.96 of a 700 cap; its resumed fix round, capped at 700 again, printed `Session limits: 350.42/700` while the session's total reached 959.6). Pass the round's own cap, and track the session's total yourself. A round far below its cap prints no `Session limits` line, fresh or resumed ([lessons](lessons.md)).

## Learning loop

At the end of each day:

1. Run `python3 scripts/mine.py "$OW_RUN_DIR" --repo <repo>`. Compare today with the previous day in its `by day` section, then look at credits per round by kind and model, CAPPED rounds, and each item's fix rounds, blocking findings and merge. `--since <date>` narrows every section to recent rounds.
2. Adjust routing and caps only where the data supports it, inside the rulings above.
3. Record each change at once with `python3 scripts/state.py marker "<what changed>" --scope all|workers|reviews|merges`. Markers go to `<run>/markers.jsonl`, outside `orchestrator.json`.
4. Report the saving by marker from the `markers` section of `mine.py`: the median credits per round before and after each marker, for each kind it covers, up to the neighbouring markers.
