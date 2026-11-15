# PARA workflow settings

The PARA workflow skills (inbox-triage, read-later-digest, weekly-review, archive-closeout, tend,
moc-builder, learning, quiz) work in any notes repository that has a `vault-validator.json`. They
take every folder and command from that file, never from their own text, so the same task runs the
same way in each repository.

## Pick the repository

1. The repository the owner names, by its source name in `~/.config/kb/sources.json` (for example
   `wiki` or `work`).
2. Else the nearest folder at or above the current one that holds `vault-validator.json`.
3. Else ask which source. Never write while unsure which repository a change belongs to.

A finding about one repository is written in that repository. Work content never goes into the
personal wiki, whose commit check refuses it.

## Settings

| Setting in `vault-validator.json` | Meaning |
| --- | --- |
| `inbox.folder` | The inbox; `inbox.skip` names the read-later queue inside it |
| `workflows.read_later` | The read-later queue |
| `workflows.archive` | Where closed-out work moves |
| `workflows.resources` | Where durable reference knowledge lives |
| `workflows.maps` | Where Maps of Content live |
| `workflows.weekly` | Where weekly review records go |
| `workflows.review_also` | Other sources, by name in `sources.json`, that a weekly review run from this repository walks too |
| `workflows.learn` | Where learning workspaces live |
| `workflows.check` | The command that runs the repository's checks |
| `workflows.state` | The agent state file the weekly review reads |
| `workflows.agent_notes` | Where agent-harness learnings are promoted |
| `tend_state` | The tend run marker |
| `contexts` | Allowed `context:` values; when absent, notes carry no `context:` field |
| `required_fields`, `types`, `statuses`, `type_fields` | Front matter for any note a skill creates |

A setting that is absent means its step does not apply in that repository: say so and skip the step.
Add a Dataview block only where the repository has an `.obsidian/` folder.
