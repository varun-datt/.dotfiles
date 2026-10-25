---
title: Use full jitter for carrier retries
created: 2026-08-14
type: decision
tags: [routing, decision, retries, carrier]
status: accepted
---
# Use full jitter for carrier retries

## Context
Carrier calls from route-planner retried on a fixed schedule: 200 ms, 400 ms, 800 ms. When a carrier slowed down, every planner instance retried at the same instants, and the carrier saw synchronized bursts of three times normal traffic. Work item #4790 has the graphs.

## Options
1. Keep exponential backoff and add full jitter.
2. Fixed delay plus a circuit breaker.
3. Move carrier calls onto an async queue.

## Decision
Option 1. `RetryPolicy` in route-planner uses full jitter: each delay is random between 0 and `min(maxDelayMs, baseDelayMs * 2^attempt)`. `maxAttempts` stays at 3. Only timeouts and HTTP 503 are retried; 4xx responses never are.

## Consequences
- Bursts flatten and total retry traffic drops.
- Tests must seed the random source to stay deterministic.
- A circuit breaker (option 2) is still wanted; tracked separately.
