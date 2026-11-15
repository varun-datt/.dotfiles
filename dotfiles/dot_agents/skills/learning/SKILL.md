---
name: learning
description: Starts or continues a retrieval-first, Markdown-indexed and selectively multimodal learning workspace in a notes repository's learning folder. Use when the user invokes /learning, asks to learn or be taught a topic over multiple sessions, or wants to continue an existing learning workspace.
disable-model-invocation: true
---

# Learn a topic

This is the shared learning workflow for the notes repositories. It adapts evidence-backed teaching patterns without depending on another teaching plugin or copying third-party prompts. Read [METHODOLOGY.md](METHODOLOGY.md) when choosing pedagogy, scaffolding, or media.

## Workspace

First pick the repository and read its folders ([PARA workflow settings](../vault-validator/references/workflows.md)).

Use one kebab-case workspace at `<topic>/` in the learning folder. Markdown remains the durable index:

- `index.md` — purpose, current focus, and links;
- `mission.md` — concrete outcome, success evidence, constraints, and exclusions;
- `sources.md` — annotated, cited, high-trust sources;
- `learning-record.md` — dated evidence of demonstrated knowledge, misconceptions, and next retrieval targets;
- optional `lessons/*.md` — reusable prose, examples, or exercises;
- optional `artifacts/` — purposeful SVG, PNG, or self-contained HTML linked from `index.md`.

Every created Markdown note must use the repository's required frontmatter. Use `type: note` for the index, mission, learning record, and lessons; use `type: reference` for sources. Do not create asset libraries, reference sites, or one file per session by default.

## Start or continue

1. Read the workspace and relevant notes in the resources folder.
2. If the mission is absent or vague, ask for the practical outcome before creating files.
3. Set one session goal and assess prior knowledge. Choose the least support that fits:
   - **novice** — brief orientation or worked example, self-explanation, then faded practice;
   - **intermediate** — learner attempt followed by progressive hints;
   - **advanced** — unassisted attempt, challenge, and transfer.
4. Prefer retrieval first, but do not demand recall of knowledge the learner has never acquired. If the learner is blank, activate adjacent knowledge, invite a prediction, or show one concise worked example before asking them to explain or complete part of it.
5. Identify one tightly scoped gap in the learner's current ability.
6. Ground instruction in trusted sources. Use Tavily search/extraction/research skills instead of unsupported parametric claims. Keep citations in `sources.md` and near claims that need them.
7. Give the minimum useful support: diagnostic question → conceptual cue → analogy → principle → procedural cue → parallel worked example. Ask what each hint changed before escalating.
8. Give specific feedback on the task, process, or self-checking strategy. Avoid generic praise and do not perform the learner's remaining thinking when a smaller cue is enough.
9. Check near transfer; use far transfer only when the concept is meaningfully portable. After scaffolded practice, include a genuinely unassisted checkpoint before claiming independence.
10. Record learning only when demonstrated. Record corrected misconceptions and future retrieval targets; do not equate material covered with material learned.

## Choose the representation

Use the lightest representation that closes the selected gap:

- prose or a concrete example for verbal/conceptual gaps;
- diagram for structure, sequence, causality, topology, or spatial relationships;
- runnable code for implementation skills;
- self-contained HTML only when manipulating dynamic state materially improves understanding.

Propose non-trivial artifacts before creating them. A visual must complement rather than duplicate the explanation, match the knowledge structure, integrate labels near what they describe, and omit decorative detail. HTML must be local-only, responsive, keyboard accessible, reduced-motion aware, free of analytics/runtime network dependencies, cited, and accompanied by a Markdown summary.

Any separate research artifact must live inside this workspace, the inbox, or a PARA destination chosen by the user—never an ad-hoc research folder at repository root.

## Record compact evidence

For each meaningful checkpoint, capture only:

- `attempt`: unassisted or scaffolded;
- `support`: none, question, hint, worked-example, or visual/interactive artifact;
- `error`: none, conceptual, procedural, strategic, or representational;
- confidence before/after when calibration adds value;
- transfer: not-run, near, or far;
- next retrieval target and date/context.

Reduce scaffolding after repeated successful unassisted evidence; restore one step when the jump was too large. Do not use fixed numeric fading thresholds as proof of mastery.

## Lifecycle

Use `quiz` later for spaced retrieval. Promote only repeatedly useful or missed concepts into the resources folder, `#review`, or `#flashcards`, with approval. When the mission is complete, propose using `archive-closeout` to distill durable outcomes and move the workspace to the archive folder; never delete it silently.

Do not commit, publish, share publicly, or push without separate explicit confirmation.
