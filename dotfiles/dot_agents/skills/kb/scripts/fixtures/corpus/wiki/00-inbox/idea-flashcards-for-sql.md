---
title: Idea - flashcards for SQL index rules
created: 2026-10-02
type: inbox
tags: [inbox, sql, spaced-repetition]
---
Turn the index notes into cards:
- Leftmost prefix rule for composite indexes.
- Why `WHERE lower(email) = ?` skips a plain index on `email`.
- Covering index: the query is answered from the index alone.
- Selectivity: an index on a two-value column rarely helps.

Add them to the review deck on Sunday; ten new cards a day at most.
