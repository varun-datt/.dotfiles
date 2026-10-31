---
name: software-testing
description: "Testing practice, one topic per reference file. Case lists: before building, list the cases a change must survive (other paths, event orders, failures, edge values, outside input, library facts) by risk, and give each a test. Event orders: drive a race or a restart on purpose so its test fails every time. Flaky tests: find the kind behind a test that passes and fails on the same code, fix that kind across the suite, and prove the fix under load. Mutation checks: prove a new test fails when the code it covers breaks, by patching that code at runtime instead of editing it. Use before building a feature or a fix, when a review found a missed case, when a test, a merge gate or a commit hook fails now and then, when a test passes alone and fails in the full run, when writing a test that waits on timers, file-system events, child processes, ports or another service, or when proving that a new test can fail."
---

# Software testing

Read the topic that matches the task; each file stands alone.

| Topic | Read when |
| --- | --- |
| [Case lists](references/case-lists.md) | Before building a feature or fix: list the cases by risk and give each a test; after a review found a case nobody listed |
| [Event orders](references/event-orders.md) | A change awaits, uses callbacks or timers, survives a restart, or checks a file then uses it |
| [Flaky tests](references/flaky-tests.md) | A test passes and fails on the same code; a gate or hook fails now and then; a new test waits on timers, OS events, processes or ports |
| [Mutation checks](references/mutation-checks.md) | Proving that new tests fail when the code they cover breaks, without editing that code |

## Rules for every topic

- **Prove a test can fail.** Commit the change first and read the commit's hash, then break the
  behaviour the test covers, see the test fail, and undo the break with `git checkout -- <file>`.
  Never undo it with a pattern delete: a `sed '/text/d'` once removed 12 identical lines, and a
  checkout run after a commit whose hook had failed reverted the uncommitted fix. Breaking it at
  runtime instead changes no file: [mutation checks](references/mutation-checks.md).
- **Read before you touch.** The failure's trace and the app's logged state come before any change
  to the test.
- **A case nobody listed is the usual miss.** List the cases before the code
  ([case lists](references/case-lists.md)); tests then follow the list, not the code just written.

## Adding a topic

- One file per topic in `references/`, sources cited, and one row in the table above.
- Add the topic's trigger phrases to `description`, so the skill loads for it.
- A topic keeps what holds across projects; a project's own details stay in its test docs, linked
  as an example.
