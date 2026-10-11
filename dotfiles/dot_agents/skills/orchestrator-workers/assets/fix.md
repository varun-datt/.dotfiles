<!-- Fix-round prompt, sent with `copilot -r <prefix><item>` (the author's own session keeps its context).
Name the run <item>-fix<N>; write the base commit to <run>/<item>-fix<N>.base for the re-review diff. -->
The review of your branch is in. Fix the findings below, then run every gate on the final tree in the foreground and give the full report your task asked for.

ACCEPTED, fix these:
1. {{FINDING}}. Evidence: {{FILE_LINE}}. Expected: {{WHAT_DONE_LOOKS_LIKE}}.
{{MORE_ACCEPTED}}

REJECTED by the orchestrator, do not change: {{REJECTED_WITH_ONE_LINE_REASON_OR_NONE}}

ALSO: {{MERGE_MAIN_INTO_BRANCH_OR_INSTALL_STEP_OR_DELETE}}

Corrections to your report from the review: {{REPORT_CORRECTIONS_OR_NONE}}

Mark every claim VERIFIED, INFERRED or OPEN.
