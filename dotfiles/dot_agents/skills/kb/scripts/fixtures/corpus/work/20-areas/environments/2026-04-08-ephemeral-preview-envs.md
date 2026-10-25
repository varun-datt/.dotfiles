---
title: Ephemeral preview environments per pull request
created: 2026-04-08
type: decision
tags: [environments, decision, preview]
status: accepted
---
# Ephemeral preview environments per pull request

## Context
Reviewers could not try a change without checking out the branch, and dev was broken by half-finished work twice a week.

## Options
1. A second shared dev environment.
2. One short-lived environment per pull request.

## Decision
Option 2. Each pull request gets a preview environment at `pr-<n>.preview.example.internal` with synthetic data, deleted after 72 hours or on merge.

## Consequences
- Cluster cost up about 15%; capped at 25 concurrent previews.
- Seed data must produce a realistic dock day: 40 doors, 300 slots, a few conflicts.
