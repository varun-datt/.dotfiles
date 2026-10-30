# Flaky tests

A flaky test passes and fails on the same code. Tell a test's own timing assumption from a real
race in the code under test before changing anything: a race in the code is a bug to fix there.

Luo, Hariri, Eloussi and Marinov, ["An Empirical Analysis of Flaky Tests"](https://mir.cs.illinois.edu/lamyaa/publications/fse14.pdf)
(FSE 2014), inspected 201 commits that fixed flaky tests: async wait, concurrency and test order
dependency were the largest categories, and "25 out of 74 (34%) Async Wait flaky tests use sleep
or waitFor with a time delay to enforce ordering."

## Procedure

1. **Reproduce and count.** Run the test alone about 30 times, then in the full suite, then under
   load (below), and note passes and failures at each level. Green alone and red in the suite
   points to order or shared state; green when idle and red under load, to a timing assumption.
2. **Read before you touch.** The failure's trace (Playwright: `unzip trace.zip`, pair the
   `before` and `after` events), the app's logged state at the failure, the timings. Blame the
   framework or the browser last: once, logging inside the app showed that the next view update
   undid the test's own scroll.
3. **Name the kind** from the table below.
4. **Fix the kind across the suite,** not only this test: search for the same pattern (fixed
   sleeps, polls counted in iterations, shared ports) and fix each one.
5. **Prove it under load:** about 30 green runs under the load where it failed. A mutation check
   on intermittent behaviour needs about 30 runs too: 12 of 12 passes with the code disabled once
   nearly got needed code deleted, and the next 12 had a failure.
6. **Ratchet:** a hygiene test that fails when a test file gains a fixed sleep or a shared port.
   Its per-file counts only go down.

## Kinds

| Kind | Sign | Fix |
| --- | --- | --- |
| Fixed sleep standing for "ready" or "saved" | A sleep before acting on something asynchronous | Wait for the effect itself: a condition with a deadline (for example Vitest `vi.waitFor` or `expect.poll`, Playwright's web-first assertions) |
| Poll deadline counted in iterations | `for (i < 100 && !done)` with 20 ms sleeps: 2 s when idle, less time to work under load | A deadline in milliseconds around a condition |
| Fixed sleep standing for "nothing happened" | A short sleep, then an assertion that no event came | A positive signal that the work finished (a later event, a returned promise); where none exists, keep the sleep and count it in the ratchet |
| Real timers in timing logic | Debounce or throttle tests measure wall-clock gaps | Fake timers, advanced by hand and restored after each test |
| OS events late, repeated or missing | A test waits for a file watcher (FSEvents, inotify) to report its own writes | Only tests about the watcher wait on the OS, in their own project run alone; other tests report the event themselves, or create their files before the first scan |
| Slow start near a short deadline | A feature asserted before its server (a language server, a cold process) has answered | Wait for a sign that it answered, then assert |
| Shared ports, folders or state; test order | Passes alone, fails in the suite or when two runs overlap | A temp folder per test; port 0, or a port derived from the process id; no shared mutable fixture |
| Child-process-heavy tests near the timeout | git or subprocess tests time out under load | Share a read-only fixture per file; a longer timeout is not the fix |

Never only lengthen a wait: find what the test is really waiting for, and wait for that.

## Load

- Load like the place it failed, such as a commit hook beside other work. A simple load is 8
  `yes > /dev/null` processes.
- Make the cleanup work in any shell: `kill "${pids[@]}"`, or start the load in its own process
  group and kill the group. A zsh script's `kill $pids` run under bash kills only the first: 7
  processes leaked for about 5 hours at about 5 cores (2026-10-29).
- Start no load while the machine swaps. Before reporting done, `pgrep -x yes | wc -l` prints 0.

## Example

`agent-mission-control`: `docs/testing.md` ("Flaky tests: kinds and rules") and
`scripts/under-load.zsh`.
