---
name: kb
description: "Searches the knowledge and code sources listed in ~/.config/kb/sources.json (a personal wiki, a work knowledge repo, product repos) by pattern or by meaning, through one JSON contract. Use to look something up from a person's question, or to find notes, decisions, runbooks or code by meaning. It searches the source you are working in; name any other with --source."
argument-hint: "<query> [--source NAME] [--mode auto|regex|lex|sem|hybrid|fused]"
---

# kb

One search over every source in the sources file. Agents, scripts and the AMC app call the same
command and get the same fields back, so the engine behind it can change without changing callers.

## Use it

```sh
python3 ~/.agents/skills/kb/scripts/kb.py search "<query>" [--source NAME ...] [--json]
python3 ~/.agents/skills/kb/scripts/kb.py sources
python3 ~/.agents/skills/kb/scripts/kb.py index [--source NAME ...]
```

- **Query as you would think it.** `auto`, the default, picks engines by the query's shape, as the
  scenario suite measured:
  - a regex (`RetryPolicy|maxAttempts`, `\bDLQ\b`) runs ripgrep;
  - up to three words (`DLQ`, `dwell report`, an identifier) runs ripgrep and BM25;
  - a longer question or a person's whole message runs search by meaning.
- `--mode regex` forces an exact pattern; `lex`, `sem`, `hybrid` and `fused` force one engine.
- **Scope:** without `--source`, kb searches only the source you are working in, the one whose
  folder holds the current directory, so work content does not end up in wiki notes or the
  reverse. Name any other source with `--source`, repeated for more; `kb.py sources` lists them.
  Outside every source, kb exits with status 2 and asks for one.
- **Each hit:** `{source, path, line, end, title, snippet, score, engines}`. `path` is relative to
  the source's root; `line` and `end` bound the matching lines; `engines` says which engines found it.

## Set up

- **Sources file:** `~/.config/kb/sources.json`, or the path in `KB_SOURCES`. Shape:
  [`scripts/sources.example.json`](scripts/sources.example.json). It is data, not code: adding a
  source changes no script. Each source is searched in place and its ignore rules are honoured.
  `paths` limits a source to some of its folders, for a root that holds other repositories.
- **Engines:** `rg` is required. `ck` (BM25 and embeddings) is found on `PATH` or through `KB_CK`;
  without it every mode falls back to regex and says so.
- **Indexes:** ck keeps one index per folder (the root, or each folder in `paths`) under
  `~/.cache/kb/ck`, or `KB_INDEX_DIR`, and writes nothing into the folder. `kb.py index` builds or
  refreshes them; run it after adding a source. Until a folder has one, kb searches it by regex and
  says so. A single file listed in `paths` is always searched by regex.
  - Why one ck run per folder: given several folders, ck 0.8.1 indexes their common parent (for a
    work folder holding product repos, all of them), and `ck --index A B` indexes only `B`.

## Test it

- `python3 -B scripts/test_kb.py`: the contract, the routing and, when ck is present, the scenario
  suite against its baseline.
- `python3 -B scripts/eval.py --by class`: hit@1, hit@5, MRR and latency for every space (wiki,
  work, product) and caller (palette, agent, request), and for each case class.
- The cases and corpus in `scripts/fixtures/` are invented (a fictional freight company); their mix
  copies measured real usage. Never add real content to them.

## Change the engine

Any tool that prints this contract can be scored: `eval.py --engine "cmd:<command>"` runs
`<command> QUERY SOURCES` with `KB_SOURCES` set. A replacement must hold `baseline.json` in every
cell (`eval.py --check`) before it becomes the default. When AMC takes the search over, its command
is scored the same way.

## Keep the cases current

Usage drifts, so the mix of cases must follow it:
[`references/refreshing-cases.md`](references/refreshing-cases.md).
