---
title: Questions for carrier rate API v3
created: 2026-10-20
type: inbox
tags: [inbox, routing, carrier]
---
- Does v3 send a `Retry-After` header on 429 and 503? If so, `RetryPolicy` should honour it instead of its own delay.
- Is a rate quote valid for 15 or 30 minutes?
- Will they accept an idempotency key on tender requests?
- Their sandbox host is `carrier-sandbox.example.com`; request test access through the partner portal, not by email.
