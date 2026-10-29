# Router levers: effort, context tier, router model, learning

Spike for the orchestrator-workers router (`route.py` v2), 2026-10-29. Each claim is VERIFIED (read on the page or in a search excerpt from it), INFERRED or OPEN. Every search and read went through `tvly`.

## R1 Effort

- VERIFIED: Anthropic's effort doc says effort applies to every output token, with or without thinking, and "lower effort also means fewer and terser tool calls". Most models default to high; Opus 5.5 and Haiku 5.5 default to medium; `max` is "absolute maximum capability". https://platform.claude.com/docs/en/build-with-claude/effort
- VERIFIED (search excerpt of the same doc): for Opus 4.7 and 4.8, "start with `xhigh` for coding and agentic use cases ... step down to `medium` or `low` only when you've measured that the lower level holds quality on your evals."
- VERIFIED (search excerpt): for GPT-6, OpenAI says to keep your current effort as the baseline and compare it against one level lower, with `medium` as the balanced starting point. https://developers.openai.com/api/docs/guides/latest-model
- VERIFIED (search excerpt): "The Danger of Overthinking" studied 4,018 agent trajectories and found a significant negative correlation between overthinking and resolution rate, stronger in reasoning models. Picking the solution with less overthinking raised quality and cut cost. https://www.research-collection.ethz.ch , https://www.alphaxiv.org
- VERIFIED (search excerpt): ARES picks an effort level for each step with a small router and uses far fewer tokens. https://arxiv.org/abs/2603.07915
- OPEN: I found no public SWE-bench table by effort level for the models we use.
- INFERRED: effort pays when a task is ambiguous (options to weigh), hard to verify, spans many interacting steps or touches a risk area. It is wasted on a narrow, well-specified edit. The current rule (ambiguity and verification both 2 or lower: medium) matches this, so it becomes the prior, and outcomes move it from there.

## R2 Context tier

- VERIFIED: `copilot --help` offers `--context <tier>`, either `default` or `long_context`.
- VERIFIED (search excerpts): on Anthropic's API, requests over 200K input tokens were billed at premium rates (2x input, 1.5x output) for the 1M window. https://thenewstack.io , https://platform.claude.com/docs/en/about-claude/pricing
- OPEN: what `long_context` costs in Copilot credits, and which window each of our models gets with it. I found no documentation.
- VERIFIED: Chroma's "Context Rot" tested 18 models and found performance degrades as input grows, unevenly, even on simple tasks. https://www.trychroma.com/research/context-rot
- VERIFIED (search excerpt): "Lost in the Middle" found accuracy is highest when the relevant text sits at the start or end of the input and drops for text in the middle. https://direct.mit.edu/tacl
- INFERRED: a bigger window helps only when a round really must hold more (long logs, repository-wide search, many large files) and would otherwise compact its context. Otherwise it costs more and invites context rot. The other context levers are cheaper to try first: a short brief, `--no-custom-instructions`, MCP servers off and fewer `--add-dir` folders.
- Router choice: `default` unless the brief shows at least two signals (long logs, the whole repository, large files, 15 or more file paths, a brief of 20,000 characters or more, breadth graded 5). Then the router learns between `default` and `long_context`, starting from a prior that favours `default`.

## R3 Router model

- VERIFIED: Arch-Router is a 1.5B model that matches queries to user-defined domain and action routes; it does not grade difficulty. https://huggingface.co/katanemo/Arch-Router-1.5B
- VERIFIED: RouteLLM trains small routers on preference data to predict when the strong model of a strong/weak pair would win. https://arxiv.org/abs/2406.18665
- VERIFIED (search excerpt): models are poor at predicting properties of their own output, difficulty included. Even large models reach only 60–70% accuracy against a 50% baseline. https://www.emergentmind.com
- VERIFIED: Copilot's auto model selection combines a system that tracks model health with one that "evaluates task complexity", and offers efficiency, balance and intelligence tiers. https://docs.github.com/en/copilot/concepts/auto-model-selection
- INFERRED: grading difficulty is hard for any model, and the routers that work are trained on outcomes rather than being bigger. Model strength alone does not settle which classifier to use; measure each against our own outcomes with `route.py eval-classifier`. This stays OPEN until the logs hold enough failed rounds.

## R4 Learning

- INFERRED from general bandit knowledge (I read no single source in full): Thompson sampling over a Beta posterior for each arm, with a hierarchical prior that adds the kind's outcomes into each cell at reduced weight, learns from few outcomes without merging the cells. Model and effort are learned as separate arms in each cell rather than as model x effort pairs, because the joint space has too few outcomes. Quality first works as a constraint: the stronger arm wins unless the cheaper one is clearly above the target.
- Reuse: designs only (RouteLLM's threshold on a predicted win rate, ARES's effort choice per task, hierarchical Beta priors). No library runs outside an API's request path.

Case against: the outcome signal (capped, failed gate, blocking finding) is noisy and partly caused by the brief, so a few rounds can teach the router the wrong arm. This would be shown if the effort and context tallies in `route.py report` stay flat as rounds accumulate.
