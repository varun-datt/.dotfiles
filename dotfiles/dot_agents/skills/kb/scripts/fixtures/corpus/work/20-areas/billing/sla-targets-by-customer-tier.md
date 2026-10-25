---
title: SLA targets by customer tier
created: 2026-02-01
type: reference
tags: [billing, sla, customers]
---
# SLA targets by customer tier

What each tier is promised, and the credit owed if we miss. billing-gateway applies credits at month end.

| Tier | On-time delivery (OTIF) | Dock appointment wait | Credit if missed |
| --- | --- | --- | --- |
| Platinum | 98% of orders | under 30 minutes | 5% of monthly freight spend |
| Gold | 96% of orders | under 45 minutes | 3% of monthly freight spend |
| Silver | 93% of orders | under 60 minutes | 1% of monthly freight spend |
| Standard | best effort | best effort | none |

Notes
- Appointment wait is measured from the booked slot start, not from arrival.
- Internal SLOs are stricter; see routing/eta-accuracy-targets.
