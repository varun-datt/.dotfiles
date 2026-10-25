---
title: Replay safety rules
created: 2026-09-17
type: note
tags: [project, platform, dlq, idempotency]
---
# Replay safety rules

1. Replay only into consumers that dedupe on `messageId`; all of ours do (see queue topology).
2. Never replay while the original cause is still present: the tool checks the consumer's error rate first.
3. Keep the original `messageId`; a new id defeats dedupe and double-bills (see the duplicate invoices event).
4. Replay oldest first so slot events apply in order.
