<!-- Task body, appended after a preamble. One work item per body. brief.py refuses a worker brief
whose MUST lines are not testable statements, or that lacks a RISK, CASES or FACTS TO VERIFY line.
Split an item the orchestrator expects to take over 45 minutes, or one that touches two of the
project's hot spots (turn and run state, file containment, a shared view's state), into two items. -->
TASK: {{ITEM_TITLE}} (branch `{{BRANCH}}`, worktree `{{WORKTREE}}`, based on `{{BASE_COMMIT}}`)

GOAL
{{GOAL_IN_TWO_OR_THREE_SENTENCES}}

MUST (each is checked by the reviewer; each is one testable statement, "WHEN <event or state>, <the part> SHALL <response>", with the cases that prove it)
1. WHEN {{EVENT_OR_STATE}}, {{PART}} SHALL {{RESPONSE}}. Cases: {{CASES_FOR_MUST_1}}.
2. {{MUST_2}}

ACCEPTANCE
{{ACCEPTANCE_ROWS_OR_TESTS_THAT_PROVE_IT}}

RISK: {{ONE_OR_MORE_OF host-state, boundary, data, UI, dotfiles, test-suite}}

CASES THE ORCHESTRATOR KNOWS: {{SIBLING_PATHS_EVENT_ORDERS_OLD_RECORD_FORMATS_AND_EARLIER_FINDINGS_IN_THESE_FILES_OR_NONE}}

FACTS TO VERIFY: {{LIBRARY_PLATFORM_OR_VENDOR_BEHAVIOUR_THE_DESIGN_RESTS_ON_WITH_WHERE_TO_CHECK_EACH_OR_NONE}}

SOURCES TO READ: {{PLAN_SECTIONS_DECISIONS_PROPOSALS_AND_THE_CONVENTIONS_THAT_APPLY}}

OWNER RULINGS THAT APPLY (do not re-decide): {{RULINGS_OR_NONE}}

REUSE CHECK: {{ESTABLISHED_LIBRARIES_FRAMEWORKS_SKILLS_TOOLS_STANDARDS_AND_PATTERNS_RESEARCHED_PLUS_IN_REPO_HELPERS_WITH_WHY_EACH_IS_USED_OR_NOT_OR_WHY_THERE_IS_NO_NEW_FUNCTIONALITY}}
ALLOWED DEPENDENCIES: {{NAMED_PACKAGES_OR_NONE}}

TECH DEBT: {{TD_IDS_FROM_DEBT_PY_FOR_FILES_TO_FIX_WITH_THEIR_LINES_OR_WHY_NOT_OR_NONE}}

OUT OF SCOPE: {{OUT_OF_SCOPE}}. Files another session is changing right now, do not edit: {{CONTESTED_FILES_OR_NONE}}.

YOUR RESOURCES: ports {{PORTS}}; install port {{INSTALL_PORT}}; reserved ids or version numbers {{RESERVED_IDS_OR_NONE}}.

TIME BUDGET: {{BUDGET_MIN}} minutes. If you are past it, finish the current piece, commit, run the gates and report what is left, with the case table as far as it got.
