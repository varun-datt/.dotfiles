---
name: tend
description: Audits a bounded slice of a Markdown notes repository (the personal wiki or the work knowledge repo) for structure, consistency, freshness, factual drift, and repository self-sufficiency. Use when the user invokes /tend or asks to maintain, clean up, or health-check the vault or notes repository.
disable-model-invocation: true
---

# Tend the vault

First pick the repository and read its marker and check command ([PARA workflow settings](../vault-validator/references/workflows.md)).

Run one bounded maintenance pass, report findings, and wait for approval before editing.

## Choose scope

Use the scope named by the user. Otherwise offer the safest small scope:

1. files changed after the timestamp in the repository's tend run marker;
2. one folder;
3. one note.

Never substitute “since the last Git commit” for “since the last tend run.” If the marker is missing or malformed, say so and ask for a bounded scope. Scan the whole vault only when the user explicitly requests it.

`repository memory` is also an explicit scope; use the reconciliation procedure below instead of a time- or path-based vault scan.

## Check

1. **Structure** — required and type-specific frontmatter, valid enums, kebab-case filenames, misplaced attachments, and tag near-duplicates.
2. **Consistency** — broken wikilinks, orphans, duplicates, contradictions, and terminology drift.
3. **Freshness** — stale notes, time-sensitive claims, aging read-later items, and projects/areas that may be closeout candidates. Suggest `archive-closeout` only after the user confirms a completed/abandoned outcome or ended/transferred responsibility.
4. **Facts** — verify only checkable claims that matter to the selected scope. Use Tavily search and extraction skills. Cite every proposed factual correction.
5. **Self-sufficiency** — identify durable repository facts or conventions that exist only in disposable agent memory, then run the repository's check command.

Respect type-specific lifecycles. In particular, `read-later` status is `queued|summarized|filed|dropped`, not the core note status.

## Reconcile repository memory

When the scope is `repository memory`, treat `/memories/repo/` as temporary input rather than an authority:

1. Break its contents into individual factual claims, decisions, and conventions.
2. Classify each item as `repo-backed`, `memory-only`, `conflicting`, or `transient`; cite the canonical repository path for every `repo-backed` item.
3. Present every `memory-only`, `conflicting`, and `transient` item with a recommended `store`, `correct`, or `discard` action, and obtain the user's decision before changing the repository or deleting memory.
4. Apply only approved repository changes, repeat the comparison, and stop if a durable claim remains unmatched or a conflict remains unresolved.
5. After the user approves cleanup, clear `/memories/repo/` and verify that it contains no files.

A repository-memory reconciliation passes only when repository memory is empty and the report identifies no unresolved memory-only durable claims or conflicts. `make check` remains required for repository edits but cannot prove semantic equivalence. Do not update `meta/system/tend-state.yml` for a repository-memory-only reconciliation; that marker tracks bounded vault-file maintenance.

## Report and apply

Return one Markdown report with:

- issue counts and severity by check;
- each affected path, evidence, and a concrete fix;
- checks that could not be completed.

Ask which fixes to apply. On approval, edit only those items, preserve the author's voice, and bump `updated` where note content changes. Archive durable notes instead of deleting them.

After an approved pass completes, propose updating the tend run marker with an ISO-8601 UTC timestamp and the completed scope. Update it only with the user's approval so the marker never claims an incomplete run.

Do not commit, publish, share publicly, or push without separate explicit confirmation.
