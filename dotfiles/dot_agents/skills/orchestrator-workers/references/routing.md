# Routing: model, effort and credit cap per round

Owner rulings, 2026-10-13. The orchestrator applies them to every round it launches; changing them is the owner's call, except the cap and routing adjustments the [learning loop](#learning-loop) records as markers.

| Round (run name) | Model | Effort | Escalate when |
| --- | --- | --- | --- |
| Build (`<item>`) | Strongest worker model | high | Medium only for a clearly mechanical build outside every risk area; high when unsure |
| Fix after review (`<item>-fixN`) | Strongest worker model | high | - |
| Resume (`<item>-resumeN`) | The model of the round it resumes | high | - |
| Catch-up merge (`<item>-catchup`, `<item>-mergeN`) | Mid-tier model of the same family | high | Strongest model for 3 or more conflicts, code-level conflicts, or any risk area |
| Review and re-review (`<item>-reviewN`, `<item>-rereviewN`) | Another model family than the author | high | max when the diff touches a risk area |
| Research (`<item>-research`) | Strongest model | high | - |

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

Every round runs with `--max-ai-credits <cap>`, where the cap is 3 x the rolling median credits of rounds of the same kind and model over the last 20 such rounds, or a fixed floor while there are fewer than 5. `python3 scripts/mine.py "$OW_RUN_DIR" --caps` prints each cap with the median and the number of rounds it came from; a kind and model it does not list uses the floor line.

- **A round that hit its cap** reads CAPPED ([details](details.md#failure-modes-and-recoveries)). Read its last calls:
  - **extend it if it was progressing:** resume it as `<item>-resumeN` with a raised cap, usually the same cap again on top of what it used;
  - **narrow it if it was looping,** as with time budgets: resume it with a narrower brief and the normal cap.
- **Resumed rounds** (`-r`). The cap counts across the conversation, so pass the session's credits so far (the AIU of the round it resumes, in `status.py`) plus the cap. ASSUMED, for the owner: whether a resume carries the earlier credits is OPEN; if it does not, this cap is loose but never cuts a round short. A round far below its cap prints no `Session limits` line, fresh or resumed ([lessons](lessons.md)), so silence settles nothing; the probe in follow-ups (g) does.

## Learning loop

At the end of each day:

1. Run `python3 scripts/mine.py "$OW_RUN_DIR" --repo <repo>`. Compare today with the previous day in its `by day` section, then look at credits per round by kind and model, CAPPED rounds, and each item's fix rounds, blocking findings and merge. `--since <date>` narrows every section to recent rounds.
2. Adjust routing and caps only where the data supports it, inside the rulings above.
3. Record each change at once with `python3 scripts/state.py marker "<what changed>" --scope all|workers|reviews|merges`. Markers go to `<run>/markers.jsonl`, outside `orchestrator.json`.
4. Report the saving by marker from the `markers` section of `mine.py`: the median credits per round before and after each marker, for each kind it covers, up to the neighbouring markers.
