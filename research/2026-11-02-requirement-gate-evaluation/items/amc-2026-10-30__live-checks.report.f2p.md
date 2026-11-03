## REQUIREMENTS MAP

- MUST 1: tests/live/workflows.live.test.ts::workflows on real Copilot > tool-search [FAIL_TO_PASS]
- MUST 1: tests/live/workflows.live.test.ts::workflows on real Copilot > run-findings [FAIL_TO_PASS]
- MUST 2: tests/unit/one-shot.test.ts::Copilot tool search option > reaches the session config only when set [FAIL_TO_PASS]
- MUST 2: tests/live/workflows.live.test.ts::workflows on real Copilot > tool-search [FAIL_TO_PASS]
- MUST 3: none (running the live suite on the default model within the budget is an operational step; the live cap check has a computed title and was skipped)
- MUST 4: none (recording passed workflows after a leak scan is an operational step; the live test's leak scan predates the branch and no test checks recording)
- MUST 5: tests/unit/transcript.test.ts::buildView > shows a hand-over summary without the model's analysis block [FAIL_TO_PASS]
- MUST 5: tests/e2e/app.spec.ts::opens the full summary from the glance card, writes it once, switches back to the card, and counts the messages since the card [FAIL_TO_PASS]
