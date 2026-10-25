---
title: Duplicate invoices after export retry
created: 2026-08-27
type: event
tags: [billing, incident, idempotency, retries]
severity: 2
---
# Duplicate invoices after export retry

Work item: #4950
Correlation id: `9a0f4c62-e3b1-4d78-b5c9-60e2a7d14f8b`

## Summary
312 customers received the August mid-month invoice twice. The export job timed out after the partner had accepted the file, then retried and sent it again.

## Contributing factors
- The export step was not idempotent: the retry generated a new interchange control number, so the partner treated it as a new file.
- The job's timeout (60 s) was shorter than the partner's acknowledgment time at month end (up to 90 s).

## Actions
- Use the invoice batch id as an idempotency key; a retry resends the same interchange number (#4951).
- Raise the export timeout to 180 s and alert on acknowledgments slower than 60 s (#4952).
- Credit notes sent to the affected customers (done).
