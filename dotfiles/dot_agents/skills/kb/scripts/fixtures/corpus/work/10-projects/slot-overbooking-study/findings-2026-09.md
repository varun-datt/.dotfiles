---
title: Overbooking findings, September
created: 2026-09-29
type: note
tags: [project, dock-scheduling, slots, research]
---
# Overbooking findings, September

| Ratio | Median dwell | p90 dwell | No-door events per day |
| --- | --- | --- | --- |
| 100% | 48 | 131 | 0.2 |
| 105% | 49 | 138 | 1.1 |
| 110% | 53 | 171 | 4.6 |
| 115% | 61 | 225 | 11.8 |

Reading: 105% costs almost nothing; 110% hurts the tail. No-shows cluster on Monday mornings, so a per-weekday ratio may beat a single number.
Caveat: the simulator ignores the early-arrival hold; rerun with it switched on.
