---
title: Composite index column order
created: 2025-10-05
type: concept
tags: [databases, sql, indexes]
---
# Composite index column order

An index on `(a, b, c)` serves queries on `a`, `a, b` and `a, b, c` (the leftmost prefix), but not `b` alone.

Ordering rule of thumb
1. Columns compared with equality first.
2. Then the column used for a range or ORDER BY.
3. Selectivity matters less than people think once 1 and 2 are right.

Example: `WHERE carrier_id = ? AND created_at > ? ORDER BY created_at` wants `(carrier_id, created_at)`.

Covering index: add the selected columns (or use INCLUDE) so the query never touches the table.
