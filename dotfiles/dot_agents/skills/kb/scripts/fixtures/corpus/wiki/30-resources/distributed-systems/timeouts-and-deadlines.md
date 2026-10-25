---
title: Timeouts and deadlines
created: 2026-03-03
type: concept
tags: [distributed-systems, timeouts, deadlines, latency]
---
# Timeouts and deadlines

A **timeout** is per call; a **deadline** is an absolute point in time for the whole request, passed down each hop.

Why deadlines
- With per-hop timeouts, a chain of 3 calls at 2 s each can take 6 s while the user gave up at 3 s.
- Passing the remaining budget lets a downstream service skip work nobody will wait for.

Setting a timeout
- Start from the p99 latency of the dependency plus a margin, not a round number.
- The caller's timeout must be longer than the callee's timeout times its retries, or the retries are wasted.
- Log which timeout fired; "timed out" alone is not actionable.
