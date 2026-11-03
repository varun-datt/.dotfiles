# Rules for a standalone repository

A repository whose `AGENTS.md` says `Layout: standalone.`: an application, the dotfiles. The
personal instructions still apply, and this repository's own rules win over these.

- Keep only what describes this repository's code or how to work in it, must change in the same
  commit as the code, and is needed by any reader without extra access: `README.md`, `AGENTS.md`,
  `.agents/skills/`, `docs/`, `docs/decisions/` (MADR). Anything else, and anything unsure, goes
  to a knowledge repository.
- No work content: these repositories may be public.
