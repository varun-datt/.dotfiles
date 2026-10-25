---
title: "Runbook: staging data refresh"
created: 2025-08-08
type: runbook
tags: [environments, runbook, staging, data]
---
# Runbook: staging data refresh

Runs Sundays at 02:00 UTC. Copies prod, masks customer names, addresses and contacts, and loads the result into staging.

## When it fails
Error: `refresh aborted: masking step exceeded 45 minutes`.
1. Check whether a new text column was added without a masking rule; the job refuses unknown text columns and then stalls on retries.
2. Add the rule to `masking-rules.yaml`, then rerun with `--resume-from mask`.

## Do not
Point staging at a prod database "just for a test". Staging alerts page nobody.
