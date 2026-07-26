# Notes for AI agents

## Comments

Don't over-comment. Keep inline comments minimal and only where the code itself can't make intent clear. If there's an important "why" worth capturing (rationale, trade-offs, non-obvious design decisions), put it in [README.md](README.md) — not scattered across the dotfiles. The code should stay clean; the README is the single place for the reasoning.

## Chezmoi validation

Run `chezmoi execute-template` and `chezmoi apply --dry-run` for read-only validation. Do not run a non-dry-run `chezmoi apply` unless the user explicitly asks; the user applies changes after review by default.
