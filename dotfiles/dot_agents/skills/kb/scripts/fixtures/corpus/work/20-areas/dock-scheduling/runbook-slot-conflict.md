---
title: "Runbook: SlotConflictException"
created: 2025-10-01
type: runbook
tags: [dock-scheduling, runbook, slots]
---
# Runbook: SlotConflictException

Error in dock-scheduler logs: `SlotConflictException: slot already held`.

Meaning: two holds raced for the same door and time window and the second lost. A few per hour are normal at shift change. A spike means something is retrying holds or the slot book is out of sync.

## Check
1. Count per door: one door with many conflicts usually means a stuck hold that never expired.
2. Is a client retrying `POST /slots/hold` in a loop? Look for the same carrier with many different `holdRequestId` values.
3. Compare `DOCK_SLOTS_MAX` for the site with the doors actually open today.

## Act
- Stuck hold: release it with `POST /slots/release` and the hold id; note the work item.
- Client loop: block the client key for 15 minutes and tell the carrier integration team.
- Slot book out of sync: restart the scheduler pod for that site; it rebuilds the book from the database on start.

## Do not
Delete rows from the slots table by hand; the audit trail feeds detention billing.
