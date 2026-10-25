---
title: DLQ replay tool
created: 2026-09-10
type: project
tags: [project, platform, dlq, tooling]
---
# DLQ replay tool

Today a dead-letter queue is replayed by a script run by hand, at a rate limit someone remembers. Goal: a tool that replays a DLQ safely.

Scope
- Select messages by failure reason and time range.
- A dry run that shows what would be replayed.
- Rate limit (default 50 per second); stop on the first new failure.
- Audit log of who replayed what.

Out of scope: editing message bodies.
