---
name: read-later-digest
description: Extracts and summarizes queued read-later items, then proposes keep, file, or drop decisions. Use when the user invokes /read-later-digest or asks to process queued articles, videos, or PDFs in a notes repository's read-later queue.
disable-model-invocation: true
---

# Digest read-later items

First pick the repository and read its folders ([PARA workflow settings](../vault-validator/references/workflows.md)).

Process items in the read-later queue whose status is `queued`. If no scope is given, ask whether to handle one item, a selection, or all queued items.

## Acquire the source

- For an article or webpage, use the installed `tavily-extract` skill. Use `tavily-search` only when discovery or corroboration is needed.
- For a video, use an available transcript or captions and cite the video URL.
- For a PDF, read the local file or linked PDF with an appropriate document tool.

Do not fabricate unavailable content. If extraction fails, leave the item queued and report the blocker.

## Summarize

Append a concise digest to the source note:

- `## TL;DR` — two or three sentences;
- `## Key points` — only decision-useful points;
- `## Why it matters` — connect to an existing project, area, resource, or stated reason saved;
- optional notable quotes with location or timestamp;
- suggested tags and PARA destination.

Keep the `source` URL, add citations or timestamps sufficient to trace claims, set `status: summarized`, and bump `updated`. Do not mirror the source.

Any separate research plan, extraction, or synthesis artifact must live in the inbox or a PARA destination chosen by the user—never an ad-hoc research folder at repository root.

## Decide disposition

Offer, but do not automatically apply:

- file as a literature/reference note and link its MOC, then set `status: filed`;
- leave summarized for a later decision;
- set `status: dropped`, then archive or delete only with explicit approval.

Do not commit, publish, share publicly, or push without separate explicit confirmation.
