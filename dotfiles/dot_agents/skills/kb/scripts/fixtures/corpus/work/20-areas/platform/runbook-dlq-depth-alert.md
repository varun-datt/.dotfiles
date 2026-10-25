---
title: "Runbook: DLQ depth alert"
created: 2025-09-15
type: runbook
tags: [platform, runbook, queues, dlq]
---
# Runbook: DLQ depth alert

Alert: `DLQ depth above 500 for 10 minutes`.

Meaning: a consumer keeps failing and has dead-lettered more than 500 messages. They are safe in the DLQ and nothing is lost yet, but the business process behind them has stalled.

## Check
1. Which queue? Each consumer has its own DLQ (`<queue>.dlq`), so the name tells you the service.
2. Peek at three messages: same error? Read the `x-failure-reason` header.
3. Did a deploy go out in the last hour?

## Act
- Bad deploy: roll back, then replay the DLQ (see the dlq-replay-tool project; until it ships, use the manual replay script at 50 messages per second).
- Poison message (one bad payload repeated): move it aside to `<queue>.parked` and replay the rest.
- Downstream outage: wait; do not replay into a dependency that is still down.

## Do not
Purge a DLQ. Billing and dock events in it may be the only copy.
