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
python3 scripts/route.py pick --run "$OW_RUN_DIR" --item <id> --kind build|fix|review|research|small|resume|merge --prompt <brief> [--author-model M] [--diff FILE] [--budget-left F] [--run-fraction F] [--seed N]
python3 scripts/route.py escalate --run "$OW_RUN_DIR" --item <id>
python3 scripts/route.py report --run "$OW_RUN_DIR"
```

`pick` prints `MODEL=... EFFORT=... CONTEXT=... CAP=...` and a `# reason` line; the orchestrator passes `CONTEXT` as `--context`. Steps: one `claude-haiku-5.5` call through `copilot -p` (no tools, no MCP servers, under `timeout`, about 0.3 credits) returns the category and 1 to 5 grades with quotes; any failure falls back to keyword rules and the table. The tier (easy, medium, hard) comes from the grades; the cell is category x tier. Each pool model gets a Beta posterior from past rounds in the cell (widened to the category, then the kind, under 3 rounds), is Thompson-sampled, and the cheapest model whose sample clears the tier's target wins. The target falls as spend (`--budget-left`) runs ahead of time (`--run-fraction`). Floors always win: `src/host/sessions.ts` and risk areas get the strongest model at high (risk-area reviews max); a review is never the author's family; never `auto`. New features have no floor (owner, 2026-10-29: "router decides from grades, history and budget alone (risk floors stay)"); the table's build row is now only the shadow and the fallback. Success means: not capped, exit 0, no blocking review finding, at most one fix round. The cap comes from `mine.py --caps`.

Levers beyond the model (evidence: [research/2026-10-29-router-levers.md](../../../../../research/2026-10-29-router-levers.md)):

- **Quality first** (owner, 2026-10-29: "if a choice has to be made prioritize quality over cost"). For model, effort and context alike, the stronger arm wins when the cheaper one has fewer than `quality.min_cell_rounds` outcomes in its cell, or its mean minus `quality.tie_sd` standard deviations falls below the target. Only spend running ahead of time (`--budget-left` against `--run-fraction`) turns the rule off and lowers the target.
- **Effort** is a learned arm: the old rule (medium when ambiguity and verification are both 2 or lower, else high) picks the prior and the arm one step up. Each arm's Beta adds the kind's other outcomes at weight `learning.kind_share`, so few outcomes still count. Floors and `kind_min_effort` still win.
- **Context** is `default` unless the brief shows `context.min_signals` signals (long logs, the whole repository, large files, many file paths, a very long brief, breadth 5). When it does, `default` and `long_context` are learned the same way, with a prior that favours `default`.
- **Classifier** is a pool (`classifier.pool`). `route.py eval-classifier --run R [--models a,b] [--max-credits N]` grades the logged briefs of R and the two run folders before it with each model. It prints credits per call, agreement with the first model, and how well a hard tier predicts failed or capped rounds. First run, 2026-10-29 (44 credits): 7 briefs, too few to decide, so Haiku stays.
- `report` adds ok and failed tallies by effort and by context. After a capped round or a failed gate, `escalate` returns the next model up the pool at the same effort.

Reading `<run>/routes.jsonl`, one JSON line per decision: `inputs` (including the seed), `classifier` (`source` is `classifier`, `stub` or `fallback`, with `fallback_reason`; each grade with its quote), `cell`, `scores` (per model: alpha, beta, n, `level` the cell was widened to, the `sample`), `target`, `floor`, `choice`, `static` (the table's choice), `differs`, `reason`. `route.py report` prints each decision against the static choice and its round's outcome. Until `routes.jsonl` has logged decisions, history is read by kind only (the category and tier of past rounds are unknown), so the router leans on the kind-level record.

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

Every round runs with `--max-ai-credits <cap>`, where the cap is 3 x the rolling median credits of rounds of the same kind and model over the last 20 such rounds, or a fixed floor while there are fewer than 5. `python3 scripts/mine.py "$OW_RUN_DIR" --caps` prints each cap with the median and the number of rounds it came from; a kind and model it does not list uses the floor line. `--history <run> ...` adds earlier runs' rounds to the window, so a new run starts from measured caps. A kind with fewer than 5 rounds on a model but 5 or more on another gets the other model's cap times the ratio of the two models' prices over the measured token mix, labelled "derived from <model> by price". Prices are in `scripts/prices.json` (or `<run>/prices.json`, `--prices`); refresh from the SDK's `listModels()` `billing.tokenPrices`. `mine.py` also reports per kind and model the calls, tokens and credits by class, wall minutes, effort and calls after a wait over 300 s, and how many rounds would have hit 2 x, 3 x, 4 x the median and P90 x 1.2 (evidence for the factor). `--chat <debug-log-dir> --budget N` prices the orchestrator chat (uncached input as cache writes, an upper bound) and prints spend against N and how many more rounds of each kind and model fit at their medians.

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
