# Distillation: what to keep, where it goes

How I turn finished work (an agent session, a research effort, a project) into records that someone, human or agent, will actually use later, and how the `distill` skill (named `distill-session` until 2026-10-25) applies that. Researched on 2026-10-23 from 19 web searches and 21 pages; one page (BetterEvaluation on after-action reviews) could not be read.

How each statement is known: a link means it comes from that source; **(inferred)** means my reasoning from those sources; **OPEN** means not yet settled.

## Bottom line

- Keep only what a future reader would otherwise get wrong or have to rediscover, write it conclusion first, and keep a pointer to the evidence underneath.
- Sort each kept item by two questions: who reads it next (an agent or me) and where it is true (this repository or everywhere). That gives four destinations plus "drop".
- Workspace items go to the repository's existing homes; failing that, to the parent knowledge repository's layout; failing that, the skill creates the standard layout below.
- Personal and generic knowledge is written in the session as raw, dated lines in the wiki's capture inbox, and the wiki's own triage files it later. The distill skill does not reason about where it fits in the wiki. **(inferred)**
- Rules meant to change how agents behave for me go where agents load them, not only into the wiki: in one small test, a wiki page alone carried a past decision into 0 of 8 later agent runs, against 7 or 8 of 8 when the rule text was delivered with the prompt ([comment by suwonleee](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f), one experiment).

## What good distillation is, for any source

These hold for distilling a session, a research effort, a meeting or a book.

