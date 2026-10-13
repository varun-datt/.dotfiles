# Notes for AI agents

## Comments

Don't over-comment. Keep inline comments minimal and only where the code itself can't make intent clear. If there's an important "why" worth capturing (rationale, trade-offs, non-obvious design decisions), put it in [README.md](README.md) — not scattered across the dotfiles. The code should stay clean; the README is the single place for the reasoning.

## Prose formatting

Don't hard-wrap prose at a fixed column. Keep each paragraph and bullet on a single line and let the editor soft-wrap.

## Commit messages

Keep them concise: a short subject line, plus a body only when the diff can't explain itself. Every line has to earn its place; don't list each file touched or narrate the process.

This repo is public. Never reference another repo's issues, PRs, commits, or people in commit messages: no `owner/repo#123`, `owner/repo@sha`, bare `#123`, issue/PR/commit URLs, or `@user`. GitHub posts them as backlinks on the other repo, and a force-push does not remove them. Describe the upstream change in words instead ("fixed upstream, ships in 0.7.0").

## Script output

Keep log messages in scripts to a minimum. Add one only when it earns its place, such as an error, a warning, or a step the user must act on. Don't echo progress or success.

## Chezmoi validation

Run `chezmoi execute-template` and `chezmoi apply --dry-run` for read-only validation. Do not run a non-dry-run `chezmoi apply` unless the user explicitly asks; the user applies changes after review by default.
