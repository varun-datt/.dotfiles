---
name: commit-guard
description: "Blocks a commit that adds an employer identifier (redaction patterns, work repository names, organisation URLs) or a secret (gitleaks) to a repository that must not hold one, such as a personal wiki or public dotfiles. Use when setting up or debugging that pre-commit check, or when it refuses a commit."
---

# commit-guard

A pre-commit check for repositories that must stay free of work content. The block lists live
outside every repository, so the check itself can be public.

## What it blocks

- **Redaction patterns:** `[pattern, replacement]` pairs, matched as whole words.
- **Repository names:** one column of a manifest, such as the work knowledge repository's list of
  repositories.
- **Organisation URLs:** each remote's host and organisation (`dev.azure.com/<org>`,
  `github.com/<org>`, `<org>.visualstudio.com`), from https and ssh remotes alike.
- **Secrets:** gitleaks on the staged changes. Without gitleaks the commit is refused.

Findings name the file, the line and the list, never the matched text, so an agent's transcript does
not repeat what was blocked. File names are checked as well as lines.

## Add it to a repository

1. `.githooks/pre-commit`, tracked in that repository:

   ```sh
   #!/bin/sh
   guard="$HOME/.agents/skills/commit-guard/scripts/guard.py"
   [ -f "$guard" ] || { echo "pre-commit: $guard is missing; apply the dotfiles." >&2; exit 1; }
   exec python3 "$guard" --staged
   ```

2. `chmod +x .githooks/pre-commit` and `git config core.hooksPath .githooks`.
3. Check what is already committed: `git ls-files -z | xargs -0 python3 <guard.py> --files`.

## Configure it

`~/.config/commit-guard/config.json`, or the path in `COMMIT_GUARD_CONFIG`. The shape is in
`scripts/guard.py`'s docstring. A word blocked by mistake goes in `allow`; when the manifest moves,
update its path here.

## Test it

`python3 -B scripts/test_guard.py`: invented names in a temporary repository; gitleaks is off there.
