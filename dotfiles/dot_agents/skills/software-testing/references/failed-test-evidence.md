# Failed-test evidence

A system or end-to-end test that fails across services leaves its cause in other systems' logs, rows, queues and traces. Reading them in the wrong order, or trusting an empty answer, sends the search to the wrong service.

## Procedure

1. **Follow the domain ids first.** Take the ids the test's setup calls returned (an order id, a device serial, a request id) and search each store by them; use trace context second and a time window last. A test runner may not send a W3C `traceparent`, and a messaging consumer *links* to the producer's span instead of becoming its child, so a trace often stops at the first queue ([OTel messaging spans](https://opentelemetry.io/docs/specs/semconv/messaging/messaging-spans/)).
2. **Give every empty result a positive control.** Before "no log line for this id" counts as evidence, run the same query on something known to exist in that store over the same window (any line from the service in the last minutes, a row written by the same setup). An empty answer with no control can mean the wrong index, the wrong time zone, missing rights or a store that is not written at all.
3. **Hand an agent a compact, deterministic result, not the raw report.** Query the captured run for the failing step's calls, ids and errors, and give the agent that. A raw test report is too big to read: one suite's report measured 10.7 MB, about 2.7 million tokens ([Kronikol](https://github.com/lemonlion/Kronikol)). Keep what the agent infers labelled apart from what the query returned.

## Traps

- A test's own debug report can record every call with its tokens and cookies: redact it before reading, sharing or attaching it.
- A search that finds nothing because the query was wrong looks the same as a system that did nothing; the control in step 2 is the only way to tell them apart.

Example: `agent-mission-control`, `research/2026-11-07-apps-reading-platform-state.md` and `research/2026-11-07-apps-test-steps-with-system-state.md`.
