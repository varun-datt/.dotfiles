## REQUIREMENTS MAP

- MUST 1: tests/unit/history.test.ts::Copilot CLI: counts a normal session's facets by rule [FAIL_TO_PASS]
- MUST 1: tests/unit/history.test.ts::VS Code: replays the chat mutation log and counts its facets [FAIL_TO_PASS]
- MUST 1: tests/unit/history.test.ts::reads incrementally: only files changed since the last read are parsed again, and broken ones are counted as skipped [FAIL_TO_PASS]
- MUST 2: tests/unit/history.test.ts::Copilot CLI: a truncated last line and unknown events are skipped, the rest still counts [FAIL_TO_PASS]
- MUST 2: tests/unit/history.test.ts::a missing source shows nothing, and links out of a history folder are not followed [FAIL_TO_PASS]
- MUST 2: tests/unit/history.test.ts::a linked folder anywhere below a root is not followed [FAIL_TO_PASS]
- MUST 3: tests/unit/history.test.ts::a missing source shows nothing, and links out of a history folder are not followed [FAIL_TO_PASS]
- MUST 3: tests/e2e/app.spec.ts::Insights shows Copilot CLI and VS Code history as their own groups, with a source filter and the sessions that could not be read [FAIL_TO_PASS]
- MUST 4: none (no test checks that history data is not sent to a model, logged or written outside the store)
- MUST 5: tests/unit/history.test.ts::reads incrementally: only files changed since the last read are parsed again, and broken ones are counted as skipped [FAIL_TO_PASS]
- MUST 5: tests/unit/history.test.ts::a large snapshot is parsed off the host thread, so the host's timers keep firing [FAIL_TO_PASS]
- MUST 6: tests/unit/history.test.ts::Copilot CLI: a truncated last line and unknown events are skipped, the rest still counts [FAIL_TO_PASS]
- MUST 6: tests/unit/history.test.ts::VS Code: a huge session is replayed [FAIL_TO_PASS]
- MUST 6: tests/unit/history.test.ts::reads incrementally: only files changed since the last read are parsed again, and broken ones are counted as skipped [FAIL_TO_PASS]
