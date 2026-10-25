---
title: Backoff notes (old)
created: 2023-05-02
type: concept
tags: [archive, retries, backoff]
---
# Backoff notes (old)

Superseded by [[exponential-backoff-with-jitter]].

Retry with exponential backoff: delay = base * 2^attempt, capped.
Add random jitter so clients do not retry in lockstep.
I used to recommend equal jitter; full jitter does less total work.
Cap attempts at 5.
