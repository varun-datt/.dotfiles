## REQUIREMENTS MAP

- MUST 1: tests/unit/attachments.test.ts::attachments > inlines up to 64 KB, sends by path above it, and checks the band edges at 2 MB, 5 MB and 100 MB [PASS_TO_PASS]
- MUST 1: tests/unit/attachments.test.ts::attachments > gives the agent a fenced path note with size, type and the data warning, and fences a hostile name [PASS_TO_PASS]
- MUST 1: tests/unit/attachments.test.ts::attachments > keeps refusing a binary or non-UTF-8 file sent by path, judged from its head [PASS_TO_PASS]
- MUST 2: tests/unit/server.test.ts::host server > refuses a file over 5 MB with 428 unless the owner confirmed it, and sends it by path once confirmed [PASS_TO_PASS]
- MUST 2: tests/unit/attachments.test.ts::attachments > asks above 5 MB: refuses an unconfirmed file with 428, and not at or under 5 MB [PASS_TO_PASS]
- MUST 3: tests/unit/attachments.test.ts::attachments > still delivers the message when a file is over 100 MB or gone, tells the owner why, and records a by-path file with its size [PASS_TO_PASS]
- MUST 3: tests/unit/attachments.test.ts::attachments > inlines up to 64 KB, sends by path above it, and checks the band edges at 2 MB, 5 MB and 100 MB [PASS_TO_PASS]
- MUST 4: tests/unit/attachments.test.ts::attachments > gives the agent a fenced path note with size, type and the data warning, and fences a hostile name [PASS_TO_PASS]
- MUST 6: tests/unit/attachments.test.ts::attachments > inlines up to 64 KB, sends by path above it, and checks the band edges at 2 MB, 5 MB and 100 MB [PASS_TO_PASS]
- MUST 6: tests/unit/server.test.ts::host server > refuses a file over 5 MB with 428 unless the owner confirmed it, and sends it by path once confirmed [PASS_TO_PASS]
