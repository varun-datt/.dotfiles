## REQUIREMENTS MAP

- MUST 1: tests/unit/knowledge.test.ts::the host reads a note only from inside its source's folder, records kb health, and refuses a short query [FAIL_TO_PASS]
- MUST 1: tests/unit/knowledge.test.ts::the palette's note search reports a timeout, a failure, bad output and a folder outside every source [FAIL_TO_PASS]
- MUST 1: tests/e2e/app.spec.ts::the palette's Notes group shows kb's notes beside the other groups, says when it is slow or failed, and opens a note read-only [FAIL_TO_PASS]
- MUST 2: tests/unit/knowledge.test.ts::the host reads a note only from inside its source's folder, records kb health, and refuses a short query [FAIL_TO_PASS]
- MUST 2: tests/unit/knowledge.test.ts::the palette's note search reads kb's contract: rows, de-duplicated and capped, openable only for a known source [FAIL_TO_PASS]
- MUST 2: tests/e2e/app.spec.ts::the palette's Notes group shows kb's notes beside the other groups, says when it is slow or failed, and opens a note read-only [FAIL_TO_PASS]
- MUST 3: tests/unit/analytics.test.ts::records a palette search as counts and the kind of row picked, never its text, and refuses anything else [FAIL_TO_PASS]
- MUST 3: tests/e2e/app.spec.ts::the palette's Notes group shows kb's notes beside the other groups, says when it is slow or failed, and opens a note read-only [FAIL_TO_PASS]
- MUST 3: tests/e2e/app.spec.ts::measures palette searches that find nothing or get no pick, without sending what was typed [FAIL_TO_PASS]
- MUST 4: tests/unit/knowledge.test.ts::the palette's note search reads kb's contract: rows, de-duplicated and capped, openable only for a known source [FAIL_TO_PASS]
- MUST 4: tests/unit/knowledge.test.ts::the palette's note search reports a timeout, a failure, bad output and a folder outside every source [FAIL_TO_PASS]
- MUST 4: tests/e2e/app.spec.ts::the palette's Notes group shows kb's notes beside the other groups, says when it is slow or failed, and opens a note read-only [FAIL_TO_PASS]
