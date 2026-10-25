---
title: JVM garbage collection basics
created: 2025-11-11
type: concept
tags: [jvm, java, gc, performance]
---
# JVM garbage collection basics

Generational hypothesis: most objects die young. The heap is split into a young generation (eden plus survivor spaces) and an old generation.

Collectors in current JDKs
- **G1**: the default; region-based; aims at a pause target (`-XX:MaxGCPauseMillis`, default 200 ms).
- **ZGC**: concurrent, pauses of a few ms, for large heaps.
- **Parallel**: throughput first, longer pauses.

What to look at
- GC logs: `-Xlog:gc*:file=gc.log`.
- Allocation rate and promotion rate.
- Full GC events: usually a heap that is too small, or a leak.

First fixes
- Set `-Xms` equal to `-Xmx` in containers to avoid resize pauses.
- Cut allocation in hot paths before tuning flags.
