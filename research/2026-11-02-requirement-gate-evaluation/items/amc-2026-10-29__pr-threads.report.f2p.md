## REQUIREMENTS MAP

- MUST 1: tests/unit/ado.test.ts::Azure DevOps work items > reads a pull request's changed files, renames included, and every human thread with nested replies, open ones first [FAIL_TO_PASS]
- MUST 1: tests/e2e/app.spec.ts::a thread on a line shows under that line in the diff with its author, photo, age and status, read-only [FAIL_TO_PASS]
- MUST 1: tests/e2e/app.spec.ts::a pull request opens on its sanitised description, lists its changed files with a read-only side-by-side diff, and shows its threads nested [FAIL_TO_PASS]
- MUST 2: tests/e2e/app.spec.ts::resolved threads on a file are hidden behind one quiet line that shows them [FAIL_TO_PASS]
- MUST 3: tests/unit/ado-overview.test.ts::pull request overview: what blocks it > lists merge conflicts, open threads with their one file, and a draft [FAIL_TO_PASS]
- MUST 3: tests/e2e/app.spec.ts::a thread on no file shows in the Overview's discussion [FAIL_TO_PASS]
- MUST 3: tests/e2e/app.spec.ts::the pull request overview lists a threads blocker: 3 open threads in ExportSettings.tsx [FAIL_TO_PASS]
- MUST 4: tests/unit/ado-overview.test.ts::pull request overview: what blocks it > names who rejected it and who waits for the author, each pointing at the threads [FAIL_TO_PASS]
- MUST 4: tests/e2e/app.spec.ts::a pull request opens on its sanitised description, lists its changed files with a read-only side-by-side diff, and shows its threads nested [FAIL_TO_PASS]
- MUST 5: tests/e2e/app.spec.ts::fifty open threads in one file all show under their lines and the diff still scrolls [FAIL_TO_PASS]
- MUST 6: tests/e2e/app.spec.ts::a thread on a line shows under that line in the diff with its author, photo, age and status, read-only [FAIL_TO_PASS]
- MUST 6: tests/e2e/app.spec.ts::resolved threads on a file are hidden behind one quiet line that shows them [FAIL_TO_PASS]
- MUST 6: tests/e2e/app.spec.ts::fifty open threads in one file all show under their lines and the diff still scrolls [FAIL_TO_PASS]
- MUST 7: tests/e2e/app.spec.ts::at 900 px wide the Files diff switches to inline [FAIL_TO_PASS]
- MUST 7: tests/e2e/app.spec.ts::the Files tree folds folders with their totals, counts lines and threads per file, and folds the lock and generated files under one row that says why [FAIL_TO_PASS]
- MUST 8: none (a render-and-inspect step for the worker's report, not something a test checks)
