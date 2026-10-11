<!-- Task body, appended after a preamble. One work item per body. -->
TASK: {{ITEM_TITLE}} (branch `{{BRANCH}}`, worktree `{{WORKTREE}}`, based on `{{BASE_COMMIT}}`)

GOAL
{{GOAL_IN_TWO_OR_THREE_SENTENCES}}

MUST (each one is checked by the reviewer)
1. {{MUST_1}}
2. {{MUST_2}}

ACCEPTANCE
{{ACCEPTANCE_ROWS_OR_TESTS_THAT_PROVE_IT}}

SOURCES TO READ: {{PLAN_SECTIONS_DECISIONS_PROPOSALS}}

OWNER RULINGS THAT APPLY (do not re-decide): {{RULINGS_OR_NONE}}

OUT OF SCOPE: {{OUT_OF_SCOPE}}. Files another session is changing right now, do not edit: {{CONTESTED_FILES_OR_NONE}}.

YOUR RESOURCES: ports {{PORTS}}; install port {{INSTALL_PORT}}; reserved ids or version numbers {{RESERVED_IDS_OR_NONE}}.

TIME BUDGET: {{BUDGET_MIN}} minutes. If you are past it, finish the current piece, commit, run the gates and report what is left.
