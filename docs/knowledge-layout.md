# Knowledge layout: where each kind of knowledge lives

Which folder each kind of knowledge goes in, for my two kinds of repository, and which layer (personal agent files, wiki, repository) owns what. Settled with the owner on 2026-10-23 and 2026-10-24. The research behind it, and the trade-offs, are in [distillation.md](distillation.md).

## Two families

**Knowledge repositories** (the wiki, a work knowledge repository) follow PARA ([Forte](https://fortelabs.com/blog/basboverview)): `00-inbox/`, `10-projects/`, `20-areas/`, `30-resources/`, `40-archive/`, plus `README.md`, `AGENTS.md` and `.agents/skills/` at the root. Number prefixes keep these folders above the cloned repositories, whose names start with a letter.

**Standalone repositories** (an application, these dotfiles) follow the common standards: `README.md`, `AGENTS.md`, `.agents/skills/`, `docs/` for what is true now, `docs/decisions/` for why (one [MADR](https://adr.github.io/madr) file per decision), and `research/` at the top level for dated investigations (`YYYY-MM-DD-topic.md`, probes in `YYYY-MM-DD-topic/`). There is no how-to or explanation folder: procedures are skills.

Each repository says which family it is in one line of its `AGENTS.md`: `Layout: knowledge (PARA).` or `Layout: standalone.`

| Kind of knowledge | Knowledge repository | Standalone repository |
| --- | --- | --- |
| Rules that always apply | `AGENTS.md` | `AGENTS.md` |
| How to do something | `.agents/skills/` | `.agents/skills/` |
| What is true now | `20-areas/` (responsibilities), `30-resources/` (topics) | `docs/` |
| Why it is like this | dated `type: decision` notes in the area or project | `docs/decisions/NNNN-slug.md` |
| What happened | dated `type: event` notes in the area or project | git history; a `docs/` page only if needed |
| Open questions, research | `10-projects/<topic>/`; `00-inbox/research-<topic>/` until it has a project | `research/` |
| Finished work | `40-archive/` | git history |
| Not sorted yet | `00-inbox/` | the plan or issue tracker |

## Research in a knowledge repository

Research is the project it serves, in `10-projects/`. Until it has one it waits in `00-inbox/research-<topic>/`. When it is finished it moves to `40-archive/`. A repository that keeps answered questions on purpose (as a record of what was asked) keeps them in the archive rather than deleting them.

## Dated history: typed notes, not a timeline folder

In a knowledge repository, a decision or event is a note named `YYYY-MM-DD-slug.md` inside the area or project it concerns, with `type: decision` or `type: event` in its front matter. Decisions and events that concern the whole repository go in an area for the repository itself, together with its `gotchas.md` (one line per wrong answer: date, wrong answer, right rule, what now prevents it).

There is no timeline folder. The timeline is a generated view over these notes: a Dataview query in an Obsidian vault, the repository's own dashboard elsewhere. When decisions had numbers before, the number is kept as `id:` in the front matter so old references still resolve.

A decision note uses MADR's sections: context, decision, why (with the options passed over), consequences. An event note says what happened, why, what was done, and what to do next time.

**Postmortem option.** For an event that is an incident, the agent offers Google SRE's postmortem template instead of the short event note when the incident meets any of the common postmortem triggers: user-visible downtime or degradation beyond a threshold, data loss of any kind, on-call intervention (rollback, rerouting traffic), resolution time above a threshold, or a monitoring failure, usually meaning the incident was found by hand ([Google SRE book](https://sre.google/sre-book/postmortem-culture/)). Any stakeholder may also ask for one (same page). Otherwise the short event note is enough.

## Which layer owns what

| Knowledge | Goes to |
| --- | --- |
| What a program or agent reads to act: rules, skills, settings | dotfiles (this repository) |
| What I read to think, learn or grow | the wiki |
| A preference | its setting in dotfiles; its reasoning in the wiki |
| Machine state and caches | neither |
| Anything private or from work | never this public repository |

## How agents find this

- My personal `AGENTS.md` carries a short routing table: which kind of knowledge goes where, and the rule to read a repository's `Layout:` line first.
- Each repository's `AGENTS.md` has its `Layout:` line and links its own homes.
- The `distill-session` skill applies the layout when a session ends ([references/layout.md](../dotfiles/dot_agents/skills/distill-session/references/layout.md)).
- A pre-commit check in this repository blocks secrets and employer identifiers. Agent hooks wait until use shows a need.
