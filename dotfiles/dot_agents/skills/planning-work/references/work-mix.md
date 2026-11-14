# Work mix for an unattended run

The mix of kinds is reported after a run, never planned: the value scores alone fill a plan
([value.md](value.md)). The split below, built from the sources in the wiki note
`00-inbox/research-agent-work-planning/findings-work-mix.md`, is only a reference to read a
run's reported mix against.

| Kind of work | Reference share | What counts |
| --- | --- | --- |
| Features | about 70% | Backlog items with their decisions taken, one at a time, each with its own tests and doc updates, each ending in a commit with the full check passing |
| Bugs and fixes | about 15% | High severity first; review findings below high go to the backlog |
| Spikes and research | about 10% | Only those that unblock a decision or a planned feature |
| Docs and process | about 5% | What the next session or the owner needs |

Dependencies still order the plan:

- An enabler goes first: a spike, fix or piece of debt that a planned feature needs, or that makes
  it clearly faster or safer to build, comes before that feature whatever its kind. "For each
  desired change, make the change easy (warning: this may be hard), then make the easy change"
  (Kent Beck, quoted by
  [taro.codes](https://taro.codes/posts/2019-10-01-make-the-change-easy)). SAFe's enablers "define
  the work needed to develop and deliver future business requirements" and "must be visible and
  treated like other backlog items" ([SAFe](https://framework.scaledagile.com/enablers)).
- An enabler counts toward the feature it serves. Log it with `--serves <feature id>`;
  `estimates.py report` shows features with their enablers as one share.
- Work that serves no planned feature is not an enabler, and is ranked on its own score.
- When a feature turns out to need an enabler mid-run, take the enabler next and re-forecast; say
  in the plan which feature each enabler serves.

- Plan below full capacity: the plan fills the forecast's P50, not every minute
  ("Agile Planning to 100% Capacity? Don't Do It!", Scaled Agile).
- Polish found on the way becomes backlog items (AMC's light rule 8; Shape Up batches bugs and
  polish into a cool-down instead of interrupting feature time).
- After the plan: depth, with at most two second-model review rounds, fixing high severity only.
- Report the split that happened (`estimates.py report`). On 2026-10-25 it was 22% features and
  53% fixes and review rounds, because the plan ran out early.
