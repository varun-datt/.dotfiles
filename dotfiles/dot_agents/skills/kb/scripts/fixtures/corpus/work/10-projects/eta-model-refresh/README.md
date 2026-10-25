---
title: ETA model refresh
created: 2026-07-07
type: project
tags: [project, routing, eta, model]
---
# ETA model refresh

Goal: bring long haul ETA error under the 90-minute target (currently 104 minutes at p80).

Approach
- Add mandatory driver rest stops to the model.
- Add dwell history at the destination dock.
- Ship behind the `route.eta.model-v2` flag and compare side by side for four weeks.

Code: `EtaEstimator` in route-planner.
