---
name: inbox-triage
description: Triages dated capture notes and other items in a notes repository's inbox (the wiki's or the work knowledge repo's) into tasks or the correct PARA destination. Use when the user invokes /inbox-triage or asks to process, file, or empty the inbox.
disable-model-invocation: true
---

# Triage the inbox

Prepare a batch plan before moving or rewriting anything.

## Scope

First pick the repository and read its folders ([PARA workflow settings](../vault-validator/references/workflows.md)).

Process the inbox folder, excluding the read-later queue. Dated `YYYY-MM-DD-capture.md` files are the single quick-capture source. Split and triage their contents item by item rather than filing a whole capture file as one note.

## Classify each item

1. Summarize the intent in one line.
2. Choose the smallest durable form:
   - a next action becomes a checkbox in the relevant daily, project, or area note;
   - a finite outcome with a deadline becomes or joins a project;
   - an ongoing responsibility becomes or joins an area;
   - non-actionable durable knowledge becomes or joins a resource;
   - inactive durable material is proposed for archive;
   - transient or rejected capture may be proposed for deletion.
3. Choose valid `type` and `status`, `context` where the repository defines contexts, tags, kebab-case path, and the relevant MOC.
4. Prefer updating an existing canonical note over creating a duplicate.
5. A `summary:` line from `distill` names a summary note and what changed: patch that note's current-state lines and bump `updated`, or propose the note when it does not exist (what it is, where it stands, key decisions, what comes next, links to the detail). In the personal wiki, work stays in general terms.

For events in an area or project with a Log, append one calendar-day bullet (sub-bullets for timed or distinct events that day) and patch only the single canonical current-state sentence whose meaning changed. Log real-world events only—not wiki edits. Remove completed one-off tasks when the Log records their completion.

## Approval boundary

Present `item → action/destination → context (where used) → MOC → source disposition` for the whole batch. Call out ambiguities instead of guessing. Apply only approved moves, merges, task additions, archives, or deletions; then repair links and bump `updated`.

Do not force inbox zero. Leave unresolved items in place with a clear reason. Fully processed transient capture files and rejected read-later items may be deleted only with explicit approval. Do not commit, publish, share publicly, or push without separate explicit confirmation.
