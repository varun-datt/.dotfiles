# Event orders

A bug that depends on order (Stop arriving while a send awaits, a stale callback from an earlier round, a file swapped between a check and a read) passes a test that only runs the happy order. Drive each order on purpose, so the test fails every time the bug is present, not once in a hundred runs.

## Procedure

1. **Name the orders.** For each `await`, callback, timer or second request in the change, write the events that can land between its start and its end (the [case lists](case-lists.md) name the usual ones). One line per order: "send, echo held, Stop, refusal".
2. **Give the code a seam at each gap.** An injected hook, a fake engine whose replies the test releases one at a time, a promise the test resolves, or a file-system function the test wraps. The seam stays in the production code only as a parameter or a dependency, never as a test flag.
3. **Write one test per order** that holds the first step at the seam, fires the interfering event, releases the step, and asserts the end state. Assert the state a person would see (the card, the record, the file), not that a function was called.
4. **Restarts are orders too.** Close the manager, store and log, open new ones on the same data, and assert what the person sees after the restart. A test that writes the answer after shutdown does not test an interrupted step: interrupt the step itself.
5. **Prove each test can fail** by reverting its fix at runtime ([mutation checks](mutation-checks.md)); a test that passes on the old code proves nothing about the order.
6. **When the orders are too many to list,** generate them. fast-check's `scheduler()` "has been specifically designed for detecting and testing race conditions": it re-orders scheduled promises and reports the order that failed, and `scheduledModelRun` runs a model of the system through the same scheduler ([fast-check, race conditions](https://fast-check.dev/docs/advanced/race-conditions); [model-based testing](https://fast-check.dev/docs/advanced/model-based-testing/)). It is a dependency: use it only where the task's ALLOWED DEPENDENCIES names it. Python's equivalent, Hypothesis's stateful testing, is not in the standard library; in a standard-library-only repository, list the orders by hand and drive them with `threading.Event` or an injected function.

## Traps

- A sleep is not a seam: it makes the order likely, not certain, and the test flaky ([flaky tests](flaky-tests.md)).
- A fake that answers in a fixed order hides every other order; give it a way to hold and release each reply.
- Capture the round or generation before the first `await`, and check it after every `await`: capturing it after the first `await` let an earlier round's write consume a later round's approval.