1. **Design for a hurried, skeptical future reader.** "Future You is impatient and skeptical, demanding proof upfront that the time they spend reviewing notes will be worthwhile" ([Forte](https://fortelabs.com/blog/progressive-summarization-a-practical-technique-for-designing-discoverable-notes)). The tension is compression against context: "you cannot compress something without losing some of its context" (same page).
2. **Conclusion on top, evidence kept below.** Forte's top layer is "an informal executive summary at the top of the note, restating the key points in my own words", and the lower layers stay as a "safety net" because "you may be making the wrong decision about what's important" ([Forte](https://fortelabs.com/blog/progressive-summarization-a-practical-technique-for-designing-discoverable-notes)). For an agent, the evidence is a path, commit, command or URL.
3. **Compress in proportion to value.** Condense "only doing as much or as little as the information deserves"; only "a small number of notes" get the full summary ([Forte](https://fortelabs.com/blog/progressive-summarization-a-practical-technique-for-designing-discoverable-notes)). Most sessions should yield a few lines, and some none: Claude Code "doesn't save something every session" ([Claude Code docs](https://code.claude.com/docs/en/memory)).
4. **One concept per entry, and update the existing entry.** Notes factored by event or source "don't combine with the old ones to form a stronger whole: you just have a scattered set of notes" ([Matuschak](https://notes.andymatuschak.org/z2hQEhqWkdRLL9JUwfawZZx)). Builders of LLM-maintained wikis name near-duplicate pages "the default failure" and check the index before creating anything ([gist comments](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)).
5. **File by when it will be needed, not where it came from.** Ahrens' question: "In which context will I want to stumble upon it again?" ([quoted by Matuschak](https://notes.andymatuschak.org/z2hQEhqWkdRLL9JUwfawZZx)). A lesson is filed under the situation that should trigger it ("before running X"), not under the session that produced it. **(inferred)**
6. **Find lessons with the after-action review questions.** "What did you expect to happen? What actually did happen? Why did it happen? What will you do next time?", asking why at least twice, and recording what went well as well as what failed ([Pearce, RealKM](https://realkm.com/2020/02/28/lessons-learned-part-5-capture-using-after-action-reviews)). Reject a lesson that only states a fix, because "the expectation as phrased above embeds the solution in it" (same page).
7. **Give every lesson an owner and a re-read point.** "There is no point in doing AARs if the lessons identified in them aren't learned and applied in the future" ([Pearce](https://realkm.com/2020/02/28/lessons-learned-part-5-capture-using-after-action-reviews)). For agents, the re-read point is a file they load at the start: `AGENTS.md`, a skill, a rule. **(inferred)**
8. **Verify by reconstruction, not memory, and let the people who were there check it.** After-action guidance rests on "a reconstruction of the facts" and circulates a draft "for participants' comments before it is shared" ([IADB guidelines](https://publications.iadb.org/publications/english/document/Guidelines-for-Conducting-After-Action-Reviews.pdf), search snippet only).
9. **Watch for ritual.** "People reduce the living practice of AARs to a sterile technique" ([Wharton](https://executiveeducation.wharton.upenn.edu/thought-leadership/wharton-at-work/2021/07/after-action-reviews-simple-tool), snippet). If every run produces boilerplate, change the method.

## Distilling an agent session

**Keep** what a future session would otherwise get wrong:

- Corrections the user made, and any mistake made twice. Claude Code's triggers are "Claude makes the same mistake a second time" and "A new teammate would need the same context" ([Claude Code docs](https://code.claude.com/docs/en/memory)); agentskills.io calls gotchas "the highest-value content in many skills" ([best practices](https://agentskills.io/skill-creation/best-practices)).
- Facts the agent had to discover that the code does not show: decisions with their reasons, where outside information lives, traps in tools.
- Open work, with the condition that releases it.

**Drop** what the code, git history or existing instructions already say: Claude Code's auto memory skips "anything it can derive from the codebase" and "anything your CLAUDE.md files already say" ([Claude Code docs](https://code.claude.com/docs/en/memory)). Also drop the story of the session itself, since the file holds what stays true, "not a summary of today's work" ([Stulberg](https://hannahstulberg.substack.com/p/claude-code-for-everything-the-best-personal-assistant-remembers-everything-about-you), snippet), and anything the session showed to be wrong.

**Write each entry** as one concrete, checkable line: "Run `npm test` before committing", not "Test your changes" ([Claude Code docs](https://code.claude.com/docs/en/memory)). Give it a reason and a citation. GitHub's Copilot Memory stores each fact as subject, fact, citations and reason ([GitHub blog](https://github.blog/ai-and-ml/github-copilot/building-an-agentic-memory-system-for-github-copilot)) and uses "Only validated facts" ([GitHub docs](https://docs.github.com/en/copilot/concepts/prompting-and-context/copilot-memory)).

**Verify before writing.** Re-open each cited location; if "the code contradicts the memory, or if the citations are invalid", store a corrected version ([GitHub blog](https://github.blog/ai-and-ml/github-copilot/building-an-agentic-memory-system-for-github-copilot)). Then search the target file for the same concept and for contradictions, since "if two instructions contradict each other, Claude may pick one arbitrarily" ([Claude Code docs](https://code.claude.com/docs/en/memory)).

**Respect budgets.** Keep an always-loaded file "under 200 lines" because "longer files consume more context and reduce adherence" ([Claude Code docs](https://code.claude.com/docs/en/memory)); move detail into linked files.

**Ask before writing a rule.** Writing procedural memory "is significantly riskier than writing to episodic or semantic memory, as it can easily introduce bugs" ([CoALA](https://arxiv.org/html/2309.02427v3)). Facts and history may be written directly; new or changed rules and skills are shown as a diff and wait for a yes. **(inferred)**

**Something that must always happen** belongs in a hook or a check, not in prose: "write it as a hook instead" ([Claude Code docs](https://code.claude.com/docs/en/memory)).

## Knowledge types

The standard taxonomy for agent memory is CoALA's: working memory for the current task, and three long-term kinds: episodic ("experience from earlier decision cycles"), semantic ("knowledge about the world and itself") and procedural (code and prompts) ([CoALA](https://arxiv.org/html/2309.02427v3)). CoALA says nothing about scope. The tools add it: Cursor has project, user and team rules ([Cursor docs](https://cursor.com/docs/rules)); Copilot Memory has repository facts and user preferences ([GitHub docs](https://docs.github.com/en/copilot/concepts/prompting-and-context/copilot-memory)); Windsurf has workspace rules, global rules and workspace-bound memories ([Windsurf docs](https://docs.devin.ai/windsurf/plugins/cascade/memories)). In all three, only project-scope files travel with git.

So each kept item gets a **kind** and a **destination**:

| Kind | CoALA | Example |
| --- | --- | --- |
| fact | semantic | "The host stores sessions in SQLite; columns are added by `ALTER TABLE` migration" |
| rule | procedural | "Never push; commit locally" |
| procedure | procedural | "How to release: build, tag, sign, upload" |
| event | episodic | "Decided X on date Y because Z", "Z broke; cause; fix" |
| lesson | episodic, distilled | "Expected A, got B, because C; next time D". Promoted to a rule when it recurs |

| Who reads it next | True only in this repository | True everywhere |
| --- | --- | --- |
| An agent | **Workspace**: `AGENTS.md`, `.agents/` skills and instructions | **Personal agent layer**: `~/.agents/AGENTS.md` and personal skills, from this dotfiles repo |
| Me | **Workspace**: what is true now and dated history, in the repository's layout ([knowledge-layout.md](knowledge-layout.md)); my handoff in `~/.agents/state/<workspace>/state.md` | **Wiki**, through its capture inbox |

Routing, in order: **(inferred)**

1. True only for this session → drop.
2. True for anyone working in this repository and safe to commit there → workspace.
3. About me, my tools or my machine, or true in any repository → personal: agent-facing rules to the personal agent layer, everything else to the wiki.
4. True for this repository but not safe to commit (private or employer content in a public repository) → personal.
5. Fits two homes → store it once in the narrower one and link from the other. Cursor applies precedence across scopes rather than copying ([Cursor docs](https://cursor.com/docs/rules)).
6. Team or organisation scope (Cursor team rules, Windsurf system rules) belongs to admins: flag it, never write it.

## Folder layout

Settled on 2026-10-24 and described in [knowledge-layout.md](knowledge-layout.md): knowledge repositories follow PARA, with decisions and events as dated typed notes in the area or project they concern; standalone repositories keep `docs/`, `docs/decisions/` and `research/`. The kinds above map onto both: **(inferred)**

| Kind | Knowledge repository | Standalone repository |
| --- | --- | --- |
| rule | `AGENTS.md` | `AGENTS.md` |
| procedure | `.agents/skills/` | `.agents/skills/` |
| fact | `20-areas/`, `30-resources/` | `docs/` |
| event | `YYYY-MM-DD-slug.md` with `type: decision` or `type: event`, in its area or project | `docs/decisions/` for decisions; git history for the rest |
| lesson | the area's `gotchas.md` | `AGENTS.md` once it is a rule, else the handoff note |
| working | `10-projects/` or `00-inbox/research-<topic>/` | `research/` |

Why these names: `AGENTS.md` at the root is the one entry point the tools share ([agents.md](https://agents.md)), and `.agents/skills/` is a default skill path for VS Code, Copilot CLI and Cursor (checked 2026-10-17). Decision files follow MADR, which allows any folder ("MADR does not enforce any repository or directory organization structure", [MADR](https://adr.github.io/madr)). One known cost: Claude Code does not read "anything under a `.agents/` directory" ([Claude Code docs](https://code.claude.com/docs/en/memory)), so `AGENTS.md` links every folder it relies on.

**Lookup order** before writing anything: **(inferred; no source covers parent repositories)**

1. **This repository's declared homes.** Its `AGENTS.md` `Layout:` line and any homes it names for decisions, plans, gotchas or handoffs, even when they differ from the standard. Two homes for one kind means one goes stale.
2. **The parent knowledge repository.** If this repository sits inside another git working tree with the PARA layout (a product repository cloned inside a knowledge repository), write workspace items there, in the area for this product.
3. **Create the standalone layout**, only the folders this run needs, and link them from `AGENTS.md`.
4. In a git worktree, write to tracked files only: "a gitignored `CLAUDE.local.md` only exists in the worktree where you created it" ([Claude Code docs](https://code.claude.com/docs/en/memory)).

## Getting personal knowledge into the wiki

The wiki is an Obsidian vault filed with PARA (projects, areas, resources, archive), following Forte's CODE: "Capture, Organize, Distill, and Express" ([Forte](https://fortelabs.com/blog/basboverview)). Its one rule is "capture without classifying"; a triage step later files each capture line into PARA, with my approval, preferring an existing note.

Three ways the skill could feed it:

1. **Write straight into curated wiki notes.** Closest to Karpathy's LLM wiki, where "the LLM owns this layer entirely" ([gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)). But Karpathy ingests "one at a time and stay[s] involved"; a session distill is many unvetted items, run from another repository without the wiki's index loaded, which is where near-duplicates come from. It also skips my approval.
2. **Append raw lines to the wiki's dated capture inbox; the wiki's triage files them later.** Every curated setup read puts a holding step before the curated notes: Forte's Inbox, "a temporary holding area where new items accumulate" ([Forte](https://fortelabs.com/blog/basboverview)); an agent that "creates organized notes in a designated folder for my review" ([myyearindata](https://www.myyearindata.com/posts/obsidian-second-brain-ai-agents)); "inbox/ ... in front" of an LLM wiki ([gist comments](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)).
3. **Write a holding file outside the wiki; a wiki-side ingest skill pulls it.** Mirrors Karpathy's immutable raw layer. Needed only if sessions run where the wiki cannot be written; otherwise it adds a second queue in front of the inbox.

**Recommended: 2.** **(inferred)** The distill skill only sorts and writes; the wiki's triage decides where things fit, with the wiki's index and conventions loaded and my approval. In one builder's pipeline, deciding where things go took "about 72% of the LLM tokens" of ingest ([gist comments](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f), one corpus), cost that does not belong in a coding session.

Each inbox line carries what triage needs: **(inferred)**

- the claim, conclusion first, in one line;
- the session's date and time, because "Timestamp by send time, not processing time" ([gist comments](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f));
- the source: repository alias and a path, commit or URL;
- a `#distilled` tag so triage can tell these from hand captures, and a kind (`fact`, `lesson`, ...).

Rules for the write: append through the wiki's own capture command so the file shape stays valid; write the raw line before any rewording, since "capture pipelines should fail open" ([gist comments](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)); report the written path; and run the redaction and secret checks first. The sources offer only a lint for "secret-shaped text" (same thread), so that gate is my own design. Never commit or push the wiki; its own rules require approval.

**Case against 2:** if sessions produce more lines than weekly triage clears, the inbox becomes the "swamp you cannot search" ([iwoszapar](https://www.iwoszapar.com/p/para-method-vs-building-a-second-brain), snippet). Watch the inbox for two or three weeks; if it grows, filter harder at distill time before changing the design.

## Open

- **OPEN** Whether the wiki repository is private. It decides whether knowledge learned at work may be captured there at all, and under which data-classification rules.
- **SETTLED 2026-10-24** Where personal agent rules land: the split rule in [knowledge-layout.md](knowledge-layout.md#which-layer-owns-what). Rules an agent reads go to this repository's `dot_agents/` (proposed as a diff); their reasoning goes to the wiki.
- **OPEN** Whether the wiki's triage skill should learn the `#distilled` tag (for example, check "already in PARA" before proposing).
- Not covered by any source read: parent-repository lookup, distilling from a finished transcript (vendors describe memory written during a session), expiry rules beyond Copilot's 28 days unused ([GitHub docs](https://docs.github.com/en/copilot/concepts/prompting-and-context/copilot-memory)), and redaction of employer identifiers.
