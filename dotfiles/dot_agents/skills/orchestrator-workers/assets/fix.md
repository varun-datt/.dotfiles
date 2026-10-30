<!-- Fix-round prompt for a fresh session: prepend preamble-worker.md. One round per item; a further
round goes on the owner's list. Name the session <prefix><item>-fix<N>, and write the worktree's HEAD
to <run>/<item>-fix<N>.base for the re-review diff. -->
THIS IS A FIX ROUND in a fresh session. Branch `{{BRANCH}}` in worktree `{{WORKTREE}}` already holds the item's build: start with `git log --oneline {{ITEM_BASE}}..HEAD` and `git diff --stat {{ITEM_BASE}}`, then read only the files the findings name. Fix only the findings below; do not widen the scope. The item's original brief follows for context.

ORIGINAL BRIEF
{{ORIGINAL_TASK_BODY}}

THIS ROUND
A review of the branch is in.

ACCEPTED, fix these:
1. {{FINDING}}. Evidence: {{FILE_LINE}}. Expected: {{WHAT_DONE_LOOKS_LIKE}}.
{{MORE_ACCEPTED}}

REJECTED by the orchestrator, do not change: {{REJECTED_WITH_ONE_LINE_REASON_OR_NONE}}

ALSO: {{MERGE_MAIN_INTO_BRANCH_OR_INSTALL_STEP_OR_DELETE}}

Corrections to the build's report from the review: {{REPORT_CORRECTIONS_OR_NONE}}

YOUR RESOURCES: worktree `{{WORKTREE}}`, branch `{{BRANCH}}`, ports {{PORTS}}.

Run every gate on the final tree in the foreground and give a labelled report. Mark every claim VERIFIED, INFERRED or OPEN.
