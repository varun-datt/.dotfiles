---
title: Writing architecture decision records
created: 2026-01-26
type: concept
tags: [practice, adr, documentation, decisions]
---
# Writing architecture decision records

An ADR records one decision: the context, the options, what was chosen and the consequences. It is written when the decision is made and not edited afterwards; a later decision supersedes it.

Template
- **Title**: a short imperative ("Use full jitter for outbound retries").
- **Status**: proposed, accepted, or superseded by a later record.
- **Context**: the forces at play, with numbers where possible.
- **Options**: at least two, with honest pros and cons.
- **Decision**: one paragraph.
- **Consequences**: what gets easier, what gets harder, what we will watch.

Habits
- One decision per record.
- Name files `YYYY-MM-DD-slug.md` so they sort by date.
- Link the record from the code or config it governs.
