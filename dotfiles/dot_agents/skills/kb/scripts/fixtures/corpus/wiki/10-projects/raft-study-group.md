---
title: Raft study group (autumn)
created: 2026-09-05
type: project
tags: [project, raft, consensus, distributed-systems]
---
# Raft study group

Goal: by the end of November each of us can explain leader election and log replication on a whiteboard without notes, and has built a toy implementation.

## Plan
| Week | Topic | Done |
| --- | --- | --- |
| 1 | Terms, roles, leader election | yes |
| 2 | Log replication, commit index | yes |
| 3 | Safety: the election restriction | no |
| 4 | Membership changes, joint consensus | no |
| 5 | Snapshots and log compaction | no |

## Open questions
- Why randomized election timeouts (150-300 ms in the toy) are enough to avoid split votes most of the time.
- How a leader notices it has lost its majority when it cannot trust the clock.

My summary notes: [[raft-consensus]].
