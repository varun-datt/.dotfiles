---
title: Product repositories
created: 2025-06-03
type: reference
tags: [repos, reference]
---
# Product repositories

- `route-planner`: Java service that builds multi-stop routes, calls carrier rate APIs with retries and estimates the ETA at each stop.
- `dock-scheduler`: TypeScript service that books dock door slots, holds early trucks and computes dwell.
- `billing-gateway`: invoices customers, exports EDI 810 invoices and applies SLA credits.

Source lives at `git.example.internal/larkspur/<repo>`. Each repo's README says how to run it locally.
