---
title: Door 7 double booked at the north site
created: 2026-09-18
type: event
tags: [dock-scheduling, incident, slots]
severity: 3
---
# Door 7 double booked at the north site

Work item: #5107
Correlation id: `b52d8e17-0c4a-4f93-a6e2-1d7f39c58b04`

## Summary
Two carriers were given the same 08:00-09:00 slot on door 7. The second truck waited 70 minutes and we paid a detention charge.

## What happened
- A carrier client retried `POST /slots/hold` after a timeout, with a new `holdRequestId` each time.
- The first hold had succeeded; the retry raced another carrier's hold for the same slot.
- A cache in front of `SlotBook` served a stale "free" answer, so the conflict check that throws `SlotConflictException` ran against the cache instead of the database.

## Actions
- The conflict check reads the database row under a lock (#5108).
- Hold requests must reuse `holdRequestId` across retries; a new id for the same carrier and slot within 60 s is rejected (#5109).
- Door-level conflict rate added to the dock dashboard (#5110).
