## REQUIREMENTS MAP

- MUST 1: tests/unit/runs.test.ts::restart while a review card is open: the card comes back with the same actions, and merging it carries the run on to its finish [FAIL_TO_PASS]
- MUST 1: tests/unit/runs.test.ts::a restored card whose orchestrator cannot be opened again says so and offers to end the run, which keeps every worktree and branch [FAIL_TO_PASS]
- MUST 1: tests/unit/runs.test.ts::restart while the finish card is open, with an answer that arrives as the host stops: the answer is refused, the card comes back, and the run merges [FAIL_TO_PASS]
- MUST 2: tests/unit/runs.test.ts::a failed run merge can be tried again: a second failure gives the new reason, two quick presses merge once, and success settles the offer [FAIL_TO_PASS]
- MUST 2: tests/unit/runs.test.ts::a worker merge that stops on a conflict names the files; its retry waits behind the run's running step, then merges as normal [FAIL_TO_PASS]
- MUST 2: tests/e2e/app.spec.ts::a run's failed merge says why and can be tried again, which merges the run [FAIL_TO_PASS]
- MUST 3: tests/unit/runs.test.ts::restart while the finish card is open, with an answer that arrives as the host stops: the answer is refused, the card comes back, and the run merges [FAIL_TO_PASS]
- MUST 3: tests/unit/runs.test.ts::the orchestrator's turn ends on its own while a review card is open: the card stays answerable and merging carries the run on [FAIL_TO_PASS]
- MUST 3: tests/unit/runs.test.ts::a worker merge that stops on a conflict names the files; its retry waits behind the run's running step, then merges as normal [FAIL_TO_PASS]
- MUST 4: tests/unit/runs.test.ts::restart while a review card is open: the card comes back with the same actions, and merging it carries the run on to its finish [FAIL_TO_PASS]
- MUST 4: tests/unit/runs.test.ts::a failed run merge can be tried again: a second failure gives the new reason, two quick presses merge once, and success settles the offer [FAIL_TO_PASS]
- MUST 4: tests/e2e/app.spec.ts::a run's failed merge says why and can be tried again, which merges the run [FAIL_TO_PASS]
