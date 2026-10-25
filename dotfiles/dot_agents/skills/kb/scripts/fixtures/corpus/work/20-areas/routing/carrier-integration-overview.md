---
title: Carrier integration overview
created: 2025-09-02
type: reference
tags: [routing, carrier, integration]
---
# Carrier integration overview

route-planner talks to carriers in three ways:
- **Rate API** (sync HTTP): price and transit time for a lane, called per route request. This is where `ERR_ROUTE_TIMEOUT` comes from.
- **Tender** (EDI 204): offer a load to a carrier; they reply within 2 hours.
- **Status** (EDI 214): the carrier pushes pickup, in-transit and delivered events, including POD images.

Client code: `CarrierClient` wraps the rate API with `RetryPolicy` and a per-carrier timeout (`carrier.timeout-ms`).
Carrier access keys are held in the platform secret store, never in config files.
