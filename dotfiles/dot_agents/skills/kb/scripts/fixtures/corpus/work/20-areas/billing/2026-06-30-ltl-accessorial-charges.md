---
title: Bill LTL accessorial charges at line level
created: 2026-06-30
type: decision
tags: [billing, decision, ltl, invoices]
status: accepted
---
# Bill LTL accessorial charges at line level

## Context
Liftgate, inside delivery and detention were summed into one "accessorials" line on LTL invoices. Customers disputed 1 invoice in 12 because they could not see what the charge was for.

## Options
1. Keep one summed line and attach a breakdown PDF.
2. One invoice line per accessorial.

## Decision
Option 2. Each accessorial is its own invoice line with a code and the stop it applies to. Detention lines carry the dwell minutes reported by dock-scheduler.

## Consequences
- Disputes should fall; EDI 810 files get longer.
- Customer EDI maps need an update; three customers need a migration window.
