---
title: Idempotency keys
created: 2026-01-19
type: concept
tags: [distributed-systems, idempotency, retries, api-design]
---
# Idempotency keys

An operation is idempotent when doing it twice has the same effect as doing it once. Retries are only safe for idempotent operations.

## The pattern
1. The client generates one unique key per logical operation (not per attempt) and sends it in a header such as `Idempotency-Key`.
2. The server stores the key with the result of the first successful attempt.
3. A repeat with the same key returns the stored result instead of acting again.

## Details that bite
- Store the key and the side effect in the same transaction, or a crash between them breaks the guarantee.
- Keys need a retention window (24 h is common); document it.
- Reject a repeated key whose request body differs: that is a client bug, not a retry.
- Consumers of at-least-once queues need the same idea: dedupe on the message id.

Related: [[exponential-backoff-with-jitter]].
