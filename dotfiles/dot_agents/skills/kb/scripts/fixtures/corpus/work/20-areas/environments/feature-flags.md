---
title: Feature flags
created: 2025-10-22
type: reference
tags: [environments, feature-flags]
---
# Feature flags

Flags are evaluated per site and per carrier. Change them in the flag console; every change needs a work item number in the reason field.

| Flag | Default | Used for |
| --- | --- | --- |
| `carrier.<id>.enabled` | true | Take a slow carrier out of route planning |
| `dock.early-arrival-hold` | false (on at North) | Hold early trucks at the gate |
| `billing.line-level-accessorials` | true | Line-level accessorial charges |
| `route.eta.model-v2` | false | New ETA model (eta-model-refresh project) |
