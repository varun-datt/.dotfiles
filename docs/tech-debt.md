# Tech debt

Known findings that did not block a merge, kept by `debt.py` (the orchestrator-workers skill). A brief that touches a listed file names its rows and fixes those under about 15 minutes; a class seen 3 times becomes a planned item; past about 30 open rows, each run plans one debt item; a row untouched for 3 runs is re-graded. Edit text outside the table freely.

| Id | Date | Area | Grade | File | Scenario | Source | Minutes | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TD-1 | 2026-10-31 | debt | Minor | dotfiles/dot_agents/skills/orchestrator-workers/scripts/debt.py | A hand-edited table with swapped columns or no separator row is misread, and add can drop the first row | p5-review2 | 15 | open |
| TD-2 | 2026-10-31 | debt | Minor | dotfiles/dot_agents/skills/orchestrator-workers/scripts/debt.py | add and close rewrite CRLF to LF, add a final newline and re-pad existing rows | p5-review2 | 10 | open |
| TD-3 | 2026-10-31 | debt | Minor | dotfiles/dot_agents/skills/orchestrator-workers/scripts/debt.py | Deleting the highest row and the next-id marker reuses its id; two handwritten rows with one id are accepted | p5-review2 | 10 | open |
| TD-4 | 2026-10-31 | debt | Minor | dotfiles/dot_agents/skills/orchestrator-workers/scripts/debt.py | A scenario ending in a newline passes, since trimming runs before the newline check | p5-review2 | 3 | open |
| TD-5 | 2026-10-31 | debt | Minor | dotfiles/dot_agents/skills/orchestrator-workers/scripts/debt.py | A stored file path written as ./src/x.ts matches no for-files query; only query paths are normalised | p5-review2 | 5 | open |
| TD-6 | 2026-10-31 | debt | Minor | dotfiles/dot_agents/skills/orchestrator-workers/scripts/debt.py | import-plan sets every file to ?, even when the passage names one file | p5-review2 | 10 | open |
| TD-7 | 2026-10-31 | debt | Minor | dotfiles/dot_agents/skills/orchestrator-workers/scripts/debt.py | import-plan dry run prints a literal pipe in a scenario as a slash, changing its meaning | p5-review2 | 5 | open |
| TD-8 | 2026-10-31 | debt | Minor | dotfiles/dot_agents/skills/orchestrator-workers/scripts/test_debt.py | The writes-nothing test compares directory entries, not bytes, so an overwrite of PLAN.md survives | p5-review2 | 5 | open |
| TD-9 | 2026-10-31 | debt | Minor | dotfiles/dot_agents/skills/orchestrator-workers/scripts/test_debt.py | Expected dates are taken once, so a run across midnight fails | p5-review2 | 5 | open |
| TD-10 | 2026-10-31 | brief | Minor | dotfiles/dot_agents/skills/orchestrator-workers/scripts/brief.py | Fence toggling ignores the delimiter length, so a 4-backtick example around a 3-backtick fence breaks the MUST count | p1-rereview | 10 | open |
| TD-11 | 2026-10-31 | brief | Minor | dotfiles/dot_agents/skills/orchestrator-workers/scripts/brief.py | The placeholder check refuses quoted prose that shows a {{NAME}} example | p3-review | 10 | open |
| TD-12 | 2026-10-31 | review | Minor | dotfiles/dot_agents/skills/orchestrator-workers/scripts/review.sh | review.sh stages through a fixed <out>.tmp name, so a source prompt at that path is removed by the rename | p3-review, p3-rereview | 5 | open |
| TD-13 | 2026-10-31 | templates | Minor | dotfiles/dot_agents/skills/orchestrator-workers/assets/rereview.md | The fix and re-review templates disagree on whether evidence that a case cannot happen may stand in for a test (assets/fix.md vs assets/rereview.md:28) | p3-review | 10 | open |
| TD-14 | 2026-10-31 | orchestrator-workers | Minor | dotfiles/dot_agents/skills/orchestrator-workers/references/routing.md | routing.md:49 still says a round's kind comes from its name suffix only; since p4 it comes from the routes.jsonl launch record first | p4-rereview2, 2026-10-31 | 5 | open |
| TD-15 | 2026-10-31 | orchestrator-workers | Minor | dotfiles/dot_agents/skills/orchestrator-workers/scripts/brief.py | brief check --repo reads docs/tech-debt.md through a docs/ symlink, so a linked docs folder lets a register outside the repository be read (containment is lexical) | p6 reviews, 2026-10-31 | 15 | open |
| TD-16 | 2026-10-31 | orchestrator-workers | Minor | dotfiles/dot_agents/skills/orchestrator-workers/scripts/debt.py | brief check takes about 4 s on a large register (estimated, not remeasured after the fix) | p6 reviews, 2026-10-31 | 20 | open |
<!-- debt.py next id: 17 -->
