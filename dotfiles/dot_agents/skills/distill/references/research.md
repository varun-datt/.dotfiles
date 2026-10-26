# Research mode

A research, spike, probe or scratch folder is the fleeting tier: it exists to be consumed. The job is not to summarise it but to decide, finding by finding, whether anything survives, and to leave the discard reasoning behind so nobody covers the same ground again.

**There is no target ratio.** How much survives depends on what the folder is made of. Agent-fetched public documentation may leave almost nothing; original analysis of code or data nobody else has read may leave most of itself. Report the proportion kept with what the folder turned out to be made of and why that gave this ratio. An unexplained ratio is the only failure.

## Step 2 additions: the keep test

Apply to every finding, in order; the first "no" ends it.

1. **Would the reader reach it from official docs in a few minutes?** Then discard it, or reduce it to a link: a local copy of upstream docs goes stale while the upstream stays current ([Google documentation guide](https://google.github.io/styleguide/docguide/best_practices.html): "Duplication is Evil"). Restated public material survives only when it was the cited reason for a change that shipped (keep the minimum, with the link), when it will be reached for again and was hard to find, or when the upstream is unstable, paywalled or likely to vanish.
2. **Is it a fact that was hard to get, or a procedure someone will repeat?** Discard spikes that answered a question; keep spikes that show how to do a task ([Shore, spike solutions](https://www.jamesshore.com/v2/books/aoad1/spike_solutions)).
3. **Can you say why it mattered and what it cost to find?** If not, drop it or link it.
4. **Is it still true?** Verify first (below).

Almost always kept: a trap (something that returns a plausible, confident, wrong answer), a gap in our own artefacts no upstream doc will mention, a negative result with its evidence, and the reason a number in code or config is that number. Almost never kept: restated docs and field tables, a second copy of a schema or config the repository already has, generic tuning advice where a measured local decision exists, advocacy with no decision attached, the original plan and any "known gaps" list, and tool exhaust.

When unsure, discard only what can be fetched again. Original analysis, negative results and anything from an environment you may not reach again cannot be recovered by re-fetching: raise each such item with the user one at a time, with your reasoning and a recommendation. A batch gets waved through.

## Verify before importing

Treat the folder as a suspect, not a source. Agent-written research usually gets mechanisms right and versions, dates and "current as of" claims wrong.

- Check it against itself first: two "current" versions, a default stated two ways, a gap list the repository contradicts.
- Re-fetch every version, date and default from upstream and note when you fetched it.
- Check every claim about our own code against the code, not the folder.
- Look a second time with a differently shaped tool (enumerate the type rather than re-read the prose).
- A readback equal to the default proves nothing; probe with a distinctive value first. A correct mechanism can sit on a code path production never takes; establish the path first.
- Mark what survives VERIFIED, INFERRED or OPEN; an OPEN item carries the exact command that would settle it.

## Step 4 addition: one fact, one home

Before declaring done, grep a distinctive word of each kept value across every file touched and read the hits: a phrase wrapped across lines counts as zero, and a substring inflates the count.

## Step 6 additions: before removing the folder

All must hold:

- [ ] The durable write has landed on disk.
- [ ] Every kept claim is marked VERIFIED, INFERRED or OPEN.
- [ ] The discard reasoning is written at the end of the new record, batched by reason, with the folder's size before and after.
- [ ] Each distinctive value appears once across the files touched.
- [ ] The new record is linked from where someone would look for it.

Then follow the repository's layout: archive the folder where it keeps finished research, or delete it. Deleting a tracked folder is reversible; an untracked or ignored folder is gone for good, so ask first.

Where the sources disagree: Zettelkasten destroys the fleeting tier, while Forte keeps everything because "you may be making the wrong decision about what's important" ([Forte](https://fortelabs.com/blog/progressive-summarization-a-practical-technique-for-designing-discoverable-notes)). Deleting is a choice that holds only while the checklist above holds. If deleted folders are asked for again more often than the distilled records are read, archive instead.
