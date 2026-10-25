---
title: Queue topology
created: 2026-05-20
type: reference
tags: [platform, queues, dlq]
---
# Queue topology

| Queue | Producer | Consumer | DLQ |
| --- | --- | --- | --- |
| `dock.arrivals` | gate scanners | dock-scheduler | `dock.arrivals.dlq` |
| `dock.slot-events` | dock-scheduler | billing-gateway | `dock.slot-events.dlq` |
| `route.requests` | TMS | route-planner | `route.requests.dlq` |
| `billing.invoices` | billing-gateway | EDI exporter | `billing.invoices.dlq` |

Delivery is at least once. Every consumer dedupes on `messageId` for 24 h.
Deliveries before dead-lettering: 5, with backoff between them (see the 2026-05-12 decision).
