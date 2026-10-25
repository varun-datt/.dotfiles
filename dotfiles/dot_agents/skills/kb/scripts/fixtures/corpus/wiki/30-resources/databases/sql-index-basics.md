---
title: SQL index basics
created: 2025-09-30
type: concept
tags: [databases, sql, indexes]
---
# SQL index basics

A B-tree index keeps keys sorted, so lookups, range scans and ORDER BY can avoid a full table scan.

When an index helps
- Equality and range predicates on the indexed column.
- Joins on the indexed column.
- ORDER BY matching the index order (no sort step).

When it does not
- Functions on the column: `WHERE lower(email) = ?` needs an expression index.
- Low selectivity: a column with two values; the planner prefers a scan.
- Leading wildcard: `LIKE '%son'`.

Costs
- Every insert and update also writes each index.
- More indexes mean slower writes and more memory pressure.

Check with `EXPLAIN`: look for "Index Scan" versus "Seq Scan" and compare estimated with actual rows.
