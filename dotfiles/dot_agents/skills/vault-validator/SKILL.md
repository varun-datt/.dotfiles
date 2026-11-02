---
name: vault-validator
description: "Checks a Markdown notes repository (the personal wiki, a work knowledge repo) against the rules that repository keeps in its own vault-validator.json: front matter fields and values, dated note names, broken wikilinks, recurring tasks without a date, required files and skills. Use before committing notes, when a repo's check fails, or when adding the same checks to another notes repo."
---

# vault-validator

One engine, many rule sets. The checks live here; each repository owns its rules as data in
`vault-validator.json` at its root, so the engine holds nothing about any one repository.

## Run it

```sh
python3 ~/.agents/skills/vault-validator/scripts/vault_validator.py --root <repo>
```

- `--rules <file>` names another rules file; `--today YYYY-MM-DD` makes date checks repeatable;
  `--baseline <file>` lists accepted debt, downgraded from error to warning.
- Exit 0 means no errors, 1 means errors, 2 means the rules file is missing.
- A repository can keep a thin `scripts/vault_validator.py` that loads this engine with its rules,
  as the wiki does, so `make check` and its own tests keep working.

## Rules file

A section that is absent switches its check off. The wiki's file is the full example:

| Key | Check |
| --- | --- |
| `note_roots`, `skip_names` | Which folders hold notes; file names skipped |
| `required_fields`, `types`, `statuses`, `type_fields`, `date_fields` | Front matter fields and values |
| `contexts`, `mixed_context` | Allowed `context:` values, and where an exception applies |
| `dated_types`, `dated_month_ok` | Dated notes are named after their `date:`; `YYYY-MM` allowed when the day is unknown |
| `read_later`, `inbox`, `retention_tags` | Wiki workflow warnings |
| `summaries` | Warns (`SUMMARY_STALE`) when a note of a listed type is older than a note it links to by more than `grace_days`; links under `skip_prefixes` are not counted |
| `skills` | Required skills, name and description checks, required references |
| `required_files`, `obsidian_plugins`, `operator_guide`, `tend_state` | Repository furniture |
| `baseline` | Default accepted-debt file |

Rules are data: never put names, employers or other private values in this skill; they belong in
the calling repository's file.

## Test it

```sh
python3 -m unittest discover -s ~/.local/share/chezmoi/dotfiles/dot_agents/skills/vault-validator/scripts
```
