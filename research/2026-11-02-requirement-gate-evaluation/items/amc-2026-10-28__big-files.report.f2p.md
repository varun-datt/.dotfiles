## REQUIREMENTS MAP

- MUST 1: tests/unit/attachments.test.ts::attachments > inlines up to 64 KB, sends by path above it, and checks the band edges at 2 MB, 5 MB and 100 MB [FAIL_TO_PASS]
- MUST 1: tests/unit/attachments.test.ts::attachments > gives the agent a fenced path note with size, type and the data warning, and fences a hostile name [FAIL_TO_PASS]
- MUST 1: tests/unit/attachments.test.ts::attachments > keeps refusing a binary or non-UTF-8 file sent by path, judged from its head [FAIL_TO_PASS]
- MUST 2: tests/unit/server.test.ts::host server > refuses a file over 5 MB with 428 unless the owner confirmed it, and sends it by path once confirmed [FAIL_TO_PASS]
- MUST 2: tests/unit/attachments.test.ts::attachments > asks above 5 MB: refuses an unconfirmed file with 428, and not at or under 5 MB [FAIL_TO_PASS]
- MUST 2: tests/e2e/app.spec.ts::asks before sending a file over 5 MB: Cancel and Escape keep the draft, Send delivers it by path [FAIL_TO_PASS]
- MUST 3: tests/unit/attachments.test.ts::attachments > still delivers the message when a file is over 100 MB or gone, tells the owner why, and records a by-path file with its size [FAIL_TO_PASS]
- MUST 3: tests/unit/attachments.test.ts::attachments > inlines up to 64 KB, sends by path above it, and checks the band edges at 2 MB, 5 MB and 100 MB [FAIL_TO_PASS]
- MUST 4: tests/unit/attachments.test.ts::attachments > gives the agent a fenced path note with size, type and the data warning, and fences a hostile name [FAIL_TO_PASS]
- MUST 5: none (no test checks either engine adapter's outgoing payload for a by-path attachment; both use the shared documents block, verified only by reading source)
- MUST 6: tests/unit/attachments.test.ts::attachments > inlines up to 64 KB, sends by path above it, and checks the band edges at 2 MB, 5 MB and 100 MB [FAIL_TO_PASS]
- MUST 6: tests/unit/server.test.ts::host server > refuses a file over 5 MB with 428 unless the owner confirmed it, and sends it by path once confirmed [FAIL_TO_PASS]
- MUST 6: tests/e2e/app.spec.ts::asks before sending a file over 5 MB: Cancel and Escape keep the draft, Send delivers it by path [FAIL_TO_PASS]
