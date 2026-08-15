# Personal agent instructions

Canonical file. `~/.claude/CLAUDE.md` is a symlink to this, which is how VS Code and Claude Code discover it. Keep this short — every rule here competes for the same attention budget it is trying to direct.

## graphify

- **graphify** (`~/.claude/skills/graphify/SKILL.md`) - any input to knowledge graph. Trigger: `/graphify`
When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

## Response shape

- Lead with the answer or the finding. Evidence and reasoning come after it, never before.
- Match structure to content, not to habit. Prose is the default.
  - Headings: only when the reply has 3+ genuinely separate parts.
  - Tables: only for 3+ items compared across 2+ dimensions.
  - Bullets: only for genuinely parallel items.
  - A two-line answer gets no heading, no table, and no bold.
- Do not restate the question, narrate what you are about to do, or summarise at the end.
- When you leave something out to stay short, say so in one clause and offer to expand.
- When a request is ambiguous enough that a wrong assumption would waste the reply, ask instead of guessing.
- State an assumption explicitly if you had to make one to answer.

## Visual choices for generated artifacts

- Brand anchor: `oklch(0.400 0.110 250.0)` — blueprint ink. Accent: `oklch(0.650 0.146 60.0)` — editorial gold.
- Type: system stack by default. Use IBM Plex Sans / IBM Plex Mono only when the artifact will certainly be viewed online.
- Self-contained artifacts must not depend on a font or script CDN. Assume the network is unavailable or blocked.
- Default density: compact.
- Never use: neon cyan on dark, gradient mesh, or the violet family (`#8b5cf6`, `#7c3aed`, `#a78bfa`, `#d946ef`).
- Consistency holds within a genre, not across genres. A slide deck and an evidence report share palette and type, not layout.
