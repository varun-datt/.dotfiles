---
title: "Runbook: ERR_ROUTE_TIMEOUT"
created: 2025-08-19
type: runbook
tags: [routing, runbook, timeouts, carrier]
---
# Runbook: ERR_ROUTE_TIMEOUT

Alert: `ERR_ROUTE_TIMEOUT rate above 2% for 5 minutes` on route-planner.

Meaning: route-planner gave up waiting for a carrier rate or transit-time call. The planner returns a partial route and the TMS falls back to the last known rate.

## Check
1. Dashboard "route-planner / carrier latency": which carrier? One slow carrier is their problem; all slow is ours.
2. Logs: `level=WARN code=ERR_ROUTE_TIMEOUT carrier=<id> attempt=<n>`. If `attempt` is always the maximum, retries are not helping.
3. Compare `carrier.timeout-ms` in config with the carrier's p99 latency this hour.

## Act
- One carrier slow: set the flag `carrier.<id>.enabled` to false for 30 minutes; the planner uses cached rates.
- All carriers slow: suspect egress; see platform/runbook-upstream-connect-error.
- Do not raise `route.retry.max-attempts` during an incident; it multiplies load on the slow carrier (see the 2026-09-03 timeout storm).

## Escalate
Routing lead if the rate stays above 2% for 30 minutes.
