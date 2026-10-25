---
title: Exponential backoff with jitter
created: 2026-02-15
type: concept
tags: [distributed-systems, retries, backoff, jitter]
---
# Exponential backoff with jitter

Retrying immediately after a failure makes overload worse. Exponential backoff waits longer after each failed attempt:

    delay = min(cap, base * 2^attempt)

Without jitter, clients that failed together retry together, in synchronized waves: a retry storm, or thundering herd. Jitter spreads them out.

## Variants
- **Full jitter**: `sleep = random(0, min(cap, base * 2^attempt))`. Usually the best choice: least total work.
- **Equal jitter**: half fixed, half random. Keeps a minimum wait.
- **Decorrelated jitter**: `sleep = min(cap, random(base, previous * 3))`.

## Rules of thumb
- Cap the number of attempts (3-5) as well as the delay.
- Only retry idempotent operations, or send an idempotency key.
- Retry on timeouts and 503; never on 4xx validation errors.
- Keep a retry budget (for example, retries at most 10% of requests) so a long outage does not triple the load.
