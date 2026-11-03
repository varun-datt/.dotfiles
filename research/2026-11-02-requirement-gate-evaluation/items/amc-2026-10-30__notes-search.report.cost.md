## REQUIREMENTS MAP

- MUST 1: tests/unit/knowledge.test.ts::the host reads a note only from inside its source's folder, records kb health, and refuses a short query [PASS_TO_PASS]
- MUST 1: tests/unit/knowledge.test.ts::the palette's note search reports a timeout, a failure, bad output and a folder outside every source [PASS_TO_PASS]
- MUST 2: tests/unit/knowledge.test.ts::the host reads a note only from inside its source's folder, records kb health, and refuses a short query [PASS_TO_PASS]
- MUST 2: tests/unit/knowledge.test.ts::the palette's note search reads kb's contract: rows, de-duplicated and capped, openable only for a known source [PASS_TO_PASS]
- MUST 3: tests/unit/analytics.test.ts::records a palette search as counts and the kind of row picked, never its text, and refuses anything else [PASS_TO_PASS]
- MUST 4: tests/unit/knowledge.test.ts::the palette's note search reads kb's contract: rows, de-duplicated and capped, openable only for a known source [PASS_TO_PASS]
- MUST 4: tests/unit/knowledge.test.ts::the palette's note search reports a timeout, a failure, bad output and a folder outside every source [PASS_TO_PASS]
