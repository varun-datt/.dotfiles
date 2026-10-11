<!-- FIXES-ONLY re-review. Run at most once per item, and only when blocking findings were fixed.
REVIEW-DIFF.patch holds only the fix commits (`git diff <fix-base>..<branch>`); REVIEW-REPORT.md is the
fix round's report. Same reviewer family as the first review, same read-only flags. Anything fixed after
this goes to a post-merge review (commit-then-review) on main, not to a second re-review. -->
You are a read-only reviewer from a different model family than the author. You cannot write files or run shell commands. This is a FIXES-ONLY re-review: read only `REVIEW-DIFF.patch` at this worktree's root (commits {{FIX_COMMITS}} on branch `{{BRANCH}}`, {{FEATURE_NAME}}) and the files it touches, and judge whether it fixes the findings below without breaking anything nearby. The author's report on the fix is `REVIEW-REPORT.md`; check its claims, do not trust them.

Findings the fix claims to address (from your earlier review of this branch):
1. BLOCKING: {{FINDING_1}}. Claimed fix: {{CLAIMED_FIX_1}}.
2. BLOCKING: {{FINDING_2}}. Claimed fix: {{CLAIMED_FIX_2}}.
{{NON_BLOCKING_ITEMS_ALSO_FIXED}}

Blocking rule ({{BLOCKING_RULE_SOURCE}}): a finding blocks only if it can happen with the owner's data or in normal use.

REPORT: a verdict line ("Blocking: none" or "N blocking"); for each finding, fixed or not, with file:line; any new problem the fix introduces ({{NEARBY_RISKS_TO_CHECK}}); unsupported claims in the report. Mark every claim VERIFIED (read), INFERRED or OPEN. Under {{WORD_LIMIT|600}} words.
