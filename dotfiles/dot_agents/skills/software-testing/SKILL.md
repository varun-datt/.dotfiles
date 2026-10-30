---
name: software-testing
description: "Testing practice, one topic per reference file. Flaky tests: find the kind behind a test that passes and fails on the same code, fix that kind across the suite, and prove the fix under load. Use when a test, a merge gate or a commit hook fails now and then, when a test passes alone and fails in the full run, or when writing a test that waits on timers, file-system events, child processes, ports or another service."
---

# Software testing

Read the topic that matches the task; each file stands alone.

| Topic | Read when |
| --- | --- |
| [Flaky tests](references/flaky-tests.md) | A test passes and fails on the same code; a gate or hook fails now and then; a new test waits on timers, OS events, processes or ports |

## Rules for every topic

- **Prove a test can fail.** Commit the change first and read the commit's hash, then break the
  behaviour the test covers, see the test fail, and undo the break with `git checkout -- <file>`.
  Never undo it with a pattern delete: a `sed '/text/d'` once removed 12 identical lines, and a
  checkout run after a commit whose hook had failed reverted the uncommitted fix.
- **Read before you touch.** The failure's trace and the app's logged state come before any change
  to the test.

## Adding a topic

- One file per topic in `references/`, sources cited, and one row in the table above.
- Add the topic's trigger phrases to `description`, so the skill loads for it.
- A topic keeps what holds across projects; a project's own details stay in its test docs, linked
  as an example.
