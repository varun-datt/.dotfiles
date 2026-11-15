---
name: moc-builder
description: Creates or refreshes a curated Map of Content from existing vault notes. Use when the user invokes /moc-builder or asks to organize a topic, build a hub, or improve navigation among related notes.
disable-model-invocation: true
---

# Build a Map of Content

First pick the repository and read its folders ([PARA workflow settings](../vault-validator/references/workflows.md)).

Use the topic supplied by the user. Search by folder, tags, links, titles, and content; semantic similarity is supporting evidence, not enough by itself.

## Build

1. Find the canonical MOC for the topic before creating one. Prefer `<topic>-moc.md` in the repository's maps folder unless a topic-local MOC is already established.
2. Propose the member notes, groupings, canonical tag, related MOCs, and uncovered gaps.
3. On approval, create or update one MOC with all required frontmatter: `type: moc`, a valid core status, and tags including `<topic>` and `moc`.
4. Add a one-line purpose, curated themed sections, and meaningful ordered wikilinks.
5. Where the repository has an `.obsidian/` folder, add a Dataview list for the canonical topic tag when it improves discovery without replacing curation.
6. Add backlinks or the canonical tag to member notes only when they are genuinely about the topic; bump each changed note's `updated`.

Represent gaps as suggestions. Add task checkboxes only when the user accepts responsibility for creating those notes.

## Guardrails

Do not create a second MOC for an existing topic, bulk-tag marginal notes, or turn the MOC into an uncurated link dump. Preserve established context when member notes span personal and work. Do not commit, publish, share publicly, or push without separate explicit confirmation.
