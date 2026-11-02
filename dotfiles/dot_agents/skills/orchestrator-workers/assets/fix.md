<!-- Fix-round prompt for a fresh session: prepend preamble-worker.md. Name the session
<prefix><item>-fix<N>, and write the worktree's HEAD to <run>/<item>-fix<N>.base for the re-review diff.
Narrow by ruling (owner, 2026-11-02): fix rounds cost more than builds (6,569 against 6,421 credits)
because each re-read the item and redid the whole build method; a kind with no end of cases goes to
the structural fix and the owner, not to another round. -->
THIS IS A FIX ROUND in a fresh session, for {{ITEM_TITLE}}. Branch `{{BRANCH}}` in worktree `{{WORKTREE}}` already holds the item's build. Read only the files the findings name and the tests next to them; do not re-read the item's brief or the build's report.

THIS ROUND REPLACES the preamble's "HOW TO BUILD" and "REPORT" sections: no impact map, no case table, no facts survey and no mutation runs. Everything else in the preamble holds.

FIX THESE, one at a time:
1. {{FINDING}}. Where: {{FILE_LINE}}. What goes wrong: {{SCENARIO}}. Done when: {{WHAT_DONE_LOOKS_LIKE}}. {{CLOSED_CLASS_LIST_OR_DELETE}}
{{MORE_FINDINGS}}

For each finding:
1. Write one test that fails on the current branch for the reason the finding gives, and show it failing.
2. Fix the code, and show the same test passing.
3. When the finding lists every case of its kind ("Cases:"), cover each listed case the same way. Otherwise fix only the case named; if you see other cases of the same kind, list them in your report under "Same kind, not fixed" with file:line, and do not hunt for more.
Do not change behaviour outside these findings.
{{UI_RENDER_STEP_OR_DELETE}}

NOT TO CHANGE (rejected by the orchestrator): {{REJECTED_WITH_ONE_LINE_REASON_OR_NONE}}

REUSE CHECK: not needed: this round fixes named findings and adds no new functionality; if a fix would need one, stop that finding and say so.
ALLOWED DEPENDENCIES: none

CHECKS: run on the final tree, in the foreground: the type check, lint on the files you changed, and the test files for the modules you changed ({{CHECK_COMMANDS}}). The merge gate runs the full suite after you.

YOUR RESOURCES: worktree `{{WORKTREE}}`, branch `{{BRANCH}}`, ports {{PORTS}}.

REPORT, your final message, plain words: per finding, the test's name, its failing and passing output in one line each, and the commit; "Same kind, not fixed" with file:line; the checks with their numbers and commands; anything you could not do and why. Mark every claim VERIFIED, INFERRED or OPEN.
