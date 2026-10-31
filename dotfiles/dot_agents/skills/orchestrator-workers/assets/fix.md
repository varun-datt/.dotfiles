<!-- Fix-round prompt for a fresh session: prepend preamble-worker.md. Name the session
<prefix><item>-fix<N>, and write the worktree's HEAD to <run>/<item>-fix<N>.base for the re-review diff.
A finding names one case; in the 2026-10-27 to 10-30 runs, 31 of 133 accepted blocking findings were a
sibling an earlier fix had left (22) or a regression a fix introduced (9), so this round fixes the class. -->
THIS IS A FIX ROUND in a fresh session. Branch `{{BRANCH}}` in worktree `{{WORKTREE}}` already holds the item's build: start with `git log --oneline {{ITEM_BASE}}..HEAD` and `git diff --stat {{ITEM_BASE}}`, then read the files the findings name. The item's original brief follows for context.

ORIGINAL BRIEF
{{ORIGINAL_TASK_BODY}}

THE BUILD'S REPORT, with its impact map and case table: `{{BUILD_REPORT_PATH}}` (read-only; the orchestrator copied it from the build round).

THIS ROUND
A review of the branch is in.

ACCEPTED, fix these, each as a class:
1. {{FINDING}}. Evidence: {{FILE_LINE}}. Class: {{CLASS_FOR_EXAMPLE_ANOTHER_SEND_PATH_A_LATE_EVENT_AFTER_STOP_A_ROOT_SPELLED_ANOTHER_WAY}}. Expected: {{WHAT_DONE_LOOKS_LIKE}}.
{{MORE_ACCEPTED}}

For each finding:
- Reproduce it first: a test that fails on the current branch for the reason the finding gives.
- Name its class and list every member your impact map finds (the other paths, orders, spellings or record formats where the same fault can occur), each with a test or a line saying why it cannot happen.
- Fix the class, then prove each test fails with its fix removed (mutation check).
- Re-run the case table from the build's report for what your change touches, and say which rows changed.
Do not change behaviour outside these classes.

REJECTED by the orchestrator, do not change: {{REJECTED_WITH_ONE_LINE_REASON_OR_NONE}}

ALSO: {{MERGE_MAIN_INTO_BRANCH_OR_INSTALL_STEP_OR_DELETE}}

Corrections to the build's report from the review: {{REPORT_CORRECTIONS_OR_NONE}}

YOUR RESOURCES: worktree `{{WORKTREE}}`, branch `{{BRANCH}}`, ports {{PORTS}}.

Run every gate on the final tree in the foreground and give a labelled report, with the class list for each finding. Mark every claim VERIFIED, INFERRED or OPEN.
