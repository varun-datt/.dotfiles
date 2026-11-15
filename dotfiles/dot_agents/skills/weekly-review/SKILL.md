---
name: weekly-review
description: Runs the weekly capture, task, reading, retrieval, and learning review across the personal wiki and the notes repositories it names. Use when the user invokes /weekly-review or asks to close open loops and choose a weekly focus.
disable-model-invocation: true
---

# Run the weekly review

First pick the repository and read its folders and check command ([PARA workflow settings](../vault-validator/references/workflows.md)). The review runs from the personal wiki and also walks each source its `workflows.review_also` names (the work knowledge repo), reading each repository's own settings. Say which repository each item comes from, and when one cannot be read, say so and review the rest.

Keep the review decision-oriented and time-boxed. Prepare actions first; apply file changes only after approval.

## Review in order

Walk every step for each repository in turn, the wiki first, so one item is decided once, in its own repository.

1. **Capture** — inspect dated captures and other inbox items; apply the `inbox-triage` classification rules.
2. **Tasks** — surface overdue and undated open tasks; propose dates, destinations, or removal of completed one-offs.
3. **Closeout** — surface projects whose outcome is explicitly complete/abandoned and areas whose responsibility explicitly ended/transferred. Offer `archive-closeout` for a user-selected candidate; never infer completion from age or archive automatically.
4. **Reading** — show the five oldest queued read-later items of each repository and ask for read, keep, or drop decisions.
5. **Retrieval** — choose a small set of `#review` notes across the repositories and offer one short `quiz`.
6. **Learning** — review active learning workspaces in every repository and choose at most one focus for the week across all of them.
7. **Agent learnings** — read the repository's agent state file. Propose promoting durable gotchas and settled decisions into their owning note; agent-harness material belongs in the repository's agent-notes file when it names one. Clear promoted entries from `state.md`, which holds current state and not a log. Skip when the file is absent.
8. **Maintenance** — when monthly maintenance is due, include stale projects and inactive areas that weekly reviews may have missed; suggest `archive-closeout` only after the user confirms the boundary. Suggest a bounded `tend` pass when due; do not force either workflow.
9. **Summaries** — list the `SUMMARY_STALE` warnings from the repository's check command, one line each, and offer to refresh those summaries; after a check that finds nothing to change, bump `updated` so the warning clears.

Use existing dashboard data when available. Label missing or stale metrics rather than inventing them.

## Weekly record

Create or update `YYYY-Www.md` in each repository's weekly records folder only when the user actually proceeds with the review and that repository has something to record. Do not create empty future records. Follow the repository's required frontmatter and use `type: note`, `status: growing`, and tags `[weekly, review]` unless canonical guidance later adds a weekly type.

Record decisions, deferred items, selected closeout candidates, the chosen learning focus, and unresolved blockers—not a dump of every query result. Each decision goes in the record of the repository it is about; the wiki's record names a work item only as "see the work weekly record", never its content. Record the week's learning focus where its workspace lives. Bump `updated` when modifying an existing record.

End with a concise checklist split into completed actions and decisions still needed. Do not commit, publish, share publicly, or push without separate explicit confirmation.
