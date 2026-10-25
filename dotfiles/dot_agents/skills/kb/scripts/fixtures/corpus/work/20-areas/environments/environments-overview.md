---
title: Environments overview
created: 2025-06-20
type: reference
tags: [environments, deploy]
---
# Environments overview

| Environment | Purpose | Address | Data |
| --- | --- | --- | --- |
| dev | shared integration, deployed on merge | `dev.example.internal` | synthetic |
| staging | release candidate, load tests | `staging.example.internal` | masked copy of prod, refreshed weekly |
| preview | one per pull request, 72 h lifetime | `pr-<n>.preview.example.internal` | synthetic |
| prod | customers | `app.example.com` | live |

Promotion: dev to staging when the release branch is cut; staging to prod after sign-off.
