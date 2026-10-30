# Router: effort, context size, same-price choices, learning and enforcement

Spike for the orchestrator-workers router (`route.py`), 2026-10-30, building on [the 2026-10-29 spike](2026-10-29-router-levers.md). Each claim is VERIFIED (read through `tvly extract`, run, or read at path:line), INFERRED or OPEN. "Our data" means the run folders `~/.local/state/orchestrator-workers/amc-2026-10-27` to `-30`: 202 worker rounds, 201 ended. Charts: [docs/design/router-effort-context.html](../docs/design/router-effort-context.html).

## In short

- **Q1 Effort.** All four models accept low to max; Opus, Haiku and gpt default to medium, Sonnet to high, though its vendor says medium for well-specified agentic coding. Reasoning was 57–74% of output at high and 26% at medium here. Raise effort for ambiguity, weak verification and risk; otherwise keep the default.
- **Q2 Context.** `long_context` gives 936k (Sonnet), 1M (Opus) and 922k (gpt) at the same Claude price; gpt doubles input above 272k; Haiku costs 5×. Claude rounds compacted silently 49 times; gpt never did. Avoiding that would have cost about 142 more credits per compacted round.
- **Q3 Same price.** No. Tokens per task differ 2–6× at one price. Choose by expected credits per success plus a minutes term; take the stronger option only within noise.
- **Q4 Learning.** Keep the Thompson core. Copy, in standard library: propensity logging, shrinkage, a graded reward, LinConTS's constrained choice, PILOT's pacing, and a version reset. Trained routers need thousands of labelled runs.
- **Q5 Our data.** The router has never seen a blocking finding (verdicts are never written where `mine.py` looks), and fix rounds fail by construction. 18 decisions for 201 rounds, 3 overridden unlogged. Cost and time comparisons hold; quality ones do not.
- **Q6 Enforcement.** Orchestrator-workers owns routing; estimating-work only requires the queue. Recommended: a `route.py run` launcher with a logged `--override`, a guard in `runqueue.py add`, and an audit in `mine.py`.
- **Q7 Also.** Detect silent compaction; log the CLI version; avoid max on reviews (all 4 errors); the reviewer is a noisy judge; time of day is OPEN.

## Q1 Effort

Facts:

- VERIFIED: the SDK's `listModels()` (`@github/copilot-sdk` 1.0.23, CLI 1.0.100) lists `supportedReasoningEfforts` as low, medium, high, xhigh and max for all four pool models, and no `defaultReasoningEffort` for any of them. Raw output: `.gates/sdk/list-models.json` (kept out of git). `copilot --help` (1.0.105) also accepts `none` and `minimal`.
- VERIFIED, https://platform.claude.com/docs/en/build-with-claude/effort:
  - Opus 5.5 and Haiku 5.5 default to medium, others to high.
  - Lower effort makes "fewer tool calls" and proceeds "directly to action without preamble"; higher effort may "explain the plan" and add "more comprehensive code comments".
  - Opus 5.5: "effort is the primary control"; "run an effort sweep on your own evals".
  - Sonnet 5.5: levels "are recalibrated"; for agentic coding "start with `medium` for well-specified tasks and move to `high` for harder or longer ones"; xhigh and max "only where your evals show a quality gain".
  - Haiku 5.5 at low is "more likely to skip a search, stop early, or skip a check".
  - Opus 4.7's table: `max` "can lead to overthinking"; `xhigh` suits agentic tasks "over 30 minutes".
  - "Consider dynamic effort: adjust effort based on task complexity."
- VERIFIED, https://developers.openai.com/api/docs/guides/reasoning:
  - GPT-6.1 Sol "defaults to `medium`".
  - For high, "evaluate both `medium` and `high`"; xhigh "only when your evals show a clear benefit", listing "security and code review".
  - "Treat `reasoning.effort` as a tuning knob, not the primary way to recover quality."
