---
title: Carrier retry policy (2024)
created: 2024-06-02
type: decision
tags: [archive, routing, retries]
status: superseded
---
# Carrier retry policy (2024)

Superseded by the 2026-08-14 decision "Use full jitter for carrier retries".

Decision at the time: retry carrier calls up to 3 times with fixed exponential delays of 200, 400 and 800 ms, implemented as `RetryPolicy` with no jitter. Reason: simple, and deterministic in tests.
