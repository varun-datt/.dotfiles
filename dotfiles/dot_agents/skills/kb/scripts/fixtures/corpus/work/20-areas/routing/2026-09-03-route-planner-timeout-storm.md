---
title: Route planner timeout storm
created: 2026-09-03
type: event
tags: [routing, incident, timeouts, retries]
severity: 2
---
# Route planner timeout storm

Work item: #4821
Correlation id of the first failing request: `3e91c0d4-7a2f-4b65-8d1e-c94f0a6b27e3`

## Summary
For 47 minutes, 18% of route requests ended with `ERR_ROUTE_TIMEOUT`. One carrier's rate API slowed to 4 s; our retries tripled its load and it slowed further.

## Timeline (UTC)
- 13:02 carrier p99 rises from 600 ms to 4 s.
- 13:06 alert `ERR_ROUTE_TIMEOUT rate above 2%` fires.
- 13:15 on-call raises `route.retry.max-attempts` from 3 to 5. Timeouts rise.
- 13:31 rolled back to 3; carrier disabled by flag.
- 13:49 error rate back under 1%.

## Contributing factors
- Retries without jitter (the 2026-08-14 decision had not shipped yet).
- `carrier.timeout-ms` was 5000, longer than the planner's own deadline of 4000, so a retry could never finish in time.

## Actions
- Ship the jittered `RetryPolicy` (#4790).
- Lower `carrier.timeout-ms` to 1500 (#4822).
- Runbook: never raise retries during an incident (done).
