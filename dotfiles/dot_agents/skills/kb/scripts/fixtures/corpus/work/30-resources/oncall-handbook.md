---
title: On-call handbook
created: 2025-07-10
type: reference
tags: [oncall, process]
---
# On-call handbook

- Rotation: one week, handover Monday 10:00.
- Page response: acknowledge within 10 minutes, update the incident channel every 30 minutes.
- Start from the runbook named in the alert. Runbooks live under `20-areas/<area>/runbook-*.md`.
- Every page gets a work item; incidents with customer impact get an event note (`type: event`) within five working days.
- Escalate to the area lead if a runbook step fails or is missing.

Common alerts and their runbooks
| Alert | Runbook |
| --- | --- |
| `ERR_ROUTE_TIMEOUT` rate above 2% | routing/runbook-route-timeout |
| `SlotConflictException` spike | dock-scheduling/runbook-slot-conflict |
| DLQ depth above 500 for 10 minutes | platform/runbook-dlq-depth-alert |
| `upstream connect error or disconnect/reset before headers` | platform/runbook-upstream-connect-error |
| Invoice export rejected | billing/runbook-invoice-export-rejected |
