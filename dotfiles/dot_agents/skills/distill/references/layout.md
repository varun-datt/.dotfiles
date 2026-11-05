# Layout

Two families. Read the repository's `AGENTS.md` for its `Layout:` line first. Create only the folders this run needs, and add a one-line link to each from the root `AGENTS.md` (create `AGENTS.md` if missing: a one-line purpose, the `Layout:` line, then the links). Rationale: the dotfiles repo's `docs/knowledge-layout.md`.

## Knowledge repository (`Layout: knowledge (PARA)`)

| Path | Holds | Kind |
| --- | --- | --- |
| `AGENTS.md`, `.agents/skills/` | always-on rules; procedures | rule, procedure |
| `00-inbox/` | not sorted yet; `research-<topic>/` until it has a project | working |
| `10-projects/<project>/` | work with a goal and an end, including research | working, event |
| `20-areas/<area>/` | what is true now about a responsibility | fact, event |
| `30-resources/<topic>/` | topics, not tied to a responsibility | fact |
| `40-archive/` | finished projects and research | any |
| `<area or project>/YYYY-MM-DD-slug.md` | a decision or event, with `type: decision` or `type: event` | event |
| the repository's own area, `gotchas.md` | one line per wrong answer: date, wrong answer, right rule, what now prevents it | lesson |

Decisions and events live in the area or project they concern; repository-wide ones go in the repository's own area. There is no timeline folder: the timeline is a generated view (Dataview, or the repository's dashboard). Keep any old decision number as `id:` in front matter.

## Standalone repository (`Layout: standalone`)

| Path | Holds | Kind |
| --- | --- | --- |
| `AGENTS.md`, `.agents/skills/` | always-on rules; procedures | rule, procedure |
| `docs/<topic>.md` | what is true now | fact |
| `docs/decisions/NNNN-slug.md` | a choice and why (MADR) | event |
| `docs/gotchas.md` | one line per wrong answer, as in a knowledge repository | lesson |
| `research/YYYY-MM-DD-topic.md`, `research/YYYY-MM-DD-topic/` | dated investigations and their probes | working |

Other events stay in git history; a lesson moves to `AGENTS.md` once it recurs.

A fact lives in one place. When a lesson hardens into a rule, the rule moves to `AGENTS.md` or `.agents/`, and the dated note keeps the event and a link. Dated notes are not edited once written; a superseded one gets a new note that links back. Mark each claim VERIFIED, INFERRED or OPEN.

## Decision note

```markdown
---
type: decision
status: accepted   # or: superseded by <link>
---
# <decision, as a statement>

Context: <the problem, in two or three sentences>.
Decision: <what was chosen>.
Why: <the reason, and the options passed over>.
Consequences: <what this makes easier or harder>.
```

In a knowledge repository, add the repository's required front matter (title, dates, tags) and name the file `YYYY-MM-DD-slug.md`. In a standalone repository, name it `NNNN-slug.md` and put the date in the body.

## Event note

```markdown
# <what happened>, YYYY-MM-DD

Expected: <...>. Happened: <...>. Why: <cause, asked twice>. Fix: <...>.
Next time: <the rule, and where it now lives>.
```

**Postmortem option.** If the event is an incident that meets any common postmortem trigger (user-visible downtime or degradation beyond a threshold, data loss of any kind, on-call intervention such as a rollback or rerouting traffic, resolution time above a threshold, or a monitoring failure, meaning it was found by hand), offer Google SRE's postmortem template instead and let the user choose. Source: https://sre.google/sre-book/postmortem-culture/