- VERIFIED, https://www.anthropic.com/claude-opus-5-5:
  - At "default effort (medium)", Opus 5.5 scores 52.5% on CursorBench against 46.6% for Opus 5 at max, and on Terminal-Bench 4.0 it "beats Opus 5 at max effort for about a fifth of the cost".
  - A tester: "even at its lowest effort setting" it caught 72% of known review bugs, against Opus 5's 56% at high.
- VERIFIED, https://www.anthropic.com/news/claude-opus-4-5: "at a medium effort level, Opus 4.5 matches Sonnet 4.5's best score on SWE-bench Verified, but uses 76% fewer output tokens".
- VERIFIED, https://www.anthropic.com/research/april-23-postmortem: Anthropic set Claude Code's default to medium because medium "achieved slightly lower intelligence with significantly less latency". Users felt the loss, and Anthropic reverted to high.
- VERIFIED, overthinking and test-time compute:
  - Longer reasoning "actively degrades performance on simple tasks" (https://arxiv.org/html/2507.14417).
  - The best test-time strategy "heavily correlates with the difficulty of the problem", and adapting it per prompt is 2–4× more efficient (https://arxiv.org/html/2408.03314).
  - Budget forcing's gains "flatten out", and forcing more "can lead the model into repetitive loops" (https://arxiv.org/html/2501.19393).
- VERIFIED, our data (`.gates/analyze7.py`, `.gates/cells.json`):

| Cell (kind, model, effort) | Rounds | Median credits | Median wall min | Output tokens/round | Reasoning share of output | Tool calls/round |
|---|---|---|---|---|---|---|
| fix, Sonnet, medium | 11 | 32 | 6 | 9.8k | 26% | 21 |
| fix, Sonnet, high | 21 | 72 | 11 | 39k | 57% | 43 |
| fix, Opus, high | 37 | 200 | 20 | 51k | 65% | 39 |
| build, Sonnet, medium | 5 | 89 | 7 | 23k | 26% | 36 |
| build, Sonnet, high | 13 | 125 | 13 | 80k | 67% | 54 |
| build, Opus, high | 34 | 388 | 29 | 128k | 74% | 78 |
| review, gpt-6.1-sol, medium | 5 | 49 | 3 | 10.6k | 53% | 21 |
| review, gpt-6.1-sol, high | 15 | 56 | 5 | 14.6k | 65% | 14 |
| review, gpt-6.1-sol, max | 13 | 72 | 7 | 27.9k | 73% | 21 |

- VERIFIED: `review.sh` passes no `--reasoning-effort` (`dotfiles/dot_agents/skills/orchestrator-workers/scripts/review.sh:63`). Five of the six review.sh rounds on 10-27 ran at medium. INFERRED: an omitted effort falls back to the model default, which breaks the "always pass effort" rule (`references/routing.md:41`).
- OPEN: no published quality-against-effort curve for Sonnet 5.5 or gpt-6.1-sol on coding tasks. The vendors publish single points, and each tells you to sweep on your own evals.

INFERRED, how effort should depend on the task:

- **Difficulty.** Effort pays on hard items and hurts on easy ones.
- **Ambiguity.** Higher effort plans and weighs options before acting; with one obvious path that is waste.
- **Verifiability.** Where a check will catch a miss, medium plus the check beats high without one, because a Sonnet medium fix costs 32 credits. Where nothing verifies the work (reviews, research, risk areas), pay for effort.
- **Risk.** Keep the floors.

So: start at the vendor default (medium), step up on grades, use xhigh only for long builds with evidence, and max only for risk-area reviews. Learn every cell with two arms.

## Q2 Context size

Facts:

- VERIFIED: `copilot --help`: `--context <tier>` is `default` or `long_context` and "overrides persisted setting". The SDK type comment says `long_context` "pins the session to the long-context tier when the selected model supports it" (`~/sandbox/personal/agent-mission-control/node_modules/@github/copilot-sdk/dist/types.d.ts`, ContextTier).
- VERIFIED, `listModels()` `billing.tokenPrices` (AI credits per 1M tokens; 1 credit = $0.01 per https://docs.github.com/copilot/reference/copilot-billing/models-and-pricing):

| Model | Default window | Default in/out/cache read/cache write | Long window | Long in/out/cache read/cache write |
|---|---|---|---|---|
| claude-haiku-5.5 | 100k | 10 / 50 / 1 / 12.5 | 936k | 50 / 250 / 5 / 62.5 (5×) |
| claude-sonnet-5.5 | 200k | 200 / 1000 / 10 / 250 | 936k | same |
| claude-opus-5.5 | 200k | 400 / 2000 / 20 / 500 | 1M | same |
| gpt-6.1-sol | 272k | 200 / 1000 / 10 / 250 | 922k | 400 / 1500 / 20 / 500 |

- VERIFIED: the GitHub pricing page agrees for gpt-6.1-sol and gives its long-context tier a "Threshold (input tokens) > 272K". It lists no long-context tier for Anthropic models and no Haiku 5.5 row. It lists Sonnet 5.5 cached input at $0.20 where the SDK says 10 credits ($0.10). OPEN: which one bills; `prices.json` follows the SDK.
- VERIFIED, https://docs.github.com/en/copilot/reference/ai-models/supported-models: "we recommend that you use the regular context window and regular reasoning by default, selecting the larger context window and higher reasoning for more complex tasks only."
- VERIFIED, https://docs.github.com/en/copilot/concepts/prompting-and-context/context-management:
  - At "approximately 80%" of the window the CLI compacts in the background, and at "approximately 95%" it waits.
  - Compaction replaces history with a summary, and "fine-grained details ... may not be included".
  - Tool output over 20 KiB goes to a file; the SDK type says 51,200 bytes (OPEN which applies).
- VERIFIED, our data (`.gates/analyze5.py`, `.gates/analyze6.py`, `.gates/analyze8.py`):
  - The default windows in the logs are 200,000 for Claude and 272,000 for gpt.
  - The `-p` logs hold no `session.compaction_*` events. A drop to under 60% of the context, from 75% or more of the window between consecutive tool calls, marks one: 49 such drops in 36 rounds, at 80–88% of the window.
  - Those were 33 of 72 Opus build and fix rounds, 3 of 57 Sonnet rounds and 0 of 68 gpt rounds.
  - Compacted rounds cost double the median credits and minutes; 1 of 18 reviewed ones had a clean next review, against 13 of 46 others. Long tasks compact, so this is confounded.
  - Without compaction, the median peak would have been 219k (maximum 453k), and the extra cache reads a median 142 credits per round, 6,772 in total: an upper bound, since tool calls outnumber model calls.
- VERIFIED: degradation with length:
  - NoLiMa: "at 32K ... 11 models drop below 50% of their strong short-length baselines" (https://arxiv.org/html/2502.05167).
  - Chroma's context rot and Lost in the Middle: 2026-10-29 spike.
- VERIFIED, prompt cache:
  - Anthropic's default cache lifetime is "5 minutes ... refreshed each time the cached content is used", measured "from the start of the request", and a 1-hour write costs 2× base input (https://platform.claude.com/docs/en/build-with-claude/prompt-caching).
  - OpenAI's cache lifetime is "at least 30 minutes after the latest write or reuse", and cache reads on GPT-6.1 Sol cost 0.05× input (https://developers.openai.com/api/docs/guides/prompt-caching).
  - Changing top-level effort mid-conversation invalidates Anthropic's cache (effort doc, best practice 5).
- VERIFIED: across all rounds, credits split 47% output, 26% cache read, 26% cache write and 1% uncached input. In gpt review and rereview rounds, cache writes were 46–64% of credits.

INFERRED:

- **A larger window helps** only when the work must stay in one session and would otherwise compact: long builds over many large files, long logs, whole-repository audits.
- **It hurts** in three ways:
  - Every later call carries the extra tokens, which on Claude shows up as cache reads.
  - Accuracy falls with length.
  - On gpt, input above 272k costs double.
- **Cheaper levers come first:** split the item, start a fresh session per phase, and keep briefs short.
- **A resumed fix round (`-r`) is cheap on Claude only within 5 minutes**, while the cache is warm. The 31 cold calls in Opus fix rounds show the cost.

## Q3 The same-price question

Facts:

- VERIFIED: Sonnet 5.5 and gpt-6.1-sol have the same default-tier prices; Opus 5.5 is 2× both (table above). Claude's long tier has the same per-token price as its default; effort has no price of its own.
- VERIFIED, our tokens per round at one price:
  - Sonnet fix at high used 4× the output of Sonnet at medium and 2.3× the credits.
  - gpt-6.1-sol fix at medium (3 rounds) cost 33 credits, against 32 for Sonnet medium, with 30% less output and 13 calls against 21.
  - gpt review at max cost 1.3× the credits of high, and the 4 session errors all came at max.
- VERIFIED: the vendors tell you to sweep effort on your own evals and to use xhigh or max only where evals show a gain. GitHub recommends the regular window and reasoning by default (Q1, Q2).
- VERIFIED: the RouterArena paper reports that routers are "inefficient at leveraging cheaper models when appropriate", per the Q4 survey's read of https://arxiv.org/html/2510.00202v1.
- VERIFIED: a review never goes to the author's family (`references/routing.md:27`). The family is read only from `--author-model` (`scripts/route.py:449`), and the logged canvas-b-rereview2 decision lacked it and picked Opus for an Opus build.
- OPEN: rate limits and availability per model in Copilot. I found no per-model limit table and did not test one.

INFERRED: "always take the stronger at the same price" is wrong for five reasons:

1. Price per token is not price per task: stronger settings spend 2–6× the tokens, with wider variance (Opus build high P90 830 credits, median 388).
2. Time: Sonnet fix took 6 minutes at medium and 11 at high; in an unattended window, minutes bind.
3. Overthinking costs quality on easy, checkable work (Q1).
4. Behaviour differs: gpt is terser; Claude at high explains and calls more tools. A gpt builder also moves reviews to Claude.
5. "Stronger" is unmeasured: no benchmark covers both Sonnet 5.5 and gpt-6.1-sol on our work.

INFERRED, decision rule for the router:

- For each candidate arm (model, effort, context), compute expected cost per success: E[credits] / P(success), plus λ × E[minutes].
  - E[credits] and E[minutes] are the cell medians, shrunk toward the kind's medians.
  - P(success) is the sampled posterior.
- Take the cheapest arm by that measure.
- When two arms' costs per success are within one standard error, take the stronger, which is quality first in the owner's sense. Same price per token never decides by itself.
- Hard constraints first: floors, the cross-family rule (read the author's model from the round's log when `--author-model` is missing), and a context tier only on signals.

## Q4 Learning

A worker surveyed 15 lines of work through `tvly extract`. I spot-checked three of its quotes against the pages, and they matched.

| Method (source) | Data it needs | Fits ~200 rounds? | Design or library | What to copy |
|---|---|---|---|---|
| RouteLLM (arxiv.org/html/2406.18665) | 80k preference battles | No; "high capacity approaches performing worse in a low-data regime" | Trained | One threshold as the cost-quality knob, which the target already is |
| FrugalGPT, cascades (arxiv.org/html/2305.05176) | Labelled pairs for a scorer | Cascade yes, scorer no | Trained scorer | Escalate on a failed check: fix rounds already do |
| AutoMix (arxiv.org/html/2310.12963) | ~50 labelled examples per task family | Partly | POMDP design | Treat the verdict as a noisy signal |
| Hybrid LLM (arxiv.org/html/2404.14618) | 10k queries × 10 samples | No | Trained | Soft labels, i.e. a graded reward |
| LLM Bandit (arxiv.org/html/2502.02743) | Benchmarks; 20–50 "quiz" prompts per new model | Quiz idea only | Trained PPO policy | Seed a new model's prior with a fixed quiz of past briefs |
| MixLLM (arxiv.org/html/2502.18482) | Router-scale logs and embeddings | No | Trained | Additive score: trade-off + uncertainty − latency |
| PILOT (arxiv.org/html/2508.21141) | Preference prior + online feedback | Budget rule yes | Design | Eligibility threshold that tightens as the spent fraction rises |
| RouterBench, RouterEval, RouterArena, kNN study | 405k–200M records | n/a | Benchmarks | "None of the routing algorithms significantly outperform the baseline Zero router"; compare against a fixed mix |
| Bandits with knapsacks, budgeted TS, LinConTS (proceedings.mlr.press/v108/saxena20a) | Online outcomes | Yes | Design | Sample means, then take the cheapest mix of at most two arms that meets the target |
| Discounted TS, sliding window, CUSUM | Online; CUSUM ~100 per arm | Discount yes, CUSUM no | Design | γ ≈ 0.98–0.99, and a reset on a known version change |
| Hierarchical / empirical-Bayes Beta (arxiv.org/html/2111.06929) | Counts per cell | Yes | Design | Cell prior = parent posterior with pseudo-count 2–4, replacing the "<3 rounds" switch |
| Graded reward (arxiv.org/pdf/1111.1797) | Reward in [0,1] | Yes | Design | Fractional Beta update with r |
| Off-policy evaluation (arxiv.org/html/2008.07146v5, arxiv.org/pdf/1606.03966) | (context, action, propensity, reward) | Later | Design; OBP and VW are libraries | Log the final action's propensity, computed by Monte Carlo over the whole rule |
| Exploration cost (arxiv.org/html/1803.02855v2) | Online | Yes | Design | Satisficing TS; a 3–5% propensity floor among near-ties |
| ARES, Route-to-Reason, BEST-Route, Self-Route | Full grids or labelled trajectories | No | Trained | Joint (model, effort) arms; label the lowest effort that succeeded; context on evidence only |

Facts I relied on:

- VERIFIED: Decision Service names "business logic [that] override[s] the chosen action" as a common error that makes "the recorded probability incorrect" (https://arxiv.org/pdf/1606.03966). `route.py` logs scores, samples and seed but no propensity (`scripts/route.py:433`). Its quality-first rule is such an override; the ignored owner overrides below are another.
- VERIFIED: RouterBench: "none of the routing algorithms significantly outperform the baseline Zero router". Cascades degrade fast when the judge's error passes 0.2 (https://arxiv.org/html/2403.12031).

INFERRED:

- **Copy LinConTS** inside the Thompson loop. It has a guarantee for "cheapest subject to success ≥ target", and it randomises between at most two arms, which yields exact propensities.
- **Shrinkage and a graded reward** fix the cold start.
- **A discount plus a version reset** handles model updates.
- **Exploring downward is cheap:** an unneeded Opus build costs a median 388 credits, while the fix round a cheaper choice might need costs 32.

## Q5 Our own data

How I derived each part of success (VERIFIED, `.gates/analyze2.py`):

- **Not capped and exit 0:** read from mine.py.
- **Blocking findings:** mine.py reads them only from `<name>.txt` (`scripts/mine.py:20,88-100,224`). No run wrote those files, so all 65 reviews read "missing". I parsed each review's last `assistant.message` instead: 56 by pattern and 9 by hand, recording counts only.
- **Fix rounds per item:** counted from names.
- **Three success measures:**
  - `ok_doc` is routing.md's item-level definition: no blocking at first review and at most one fix round.
  - `ok_code` is what `round_ok` computes with `blocking` always None (`scripts/route.py:204`).
  - `ok_round` is not capped, exit 0, and the item's next review clean or absent.
- **Research items** are labelled kind build by name; I relabelled them by their `research` prefix.

| Cell | Rounds | ok_doc | ok_code | ok_round | Median / P90 credits | Median wall min | Peak context (median) |
|---|---|---|---|---|---|---|---|
| build Opus high | 34 | 17 | 25 | 18 | 388 / 830 | 29 | 162k |
| build Sonnet high | 13 | 4 | 7 | 5 | 125 / 217 | 13 | 124k |
| build Sonnet medium | 5 | 3 | 4 | 3 | 89 / 91 | 7 | 89k |
| fix Opus high | 37 | 6 | 14 | 23 | 200 / 409 | 20 | 147k |
| fix Sonnet high | 21 | 2 | 4 | 12 | 72 / 138 | 11 | – |
| fix Sonnet medium | 11 | 3 | 4 | 10 | 32 / 61 | 6 | – |
| fix gpt-6.1-sol medium | 3 | 2 | – | 3 | 33 / – | 2 | – |
| review gpt high / max / medium | 15 / 13 / 5 | all ok | | | 56 / 72 / 49 | 5 / 7 / 3 | – |
| rereview gpt high / max | 21 / 10 | 21 / 6 | | | 36 / 57 | 2 / 6 | – |
| research Sonnet high | 3 | 3 | | | 78 | 5 | – |
| catchup, resume, other | 1–4 each | | | | | | |

VERIFIED, other counts:

- **Kinds:** fix 73, build 57 (including 4 research), review 33, rereview 32, catchup 4, resume 3.
- **Fix rounds per build item (56 items):** 0 for 18 items, 1 for 22, 2 for 8, 3 for 7, 4 for 1.
- **Reviews:** 28 items were reviewed, and 26 of them had blocking findings at the first review. 16 items had fix rounds but no review round.
- **Effort mix of worker rounds by run:**
  - 10-27: 25 high, 3 medium.
  - 10-28: 29 high.
  - 10-29: 18 high, 14 medium.
  - 10-30: 42 high, 5 medium.
- **Tokens by class:** 47% of credits went to output.

VERIFIED, the 18 decisions in `amc-2026-10-29/routes.jsonl`:

- They cover 16 rounds; two items were picked twice. One of those first picks used a floor that `routes.json` no longer has.
- 13 ran as chosen. 3 were overridden with no record:
  - Opus became Sonnet on a fix.
  - high became max on a rereview.
  - Opus max became gpt max on a review, because the router lacked `--author-model` and would have broken the family rule.
- Every pick was high, plus one max; the effort arms held only "high", because the rule said high (`scripts/route.py:385-388`).
- No context signal fired.
- Quality first was off in the later 9 decisions, because spend ran ahead of time.
- 11 of 18 differed from the static table, mostly fix rounds sent to Opus high where the table says Sonnet medium.
- By `ok_round`, 9 of the 14 build and fix rounds succeeded and 5 failed. Of the 2 rereviews, one returned a verdict and one was flagged as an error.

What the data can and cannot support:

- **Can (VERIFIED):** cost, minutes, tokens, calls and compaction by cell; that medium halves or quarters tokens; that Opus costs 2–3× Sonnet per round.
- **Cannot (INFERRED):** quality comparisons. Harder items went to Opus, briefs differ, 10-30 was routed by hand, the reviewer blocks almost everything, cells hold 1–37 rounds, `ok_doc` fails every fix round by construction, and `ok_code` ignores reviews.

## Q6 Enforcement

Facts:

- VERIFIED: orchestrator-workers owns routing.
  - "`route.py pick` chooses them per round and logs why" (`dotfiles/dot_agents/skills/orchestrator-workers/SKILL.md:159`).
  - Its launch recipe takes `--model <model> --reasoning-effort <effort>` (SKILL.md:142).
  - Routing.md says "Never the automatic model choice" (`references/routing.md:41`).
- VERIFIED: estimating-work only says unattended runs go to `copilot -p` workers "through the orchestrator-workers skill and its queue runner" (`dotfiles/dot_agents/skills/estimating-work/SKILL.md:116-117`). Its run guard is a Stop hook that blocks ending a turn. It has no routing.
- VERIFIED, bypass in `~/.local/state/orchestrator-workers/amc-2026-10-30/run1030/`: `launch.zsh`, `launch-direct.zsh`, `fix.zsh`, `fix-research.zsh` and `review2.zsh` take `MODEL` and `EFFORT` from the environment with fixed defaults (Opus high, Sonnet medium, gpt high) and never call `route.py`. 82 rounds ran with 0 decisions logged; 42 of 47 worker rounds ran high through environment overrides no log records.
- VERIFIED, choke points, none of which checks routing today: `brief.py check` (placeholders, REUSE CHECK, ALLOWED DEPENDENCIES); `runqueue.py add --cmd`, which runs any shell command (`scripts/runqueue.py:149,181`); `review.sh`, which sets its own model and no effort; and `mine.py` and `status.py`, which report after the fact.
- VERIFIED: each round's actual model and effort are in its log (`user.message` `responsesReasoning`, read by mine.py), so an audit can compare them with routes.jsonl.
- VERIFIED, https://docs.github.com/en/copilot/reference/hooks-reference:
  - A `preToolUse` hook gets `toolName` and `toolArgs` and can return `permissionDecision` "deny" with a reason.
  - User-level hooks live in `~/.copilot/hooks/*.json`.
  - `sessionStart` can only add context, not block.

Options (INFERRED):

1. **Audit only.** `mine.py` joins rounds to decisions by name and flags unrouted rounds, mismatches and overrides; `status.py` shows the count. It catches a bypass only after the spend.
2. **One launcher.** `route.py run <item> <kind> --brief F [--override model=..,effort=..,reason=..]`:
   - checks the brief, picks or logs the override with the owner's reason, and execs copilot with exactly the logged values;
   - `runqueue.py add` refuses a `copilot` command that does not go through it, unless the command carries a logged `--unrouted-reason`;
   - `review.sh` calls it.
3. **Hook.** A user-level `preToolUse` hook denies `copilot -p` commands that skip `route.py run`. It cannot see inside a script such as `launch.zsh`, and it fires in every session.

Recommended: 2 + 1. The launcher makes the routed path the easy one and logs the owner's overrides; the audit catches scripts that bypass both. Add the hook only if the audit shows a bypass after that.

Tests that prove it:

- `test_route.py`: `run --stub` launches a fake `copilot` on `PATH` whose argv matches the logged decision; `--override` logs its reason; a missing author model is read from the round log.
- `test_runqueue.py`: `add` refuses a bare `copilot -p`.
- `test_mine.py`: a fixture with one routed, one overridden and one unrouted round reports one of each; a model or effort mismatch is flagged; the 10-30 folder reports 82 unrouted.

## Q7 Other things that matter

1. **Silent compaction (VERIFIED).** 49 compactions and no log event. Log them from the context drop, use an earlier compaction as a context signal, and count it as cost.
2. **Harness changes (VERIFIED).** Anthropic's quality drop came from a default effort, pruned thinking and one system-prompt line, while "the API was not impacted". Our logs record no CLI version. Log the CLI version and model id with each decision, and reset an arm when either changes, re-seeding it with a fixed quiz of about 20 past briefs.
3. **Max effort is fragile (VERIFIED).** All 4 session errors were gpt max rereviews, 2 with no message.
4. **The judge is noisy (VERIFIED counts, INFERRED meaning).** 26 of 28 first reviews blocked, and RouterBench finds cascades collapse above a 0.2 judge error. A finding that its fix round left unchanged is likely a false alarm.
5. **Time of day (OPEN).** Opus wall minutes per 1,000 output tokens ranged 0.23–0.45 across 4-hour blocks of 1–31 rounds: too thin to read.

## Decisions for the owner

Ruled 2026-10-30 (owner: "go with recommendations"): D1 option 2, D2 option 2, D3 option 1, D4 option 2, D5 option 2. Build phases 1 to 3 now; phases 4 to 6 after about two runs of clean outcome data.

**D1. What counts as success.** It binds `mine.py` verdict reading, `round_ok`, `report` and every learned arm.

1. Keep routing.md's binary item-level definition; only make the reviewer write `<name>.txt`.
2. A per-round graded reward in [0,1], attributed to the round:
   - 1 if the next review is clean or there is none and the gates pass;
   - 0.5 if the next review has only non-blocking findings or the round needs one fix;
   - 0 if capped, exit ≠ 0, or blocking.

   Credits and minutes stay in the decision rule. mine.py also parses the verdict from the review's last message.
3. Item-level graded reward shared by all of the item's rounds.

Recommended: 2. Option 1 fails every fix round, and option 3 cannot tell the builder from the fixer.

**D2. Effort arms.** It binds `routes.json` `learning`, the floors and the reviewer launch.

1. Keep medium and high, and fix the single-arm case.
2. Two adjacent arms always, on a low-to-xhigh ladder centred on the vendor default for the model, stepped by grades; max only for risk-area reviews; label each success with the lowest effort that worked.
3. A fixed effort per kind and model, with no learning.

Recommended: 2. It is the vendors' "sweep on your evals" done online, at no extra round cost.

**D3. Context tier.** It binds `context` in `routes.json` and the brief rules.

1. Keep the signal rule (two or more signals) and add "an earlier round of this item compacted" as a signal; learn default against long_context.
2. Always default; split an item instead of widening.
3. long_context for every Claude build round, since its per-token price is the same.

Recommended: 1. Compaction is real (33 of 72 Opus worker rounds); option 3 carries about 142 more credits per compacted round.

**D4. The same-price rule.** It binds `choose` and quality first.

1. Always the stronger at equal per-token price.
2. Cheapest expected credits per success plus a minutes term; the stronger only when within one standard error.
3. Price-blind: always the cheapest arm that clears the target.

Recommended: 2. It keeps quality first only where the data cannot tell the arms apart.

**D5. Enforcement.** It binds SKILL.md's launch recipe, `runqueue.py`, `review.sh` and `mine.py`.

1. Audit only.
2. The launcher plus the audit.
3. The launcher, the audit and a `preToolUse` hook.

Recommended: 2. It covers every path the 10-30 run took; the hook adds friction everywhere and misses wrapper scripts.

## Build plan

Each phase fits one worker session, standard library only, with tests in the skill's `scripts/test_*.py`.

1. **Truthful outcomes.** `mine.py` parses the verdict from the review's last `assistant.message` when `<name>.txt` is missing, and records compactions and propensity; `review.sh` writes `<name>.txt` and passes `--reasoning-effort`.

   Tests: fixture logs with "Blocking: none", "2 blocking" and no verdict; a context drop reads as one compaction; the 10-29 folder reports non-None blocking for every reviewed item.
2. **Audit.** `mine.py --audit` joins rounds to routes.jsonl and flags unrouted rounds and mismatches; `status.py` shows the count.

   Tests: as in Q6.
3. **Launcher and override.** `route.py run` with `--override`; the author model read from the round log; the CLI version and model id logged; `runqueue.py add` refuses bare copilot commands; SKILL.md's recipe uses the launcher.

   Tests: as in Q6.
4. **Learning core.**
   - The graded reward (D1).
   - Hierarchical shrinkage replaces the "<3 rounds" widening.
   - Two effort arms always (D2).
   - Monte Carlo propensity logged per decision.
   - A version-change reset.

   Tests:
   - With a seeded RNG, a cell with 5 clean medium outcomes picks medium more often than one with none.
   - Propensities over a decision's arms sum to 1.
   - A changed version string resets the arm to its prior.
   - Rerunning the 18 logged 10-29 decisions with `--stub` reproduces their model where no override applied.
5. **Constrained choice and pacing.** LinConTS's two-arm mix replaces the quality-first override (D4), and PILOT's spend-fraction threshold replaces the target cut.

   Tests: the mix meets the target on sampled means in a synthetic table, and the cheaper arm gets more weight as spend runs ahead. A replay over the four runs' rounds, against a fixed-mix baseline, reports expected credits per success.
6. **Context learning (D3).** The compaction signal and default against long_context.

   Tests: a brief whose item compacted before offers both arms, and a fresh one offers only default.

Case against: about five outcomes per cell, a strict reviewer and varying briefs mean priors will drive most choices for weeks, and a hand-set table at vendor defaults might do as well. The phase 5 replay would show it; if it shows no gain after 200 more rounds, freeze the learning and keep the audit.
