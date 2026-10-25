---
name: repo-atlas
description: Keep a short, refreshable index of the git repositories under one folder, so an agent can tell which repository a question belongs to before searching. Use when asked to "refresh the repos", "update the repo index", "which repo holds X", to pull many repositories at once safely, or to build or update a repos.md / llms.txt-style map of a multi-repo workspace. Not for searching inside repositories (use kb) or for code navigation.
---

# repo-atlas

Two steps, each a subcommand of `scripts/atlas.py`. Every path is an argument; nothing here
names an organisation.

## 1. Refresh

```bash
python3 ~/.agents/skills/repo-atlas/scripts/atlas.py refresh <parent> [--repos a,b] [--dry-run] </dev/null
```

- Fetches every repository directly under `<parent>` in parallel, never prompting for credentials.
- Pulls (`--ff-only`) only when the tree has no uncommitted tracked changes **and** is on the
  default branch. Otherwise it fetches only and says why.
- Prints one JSON line per repo: `before`, `after`, `action`, `behind` (commits the default
  branch is ahead of HEAD). Exit 1 if any fetch failed.
- Run `--dry-run` first on repositories you have not refreshed before: it reads only.

## 2. Facts

```bash
python3 ~/.agents/skills/repo-atlas/scripts/atlas.py facts <parent> --out <dir> [--repos a,b]
```

Writes `<dir>/repos.json` and `<dir>/repos.md` (llms.txt shape: one line per repo, grouped by
`area`). Collected by script: remote, commit and date, the README's first prose sentence, Backstage
`catalog-info.yaml` fields, build manifests, languages, top-level folders, whether AGENTS.md exists.

- An entry is rebuilt only when its **structure fingerprint** (top-level folders plus manifest
  contents) changes, so the file does not churn on every commit.
- `area`, `summary` and `pointers` are **kept by hand** in `repos.json` and never overwritten.
  `summary` replaces the README sentence in `repos.md`. Add one when the README is empty, a
  template, or about tooling rather than the service.

## Known limits (measured on 10 service repositories, 2026-10-24)

- The README's first sentence was a usable summary for 5 of 10; the other 5 need a hand-kept
  `summary` (empty README, template text, a diagram, or a tooling note).
- A Backstage `description` can be a comma-separated list of components shared by several
  repositories rather than a description. It is stored as `catalog.components` and not shown.
- Sentence splitting stops at abbreviations such as "i.e.".
