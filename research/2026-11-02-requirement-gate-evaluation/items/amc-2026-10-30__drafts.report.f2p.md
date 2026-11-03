## REQUIREMENTS MAP

- MUST 1: tests/unit/drafts.test.ts::changeDrafts > adds, edits, removes, clears sent pieces and discards all [FAIL_TO_PASS]
- MUST 1: tests/e2e/app.spec.ts::gathers draft pieces from a reply and a file line, edits and removes them, keeps them over a reload and sends them as one message [FAIL_TO_PASS]
- MUST 2: tests/unit/drafts.test.ts::changeDrafts > adds, edits, removes, clears sent pieces and discards all [FAIL_TO_PASS]
- MUST 2: tests/e2e/app.spec.ts::gathers draft pieces from a reply and a file line, edits and removes them, keeps them over a reload and sends them as one message [FAIL_TO_PASS]
- MUST 3: tests/unit/drafts.test.ts::composeDraft > sends each piece's quoted anchor, its file and line, and its note, then the owner's text [FAIL_TO_PASS]
- MUST 3: tests/unit/drafts.test.ts::composeDraft > names a single piece without a count, and leaves the owner's text alone when there are no pieces [FAIL_TO_PASS]
- MUST 3: tests/e2e/app.spec.ts::gathers draft pieces from a reply and a file line, edits and removes them, keeps them over a reload and sends them as one message [FAIL_TO_PASS]
- MUST 4: tests/unit/drafts.test.ts::changeDrafts > keeps anchors inside the session's folder and refuses empty quotes and unknown pieces [FAIL_TO_PASS]
- MUST 4: tests/e2e/app.spec.ts::gathers draft pieces from a reply and a file line, edits and removes them, keeps them over a reload and sends them as one message [FAIL_TO_PASS]
- MUST 5: none (no test adds or sends pieces while a turn is running)
- MUST 6: tests/unit/drafts.test.ts::composeDraft > sends each piece's quoted anchor, its file and line, and its note, then the owner's text [FAIL_TO_PASS]
- MUST 6: tests/e2e/app.spec.ts::gathers draft pieces from a reply and a file line, edits and removes them, keeps them over a reload and sends them as one message [FAIL_TO_PASS]
