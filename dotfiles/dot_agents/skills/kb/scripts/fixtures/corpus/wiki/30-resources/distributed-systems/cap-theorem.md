---
title: CAP theorem
created: 2025-10-14
type: concept
tags: [distributed-systems, cap, consistency]
---
# CAP theorem

During a network partition a distributed store must choose between:
- **Consistency**: every read sees the latest write (linearizable).
- **Availability**: every request to a live node gets a non-error answer.

Partitions happen whether you plan for them or not, so the real choice is consistency or availability *while partitioned*.

Common misreadings
- "Pick two of three" misleads: without a partition you can have both.
- CAP says nothing about latency. PACELC adds it: else (no partition), choose latency or consistency.

Examples
- A Raft-based store chooses consistency: the minority side refuses writes.
- A last-write-wins store chooses availability and reconciles later.
