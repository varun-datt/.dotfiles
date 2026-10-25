---
title: ETA accuracy targets
created: 2026-01-15
type: reference
tags: [routing, eta, slo]
---
# ETA accuracy targets

ETA error = actual arrival minus predicted arrival, measured at the last stop.

| Lane type | Target (p80 absolute error) | Current (Q3) |
| --- | --- | --- |
| Urban LTL, under 50 km | within 15 minutes | 19 minutes |
| Regional FTL, 50-400 km | within 30 minutes | 27 minutes |
| Long haul FTL, over 400 km | within 90 minutes | 104 minutes |
| Cross-dock transfer | within 20 minutes | 22 minutes |

Notes
- These are SLOs, not customer SLAs; for promises see billing/sla-targets-by-customer-tier.
- Long haul misses are mostly driver rest stops the model does not know about; see the eta-model-refresh project.
