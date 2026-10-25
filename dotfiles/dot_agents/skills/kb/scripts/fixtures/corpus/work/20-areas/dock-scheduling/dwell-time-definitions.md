---
title: Dwell time definitions
created: 2025-11-14
type: reference
tags: [dock-scheduling, dwell, definitions]
---
# Dwell time definitions

- **Dwell**: gate-in scan to gate-out scan, in minutes. Computed by `computeDwellMinutes` in dock-scheduler.
- **Door time**: door assigned to door released.
- **Pre-gate wait**: arrival at the staging lane to gate-in (only at sites running the early-arrival hold).
- **Detention**: dwell beyond the free time in the carrier contract (usually 120 minutes); we pay it.

Edge cases
- Missing gate-out: excluded from reports and flagged to the site.
- Visit spanning midnight: no special handling; timestamps are UTC.
- Trailer drop (no driver waiting): dwell is not computed.
