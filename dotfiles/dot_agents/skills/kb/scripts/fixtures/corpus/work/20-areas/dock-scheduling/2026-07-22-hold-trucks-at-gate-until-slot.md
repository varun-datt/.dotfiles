---
title: Hold early trucks at the gate until their slot opens
created: 2026-07-22
type: decision
tags: [dock-scheduling, decision, slots, yard]
status: accepted
---
# Hold early trucks at the gate until their slot opens

## Context
About 22% of trucks arrive more than 45 minutes before their slot. The gate lets them in and they wait in the yard or block door aprons, which raises dwell for everyone and caused two near-misses with yard tractors in June.

## Options
1. Admit early arrivals and queue them in the yard (current behaviour).
2. Hold early arrivals in a staging lane outside the gate; call each one forward 20 minutes before its slot.
3. Let an early arrival take any free door if one exists; otherwise hold it as in option 2.

## Decision
Option 3. When the gate scans the ASN, dock-scheduler looks for a free door; if `allocateSlot` finds one the truck goes straight in, otherwise the YMS sends it to the staging lane and calls it forward 20 minutes before its booked slot.

## Consequences
- Dwell measured from gate-in drops; time in the staging lane is tracked separately as pre-gate wait.
- Carriers may object to waiting outside; the SLA clock starts at the booked slot, not at arrival.
- Needs sign-off on the staging lane from site safety.
