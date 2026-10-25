---
title: GC notes for Java 8 (old)
created: 2022-11-20
type: concept
tags: [archive, jvm, gc]
---
# GC notes for Java 8 (old)

Old notes from the CMS era, kept for reference. Superseded by [[jvm-gc-basics]].
- CMS: concurrent old-generation collector; fragmentation led to full GCs.
- PermGen sizing errors (`java.lang.OutOfMemoryError: PermGen space`) went away with Metaspace.
- `-XX:+PrintGCDetails` for logs, later replaced by unified logging.
