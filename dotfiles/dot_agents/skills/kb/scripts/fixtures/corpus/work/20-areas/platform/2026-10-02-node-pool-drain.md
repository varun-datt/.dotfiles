---
title: Node pool drain evicted scheduler pods
created: 2026-10-02
type: event
tags: [platform, incident, kubernetes, pods]
severity: 3
---
# Node pool drain evicted scheduler pods

Work item: #5233
Correlation id: `d4e7a90b-15c3-4e2f-8a6d-b3f0c2915e76`

## Summary
During a planned node pool upgrade, all three dock-scheduler pods for the south site were evicted within two minutes. For 6 minutes callers saw `upstream connect error or disconnect/reset before headers` and the gates fell back to paper slips.

## Contributing factors
- No PodDisruptionBudget on dock-scheduler, so the drain removed every pod at once.
- Pods took 90 s to become ready because the slot book is rebuilt on start.

## Actions
- Add a PodDisruptionBudget with `minAvailable: 2` (#5234).
- Rebuild the slot book lazily, per door, after start (#5235).
