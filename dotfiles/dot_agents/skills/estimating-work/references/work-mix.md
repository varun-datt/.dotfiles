# Work mix for an unattended run

The default split of the plan, unless the owner sets another before leaving. No study gives one
right split; this one is built from the sources in the wiki note
`00-inbox/research-agent-work-planning/findings-work-mix.md`.

| Kind of work | Share of the plan | What counts |
| --- | --- | --- |
| Features | about 70% | Backlog items with their decisions taken, one at a time, each with its own tests and doc updates, each ending in a commit with the full check passing |
| Bugs and fixes | about 15% | High severity first; review findings below high go to the backlog |
| Spikes and research | about 10% | Only those that unblock a decision or a planned feature |
| Docs and process | about 5% | What the next session or the owner needs |

- Plan below full capacity: the plan fills the forecast's P50, not every minute
  ("Agile Planning to 100% Capacity? Don't Do It!", Scaled Agile).
- Polish found on the way becomes backlog items (AMC's light rule 8; Shape Up batches bugs and
  polish into a cool-down instead of interrupting feature time).
- After the plan: depth, with at most two second-model review rounds, fixing high severity only
  (owner, 2026-10-25).
- Report the split that happened (`estimates.py report`) beside the split asked for. On
  2026-10-25 it was 22% features and 53% fixes and review rounds, because the plan ran out early.
