---
name: weekly-review
description: Runs the vault's weekly capture, task, reading, retrieval, and learning review. Use when the user invokes /weekly-review or asks to close open loops and choose a weekly focus.
disable-model-invocation: true
---

# Run the weekly review

First pick the repository and read its folders and check command ([PARA workflow settings](../vault-validator/references/workflows.md)).

Keep the review decision-oriented and time-boxed. Prepare actions first; apply file changes only after approval.

## Review in order

1. **Capture** — inspect dated captures and other inbox items; apply the `inbox-triage` classification rules.
2. **Tasks** — surface overdue and undated open tasks; propose dates, destinations, or removal of completed one-offs.
3. **Closeout** — surface projects whose outcome is explicitly complete/abandoned and areas whose responsibility explicitly ended/transferred. Offer `archive-closeout` for a user-selected candidate; never infer completion from age or archive automatically.
4. **Reading** — show the five oldest queued read-later items and ask for read, keep, or drop decisions.
5. **Retrieval** — choose a small set of `#review` notes and offer one short `quiz`.
6. **Learning** — review active learning workspaces and choose at most one focus for the week.
7. **Agent learnings** — read the repository's agent state file. Propose promoting durable gotchas and settled decisions into their owning note; agent-harness material belongs in the repository's agent-notes file when it names one. Clear promoted entries from `state.md`, which holds current state and not a log. Skip when the file is absent.
8. **Maintenance** — when monthly maintenance is due, include stale projects and inactive areas that weekly reviews may have missed; suggest `archive-closeout` only after the user confirms the boundary. Suggest a bounded `tend` pass when due; do not force either workflow.
9. **Summaries** — list the `SUMMARY_STALE` warnings from the repository's check command, one line each, and offer to refresh those summaries; after a check that finds nothing to change, bump `updated` so the warning clears.

Use existing dashboard data when available. Label missing or stale metrics rather than inventing them.

## Weekly record

Create or update `YYYY-Www.md` in the weekly records folder only when the user actually proceeds with the review. Do not create empty future records. Follow the repository's required frontmatter and use `type: note`, `status: growing`, and tags `[weekly, review]` unless canonical guidance later adds a weekly type.

Record decisions, deferred items, selected closeout candidates, the chosen learning focus, and unresolved blockers—not a dump of every query result. Bump `updated` when modifying an existing record.

End with a concise checklist split into completed actions and decisions still needed. Do not commit, publish, share publicly, or push without separate explicit confirmation.
