# Refreshing the test cases

The cases in `scripts/fixtures/cases.json` are invented, but their mix copies how search is really
used: who searches (a person in a palette or search box, an agent's own search call, a person's
message to an agent), in which space, and with what shape of query. Usage drifts, so the mix must
be measured again and the cases changed to follow it. The cases and the scoring scripts live only in
the chezmoi source, so the paths below are relative to `$(chezmoi source-path)/dot_agents/skills/kb`.

## When

- About every three months.
- When a new way to search appears: AMC's palette over sources, an agent tool, a new editor.
- Before the default engine or `auto`'s routing changes.

## Steps

1. Measure: `python3 -B scripts/usage_shapes.py --sources-file ~/.config/kb/sources.json --json /tmp/usage.json`.
   It reads chat transcripts, Copilot CLI logs, the editor's search history and the Copilot
   session store, read-only, and prints counts and shares only, never query text.
2. Compare with the last measurement below. A share that moved by 10 points or more, a new caller
   or a new space means the mix is stale.
3. Change `scripts/fixtures/cases.json` to match: add or rewrite cases in the classes that moved,
   keep the class list in sync, and keep every word invented (Larkspur Freight, `example.com`).
   Request cases must match the measured length profile, noise included.
4. `python3 -B scripts/fixtures/check_cases.py` must print OK.
5. `python3 -B scripts/eval.py --by class` for every mode. If the default loses a cell, change
   `engines_for` in `kb.py` only after step 6 agrees.
6. Check against real usage, in a temporary folder outside every repository: take the person's
   messages from the session store, label each with the knowledge files an agent first read in
   that turn, copy the sources the labels come from, and score the modes there, once with each
   message limited to its own source and once with every source at once. Delete the copy
   afterwards. Real queries and paths never enter the fixtures.
7. `python3 -B scripts/eval.py --write-baseline`, then update the measurement below with the date.

## Why step 6 exists

On 2026-10-24, an `auto` tuned on the mock suite alone sent sentences to BM25 plus embeddings and
scored 69 of 75 there, but on 93 real messages it found 11 where embeddings alone found 27. The
mock requests were shorter and cleaner than real messages, and prose with a bracket or a `$` was
routed as a regex. The request cases were lengthened to the measured profile and the regex test
tightened; both checks then agreed (64 of 75 mock, 27 of 93 real).

On 2026-10-25 the same 93 messages, scored against all three sources at once instead of each
message's own, found 12 in the top 5 and never put the right file first. Results were merged per
source, so each source's best hit tied at reciprocal rank 1 and the first source listed always won.
Merging each engine's hits across sources by score first raised that to 27, with 10 first; scoring
each message against its own source stayed at 29 (11 first). Step 6 now scores both ways.

Of the 64 misses left, the first 15 read one by one were mostly label noise: the file an agent
opened first was often a side errand (a message about a tool path labelled with an infographic
draft). None of the 15 shared a query shape that a routing change would catch.

## Last measurement, 2026-10-24

Agents' own searches (VS Code transcripts and Copilot CLI logs):
- Nearly all are regex or keyword searches: terminal `grep` and `rg` (18,557 calls), the editor's
  grep tool (2,632), file-name searches (411 in the editor, 298 in the CLI). Semantic search: 11
  calls. `ck`, `qmd` or `kb` from the terminal: 60, nearly all from the 2026-10-24 trials.
- The editor's grep tool: median 2 words, 86% regex, median 4 alternatives (`a|b|c|d`), 48% hold
  an identifier, 16% an acronym, 7% a number; 70% are followed by a file read within three calls.
- Terminal `grep` and `rg`: median 2 to 3 words, one pattern, 19 to 35% identifiers.

A person in a search box (the editor's search history, 83 queries): median 1 word, up to 41%
identifiers, natural language 7% or less. Whether the box was in regex mode is not recorded.

A person's messages to agents (session store, 2,425 messages): median 40 words (25th percentile 19,
75th 84, 90th 162); 30% name a file; 11% hold a question mark; 7% a list.

Not yet measured, because no log exists: AMC's palette searches and kb's own calls. Add them to
`usage_shapes.py` when they are logged.
