---
title: One dead-letter queue per consumer
created: 2026-05-12
type: decision
tags: [platform, decision, queues, dlq]
status: accepted
---
# One dead-letter queue per consumer

## Context
All services shared one DLQ. When it filled up nobody knew whose messages they were, and replaying meant filtering thousands of mixed messages by hand.

## Options
1. Keep the shared DLQ and add a source header.
2. One DLQ per consumer queue (`<queue>.dlq`).

## Decision
Option 2. Each consumer dead-letters to `<queue>.dlq` after 5 failed deliveries, with exponential backoff between deliveries (1 s, 5 s, 30 s, 2 min, 10 min). Alert per DLQ at 500 messages for 10 minutes.

## Consequences
- More queues to create; the platform module creates them from the consumer's config.
- Replay is per service; the dlq-replay-tool project builds on this.
