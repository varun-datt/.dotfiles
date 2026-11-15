---
name: archive-closeout
description: Distills reusable knowledge and safely archives a completed, abandoned, superseded, or retired project, area, or learning workspace. Use when the user invokes /archive-closeout or explicitly asks to close out and archive a named durable note.
disable-model-invocation: true
---

# Close out and archive durable work

Distill before moving. Prepare a closeout plan, then apply only the parts the user approves.

First pick the repository and read its folders and check command ([PARA workflow settings](../vault-validator/references/workflows.md)).

## Confirm the boundary

Require a named target and one explicit state: completed, abandoned, superseded, or responsibility ended/transferred. Age, inactivity, or empty tasks are evidence to review—not permission to archive.

For an area, confirm the ongoing responsibility truly ended or moved elsewhere. For a learning workspace, confirm the mission is complete or intentionally abandoned.

## Inspect

Read the target plus relevant backlinks, outlinks, owning areas, linked projects/resources, open tasks, Logs, and current-state sections. Identify:

- the outcome and why work stopped;
- unresolved tasks, risks, commitments, and recurring responsibilities;
- reusable decisions and rationale, verified facts, lessons, processes, and references;
- existing canonical notes that should receive each durable item;
- path-based links that an archive move would break.

Do not treat every paragraph as reusable. Preserve transient planning and detailed history in the archived source instead of duplicating them elsewhere.

## Propose before editing

Return one bounded closeout plan:

1. **Closeout state** — target, state, outcome, effective date, and unresolved ambiguity.
2. **Task disposition** — move, cancel, retain as unresolved history, or remove a completed one-off whose completion is recorded. Never silently mark work complete.
3. **Distillation** — found with the `distill` skill: its document mode for one note, its research mode for a folder. Run only its steps 1 to 3 (find the homes, gather candidates, judge and sort) and list here each durable item, its existing or proposed destination, and the minimal patch needed. Prefer an existing area/resource over creating a note. Include how the owning note will retain **exactly one** canonical link to the archived source (see Distillation rules).
4. **Owning state** — at most one current-state patch and one calendar-day Log entry (with timed sub-bullets if needed) per affected area when meaning changed.
5. **Archive move** — proposed path under the archive folder and links requiring repair.
6. **External records** — safe pointers only; classify documents and identifiers before retention.
7. **Validation** — focused link checks and the repository's check command.

Call out facts that need verification. Ask for approval of destinations, task dispositions, state patches, and archive path.

## Distillation rules

- Keep a single canonical statement for each fact.
- Distill conclusions and reusable evidence, not source dumps or chronology already preserved in the archived note.
- Preserve decision rationale when it changes future choices.
- Transfer recurring responsibilities before retiring an area; do not orphan them.
- Keep the archived source as historical evidence with a concise `## Closeout` summary and links to distilled destinations.
- Do not convert abandoned hypotheses or unverified claims into evergreen knowledge.
- **Single archive pointer:** in the owning durable note (usually one area section), keep **exactly one** link/mention of the archived source from the distilled place (e.g. `**Install archive:** [[archived-note]]`). Do not scatter archive links across inventory rows, duplicate summary bullets, caveats, or multiple “history →” lines. Prefer omitting a Log `↪` to the archive once that single durable pointer exists; the Log should point at the owning section instead. Call this out in the closeout plan’s distillation step.

## Apply in safe order

After approval:

1. patch approved destination notes with `distill`'s step 4 (verify, then write) and step 5 for personal or generic items, and bump `updated`; its finish step does not run here, so nothing is removed or committed;
2. apply approved task transfers/cancellations/removals;
3. add or update the source `## Closeout` summary;
4. move the source or workspace to the approved path under the archive folder;
5. repair path-dependent links while preserving valid basename wikilinks;
6. run focused checks and the repository's check command;
7. report completed actions, preserved history, and unresolved decisions.

Do not delete the durable source, rewrite Git history, publish, commit, or push without separate explicit permission.
